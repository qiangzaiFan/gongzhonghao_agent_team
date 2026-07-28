#!/usr/bin/env python3
"""Persist and summarize post-publication performance for Anxia drafts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

from content_record import DEFAULT_RECORD_DIR, article_digest, default_record_path, load_record, validate_record


BASE_DIR = Path(__file__).parent
DEFAULT_LOG_PATH = BASE_DIR / "reviews" / "performance.jsonl"
METRIC_FIELDS = ("impressions", "reads", "likes", "shares", "comments", "follows")
SCORE_READ_WEIGHT = 0.4
SCORE_ENGAGEMENT_WEIGHT = 0.6


def _non_negative(value: int, name: str) -> int:
    if value < 0:
        raise ValueError(f"{name} 不能小于 0")
    return value


def _distribution_variants(
    record: dict[str, Any],
    dimension: str,
) -> tuple[list[dict[str, str]], str]:
    distribution = record.get("distribution")
    if isinstance(distribution, dict):
        details = distribution.get(dimension)
        if isinstance(details, dict) and isinstance(details.get("variants"), list):
            variants: list[dict[str, str]] = []
            for raw_variant in details["variants"]:
                if not isinstance(raw_variant, dict):
                    continue
                key = str(raw_variant.get("key", "")).strip()
                text = str(raw_variant.get("text", "")).strip()
                if not key or not text:
                    continue
                variant = {"key": key, "text": text}
                for field in ("label", "formula"):
                    value = str(raw_variant.get(field, "")).strip()
                    if value:
                        variant[field] = value
                variants.append(variant)
            selected_key = str(details.get("selected_key", "")).strip()
            if variants:
                return variants, selected_key

    if dimension == "title":
        titles = record.get("titles")
        candidates = titles.get("candidates", []) if isinstance(titles, dict) else []
        variants = [
            {"key": f"title-{index}", "text": str(title).strip(), "formula": "未标注"}
            for index, title in enumerate(candidates, start=1)
            if str(title).strip()
        ]
        selected = titles.get("selected") if isinstance(titles, dict) else ""
        selected_key = next(
            (item["key"] for item in variants if item["text"] == selected),
            variants[0]["key"] if variants else "",
        )
        return variants, selected_key

    body_variant = record.get("body_variant")
    hook = body_variant.get("hook") if isinstance(body_variant, dict) else ""
    return (
        [{"key": "opening-default", "text": str(hook).strip(), "label": "默认开头"}]
        if str(hook).strip()
        else [],
        "opening-default",
    )


def _resolve_variant(
    record: dict[str, Any],
    dimension: str,
    requested_key: str | None,
) -> dict[str, str]:
    variants, selected_key = _distribution_variants(record, dimension)
    selected = (requested_key or selected_key).strip()
    for variant in variants:
        if variant["key"] == selected:
            return variant
    choices = "、".join(f"{item['key']}（{item['text']}）" for item in variants)
    label = "标题" if dimension == "title" else "开头"
    raise ValueError(f"不支持的{label}版本 {selected or '空'}；可选：{choices or '无'}")


def build_entry(
    article_path: Path,
    record_path: Path,
    *,
    published_at: str,
    impressions: int,
    reads: int,
    likes: int,
    shares: int,
    comments: int,
    follows: int,
    title_variant: str | None = None,
    opening_variant: str | None = None,
) -> dict[str, Any]:
    errors = validate_record(article_path, record_path)
    if errors:
        raise ValueError("；".join(errors))
    values = {
        name: _non_negative(value, name)
        for name, value in {
            "impressions": impressions,
            "reads": reads,
            "likes": likes,
            "shares": shares,
            "comments": comments,
            "follows": follows,
        }.items()
    }
    if values["impressions"] and values["reads"] > values["impressions"]:
        raise ValueError("reads 不能大于 impressions")

    record = load_record(record_path)
    topic = record["topic"]
    variant = record["body_variant"]
    title_choice = _resolve_variant(record, "title", title_variant)
    opening_choice = _resolve_variant(record, "opening", opening_variant)
    read_base = values["reads"]
    engagement = values["likes"] + values["shares"] + values["comments"] + values["follows"]
    return {
        "schema_version": 1,
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "published_at": published_at,
        "article": str(article_path.resolve()),
        "article_sha256": article_digest(article_path),
        "editorial_record": str(record_path.resolve()),
        "sign": topic["sign"],
        "theme": topic["theme"],
        "body_variant": variant["key"],
        "title_variant": title_choice["key"],
        "title_formula": title_choice.get("formula", "未标注"),
        "published_title": title_choice["text"],
        "opening_variant": opening_choice["key"],
        "opening_label": opening_choice.get("label", "未标注"),
        "opening_text": opening_choice["text"],
        **values,
        "read_rate": round(values["reads"] / values["impressions"], 6) if values["impressions"] else None,
        "engagement_rate": round(engagement / read_base, 6) if read_base else None,
    }


def append_entry(log_path: Path, entry: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_entries(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            entry = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{log_path}:{line_no} 不是有效 JSON：{exc}") from exc
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _group_summary(entries: list[dict[str, Any]], field: str) -> list[tuple[str, int, float, float]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        value = str(entry.get(field, "")).strip()
        if value:
            groups[value].append(entry)

    summary: list[tuple[str, int, float, float]] = []
    for value, group in groups.items():
        read_rates = [float(item["read_rate"]) for item in group if item.get("read_rate") is not None]
        engagement_rates = [
            float(item["engagement_rate"])
            for item in group
            if item.get("engagement_rate") is not None
        ]
        summary.append(
            (
                value,
                len(group),
                sum(read_rates) / len(read_rates) if read_rates else 0.0,
                sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0.0,
            )
        )
    return sorted(summary, key=lambda item: (item[3], item[2], item[1]), reverse=True)


def topic_performance_scores(
    entries: list[dict[str, Any]],
    *,
    min_samples: int = 3,
) -> dict[tuple[str, str], float]:
    """Return reliable sign/theme scores for planning, not a raw one-post ranking."""
    if min_samples <= 0:
        raise ValueError("min_samples 必须大于 0")

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        sign = str(entry.get("sign", "")).strip()
        theme = str(entry.get("theme", "")).strip()
        if sign and theme:
            groups[(sign, theme)].append(entry)

    scores: dict[tuple[str, str], float] = {}
    for key, group in groups.items():
        if len(group) < min_samples:
            continue
        read_rates = [float(item["read_rate"]) for item in group if item.get("read_rate") is not None]
        engagement_rates = [
            float(item["engagement_rate"])
            for item in group
            if item.get("engagement_rate") is not None
        ]
        if not read_rates or not engagement_rates:
            continue
        scores[key] = round(
            sum(read_rates) / len(read_rates) * SCORE_READ_WEIGHT
            + sum(engagement_rates) / len(engagement_rates) * SCORE_ENGAGEMENT_WEIGHT,
            6,
        )
    return scores


def performance_score(entry: dict[str, Any]) -> float | None:
    read_rate = entry.get("read_rate")
    engagement_rate = entry.get("engagement_rate")
    if read_rate is None or engagement_rate is None:
        return None
    return float(read_rate) * SCORE_READ_WEIGHT + float(engagement_rate) * SCORE_ENGAGEMENT_WEIGHT


def breakout_entries(
    entries: list[dict[str, Any]],
    *,
    min_samples: int = 5,
    multiplier: float = 1.5,
) -> tuple[float | None, float | None, list[dict[str, Any]]]:
    """Select posts that materially beat the account's typical combined rate."""
    if min_samples <= 0:
        raise ValueError("min_samples 必须大于 0")
    if multiplier <= 1:
        raise ValueError("multiplier 必须大于 1")

    scored = [
        (score, entry)
        for entry in entries
        if (score := performance_score(entry)) is not None
    ]
    if len(scored) < min_samples:
        return None, None, []

    baseline = median(score for score, _ in scored)
    threshold = baseline * multiplier
    breakout = [
        {**entry, "performance_score": round(score, 6)}
        for score, entry in scored
        if score >= threshold
    ]
    breakout.sort(
        key=lambda entry: (
            float(entry["performance_score"]),
            float(entry.get("engagement_rate") or 0.0),
            float(entry.get("read_rate") or 0.0),
        ),
        reverse=True,
    )
    return baseline, threshold, breakout


def format_report(entries: list[dict[str, Any]]) -> str:
    lines = [f"已记录表现：{len(entries)} 篇"]
    if not entries:
        lines.append("暂无数据。发布后用 record 写入曝光、阅读和互动数据。")
        return "\n".join(lines)

    for field, label in (
        ("theme", "主题"),
        ("sign", "星座"),
        ("title_formula", "标题公式"),
        ("title_variant", "标题版本"),
        ("opening_variant", "开头版本"),
        ("body_variant", "正文变体"),
    ):
        lines.extend(("", f"## {label}表现"))
        for value, count, read_rate, engagement_rate in _group_summary(entries, field):
            lines.append(
                f"- {value}：{count} 篇，阅读率 {read_rate:.2%}，互动率 {engagement_rate:.2%}"
            )
    return "\n".join(lines)


def format_postmortem(
    entries: list[dict[str, Any]],
    *,
    min_samples: int = 5,
    multiplier: float = 1.5,
) -> str:
    valid_count = sum(performance_score(entry) is not None for entry in entries)
    baseline, threshold, breakout = breakout_entries(
        entries,
        min_samples=min_samples,
        multiplier=multiplier,
    )
    if baseline is None or threshold is None:
        return (
            f"爆款复盘：有效样本 {valid_count} 篇，至少需要 {min_samples} 篇"
            "同时具备阅读率和互动率的记录。"
        )

    lines = [
        f"爆款复盘：有效样本 {valid_count} 篇，账号综合基线 {baseline:.2%}，"
        f"入选阈值 {threshold:.2%}（基线 × {multiplier:g}）",
    ]
    if not breakout:
        lines.append("暂无超过阈值的文章，继续积累样本后再看趋势。")
        return "\n".join(lines)

    for index, entry in enumerate(breakout, start=1):
        title = str(entry.get("published_title") or Path(str(entry.get("article", ""))).stem)
        lines.extend(
            (
                "",
                f"## 复盘卡 {index}：{title}",
                (
                    f"- 表现：综合 {float(entry['performance_score']):.2%}，"
                    f"阅读率 {float(entry.get('read_rate') or 0.0):.2%}，"
                    f"互动率 {float(entry.get('engagement_rate') or 0.0):.2%}"
                ),
                f"- 选题：{entry.get('sign', '未标注')} × {entry.get('theme', '未标注')}；"
                f"正文 {entry.get('body_variant', '未标注')}",
                (
                    f"- 标题：{entry.get('title_formula', '未标注')} "
                    f"({entry.get('title_variant', '未标注')})"
                ),
                (
                    f"- 开头：{entry.get('opening_label', '未标注')} "
                    f"({entry.get('opening_variant', '未标注')})"
                ),
                f"- 发布时间：{entry.get('published_at', '未标注')}",
            )
        )
    return "\n".join(lines)


def record(args: argparse.Namespace) -> int:
    if not args.article.is_file():
        print(f"文章不存在：{args.article}", file=sys.stderr)
        return 1
    record_path = args.editorial_record or default_record_path(args.article, args.record_dir)
    try:
        entry = build_entry(
            args.article,
            record_path,
            published_at=args.published_at,
            impressions=args.impressions,
            reads=args.reads,
            likes=args.likes,
            shares=args.shares,
            comments=args.comments,
            follows=args.follows,
            title_variant=args.title_variant,
            opening_variant=args.opening_variant,
        )
    except ValueError as exc:
        print(f"无法记录表现：{exc}", file=sys.stderr)
        return 1
    append_entry(args.log, entry)
    print(f"已记录表现：{args.log}")
    return 0


def report(args: argparse.Namespace) -> int:
    try:
        entries = load_entries(args.log)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(format_report(entries))
    return 0


def postmortem(args: argparse.Namespace) -> int:
    try:
        entries = load_entries(args.log)
        print(
            format_postmortem(
                entries,
                min_samples=args.min_samples,
                multiplier=args.multiplier,
            )
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="记录和复盘安夏短文发布表现")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("article", type=Path)
    record_parser.add_argument("--editorial-record", type=Path)
    record_parser.add_argument("--record-dir", type=Path, default=DEFAULT_RECORD_DIR)
    record_parser.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    record_parser.add_argument(
        "--published-at",
        default=datetime.now().astimezone().isoformat(timespec="seconds"),
    )
    for field in METRIC_FIELDS:
        record_parser.add_argument(f"--{field}", required=True, type=int)
    record_parser.add_argument(
        "--title-variant",
        help="实际发布标题版本，例如 title-2；默认使用编辑记录中的默认版本",
    )
    record_parser.add_argument(
        "--opening-variant",
        help="实际发布开头版本，例如 direct-alert；默认使用编辑记录中的默认版本",
    )
    record_parser.set_defaults(func=record)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    report_parser.set_defaults(func=report)

    postmortem_parser = subparsers.add_parser("postmortem")
    postmortem_parser.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    postmortem_parser.add_argument("--min-samples", type=int, default=5)
    postmortem_parser.add_argument("--multiplier", type=float, default=1.5)
    postmortem_parser.set_defaults(func=postmortem)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
