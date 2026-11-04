# -*- coding: utf-8 -*-
"""中文分词：游戏专名 + 停用词 + 单字白名单，词云与代表词共用一套口径。"""
import logging
import re
from functools import lru_cache
from pathlib import Path

import jieba

jieba.setLogLevel(logging.ERROR)

DICT_DIR = Path(__file__).parent / "dict"

# 单字白名单：游戏意象 + 常见情感单字，避免“剑 / 鬼 / 帅”被长度规则误删
SINGLE_CHAR = set(
    "剑刀棍鬼妖魔神佛道符雷火虎蚌魂血雨水山庙曲乐尸骨味女拟主怪"
    "帅爽赞棒差烂丑美僵蠢萌燃"
)

SYNONYMS = {
    "黑猴": "黑神话悟空", "黑悟空": "黑神话悟空", "黑猴子": "黑神话悟空",
    "悟空": "黑神话悟空", "游科": "游戏科学",
    "小破站": "B站", "阿b": "B站", "b站": "B站", "B站": "B站",
    "小红薯": "小红书", "xhs": "小红书",
    "换皮怪": "换皮", "套皮": "换皮", "换汤不换药": "换皮",
    "魂系": "魂类", "类魂": "魂类",
    "影零": "影之刃零", "影之刃": "影之刃零", "影之刃0": "影之刃零",
}
ENGLISH_CANON = {
    "ai": "AI", "pv": "PV", "ui": "UI", "mod": "MOD", "ip": "IP", "tga": "TGA",
    "dlss": "DLSS", "dlss5": "DLSS5", "ue5": "UE5", "arpg": "ARPG", "act": "ACT",
    "qte": "QTE", "4k": "4K", "3a": "3A", "ps5": "PS5", "ps6": "PS6", "gta6": "GTA6",
}

NOISE_RE = [
    re.compile(r"@[^\s:：]+"),
    re.compile(r"#[^#\s]{1,20}(?:\[话题\])?#"),
    re.compile(r"\[[^\[\]\r\n]{1,20}\]"),
]


def _load_lines(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]


@lru_cache(maxsize=1)
def _prepare():
    for line in _load_lines(DICT_DIR / "game_dict.txt"):
        parts = line.split()
        word = parts[0]
        freq = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1000
        jieba.add_word(word, freq=freq, tag="nz")
    return set(_load_lines(DICT_DIR / "stopwords.txt"))


@lru_cache(maxsize=1)
def generic_words():
    return set(_load_lines(DICT_DIR / "generic_words.txt"))


def clean(text):
    text = str(text or "")
    for pattern in NOISE_RE:
        text = pattern.sub(" ", text)
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", " ", text)


def tokens(text, drop_generic=False):
    """切词并按停用词、长度、同义词规则归一；drop_generic 用于词云与主题代表词。"""
    stop = _prepare()
    extra = generic_words() if drop_generic else set()
    out = []
    for w in jieba.lcut(clean(text)):
        w = w.strip()
        if not w:
            continue
        low = w.lower()
        w = SYNONYMS.get(w, ENGLISH_CANON.get(low, w))
        if w in stop or w in extra or w.isdigit():
            continue
        if len(w) < 2 and w not in SINGLE_CHAR:
            continue
        out.append(w)
    return out
