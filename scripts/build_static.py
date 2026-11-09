# -*- coding: utf-8 -*-
"""把看板导出为一个自包含的静态 HTML：static/index.html（图表可交互、筛选在本地完成）。

用法：python scripts/build_static.py
产出：static/index.html（可直接双击打开 / 上传 GitHub Pages）
只去掉两件静态页做不到的事：上传 CSV 跑工作流、结果预览；其余页面、筛选、明细表全部保留。
"""
import base64
import html as H
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import plotly.io as pio
from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import charts as C
from config import ACCENT, ACCENT2, GOLD, SENTI_CN, SENTI_COLOR, THEME_COLOR
from tokenizer import tokens

DATA = ROOT / "data"
ASSETS = ROOT / "assets"
REPORTS = ROOT / "reports"
OUT = ROOT / "static"

PAPER = "#f8f6f2"
SURFACE = "#fffdf8"
INK = "#23201c"
MUTED = "#7d7468"
RULE = "#e2dacd"

PLATFORMS = ["全部平台", "B站", "小红书", "小黑盒", "微博", "B站弹幕"]
PLAT_OPTIONS = [("全部平台", ""), ("B站", "B站"), ("小红书", "小红书"),
                ("小黑盒", "小黑盒"), ("微博", "微博"), ("B站弹幕", "B站弹幕")]
PLATFORM_META = {
    "小黑盒": ("战斗评估 + 原创性质疑", "先立新作锚点，用新作的差别回应换皮争议"),
    "小红书": ("战斗 + 画面审美", "强调画面质感：光照、材质、场景"),
    "微博": ("战斗 + 期待表态", "放预约入口 + 定档信息，便于转发扩散"),
    "B站": ("战斗 + 技术/角色", "角色特写与设定图优先，留出二创空间"),
    "B站弹幕": ("仪式玩梗为主", "保留仪式梗生态，但不要把梗当评价"),
}


# ---------------------------------------------------------------- 小工具
def esc(s):
    return H.escape(str(s))


def num(v):
    return f"{v:,}"


def mmss(sec):
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


def fmt_pct(x, digits=1):
    return f"{x * 100:.{digits}f}%"


def inline(s):
    s = H.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return s


def is_view(text):
    """以加粗句子开头的段落，按“观点行”做色块强调，避免整页黑字。"""
    return bool(re.match(r"^\*\*", text))


def render_md(md, drop_first_h1=True):
    """够用的 Markdown → HTML：标题 / 表格 / 列表 / 引用 / 分隔线 / 加粗 / 行内代码。"""
    lines = md.splitlines()
    out, i, n, dropped = [], 0, len(lines), False
    while i < n:
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        if s in ("---", "***", "___"):
            out.append("<hr>")
            i += 1
            continue
        m = re.match(r"(#+)\s+(.*)", s)
        if m:
            lv, txt = len(m.group(1)), m.group(2).strip()
            if lv == 1 and drop_first_h1 and not dropped:
                dropped = True
                i += 1
                continue
            out.append(f"<h{lv}>{inline(txt)}</h{lv}>")
            i += 1
            continue
        if s.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            rows = [r for r in rows if r and not set("".join(r)) <= set("-: ")]
            if rows:
                th = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
                tb = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                             for r in rows[1:])
                out.append(f'<div class="tw"><table><thead><tr>{th}</tr></thead>'
                           f"<tbody>{tb}</tbody></table></div>")
            continue
        if s.startswith(">"):
            q = []
            while i < n and lines[i].strip().startswith(">"):
                q.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append('<div class="mdquote">'
                       + "".join(f"<p>{inline(x)}</p>" for x in q) + "</div>")
            continue
        if s.startswith("- "):
            items = []
            while i < n and lines[i].strip().startswith("- "):
                items.append(lines[i].strip()[2:])
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue
        if re.match(r"\d+\.\s", s):
            items = []
            while i < n and re.match(r"\d+\.\s", lines[i].strip()):
                items.append(re.sub(r"^\d+\.\s", "", lines[i].strip()))
                i += 1
            out.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol>")
            continue
        buf = [s]
        i += 1
        while i < n:
            t = lines[i].strip()
            if (not t or t.startswith(("#", "|", ">", "- ")) or t in ("---", "***", "___")
                    or re.match(r"\d+\.\s", t)):
                break
            buf.append(t)
            i += 1
        text = " ".join(buf)
        cls = ' class="view"' if is_view(text) else ""
        out.append(f"<p{cls}>{inline(text)}</p>")
    return "\n".join(out)


def img_uri(path, width=1100):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if im.width > width:
        im = im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=72, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def b64_uri(data, mime):
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def embed(fig):
    return pio.to_html(fig, include_plotlyjs=False, full_html=False,
                       config={"displayModeBar": False, "responsive": True})


def masthead(kicker, title, sub):
    return (f'<div class="masthead"><div class="kicker">{kicker}</div>'
            f"<h1>{title}</h1><div class=\"sub\">{sub}</div></div>")


def sec(n, title, sub=""):
    return (f'<div class="sec-title"><span class="num">{n}</span><h2>{title}</h2></div>'
            + (f'<p class="sec-sub">{sub}</p>' if sub else ""))


def kpi_row(items):
    cells = "".join(
        f'<div class="kpi"><div class="v">{v}</div><div class="l">{l}</div>'
        + (f'<div class="n">{n}</div>' if n else "") + "</div>"
        for v, l, n in items)
    return f'<div class="kpi-row">{cells}</div>'


def chart(fig):
    return f'<div class="chart">{embed(fig)}</div>'


def chips(items):
    return "".join(
        f'<span class="chip"><span class="dot" style="background:{c}"></span>{esc(t)}</span>'
        for t, c in items)


def editorial_table(headers, rows, aligns=None, tid=None, keys=None):
    aligns = aligns or ["left"] * len(headers)
    attrs = f' id="{tid}"' if tid else ""
    th = "".join(
        f'<th class="{("r" if a == "right" else "")}"'
        + (f' data-k="{k}"' if keys and k is not None else "") + f">{h}</th>"
        for h, a, k in zip(headers, aligns, keys or [None] * len(headers)))
    body = "".join(
        "<tr>" + "".join(
            f'<td class="{("r" if a == "right" else "")}">{c}</td>' for c, a in zip(r, aligns)
        ) + "</tr>" for r in rows)
    return (f'<div class="tw"><table{attrs}><thead><tr>{th}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def select(id_, options, label, default=""):
    opts = "".join(
        f'<option value="{esc(v)}"{" selected" if v == default else ""}>{esc(t)}</option>'
        for t, v in options)
    return f'<label>{label}<select id="{id_}">{opts}</select></label>'


def note(s):
    return f'<p class="note">{s}</p>'


# ---------------------------------------------------------------- 数据
def load():
    return {
        "comments": pd.read_parquet(DATA / "comments.parquet"),
        "danmaku": pd.read_parquet(DATA / "danmaku.parquet"),
        "summary": pd.read_parquet(DATA / "sentiment_summary.parquet"),
        "themes": pd.read_parquet(DATA / "themes.parquet"),
        "topics": pd.read_parquet(DATA / "topics.parquet"),
        "windows": pd.read_parquet(DATA / "windows_10s.parquet"),
        "peaks": pd.read_parquet(DATA / "peaks.parquet"),
        "stats": json.loads((DATA / "stats.json").read_text(encoding="utf-8")),
    }


def theme_overall(themes):
    d = themes[themes["theme"] != "未建模"].copy()
    n = d.groupby("theme")["n"].sum().rename("n")
    w, g = d["n"], d["theme"]

    def wavg(col):
        return (d[col] * w).groupby(g).sum() / n

    mean = wavg("mean_sentiment")
    var = wavg("sentiment_var") + ((d["mean_sentiment"] - g.map(mean)) ** 2 * w).groupby(g).sum() / n
    out = pd.DataFrame({"n": n, "positive_rate": wavg("positive_rate"),
                        "negative_rate": wavg("negative_rate"),
                        "mean_sentiment": mean, "sentiment_var": var}).reset_index()
    out["net"] = out["positive_rate"] - out["negative_rate"]
    out["share"] = out["n"] / out["n"].sum()
    return out.sort_values("n", ascending=False)


def rows_for(d, platform):
    if platform == "B站弹幕":
        return d["danmaku"]
    src = d["comments"]
    return src if platform == "全部平台" else src[src["platform"] == platform]


def compute_rep(sub, limit=12):
    out = {"n": {}, "words": {}}
    for key in ["positive", "neutral", "negative"]:
        part = sub[sub["label"] == key]
        cnt = Counter()
        for t in part["text"]:
            cnt.update(tokens(t, drop_generic=True))
        items = [(w, k) for w, k in cnt.items() if k >= 2]
        items.sort(key=lambda x: (-x[1], x[0]))
        out["words"][key] = [[w, int(k)] for w, k in items[:limit]]
        out["n"][key] = int(len(part))
    return out


# ---------------------------------------------------------------- 页面
def page_brief(summary_md, pdf_uri):
    body = render_md(summary_md)
    return (
        masthead("BRIEF / 00", "项目说明与摘要",
                 "先说这份看板做了什么、数据从哪来，再给这次演示的结论；文末可下载 PDF 摘要。")
        + f'<div class="report">{body}</div>'
        + f'<a class="btn" download="钟馗实机演示_舆情摘要.pdf" href="{pdf_uri}">下载摘要 PDF</a>'
        + note("本页文字即摘要 PDF 的内容；要核对数字，去「数据与口径」翻原始明细。")
    )


def page_overview(d, overall):
    stats = d["stats"]
    n_themes = int(d["themes"][d["themes"]["theme"] != "未建模"]["theme"].nunique())

    d2 = d["topics"][d["topics"]["theme"] != "未建模"].copy()
    d2["s"] = d2["share"] / d2.groupby("platform")["share"].transform("sum")
    g2 = d2.groupby(["platform", "theme"], as_index=False)["s"].sum()
    hhi = (g2["s"] ** 2).groupby(g2["platform"]).sum()
    top3 = (g2[~g2["theme"].isin(["其他/综合"])]
            .sort_values("s", ascending=False).groupby("platform").head(3))
    evidence = {p: "<br>".join(f"{r.theme} {fmt_pct(r.s)}" for r in g.itertuples())
                for p, g in top3.groupby("platform")}
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

    return (
        masthead("COMMUNITY INTELLIGENCE / 01", "钟馗实机演示 · 舆论结构总览",
                 "通过爬虫采集在b站、小黑盒、微博、小红书中官号最新 15 分 53 秒实机演示中评论 11,280 条 ＋ b站弹幕 24,733 条")
        + '<div class="card"><h4>数据来源</h4><p class="note">针对黑神话钟馗最新 15 分 53 秒实机演示，'
          "爬取 B 站、微博、小红书、小黑盒上官号实机演示视频下评论与b站弹幕，逐条打上正向 / 中性 / 负向"
          "三种情感标签，再把文本聚成 13 个主题进行分析。清洗后可用文本共 36,013 。</p></div>"
        + kpi_row([
            ("1,359.7 万", "B站播放", "点赞 97.1 万 · 评论 11.6 万 · 转发 50.2 万"),
            ("239 万", "微博话题阅读", "点赞 1.5 万 · 评论 1801 · 转发 3430"),
            ("1.81 万", "小黑盒点赞", "评论 7288 · 转发 7288"),
            ("4.8 万", "小红书点赞", "评论 4184 · 转发2.9w"),
        ])
        + '<div class="verdict"><span class="tag">核心判断</span><br>'
          "播放与互动都在头部量级，<b>实机演出曝光度较高</b>。但文字层面多数人只是打卡和附和社区情绪："
          "出现最多的 <b>8 条弹幕</b>（“来了来了”“帅”“牛逼”）就占全部弹幕的 <b>64.1%</b>——"
          "<b>观众围观不等于认同作品内容</b>。<br>"
          "实机演示的主题信息主要来自两处：B站 <b>186 条百字长评</b>，和小黑盒的战斗类讨论。<br>"
          "一句话总结：<b>最关注战斗，最认可画面与音乐，最分裂的是角色与战斗</b>。"
          "风险点在“像不像悟空”的区分度担忧，以及穿模、音效复用这类制作精度，对剧情讨论较少。"
          "</div>"
        + kpi_row([
            (num(stats["comments"]), "评论总量", "四平台 · 45.6% 为二级评论"),
            (num(stats["danmaku"]), "弹幕总量", "单支视频 · 953 秒"),
            (num(int(stats["danmaku_per_min"])), "弹幕 / 分钟", "事件级密度"),
            (str(n_themes), "统一主题", "547 簇归并"),
        ])
        + sec("01", "两个结构信号", "一级评论和二级评论是两种人：主楼表态，情感色彩鲜明，楼中楼多为讨论争议。")
        + chips([("一级评论", ACCENT), ("二级评论", GOLD)])
        + '<div class="grid2"><div>'
        + chart(C.fig_level_positive(d["summary"]))
        + note("<b>一级评论正向占比远高于二级评论。</b> 微博一级正向 41.8%，B站一级 42.5%；"
               "但 B站二级负向 12.8%，已反超一级的 5.9%。")
        + "</div><div>"
        + chart(C.fig_theme_variance(overall))
        + note("分歧最大的六个主题集中在 0.41–0.49，彼此差距很小，排名不必细究；"
               "有用的是方向：方差可能来自平台内正负双方讨论，也可能来自不同平台存在的情感差异。"
               "<b>角色形象、战斗打击感在平台之间正负翻转，说明不同平台观点不一，画面美术在四个平台都为正，"
               "说明美术受到一致认可。</b>")
        + "</div></div>"
        + sec("02", "五种数据源，五种主题侧重", "第一名都是战斗，真正的差异在第二、第三名。")
        + editorial_table(["平台", "前 3 主题（占比）", "有效话题数", "情绪分", "主题侧重", "宣传物料投放建议"],
                          rows, ["left", "left", "right", "right", "left", "left"])
        + note("占比按「平台 × 主题」合计后列内归一，与「主题与平台 · 讨论结构」同一口径；"
               "「其他/综合」是杂项桶（占全部文本 36.6%），不参与排名但计入分母。"
               "四个评论平台的第一名都是战斗，<b>平台差异要综合top前三考虑</b>："
               "小黑盒倾向与前作差异的换皮讨论，小红书接着谈画面，微博多为期待发售信号，B站接着谈技术细节与角色。"
               "「有效话题数」＝ 1 ÷ Σ(各主题份额²)，越大越分散，可理解为“相当于几个主题在平均分配讨论”，不是主题个数。")
        + sec("03", "后续宣发建议", "基于上面的结构信号，给出投入产出比重要度排序。")
        + '<div class="grid3">'
        + "".join(
            f'<div class="action"><div class="no">{no}</div><h4>{t}</h4><p>{b}</p></div>'
            for no, t, b in [
                ("建议 01", "在物料里建立新作的基调锚点",
                 "不用专发设定声明；开头 3–5 秒用题材、美术与战斗语言，让人看出它与《悟空》是两款游戏，且与竞品有亮眼差异化。"),
                ("建议 02", "画面与民俗音乐做工作室标签",
                 "阴天写实光照、傩戏打击乐几乎不卷入换皮争议，是跨作品复用最安全的两个资产。"),
                ("建议 03", "战斗手感暂不做主打宣发",
                 "关注度最高，但小黑盒负向 31.6% 已反超正向 23.7%。等调优后再正面宣发。"),
            ])
        + "</div>"
        + note("口径：情感标签为外部 AI 全量打标（第二模型交叉验证，一致性中等偏强）；"
               "弹幕负向仅 3.4%，负向判断以评论为主。主题为五个数据集各自聚类后归并的 13 类。")
    )


def page_sentiment(d, overall):
    return (
        masthead("SENTIMENT / 02", "情感结构：一级评论表态，楼中楼讨论",
                 "把平台、评论层级、主题三个维度拆开，避免被 24,733 条弹幕的平均值稀释。")
        + sec("01", "平台 × 评论层级",
              "同一平台的主楼与楼中楼，情绪方向可能相反。一级评论抛出倾向明确的观点，二级评论中讨论甚至争吵")
        + chips([("正向", SENTI_COLOR["positive"]), ("中性", SENTI_COLOR["neutral"]),
                 ("负向", SENTI_COLOR["negative"])])
        + chart(C.fig_level_stack(d["summary"]))
        + note("四个平台的二级正向率都明显低于一级：B站 42.5% → 14.0%、小红书 36.8% → 13.6%、"
               "小黑盒 32.2% → 12.0%、微博 41.8% → 16.5%。小红书二级情绪分已转负（−7%）；小黑盒相反，"
               "一级负向 24.7% 为四组最高，核心玩家在主楼就直接下判断。微博二级仅 79 条，"
               "微博用户评论往往较少楼中讨论，方向可参考、不宜细读。")
        + sec("02", "主题 × 平台",
              "红色为正向，墨绿为负向，越深越强；空白格为样本少于 30 条。正向评论计+1，负向评论计-1，中立评论计0")
        + chart(C.fig_theme_heat(d["themes"], overall))
        + note("同一主题在不同平台情感方向可能反转，只在<b>营销社区、画面美术、期待对比</b>三个主题上一致正向："
               "战斗打击感在评论区几乎贴着 0（B站 +0.08、小红书 +0.03、微博 +0.04），并在小黑盒转负（−0.08）；"
               "换皮争议在微博 +0.40，在小红书、小黑盒却是 −0.10；角色形象微博 +0.27、小红书 −0.08。"
               "说明这些主题难有客观标准，差异来自人群主观判断。弹幕整列偏高（+0.38 ~ +0.49）是渠道特性，不与评论列横向比较。")
        + sec("03", "合并后的主题净情感", "按样本量加权，剔除“未建模”后比较。鼠标移到对应柱状图可看正负情感数值")
        + chart(C.fig_theme_net(overall))
        + note("按净值排：画面美术 +24.2、期待对比 +23.3、音乐音效 +22.3 居前；"
               "战斗打击感与换皮争议 +12.0、剧情叙事 +11.5、角色形象 +7.4 垫底。"
               "需要注意角色形象是正 24.2% / 负 16.9% 的“两头情感都高”，存在争论；"
               "剧情叙事仅 227 条（占比最低），负向 9.3% 不算高，但出现即多为“内容缺失”批评，当风险信号读。")
    )


def page_timeline(d):
    stats = d["stats"]
    peaks = d["peaks"].copy()
    peaks["时段"] = peaks.apply(lambda r: f"{mmss(r['t_start'])}–{mmss(r['t_end'])}", axis=1)
    pk_rows = []
    for _, r in peaks.iterrows():
        val = f"{r['value']:+.3f}" if r["kind"] != "弹幕量峰" else "—"
        evt = (r["event_topic"] if isinstance(r["event_topic"], str)
               else ("齐刷段：情绪同步，不计入情感峰" if r["kind"] == "弹幕量峰" else "—"))
        pk_rows.append([r["rank"], r["kind"], r["时段"], f"{int(r['n']):,}",
                        val, r["label_mix"], evt])
    options = "".join(
        f'<option value="{i}">{esc(r["rank"])} · {esc(r["kind"])} · {esc(r["时段"])} · {esc(r["label_mix"])}</option>'
        for i, r in peaks.iterrows())
    return (
        masthead("TIMELINE / 03", "弹幕时间轴：观众注意力与情绪节奏",
                 "10 秒窗口 / 2 秒步进。上图看弹幕量，下图看情绪方向。")
        + chart(C.fig_timeline(d["windows"], d["peaks"], duration=stats["duration_sec"]))
        + note(f"全片 {stats['duration_sec']} 秒；共爬取 {stats['danmaku']:,} 条弹幕，"
               f"平均每分钟 {int(stats['danmaku_per_min']):,} 条。峰值先看量，再看情感指数是否同向。")
        + note("口径说明：P / V 是人工回看挑选的“内容型情绪”窗口，去除了仪式类、刷屏玩梗弹幕如“来了”之类的情感影响，"
               "因此与情感高峰略有错位。因P / V 只从非刷屏窗口里选。像 12:22–12:32（N4，1,591 条、正向 94%、情感 0.963）"
               "这种全场齐刷同一句正面弹幕的段落，情感虽高，但属于情绪同步而不是内容讨论，"
               "归入弹幕量峰 N，不重复进情感峰；0:00–0:10（N1，4,075 条、96% 仪式）同理。"
               "所以“弹幕量峰”和“情感峰”位置错开是口径设计，不是漏标。")
        + sec("01", "峰谷定位", "P = 情感峰，V = 情感谷，N = 弹幕量峰；刷屏齐刷段只进 N，不重复计入情感峰。")
        + editorial_table(["编号", "类型", "时段", "弹幕量", "情感值", "标签构成", "现场 / 事件"],
                          pk_rows, ["left", "left", "left", "right", "right", "left", "left"])
        + sec("02", "窗口回放", "选一个峰 / 谷，看这一刻观众具体在说什么。")
        + f'<div class="ctrl"><label>选择窗口<select id="pk-sel">{options}</select></label></div>'
        + '<div class="grid2" style="grid-template-columns:1.15fr 1fr"><div>'
          '<div class="card"><h4 id="pk-rank">—</h4><p class="note" id="pk-scene">—</p>'
          '<p class="quote" id="pk-ev">—</p></div></div><div>'
          '<div class="sec-sub" style="margin-top:0">窗口内高频弹幕</div>'
          '<div class="scroll"><table id="pk-table"><thead><tr><th>弹幕</th><th class="r">次数</th></tr></thead>'
          '<tbody id="pk-body"></tbody></table></div></div></div>'
        + note("注意 5:48 的“假峰”：706 条弹幕、91% 为仪式刷屏（“放火烧山，牢底坐穿”），"
               "它是集体玩梗，不是情绪高点，此处把玩梗误判为负向谷。")
    )


def page_themes(d, overall):
    cand = overall[overall["n"] >= 120]["theme"].tolist()
    default_i = cand.index("角色形象") if "角色形象" in cand else 0
    theme_opts = "".join(
        f'<option value="{i}"{" selected" if i == default_i else ""}>{esc(t)}</option>'
        for i, t in enumerate(cand))
    tc_html = "".join(
        f'<div class="tc" style="display:{"block" if i == default_i else "none"}">'
        + embed(C.fig_theme_platform(d["themes"], t)) + "</div>"
        for i, t in enumerate(cand))

    wc = [("评论 · 四平台合并", "wc_comments.jpg"), ("评论 · B站", "wc_comments_bili.jpg"),
          ("评论 · 小红书", "wc_comments_xhs.jpg"), ("评论 · 小黑盒", "wc_comments_xiaoheihe.jpg"),
          ("评论 · 微博", "wc_comments_weibo.jpg"), ("弹幕 · B站", "wc_danmaku.jpg")]
    wc_sel = "".join(f'<option value="{i}">{esc(t)}</option>' for i, (t, _) in enumerate(wc))
    wc_imgs = ""
    for i, (_, f) in enumerate(wc):
        p = ASSETS / f
        if not p.exists():
            continue
        wc_imgs += (f'<img class="wc" src="{img_uri(p)}" alt="{esc(f)}" '
                    f'style="display:{"block" if i == 0 else "none"}">')

    themes = sorted(d["topics"]["theme"].unique().tolist())
    th_opts = '<option value="">全部主题</option>' + "".join(
        f'<option value="{esc(t)}">{esc(t)}</option>' for t in themes)

    return (
        masthead("TOPICS / 04", "主题与平台：舆论关注焦点",
                 "13 个统一主题，由 547 个聚类簇归并；每个主题都能追到原始文本。")
        + sec("01", "讨论结构", "每一行是一个数据集，色块是主题；完整名称见上方色块图例。")
        + chips([(t, THEME_COLOR.get(t, "#b9ac9a")) for t in THEME_COLOR if t != "未建模"])
        + chart(C.fig_theme_share(d["topics"]))
        + note("词云是全部文本合并后的高频词，已分平台制图；评论可按平台单独看，也可四平台合并。"
               "分词已加载自制游戏专名词典（打击感、大蚌真君、换皮、黑神话钟馗等）与哈工大停用词，"
               "过滤「一定 / 可能 / 一样」这类噪声。")
        + f'<div class="ctrl"><label>词云视角<select id="wc-sel">{wc_sel}</select></label></div>'
        + wc_imgs
        + sec("02", "拆开一个主题", "看它在各平台的正负结构、代表词与原文样例。")
        + f'<div class="ctrl"><label>主题<select id="th-sel">{theme_opts}</select></label>'
          '<label style="flex:1"><span style="visibility:hidden">平台</span>'
          '<span class="seg" id="pl-seg">'
        + "".join(f'<button data-p="{esc(p)}" class="{"on" if i == 0 else ""}">{esc(p)}</button>'
                  for i, p in enumerate(PLATFORMS))
        + "</span></label></div>"
        + '<div class="grid2"><div>'
        + chips([("正向", ACCENT), ("负向", ACCENT2)])
        + tc_html
        + "</div><div>"
          '<div class="card"><h4>代表词 · 按情感拆分</h4>'
          '<p class="note">口径：按“平台 · 主题”过滤原文后分词，按词频排序；已去掉「黑神话 / 钟馗 / 游戏 / 一定 / 可能」'
          '这类每个主题都会出现的通用词。词后数字为出现次数。</p>'
          '<div id="rep-box"></div></div>'
          "</div></div>"
        + sec("03", "主题明细表", "按平台、主题筛选后再排序；表格本身也可点列头排序。")
        + f'<div class="ctrl">{select("t-plat", PLAT_OPTIONS, "平台", "小黑盒")}'
          f'<label>主题<select id="t-theme">{th_opts}</select></label></div>'
        + '<div class="scroll"><table id="t-table">'
          '<colgroup><col style="width:90px"><col style="width:150px">'
          '<col style="width:96px"><col style="width:110px"><col><col style="width:96px"></colgroup><thead><tr>'
          '<th>平台</th><th>主题</th><th class="r" data-k="2">簇样本量</th>'
          '<th class="r" data-k="3">占该平台 %</th><th>代表词</th><th class="r" data-k="5">情感均值</th>'
          '</tr></thead><tbody id="t-body"></tbody></table></div>'
        + '<p class="note" id="t-cnt" style="margin-top:8px">—</p>'
        + '<a class="btn" href="#" id="t-export">导出当前筛选 CSV</a>'
    )


def page_data(d):
    stats = d["stats"]
    theme_opts_c = '<option value="">全部主题</option>' + "".join(
        f'<option value="{esc(t)}">{esc(t)}</option>' for t in d["comments"]["theme"].unique())
    theme_opts_d = '<option value="">全部主题</option>' + "".join(
        f'<option value="{esc(t)}">{esc(t)}</option>' for t in d["danmaku"]["theme"].unique())
    return (
        masthead("DATA & METHOD / 05", "数据、口径与复用",
                 "全部原始文本都在这里；替换同结构 CSV 即可复跑。")
        + kpi_row([
            (num(stats["comments"]), "评论", "非全量数据"),
            (num(stats["danmaku"]), "弹幕", "非全量数据"),
            ("13", "统一主题", "人工确认命名"),
            ("0.58–0.75", "交叉验证一致性", "另一AI模型复核"),
        ])
        + sec("01", "评论明细", "按平台、情感、层级、主题筛选；表格可直接复制到 Excel。")
        + '<div class="ctrl">'
        + '<label>平台<select id="c-plat"><option value="B站">B站</option>'
          '<option value="小红书">小红书</option><option value="小黑盒" selected>小黑盒</option>'
          '<option value="微博">微博</option></select></label>'
        + '<label>情感<select id="c-senti"><option value="">全部情感</option>'
          '<option value="正向">正向</option><option value="中性">中性</option>'
          '<option value="负向">负向</option></select></label>'
        + '<label>评论层级<select id="c-level"><option value="">全部层级</option>'
          '<option value="一级">一级</option><option value="二级">二级</option></select></label>'
        + f'<label>主题<select id="c-theme">{theme_opts_c}</select></label></div>'
        + '<div class="scroll" style="max-height:400px"><table id="c-table">'
          '<colgroup><col style="width:86px"><col><col style="width:64px">'
          '<col style="width:132px"><col style="width:64px"></colgroup><thead><tr>'
          '<th>平台</th><th>文本</th><th>情感</th><th>主题</th><th>层级</th>'
          '</tr></thead><tbody id="c-body"></tbody></table></div>'
        + '<p class="note" id="c-cnt" style="margin-top:8px">—</p>'
        + '<a class="btn" href="#" id="c-export">导出当前筛选 CSV</a>'
        + sec("02", "弹幕明细", "按时间、情感与主题筛选，用于回看某个窗口。")
        + '<div class="ctrl">'
        + '<label>时间范围（分钟）<span style="color:#23201c;letter-spacing:0">'
          '<span id="dm-a-val">6.0</span> – <span id="dm-b-val">8.0</span></span></label>'
        + '<label>起点<input type="range" id="dm-a" min="0" max="16" step="0.5" value="6"></label>'
        + '<label>终点<input type="range" id="dm-b" min="0" max="16" step="0.5" value="8"></label>'
        + '<label>弹幕情感<select id="dm-senti"><option value="">全部情感</option>'
          '<option value="正向">正向</option><option value="中性">中性</option>'
          '<option value="负向">负向</option><option value="惊讶">惊讶</option>'
          '<option value="仪式">仪式</option></select></label>'
        + f'<label>主题<select id="dm-theme">{theme_opts_d}</select></label></div>'
        + '<div class="scroll" style="max-height:400px"><table id="dm-table">'
          '<colgroup><col style="width:76px"><col><col style="width:64px">'
          '<col style="width:132px"></colgroup><thead><tr>'
          '<th>时间</th><th>弹幕</th><th>情感</th><th>主题</th>'
          '</tr></thead><tbody id="dm-body"></tbody></table></div>'
        + '<p class="note" id="dm-cnt" style="margin-top:8px">—</p>'
        + sec("03", "口径与边界", "结论能用，但别把它当产品周期的结论。")
        + '<div class="card"><p class="note">'
          "1. 情感标签为外部 AI 全量打标（正 / 中 / 负，弹幕另含 惊讶 / 仪式）；"
          "第二模型交叉验证一致性 0.58–0.75，占比结论可用，但不宜声称“高度可靠”。<br>"
          "2. 弹幕负向仅 3.4%，不代表满意——弹幕场景天然不爱发负面，负向判断必须以评论为主。<br>"
          "3. 主题归并损失：547 簇压到 13 类后，“其他/综合”占 15%–41%，影响绝对值，不影响跨平台比较。<br>"
          "4. 单条视频、非概率抽样，描述的是这一支演示的舆论结构，不能外推到整个产品周期。<br>"
          "5. 峰谷必须人工回看画面——这是本分析里唯一不可自动化的环节，也是结论可信度的来源。"
          "</p></div>"
    )


def page_report(kicker, title, sub, md_text, md_bytes, fname):
    return (
        masthead(kicker, title, sub)
        + f'<div class="report">{render_md(md_text)}</div>'
        + f'<a class="btn" download="{fname}" href="{b64_uri(md_bytes, "text/markdown")}">下载 Markdown</a>'
    )


# ---------------------------------------------------------------- 样式
CSS = """
*{box-sizing:border-box}
html,body{margin:0;background:@PAPER@;color:@INK@}
body{font-family:"Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif;font-size:14px;
line-height:1.8;-webkit-font-smoothing:antialiased}
h1,h2,h3,h4{font-family:"Noto Serif SC","Songti SC","SimSun",serif;font-weight:700;color:@INK@}
a{color:@ACCENT@}
.layout{display:flex;align-items:flex-start;min-height:100vh}
.side{position:sticky;top:0;height:100vh;width:258px;flex:0 0 258px;overflow:auto;
background:#efe9df;border-right:1px solid @RULE@;padding:26px 20px 40px}
.brand{font-family:serif;font-size:21px;font-weight:700;letter-spacing:.06em}
.brandsub{font-size:11px;color:@MUTED@;line-height:1.7;margin:6px 0 18px;letter-spacing:.04em}
.nav{display:flex;flex-direction:column;gap:2px;border-top:1px solid @RULE@;padding-top:12px}
.nav a{display:block;padding:9px 10px;font-size:13.5px;color:@MUTED@;text-decoration:none;
border-left:3px solid transparent;letter-spacing:.02em}
.nav a:hover{color:@INK@}
.nav a.on{color:@INK@;font-weight:600;border-left-color:@ACCENT@;background:#faf6f0}
.side-note{font-size:11px;color:@MUTED@;line-height:1.9;margin-top:22px;
border-top:1px solid @RULE@;padding-top:14px}
main{flex:1;min-width:0;padding:34px 4vw 80px}
.wrap{max-width:1000px;margin:0 auto}
.page{display:none}
.page.on{display:block}
.masthead{border-top:3px solid @INK@;border-bottom:1px solid @RULE@;padding:20px 0 16px;margin-bottom:22px}
.kicker{font-size:11.5px;letter-spacing:.3em;color:@ACCENT@;font-weight:600}
.masthead h1{font-size:clamp(26px,2.6vw,34px);margin:8px 0 6px;letter-spacing:.03em}
.sub{color:@MUTED@;font-size:13.5px;letter-spacing:.04em}
.sec-title{display:flex;align-items:baseline;gap:12px;margin:30px 0 4px}
.sec-title .num{font-family:serif;color:@ACCENT@;font-size:12px;letter-spacing:.22em}
.sec-title h2{font-size:21px;margin:0}
.sec-sub{color:@MUTED@;font-size:13px;margin:0 0 10px}
.note{font-size:12.5px;color:@MUTED@;line-height:1.9;margin:10px 0 20px}
.note b{color:@INK@}
.card{background:@SURFACE@;border:1px solid @RULE@;padding:18px 20px;margin:14px 0}
.card h4{margin:0 0 8px;font-size:16px}
.card .note{margin:0}
.verdict{background:@INK@;color:#f5f1e8;padding:18px 22px;margin:16px 0 20px;
font-size:15px;line-height:2.0}
.verdict b{color:#e0b04a;font-weight:600}
.verdict .tag{display:inline-block;font-size:11px;letter-spacing:.22em;color:#e0b04a;margin-bottom:6px}
.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:@RULE@;
border:1px solid @RULE@;margin:16px 0 22px}
.kpi{background:@SURFACE@;padding:16px 18px 14px}
.kpi .v{font-family:serif;font-size:30px;font-weight:700;color:@ACCENT@;line-height:1.2}
.kpi .l{font-size:11.5px;letter-spacing:.16em;color:@MUTED@;margin-top:6px}
.kpi .n{font-size:12px;color:@MUTED@;margin-top:4px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:22px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.chart{margin:8px 0}
.chip{display:inline-block;border:1px solid @RULE@;background:@SURFACE@;padding:2px 9px;
margin:0 6px 6px 0;font-size:12px;color:#5d554a}
.chip .dot{display:inline-block;width:9px;height:9px;margin-right:6px}
.chip .cnt{color:#a99f90;margin-left:4px}
.word-h{font-size:12.5px;font-weight:600;margin:12px 0 6px}
.action{background:@SURFACE@;border:1px solid @RULE@;border-top:2px solid @ACCENT@;padding:14px 16px}
.action .no{font-family:serif;color:@ACCENT@;font-size:12px;letter-spacing:.2em}
.action h4{font-size:15px;margin:6px 0}
.action p{font-size:12.5px;color:@MUTED@;margin:0;line-height:1.8}
.quote{border-left:3px solid @ACCENT@;padding:6px 0 6px 14px;margin:10px 0;
font-size:13px;color:#4a443c;line-height:1.85}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-weight:600;color:@MUTED@;font-size:11.5px;letter-spacing:.12em;
border-bottom:1.5px solid @INK@;padding:8px 10px 7px;white-space:nowrap}
th.r{text-align:right}
td{border-bottom:1px solid @RULE@;padding:9px 10px;vertical-align:top}
td.r{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
tr:nth-child(even) td{background:#fbf8f2}
.tw{overflow-x:auto;margin:10px 0 18px}
.scroll{max-height:420px;overflow:auto;border:1px solid @RULE@;background:@SURFACE@;margin:10px 0}
.scroll td:first-child{white-space:nowrap}
.scroll table{font-size:12.5px}
.scroll thead th{position:sticky;top:0;background:#f4efe5;z-index:1}
.wordcloud,.wc{width:100%;border:1px solid @RULE@;background:@SURFACE@;padding:8px;margin:8px 0 18px}
.btn{display:inline-block;margin:6px 12px 18px 0;padding:9px 16px;background:@INK@;
color:#f5f1e8;text-decoration:none;font-size:13px}
.btn:hover{background:@ACCENT@;color:#fff}
.ctrl{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;margin:12px 0 14px}
.ctrl label{display:flex;flex-direction:column;gap:5px;font-size:11.5px;letter-spacing:.12em;
color:@MUTED@;max-width:100%}
select{background:@SURFACE@;border:1px solid @RULE@;padding:7px 10px;font-size:13px;
color:@INK@;font-family:inherit;border-radius:0;min-width:130px;letter-spacing:0}
input[type=range]{accent-color:@ACCENT@;width:170px;margin:6px 0}
.seg{display:inline-flex;flex-wrap:wrap;border:1px solid @RULE@;background:@SURFACE@}
.seg button{border:0;background:transparent;padding:7px 11px;font-size:12.5px;color:@MUTED@;
cursor:pointer;font-family:inherit}
.seg button.on{background:@INK@;color:#f5f1e8}
.report{max-width:860px;font-size:14.5px;line-height:2.0;color:#38332c}
.report h1{font-size:26px;margin:18px 0 10px}
.report h2{font-size:19px;margin:34px 0 14px;padding:8px 14px 8px 16px;
border-left:5px solid @ACCENT@;background:linear-gradient(90deg,#f2eae0,rgba(248,246,242,0));
letter-spacing:.02em}
.report h3{font-size:15.5px;margin:24px 0 8px;color:#8f2c1b;padding-left:12px;position:relative}
.report h3:before{content:"";position:absolute;left:0;top:.5em;width:5px;height:5px;
background:@GOLD@;border-radius:50%}
.report p{margin:12px 0}
.report b{color:#96301c;font-weight:600}
.report .view{margin:18px 0;padding:13px 18px;
background:linear-gradient(90deg,rgba(176,50,28,.07),rgba(176,50,28,.015));
border-left:3px solid @ACCENT@;border-radius:0 2px 2px 0}
.report .view b{color:#8f2c1b}
.report ul,.report ol{padding-left:20px;margin:8px 0 16px}
.report li{margin:5px 0}
.report li::marker{color:@ACCENT@}
.report .mdquote{border-left:3px solid @GOLD@;background:#fbf7ee;padding:10px 16px;
margin:14px 0;color:#6a6155;font-size:13px}
.report .mdquote p{margin:4px 0}
.report code{background:#f3ece2;padding:1px 5px;font-size:12.5px;color:#6b3b2a}
.report hr{border:none;border-top:1px solid @RULE@;margin:26px 0}
.report table{font-size:12.8px}
.report td{line-height:1.7}
footer{margin-top:40px;padding-top:16px;border-top:1px solid @RULE@;
color:@MUTED@;font-size:11.5px;line-height:1.9}
@media (max-width:1100px){.kpi-row{grid-template-columns:repeat(2,1fr)}
.grid2{grid-template-columns:1fr !important}.grid3{grid-template-columns:1fr}}
@media (max-width:900px){.layout{display:block}
.side{position:static;width:auto;height:auto;border-right:0;border-bottom:1px solid @RULE@;padding:18px}
.nav{flex-direction:row;flex-wrap:wrap;gap:4px}
.nav a{border-left:0;border-bottom:3px solid transparent;padding:8px 10px}
.nav a.on{border-left:0;border-bottom-color:@ACCENT@}
main{padding:20px 5vw 60px}}
"""


# ---------------------------------------------------------------- 交互
JS = """
const PAY=JSON.parse(document.getElementById('payload').textContent);
const $=id=>document.getElementById(id);
const esc=v=>{const d=document.createElement('div');d.textContent=(v==null?'':String(v));return d.innerHTML;};
const fmtT=m=>{const s=Math.round(m*60);return Math.floor(s/60)+':'+String(s%60).padStart(2,'0');};

const tabs=[...document.querySelectorAll('.nav a')];
function resizeIn(id){
  const root=document.querySelector('#'+id);
  if(!root)return;
  root.querySelectorAll('.plotly-graph-div').forEach(el=>{try{Plotly.Plots.resize(el)}catch(e){}});
}
function go(id){
  tabs.forEach(a=>a.classList.toggle('on',a.dataset.id===id));
  document.querySelectorAll('.page').forEach(p=>p.classList.toggle('on',p.id===id));
  try{history.replaceState(null,'','#'+id)}catch(e){}
  window.scrollTo(0,0);
  setTimeout(()=>resizeIn(id),60);
}
tabs.forEach(a=>a.addEventListener('click',e=>{e.preventDefault();go(a.dataset.id);}));
go(location.hash.replace('#','')||'brief');

/* CSV */
function csvOf(tableId){
  const rows=[...$(tableId).querySelectorAll('tr')];
  return '\\ufeff'+rows.map(tr=>[...tr.children].map(td=>'"'+td.innerText.replace(/"/g,'""')+'"').join(',')).join('\\r\\n');
}
function save(name,text,type){
  const b=new Blob([text],{type:type||'text/csv;charset=utf-8'});
  const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name;a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),800);
}

/* 评论明细 */
function renderComments(){
  const p=$('c-plat').value,se=$('c-senti').value,lv=$('c-level').value,th=$('c-theme').value;
  const rows=PAY.comments.filter(r=>(!p||r[0]===p)&&(!se||r[2]===se)&&(!lv||r[4]===lv)&&(!th||r[3]===th));
  $('c-body').innerHTML=rows.map(r=>
    `<tr><td>${esc(r[0])}</td><td class="txt">${esc(r[1])}</td><td>${esc(r[2])}</td><td>${esc(r[3])}</td><td>${esc(r[4])}</td></tr>`
  ).join('');
  $('c-cnt').textContent=`当前 ${rows.length.toLocaleString()} 行；共 ${PAY.comments_total.toLocaleString()} 行。静态版为单选筛选，默认只看小黑盒。`;
}
['c-plat','c-senti','c-level','c-theme'].forEach(id=>$(id).addEventListener('change',renderComments));
$('c-export').addEventListener('click',e=>{e.preventDefault();save('comments_view.csv',csvOf('c-table'));});

/* 弹幕明细 */
function renderDanmaku(){
  let a=parseFloat($('dm-a').value),b=parseFloat($('dm-b').value);
  if(a>b){b=a;$('dm-b').value=b;}
  $('dm-a-val').textContent=a.toFixed(1);$('dm-b-val').textContent=b.toFixed(1);
  const se=$('dm-senti').value,th=$('dm-theme').value;
  const rows=PAY.danmaku.filter(r=>r[0]>=a&&r[0]<=b&&(!se||r[2]===se)&&(!th||r[3]===th));
  $('dm-body').innerHTML=rows.slice(0,400).map(r=>
    `<tr><td class="r">${fmtT(r[0])}</td><td class="txt">${esc(r[1])}</td><td>${esc(r[2])}</td><td>${esc(r[3])}</td></tr>`
  ).join('');
  $('dm-cnt').textContent=`当前 ${rows.length.toLocaleString()} 行；表格最多显示 400 行。`;
}
['dm-a','dm-b'].forEach(id=>$(id).addEventListener('input',renderDanmaku));
['dm-senti','dm-theme'].forEach(id=>$(id).addEventListener('change',renderDanmaku));

/* 主题明细 */
let topSort={k:null,d:1};
function renderTopics(){
  const p=$('t-plat').value,th=$('t-theme').value;
  let rows=PAY.topics.filter(r=>(!p||r[0]===p)&&(!th||r[1]===th));
  if(topSort.k!==null){const k=topSort.k,dir=topSort.d;rows=rows.slice().sort((x,y)=>dir*(x[k]-y[k]));}
  else rows=rows.slice().sort((x,y)=>x[0].localeCompare(y[0],'zh')||y[2]-x[2]);
  $('t-body').innerHTML=rows.map(r=>
    `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td><td class="r">${r[2]}</td><td class="r">${r[3].toFixed(1)}</td><td>${esc(r[4])}</td><td class="r">${r[5].toFixed(3)}</td></tr>`
  ).join('');
  $('t-cnt').textContent=`当前 ${rows.length.toLocaleString()} 行。`;
}
['t-plat','t-theme'].forEach(id=>$(id).addEventListener('change',()=>{topSort={k:null,d:1};renderTopics();}));
document.querySelectorAll('#t-table th[data-k]').forEach(th=>{
  th.style.cursor='pointer';
  th.addEventListener('click',()=>{
    const k=Number(th.dataset.k);
    if(topSort.k===k){topSort.d*=-1}else{topSort.k=k;topSort.d=1}
    renderTopics();
  });
});
$('t-export').addEventListener('click',e=>{e.preventDefault();save('topics_view.csv',csvOf('t-table'));});

/* 窗口回放 */
function showPeak(){
  const p=PAY.peaks[Number($('pk-sel').value)];
  $('pk-rank').textContent=p.rank+' · '+(p.topic||'弹幕量峰');
  $('pk-scene').textContent=p.scene||'未标注场景';
  $('pk-ev').textContent=p.evidence||'—';
  $('pk-body').innerHTML=p.top.map(t=>`<tr><td>${esc(t[0])}</td><td class="r">${t[1]}</td></tr>`).join('');
}
$('pk-sel').addEventListener('change',showPeak);

/* 词云 */
$('wc-sel').addEventListener('change',()=>{
  const i=Number($('wc-sel').value);
  document.querySelectorAll('.wc').forEach((im,k)=>{im.style.display=(k===i?'block':'none')});
});

/* 主题拆分 */
function renderRep(){
  const th=PAY.themes[Number($('th-sel').value)];
  const pl=document.querySelector('#pl-seg button.on').dataset.p;
  const data=PAY.rep[pl+'|'+th]||{n:{},words:{}};
  const meta={positive:['正向','#b0321c'],neutral:['中性','#b9ac9a'],negative:['负向','#234f47']};
  $('rep-box').innerHTML=['positive','neutral','negative'].map(k=>{
    const [cn,color]=meta[k],arr=(data.words&&data.words[k])||[],n=(data.n&&data.n[k])||0;
    const head=`<div class="word-h" style="color:${color}">${cn}<span style="color:#a99f90;font-weight:400;margin-left:8px">样本 ${n.toLocaleString()} 条</span></div>`;
    const body=arr.length?arr.map(w=>`<span class="chip">${esc(w[0])}<span class="cnt">${w[1]}</span></span>`).join(''):'<span class="note" style="margin:0">无</span>';
    return head+body;
  }).join('');
}
function showTheme(){
  const i=Number($('th-sel').value);
  document.querySelectorAll('.tc').forEach((d,k)=>{d.style.display=(k===i?'block':'none')});
  setTimeout(()=>{const box=document.querySelectorAll('.tc')[i];const g=box&&box.querySelector('.plotly-graph-div');if(g){try{Plotly.Plots.resize(g)}catch(e){}}},60);
  renderRep();
}
$('th-sel').addEventListener('change',showTheme);
document.querySelectorAll('#pl-seg button').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('#pl-seg button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');renderRep();
}));

/* 初始化 */
renderComments();
renderDanmaku();
renderTopics();
showPeak();
showTheme();
"""


# ---------------------------------------------------------------- 组装
def build():
    d = load()
    overall = theme_overall(d["themes"])
    OUT.mkdir(exist_ok=True)

    summary_md = (REPORTS / "executive-summary.md").read_text(encoding="utf-8")
    pdf = REPORTS / "executive-summary.pdf"
    pdf_uri = b64_uri(pdf.read_bytes(), "application/pdf") if pdf.exists() else "#"

    report_md = (REPORTS / "report.md").read_text(encoding="utf-8")
    fqa_md = (REPORTS / "five-question-analysis.md").read_text(encoding="utf-8")

    # ---- 主题页：代表词（按平台 × 主题）
    cand = overall[overall["n"] >= 120]["theme"].tolist()
    cand_set = set(cand)
    rep = {}
    for p in PLATFORMS:
        src = rows_for(d, p)
        for th, g in src.groupby("theme"):
            if th in cand_set:
                rep[f"{p}|{th}"] = compute_rep(g)

    # ---- 时间轴：每个峰谷窗口的高频弹幕
    peaks_payload = []
    for _, r in d["peaks"].iterrows():
        win = d["danmaku"][(d["danmaku"]["t_sec"] >= r["t_start"])
                           & (d["danmaku"]["t_sec"] < r["t_end"])]
        vc = win["text"].value_counts().head(8)
        peaks_payload.append({
            "rank": r["rank"], "kind": r["kind"],
            "topic": r["event_topic"] if isinstance(r["event_topic"], str) else None,
            "scene": r["scene"] if isinstance(r["scene"], str) else None,
            "evidence": r["evidence"] if isinstance(r["evidence"], str) else None,
            "top": [[str(k), int(v)] for k, v in vc.items()],
        })

    # ---- 明细数据
    comments_payload = [
        [r.platform, r.text, SENTI_CN.get(r.label, r.label), r.theme,
         "二级" if r.is_reply else "一级"]
        for r in d["comments"].itertuples()
    ]
    danmaku_payload = [
        [round(r.t_sec / 60, 3), r.text, SENTI_CN.get(r.label, r.label), r.theme]
        for r in d["danmaku"].itertuples()
    ]
    topics_payload = [
        [r.platform, r.theme, int(r.size), round(float(r.share) * 100, 1),
         str(r.top_words), round(float(r.mean_sentiment), 3)]
        for r in d["topics"][d["topics"]["theme"] != "未建模"].itertuples()
    ]

    payload = {
        "comments": comments_payload, "comments_total": int(d["stats"]["comments"]),
        "danmaku": danmaku_payload, "topics": topics_payload,
        "peaks": peaks_payload, "rep": rep, "themes": cand, "plats": PLATFORMS,
    }
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    # ---- 页面
    pages = [
        ("brief", "项目说明与摘要", page_brief(summary_md, pdf_uri)),
        ("overview", "概览", page_overview(d, overall)),
        ("sentiment", "情感结构", page_sentiment(d, overall)),
        ("timeline", "弹幕时间轴", page_timeline(d)),
        ("themes", "主题与平台", page_themes(d, overall)),
        ("data", "数据与口径", page_data(d)),
        ("report", "研究报告", page_report(
            "REPORTS / 06", "黑神话·钟馗 社区舆论分析报告",
            "完整分析：热度、情感结构、峰谷、主题、平台差异与建议。摘要见「项目说明与摘要」。",
            report_md, report_md.encode("utf-8"), "report.md")),
        ("fqa", "实机演示分析", page_report(
            "REPORTS / 07", "社区舆论五问分析",
            "五个问题逐条回答：热度形态、内容归因、风险定位、平台差异、工具化需求。",
            fqa_md, fqa_md.encode("utf-8"), "five-question-analysis.md")),
    ]

    nav = "".join(f'<a href="#{i}" data-id="{i}" class="{"on" if k == 0 else ""}">{t}</a>'
                  for k, (i, t, _) in enumerate(pages))
    body = "\n".join(f'<section class="page{" on" if k == 0 else ""}" id="{i}">{c}</section>'
                     for k, (i, _, c) in enumerate(pages))

    css = (CSS.replace("@PAPER@", PAPER).replace("@SURFACE@", SURFACE).replace("@INK@", INK)
           .replace("@MUTED@", MUTED).replace("@RULE@", RULE).replace("@ACCENT@", ACCENT)
           .replace("@ACCENT2@", ACCENT2).replace("@GOLD@", GOLD))

    doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>钟馗 · 舆情看板（静态版）</title>
<style>{css}</style>
<script>{get_plotlyjs()}</script>
</head><body>
<div class="layout">
<aside class="side">
<div class="brand">钟馗 · 舆情看板</div>
<div class="brandsub">COMMUNITY INTELLIGENCE<br>15 分钟实机演示 · 四平台评论 + B站弹幕</div>
<nav class="nav">{nav}</nav>
<p class="side-note">Demo：11,280 条评论 + 24,733 条弹幕。<br>
静态版：图表可交互，筛选与导出都在浏览器本地完成，无需服务端。</p>
</aside>
<main><div class="wrap">
{body}
<footer>数据来源：B站 / 小红书 / 小黑盒 / 微博 公开评论与 B站弹幕；情感由外部 AI 全量打标，
主题由五个数据集聚类后归并。本页为静态导出版，交互图表可离线打开。</footer>
</div></main>
</div>
<script id="payload" type="application/json">{payload_json}</script>
<script>{JS}</script>
</body></html>"""

    (OUT / "index.html").write_text(doc, encoding="utf-8")
    size = (OUT / "index.html").stat().st_size / 1024
    print(f"ok static/index.html {size:.0f} KB")


if __name__ == "__main__":
    build()
