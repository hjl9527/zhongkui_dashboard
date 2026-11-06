# -*- coding: utf-8 -*-
"""把 reports/executive-summary.md 排成 A4 版式：reports/executive-summary.pdf + .jpg。

md 是可编辑的正文来源，本脚本只负责排版：改字改数请改 md，再跑本脚本。
结构按「章节 + 段落/小标题/表格/列表」自动流式排版，放不下自动翻页。
字体用系统微软雅黑（正文）/ 雅黑粗体（标题），保存前做字形子集化，体积可控。
"""
import os
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
MD = REPORTS / "executive-summary.md"
MSYH = r"C:\Windows\Fonts\msyh.ttc"
MSYHBD = r"C:\Windows\Fonts\msyhbd.ttc"

# ---- 配色（中式编辑风） ----
INK = (0.137, 0.125, 0.110)
RED = (0.690, 0.196, 0.110)
GREEN = (0.137, 0.310, 0.278)
GRAY = (0.420, 0.400, 0.345)
CREAM = (0.973, 0.965, 0.949)
PANEL = (0.953, 0.937, 0.902)
LINE = (0.847, 0.816, 0.769)
GOLD = (0.788, 0.635, 0.153)

FW, FH = 595.276, 841.890
MX = 40
CW = FW - 2 * MX

REG_NAME = "yh"
BOLD_NAME = "yhbd"
_REG = pymupdf.Font(fontfile=MSYH)
_BOLD = pymupdf.Font(fontfile=MSYHBD)

BODY = 8.6          # 正文字号
LEAD = 1.55         # 正文行距倍数
BOTTOM = FH - 44    # 版心底线


# ---------------------------------------------------------------- 文本
def measure(s, size, bold=False):
    return (_BOLD if bold else _REG).text_length(s, size)


def draw_text(page, x, y, s, size=8, color=INK, bold=False, align="left"):
    """y 为基线。align 支持 left / right / center。"""
    if align != "left":
        w = measure(s, size, bold)
        x -= w if align == "right" else w / 2
    page.insert_text((x, y), s, fontsize=size, color=color,
                     fontname=BOLD_NAME if bold else REG_NAME)


_TOK = re.compile(r"[A-Za-z0-9%.,+\-/:–]+|[^\s]")


def wrap(s, size, width, bold=False):
    """按字宽折行；数字/英文串不拆开。"""
    lines, cur = [], ""
    for tok in _TOK.findall(s):
        cand = cur + tok
        if cur and measure(cand, size, bold) > width:
            lines.append(cur.rstrip())
            cur = tok.lstrip()
        else:
            cur = cand
    if cur.strip():
        lines.append(cur)
    for i in range(1, len(lines)):
        while lines[i][:1] in "，。、；：！？）」’”%":
            lines[i - 1] += lines[i][0]
            lines[i] = lines[i][1:]
    return lines


def hline(page, x0, x1, y, color=LINE, w=0.8):
    page.draw_line(pymupdf.Point(x0, y), pymupdf.Point(x1, y), color=color, width=w)


def rect(page, r, fill=None, stroke=None, w=0.8):
    page.draw_rect(pymupdf.Rect(*r), color=stroke, fill=fill, width=w)


# ---------------------------------------------------------------- md 解析
NUM = ("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")


def blockify(lines):
    """把一节里的行切成 (kind, payload)：para / sub / table / list。"""
    out, i, n = [], 0, len(lines)
    while i < n:
        s = lines[i]
        if s.startswith("|"):
            rows = []
            while i < n and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip("|").split("|")]
                rows.append(cells)
                i += 1
            rows = [r for r in rows if not set("".join(r)) <= set("-: ")]
            out.append(("table", rows))
        elif s.startswith("### "):
            out.append(("sub", s[4:].strip()))
            i += 1
        elif s.startswith("- ") or s[:2] in NUM:
            items = []
            while i < n and (lines[i].startswith("- ") or lines[i][:2] in NUM):
                items.append(lines[i])
                i += 1
            out.append(("list", items))
        else:
            out.append(("para", s))
            i += 1
    return out


def parse_md(path):
    raw = Path(path).read_text(encoding="utf-8")
    title, header, sections, cur = "", [], [], None
    for ln in raw.splitlines():
        s = ln.rstrip()
        if s.startswith("# "):
            title = s[2:].strip()
        elif s.startswith("## "):
            cur = {"name": s[3:].strip(), "lines": []}
            sections.append(cur)
        elif s.strip():
            (cur["lines"] if cur else header).append(s.strip())
    return {
        "title": title,
        "header": header,
        "sections": [{"name": s["name"], "blocks": blockify(s["lines"])}
                     for s in sections],
    }


# ---------------------------------------------------------------- 页面状态
STATE = {"doc": None, "page": None, "y": 0, "title": "", "section": ""}


def start_page(refill=True):
    page = STATE["doc"].new_page(width=FW, height=FH)
    page.insert_font(fontname=REG_NAME, fontfile=MSYH)
    page.insert_font(fontname=BOLD_NAME, fontfile=MSYHBD)
    rect(page, (0, 0, FW, FH), fill=(1, 1, 1))
    if refill:
        head = (STATE["section"] + "（续）") if STATE["section"] else STATE["title"]
        draw_text(page, MX, 42, head, 9, GRAY, bold=True)
        hline(page, MX, FW - MX, 48, color=LINE)
        STATE["y"] = 62
    else:
        STATE["y"] = 46
    STATE["page"] = page
    return page


def ensure(need, gap=0):
    """确保当前页还能放下 need；放不下就翻页。"""
    if STATE["y"] + need > BOTTOM:
        start_page()
        return True
    STATE["y"] += gap
    return False


# ---------------------------------------------------------------- 版式块
def draw_section(name):
    ensure(52, gap=14)
    STATE["section"] = name
    page, y = STATE["page"], STATE["y"]
    rect(page, (MX, y - 10, MX + 3, y + 1), fill=RED)
    draw_text(page, MX + 10, y, name, 10.5, INK, bold=True)
    hline(page, MX, FW - MX, y + 6, color=LINE)
    STATE["y"] = y + 18


def draw_para(text, size=BODY, color=INK, lead=LEAD, indent=0):
    for ln in wrap(text, size, CW - indent):
        lh = size * lead
        ensure(lh + 2)
        draw_text(STATE["page"], MX + indent, STATE["y"] + size, ln, size, color)
        STATE["y"] += lh
    STATE["y"] += 1


def draw_sub(text):
    lh = 10 * 1.45
    ensure(lh + 6, gap=4)
    for i, ln in enumerate(wrap(text, 9.2, CW, bold=True)):
        draw_text(STATE["page"], MX, STATE["y"] + 9.2, ln, 9.2, RED if i == 0 else INK,
                  bold=True)
        STATE["y"] += lh
    STATE["y"] += 2


def draw_list(items):
    for it in items:
        draw_para(it, indent=11)


def col_widths(rows, total, size=7.7):
    n = max(len(r) for r in rows)
    weights = []
    for j in range(n):
        w = 0
        for r in rows:
            cell = r[j] if j < len(r) else ""
            w = max(w, measure(cell, size, bold=True))
        weights.append(max(w, 46))
    k = total / sum(weights)
    return [w * k for w in weights]


def draw_table(rows):
    if not rows:
        return
    size = 7.6
    widths = col_widths(rows, CW, size)
    head_h = 16

    def row_h(r):
        return max(13, max(len(wrap(r[j] if j < len(r) else "", size,
                                    widths[j] - 8)) for j in range(len(widths))) * 10.2 + 4)

    # 小表整体不拆页：放不下就整张翻到下一页
    total = head_h + sum(row_h(r) for r in rows[1:])
    if total <= BOTTOM - 62 and STATE["y"] + total > BOTTOM:
        start_page()

    def draw_head():
        ensure(head_h + 4, gap=4)
        cx = MX
        for j, cell in enumerate(rows[0]):
            rect(STATE["page"], (cx, STATE["y"], cx + widths[j], STATE["y"] + head_h),
                 fill=INK)
            draw_text(STATE["page"], cx + 4, STATE["y"] + 11.5, cell, size, (1, 1, 1),
                      bold=True)
            cx += widths[j]
        STATE["y"] += head_h

    draw_head()
    for i, r in enumerate(rows[1:]):
        cells = [wrap(r[j] if j < len(r) else "", size, widths[j] - 8) for j in
                 range(len(widths))]
        rh = row_h(r)
        if STATE["y"] + rh > BOTTOM:
            start_page()
            draw_head()
        rect(STATE["page"], (MX, STATE["y"], FW - MX, STATE["y"] + rh),
             fill=PANEL if i % 2 == 0 else (1, 1, 1))
        cx = MX
        for j, lines in enumerate(cells):
            ty = STATE["y"] + 10.5
            for ln in lines:
                draw_text(STATE["page"], cx + 4, ty, ln, size, INK if j == 0 else GRAY,
                          bold=(j == 0))
                ty += 10.2
            cx += widths[j]
        STATE["y"] += rh
    STATE["y"] += 8


# ---------------------------------------------------------------- 组装
def build():
    d = parse_md(MD)
    REPORTS.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open()
    STATE["doc"] = doc
    STATE["title"] = d["title"]
    page = start_page(refill=False)

    # 抬头
    y = 52
    draw_text(page, MX, y, d["title"], 19, INK, bold=True)
    y += 24
    for j, line in enumerate(d["header"]):
        size, color, bold = (11, RED, True) if j == 0 else (8.4, GRAY, False)
        for ln in wrap(line, size, CW, bold):
            draw_text(page, MX, y, ln, size, color, bold)
            y += size * 1.45
        y += 3
    hline(page, MX, FW - MX, y + 2, color=RED, w=1.4)
    STATE["y"] = y + 16

    for sec in d["sections"]:
        draw_section(sec["name"])
        for kind, payload in sec["blocks"]:
            if kind == "para":
                draw_para(payload)
            elif kind == "sub":
                draw_sub(payload)
            elif kind == "list":
                draw_list(payload)
            elif kind == "table":
                draw_table(payload)

    # 页脚与页码
    pages = len(doc)
    for i, pg in enumerate(doc):
        fy = FH - 24
        draw_text(pg, MX, fy, "数据分析 / 社区舆论", 7, GRAY)
        draw_text(pg, FW - MX, fy, f"{i + 1} / {pages}", 7, GRAY, align="right")

    out = REPORTS / "executive-summary.pdf"
    doc.subset_fonts()
    doc.set_metadata({"title": d["title"], "author": "社区舆论分析"})
    doc.save(out, garbage=4, deflate=True)
    doc.close()

    p = pymupdf.open(out)
    for i, pg in enumerate(p):
        pg.get_pixmap(dpi=110).save(REPORTS / f"executive-summary-p{i + 1}.jpg")
    p.close()
    # 兼容旧文件名：首页缩略图
    p = pymupdf.open(out)
    p[0].get_pixmap(dpi=120).save(REPORTS / "executive-summary.jpg")
    p.close()
    print("saved", out, os.path.getsize(out) // 1024, "KB", "pages", pages)


if __name__ == "__main__":
    build()
