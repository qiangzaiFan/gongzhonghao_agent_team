#!/usr/bin/env python3
"""Analyze the Anxia astrology corpus and print a compact operating profile."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import mean

from anxia_corpus import DEFAULT_CORPUS_DIR, SIGN_TERMS, TITLE_KEYWORDS, count_terms, load_corpus


def _date_range(items) -> str:
    if not items:
        return "n/a"
    dates = [item.published for item in items]
    return f"{min(dates).isoformat()}..{max(dates).isoformat()}"


def _avg(values: list[int]) -> float:
    return mean(values) if values else 0.0


def _bucket_lengths(items) -> dict[str, int]:
    buckets = {"<120": 0, "120-260": 0, "261-450": 0, "451-900": 0, "900+": 0}
    for item in items:
        if item.cjk < 120:
            buckets["<120"] += 1
        elif item.cjk <= 260:
            buckets["120-260"] += 1
        elif item.cjk <= 450:
            buckets["261-450"] += 1
        elif item.cjk < 900:
            buckets["451-900"] += 1
        else:
            buckets["900+"] += 1
    return buckets


def _daily_counts(items) -> Counter[date]:
    counts: Counter[date] = Counter()
    for item in items:
        counts[item.published] += 1
    return counts


def _top_endings(items, limit: int = 8) -> list[tuple[str, int]]:
    endings: Counter[str] = Counter()
    for item in items:
        lines = [line.strip() for line in item.plain.splitlines() if line.strip()]
        if not lines:
            text = item.plain.strip()
            if text:
                endings[text[-36:]] += 1
            continue
        endings[lines[-1][-42:]] += 1
    return endings.most_common(limit)


def build_report(corpus_dir: Path, since: date) -> str:
    articles = load_corpus(corpus_dir)
    recent = [item for item in articles if item.published >= since]
    titles = [item.title for item in articles]
    recent_titles = [item.title for item in recent]
    duplicate_titles = [
        (title, count)
        for title, count in Counter(titles).most_common()
        if count > 1
    ]
    daily = _daily_counts(recent)
    daily_distribution: defaultdict[int, int] = defaultdict(int)
    for count in daily.values():
        daily_distribution[count] += 1

    lines = [
        "# 安夏星座语料分析",
        "",
        f"- 语料目录：{corpus_dir}",
        f"- 全量文章：{len(articles)}",
        f"- 全量日期：{_date_range(articles)}",
        f"- 主分析窗口：{since.isoformat()}..{_date_range(recent).split('..')[-1]}",
        f"- 窗口文章：{len(recent)}",
        f"- 窗口平均正文：{_avg([item.cjk for item in recent]):.1f} 个中文字符",
        "",
        "## 每日发布数",
    ]
    if daily:
        lines.append(f"- 平均每日：{_avg(list(daily.values())):.2f} 篇")
        lines.extend(
            f"- {count} 篇/天：{days} 天"
            for count, days in sorted(daily_distribution.items())
        )
    else:
        lines.append("- 无窗口数据")

    lines.append("")
    lines.append("## 正文长度")
    for name, count in _bucket_lengths(recent).items():
        lines.append(f"- {name}：{count}")

    lines.append("")
    lines.append("## 星座覆盖")
    sign_counts = count_terms(recent_titles, SIGN_TERMS)
    for sign, count in sorted(sign_counts.items(), key=lambda item: (-item[1], item[0])):
        if count:
            lines.append(f"- {sign}：{count}")

    lines.append("")
    lines.append("## 标题关键词")
    keyword_counts = count_terms(recent_titles, TITLE_KEYWORDS)
    for keyword, count in sorted(keyword_counts.items(), key=lambda item: (-item[1], item[0])):
        if count:
            lines.append(f"- {keyword}：{count}")

    lines.append("")
    lines.append("## 重复标题")
    if duplicate_titles:
        lines.extend(f"- {title}：{count}" for title, count in duplicate_titles[:20])
    else:
        lines.append("- 未发现重复标题")

    lines.append("")
    lines.append("## 正文常用结尾")
    endings = _top_endings(recent)
    if endings:
        lines.extend(f"- {ending}：{count}" for ending, count in endings)
    else:
        lines.append("- 无窗口数据")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="分析安夏星座知识库文章")
    parser.add_argument("corpus_dir", nargs="?", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--since", default="2026-06-01", help="主分析窗口开始日期 YYYY-MM-DD")
    args = parser.parse_args()
    try:
        since = date.fromisoformat(args.since)
    except ValueError as exc:
        parser.error(f"--since 必须是 YYYY-MM-DD：{exc}")
    print(build_report(args.corpus_dir, since))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
