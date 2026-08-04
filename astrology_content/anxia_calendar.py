#!/usr/bin/env python3
"""Generate a stable Anxia-style daily topic calendar."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from anxia_corpus import DEFAULT_CORPUS_DIR, SIGN_TERMS, load_corpus
from performance_tracker import DEFAULT_LOG_PATH, load_entries, topic_performance_scores


TEMPLATE_POOLS = {
    "运势/提醒": (
        ("{sign}座本月必须警惕的一个{risk}", {"risk": ("节奏信号", "情绪消耗", "社交误区")}),
        ("{sign}座下半年躲不掉的三大{change}", {"change": ("状态转折", "生活变化", "重要选择")}),
        ("{month}，给{sign}座一个{reminder}", {"reminder": ("重要提醒", "事业提醒", "节奏提醒")}),
        ("{sign}座，{stage}整体运势开始走高", {"stage": ("下半年", "本月", "这段时间")}),
    ),
    "关系/性格": (
        ("能让{sign}座{reaction}的{obj}", {"reaction": ("彻底清醒", "重新靠近", "主动珍惜"), "obj": ("两种关系", "一个细节", "三类人")}),
        ("{sign}座这辈子最该珍惜的{asset}", {"asset": ("三种真心", "一个贵人", "一类关系")}),
    ),
    "财运/贵人": (
        ("{sign}座，{month}有一个{opportunity}正在路上", {"opportunity": ("财运机会", "贵人信号", "事业机会")}),
        ("{sign}座最容易忽略的一个{asset}", {"asset": ("贵人", "事业机会", "财务突破口")}),
        ("{sign}座下半年会出现的三大{change}", {"change": ("财务变化", "事业机会", "贵人信号")}),
    ),
}
THEMES = tuple(TEMPLATE_POOLS)
FALLBACK_SIGNS = SIGN_TERMS
MONTH_LABELS = tuple(f"{month}月" for month in range(1, 13))
DEFAULT_DAILY_SHORT_ARTICLES = 2


@dataclass(frozen=True)
class CalendarItem:
    day: date
    slot: int
    sign: str
    theme: str
    title: str
    angle: str


def _sign_rotation(corpus_dir: Path | None = None) -> list[str]:
    if corpus_dir is None:
        return list(FALLBACK_SIGNS)
    try:
        articles = load_corpus(corpus_dir)
    except FileNotFoundError:
        return list(FALLBACK_SIGNS)
    recent_titles = [item.title for item in articles if item.published >= date(2026, 6, 1)]
    counts = {sign: sum(1 for title in recent_titles if sign in title) for sign in SIGN_TERMS}
    missing_first = sorted(SIGN_TERMS, key=lambda sign: (counts[sign], SIGN_TERMS.index(sign)))
    return missing_first or list(FALLBACK_SIGNS)


def _choose_balanced_sign(
    *,
    signs: list[str],
    used_today: set[str],
    scheduled_counts: dict[str, int],
    theme: str,
    topic_scores: dict[tuple[str, str], float],
) -> str:
    candidates = [sign for sign in signs if sign not in used_today]
    lowest_count = min(scheduled_counts[sign] for sign in candidates)
    balanced = [sign for sign in candidates if scheduled_counts[sign] == lowest_count]
    order = {sign: index for index, sign in enumerate(signs)}
    return max(
        balanced,
        key=lambda sign: (topic_scores.get((sign, theme), 0.0), -order[sign]),
    )


def generate_calendar(
    *,
    days: int,
    daily: int,
    start: date,
    profile: str,
    corpus_dir: Path | None = DEFAULT_CORPUS_DIR,
    performance_entries: list[dict[str, object]] | None = None,
    performance_min_samples: int = 3,
) -> list[CalendarItem]:
    if days <= 0:
        raise ValueError("--days 必须大于 0")
    if daily <= 0:
        raise ValueError("--daily 必须大于 0")
    if profile != "anxia_short":
        raise ValueError("当前排期生成器只支持 --profile anxia_short")

    signs = _sign_rotation(corpus_dir)
    rotation = (start.toordinal() * daily) % len(signs)
    signs = signs[rotation:] + signs[:rotation]
    topic_scores = topic_performance_scores(
        list(performance_entries or []),
        min_samples=performance_min_samples,
    )
    month = MONTH_LABELS[(start.month - 1) % len(MONTH_LABELS)]
    items: list[CalendarItem] = []
    scheduled_counts = {sign: 0 for sign in signs}
    for day_offset in range(days):
        day = start + timedelta(days=day_offset)
        used_today: set[str] = set()
        for slot in range(daily):
            # Use the absolute date so separate one-day runs keep rotating all three themes.
            theme = THEMES[(day.toordinal() * daily + slot) % len(THEMES)]
            pool = TEMPLATE_POOLS[theme]
            template, variables = pool[(day_offset + slot) % len(pool)]
            sign = _choose_balanced_sign(
                signs=signs,
                used_today=used_today,
                scheduled_counts=scheduled_counts,
                theme=theme,
                topic_scores=topic_scores,
            )
            used_today.add(sign)
            scheduled_counts[sign] += 1
            values = {key: options[(day_offset + slot) % len(options)] for key, options in variables.items()}
            title = template.format(sign=sign, month=month, **values)
            angle = {
                "运势/提醒": "直接点出近期变化，再拆成生活、事业或情绪中的两个表现。",
                "关系/性格": "从一个可观察细节进入，解释这个星座为什么会靠近或退开。",
                "财运/贵人": "写机会来源和接住方式，保留期待感但避免确定收益承诺。",
            }[theme]
            items.append(CalendarItem(day, slot + 1, sign, theme, title, angle))
    return items


def format_calendar(items: list[CalendarItem]) -> str:
    lines = [
        "| 日期 | 序号 | 星座 | 主题 | 标题 | 写作角度 |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for item in items:
        lines.append(
            f"| {item.day.isoformat()} | {item.slot} | {item.sign} | "
            f"{item.theme} | {item.title} | {item.angle} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成安夏短文号每日选题排期")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--daily", type=int, default=DEFAULT_DAILY_SHORT_ARTICLES)
    parser.add_argument("--profile", default="anxia_short")
    parser.add_argument("--start", default=date.today().isoformat())
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--performance-log", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--performance-min-samples", type=int, default=3)
    args = parser.parse_args()
    try:
        start = date.fromisoformat(args.start)
        performance_entries = load_entries(args.performance_log)
        items = generate_calendar(
            days=args.days,
            daily=args.daily,
            start=start,
            profile=args.profile,
            corpus_dir=args.corpus_dir,
            performance_entries=performance_entries,
            performance_min_samples=args.performance_min_samples,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(format_calendar(items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
