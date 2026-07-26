from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from anxia_calendar import CalendarItem
from anxia_generate import build_drafts, hot_source_title_for_item, output_path, render_markdown
from quality_gate import parse_article, validate_article


class AnxiaGenerateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_builds_three_valid_short_drafts(self) -> None:
        drafts = build_drafts(date(2026, 7, 26), 3, corpus_dir=None)
        self.assertEqual(len(drafts), 3)
        for draft in drafts:
            path = output_path(self.root, draft)
            path.write_text(render_markdown(draft), encoding="utf-8")
            result = validate_article(parse_article(path))
            self.assertEqual(result.errors, [])

    def test_builds_three_days_of_daily_three(self) -> None:
        drafts = build_drafts(date(2026, 7, 26), 3, corpus_dir=None, days=3)
        self.assertEqual(len(drafts), 9)
        self.assertEqual(len({draft.item.day for draft in drafts}), 3)

    def test_builds_seven_days_of_daily_three(self) -> None:
        drafts = build_drafts(date(2026, 7, 26), 3, corpus_dir=None, days=7)
        self.assertEqual(len(drafts), 21)
        self.assertEqual(len({draft.item.day for draft in drafts}), 7)

    def test_viral_safe_adds_stronger_hooks(self) -> None:
        drafts = build_drafts(date(2026, 7, 26), 3, corpus_dir=None, mode="viral-safe")
        self.assertTrue(any("！" in draft.title for draft in drafts))
        self.assertTrue(all("刷到接好运" in draft.body for draft in drafts))
        self.assertTrue(all("�" not in draft.title + draft.body for draft in drafts))

    def test_balanced_keeps_calendar_titles(self) -> None:
        drafts = build_drafts(date(2026, 7, 26), 3, corpus_dir=None, mode="balanced")
        self.assertEqual(drafts[0].title, drafts[0].item.title)

    def test_hot_source_can_reuse_repeated_title(self) -> None:
        title = "天蝎座7月一定会发生的三件喜事！"
        for index in range(2):
            (self.root / f"000{index + 1}_2026-07-2{index}_{title}_22474848{index}_1.md").write_text(
                "---\n"
                f"title: {title}\n"
                "---\n\n"
                "天蝎这段时间会看见新的变化。\n",
                encoding="utf-8",
            )
        item = CalendarItem(
            day=date(2026, 7, 26),
            slot=1,
            sign="天蝎",
            theme="运势/提醒",
            title="天蝎近期运势开始往上走了！",
            angle="",
        )
        self.assertEqual(hot_source_title_for_item(item, self.root, min_count=2), title)


if __name__ == "__main__":
    unittest.main()
