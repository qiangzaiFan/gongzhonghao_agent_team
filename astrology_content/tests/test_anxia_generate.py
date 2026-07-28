from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from anxia_calendar import CalendarItem
from anxia_generate import (
    build_drafts,
    build_daily_fortune_drafts,
    daily_card_markdown_refs,
    daily_fortune_card_paths,
    hot_source_title_for_item,
    output_path,
    render_markdown,
    title_formula,
    write_daily_fortune_cards,
)
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
        self.assertTrue(all(draft.recent_conflict is None for draft in drafts))

    def test_builds_seven_original_daily_fortune_articles(self) -> None:
        drafts = build_daily_fortune_drafts(
            date(2026, 7, 28),
            days=7,
            slot=4,
        )

        self.assertEqual(len(drafts), 7)
        self.assertTrue(all(draft.recent_conflict is None for draft in drafts))
        self.assertEqual(drafts[0].title, "十二星座每日好运丨2026.07.28")
        self.assertTrue(all(draft.body.count("## ") == 4 for draft in drafts))
        self.assertTrue(all(len(draft.opening_candidates) == 2 for draft in drafts))
        self.assertTrue(all("先先" not in draft.body for draft in drafts))

        for draft in drafts:
            path = output_path(self.root, draft)
            path.write_text(render_markdown(draft), encoding="utf-8")
            result = validate_article(parse_article(path), profile="daily_fortune")
            self.assertEqual(result.errors, [])

    def test_daily_fortune_cards_are_written_and_validated(self) -> None:
        day = date(2026, 7, 28)
        draft = build_daily_fortune_drafts(day, days=1, slot=4)[0]
        article_dir = self.root / "articles"
        article_dir.mkdir()
        article_path = output_path(article_dir, draft)
        default_card_paths = daily_fortune_card_paths(
            day,
            asset_dir=self.root / "assets" / "daily_fortune_cards",
        )
        self.assertTrue(all(path.suffix == ".png" for path in default_card_paths.values()))
        card_paths = write_daily_fortune_cards(
            day,
            asset_dir=self.root / "assets" / "daily_fortune_cards",
            image_format="svg",
        )

        self.assertEqual(len(card_paths), 12)
        self.assertTrue(all(path.is_file() for path in card_paths.values()))
        self.assertIn("天秤座", card_paths["天秤"].read_text(encoding="utf-8"))

        article_path.write_text(
            render_markdown(
                draft,
                daily_card_images=daily_card_markdown_refs(card_paths, article_dir=article_dir),
            ),
            encoding="utf-8",
        )
        result = validate_article(parse_article(article_path), profile="daily_fortune")
        self.assertEqual(result.errors, [])
        self.assertEqual(result.metrics["image_count"], 12)

    def test_multi_day_drafts_rotate_bodies_and_keep_title_options(self) -> None:
        drafts = build_drafts(date(2026, 7, 26), 3, corpus_dir=None, days=7)
        self.assertEqual(len({draft.body for draft in drafts}), len(drafts))
        self.assertTrue(all(len(draft.title_candidates) >= 3 for draft in drafts))
        self.assertTrue(all(draft.title in draft.title_candidates for draft in drafts))
        self.assertTrue(all(len(draft.opening_candidates) == 2 for draft in drafts))
        self.assertTrue(
            all(draft.body.startswith(draft.opening_variant["text"]) for draft in drafts)
        )

    def test_recent_duplicate_automatically_switches_body_variant(self) -> None:
        baseline = build_drafts(date(2026, 7, 28), 3, corpus_dir=None)[0]
        drafts = build_drafts(
            date(2026, 7, 28),
            3,
            corpus_dir=None,
            recent_drafts=[("recent.md", baseline.body)],
        )

        self.assertNotEqual(drafts[0].body, baseline.body)
        self.assertNotEqual(drafts[0].body_variant["key"], baseline.body_variant["key"])
        self.assertIsNone(drafts[0].recent_conflict)

    def test_viral_safe_adds_stronger_hooks(self) -> None:
        drafts = build_drafts(date(2026, 7, 26), 3, corpus_dir=None, mode="viral-safe")
        self.assertTrue(any("！" in draft.title for draft in drafts))
        self.assertTrue(all("刷到接好运" in draft.body for draft in drafts))
        self.assertTrue(all("�" not in draft.title + draft.body for draft in drafts))

    def test_balanced_keeps_calendar_titles(self) -> None:
        drafts = build_drafts(date(2026, 7, 26), 3, corpus_dir=None, mode="balanced")
        self.assertEqual(drafts[0].title, drafts[0].item.title)

    def test_title_formula_respects_relationship_theme_before_keyword(self) -> None:
        self.assertEqual(
            title_formula("天蝎这辈子最该珍惜的一个贵人", "关系/性格"),
            "关系洞察型",
        )

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
