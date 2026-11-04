# -*- coding: utf-8 -*-
"""Plotly 图表：统一中式编辑风。"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import (ACCENT, ACCENT2, GOLD, INK, MUTED, PAPER, PLATFORM_COLOR, RULE,
                    SENTI_CN, SENTI_COLOR, SURFACE, THEME_COLOR)

SERIF = "Noto Serif SC, Noto Serif CJK SC, Songti SC, SimSun, serif"
SANS = "Noto Sans SC, Noto Sans CJK SC, PingFang SC, Microsoft YaHei, sans-serif"
PLATFORM_ORDER = ["B站", "小红书", "小黑盒", "微博", "B站弹幕"]


def base(fig, height=360, legend=True, title=None):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=SANS, color=INK, size=12),
        margin=dict(l=10, r=12, t=44, b=16),
        title=dict(text=title, font=dict(family=SERIF, size=15, color=INK), x=0, xanchor="left") if title else None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)",
                    font=dict(size=11, color=MUTED)) if legend else dict(visible=False),
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=RULE, font=dict(family=SANS, color=INK)),
        bargap=0.28,
    )
    fig.update_xaxes(showgrid=False, linecolor=RULE, tickfont=dict(size=11, color=MUTED),
                     title_font=dict(size=11, color=MUTED))
    fig.update_yaxes(gridcolor="#ece6dc", zeroline=False, linecolor=RULE,
                     tickfont=dict(size=11, color=MUTED), title_font=dict(size=11, color=MUTED))
    return fig


# ---------- 概览 ----------
def fig_level_positive(summary):
    d = summary[summary["level"].isin(["一级评论", "二级评论"])]
    fig = go.Figure()
    for lvl, color in [("一级评论", ACCENT), ("二级评论", GOLD)]:
        x = d[d["level"] == lvl].sort_values("platform")
        fig.add_bar(x=x["platform"].map({"bili_comments": "B站", "xhs_comments": "小红书",
                                         "xiaoheihe_comments": "小黑盒", "weibo_comments": "微博"}),
                    y=x["positive_pct"] * 100, name=lvl,
                    marker_color=color, marker_line_width=0,
                    text=(x["positive_pct"] * 100).round(1), textposition="outside",
                    textfont=dict(size=10, color=MUTED), texttemplate="%{text}%")
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="正向占比（%）", range=[0, 52])
    fig = base(fig, height=330, legend=False, title="一级 vs 二级评论：正向占比")
    return fig


def fig_theme_variance(overall, top=6):
    d = overall[overall["n"] >= 120].nlargest(top, "sentiment_var").sort_values("sentiment_var")
    fig = go.Figure(go.Bar(
        x=d["sentiment_var"], y=d["theme"], orientation="h",
        marker_color=ACCENT, marker_line_width=0,
        text=d["sentiment_var"].round(3), textposition="outside",
        textfont=dict(size=10, color=MUTED),
        hovertemplate="%{y}<br>簇内方差 %{x:.3f}<extra></extra>",
    ))
    fig.update_xaxes(title="情感方差（越大越分裂）", range=[0, max(0.52, d["sentiment_var"].max() * 1.3)])
    return base(fig, height=330, legend=False, title="最分裂的六个主题 · 簇内方差")


# ---------- 情感 ----------
def fig_level_stack(summary):
    code2name = {"bili_comments": "B站", "xhs_comments": "小红书",
                 "xiaoheihe_comments": "小黑盒", "weibo_comments": "微博"}
    d = summary.copy()
    d["platform"] = d["platform"].map(code2name)
    levels = ["全部", "一级评论", "二级评论"]
    fig = go.Figure()
    for li, lvl in enumerate(levels):
        x = d[d["level"] == lvl].set_index("platform").reindex(
            [p for p in ["B站", "小红书", "小黑盒", "微博"] if p in set(d["platform"])])
        for key, cn in [("positive", "正向"), ("neutral", "中性"), ("negative", "负向")]:
            fig.add_bar(x=[f"{p}·{lvl}" for p in x.index], y=x[f"{key}_pct"] * 100,
                        name=cn, marker_color=SENTI_COLOR[key], marker_line_width=0,
                        showlegend=(li == 0),
                        hovertemplate="%{x}<br>" + cn + " %{y:.1f}%<extra></extra>")
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title="占比（%）", range=[0, 100])
    fig.update_xaxes(tickangle=-35, tickfont=dict(size=10, color=MUTED))
    fig = base(fig, height=390, legend=False)
    fig.update_layout(margin=dict(l=10, r=12, t=20, b=58))
    return fig


def fig_theme_heat(themes, overall):
    order = overall["theme"].tolist()
    d = themes[(themes["theme"].isin(order)) & (themes["theme"] != "未建模")]
    piv = d.pivot_table(index="theme", columns="platform_name", values="mean_sentiment", aggfunc="first")
    n = d.pivot_table(index="theme", columns="platform_name", values="n", aggfunc="sum")
    n = n.reindex(index=piv.index, columns=piv.columns)
    piv = piv.where(n >= 30)          # 样本过少的格子留白，避免 1.00 这类假信号
    piv = piv.reindex(order)
    cols = [c for c in PLATFORM_ORDER if c in piv.columns]
    fig = go.Figure(go.Heatmap(
        z=piv[cols].values, x=cols, y=piv.index.tolist(),
        colorscale=[[0, ACCENT2], [0.5, "#f1ece2"], [1, ACCENT]], zmid=0,
        text=piv[cols].round(2).values, texttemplate="%{text}",
        textfont=dict(size=10, color="#4a443c"),
        hovertemplate="%{y} · %{x}<br>情感均值 %{z:.2f}<extra></extra>",
        colorbar=dict(thickness=10, outlinewidth=0, tickfont=dict(size=10, color=MUTED),
                      title=dict(text="情感均值", font=dict(size=10, color=MUTED))),
        xgap=2, ygap=2,
    ))
    return base(fig, height=420, legend=False, title="主题 × 平台：谁在正向，谁在负向（均值 −1 ~ +1）")


def fig_theme_net(overall, min_n=120):
    d = overall[overall["n"] >= min_n].sort_values("net")
    colors = [ACCENT if v >= 0 else ACCENT2 for v in d["net"]]
    fig = go.Figure(go.Bar(
        x=d["net"] * 100, y=d["theme"], orientation="h",
        marker_color=colors, marker_line_width=0,
        text=(d["net"] * 100).round(1), texttemplate="%{text}", textposition="outside",
        textfont=dict(size=10, color=MUTED),
        customdata=d[["positive_rate", "negative_rate"]].values * 100,
        hovertemplate="%{y}<br>净值 %{x:.1f}<br>正 %{customdata[0]:.1f} / 负 %{customdata[1]:.1f}<extra></extra>",
    ))
    fig.update_xaxes(title="正向率 − 负向率（百分点）", zeroline=True, zerolinecolor=RULE)
    return base(fig, height=420, legend=False, title="合并后的主题净情感")


# ---------- 弹幕时间轴 ----------
def _split_by_sign(x, y):
    """把折线按正负拆成两条，并在过零点插入 0，避免断线。"""
    xs = list(x)
    ys = [float(v) for v in y]
    seg = {1: {"x": [], "y": []}, -1: {"x": [], "y": []}}
    prev = None
    for i, (xi, yi) in enumerate(zip(xs, ys)):
        s = 1 if yi >= 0 else -1
        if prev is not None and s != prev:
            y0 = ys[i - 1]
            t = y0 / (y0 - yi) if (y0 - yi) else 0.0
            xc = xs[i - 1] + t * (xi - xs[i - 1])
            seg[prev]["x"] += [xc, None]
            seg[prev]["y"] += [0.0, None]
            seg[s]["x"].append(xc)
            seg[s]["y"].append(0.0)
        seg[s]["x"].append(xi)
        seg[s]["y"].append(yi)
        prev = s
    return seg


def fig_timeline(windows, peaks=None, height=470, duration=None):
    w = windows.copy()
    w["x"] = (w["t_start"] + 5) / 60
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
                        row_heights=[0.54, 0.46],
                        specs=[[{"secondary_y": True}], [{}]],
                        subplot_titles=("弹幕量（10 秒窗口 / 2 秒步进）", "情感指数（仅有效情感样本）"))
    fig.add_trace(go.Scatter(
        x=w["x"], y=w["n"], mode="lines", fill="tozeroy", name="弹幕量",
        line=dict(color=GOLD, width=1.2), fillcolor="rgba(201,162,39,.22)",
        hovertemplate="%{x:.1f} 分<br>%{y:,} 条 / 10 秒<extra></extra>",
    ), row=1, col=1)
    if "ritual_rate" in w.columns:
        fig.add_trace(go.Scatter(
            x=w["x"], y=w["ritual_rate"] * 100, mode="lines", name="仪式占比（右轴）",
            line=dict(color="#a99a80", width=1, dash="dot"),
            hovertemplate="仪式 %{y:.1f}%<extra></extra>",
        ), row=1, col=1, secondary_y=True)
    seg = _split_by_sign(w["x"], w["mean_sentiment"])
    for key, color, name in [(1, ACCENT, "情感指数 ≥ 0"), (-1, ACCENT2, "情感指数 < 0")]:
        fig.add_trace(go.Scatter(
            x=seg[key]["x"], y=seg[key]["y"], mode="lines", name=name,
            line=dict(color=color, width=1.6), connectgaps=False,
            hovertemplate="%{x:.1f} 分<br>指数 %{y:.2f}<extra></extra>",
        ), row=2, col=1)
    fig.add_hline(y=0, row=2, col=1, line=dict(color=RULE, width=1))
    fig.update_yaxes(title_text="条 / 10 秒", row=1, col=1, rangemode="tozero")
    if "ritual_rate" in w.columns:
        fig.update_yaxes(title_text="仪式占比 %", row=1, col=1, secondary_y=True, range=[0, 100])
    fig.update_yaxes(title_text="情感指数", row=2, col=1, range=[-0.4, 1.05])
    fig.update_xaxes(title_text="视频时间（分钟）", row=2, col=1)
    if duration:
        fig.update_xaxes(range=[0, duration / 60])
    fig.update_annotations(font=dict(family=SERIF, size=11, color=MUTED))
    if peaks is not None:
        for _, p in peaks.iterrows():
            if p["rank"] in ("P1", "P2", "P3", "V1", "V2"):
                color = ACCENT if p["kind"] == "峰" else ACCENT2
                x = (p["t_start"] + 5) / 60
                for row in (1, 2):
                    fig.add_vline(x=x, row=row, col=1, line=dict(color=color, width=1, dash="dash"))
                fig.add_annotation(x=x, y=0.5, yref="paper", text=p["rank"], showarrow=False,
                                   font=dict(size=9, color=color), xshift=10, yshift=-6)
    fig = base(fig, height=height, legend=True)
    fig.update_layout(margin=dict(l=10, r=12, t=44, b=16),
                      legend=dict(orientation="h", x=1.0, xanchor="right", y=1.0, yanchor="bottom",
                                  bgcolor="rgba(248,246,242,.9)", font=dict(size=10, color=MUTED)))
    return fig


# ---------- 主题与平台 ----------
def fig_theme_share(topics):
    order = [t for t in THEME_COLOR if t != "未建模"]
    d = topics[topics["theme"] != "未建模"].copy()
    d["share_norm"] = d["share"] / d.groupby("platform")["share"].transform("sum")
    piv = d.pivot_table(index="platform", columns="theme", values="share_norm", aggfunc="sum")
    piv = piv.reindex([p for p in PLATFORM_ORDER if p in piv.index])
    piv = piv.reindex(columns=[t for t in order if t in piv.columns]).fillna(0)
    fig = go.Figure()
    for t in piv.columns:
        fig.add_bar(y=piv.index, x=piv[t] * 100, orientation="h", name=t,
                    marker_color=THEME_COLOR.get(t, "#b9ac9a"), marker_line_width=0,
                    hovertemplate="%{y} · " + t + " %{x:.1f}%<extra></extra>")
    fig.update_layout(barmode="stack")
    fig.update_xaxes(title="主题份额（%，剔除未建模后归一）", range=[0, 100])
    return base(fig, height=330, legend=False)


def fig_theme_platform(themes, theme):
    d = themes[(themes["theme"] == theme) & (themes["platform_name"].isin(PLATFORM_ORDER))].copy()
    d["platform_name"] = pd.Categorical(d["platform_name"], PLATFORM_ORDER, ordered=True)
    d = d.sort_values("platform_name")
    fig = go.Figure()
    for key, cn in [("positive", "正向"), ("negative", "负向")]:
        fig.add_bar(x=d["platform_name"], y=d[key + "_rate"] * 100, name=cn,
                    marker_color=SENTI_COLOR[key], marker_line_width=0,
                    text=(d[key + "_rate"] * 100).round(1), texttemplate="%{text}",
                    textposition="outside", textfont=dict(size=10, color=MUTED),
                    hovertemplate="%{x}<br>" + cn + " %{y:.1f}%<extra></extra>")
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="占比（%）")
    fig = base(fig, height=330, legend=False, title=f"「{theme}」在各平台的正负结构")
    return fig


# ---------- 上传模式 ----------
def fig_fast_sentiment(counts):
    d = counts.reindex(["positive", "neutral", "negative"]).fillna(0)
    fig = go.Figure(go.Bar(
        x=[SENTI_CN[k] for k in d.index], y=d.values,
        marker_color=[SENTI_COLOR[k] for k in d.index], marker_line_width=0,
        text=[f"{v:,}" for v in d.values], textposition="outside",
        textfont=dict(size=10, color=MUTED),
    ))
    return base(fig, height=300, legend=False, title="情感分布")


def fig_fast_topics(share_df):
    d = share_df.sort_values("share")
    fig = go.Figure(go.Bar(
        x=d["share"] * 100, y=d["theme"], orientation="h",
        marker_color=ACCENT, marker_line_width=0,
        text=(d["share"] * 100).round(1), texttemplate="%{text}%", textposition="outside",
        textfont=dict(size=10, color=MUTED),
    ))
    fig.update_xaxes(title="主题占比（%）")
    return base(fig, height=320, legend=False, title="主题分布（TF-IDF + KMeans）")
