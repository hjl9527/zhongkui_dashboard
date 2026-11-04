# -*- coding: utf-8 -*-
"""数据加载与派生指标。"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).parent / "data"


@st.cache_data(show_spinner=False)
def load_demo():
    return {
        "comments": pd.read_parquet(DATA_DIR / "comments.parquet"),
        "danmaku": pd.read_parquet(DATA_DIR / "danmaku.parquet"),
        "windows": pd.read_parquet(DATA_DIR / "windows_10s.parquet"),
        "peaks": pd.read_parquet(DATA_DIR / "peaks.parquet"),
        "summary": pd.read_parquet(DATA_DIR / "sentiment_summary.parquet"),
        "themes": pd.read_parquet(DATA_DIR / "themes.parquet"),
        "topics": pd.read_parquet(DATA_DIR / "topics.parquet"),
        "stats": json.loads((DATA_DIR / "stats.json").read_text(encoding="utf-8")),
    }


@st.cache_data(show_spinner=False)
def theme_overall(themes: pd.DataFrame) -> pd.DataFrame:
    """把「主题 × 平台」按样本量合并，方差 = 组内方差 + 组间方差。"""
    d = themes[themes["theme"] != "未建模"].copy()
    n = d.groupby("theme")["n"].sum().rename("n")
    w = d["n"]
    g = d["theme"]

    def wavg(col):
        return (d[col] * w).groupby(g).sum() / n

    mean = wavg("mean_sentiment")
    var = wavg("sentiment_var") + ((d["mean_sentiment"] - g.map(mean)) ** 2 * w).groupby(g).sum() / n
    out = pd.DataFrame({
        "n": n,
        "positive_rate": wavg("positive_rate"),
        "negative_rate": wavg("negative_rate"),
        "mean_sentiment": mean,
        "sentiment_var": var,
    }).reset_index()
    out["net"] = out["positive_rate"] - out["negative_rate"]
    out["share"] = out["n"] / out["n"].sum()
    return out.sort_values("n", ascending=False)


@st.cache_data(show_spinner=False)
def platform_kpis(summary: pd.DataFrame) -> pd.DataFrame:
    d = summary[summary["level"] == "全部"].copy()
    d["net"] = d["positive_pct"] - d["negative_pct"]
    return d.sort_values("mean_sentiment", ascending=False)


def theme_rank(topics: pd.DataFrame) -> pd.DataFrame:
    """平台 × 主题的份额，剔除未建模后按平台归一。"""
    d = topics[topics["theme"] != "未建模"].copy()
    d["share_norm"] = d["share"] / d.groupby("platform")["share"].transform("sum")
    return d
