#!/usr/bin/env python3
"""Generate a stable Anxia-style daily topic calendar."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from anxia_corpus import DEFAULT_CORPUS_DIR, SIGN_TERMS, load_corpus


TEMPLATE_POOLS = {
    "运势/提醒": (
        ("{sign}本月必须警惕的一个{risk}", {"risk": ("旧习惯", "情绪消耗", "社交误区")}),
        ("{sign}下半年躲不掉的三大{change}", {"change": ("状态转折", "关系变化", "财务提醒")}),
        ("{month}，给{sign}一个{reminder}", {"reminder": ("重要提醒", "人际提醒", "节奏提醒")}),
        ("{sign}，{stage}整体运势开始走高", {"stage": ("下半年", "本月", "这段时间")}),
    ),
    "关系/性格": (
        ("能让{sign}{reaction}的{obj}", {"reaction": ("慢慢拉开距离", "瞬间清醒", "重新靠近"), "obj": ("一个细节", "一种态度", "一段关系")}),
        ("{sign}这辈子最该珍惜的{asset}", {"asset": ("一种关系", "一个贵人", "一类真心")}),
    ),
    "财运/贵人": (
        ("{sign}，{month}有一个{opportunity}正在路上", {"opportunity": ("新机会", "贵人信号", "收入变化")}),
        ("{sign}最容易忽略的一个{asset}", {"asset": ("贵人", "机会", "财务突破口")}),
    ),
}
THEMES = tuple(TEMPLATE_POOLS)
FALLBACK_SIGNS = SIGN_TERMS
MONTH_LABELS = tuple(f"{month}月" for month in range(1, 13))


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


def generate_calendar(
    *,
    days: int,
    daily: int,
    start: date,
    profile: str,
    corpus_dir: Path | None = DEFAULT_CORPUS_DIR,
) -> list[CalendarItem]:
    if days <= 0:
        raise ValueError("--days 必须大于 0")
    if daily <= 0:
        raise ValueError("--daily 必须大于 0")
    if profile != "anxia_short":
        raise ValueError("当前排期生成器只支持 --profile anxia_short")

    signs = _sign_rotation(corpus_dir)
    month = MONTH_LABELS[(start.month - 1) % len(MONTH_LABELS)]
    items: list[CalendarItem] = []
    sign_index = 0
    for day_offset in range(days):
        day = start + timedelta(days=day_offset)
        used_today: set[str] = set()
        for slot in range(daily):
            theme = THEMES[slot % len(THEMES)]
            pool = TEMPLATE_POOLS[theme]
            template, variables = pool[(day_offset + slot) % len(pool)]
            sign = signs[sign_index % len(signs)]
            while sign in used_today and len(used_today) < len(signs):
                sign_index += 1
                sign = signs[sign_index % len(signs)]
            used_today.add(sign)
            sign_index += 1
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
    parser.add_argument("--daily", type=int, default=3)
    parser.add_argument("--profile", default="anxia_short")
    parser.add_argument("--start", default=date.today().isoformat())
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    args = parser.parse_args()
    try:
        start = date.fromisoformat(args.start)
        items = generate_calendar(
            days=args.days,
            daily=args.daily,
            start=start,
            profile=args.profile,
            corpus_dir=args.corpus_dir,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(format_calendar(items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
