# -*- coding: utf-8 -*-
"""全站共用的常量、色板与样式。"""

PAPER = "#f8f6f2"
SURFACE = "#fffdf8"
INK = "#23201c"
MUTED = "#7d7468"
RULE = "#e2dacd"
ACCENT = "#b0321c"     # 朱砂
ACCENT2 = "#234f47"    # 墨绿
GOLD = "#c9a227"       # 赭金

SENTI_COLOR = {
    "positive": ACCENT,
    "neutral": "#b9ac9a",
    "negative": ACCENT2,
    "surprise": "#4a6fa5",
    "ritual": GOLD,
}
SENTI_CN = {"positive": "正向", "neutral": "中性", "negative": "负向",
            "surprise": "惊讶", "ritual": "仪式"}

PLATFORM_COLOR = {
    "B站": "#b0321c",
    "小红书": "#c9694f",
    "小黑盒": "#234f47",
    "微博": "#4a6fa5",
}

THEME_COLOR = {
    "战斗打击感": "#b0321c",
    "画面美术": "#c9694f",
    "角色形象": "#8c3b52",
    "剧情叙事": "#4a6fa5",
    "玩法系统": "#5b7f6f",
    "技术性能": "#234f47",
    "音乐音效": "#c9a227",
    "换皮争议": "#6b5b4a",
    "期待对比": "#a8845c",
    "仪式玩梗": "#d9b04a",
    "角色扮演/身份认同": "#7a6a8f",
    "营销社区": "#9b8770",
    "其他/综合": "#c3b8a8",
    "未建模": "#ded6c9",
}

CSS = f"""
<style>
:root {{
  --paper: {PAPER};
  --surface: {SURFACE};
  --ink: {INK};
  --muted: {MUTED};
  --rule: {RULE};
  --accent: {ACCENT};
  --accent2: {ACCENT2};
  --gold: {GOLD};
  --serif: "Noto Serif SC", "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", "SimSun", serif;
  --sans: "Noto Sans SC", "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif;
}}
html, body, .stApp, [data-testid="stAppViewContainer"] {{
  background: var(--paper);
  color: var(--ink);
  font-family: var(--sans);
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{
  background: #efe9df;
  border-right: 1px solid var(--rule);
}}
[data-testid="stSidebar"] * {{ font-family: var(--sans); }}
[data-testid="stSidebar"] .stRadio label p {{ font-size: 14px; }}
.block-container {{ padding-top: 2.4rem; padding-bottom: 3rem; max-width: 1180px; }}

h1, h2, h3, h4 {{ font-family: var(--serif); font-weight: 700; color: var(--ink); }}
p, li, .stMarkdown {{ line-height: 1.85; }}
a {{ color: var(--accent); }}

.masthead {{
  border-top: 3px solid var(--ink);
  border-bottom: 1px solid var(--rule);
  padding: 20px 0 16px;
  margin-bottom: 22px;
}}
.masthead .kicker {{
  font-size: 11.5px; letter-spacing: .3em; color: var(--accent); font-weight: 600;
}}
.masthead h1 {{ font-size: clamp(26px, 2.6vw, 34px); margin: 8px 0 6px; letter-spacing: .03em; }}
.masthead .sub {{ color: var(--muted); font-size: 13.5px; letter-spacing: .04em; }}

.verdict {{
  background: var(--ink); color: #f5f1e8;
  padding: 18px 22px; margin: 6px 0 18px;
  font-size: 15px; line-height: 2.0;
}}
.verdict b {{ color: #e0b04a; font-weight: 600; }}
.verdict .tag {{
  display: inline-block; font-size: 11px; letter-spacing: .22em;
  color: #e0b04a; margin-bottom: 6px;
}}

.kpi-row {{
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 1px; background: var(--rule);
  border: 1px solid var(--rule); margin: 4px 0 20px;
}}
.kpi {{ background: var(--surface); padding: 16px 18px 14px; }}
.kpi .v {{ font-family: var(--serif); font-size: 30px; font-weight: 700; color: var(--accent); line-height: 1.2; }}
.kpi .v small {{ font-size: 14px; color: var(--muted); font-weight: 400; }}
.kpi .l {{ font-size: 11.5px; letter-spacing: .16em; color: var(--muted); margin-top: 6px; }}
.kpi .n {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}

.sec-title {{ display: flex; align-items: baseline; gap: 12px; margin: 26px 0 4px; }}
.sec-title .num {{ font-family: var(--serif); color: var(--accent); font-size: 12px; letter-spacing: .22em; }}
.sec-title h2 {{ font-size: 21px; margin: 0; }}
.sec-sub {{ color: var(--muted); font-size: 13px; margin: 0 0 10px; }}

.card {{
  background: var(--surface); border: 1px solid var(--rule);
  padding: 18px 20px; margin-bottom: 14px;
}}
.card h4 {{ margin: 0 0 8px; font-size: 16px; }}
.card .note {{ font-size: 12.5px; color: var(--muted); line-height: 1.8; }}

.note {{ font-size: 12.5px; color: var(--muted); line-height: 1.85; }}
.rule {{ border-top: 1px solid var(--rule); margin: 18px 0; }}

table.editorial {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
table.editorial th {{
  text-align: left; font-weight: 600; color: var(--muted);
  font-size: 11.5px; letter-spacing: .12em;
  border-bottom: 1.5px solid var(--ink); padding: 8px 10px 7px;
}}
table.editorial td {{ border-bottom: 1px solid var(--rule); padding: 9px 10px; vertical-align: top; }}
table.editorial td.strong {{ font-weight: 600; }}
table.editorial td.num {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}

.quote {{
  border-left: 3px solid var(--accent);
  padding: 6px 0 6px 14px; margin: 10px 0;
  font-size: 13px; color: #4a443c;
}}
.chip {{
  display: inline-block; border: 1px solid var(--rule); background: var(--surface);
  padding: 2px 9px; margin: 0 6px 6px 0; font-size: 12px; color: #5d554a;
}}
.action {{
  background: var(--surface); border: 1px solid var(--rule); border-top: 2px solid var(--accent);
  padding: 14px 16px; height: 100%;
}}
.action .no {{ font-family: var(--serif); color: var(--accent); font-size: 12px; letter-spacing: .2em; }}
.action h4 {{ font-size: 15px; margin: 6px 0 6px; }}
.action p {{ font-size: 12.5px; color: var(--muted); margin: 0; line-height: 1.8; }}

div[data-testid="stDataFrame"] {{ border: 1px solid var(--rule); }}
.stButton button, .stDownloadButton button {{
  background: var(--ink); color: #f5f1e8; border: none; border-radius: 0;
  padding: 8px 18px; font-size: 13px;
}}
.stButton button:hover, .stDownloadButton button:hover {{ background: var(--accent); color: #fff; }}
[data-testid="stFileUploader"] section {{ background: var(--surface); border: 1px dashed #c9bfae; }}
.stAlert {{ border-radius: 0; }}
footer {{ visibility: hidden; }}
[data-testid="stToolbar"] {{ display: none; }}

@media (max-width: 1000px) {{
  .kpi-row {{ grid-template-columns: repeat(2, 1fr); }}
  .block-container {{ padding-top: 1.6rem; }}
}}
</style>
"""
