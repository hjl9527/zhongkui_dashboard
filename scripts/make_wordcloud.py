# -*- coding: utf-8 -*-
"""预生成词云 PNG，避免在 Streamlit Cloud 上依赖中文字体与实时渲染。"""
import os
import sys
from collections import Counter

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tokenizer import tokens  # noqa: E402

try:
    from wordcloud import WordCloud
except ImportError:
    raise SystemExit("请先安装 wordcloud")

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
COLORS = ["#b0321c", "#234f47", "#c9a227", "#4a6fa5", "#8c3b52", "#a8845c", "#23201c"]


def most_common(texts, limit=400):
    counter = Counter()
    for t in texts:
        counter.update(tokens(t, drop_generic=True))
    return dict(counter.most_common(limit))


def draw(freq, out, title=None):
    if not freq:
        print("skip empty", out)
        return
    font = next((f for f in FONT_CANDIDATES if os.path.exists(f)), None)
    if font is None:
        raise SystemExit("找不到中文字体")

    def color_func(word, font_size, position, orientation, random_state=None, **kwargs):
        return COLORS[hash(word) % len(COLORS)]

    wc = WordCloud(font_path=font, width=1200, height=600, background_color="#f8f6f2",
                   max_words=260, prefer_horizontal=0.92, relative_scaling=0.4,
                   margin=6, color_func=color_func)
    wc.generate_from_frequencies(freq)
    wc.to_file(out.replace(".jpg", ".png"))
    from PIL import Image
    Image.open(out.replace(".jpg", ".png")).convert("RGB").save(out, quality=82, optimize=True)
    os.remove(out.replace(".jpg", ".png"))
    print("saved", out, os.path.getsize(out) // 1024, "KB")


def main():
    data = os.path.join(ROOT, "data")
    assets = os.path.join(ROOT, "assets")
    os.makedirs(assets, exist_ok=True)
    comments = pd.read_parquet(os.path.join(data, "comments.parquet"))
    danmaku = pd.read_parquet(os.path.join(data, "danmaku.parquet"))
    draw(most_common(comments["text"]), os.path.join(assets, "wc_comments.jpg"))
    for name, slug in [("B站", "bili"), ("小红书", "xhs"), ("小黑盒", "xiaoheihe"), ("微博", "weibo")]:
        draw(most_common(comments.loc[comments["platform"] == name, "text"]),
             os.path.join(assets, f"wc_comments_{slug}.jpg"))
    draw(most_common(danmaku.loc[danmaku["label"] != "ritual", "text"]),
         os.path.join(assets, "wc_danmaku.jpg"))


if __name__ == "__main__":
    main()
