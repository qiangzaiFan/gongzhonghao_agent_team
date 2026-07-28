from __future__ import annotations

import unittest
from collections import Counter, defaultdict
from datetime import date

from anxia_calendar import generate_calendar


class AnxiaCalendarTests(unittest.TestCase):
    def test_seven_days_daily_three_generates_twenty_one_items(self) -> None:
        items = generate_calendar(
            days=7,
            daily=3,
            start=date(2026, 7, 24),
            profile="anxia_short",
            corpus_dir=None,
        )
        self.assertEqual(len(items), 21)

    def test_every_day_has_three_items_and_mixed_themes(self) -> None:
        items = generate_calendar(
            days=7,
            daily=3,
            start=date(2026, 7, 24),
            profile="anxia_short",
            corpus_dir=None,
        )
        by_day: defaultdict[date, list[str]] = defaultdict(list)
        for item in items:
            by_day[item.day].append(item.theme)
        self.assertTrue(all(len(themes) == 3 for themes in by_day.values()))
        self.assertTrue(all(len(set(themes)) > 1 for themes in by_day.values()))

    def test_signs_are_balanced(self) -> None:
        items = generate_calendar(
            days=7,
            daily=3,
            start=date(2026, 7, 24),
            profile="anxia_short",
            corpus_dir=None,
        )
        counts = Counter(item.sign for item in items)
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_reliable_topic_performance_prioritizes_matching_sign(self) -> None:
        entries = [
            {
                "sign": "天蝎",
                "theme": "运势/提醒",
                "read_rate": 0.42,
                "engagement_rate": 0.18,
            }
            for _ in range(3)
        ]
        items = generate_calendar(
            days=1,
            daily=3,
            start=date(2026, 7, 28),
            profile="anxia_short",
            corpus_dir=None,
            performance_entries=entries,
        )

        self.assertEqual(items[0].theme, "运势/提醒")
        self.assertEqual(items[0].sign, "天蝎")

    def test_single_day_runs_rotate_sign_groups_by_date(self) -> None:
        first_day = generate_calendar(
            days=1,
            daily=3,
            start=date(2026, 7, 28),
            profile="anxia_short",
            corpus_dir=None,
        )
        next_day = generate_calendar(
            days=1,
            daily=3,
            start=date(2026, 7, 29),
            profile="anxia_short",
            corpus_dir=None,
        )

        self.assertFalse({item.sign for item in first_day} & {item.sign for item in next_day})


if __name__ == "__main__":
    unittest.main()
