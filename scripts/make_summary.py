# -*- coding: utf-8 -*-
"""把 reports/executive-summary.md 排成一页 A4：reports/executive-summary.pdf + .jpg。

md 是可编辑的正文来源，本脚本只负责排版：改字改数请改 md，再跑本脚本。
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
    # 避免行首出现收尾标点
    for i in range(1, len(lines)):
        while lines[i][:1] in "，。、；：！？）」’”%":
            lines[i - 1] += lines[i][0]
            lines[i] = lines[i][1:]
    return lines


def para(page, x, y, width, s, size=7.5, color=INK, bold=False, lead=1.35,
         align="left"):
    """从基线 y 开始画一段，返回下一段的基线。"""
    lh = size * lead
    for ln in wrap(s, size, width, bold):
        if align == "center":
            draw_text(page, x + width / 2, y, ln, size, color, bold, "center")
        else:
            draw_text(page, x, y, ln, size, color, bold)
        y += lh
    return y


def hline(page, x0, x1, y, color=LINE, w=0.8):
    page.draw_line(pymupdf.Point(x0, y), pymupdf.Point(x1, y), color=color, width=w)


def rect(page, r, fill=None, stroke=None, w=0.8):
    page.draw_rect(pymupdf.Rect(*r), color=stroke, fill=fill, width=w)


# ---------------------------------------------------------------- md 解析
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

    def paras(lines):
        return [l for l in lines if not l.startswith("|")]

    def table(lines):
        rows = [l for l in lines if l.startswith("|")]
        cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
        return [c for c in cells if not set("".join(c)) <= set("-: ")]

    def bullets(lines):
        return [[p.strip() for p in l.lstrip("- ").split("｜")] for l in lines
                if l.startswith("- ")]

    def items(lines):
        """### 小标题 + 正文段落，用于信号卡与行动卡。"""
        out, head = [], None
        for l in lines:
            if l.startswith("### "):
                head = l[4:].strip()
                out.append({"title": head, "body": ""})
            elif out:
                out[-1]["body"] += l
        return out

    by = {s["name"]: s["lines"] for s in sections}
    names = list(by)
    date = ""
    for h in header:
        if h.startswith("日期："):
            date = h[3:].strip()

    return {
        "title": title,
        "subtitle": header[0] if header else "",
        "meta": header[1] if len(header) > 1 else "",
        "date": date,
        "verdict": "".join(paras(by.get("核心判断", []))),
        "kpi": bullets(by.get("关键数字", [])),
        "signals": items(by.get("四个信号", [])),
        "chart1": table(by.get(names[3], [])),
        "chart2": table(by.get(names[4], [])),
        "ptable": table(by.get(names[5], [])),
        "actions": items(by.get("下一步", [])),
        "footnote": "".join(paras(by.get("口径与可靠性", []))),
    }


# ---------------------------------------------------------------- 版式块
def section_title(page, x, y, title):
    draw_text(page, x, y, title, 9, INK, bold=True)


def bar_chart(page, x, y, w, h, title, rows, colors):
    """rows: [[平台, 一级值, 二级值], ...]，表头首行。"""
    head, body = rows[0], rows[1:]
    labels = [r[0] for r in body]
    series = [(head[i + 1], {r[0]: float(r[i + 1]) for r in body})
              for i in range(len(head) - 1)]

    rect(page, (x, y, x + w, y + h), fill=PANEL)
    section_title(page, x + 11, y + 17, title)
    lx = x + 11
    for si, (name, _) in enumerate(series):
        rect(page, (lx, y + 23, lx + 8, y + 31), fill=colors[si])
        draw_text(page, lx + 12, y + 30, name, 7.5, INK)
        lx += measure(name, 7.5) + 28

    maxv = max(v for _, vals in series for v in vals.values())
    axis_max = 50 if maxv <= 50 else maxv * 1.06
    plot_x = x + 46
    plot_w = w - 46 - 26
    top = y + 40
    row_h = (h - 40 - 10) / len(labels)
    for i, lab in enumerate(labels):
        ry = top + i * row_h
        draw_text(page, x + 11, ry + row_h / 2 + 3, lab, 7.5, INK)
        bh = 9
        for si, (_, vals) in enumerate(series):
            by = ry + (row_h - 2 * bh - 3) / 2 + si * (bh + 3)
            bw = plot_w * vals[lab] / axis_max
            rect(page, (plot_x, by, plot_x + bw, by + bh), fill=colors[si])
            draw_text(page, plot_x + bw + 4, by + bh / 2 + 2.7,
                      f"{vals[lab]:.1f}", 7.5, INK)


def hbar(page, x, y, w, h, title, rows, color=GREEN):
    """rows: [[名称, 数值], ...]，表头首行。"""
    head, body = rows[0], rows[1:]
    rect(page, (x, y, x + w, y + h), fill=PANEL)
    section_title(page, x + 11, y + 17, title)

    maxv = max(float(r[1]) for r in body)
    label_w, num_w, bar_pad = 62, 34, 11
    bar_w = w - bar_pad - label_w - num_w
    top = y + 30
    row_h = (h - 30 - 10) / len(body)
    bah = 9
    for i, (name, val) in enumerate(body):
        v = float(val)
        by = top + i * row_h + (row_h - bah) / 2
        draw_text(page, x + bar_pad, by + bah / 2 + 2.7, name, 7.5, INK)
        bw = bar_w * v / (maxv * 1.02)
        rect(page, (x + bar_pad + label_w, by, x + bar_pad + label_w + bw, by + bah),
             fill=color)
        draw_text(page, x + bar_pad + label_w + bw + 4, by + bah / 2 + 2.7,
                  f"{v:.3f}", 7.5, INK)


def kpi_card(page, x, y, w, number, label, sub, accent):
    rect(page, (x, y, x + w, y + 52), fill=PANEL)
    rect(page, (x, y, x + 3, y + 52), fill=accent)
    draw_text(page, x + 11, y + 21, number, 15, accent, bold=True)
    draw_text(page, x + 11, y + 35, label, 8.5, INK, bold=True)
    draw_text(page, x + 11, y + 46, sub, 7, GRAY)


def signal_card(page, x, y, w, h, title, body, accent):
    rect(page, (x, y, x + w, y + h), fill=PANEL)
    rect(page, (x, y, x + w, y + 17), fill=CREAM)
    draw_text(page, x + 9, y + 12, title, 8, accent, bold=True)
    para(page, x + 9, y + 30, w - 18, body, size=7.4, color=INK, lead=1.38)


def action_card(page, x, y, w, h, no, title, body, accent):
    rect(page, (x, y, x + w, y + h), fill=PANEL)
    rect(page, (x, y, x + w, y + 2.6), fill=accent)
    draw_text(page, x + 9, y + 17, no, 8, accent, bold=True)
    draw_text(page, x + 26, y + 17, title, 8, INK, bold=True)
    para(page, x + 9, y + 32, w - 18, body, size=7.2, color=INK, lead=1.4)


# ---------------------------------------------------------------- 组装
def build():
    d = parse_md(MD)
    REPORTS.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open()
    page = doc.new_page(width=FW, height=FH)
    page.insert_font(fontname=REG_NAME, fontfile=MSYH)
    page.insert_font(fontname=BOLD_NAME, fontfile=MSYHBD)
    rect(page, (0, 0, FW, FH), fill=(1, 1, 1))

    y = 46
    draw_text(page, MX, y, d["title"], 19, INK, bold=True)
    draw_text(page, FW - MX, y + 1, d["date"], 8, GRAY, align="right")
    y += 25
    draw_text(page, MX, y, d["subtitle"], 11, RED, bold=True)
    y += 18
    draw_text(page, MX, y, d["meta"], 8.5, GRAY)
    y += 11
    hline(page, MX, FW - MX, y, color=RED, w=1.4)
    y += 12

    # 核心判断
    lines = wrap(d["verdict"], 8.5, CW - 22)
    bh = 30 + len(lines) * 12.4 + 10
    rect(page, (MX, y, FW - MX, y + bh), fill=CREAM)
    rect(page, (MX, y, MX + 3, y + bh), fill=RED)
    draw_text(page, MX + 11, y + 16, "核心判断", 8, RED, bold=True)
    para(page, MX + 11, y + 30, CW - 22, d["verdict"], size=8.5, color=INK, lead=1.46)
    y += bh + 10

    # 关键数字
    kw = (CW - 3 * 4) / 4
    accents = [RED, RED, GREEN, GOLD]
    for i, item in enumerate(d["kpi"][:4]):
        kpi_card(page, MX + i * (kw + 4), y, kw, *item[:3], accents[i])
    y += 52 + 11

    # 四个信号
    gap = 8
    cw2 = (CW - gap) / 2
    ch = 82
    accents = [RED, GREEN, RED, GREEN]
    for i, sig in enumerate(d["signals"][:4]):
        cx = MX + (i % 2) * (cw2 + gap)
        cy = y + (i // 2) * (ch + gap)
        signal_card(page, cx, cy, cw2, ch, sig["title"], sig["body"], accents[i])
    y += 2 * ch + gap + 10

    # 两张图
    gh = 150
    c1 = d["chart1"]
    c2 = d["chart2"]
    bar_chart(page, MX, y, cw2, gh, "一级 vs 二级评论 · 正向占比（%）", c1, [RED, GRAY])
    hbar(page, MX + cw2 + gap, y, cw2, gh, "主题分歧度 TOP 6（越高越分裂）", c2)
    y += gh + 11

    # 平台表
    pt = d["ptable"]
    head, rows = pt[0], pt[1:]
    section_title(page, MX, y, "平台角色一览（PV 一套全平台同版，海报分版）")
    y += 8
    cols = [52, 108, 226, CW - 52 - 108 - 226]
    cx = MX
    for name, w in zip(head, cols):
        rect(page, (cx, y, cx + w, y + 15), fill=INK)
        draw_text(page, cx + 5, y + 10.5, name, 7.5, (1, 1, 1), bold=True)
        cx += w
    y += 15
    rh = 19
    for i, r in enumerate(rows):
        rect(page, (MX, y, FW - MX, y + rh), fill=PANEL if i % 2 == 0 else (1, 1, 1))
        cx = MX
        for j, (cell, w) in enumerate(zip(r, cols)):
            draw_text(page, cx + 5, y + 13, cell, 7.5,
                      INK if j == 0 else (GREEN if j == 3 else GRAY), bold=(j == 0))
            cx += w
        y += rh
    y += 11

    # 下一步
    ah = 64
    aw3 = (CW - 2 * gap) / 3
    accents = [RED, GREEN, GOLD]
    for i, act in enumerate(d["actions"][:3]):
        no, title = act["title"].split(" ", 1)
        action_card(page, MX + i * (aw3 + gap), y, aw3, ah, no, title, act["body"],
                    accents[i])
    y += ah + 10

    # 尾注与页脚
    hline(page, MX, FW - MX, y, color=LINE)
    y += 5
    end = para(page, MX, y + 7, CW, d["footnote"], size=7, color=GRAY, lead=1.45)

    fy = max(FH - 28, end + 8)
    draw_text(page, MX, fy, "数据分析 / 社区舆论", 7, GRAY)
    draw_text(page, FW - MX, fy, "内部参考 · 非对外发布", 7, GRAY, align="right")
    if end > fy - 8:
        print("warning: 内容压到页脚，end y =", round(end, 1))

    out = REPORTS / "executive-summary.pdf"
    doc.subset_fonts()
    doc.set_metadata({"title": d["title"], "author": "社区舆论分析"})
    doc.save(out, garbage=4, deflate=True)
    doc.close()

    p = pymupdf.open(out)
    p[0].get_pixmap(dpi=120).save(REPORTS / "executive-summary.jpg")
    p.close()
    print("saved", out, os.path.getsize(out) // 1024, "KB")
    print("saved", REPORTS / "executive-summary.jpg",
          os.path.getsize(REPORTS / "executive-summary.jpg") // 1024, "KB")
    print("bottom baseline y =", round(y, 1), "/ page", FH)


if __name__ == "__main__":
    build()
