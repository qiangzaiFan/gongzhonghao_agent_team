#!/usr/bin/env python3
"""Helpers for reading the Anxia astrology article corpus."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from quality_gate import cjk_len, markdown_to_plain, parse_article


DEFAULT_CORPUS_DIR = Path(r"D:\自媒体\知识库\01-公众号文章\星座公众号文章\安夏星座")
ARTICLE_NAME_RE = re.compile(
    r"^(?P<seq>\d{4})_(?P<published>\d{4}-\d{2}-\d{2})_"
    r"(?P<title>.+)_(?P<appmsgid>\d+)_(?P<itemidx>\d+)\.md$"
)
SIGN_TERMS = (
    "白羊",
    "金牛",
    "双子",
    "巨蟹",
    "狮子",
    "处女",
    "天秤",
    "天蝎",
    "射手",
    "摩羯",
    "水瓶",
    "双鱼",
)
TITLE_KEYWORDS = (
    "财运",
    "贵人",
    "好运",
    "喜事",
    "下半年",
    "本月",
    "7月",
    "6月",
    "8月",
    "事业",
    "感情",
    "警惕",
    "远离",
    "小心",
    "躲不掉",
    "这辈子",
    "第一名",
    "三大",
    "TOP3",
    "马上转运",
)


@dataclass(frozen=True)
class CorpusArticle:
    path: Path
    seq: int
    published: date
    title: str
    appmsgid: str
    itemidx: int
    body: str
    plain: str
    cjk: int


def is_corpus_article(path: Path) -> bool:
    return ARTICLE_NAME_RE.match(path.name) is not None


def clean_article_body(body: str) -> str:
    body = re.sub(r"(?m)^# .*$", "", body)
    body = re.sub(r"(?m)^- 公众号文章：.*$", "", body)
    body = re.sub(r"(?m)^- 星座：.*$", "", body)
    body = re.sub(r"(?m)^- 发布时间：.*$", "", body)
    body = re.sub(r"(?m)^- 原文链接：.*$", "", body)
    return body.strip()


def load_corpus_article(path: Path) -> CorpusArticle | None:
    match = ARTICLE_NAME_RE.match(path.name)
    if not match:
        return None
    article = parse_article(path)
    body = clean_article_body(article.body)
    plain = markdown_to_plain(body)
    return CorpusArticle(
        path=path,
        seq=int(match.group("seq")),
        published=date.fromisoformat(match.group("published")),
        title=article.title or match.group("title"),
        appmsgid=match.group("appmsgid"),
        itemidx=int(match.group("itemidx")),
        body=body,
        plain=plain,
        cjk=cjk_len(plain),
    )


def load_corpus(corpus_dir: Path) -> list[CorpusArticle]:
    if not corpus_dir.is_dir():
        raise FileNotFoundError(f"安夏知识库目录不存在：{corpus_dir}")
    articles: list[CorpusArticle] = []
    for path in sorted(corpus_dir.glob("*.md")):
        item = load_corpus_article(path)
        if item is not None:
            articles.append(item)
    return articles


def count_terms(titles: list[str], terms: tuple[str, ...]) -> dict[str, int]:
    return {term: sum(title.count(term) for title in titles) for term in terms}


def normalized_title(title: str) -> str:
    return re.sub(r"\s+", "", title)


def hot_titles_by_reuse(articles: list[CorpusArticle], *, min_count: int = 2) -> set[str]:
    counts = Counter(normalized_title(item.title) for item in articles if item.title)
    return {title for title, count in counts.items() if count >= min_count}
