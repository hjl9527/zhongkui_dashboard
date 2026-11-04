# -*- coding: utf-8 -*-
"""把分析产物压成看板用的全量 parquet（zstd）。

用法：
    python scripts/build_data.py --source "D:\\找工啦\\简历\\游科_运营\\数据分析"
"""
import argparse
import json
import os

import pandas as pd

PLATFORMS = {
    "bili_comments": "B站",
    "xhs_comments": "小红书",
    "xiaoheihe_comments": "小黑盒",
    "weibo_comments": "微博",
}


def _merge_theme(mapping, code):
    mp = mapping.loc[mapping["platform"] == code, ["topic_id", "confirmed_name"]]
    return mp.rename(columns={"confirmed_name": "theme"})


def build_comments(source, out_dir, mapping):
    frames = []
    sent_dir = os.path.join(source, "outputs", "01_sentiment")
    topic_dir = os.path.join(source, "outputs", "03_topics_bt")
    for code, name in PLATFORMS.items():
        lab = pd.read_csv(os.path.join(sent_dir, f"labels_{code}.csv"))
        top = pd.read_csv(os.path.join(topic_dir, f"topics_{code}.csv"))[["id", "topic_id"]]
        d = lab[["text_clean", "is_reply", "label"]].copy()
        d["row_id"] = lab["id"].values
        d = d.merge(top, left_on="row_id", right_on="id", how="left")
        d = d.merge(_merge_theme(mapping, code), on="topic_id", how="left")
        d = d.rename(columns={"text_clean": "text"})
        d["platform"] = name
        d["platform_code"] = code
        d["is_reply"] = d["is_reply"].fillna(False).astype(bool)
        d["label"] = d["label"].fillna("neutral")
        d["theme"] = d["theme"].fillna("未建模")
        d["topic_id"] = d["topic_id"].astype("Int64")
        frames.append(d[["platform", "platform_code", "text", "is_reply", "label", "topic_id", "theme"]])
    comments = pd.concat(frames, ignore_index=True)
    comments.to_parquet(os.path.join(out_dir, "comments.parquet"), compression="zstd", index=False)
    return comments


def build_danmaku(source, out_dir, mapping):
    dm = pd.read_csv(os.path.join(source, "danmu_tokenized.csv"), usecols=["progress", "text_clean"])
    lab = pd.read_csv(os.path.join(source, "outputs", "02_danmaku", "labels_danmaku.csv"))
    top = pd.read_csv(os.path.join(source, "outputs", "03_topics_bt", "topics_danmaku.csv"))[["id", "topic_id"]]
    assert len(dm) == len(lab) == len(top), (len(dm), len(lab), len(top))
    d = dm.rename(columns={"text_clean": "text"}).copy()
    d["label"] = lab["label"].values
    d["topic_id"] = top["topic_id"].astype("Int64").values
    d = d.merge(_merge_theme(mapping, "danmaku"), on="topic_id", how="left")
    d["theme"] = d["theme"].fillna("未建模")
    d["t_sec"] = d["progress"].round(0).astype(int)
    d["platform"] = "B站"
    d = d[["platform", "progress", "t_sec", "text", "label", "topic_id", "theme"]]
    d.to_parquet(os.path.join(out_dir, "danmaku.parquet"), compression="zstd", index=False)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=r"D:\找工啦\简历\游科_运营\数据分析")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
    args = ap.parse_args()
    src, out = args.source, args.out
    os.makedirs(out, exist_ok=True)
    mapping = pd.read_csv(os.path.join(src, "outputs", "03_topics_bt", "theme_mapping.csv"))

    comments = build_comments(src, out, mapping)
    danmaku = build_danmaku(src, out, mapping)

    win = pd.read_csv(os.path.join(src, "outputs", "02_danmaku", "windows_10s_step2s.csv"))
    win.to_parquet(os.path.join(out, "windows_10s.parquet"), compression="zstd", index=False)

    peaks = pd.read_csv(os.path.join(src, "outputs", "02_danmaku", "peaks_valleys_10s.csv"))
    ann = pd.read_csv(os.path.join(src, "outputs", "02_danmaku", "peak_annotations.csv"))
    ann = ann[["rank", "scene", "event_topic", "evidence"]]
    peaks = peaks.merge(ann, on="rank", how="left")
    peaks.to_parquet(os.path.join(out, "peaks.parquet"), compression="zstd", index=False)

    summary = pd.read_csv(os.path.join(src, "outputs", "01_sentiment", "sentiment_summary.csv"))
    summary.to_parquet(os.path.join(out, "sentiment_summary.parquet"), compression="zstd", index=False)

    ts = pd.read_csv(os.path.join(src, "outputs", "04_report", "theme_sentiment_matrix.csv"))
    ts["theme"] = ts["theme"].replace({"未建模/无主题": "未建模", "未建模/无主题 ": "未建模"})
    share = pd.read_csv(os.path.join(src, "outputs", "04_report", "theme_share_matrix.csv"))
    ts = ts.rename(columns={"platform": "platform_code"})
    share_long = share.melt(id_vars="theme", var_name="platform_code", value_name="share")
    ts = ts.merge(share_long, on=["theme", "platform_code"], how="left")
    code2name = {**PLATFORMS, "danmaku": "B站弹幕"}
    ts["platform_name"] = ts["platform_code"].map(code2name)
    ts.to_parquet(os.path.join(out, "themes.parquet"), compression="zstd", index=False)

    frames = []
    topic_dir = os.path.join(src, "outputs", "03_topics_bt")
    for code, name in PLATFORMS.items():
        info = pd.read_csv(os.path.join(topic_dir, f"topic_info_{code}.csv"))
        sent = pd.read_csv(os.path.join(topic_dir, f"topic_sentiment_{code}.csv"))
        d = info.merge(sent.drop(columns=["top_words", "size", "share"], errors="ignore"), on="topic_id", how="left")
        d = d.merge(_merge_theme(mapping, code), on="topic_id", how="left")
        d["theme"] = d["theme"].fillna("未建模")
        d["platform"] = name
        d["platform_code"] = code
        d["representative_docs"] = d["representative_docs"].fillna("").str.slice(0, 300)
        frames.append(d[["platform", "platform_code", "topic_id", "theme", "size", "share", "top_words",
                         "representative_docs", "positive_rate", "negative_rate", "mean_sentiment",
                         "sentiment_var", "polarization"]])
    info = pd.read_csv(os.path.join(topic_dir, "topic_info_danmaku.csv"))
    sent = pd.read_csv(os.path.join(topic_dir, "topic_sentiment_danmaku.csv"))
    d = info.merge(sent.drop(columns=["top_words", "size", "share"], errors="ignore"), on="topic_id", how="left")
    d = d.merge(_merge_theme(mapping, "danmaku"), on="topic_id", how="left")
    d["theme"] = d["theme"].fillna("未建模")
    d["platform"] = "B站弹幕"
    d["platform_code"] = "danmaku"
    d["representative_docs"] = d["representative_docs"].fillna("").str.slice(0, 300)
    frames.append(d[["platform", "platform_code", "topic_id", "theme", "size", "share", "top_words",
                     "representative_docs", "positive_rate", "negative_rate", "mean_sentiment",
                     "sentiment_var", "polarization"]])
    pd.concat(frames, ignore_index=True).to_parquet(
        os.path.join(out, "topics.parquet"), compression="zstd", index=False)

    stats = {
        "comments": int(len(comments)),
        "danmaku": int(len(danmaku)),
        "duration_sec": int(danmaku["progress"].max()),
        "danmaku_per_min": round(len(danmaku) / (danmaku["progress"].max() / 60), 0),
        "platforms": [
            {"name": k, "comments": int(v), "reply_share": round(float(comments.loc[comments.platform == k, "is_reply"].mean()), 4)}
            for k, v in comments["platform"].value_counts().items()
        ],
    }
    with open(os.path.join(out, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    for name in sorted(os.listdir(out)):
        p = os.path.join(out, name)
        print(f"{name:28s} {os.path.getsize(p)/1024:8.1f} KB")


if __name__ == "__main__":
    main()
