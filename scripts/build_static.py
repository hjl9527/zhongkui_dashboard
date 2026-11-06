# -*- coding: utf-8 -*-
"""把看板导出为一个自包含的静态 HTML：static/index.html（含交互图表，无需服务端）。

用法：python scripts/build_static.py
产出：static/index.html（可直接双击打开 / 上传 GitHub Pages）
"""
import html
import json
import re
import shutil
import sys
from pathlib import Path

import pandas as pd
import plotly.io as pio
from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import charts as C

DATA = ROOT / "data"
REPORTS = ROOT / "reports"
OUT = ROOT / "static"

PAPER, INK, MUTED, RULE = "#f8f6f2", "#23201c", "#7d7468", "#e2dacd"
ACCENT, ACCENT2, GOLD = "#b0321c", "#234f47", "#c9a227"


# ---------------------------------------------------------------- markdown → html
def inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return s


def md_to_html(md):
    out, i, lines = [], 0, md.splitlines()
    n = len(lines)
    while i < n:
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        if s.startswith("# "):
            out.append(f"<h1>{inline(s[2:])}</h1>")
            i += 1
        elif s.startswith("## "):
            out.append(f"<h2>{inline(s[3:])}</h2>")
            i += 1
        elif s.startswith("### "):
            out.append(f"<h3>{inline(s[4:])}</h3>")
            i += 1
        elif s.startswith("|"):
            rows = []
            while i < n and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            rows = [r for r in rows if not set("".join(r)) <= set("-: ")]
            if not rows:
                continue
            th = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
            tb = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                         for r in rows[1:])
            out.append(f"<div class='tw'><table><thead><tr>{th}</tr></thead>"
                       f"<tbody>{tb}</tbody></table></div>")
        elif s.startswith("- ") or re.match(r"\d+\.\s", s):
            items = []
            while i < n and (lines[i].strip().startswith("- ")
                             or re.match(r"\d+\.\s", lines[i].strip())):
                items.append(lines[i].strip())
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x.lstrip('- '))}</li>" for x in items)
                       + "</ul>")
        else:
            out.append(f"<p>{inline(s)}</p>")
            i += 1
    return "\n".join(out)


# ---------------------------------------------------------------- 数据
def load():
    return {
        "comments": pd.read_parquet(DATA / "comments.parquet"),
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
    return out.sort_values("n", ascending=False)


def embed(fig):
    return pio.to_html(fig, include_plotlyjs=False, full_html=False,
                       config={"displayModeBar": False, "responsive": True})


def num(v):
    return f"{v:,}"


def mmss(sec):
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


MACRO = [
    ("B站", "1,359.7w", "97.1w", "23.1w", "50.2w", "11.6w"),
    ("微博", "239w", "1.4w", "—", "3430", "1801"),
    ("小红书", "/", "4.8w", "7606", "2.9w", "4184"),
    ("小黑盒", "/", "1.8w", "2544", "7288", "7288"),
    ("YouTube", "358w", "16w", "/", "/", "1.4w"),
]


def build():
    d = load()
    overall = theme_overall(d["themes"])
    stats = d["stats"]
    OUT.mkdir(exist_ok=True)

    # ---- 摘要
    summary_md = (REPORTS / "executive-summary.md").read_text(encoding="utf-8")
    summary_html = md_to_html(summary_md)

    # ---- 宏观 + KPI
    macro_rows = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in MACRO)
    n_themes = int(d["themes"][d["themes"]["theme"] != "未建模"]["theme"].nunique())
    kpis = [(num(stats["comments"]), "评论总量", "四平台 · 45.6% 为二级评论"),
            (num(stats["danmaku"]), "弹幕总量", "单支视频 · 953 秒"),
            (num(int(stats["danmaku_per_min"])), "弹幕 / 分钟", "事件级密度"),
            (str(n_themes), "统一主题", "547 簇归并")]

    # ---- 平台表
    g2 = d["topics"][d["topics"]["theme"] != "未建模"].copy()
    g2["s"] = g2["share"] / g2.groupby("platform")["share"].transform("sum")
    hhi = (g2["s"] ** 2).groupby(g2["platform"]).sum()
    top3 = (g2[~g2["theme"].isin(["其他/综合"])]
            .sort_values("s", ascending=False).groupby("platform").head(3))
    ev = {p: "<br>".join(f"{r.theme} {r.s * 100:.1f}%" for r in g.itertuples())
          for p, g in top3.groupby("platform")}
    meta = {
        "小黑盒": ("战斗评估 + 原创性质疑", "先立新作锚点，用新作的差别回应换皮争议"),
        "小红书": ("战斗 + 画面审美", "强调画面质感：光照、材质、场景"),
        "微博": ("战斗 + 期待表态", "放预约入口 + 定档信息，便于转发扩散"),
        "B站": ("战斗 + 技术/角色", "角色特写与设定图优先，留出二创空间"),
        "B站弹幕": ("仪式玩梗为主", "保留仪式梗生态，但不要把梗当评价"),
    }
    mean = (d["themes"][d["themes"]["theme"] != "未建模"]
            .assign(w=lambda x: x["n"] * x["mean_sentiment"])
            .groupby("platform_name")[["w", "n"]].sum().pipe(lambda x: x["w"] / x["n"]))
    prows = []
    for p in ["小黑盒", "小红书", "微博", "B站", "B站弹幕"]:
        focus, advice = meta[p]
        m = "—" if p == "B站弹幕" else f"{mean.get(p, 0):+.3f}"
        prows.append(f"<tr><td>{p}</td><td class='ev'>{ev.get(p, '—')}</td>"
                     f"<td class='r'>{1 / hhi.loc[p]:.1f}</td><td class='r'>{m}</td>"
                     f"<td>{focus}</td><td>{advice}</td></tr>")
    platform_table = (
        "<table><thead><tr><th>平台</th><th>前 3 主题（占比）</th><th>有效话题数</th>"
        "<th>情绪分</th><th>主题侧重</th><th>宣传物料投放建议</th></tr></thead><tbody>"
        + "".join(prows) + "</tbody></table>")

    # ---- 主题明细
    trows = "".join(
        f"<tr><td>{r.theme}</td><td class='r'>{num(int(r.n))}</td>"
        f"<td class='r'>{r.positive_rate * 100:.1f}%</td>"
        f"<td class='r'>{r.negative_rate * 100:.1f}%</td>"
        f"<td class='r'>{r['net'] * 100:+.1f}</td></tr>"
        for _, r in overall.iterrows())

    # ---- 峰谷表
    peaks = d["peaks"].copy()
    pk_rows = ""
    for _, r in peaks.iterrows():
        span = f"{mmss(r['t_start'])}–{mmss(r['t_end'])}"
        val = f"{r['value']:+.3f}" if r["kind"] != "弹幕量峰" else "—"
        evt = (r["event_topic"] if isinstance(r["event_topic"], str)
               else ("齐刷段：情绪同步，不计入情感峰" if r["kind"] == "弹幕量峰" else "—"))
        pk_rows += (f"<tr><td>{r['rank']}</td><td>{r['kind']}</td><td>{span}</td>"
                    f"<td class='r'>{num(int(r['n']))}</td><td class='r'>{val}</td>"
                    f"<td>{r['label_mix']}</td><td>{evt}</td></tr>")
    peak_table = ("<table><thead><tr><th>编号</th><th>类型</th><th>时段</th><th>弹幕量</th>"
                  "<th>情感值</th><th>标签构成</th><th>现场 / 事件</th></tr></thead><tbody>"
                  + pk_rows + "</tbody></table>")

    # ---- 报告
    report_html = (md_to_html((REPORTS / "report.md").read_text(encoding="utf-8"))
                   + md_to_html((REPORTS / "five-question-analysis.md").read_text(encoding="utf-8")))

    copy_pdf = REPORTS / "executive-summary.pdf"
    if copy_pdf.exists():
        shutil.copy(copy_pdf, OUT / "executive-summary.pdf")

    kpi_html = "".join(f"<div class='kpi'><div class='v'>{v}</div>"
                       f"<div class='l'>{l}</div><div class='n'>{s}</div></div>"
                       for v, l, s in kpis)

    charts = {
        "lv": embed(C.fig_level_positive(d["summary"])),
        "var": embed(C.fig_theme_variance(overall)),
        "stack": embed(C.fig_level_stack(d["summary"])),
        "heat": embed(C.fig_theme_heat(d["themes"], overall)),
        "net": embed(C.fig_theme_net(overall)),
        "tl": embed(C.fig_timeline(d["windows"], d["peaks"],
                                   duration=stats["duration_sec"])),
        "share": embed(C.fig_theme_share(d["topics"])),
    }

    css = f"""
*{{box-sizing:border-box}}
body{{margin:0;background:{PAPER};color:{INK};
font-family:"Source Han Serif SC","Songti SC","Microsoft YaHei",serif;line-height:1.75}}
header{{padding:34px 6vw 14px}}
.kicker{{font-size:11px;letter-spacing:.22em;color:{ACCENT};font-weight:700}}
h1{{font-size:30px;margin:8px 0 6px;letter-spacing:.02em}}
.sub{{color:{MUTED};font-size:13.5px}}
nav{{position:sticky;top:0;background:{PAPER};border-bottom:1px solid {RULE};
padding:0 6vw;display:flex;gap:22px;flex-wrap:wrap;z-index:20}}
nav a{{padding:12px 2px 10px;font-size:13.5px;color:{MUTED};text-decoration:none;
border-bottom:3px solid transparent}}
nav a.on{{color:{INK};border-bottom-color:{ACCENT};font-weight:700}}
main{{padding:8px 6vw 70px}}
section{{display:none;max-width:960px}}
section.on{{display:block}}
h2{{font-size:19px;margin:30px 0 6px;padding-left:10px;border-left:4px solid {ACCENT}}}
h3{{font-size:15px;margin:22px 0 6px;color:{ACCENT}}}
p{{font-size:14px;margin:8px 0}}
.note{{font-size:12.5px;color:{MUTED};background:#fffdf8;border:1px solid {RULE};
padding:10px 12px;margin:10px 0 22px}}
.kpirow{{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}}
.kpi{{flex:1 1 160px;background:#fffdf8;border:1px solid {RULE};padding:14px 16px}}
.kpi .v{{font-size:26px;font-weight:700;color:{ACCENT}}}
.kpi .l{{font-size:12.5px;margin-top:2px}}
.kpi .n{{font-size:11.5px;color:{MUTED}}}
.tw{{overflow-x:auto;margin:12px 0 20px}}
table{{border-collapse:collapse;width:100%;background:#fffdf8;font-size:12.8px}}
th{{background:{INK};color:#fff;text-align:left;padding:7px 8px;font-weight:600;
white-space:nowrap}}
td{{padding:7px 8px;border-bottom:1px solid {RULE};vertical-align:top}}
tr:nth-child(even) td{{background:#fbf8f2}}
td.r{{text-align:right;white-space:nowrap}}
td.ev{{white-space:nowrap;line-height:1.9}}
.chart{{margin:10px 0}}
ul{{margin:8px 0 18px;padding-left:20px}}
li{{font-size:13.6px;margin:4px 0}}
.btn{{display:inline-block;margin:10px 0 18px;padding:9px 16px;background:{ACCENT};
color:#fff;text-decoration:none;font-size:13px}}
footer{{padding:30px 6vw 50px;color:{MUTED};font-size:11.5px;border-top:1px solid {RULE}}}
"""

    js = """
const tabs=[...document.querySelectorAll('nav a')];
const secs=[...document.querySelectorAll('section')];
function go(id){
 tabs.forEach(a=>a.classList.toggle('on',a.dataset.id===id));
 secs.forEach(s=>s.classList.toggle('on',s.id===id));
 window.scrollTo({top:0});
}
tabs.forEach(a=>a.onclick=e=>{e.preventDefault();go(a.dataset.id);});
go('brief');
"""

    doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>钟馗 · 舆情看板（静态版）</title>
<style>{css}</style>
<script>{get_plotlyjs()}</script>
</head><body>
<header>
<div class="kicker">COMMUNITY INTELLIGENCE · STATIC EDITION</div>
<h1>钟馗实机演示 · 舆情看板</h1>
<div class="sub">B站 / 小红书 / 小黑盒 / 微博评论 11,280 条 ＋ B站弹幕 24,733 条 ｜ 15 分 53 秒实机演示 ｜ 静态版，可直接离线打开</div>
</header>
<nav>
<a href="#" data-id="brief" class="on">项目说明与摘要</a>
<a href="#" data-id="overview">概览</a>
<a href="#" data-id="sentiment">情感结构</a>
<a href="#" data-id="timeline">弹幕时间轴</a>
<a href="#" data-id="themes">主题与平台</a>
<a href="#" data-id="report">研究报告</a>
</nav>
<main>
<section id="brief" class="on">{summary_html}
<a class="btn" href="executive-summary.pdf" download>下载摘要 PDF</a>
<p class="note">本页文字与 PDF 同源。交互版（可上传 CSV、按平台筛选）见在线看板。</p>
</section>

<section id="overview">
<h2>一次实机演示，五个数据源</h2>
<p>制作人做了一支 15 分 53 秒的实机演示，由官号分发到 B站、微博、小红书、小黑盒与 YouTube；
运营在各平台采集评论与弹幕，做正/中/负三支情感打标与主题聚类，回答一个问题：<b>这次演示的效果如何</b>。</p>
<table><thead><tr><th>平台</th><th>播放 / 阅读</th><th>点赞</th><th>收藏</th><th>转发</th><th>总评论</th></tr></thead>
<tbody>{macro_rows}</tbody></table>
<div class="kpirow">{kpi_html}</div>
<h2>两个先看的结构信号</h2>
<div class="chart">{charts['lv']}</div>
<p class="note">微博一级正向 41.8%、B站一级 42.5%；但 B站二级负向 12.8% 已反超一级的 5.9%——主楼在表态，楼中楼在追问。</p>
<div class="chart">{charts['var']}</div>
<p class="note">分歧最大的六个主题集中在 0.41–0.49，彼此差距很小，排名不必细究；有用的是方向：角色形象、战斗打击感在平台之间正负翻转，画面美术在四个平台都为正。</p>
<h2>五个数据集，五种主题侧重</h2>
<div class="tw">{platform_table}</div>
<p class="note">四个评论平台第一名都是战斗，差异要看第二、第三名。「有效话题数」＝ 1 ÷ Σ(各主题份额²)，越大越分散，不是主题个数。</p>
<p class="note">口径：情感标签为外部 AI 全量打标（第二模型交叉验证，一致性中等偏强）；弹幕负向仅 3.4%，负向判断以评论为主。</p>
</section>

<section id="sentiment">
<h2>平台 × 评论层级</h2>
<div class="chart">{charts['stack']}</div>
<p class="note">四个平台的二级正向率都明显低于一级：B站 42.5% → 14.0%、小红书 36.8% → 13.6%、小黑盒 32.2% → 12.0%、微博 41.8% → 16.5%。小红书二级情绪分已转负；小黑盒一级负向 24.7% 为四组最高，硬核玩家在主楼就直接下判断。</p>
<h2>主题 × 平台</h2>
<div class="chart">{charts['heat']}</div>
<p class="note">同一主题换平台就换方向：战斗打击感在评论区几乎贴着 0，只有小黑盒转负；换皮争议在微博 +0.40、在小红书与小黑盒 −0.10；角色形象微博 +0.27、小红书 −0.08。差异来自人群，而不是主题本身。</p>
<h2>合并后的主题净情感</h2>
<div class="chart">{charts['net']}</div>
<p class="note">画面美术 +24.2、期待对比 +23.3、音乐音效 +22.3 居前；战斗打击感与换皮争议 +12.0、剧情叙事 +11.5、角色形象 +7.4 垫底。角色形象是“两头都高”的争论型主题；剧情仅 227 条，出现即多为“内容缺失”批评，当风险信号读。</p>
</section>

<section id="timeline">
<h2>弹幕时间轴：注意力与情绪节奏</h2>
<div class="chart">{charts['tl']}</div>
<p class="note">全片 953 秒、24,733 条弹幕，平均每分钟 1,557 条。峰值先看量，再看情感指数是否同向。</p>
<h2>峰谷定位</h2>
<div class="tw">{peak_table}</div>
<p class="note">P = 情感峰，V = 情感谷，N = 弹幕量峰；齐刷段只进 N，不重复计入情感峰，所以“量峰”和“情感峰”略有错位是口径设计。</p>
</section>

<section id="themes">
<h2>讨论结构：13 个主题的占比</h2>
<div class="chart">{charts['share']}</div>
<h2>主题明细（五数据集合并，剔除未建模）</h2>
<div class="tw"><table><thead><tr><th>主题</th><th>样本</th><th>正向</th><th>负向</th>
<th>净情感（百分点）</th></tr></thead><tbody>{trows}</tbody></table></div>
<p class="note">净情感 = 正向占比 − 负向占比。数值越高越安全，接近 0 或转负的主题最需要跟进。</p>
</section>

<section id="report">
{report_html}
</section>
</main>
<footer>数据来源：B站 / 小红书 / 小黑盒 / 微博 公开评论与 B站弹幕；情感由外部 AI 全量打标，主题由五数据集聚类后归并。
本页为静态导出版，交互版见在线看板。</footer>
<script>{js}</script>
</body></html>"""
    (OUT / "index.html").write_text(doc, encoding="utf-8")
    size = (OUT / "index.html").stat().st_size / 1024
    print(f"ok static/index.html {size:.0f} KB")


if __name__ == "__main__":
    build()
