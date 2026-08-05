from __future__ import annotations

import base64
import tempfile
import struct
import unittest
from datetime import date
from pathlib import Path

from anxia_calendar import CalendarItem
from anxia_generate import (
    build_drafts,
    build_daily_fortune_card,
    build_daily_fortune_drafts,
    daily_card_markdown_refs,
    daily_card_theme,
    daily_fortune_card_paths,
    daily_fortune_cover_content,
    daily_fortune_cover_path,
    daily_fortune_follow_path,
    hot_source_title_for_item,
    output_path,
    pet_cover_markdown_ref,
    pet_cover_path,
    render_body_with_variant,
    render_daily_fortune_card_svg,
    render_daily_fortune_cover_svg,
    render_markdown,
    title_formula,
    title_pattern,
    title_variants_for_item,
    write_daily_fortune_cards,
    write_daily_fortune_follow,
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

    def test_short_draft_can_include_pet_cover_reference(self) -> None:
        draft = build_drafts(date(2026, 7, 26), 1, corpus_dir=None)[0]
        article_dir = self.root / "articles"
        article_dir.mkdir()
        cover_path = pet_cover_path(self.root / "assets" / "pet_covers", draft)
        content = render_markdown(
            draft,
            pet_cover_image=pet_cover_markdown_ref(cover_path, article_dir=article_dir),
        )

        self.assertIn("治愈系萌宠封面", content)
        self.assertIn("../assets/pet_covers/", content)
        self.assertEqual(content.count("!["), 1)

    def test_builds_three_days_of_daily_three(self) -> None:
        drafts = build_drafts(date(2026, 7, 26), 3, corpus_dir=None, days=3)
        self.assertEqual(len(drafts), 9)
        self.assertEqual(len({draft.item.day for draft in drafts}), 3)

    def test_body_variant_fulfills_selected_title(self) -> None:
        cases = (
            ("运势/提醒", "射手座下半年躲不掉的三大转折", "three-areas", "三处变化"),
            ("关系/性格", "能让射手座彻底清醒的两种关系", "draining-patterns", "两种"),
            ("财运/贵人", "射手座本月最容易忽略的一个贵人", "resource-person", "贵人"),
        )
        for theme, title, expected_variant, expected_text in cases:
            with self.subTest(theme=theme):
                item = CalendarItem(
                    day=date(2026, 8, 10),
                    slot=0,
                    sign="射手",
                    theme=theme,
                    title=title,
                    angle="原创测试角度",
                )
                body, variant, _ = render_body_with_variant(
                    item,
                    selected_title=title,
                )
                self.assertEqual(variant["key"], expected_variant)
                self.assertIn(expected_text, body)

    def test_daily_two_batch_contains_all_non_daily_themes(self) -> None:
        drafts = build_drafts(date(2026, 8, 10), 2, corpus_dir=None, days=3)

        self.assertEqual(
            {draft.item.theme for draft in drafts},
            {"运势/提醒", "关系/性格", "财运/贵人"},
        )
        finance_bodies = [
            draft.body for draft in drafts if draft.item.theme == "财运/贵人"
        ]
        self.assertTrue(finance_bodies)
        self.assertTrue(all(any(term in body for term in ("财运", "贵人", "事业", "机会")) for body in finance_bodies))

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

    def test_daily_fortune_cover_uses_xiaye_design(self) -> None:
        day = date(2026, 7, 28)
        svg_text = render_daily_fortune_cover_svg(day, card_theme="mint")
        focus, top_cards = daily_fortune_cover_content(day)

        self.assertIn('width="900"', svg_text)
        self.assertIn('height="380"', svg_text)
        self.assertIn("夏野日运", svg_text)
        self.assertIn("十二星座每日好运", svg_text)
        self.assertIn("今日好运", svg_text)
        self.assertIn(f"关键词 · {focus}", svg_text)
        self.assertIn("好运前三", svg_text)
        self.assertTrue(all(card.sign in svg_text for card in top_cards))
        self.assertTrue(all(f"{card.score}分" in svg_text for card in top_cards))
        self.assertNotIn("coverStripe", svg_text)
        self.assertNotIn("火土风水", svg_text)

    def test_daily_fortune_cover_ranking_is_score_ordered(self) -> None:
        _, top_cards = daily_fortune_cover_content(date(2026, 8, 5))

        self.assertEqual([card.sign for card in top_cards], ["天秤", "金牛", "水瓶"])
        self.assertEqual([card.score for card in top_cards], sorted((card.score for card in top_cards), reverse=True))

    def test_daily_fortune_cover_is_first_image(self) -> None:
        day = date(2026, 7, 28)
        draft = build_daily_fortune_drafts(day, days=1, slot=4)[0]
        article_dir = self.root / "articles"
        article_dir.mkdir()
        cover_ref = daily_fortune_cover_path(
            day,
            asset_dir=self.root / "assets" / "daily_fortune_covers",
        )
        card_paths = daily_fortune_card_paths(
            day,
            asset_dir=self.root / "assets" / "daily_fortune_cards",
            image_format="svg",
        )
        content = render_markdown(
            draft,
            daily_fortune_cover_image=str(cover_ref.relative_to(article_dir.parent)).replace("\\", "/"),
            daily_card_images=daily_card_markdown_refs(card_paths, article_dir=article_dir),
        )

        self.assertIn("![夏野日运封面]", content.splitlines()[4])
        self.assertLess(content.index("夏野日运封面"), content.index("白羊座每日好运卡"))
        self.assertEqual(content.count("!["), 13)

    def test_daily_fortune_follow_guide_is_last_image(self) -> None:
        day = date(2026, 7, 28)
        draft = build_daily_fortune_drafts(day, days=1, slot=3)[0]
        article_dir = self.root / "articles"
        article_dir.mkdir()
        follow_path = write_daily_fortune_follow(
            asset_dir=self.root / "assets" / "daily_fortune_follow"
        )
        follow_ref = str(follow_path.relative_to(article_dir.parent)).replace("\\", "/")
        content = render_markdown(draft, daily_fortune_follow_image=follow_ref)

        self.assertEqual(follow_path, daily_fortune_follow_path(asset_dir=follow_path.parent))
        self.assertTrue(content.rstrip().endswith(f"![每日好运关注指引]({follow_ref})"))
        header = follow_path.read_bytes()[:24]
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", header[16:24]), (1800, 720))

    def test_daily_fortune_pink_card_theme_uses_separate_asset_dir(self) -> None:
        day = date(2026, 7, 28)
        default_paths = daily_fortune_card_paths(
            day,
            asset_dir=self.root / "assets" / "daily_fortune_cards",
            image_format="svg",
        )
        self.assertIn("20260728", str(default_paths["天秤"]))
        self.assertNotIn("20260728_mint", str(default_paths["天秤"]))

        pink_paths = daily_fortune_card_paths(
            day,
            asset_dir=self.root / "assets" / "daily_fortune_cards",
            image_format="svg",
            card_theme="pink",
        )
        self.assertIn("20260728_pink", str(pink_paths["天秤"]))

        card_paths = write_daily_fortune_cards(
            day,
            asset_dir=self.root / "assets" / "daily_fortune_cards",
            image_format="svg",
            card_theme="pink",
        )
        svg_text = card_paths["天秤"].read_text(encoding="utf-8")
        self.assertIn(daily_card_theme("pink").frame_start, svg_text)
        self.assertIn("天秤座", svg_text)

        default_svg = render_daily_fortune_card_svg(build_daily_fortune_card("天秤", day), day)
        self.assertIn(daily_card_theme("mint").frame_start, default_svg)

    def test_daily_fortune_card_embeds_character_png(self) -> None:
        character_dir = self.root / "zodiac_characters"
        character_dir.mkdir()
        image_bytes = b"test-png-bytes"
        (character_dir / "\u767d\u7f8a\u5ea7.png").write_bytes(image_bytes)

        svg_text = render_daily_fortune_card_svg(
            build_daily_fortune_card("\u767d\u7f8a", date(2026, 7, 28)),
            date(2026, 7, 28),
            character_asset_dir=character_dir,
        )

        encoded = base64.b64encode(image_bytes).decode("ascii")
        self.assertIn(f"data:image/png;base64,{encoded}", svg_text)
        self.assertIn('x="114" y="220"', svg_text)
        self.assertIn('preserveAspectRatio="xMidYMid slice"', svg_text)
        self.assertIn('clip-path="url(#avatarPanelClip)"', svg_text)

    def test_cairosvg_png_renderer_writes_full_size_card(self) -> None:
        try:
            import cairosvg  # noqa: F401
        except (ImportError, OSError):
            self.skipTest("CairoSVG is not available")

        day = date(2026, 7, 28)
        card_paths = write_daily_fortune_cards(
            day,
            asset_dir=self.root / "assets" / "daily_fortune_cards",
            image_format="png",
            card_theme="mint",
            png_renderer="cairosvg",
        )
        image_path = card_paths["天秤"]
        self.assertTrue(image_path.is_file())
        header = image_path.read_bytes()[:24]
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", header[16:24])
        self.assertEqual((width, height), (960, 1280))

    def test_native_png_renderer_writes_full_size_card(self) -> None:
        day = date(2026, 7, 28)
        card_paths = write_daily_fortune_cards(
            day,
            asset_dir=self.root / "assets" / "daily_fortune_cards",
            image_format="png",
            card_theme="mint",
        )

        self.assertEqual(len(card_paths), 12)
        image_path = card_paths["天秤"]
        header = image_path.read_bytes()[:24]
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", header[16:24])
        self.assertEqual((width, height), (960, 1280))

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
        self.assertIn("事业信号", drafts[0].title)
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
            "关系助力型",
        )

    def test_title_candidates_stay_aligned_with_body_variant(self) -> None:
        item = CalendarItem(
            day=date(2026, 8, 12),
            slot=0,
            sign="天蝎",
            theme="财运/贵人",
            title="天蝎座本月最容易忽略的一个贵人！",
            angle="贵人带来信息和资源",
        )
        variants = title_variants_for_item(
            item,
            item.title,
            body_variant_key="resource-person",
        )

        self.assertEqual(len(variants), 4)
        self.assertTrue(
            all("贵人" in variant["text"] or "关键人物" in variant["text"] for variant in variants)
        )
        self.assertEqual({variant["formula"] for variant in variants}, {"贵人资源型"})
        self.assertGreaterEqual(len({variant["pattern"] for variant in variants}), 2)

    def test_title_pattern_separates_click_hooks(self) -> None:
        self.assertEqual(title_pattern("天蝎座本月必须警惕的一个信号！"), "风险提醒型")
        self.assertEqual(title_pattern("天蝎座近期有三个进账线索！"), "数字清单型")
        self.assertEqual(title_pattern("天蝎座的整体运势慢慢走高！"), "趋势预告型")

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
