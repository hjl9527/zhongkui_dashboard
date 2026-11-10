# -*- coding: utf-8 -*-
"""把 reports/*.md 排成 A4 PDF：report.pdf、five-question-analysis.pdf。

md 是唯一正文来源，本脚本只负责排版：封面 + 每章另起一页 + 表格自动分页。
改字改数请改 md，再跑：python scripts/make_reports.py
"""
import os
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"

MSYH = r"C:\Windows\Fonts\msyh.ttc"
MSYHBD = r"C:\Windows\Fonts\msyhbd.ttc"
SONG = r"C:\Windows\Fonts\STZHONGS.TTF"

# ---- 配色（与看板同一套中式编辑风） ----
INK = (0.137, 0.125, 0.110)
RED = (0.690, 0.196, 0.110)
GREEN = (0.137, 0.310, 0.278)
GRAY = (0.420, 0.400, 0.345)
LIGHT = (0.560, 0.535, 0.480)
CREAM = (0.973, 0.965, 0.949)
PANEL = (0.953, 0.937, 0.902)
BAND = (0.980, 0.949, 0.932)
LINE = (0.847, 0.816, 0.769)
GOLD = (0.788, 0.635, 0.153)
WHITE = (1, 1, 1)
CODE = (0.360, 0.310, 0.245)
BODY_INK = (0.196, 0.180, 0.157)

FW, FH = 595.276, 841.890
MX = 52
CW = FW - 2 * MX
BOTTOM = FH - 56

BODY = 9.0
LEAD = 1.82

REG, BLD, SER = "yh", "yhbd", "song"
_F_REG = pymupdf.Font(fontfile=MSYH)
_F_BLD = pymupdf.Font(fontfile=MSYHBD)
_F_SER = pymupdf.Font(fontfile=SONG)


# ---------------------------------------------------------------- 基础绘制
def measure(s, size, bold=False, font=None):
    f = _F_SER if font == "song" else (_F_BLD if bold else _F_REG)
    return f.text_length(s, size)


def draw(page, x, y, s, size=9, color=INK, bold=False, align="left", font=None):
    """y 为基线；font="song" 用华文中宋。"""
    name = SER if font == "song" else (BLD if bold else REG)
    if align != "left":
        w = measure(s, size, bold, font)
        x -= w if align == "right" else w / 2
    page.insert_text((x, y), s, fontsize=size, color=color, fontname=name)


def hline(page, x0, x1, y, color=LINE, w=0.8):
    page.draw_line(pymupdf.Point(x0, y), pymupdf.Point(x1, y), color=color, width=w)


def vline(page, x, y0, y1, color=LINE, w=0.8):
    page.draw_line(pymupdf.Point(x, y0), pymupdf.Point(x, y1), color=color, width=w)


def rect(page, r, fill=None, stroke=None, w=0.8):
    page.draw_rect(pymupdf.Rect(*r), color=stroke, fill=fill, width=w)


# ---------------------------------------------------------------- 行内富文本
def segments(text):
    """把 **粗体** 与 `代码` 拆成 [(文本, 样式)]，样式 n/b/c。"""
    out, pos = [], 0
    for m in re.finditer(r"\*\*(.+?)\*\*|`([^`]+)`", text):
        if m.start() > pos:
            out.append((text[pos:m.start()], "n"))
        out.append((m.group(1), "b") if m.group(1) is not None else (m.group(2), "c"))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], "n"))
    return out


_TOK = re.compile(r"[A-Za-z0-9@._/:%+\-–—]+|\s|.")


def tokens(text):
    for part, st in segments(text):
        for t in _TOK.findall(part):
            if t:
                yield t, st


def tok_w(t, size, st):
    size = size * 0.97 if st == "c" else size
    return measure(t, size, st == "b")


def wrap_rich(text, size, width):
    """返回若干行，每行是 [(片段, 样式)]；行首避头点。"""
    lines, cur, w = [], [], 0.0
    for t, st in tokens(text):
        pieces = list(t) if tok_w(t, size, st) > width else [t]
        for p in pieces:
            tw = tok_w(p, size, st)
            if cur and w + tw > width:
                lines.append(cur)
                cur, w = [], 0.0
            cur.append((p, st))
            w += tw
    if cur:
        lines.append(cur)
    for i in range(1, len(lines)):
        while lines[i] and lines[i][0][0][:1] in "，。、；：！？）」’”%":
            lines[i - 1].append(lines[i].pop(0))
    return lines


def draw_rich(page, x, y, line, size, color=BODY_INK, bold_color=RED, force_bold=False):
    cx = x
    for t, st in line:
        if force_bold or st == "b":
            draw(page, cx, y, t, size, bold_color if not force_bold else color, bold=True)
        elif st == "c":
            draw(page, cx, y, t, size * 0.97, CODE)
        else:
            draw(page, cx, y, t, size, color)
        cx += tok_w(t, size, st)
    return cx


# ---------------------------------------------------------------- 页面状态
S = {"doc": None, "page": None, "y": 0, "section": "", "running": "", "toc": []}


def start_page(new_section=False):
    page = S["doc"].new_page(width=FW, height=FH)
    for name, path in ((REG, MSYH), (BLD, MSYHBD), (SER, SONG)):
        page.insert_font(fontname=name, fontfile=path)
    rect(page, (0, 0, FW, FH), fill=WHITE)
    page.insert_text((MX, 36), S["running"], fontsize=7, color=LIGHT, fontname=REG)
    if S["section"]:
        page.insert_text((FW - MX - measure(S["section"], 7), 36), S["section"],
                         fontsize=7, color=GRAY, fontname=REG)
    hline(page, MX, FW - MX, 42, LINE)
    S["page"] = page
    S["y"] = 64
    return page


def ensure(need, gap=0):
    if S["y"] + need > BOTTOM:
        start_page()
        return True
    S["y"] += gap
    return False


# ---------------------------------------------------------------- 版式块
def start_section(num, name):
    S["section"] = name
    ensure(240, gap=26)          # 不在每章强制翻页，但章头不能只带一两行落在页底
    page = S["page"]
    y = S["y"] + 12
    draw(page, MX, y + 4, f"{num:02d}", 8.8, RED, bold=True)
    vline(page, MX + 21, y - 10, y + 8, LINE)
    draw(page, MX + 30, y + 10, name, 16.5, INK, bold=True, font="song")
    hline(page, MX, FW - MX, y + 24, LINE)
    page.draw_line(pymupdf.Point(MX, y + 24), pymupdf.Point(MX + 70, y + 24),
                   color=RED, width=2.2)
    S["y"] = y + 42
    S["toc"].append((name, S["doc"].page_count - 1))   # 封面不计入正文页码


def draw_h3(text):
    num = None
    m = re.match(r"^(\d+)\.\s*(.+)$", text)
    if m:
        num, text = m.group(1), m.group(2)
    lines = wrap_rich(text, 10.2, CW - 16)
    h = len(lines) * 14.6
    ensure(h + 86, gap=10)          # 小标题不留孤行：至少带 4 行正文一起走
    rect(S["page"], (MX, S["y"] + 2, MX + 4.5, S["y"] + 9.5), fill=RED)
    if num:
        draw(S["page"], MX + 13, S["y"] + 9.5, num, 8.2, RED, bold=True, align="right")
    for i, ln in enumerate(lines):
        draw_rich(S["page"], MX + 26 if num else MX + 14, S["y"] + 10 + i * 14.6, ln, 10.2,
                  color=INK, force_bold=True)
    S["y"] += h + 5


def is_subhead(text):
    """整段加粗且很短，按小标题处理。"""
    return (text.startswith("**") and text.endswith("**")
            and text.count("**") == 2 and len(text) < 48)


def draw_para(text, size=BODY, indent=0, gap=0, note=False):
    if text.startswith("（") or text.startswith("("):
        note = True
    if note:
        size, color, lead, gap = 8.1, GRAY, 1.72, 6
    else:
        color, lead = BODY_INK, LEAD

    view = text.startswith("**") and not is_subhead(text) and not note
    pad = 11 if view else 0
    width = CW - indent - 2 * pad
    lines = wrap_rich(text, size, width)
    lh = size * lead
    block_h = len(lines) * lh + (2 * 8 if view else 0)

    if block_h > BOTTOM - 64:                       # 长段落不能整块放，就正常流式排
        view, pad, block_h = False, 0, len(lines) * lh
        width = CW - indent
        lines = wrap_rich(text, size, width)

    ensure(block_h, gap=gap)
    if view:
        rect(S["page"], (MX, S["y"], FW - MX, S["y"] + block_h), fill=BAND)
        rect(S["page"], (MX, S["y"], MX + 2.6, S["y"] + block_h), fill=RED)
        y0 = S["y"] + 8 + size * 0.86
        for i, ln in enumerate(lines):
            draw_rich(S["page"], MX + pad, y0 + i * lh, ln, size, color=color)
        S["y"] += block_h + 7
    else:
        for i, ln in enumerate(lines):
            draw_rich(S["page"], MX + indent, S["y"] + size * 0.86 + i * lh, ln, size,
                      color=color)
        S["y"] += len(lines) * lh + (4 if note else 5)


def draw_list(items):
    for it in items:
        numbered = bool(re.match(r"^\d+\.\s", it))
        body = re.sub(r"^(\d+\.\s|-\s)", "", it).strip()
        marker = re.match(r"^(\d+)\.", it).group(1) if numbered else "—"
        lines = wrap_rich(body, BODY, CW - 20)
        ensure(len(lines) * BODY * LEAD + 5, gap=3)
        y = S["y"] + BODY * 0.86
        if numbered:
            draw(S["page"], MX + 2, y, marker, 8.4, RED, bold=True, align="right")
            draw(S["page"], MX + 4, y, ".", 8.4, RED, bold=True)
        else:
            draw(S["page"], MX + 2, y, marker, 8.4, RED, bold=True)
        for i, ln in enumerate(lines):
            draw_rich(S["page"], MX + 20, y + i * BODY * LEAD, ln, BODY)
        S["y"] += len(lines) * BODY * LEAD + 4


def draw_quote(lines):
    texts = [ln.lstrip("> ").strip() for ln in lines]
    blocks, h = [], 0
    for t in texts:
        ls = wrap_rich(t, 8.5, CW - 30)
        blocks.append(ls)
        h += len(ls) * 8.5 * 1.68
    h += 16
    ensure(h + 12, gap=8)
    rect(S["page"], (MX, S["y"], FW - MX, S["y"] + h), fill=(0.984, 0.969, 0.933))
    rect(S["page"], (MX, S["y"], MX + 2.6, S["y"] + h), fill=GOLD)
    y = S["y"] + 8 + 8.5 * 0.86
    for ls in blocks:
        for ln in ls:
            draw_rich(S["page"], MX + 13, y, ln, 8.5, color=GRAY)
            y += 8.5 * 1.68
    S["y"] += h + 10


# ---------------------------------------------------------------- 表格
NUMCELL = re.compile(r"^[\s\d.,%+\-−–—·/]+$")


def plain(s):
    return re.sub(r"\*\*|`", "", s).strip()


def is_num_col(rows, j):
    vals = [plain(r[j]) for r in rows[1:] if j < len(r) and plain(r[j])]
    vals = [v for v in vals if v not in ("—", "—", "-")]
    return bool(vals) and all(NUMCELL.match(v) for v in vals)


def col_widths(rows, size=7.5):
    """短列（标题、平台名）先按内容给足，长文本列再分剩余宽度。"""
    n = max(len(r) for r in rows)
    raw = []
    for j in range(n):
        w = 40
        for r in rows:
            cell = plain(r[j]) if j < len(r) else ""
            w = max(w, measure(cell, size, True) + 11)
        raw.append(w)
    if sum(raw) <= CW:
        short_n = sum(1 for w in raw if w <= 100)
        extra = CW - sum(raw) - 2 * short_n          # 短列各加 2pt，剩余给长文本列
        idx = [j for j, w in enumerate(raw) if w > 100]
        if idx and extra > 0:
            k = extra / sum(raw[j] for j in idx)
            return [w * (1 + k) if j in idx else w + 2 for j, w in enumerate(raw)]
        return [w + max(extra, 0) / n for w in raw]
    short = [w for w in raw if w <= 100]
    long_w = [w for w in raw if w > 100]
    rest = CW - sum(short)
    if rest > 0 and long_w:
        k = rest / sum(long_w)
        return [w if w <= 100 else w * k for w in raw]
    k = CW / sum(raw)
    return [w * k for w in raw]


def draw_table(rows):
    if not rows:
        return
    size, lh = 7.5, 10.6
    widths = col_widths(rows, size)
    head_h = 19
    numeric = [is_num_col(rows, j) for j in range(len(widths))]

    def cells_of(r):
        return [wrap_rich(r[j] if j < len(r) else "", size, widths[j] - 9)
                for j in range(len(widths))]

    def row_h(cs):
        return max(15, max(len(c) for c in cs) * lh + 5)

    body = [cells_of(r) for r in rows[1:]]
    total = head_h + sum(row_h(c) for c in body)
    space = BOTTOM - S["y"] - 8
    if total > space and total <= 430:      # 中等表：整表挪到下一页，不留表尾
        start_page()
    elif total > space:                     # 长表：允许拆页，但至少留表头 + 3 行
        ensure(head_h + 48, gap=8)

    def head():
        ensure(head_h + 6, gap=8)
        rect(S["page"], (MX, S["y"], FW - MX, S["y"] + head_h), fill=INK)
        cx = MX
        for j, cell in enumerate(rows[0]):
            if numeric[j]:
                draw(S["page"], cx + widths[j] - 5, S["y"] + 12.6, plain(cell), size,
                     WHITE, bold=True, align="right")
            else:
                draw(S["page"], cx + 5, S["y"] + 12.6, plain(cell), size, WHITE, bold=True)
            cx += widths[j]
        S["y"] += head_h

    head()
    for i, cs in enumerate(body):
        rh = row_h(cs)
        if S["y"] + rh > BOTTOM:
            start_page()
            head()
        if i % 2 == 0:
            rect(S["page"], (MX, S["y"], FW - MX, S["y"] + rh), fill=PANEL)
        cx = MX
        for j, lines in enumerate(cs):
            ty = S["y"] + 11.8
            total_w = sum(tok_w(t, size, st) for ln in lines for t, st in ln)
            for ln in lines:
                if numeric[j]:
                    draw_rich(S["page"], cx + widths[j] - 5 - total_w, ty, ln, size,
                              color=INK if j == 0 else GRAY, force_bold=False)
                else:
                    draw_rich(S["page"], cx + 5, ty, ln, size,
                              color=INK if j == 0 else BODY_INK,
                              bold_color=INK if j == 0 else RED)
                ty += lh
            cx += widths[j]
        hline(S["page"], MX, FW - MX, S["y"] + rh, LINE, 0.5)
        S["y"] += rh
    S["y"] += 12


# ---------------------------------------------------------------- md 解析
def parse_md(path):
    raw = Path(path).read_text(encoding="utf-8")
    title, header, sections, cur = "", [], [], None
    for ln in raw.splitlines():
        s = ln.rstrip()
        if not s.strip() or s.strip() in ("---", "***"):
            continue
        if s.startswith("# "):
            title = s[2:].strip()
        elif s.startswith("## "):
            # md 里的「一、二、」序号去掉，统一用版面自己的 01/02 编号
            name = re.sub(r"^[一二三四五六七八九十百]+、\s*", "", s[3:].strip())
            cur = {"name": name, "lines": []}
            sections.append(cur)
        elif s.startswith("### "):
            (cur["lines"] if cur else header).append(s)
        else:
            (cur["lines"] if cur else header).append(s.strip())
    return {"title": title, "header": header, "sections": sections}


def render_section(num, name, lines):
    start_section(num, name)
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        if s.startswith("### "):
            draw_h3(s[4:].strip())
            i += 1
        elif s.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            rows = [r for r in rows if not set("".join(r)) <= set("-: ")]
            draw_table(rows)
        elif s.startswith(">"):
            q = []
            while i < n and lines[i].strip().startswith(">"):
                q.append(lines[i].strip())
                i += 1
            draw_quote(q)
        elif s.startswith("- ") or re.match(r"^\d+\.\s", s):
            items = []
            while i < n and (lines[i].strip().startswith("- ")
                             or re.match(r"^\d+\.\s", lines[i].strip())):
                items.append(lines[i].strip())
                i += 1
            draw_list(items)
        elif is_subhead(s):
            ensure(20, gap=8)
            for ln in wrap_rich(s, 9.8, CW):
                draw_rich(S["page"], MX, S["y"] + 9, ln, 9.8, color=INK, force_bold=True)
                S["y"] += 13.4
            S["y"] += 2
            i += 1
        else:
            draw_para(s)
            i += 1


# ---------------------------------------------------------------- 封面
def draw_cover(cfg, toc):
    page = S["doc"][0]
    draw(page, MX, 64, cfg["kicker"], 7.6, RED, bold=True)
    draw(page, FW - MX, 64, cfg["date"], 7.6, LIGHT, align="right")
    hline(page, MX, FW - MX, 74, INK, 1.2)

    y = 150
    for ln in cfg["title"].split("\n"):
        draw(page, MX, y, ln, 29, INK, bold=True, font="song")
        y += 39
    y += 4
    hline(page, MX, MX + 96, y, RED, 2.6)
    y += 22
    draw(page, MX, y, cfg["subtitle"], 10.2, GRAY)
    y += 26

    for ln in wrap_rich(cfg["lede"], 8.8, 428):
        draw_rich(page, MX, y, ln, 8.8, color=(0.29, 0.27, 0.23))
        y += 15.2

    y += 10
    for k, v in cfg["meta"]:
        draw(page, MX, y, k, 7.4, LIGHT)
        vx = MX + 62
        for j, ln in enumerate(wrap_rich(v, 8.2, CW - 62)):
            draw_rich(page, vx, y + j * 12.6, ln, 8.2, color=BODY_INK)
        y += 12.6 * max(1, len(wrap_rich(v, 8.2, CW - 62))) + 8

    # 目录
    y = max(y + 40, 520)
    draw(page, MX, y, "目录  CONTENTS", 7.6, RED, bold=True)
    hline(page, MX, FW - MX, y + 7, LINE)
    y += 22
    for k, (name, pg) in enumerate(toc):
        if y > FH - 96:
            break
        draw(page, MX, y, f"{k + 1:02d}", 7.6, LIGHT)
        draw(page, MX + 22, y, name, 9.2, INK)
        dots_x0 = MX + 22 + measure(name, 9.2) + 8
        dots_x1 = FW - MX - 22
        if dots_x1 > dots_x0:
            x = dots_x0
            while x < dots_x1:
                page.draw_line(pymupdf.Point(x, y - 1.5), pymupdf.Point(x + 1.6, y - 1.5),
                               color=LINE, width=0.7)
                x += 5
        draw(page, FW - MX, y, str(pg), 8.6, GRAY, align="right")
        y += 19

    hline(page, MX, FW - MX, FH - 62, INK, 0.9)
    draw(page, MX, FH - 48, cfg["footer_left"], 7.2, LIGHT)
    draw(page, FW - MX, FH - 48, cfg["footer_right"], 7.2, LIGHT, align="right")


# ---------------------------------------------------------------- 组装
def build(cfg):
    doc = pymupdf.open()
    S.update({"doc": doc, "section": "", "running": cfg["running"], "toc": []})
    cover = doc.new_page(width=FW, height=FH)
    for name, path in ((REG, MSYH), (BLD, MSYHBD), (SER, SONG)):
        cover.insert_font(fontname=name, fontfile=path)
    rect(cover, (0, 0, FW, FH), fill=WHITE)

    d = parse_md(REPORTS / cfg["src"])
    start_page()                      # 封面之后的第一个正文页
    for k, sec in enumerate(d["sections"], start=1):
        render_section(k, sec["name"], sec["lines"])

    pages = doc.page_count
    for i in range(1, pages):
        pg = doc[i]
        draw(pg, MX, FH - 32, cfg["footer_left"], 7.2, LIGHT)
        draw(pg, FW / 2, FH - 32, "·", 7.2, LIGHT, align="center")
        draw(pg, FW - MX, FH - 32, f"{i:02d} / {pages - 1:02d}", 7.2, LIGHT, align="right")

    draw_cover(cfg, S["toc"])
    doc.set_toc([[1, name, pg] for name, pg in S["toc"]])
    doc.set_metadata({"title": cfg["title"].replace("\n", " "),
                      "author": "何俊霖", "subject": cfg["subtitle"]})
    out = REPORTS / cfg["out"]
    doc.subset_fonts()
    doc.save(out, garbage=4, deflate=True)
    doc.close()

    p = pymupdf.open(out)
    for i in range(min(3, p.page_count)):
        p[i].get_pixmap(dpi=100).save(Path(os.environ["TEMP"]) / f"preview_{cfg['out']}_{i + 1}.png")
    print(f"saved {out.name}  {os.path.getsize(out) // 1024} KB  pages {p.page_count}")
    p.close()


DOCS = [
    {
        "src": "report.md",
        "out": "report.pdf",
        "kicker": "COMMUNITY INTELLIGENCE  /  REPORT 01",
        "date": "2026.11",
        "title": "黑神话·钟馗\n社区舆论分析报告",
        "subtitle": "15 分 53 秒实机演示 ｜ 四平台评论 ＋ B 站弹幕",
        "lede": "本报告基于黑神话官号在 B 站、小红书、小黑盒、微博发布的实机演示下的评论与 B 站弹幕，"
                "为文本逐条附上情感标签并聚类为 13 个主题，分析本次实机演示在社区中的舆论结构。",
        "meta": [
            ("数据规模", "评论 11,280 条 ＋ 弹幕 24,733 条 ＝ 36,013 条文本（B 站前台弹幕 15.37 万，非全量）"),
            ("分析框架", "情感打标（正／中／负）× 主题聚类（547 簇归并 13 类）× 弹幕峰谷定位"),
            ("阅读方式", "每章先给判断，再给数据支撑；口径与边界见附录"),
            ("配套材料", "网页数据看板（可交互）· 一页 PDF 摘要 · 五问分析（另附）"),
        ],
        "running": "黑神话·钟馗 社区舆论分析报告",
        "footer_left": "社区舆论分析 · 2026.11",
        "footer_right": "REPORT 01",
    },
    {
        "src": "five-question-analysis.md",
        "out": "five-question-analysis.pdf",
        "kicker": "COMMUNITY INTELLIGENCE  /  REPORT 02",
        "date": "2026.11",
        "title": "15 分钟实机演示\n社区舆论五问分析",
        "subtitle": "热度形态 · 内容归因 · 风险定位 · 平台差异 · 工具需求",
        "lede": "把这次复盘拆成五个问题逐条回答。每节先给结论，再给数据支撑与指标表现；"
                "只想看结论，读每节标题与段首即可。",
        "meta": [
            ("分析对象", "B 站 / 小红书 / 小黑盒 / 微博评论 11,280 条 ＋ B 站弹幕 24,733 条"),
            ("情感标签", "外部 AI 全量打标（正／中／负，弹幕另含 惊讶／仪式）"),
            ("主题口径", "五个数据集各自聚类，547 簇归并为 13 个统一主题"),
            ("配套材料", "网页数据看板（可交互）· 一页 PDF 摘要 · 完整研究报告（另附）"),
        ],
        "running": "15 分钟实机演示 · 社区舆论五问分析",
        "footer_left": "社区舆论分析 · 2026.11",
        "footer_right": "REPORT 02",
    },
]


if __name__ == "__main__":
    todo = DOCS
    if len(sys.argv) > 1:
        todo = [d for d in DOCS if sys.argv[1] in d["src"]]
    for cfg in todo:
        build(cfg)
