#!/usr/bin/env python3
"""统计体制内公众号参考语料的可迁移写作特征。"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path


IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
HTML_RE = re.compile(r"<[^>]+>")
SOURCE_RE = re.compile(r"^\*?来源\s*:", re.I)
SENTENCE_RE = re.compile(r"[^!?！？。…\n]+[!?！？。…]*")
EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "]",
    flags=re.UNICODE,
)
NUMBERED_RE = re.compile(
    r"^(?:#{1,6}\s*)?(?:\d{1,2}[.、]|[0-9]{2}|[一二三四五六七八九十]+[、.])\s*"
)
ENDING_CTA_RE = re.compile(r"点赞|在看|关注|留言|分享|转发|互动|说说看")


def median(values: list[int]) -> float:
    return round(statistics.median(values), 1) if values else 0.0


def mean(values: list[int]) -> float:
    return round(statistics.mean(values), 1) if values else 0.0


def percentile(values: list[int], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * ratio)
    return float(ordered[index])


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    frontmatter: dict[str, str] = {}
    for line in text[4:end].splitlines():
        match = re.match(r"^([a-zA-Z_]+):\s*[\"']?(.*?)[\"']?\s*$", line)
        if match:
            frontmatter[match.group(1)] = match.group(2)
    return frontmatter, text[end + 5 :]


def clean_lines(text: str, title: str) -> list[str]:
    cleaned: list[str] = []
    title_seen = False
    in_recommendations = False

    for raw_line in text.splitlines():
        line = raw_line.replace("\u00a0", " ").strip()
        if not line:
            continue
        if SOURCE_RE.search(line):
            break
        if re.match(r"^(?:#{1,6}\s*)?往期(?:推荐|文章|回顾)", line):
            in_recommendations = True
        if in_recommendations:
            continue
        if IMAGE_RE.fullmatch(line):
            continue
        line = IMAGE_RE.sub("", line)
        line = LINK_RE.sub(r"\1", line)
        line = HTML_RE.sub("", line)
        line = re.sub(r"^[>*_-]+\s*", "", line)
        line = line.replace("**", "").replace("__", "").strip()
        if not line:
            continue
        if line.lstrip("# ") == title and not title_seen:
            title_seen = True
            continue
        if line in {"---", "***", "* * *"}:
            continue
        cleaned.append(line)
    return cleaned


def chinese_length(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def sentence_lengths(paragraphs: list[str]) -> list[int]:
    lengths: list[int] = []
    for paragraph in paragraphs:
        for sentence in SENTENCE_RE.findall(paragraph):
            length = chinese_length(sentence)
            if length:
                lengths.append(length)
    return lengths


def detect_opening(paragraphs: list[str]) -> str:
    opening = "".join(paragraphs[:3])
    if not opening:
        return "空文"
    if re.search(r"您好|来信|周老师", opening):
        return "来信/答疑"
    if "？" in opening or "?" in opening:
        return "疑问钩子"
    if re.search(r"我今年|我是|这几天|今天|最近|昨天|前几天", opening):
        return "第一人称场景"
    if re.search(r"换届|体制内|基层|乡镇|公务员|事业编", opening):
        return "现象/机制切入"
    if re.search(r"大家好|点击上方|关注我们", opening):
        return "问候/关注引导"
    return "直接陈述"


def title_features(title: str) -> list[str]:
    features: list[str] = []
    if "？" in title or "?" in title:
        features.append("疑问")
    if "：" in title or ":" in title or "_" in title:
        features.append("主题+补充")
    if re.search(r"\d", title):
        features.append("数字")
    if re.search(r"我|我们|亲历|亲身", title):
        features.append("第一人称")
    if re.search(r"为什么|怎么|如何|到底|真的|吗", title):
        features.append("问题导向")
    if re.search(r"但|却|不是|而是|没想到|竟然|反而|越.*越", title):
        features.append("反差")
    if re.search(r"体制内|乡镇|基层|公务员|事业编|单位|局长|科级", title):
        features.append("体制标签")
    return features or ["陈述"]


def article_metrics(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = parse_frontmatter(text)
    title = frontmatter.get("title") or re.sub(r"^\d{4}-\d{2}-\d{2}\s*-\s*", "", path.stem)
    paragraphs = clean_lines(body, title)
    paragraph_lengths = [chinese_length(p) for p in paragraphs]
    sentences = sentence_lengths(paragraphs)
    joined = "\n".join(paragraphs)
    ending = "".join(paragraphs[-5:])

    return {
        "path": str(path),
        "title": title,
        "title_length": chinese_length(title),
        "title_features": title_features(title),
        "body_length": chinese_length(joined),
        "paragraph_count": len(paragraphs),
        "paragraph_lengths": paragraph_lengths,
        "sentence_lengths": sentences,
        "opening": detect_opening(paragraphs),
        "first_person": len(re.findall(r"我|我们|咱们", joined)),
        "second_person": len(re.findall(r"你|您", joined)),
        "questions": len(re.findall(r"[？?]", joined)),
        "exclamations": len(re.findall(r"[！!]", joined)),
        "emoji": len(EMOJI_RE.findall(joined)),
        "numbered_sections": sum(bool(NUMBERED_RE.search(p)) for p in paragraphs),
        "ending_cta": bool(ENDING_CTA_RE.search(ending)),
        "ending_excerpt": ending[-100:],
    }


def aggregate(author: str, articles: list[dict[str, object]]) -> dict[str, object]:
    nonempty = [article for article in articles if article["body_length"]]
    title_lengths = [int(article["title_length"]) for article in articles]
    body_lengths = [int(article["body_length"]) for article in nonempty]
    paragraph_counts = [int(article["paragraph_count"]) for article in nonempty]
    paragraph_lengths = [
        int(length)
        for article in nonempty
        for length in article["paragraph_lengths"]  # type: ignore[union-attr]
    ]
    sentences = [
        int(length)
        for article in nonempty
        for length in article["sentence_lengths"]  # type: ignore[union-attr]
    ]
    title_features = Counter(
        feature
        for article in articles
        for feature in article["title_features"]  # type: ignore[union-attr]
    )
    openings = Counter(str(article["opening"]) for article in nonempty)

    return {
        "author": author,
        "files": len(articles),
        "nonempty": len(nonempty),
        "title_length": {
            "mean": mean(title_lengths),
            "median": median(title_lengths),
            "p25": percentile(title_lengths, 0.25),
            "p75": percentile(title_lengths, 0.75),
        },
        "body_length": {
            "mean": mean(body_lengths),
            "median": median(body_lengths),
            "p25": percentile(body_lengths, 0.25),
            "p75": percentile(body_lengths, 0.75),
        },
        "paragraphs_per_article_median": median(paragraph_counts),
        "paragraph_length_median": median(paragraph_lengths),
        "sentence_length_median": median(sentences),
        "title_features": dict(title_features.most_common()),
        "openings": dict(openings.most_common()),
        "articles_with_numbered_sections_pct": round(
            100 * sum(bool(article["numbered_sections"]) for article in nonempty) / len(nonempty), 1
        )
        if nonempty
        else 0.0,
        "articles_with_emoji_pct": round(
            100 * sum(bool(article["emoji"]) for article in nonempty) / len(nonempty), 1
        )
        if nonempty
        else 0.0,
        "articles_with_ending_cta_pct": round(
            100 * sum(bool(article["ending_cta"]) for article in nonempty) / len(nonempty), 1
        )
        if nonempty
        else 0.0,
        "first_person_per_1000_chars": round(
            1000 * sum(int(article["first_person"]) for article in nonempty) / sum(body_lengths), 1
        )
        if body_lengths and sum(body_lengths)
        else 0.0,
        "second_person_per_1000_chars": round(
            1000 * sum(int(article["second_person"]) for article in nonempty) / sum(body_lengths), 1
        )
        if body_lengths and sum(body_lengths)
        else 0.0,
        "questions_per_article": round(
            sum(int(article["questions"]) for article in nonempty) / len(nonempty), 1
        )
        if nonempty
        else 0.0,
        "exclamations_per_article": round(
            sum(int(article["exclamations"]) for article in nonempty) / len(nonempty), 1
        )
        if nonempty
        else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="包含各博主子目录的语料根目录")
    parser.add_argument("--details", action="store_true", help="同时输出单篇文章指标")
    args = parser.parse_args()

    if not args.source.is_dir():
        parser.error(f"语料目录不存在: {args.source}")

    report: dict[str, object] = {"source": str(args.source), "authors": []}
    details: dict[str, list[dict[str, object]]] = {}
    for author_dir in sorted(path for path in args.source.iterdir() if path.is_dir()):
        articles = [article_metrics(path) for path in sorted(author_dir.glob("*.md"))]
        report["authors"].append(aggregate(author_dir.name, articles))  # type: ignore[union-attr]
        if args.details:
            details[author_dir.name] = articles
    if args.details:
        report["details"] = details

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
