# -*- coding: utf-8 -*-
"""钟馗·舆情看板 —— 15 分钟实机演示的社区舆论数据看板。"""
import html
from collections import Counter
from pathlib import Path

import streamlit as st

from config import ACCENT, ACCENT2, CSS, GOLD, SENTI_CN, SENTI_COLOR, THEME_COLOR

st.set_page_config(page_title="钟馗·舆情看板", page_icon="◆", layout="centered",
                   initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)

ROOT = Path(__file__).parent
DEMO_SOURCE = "Demo 数据 · 钟馗实机演示"
UPLOAD_SOURCE = "上传我的 CSV"


# ---------------------------------------------------------------- UI helpers
def masthead(kicker, title, sub):
    st.markdown(
        f'<div class="masthead"><div class="kicker">{kicker}</div>'
        f"<h1>{title}</h1><div class=\"sub\">{sub}</div></div>",
        unsafe_allow_html=True,
    )


def sec(num, title, sub=""):
    st.markdown(
        f'<div class="sec-title"><span class="num">{num}</span><h2>{title}</h2></div>'
        + (f'<p class="sec-sub">{sub}</p>' if sub else ""),
        unsafe_allow_html=True,
    )


def kpi_row(items):
    cells = "".join(
        f'<div class="kpi"><div class="v">{v}</div><div class="l">{l}</div>'
        + (f'<div class="n">{n}</div>' if n else "")
        + "</div>"
        for v, l, n in items
    )
    st.markdown(f'<div class="kpi-row">{cells}</div>', unsafe_allow_html=True)


def editorial_table(headers, rows, aligns=None):
    aligns = aligns or ["left"] * len(headers)
    th = "".join(f'<th style="text-align:{a}">{h}</th>' for h, a in zip(headers, aligns))
    body = ""
    for r in rows:
        body += "<tr>" + "".join(
            f'<td class="{("num" if a == "right" else "")}">{c}</td>' for c, a in zip(r, aligns)
        ) + "</tr>"
    st.markdown(f'<table class="editorial"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>',
                unsafe_allow_html=True)


def chart(fig):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def legend_chips(items):
    """图表上方的色块图例，替代图内 legend，避免压住柱子。"""
    st.markdown(
        "".join(
            f'<span class="chip"><span style="display:inline-block;width:9px;height:9px;'
            f'background:{color};margin-right:6px"></span>{html.escape(label)}</span>'
            for label, color in items
        ),
        unsafe_allow_html=True,
    )


def word_chips(pairs):
    if not pairs:
        return '<span class="note">无</span>'
    return "".join(
        f'<span class="chip">{html.escape(w)}'
        f'<span style="color:#a99f90;margin-left:4px">{n}</span></span>'
        for w, n in pairs
    )


@st.cache_data(show_spinner=False)
def _platform_rows(platform):
    from data import load_demo
    d = load_demo()
    if platform == "B站弹幕":
        return d["danmaku"]
    src = d["comments"]
    return src if platform == "全部平台" else src[src["platform"] == platform]


@st.cache_data(show_spinner=False)
def _label_words(platform, theme, label):
    import tokenizer as T  # 延迟加载 jieba 词典，避免拖慢首屏
    src = _platform_rows(platform)
    src = src[(src["label"] == label) & (src["theme"] == theme)]
    counter = Counter()
    for text in src["text"]:
        counter.update(T.tokens(text, drop_generic=True))
    return counter, len(src)


@st.cache_data(show_spinner=False)
def rep_words(platform, theme, limit=12):
    """主题代表词：先去掉“每个主题都会出现”的产品名与泛化词，再按词频排序。"""
    out = {"n": {}, "words": {}}
    for key in ["positive", "neutral", "negative"]:
        sub, n_sub = _label_words(platform, theme, key)
        items = [(w, k) for w, k in sub.items() if k >= 2]
        items.sort(key=lambda x: -x[1])
        out["words"][key] = items[:limit]
        out["n"][key] = n_sub
    return out



def fmt_pct(x, digits=1):
    return f"{x * 100:.{digits}f}%"


def mmss(sec):
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


PLATFORM_META = {
    "小黑盒": ("战斗评估 + 原创性质疑", "先立新作锚点，用新作的差别回应换皮争议"),
    "小红书": ("战斗 + 画面审美", "强调画面质感：光照、材质、场景"),
    "微博": ("战斗 + 期待表态", "放预约入口 + 定档信息，便于转发扩散"),
    "B站": ("战斗 + 技术/角色", "角色特写与设定图优先，留出二创空间"),
    "B站弹幕": ("仪式玩梗为主", "保留仪式梗生态，但不要把梗当评价"),
}


# ---------------------------------------------------------------- 项目说明与摘要
def _summary_text():
    """摘要 md 原文，去掉首行一级标题，避免与页头重复。不做缓存，改 md 后刷新即可生效。"""
    lines = (ROOT / "reports" / "executive-summary.md").read_text(encoding="utf-8").splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def page_brief(d=None):
    masthead("BRIEF / 00", "项目说明与摘要",
             "先说这份看板做了什么、数据从哪来，再给这次演示的结论；文末可下载 PDF 摘要。")
    st.markdown(_summary_text())
    pdf = ROOT / "reports" / "executive-summary.pdf"
    if pdf.exists():
        st.download_button("下载摘要 PDF", pdf.read_bytes(),
                           file_name="钟馗实机演示_舆情摘要.pdf", mime="application/pdf")
    st.markdown(
        '<p class="note">本页文字即摘要 PDF 的内容；要核对数字，去「数据与口径」翻原始明细。'
        '文字先出、图表后加载，是为减少首屏等待。</p>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- 概览
def page_overview(d):
    import charts as C
    from data import theme_overall
    stats = d["stats"]
    themes = d["themes"]
    overall = theme_overall(themes)
    masthead("COMMUNITY INTELLIGENCE / 01",
             "钟馗实机演示 · 舆论结构总览",
             "通过爬虫采集在b站、小黑盒、微博、小红书中官号最新 15 分 53 秒实机演示中评论 11,280 条 ＋ b站弹幕 24,733 条")

    st.markdown('<p class="note">加载提示：首次打开、刷新或切换页面时，图表与数据需要十几秒加载。'
                '若白屏或转圈超过 10 秒、或提示 TypeError、乱码，请按 Ctrl + Shift + R 强制刷新；'
                '多刷 1–2 次即可恢复，已缓存的模块第二次会更快。</p>', unsafe_allow_html=True)

    st.markdown(
        '<div class="card"><h4>数据来源</h4>'
        '<p class="note">针对黑神话钟馗最新 15 分 53 秒实机演示，爬取 B 站、微博、'
        '小红书、小黑盒上官号实机演示视频下评论与b站弹幕，逐条打上正向 / 中性 / 负向三种情感标签'
        '，再把文本聚成 13 个主题进行分析。清洗后可用文本共 36,013 。</p></div>',
        unsafe_allow_html=True)

    kpi_row([
        ("1,359.7 万", "B站播放", "点赞 97.1 万 · 评论 11.6 万 · 转发 50.2 万"),
        ("239 万", "微博话题阅读", "点赞 1.5 万 · 评论 1801 · 转发 3430"),
        ("1.81 万", "小黑盒点赞", "评论 7288 · 转发 7288"),
        ("4.8 万", "小红书点赞", "评论 4184 · 转发2.9w"),
    ])

    st.markdown(
        '<div class="verdict"><span class="tag">核心判断</span><br>'
        "播放与互动都在头部量级，<b>实机演出曝光度较高</b>。但文字层面多数人只是打卡和附和社区情绪："
        "出现最多的 <b>8 条弹幕</b>（“来了来了”“帅”“牛逼”）就占全部弹幕的 <b>64.1%</b>——"
        "<b>观众围观不等于认同作品内容</b>。<br>"
        "实机演示的主题信息主要来自两处：B站 <b>186 条百字长评</b>，和小黑盒的战斗类讨论。<br>"
        "一句话总结：<b>最关注战斗，最认可画面与音乐，最分裂的是角色与战斗</b>。"
        "风险点在“像不像悟空”的区分度担忧，以及穿模、音效复用这类制作精度，对剧情讨论较少。"
        "</div>",
        unsafe_allow_html=True,
    )

    n_themes = int(themes[themes["theme"] != "未建模"]["theme"].nunique())
    kpi_row([
        (f"{stats['comments']:,}", "评论总量", "四平台 · 45.6% 为二级评论"),
        (f"{stats['danmaku']:,}", "弹幕总量", "单支视频 · 953 秒"),
        (f"{int(stats['danmaku_per_min']):,}", "弹幕 / 分钟", "事件级密度"),
        (f"{n_themes}", "统一主题", "547 簇归并"),
    ])

    sec("01", "两个结构信号", "一级评论和二级评论是两种人：主楼表态，情感色彩鲜明，楼中楼多为讨论争议。")
    legend_chips([("一级评论", ACCENT), ("二级评论", GOLD)])
    c1, c2 = st.columns(2)
    with c1:
        chart(C.fig_level_positive(d["summary"]))
        st.markdown('<p class="note"><b>一级评论正向占比远高于二级评论。</b> 微博一级正向 41.8%，B站一级 42.5%；但 B站二级负向 12.8%，'
                    '已反超一级的 5.9%。</p>', unsafe_allow_html=True)
    with c2:
        chart(C.fig_theme_variance(overall))
        st.markdown('<p class="note">分歧最大的六个主题集中在 0.41–0.49，彼此差距很小，排名不必细究；'
                    '有用的是方向：方差可能来自平台内正负双方讨论，也可能来自不同平台存在的情感差异。<b>角色形象、战斗打击感在平台之间正负翻转，说明不同平台观点不一，画面美术在四个平台都为正，说明美术受到一致认可。</b></p>',
                    unsafe_allow_html=True)

    sec("02", "五种数据源，五种主题侧重", "第一名都是战斗，真正的差异在第二、第三名。")
    d2 = d["topics"][d["topics"]["theme"] != "未建模"].copy()
    d2["s"] = d2["share"] / d2.groupby("platform")["share"].transform("sum")
    # 一个主题由多个簇组成：先按「平台 × 主题」合计份额，再取 Top1、算集中度
    g2 = d2.groupby(["platform", "theme"], as_index=False)["s"].sum()
    hhi = (g2["s"] ** 2).groupby(g2["platform"]).sum()
    # 「其他/综合」是未归入具体主题的杂项桶，不参与排名（但计入分母）
    # 多数平台的第一名都是战斗，差异体现在第二、第三名，所以展示前三
    top3 = (g2[~g2["theme"].isin(["其他/综合"])]
            .sort_values("s", ascending=False).groupby("platform").head(3))
    evidence = {
        p: "<br>".join(f"{r.theme} {fmt_pct(r.s)}" for r in g.itertuples())
        for p, g in top3.groupby("platform")
    }
    mean = (d["themes"][d["themes"]["theme"] != "未建模"]
            .assign(w=lambda x: x["n"] * x["mean_sentiment"])
            .groupby("platform_name")[["w", "n"]].sum().pipe(lambda x: x["w"] / x["n"]))
    rows = []
    for p in ["小黑盒", "小红书", "微博", "B站", "B站弹幕"]:
        if p not in evidence:
            continue
        focus, advice = PLATFORM_META[p]
        m = "—" if p == "B站弹幕" else f"{mean.get(p, 0):+.3f}"
        rows.append([p, evidence[p], f"{1 / hhi.loc[p]:.1f}", m, focus, advice])
    editorial_table(["平台", "前 3 主题（占比）", "有效话题数", "情绪分", "主题侧重", "宣传物料投放建议"],
                    rows, ["left", "left", "right", "right", "left", "left"])
    st.markdown(
        '<p class="note">占比按「平台 × 主题」合计后列内归一，与「主题与平台 · 讨论结构」同一口径；'
        '「其他/综合」是杂项桶（占全部文本 36.6%），不参与排名但计入分母。'
        '四个评论平台的第一名都是战斗，<b>平台差异要综合top前三考虑</b>：小黑盒倾向与前作差异的换皮讨论，小红书接着谈画面，'
        '微博多为期待发售信号，B站接着谈技术细节与角色。「有效话题数」＝ 1 ÷ Σ(各主题份额²)，越大越分散，'
        '可理解为“相当于几个主题在平均分配讨论”，不是主题个数。</p>',
        unsafe_allow_html=True,
    )

    sec("03", "后续宣发建议", "基于上面的结构信号，给出投入产出比重要度排序。")
    a1, a2, a3 = st.columns(3)
    for col, no, title, body in [
        (a1, "建议 01", "在物料里建立新作的基调锚点",
         "不用专发设定声明；开头 3–5 秒用题材、美术与战斗语言，让人看出它与《悟空》是两款游戏，且与竞品有亮眼差异化。"),
        (a2, "建议 02", "画面与民俗音乐做工作室标签",
         "阴天写实光照、傩戏打击乐几乎不卷入换皮争议，是跨作品复用最安全的两个资产。"),
        (a3, "建议 03", "战斗手感暂不做主打宣发",
         "关注度最高，但小黑盒负向 31.6% 已反超正向 23.7%。等调优后再正面宣发。"),
    ]:
        col.markdown(f'<div class="action"><div class="no">{no}</div><h4>{title}</h4>'
                     f'<p>{body}</p></div>', unsafe_allow_html=True)

    st.markdown(
        '<p class="note" style="margin-top:18px">口径：情感标签为外部 AI 全量打标（第二模型交叉验证，一致性中等偏强）；'
        '弹幕负向仅 3.4%，负向判断以评论为主。主题为五个数据集各自聚类后归并的 13 类。</p>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- 情感
def page_sentiment(d):
    import charts as C
    from data import theme_overall
    masthead("SENTIMENT / 02", "情感结构：一级评论表态，楼中楼讨论",
             "把平台、评论层级、主题三个维度拆开，避免被 24,733 条弹幕的平均值稀释。")
    overall = theme_overall(d["themes"])

    sec("01", "平台 × 评论层级", "同一平台的主楼与楼中楼，情绪方向可能相反。一级评论抛出倾向明确的观点，二级评论中讨论甚至争吵")
    legend_chips([("正向", SENTI_COLOR["positive"]), ("中性", SENTI_COLOR["neutral"]),
                  ("负向", SENTI_COLOR["negative"])])
    chart(C.fig_level_stack(d["summary"]))
    st.markdown(
        '<p class="note">四个平台的二级正向率都明显低于一级：B站 42.5% → 14.0%、小红书 36.8% → 13.6%、'
        '小黑盒 32.2% → 12.0%、微博 41.8% → 16.5%。小红书二级情绪分已转负（−7%）；小黑盒相反，'
        '一级负向 24.7% 为四组最高，核心玩家在主楼就直接下判断。微博二级仅 79 条，微博用户评论往往较少楼中讨论，方向可参考、不宜细读。</p>',
        unsafe_allow_html=True)

    sec("02", "主题 × 平台", "红色为正向，墨绿为负向，越深越强；空白格为样本少于 30 条。正向评论计+1，负向评论计-1，中立评论计0")
    chart(C.fig_theme_heat(d["themes"], overall))
    st.markdown(
        '<p class="note">同一主题在不同平台情感方向可能反转，只在<b>营销社区、画面美术、期待对比</b>三个主题上一致正向：战斗打击感在评论区几乎贴着 0（B站 +0.08、小红书 +0.03、'
        '微博 +0.04），并在小黑盒转负（−0.08）；换皮争议在微博 +0.40，在小红书、小黑盒却是 −0.10；'
        '角色形象微博 +0.27、小红书 −0.08。说明这些主题难有客观标准，差异来自人群主观判断。'
        '弹幕整列偏高（+0.38 ~ +0.49）是渠道特性，不与评论列横向比较。</p>',
        unsafe_allow_html=True)

    sec("03", "合并后的主题净情感", "按样本量加权，剔除“未建模”后比较。鼠标移到对应柱状图可看正负情感数值")
    chart(C.fig_theme_net(overall))
    st.markdown(
        '<p class="note">按净值排：画面美术 +24.2、期待对比 +23.3、音乐音效 +22.3 居前；'
        '战斗打击感与换皮争议 +12.0、剧情叙事 +11.5、角色形象 +7.4 垫底。'
        '需要注意角色形象是正 24.2% / 负 16.9% 的“两头情感都高”，存在争论；'
        '剧情叙事仅 227 条（占比最低），负向 9.3% 不算高，但出现即多为“内容缺失”批评，当风险信号读。</p>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- 时间轴
def page_timeline(d):
    import charts as C
    masthead("TIMELINE / 03", "弹幕时间轴：观众注意力与情绪节奏",
             "10 秒窗口 / 2 秒步进。上图看弹幕量，下图看情绪方向。")

    chart(C.fig_timeline(d["windows"], d["peaks"], duration=d["stats"]["duration_sec"]))
    st.markdown(
        f'<p class="note">全片 {d["stats"]["duration_sec"]} 秒；共爬取 {d["stats"]["danmaku"]:,} 条弹幕，'
        f'平均每分钟 {int(d["stats"]["danmaku_per_min"]):,} 条。峰值先看量，再看情感指数是否同向。</p>',
        unsafe_allow_html=True)
    st.markdown(
        '<p class="note">口径说明：P / V 是人工回看挑选的“内容型情绪”窗口，去除了仪式类、刷屏玩梗弹幕如“来了”之类的情感影响， '
        '因此与情感高峰略有错位。因P / V 只从非刷屏窗口里选。像 12:22–12:32（N4，1,591 条、正向 94%、情感 0.963）'
        '这种全场齐刷同一句正面弹幕的段落，情感虽高，但属于情绪同步而不是内容讨论，'
        '归入弹幕量峰 N，不重复进情感峰；0:00–0:10（N1，4,075 条、96% 仪式）同理。'
        '所以“弹幕量峰”和“情感峰”位置错开是口径设计，不是漏标。</p>',
        unsafe_allow_html=True)

    peaks = d["peaks"].copy()
    peaks["时段"] = peaks.apply(lambda r: f"{mmss(r['t_start'])}–{mmss(r['t_end'])}", axis=1)

    sec("01", "峰谷定位", "P = 情感峰，V = 情感谷，N = 弹幕量峰；刷屏齐刷段只进 N，不重复计入情感峰。")
    editorial_table(
        ["编号", "类型", "时段", "弹幕量", "情感值", "标签构成", "现场 / 事件"],
        [[r["rank"], r["kind"], r["时段"], f"{int(r['n']):,}",
          f"{r['value']:+.3f}" if r["kind"] != "弹幕量峰" else "—",
          r["label_mix"],
          r["event_topic"] if isinstance(r["event_topic"], str)
          else ("齐刷段：情绪同步，不计入情感峰" if r["kind"] == "弹幕量峰" else "—")]
         for _, r in peaks.iterrows()],
        ["left", "left", "left", "right", "right", "left", "left"],
    )

    sec("02", "窗口回放", "选一个峰 / 谷，看这一刻观众具体在说什么。")
    labels = [f"{r['rank']} · {r['kind']} · {r['时段']} · {r['label_mix']}" for _, r in peaks.iterrows()]
    pick = st.selectbox("选择窗口", labels, label_visibility="collapsed")
    row = peaks.iloc[labels.index(pick)]
    c1, c2 = st.columns([1.15, 1])
    with c1:
        st.markdown(
            f'<div class="card"><h4>{row["rank"]} · {row["event_topic"]}</h4>'
            f'<p class="note">{row["scene"] if isinstance(row["scene"], str) else "未标注场景"}</p>'
            f'<p class="quote">{row["evidence"] if isinstance(row["evidence"], str) else "—"}</p></div>',
            unsafe_allow_html=True,
        )
    with c2:
        win = d["danmaku"][
            (d["danmaku"]["t_sec"] >= row["t_start"]) & (d["danmaku"]["t_sec"] < row["t_end"])]
        vc = win["text"].value_counts().head(8).rename_axis("弹幕").reset_index(name="次数")
        st.markdown('<div class="sec-sub" style="margin-top:0">窗口内高频弹幕</div>',
                    unsafe_allow_html=True)
        st.dataframe(vc, hide_index=True, width="stretch", height=280)

    st.markdown(
        '<p class="note">注意 5:48 的“假峰”：706 条弹幕、91% 为仪式刷屏（“放火烧山，牢底坐穿”），'
        '它是集体玩梗，不是情绪高点，此处把玩梗误判为负向谷。</p>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- 主题
def page_themes(d):
    import charts as C
    from data import theme_overall
    masthead("TOPICS / 04", "主题与平台：舆论关注焦点",
             "13 个统一主题，由 547 个聚类簇归并；每个主题都能追到原始文本。")
    overall = theme_overall(d["themes"])

    sec("01", "讨论结构", "每一行是一个数据集，色块是主题；完整名称见上方色块图例。")
    chips = "".join(
        f'<span class="chip"><span style="display:inline-block;width:9px;height:9px;'
        f'background:{THEME_COLOR.get(t, "#b9ac9a")};margin-right:6px"></span>{html.escape(t)}</span>'
        for t in THEME_COLOR if t != "未建模"
    )
    st.markdown(chips, unsafe_allow_html=True)
    chart(C.fig_theme_share(d["topics"]))

    st.markdown(
        '<p class="note" style="margin-top:14px">词云是全部文本合并后的高频词，已分平台制图；'
        '评论可按平台单独看，也可四平台合并。分词已加载自制游戏专名词典（打击感、大蚌真君、换皮、黑神话钟馗等）'
        '与哈工大停用词，过滤「一定 / 可能 / 一样」这类噪声。</p>', unsafe_allow_html=True)
    wc_options = {
        "评论 · 四平台合并": "wc_comments.jpg",
        "评论 · B站": "wc_comments_bili.jpg",
        "评论 · 小红书": "wc_comments_xhs.jpg",
        "评论 · 小黑盒": "wc_comments_xiaoheihe.jpg",
        "评论 · 微博": "wc_comments_weibo.jpg",
        "弹幕 · B站": "wc_danmaku.jpg",
    }
    wc_pick = st.selectbox("词云视角", list(wc_options), label_visibility="collapsed")
    wc_path = ROOT / "assets" / wc_options[wc_pick]
    if wc_path.exists():
        st.image(str(wc_path), width="stretch")

    sec("02", "拆开一个主题", "看它在各平台的正负结构、代表词与原文样例。")
    cand = overall[overall["n"] >= 120]["theme"].tolist()
    theme = st.selectbox("主题", cand, index=cand.index("角色形象") if "角色形象" in cand else 0,
                         label_visibility="collapsed")
    plats = ["全部平台", "B站", "小红书", "小黑盒", "微博", "B站弹幕"]
    platform = st.radio("平台", plats, horizontal=True, label_visibility="collapsed")
    c1, c2 = st.columns([1, 1])
    with c1:
        legend_chips([("正向", ACCENT), ("负向", ACCENT2)])
        chart(C.fig_theme_platform(d["themes"], theme))
        sub = d["topics"][d["topics"]["theme"] == theme]
        doc = sub.sort_values("size", ascending=False).iloc[0] if len(sub) else None
        
        
    with c2:
        rep = rep_words(platform, theme)
        st.markdown('<div class="card"><h4>代表词 · 按情感拆分</h4>'
                    f'<p class="note">口径：按“{html.escape(platform)} · {html.escape(theme)}”'
                    '过滤原文后分词，按词频排序；已去掉「黑神话 / 钟馗 / 游戏 / 一定 / 可能」'
                    '这类每个主题都会出现的通用词。词后数字为出现次数。</p>', unsafe_allow_html=True)
        for key, cn, color in [("positive", "正向", ACCENT), ("neutral", "中性", "#b9ac9a"),
                               ("negative", "负向", ACCENT2)]:
            st.markdown(
                f'<div style="margin:10px 0 2px;font-size:12.5px;color:{color};'
                f'font-weight:600">{cn}'
                f'<span style="color:#a99f90;font-weight:400;margin-left:8px">'
                f'样本 {rep["n"][key]:,} 条</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(word_chips(rep["words"][key]), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    sec("03", "主题明细表", "按平台、主题筛选后再排序；表格本身也可点列头排序。")
    df = d["topics"][["platform", "theme", "size", "share", "top_words", "mean_sentiment"]].copy()
    df = df[df["theme"] != "未建模"]
    f1, f2 = st.columns(2)
    all_plats = df["platform"].unique().tolist()
    pf = f1.multiselect("平台", all_plats,
                        default=["小黑盒"] if "小黑盒" in all_plats else all_plats[:1])
    tf = f2.multiselect("主题", df["theme"].unique().tolist(), default=[])
    if pf:
        df = df[df["platform"].isin(pf)]
    if tf:
        df = df[df["theme"].isin(tf)]
    df = df.sort_values(["platform", "size"], ascending=[True, False])
    df["share"] = (df["share"] * 100).round(1)
    df["mean_sentiment"] = df["mean_sentiment"].round(3)
    st.dataframe(df.rename(columns={"platform": "平台", "theme": "主题", "size": "簇样本量",
                                    "share": "占该平台 %", "top_words": "代表词",
                                    "mean_sentiment": "情感均值"}),
                 hide_index=True, width="stretch", height=320)
    st.caption(f"当前 {len(df):,} 行。")
    st.download_button("导出当前筛选 CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="topics_view.csv", mime="text/csv",
                       key="dl_topics")


# ---------------------------------------------------------------- 数据
def page_data(d):
    masthead("DATA & METHOD / 05", "数据、口径与复用",
             "全部原始文本都在这里；替换同结构 CSV 即可复跑，上传入口见侧边栏。")
    stats = d["stats"]
    kpi_row([
        (f"{stats['comments']:,}", "评论", "非全量数据"),
        (f"{stats['danmaku']:,}", "弹幕", "非全量数据"),
        ("13", "统一主题", "人工确认命名"),
        ("0.58–0.75", "交叉验证一致性", "另一AI模型复核"),
    ])

    sec("01", "评论明细", "按平台、情感、层级、主题筛选；表格可直接复制到 Excel。")
    c1, c2, c3, c4 = st.columns(4)
    plats = sorted(d["comments"]["platform"].unique())
    plat = c1.multiselect("平台", plats,
                          default=["小黑盒"] if "小黑盒" in plats else plats[:1])
    senti = c2.multiselect("情感", ["positive", "neutral", "negative"], default=[])
    level = c3.multiselect("评论层级", ["一级", "二级"], default=[])
    theme = c4.multiselect("主题", d["comments"]["theme"].unique().tolist(), default=[])
    df = d["comments"][d["comments"]["platform"].isin(plat)]
    if senti:
        df = df[df["label"].isin(senti)]
    if level:
        df = df[df["is_reply"].map({True: "二级", False: "一级"}).isin(level)]
    if theme:
        df = df[df["theme"].isin(theme)]
    df = df.assign(情感=df["label"].map(SENTI_CN), 层级=df["is_reply"].map({True: "二级", False: "一级"}))
    st.dataframe(df[["platform", "text", "情感", "theme", "层级"]].rename(
        columns={"platform": "平台", "text": "文本", "theme": "主题"}),
        hide_index=True, width="stretch", height=340)
    st.caption(f"当前 {len(df):,} 行；共 {stats['comments']:,} 行。默认只看小黑盒，"
               "需要全量时在「平台」里多选其他平台。")
    st.download_button("导出当前筛选 CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="comments_view.csv", mime="text/csv")

    sec("02", "弹幕明细", "按时间、情感与主题筛选，用于回看某个窗口。")
    c4, c5, c6 = st.columns([1.4, 1, 1])
    rng = c4.slider("时间范围（分钟）", 0.0, 16.0, (6.0, 8.0), 0.5)
    dm_senti = c5.multiselect("弹幕情感", ["positive", "neutral", "negative", "surprise", "ritual"], default=[])
    dm_theme = c6.multiselect("主题", d["danmaku"]["theme"].unique().tolist(), default=[])
    dm = d["danmaku"]
    dm = dm[(dm["t_sec"] >= rng[0] * 60) & (dm["t_sec"] <= rng[1] * 60)]
    if dm_senti:
        dm = dm[dm["label"].isin(dm_senti)]
    if dm_theme:
        dm = dm[dm["theme"].isin(dm_theme)]
    show = dm.assign(时间=dm["t_sec"].map(mmss), 情感=dm["label"].map(SENTI_CN))[
        ["时间", "text", "情感", "theme"]].rename(columns={"text": "弹幕", "theme": "主题"})
    st.dataframe(show.head(400), hide_index=True, width="stretch", height=320)
    st.caption(f"当前 {len(dm):,} 行；表格最多显示 400 行。")

    sec("03", "口径与边界", "结论能用，但别把它当产品周期的结论。")
    st.markdown(
        '<div class="card"><p class="note">'
        "1. 情感标签为外部 AI 全量打标（正 / 中 / 负，弹幕另含 惊讶 / 仪式）；"
        "第二模型交叉验证一致性 0.58–0.75，占比结论可用，但不宜声称“高度可靠”。<br>"
        "2. 弹幕负向仅 3.4%，不代表满意——弹幕场景天然不爱发负面，负向判断必须以评论为主。<br>"
        "3. 主题归并损失：547 簇压到 13 类后，“其他/综合”占 15%–41%，影响绝对值，不影响跨平台比较。<br>"
        "4. 单条视频、非概率抽样，描述的是这一支演示的舆论结构，不能外推到整个产品周期。<br>"
        "5. 峰谷必须人工回看画面——这是本分析里唯一不可自动化的环节，也是结论可信度的来源。"
        "</p></div>", unsafe_allow_html=True)


# ---------------------------------------------------------------- 报告
def page_report(d=None):
    masthead("REPORTS / 06", "数据分析报告",
             "两份成品报告：总报告与五问分析。摘要见「项目说明与摘要」，可在那里下载 PDF。")
    pick = st.radio("报告", ["总报告", "五问分析"], horizontal=True,
                    label_visibility="collapsed")
    rp = ROOT / "reports"

    fname = "report.md" if pick == "总报告" else "five-question-analysis.md"
    path = rp / fname
    if not path.exists():
        st.info(f"缺少 reports/{fname}。")
        return
    text = path.read_text(encoding="utf-8")
    st.download_button("下载 Markdown", text.encode("utf-8"), file_name=fname,
                       mime="text/markdown")
    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    st.markdown(text, unsafe_allow_html=True)


# ---------------------------------------------------------------- 上传
def page_upload():
    import fastlane  # 仅上传页需要，延迟加载
    masthead("REUSE / 07", "上传你的 CSV，复用同一套工作流",
             "支持评论或弹幕；自动识别文本 / 时间 / 平台列，词典打标 + TF-IDF 主题 + 时间轴。")
    st.markdown(
        '<div class="card"><p class="note">'
        "<b>最小要求</b>：一行一条文本，至少包含 <code>text_clean</code> / <code>text</code> / "
        "<code>content</code> 之一。可选列：<code>progress</code>（弹幕秒数）、<code>platform</code>。<br>"
        "<b>输出</b>：情感分布、主题分布、评论样本表；弹幕额外输出 10 秒窗口时间轴。<br>"
        "<b>提示</b>：上传模式为快速版口径（词典 + KMeans），与 Demo 的 AI 打标 + 主题聚类不可直接横向比较。"
        "</p></div>", unsafe_allow_html=True,
    )
    file = st.file_uploader("选择 CSV 文件", type=["csv"])
    kind = st.radio("数据类型", ["评论 comments", "弹幕 danmaku"], horizontal=True)
    kind = "danmaku" if kind.startswith("弹幕") else "comment"

    if file is None:
        st.info("等待上传。也可以先回到 Demo，看看成品长什么样。")
        return
    try:
        raw = fastlane.read_csv(file)
        text, time, plat = fastlane.detect(raw)
    except Exception as e:
        st.error(f"字段识别失败：{e}")
        return
    st.markdown(f'<p class="note">已识别：文本列 <code>{text}</code>'
                + (f"｜时间列 <code>{time}</code>" if time else "｜无时间列")
                + (f"｜平台列 <code>{plat}</code>" if plat else "")
                + f"｜共 {len(raw):,} 行</p>", unsafe_allow_html=True)
    if kind == "danmaku" and not time:
        st.warning("弹幕缺少 progress 时间列，将只输出情感与主题，不输出时间轴。")

    with st.spinner("正在打标与聚类…"):
        res = fastlane.analyze(raw, kind)
    st.session_state["fast"] = res
    st.success(f"完成：{len(res['df']):,} 行，{res['df']['theme'].nunique()} 个主题簇。")
    st.markdown('<p class="note">结果已生成，点击侧边栏「结果预览」查看。</p>', unsafe_allow_html=True)


def page_fast_result():
    import charts as C
    res = st.session_state.get("fast")
    if not res:
        masthead("RESULT / 08", "结果预览", "还没有上传数据。")
        st.info("请先在「上传与运行」页选择 CSV。")
        return
    df = res["df"]
    masthead("RESULT / 08", "上传数据 · 结果预览", "快速版口径：词典情感打标 + TF-IDF/KMeans 主题。")
    pos = (df["label"] == "positive").mean()
    neg = (df["label"] == "negative").mean()
    kpi_row([
        (f"{len(df):,}", "文本总量", "上传数据"),
        (fmt_pct(pos), "正向占比", "词典命中口径"),
        (fmt_pct(neg), "负向占比", "词典命中口径"),
        (f"{df['theme'].nunique()}", "主题簇", "TF-IDF + KMeans"),
    ])
    c1, c2 = st.columns(2)
    with c1:
        chart(C.fig_fast_sentiment(res["counts"]))
    with c2:
        chart(C.fig_fast_topics(res["topics"]))
    if res["windows"] is not None:
        sec("01", "弹幕时间轴", "10 秒窗口 / 2 秒步进。")
        chart(C.fig_timeline(res["windows"], None))
    sec("02", "主题明细", "每个簇的前 10 个 TF-IDF 词。")
    st.dataframe(res["topics"].rename(columns={"theme": "主题", "size": "样本量",
                                              "share": "占比", "top_words": "代表词"}).assign(
        占比=lambda x: (x["占比"] * 100).round(1)),
        hide_index=True, width="stretch", height=300)
    sec("03", "文本样例", "按情感筛选，检查打标是否符合预期。")
    pick = st.multiselect("情感", ["positive", "neutral", "negative"], default=["negative"])
    sample = df[df["label"].isin(pick)] if pick else df
    st.dataframe(sample[["text", "label", "theme", "platform"]].head(200).rename(
        columns={"text": "文本", "label": "情感", "theme": "主题", "platform": "平台"}),
        hide_index=True, width="stretch", height=300)


# ---------------------------------------------------------------- 入口
def main():
    with st.sidebar:
        st.markdown('<div style="font-family:serif;font-size:22px;font-weight:700;'
                    'letter-spacing:.06em;padding:4px 0 2px">钟馗 · 舆情看板</div>', unsafe_allow_html=True)
        st.markdown('<p class="note" style="margin:0 0 16px">COMMUNITY INTELLIGENCE<br>'
                    '15 分钟实机演示 · 四平台评论 + B站弹幕</p>', unsafe_allow_html=True)
        st.markdown('<p class="note" style="margin:0 0 12px">首次打开或刷新后，图表与表格需要几秒加载；'
                    '若出现白屏、转圈或 TypeError，按 Ctrl + Shift + R 强制刷新 1–2 次即可恢复，'
                    '已加载的模块会被浏览器缓存，第二次通常更快。</p>', unsafe_allow_html=True)
        source = st.radio("数据源", [DEMO_SOURCE, UPLOAD_SOURCE])
        if source == DEMO_SOURCE:
            pages = ["项目说明与摘要", "概览", "情感结构", "弹幕时间轴", "主题与平台", "数据与口径", "研究报告"]
        else:
            pages = ["上传与运行", "结果预览"]
        page = st.radio("页面", pages)
        st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
        st.markdown('<p class="note">Demo：11,280 条评论 + 24,733 条弹幕，'
                    '全量 parquet 约 1 MB。<br>上传：评论 / 弹幕 CSV，可复跑同一套流程。</p>',
                    unsafe_allow_html=True)

    if source == UPLOAD_SOURCE:
        page_upload() if page == "上传与运行" else page_fast_result()
        return

    if page == "项目说明与摘要":
        page_brief()
        return

    from data import load_demo
    d = load_demo()
    {"概览": page_overview, "情感结构": page_sentiment,
     "弹幕时间轴": page_timeline, "主题与平台": page_themes,
     "数据与口径": page_data, "研究报告": page_report}[page](d)


if __name__ == "__main__":
    main()
