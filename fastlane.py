# -*- coding: utf-8 -*-
"""上传模式的轻量分析：词典打标 → TF-IDF/KMeans 主题 → 时间窗聚合。

口径与 Demo 不同：Demo 用 BERTopic + 外部 AI 打标；这里是可离线复跑的快速版。
"""
import re

import numpy as np
import pandas as pd
import streamlit as st

POS_WORDS = """牛逼 牛比 牛b 神作 神了 惊艳 帅 帅气 爽 爽快 厉害 喜欢 期待 好看 好听 好玩
漂亮 精彩 震撼 真实 逼真 精细 精致 流畅 丝滑 舒服 带感 燃 顶 顶级 满分 好评 爱了
用心 诚意 进步 稳 强 绝了 太牛 夸张 完美 优秀 感动 泪目 文化 细节 质感 有感觉""".split()
NEG_WORDS = """失望 拉胯 拉跨 垃圾 丑 差 崩 穿模 糊 僵硬 掉帧 卡顿 卡 换皮 圈钱 敷衍 无聊
难看 难听 难受 劝退 退钱 不行 缺点 问题 严重 割韭菜 缝合 抄袭 廉价 出戏 尴尬 翻车
崩坏 恶心 太差 没意思 烂 空洞 生硬 突兀 重复 单调 拉 一般 试水 担忧 害怕 劝退 降智""".split()
NEGATORS = ("不", "没", "没有", "别", "无", "非", "未", "不算")
INTENSIFIERS = {"很": 1.3, "太": 1.4, "超": 1.45, "非常": 1.4, "特别": 1.3, "真": 1.2,
                "巨": 1.45, "贼": 1.3, "极其": 1.5}
STOPWORDS = set("""的 了 是 在 我 你 他 她 它 们 这 那 就 都 也 又 还 和 与 及 而 但 却
因为 所以 如果 但是 然后 一个 什么 怎么 这样 那样 自己 现在 已经 可以 没有 不是 就是
有点 一些 这个 那个 感觉 觉得 真的 其实 还是 只是 不过 而且 或者 的话 时候 一直
啊 吧 呢 吗 哦 嗯 哈 呀 啦 嘛 么 呼 哎 咦 诶 个 上 下 中 里 外 后 前""".split())
COLS_TEXT = ["text_clean", "text", "content", "内容", "评论", "弹幕", "comment", "body"]
COLS_TIME = ["progress", "time", "timestamp", "seconds", "second", "时刻", "时间", "秒"]
COLS_PLATFORM = ["platform", "平台", "source", "channel"]
SENTI_SET = set(POS_WORDS) | set(NEG_WORDS)


def read_csv(file) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            file.seek(0)
            return pd.read_csv(file, encoding=enc)
        except Exception:
            continue
    raise ValueError("CSV 编码无法识别，请另存为 UTF-8。")


def detect(df: pd.DataFrame):
    text = next((c for c in COLS_TEXT if c in df.columns), None)
    if text is None:
        raise ValueError("没有找到文本列：需要 text_clean / text / content 之一。")
    time = next((c for c in COLS_TIME if c in df.columns), None)
    plat = next((c for c in COLS_PLATFORM if c in df.columns), None)
    return text, time, plat


def score_text(text: str):
    text = str(text)
    pos = neg = 0.0
    for w in POS_WORDS:
        start = 0
        while True:
            i = text.find(w, start)
            if i < -1 or i == -1:
                break
            prefix = text[max(0, i - 3):i]
            flip = any(n in prefix for n in NEGATORS)
            weight = 1.0
            for k, v in INTENSIFIERS.items():
                if prefix.endswith(k):
                    weight = v
                    break
            if flip:
                neg += weight
            else:
                pos += weight
            start = i + len(w)
    for w in NEG_WORDS:
        start = 0
        while True:
            i = text.find(w, start)
            if i == -1:
                break
            prefix = text[max(0, i - 3):i]
            flip = any(n in prefix for n in NEGATORS)
            weight = 1.0
            for k, v in INTENSIFIERS.items():
                if prefix.endswith(k):
                    weight = v
                    break
            if flip:
                pos += weight
            else:
                neg += weight
            start = i + len(w)
    if pos > neg:
        label = "positive"
    elif neg > pos:
        label = "negative"
    else:
        label = "neutral"
    total = pos + neg
    index = 0.0 if total == 0 else (pos - neg) / total
    return label, index, pos, neg


def tokens(text: str):
    """统一分词口径：游戏词典 + 哈工大停用词 + 单字白名单。"""
    from tokenizer import tokens as _tokens
    return _tokens(text)


def build_topics(df: pd.DataFrame, k: int = 8):
    from sklearn.cluster import KMeans
    from sklearn.feature_extraction.text import TfidfVectorizer

    docs = [" ".join(tokens(t)) for t in df["text"]]
    mask = [bool(d.strip()) for d in docs]
    if sum(mask) < 40:
        df["theme"] = "未建模"
        df["topic_id"] = -1
        return df, pd.DataFrame([{"topic_id": -1, "theme": "未建模", "size": len(df),
                                  "share": 1.0, "top_words": ""}])

    valid = [d for d, m in zip(docs, mask) if m]
    n = len(valid)
    k = max(2, min(k, max(2, n // 40)))
    vec = TfidfVectorizer(max_features=3000, min_df=2, token_pattern=r"(?u)\b\w+\b")
    x = vec.fit_transform(valid)
    km = KMeans(n_clusters=k, n_init=4, random_state=0)
    km.fit(x)
    terms = np.array(vec.get_feature_names_out())
    names = []
    for i in range(k):
        top = terms[np.argsort(km.cluster_centers_[i])[::-1][:3]]
        names.append(f"T{i + 1} · " + "/".join(top))

    theme = np.array(["未建模"] * len(df), dtype=object)
    topic = np.array([-1] * len(df))
    theme[np.array(mask)] = [names[i] for i in km.labels_]
    topic[np.array(mask)] = km.labels_
    df["theme"] = theme
    df["topic_id"] = topic
    share = df["theme"].value_counts(normalize=True).rename("share").reset_index()
    share.columns = ["theme", "share"]
    top_words = []
    for i in range(k):
        top = "、".join(terms[np.argsort(km.cluster_centers_[i])[::-1][:10]])
        top_words.append({"topic_id": i, "theme": names[i], "size": int((km.labels_ == i).sum()),
                          "share": float((km.labels_ == i).mean()), "top_words": top})
    return df, pd.DataFrame(top_words)


def make_windows(df: pd.DataFrame, step: int = 2, win: int = 10) -> pd.DataFrame:
    d = df.dropna(subset=["progress"]).copy()
    d["b"] = (d["progress"] // step).astype(int)
    g = d.groupby("b").agg(n=("label", "size"), pos=("label", lambda s: (s == "positive").sum()),
                           neg=("label", lambda s: (s == "negative").sum()),
                           s=("index", "sum"), sn=("index", lambda s: (s != 0).sum()))
    full = pd.DataFrame({"b": np.arange(0, int(d["progress"].max()) // step + 1)}).set_index("b")
    g = full.join(g).fillna(0)
    r = max(1, win // step)
    rolled = g.rolling(r, min_periods=1).sum()
    out = pd.DataFrame({
        "t_start": np.arange(0, len(rolled)) * step,
        "t_end": np.arange(0, len(rolled)) * step + win,
        "n": rolled["n"],
        "n_positive": rolled["pos"],
        "n_negative": rolled["neg"],
        "mean_sentiment": np.where(rolled["sn"] > 0, rolled["s"] / rolled["sn"].replace(0, np.nan), 0),
        "positive_rate": np.where(rolled["n"] > 0, rolled["pos"] / rolled["n"].replace(0, np.nan), 0),
        "negative_rate": np.where(rolled["n"] > 0, rolled["neg"] / rolled["n"].replace(0, np.nan), 0),
    }).fillna(0)
    return out


@st.cache_data(show_spinner=False)
def analyze(raw: pd.DataFrame, kind: str):
    text, time, plat = detect(raw)
    df = pd.DataFrame({"text": raw[text].fillna("").astype(str)})
    df["platform"] = raw[plat].astype(str) if plat else ("B站弹幕" if kind == "danmaku" else "上传数据")
    if time:
        df["progress"] = pd.to_numeric(raw[time], errors="coerce")
    res = df["text"].map(score_text)
    df["label"] = [r[0] for r in res]
    df["index"] = [r[1] for r in res]
    df["positive"] = [r[2] for r in res]
    df["negative"] = [r[3] for r in res]

    topic_table = pd.DataFrame()
    if len(df) >= 40:
        df, topic_table = build_topics(df)
    else:
        df["theme"] = "样本不足"
        df["topic_id"] = 0
        topic_table = pd.DataFrame([{"topic_id": 0, "theme": "样本不足", "size": len(df),
                                     "share": 1.0, "top_words": ""}])

    counts = df["label"].value_counts()
    summary = (df.groupby("platform")["label"]
               .agg(n="size",
                    positive_pct=lambda s: (s == "positive").mean(),
                    neutral_pct=lambda s: (s == "neutral").mean(),
                    negative_pct=lambda s: (s == "negative").mean())
               .reset_index())
    summary["mean_sentiment"] = summary["platform"].map(df.groupby("platform")["index"].mean())
    summary["level"] = "全部"

    windows = make_windows(df) if kind == "danmaku" and time else None
    return {"df": df, "counts": counts, "summary": summary, "topics": topic_table,
            "windows": windows, "kind": kind}
