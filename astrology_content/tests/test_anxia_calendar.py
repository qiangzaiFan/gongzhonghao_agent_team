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


if __name__ == "__main__":
    unittest.main()
