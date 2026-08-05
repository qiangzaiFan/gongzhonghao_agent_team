from __future__ import annotations

import json
import re
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

import baitao_weekly as weekly
from baitao_weekly import (
    CARD_BODY_FIELDS,
    CARD_SIZE,
    MIN_CARD_CJK,
    SIGNS,
    build_weekly_draft,
    load_weekly_events,
    write_weekly_package,
)
from baitao_weekly_analyze import summarize
from quality_gate import image_size, parse_article, validate_article


class BaiTaoWeeklyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.events_path = self.root / "events.json"
        self.events_path.write_text(
            json.dumps(
                {
                    "week_start": "2026-08-10",
                    "source_note": "测试数据已由编辑复核，不用于实际发布。",
                    "events": [
                        {
                            "date": "2026-08-10",
                            "name": "工作节奏变化",
                            "summary": "适合梳理任务边界，确认本周最需要优先完成的事。",
                            "detail": "工作上可以先将任务拆分，再核对时间和可用资源。涉及多人协作时，提前说清交付标准能减少返工。",
                            "focus": "work",
                            "affected_signs": ["白羊", "摩羯"],
                        },
                        {
                            "date": "2026-08-13",
                            "name": "关系沟通变化",
                            "summary": "适合重新确认彼此需求，不用为小分歧反复猜测。",
                            "detail": "沟通时先说清实际情况，再表达自己的感受和期待。对重要安排留下明确回复，比默认对方明白更稳妥。",
                            "focus": "relationship",
                            "affected_signs": ["巨蟹", "天秤"],
                        },
                        {
                            "date": "2026-08-15",
                            "name": "财务整理变化",
                            "summary": "适合核对支出、回款和续费，把模糊的数字重新理清。",
                            "detail": "这个节点更适合查漏补缺，不需要因为一时优惠临时改变计划。涉及合作收益时，先确认结算周期和条件。",
                            "focus": "finance",
                            "affected_signs": ["金牛", "天蝎"],
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_builds_distinct_cards_for_all_signs(self) -> None:
        week_start, events, _ = load_weekly_events(self.events_path)
        draft = build_weekly_draft(week_start, events)

        self.assertEqual(len(draft.cards), 12)
        self.assertEqual({card.sign for card in draft.cards}, set(SIGNS))
        self.assertEqual(len({json.dumps(asdict(card), ensure_ascii=False) for card in draft.cards}), 12)
        self.assertTrue(all(card.single != card.partnered for card in draft.cards))
        opening_patterns = {
            re.sub(r"(?:白羊|金牛|双子|巨蟹|狮子|处女|天秤|天蝎|射手|摩羯|水瓶|双鱼)座", "星座", card.overall.split("。", 1)[0])
            for card in draft.cards
        }
        self.assertGreaterEqual(len(opening_patterns), 4)
        for card in draft.cards:
            body = "".join(str(getattr(card, field)) for field in CARD_BODY_FIELDS)
            self.assertGreaterEqual(sum("\u4e00" <= char <= "\u9fff" for char in body), MIN_CARD_CJK)
            for field in ("single", "partnered", "study", "work", "finance", "health"):
                self.assertTrue(any(event.name in getattr(card, field) for event in events))

    def test_writes_valid_article_and_fourteen_local_images(self) -> None:
        week_start, events, source_note = load_weekly_events(self.events_path)
        draft = build_weekly_draft(week_start, events)
        article, review = write_weekly_package(
            draft,
            article_dir=self.root / "articles",
            asset_dir=self.root / "assets" / "weekly_fortune",
            review_dir=self.root / "reviews",
            source_note=source_note,
        )

        result = validate_article(parse_article(article), profile="weekly_fortune")
        payload = json.loads(review.read_text(encoding="utf-8"))

        self.assertEqual(result.errors, [])
        self.assertEqual(result.metrics["image_count"], 14)
        self.assertEqual(len(payload["cards"]), 12)
        article_text = article.read_text(encoding="utf-8")
        self.assertEqual(article_text.count("**点击查看大图**"), 4)
        self.assertEqual(article_text.count("| :---: | :---: | :---: |"), 4)
        self.assertEqual(
            image_size(self.root / "assets" / "weekly_fortune" / "20260810" / "cards" / "白羊座.png"),
            CARD_SIZE,
        )

    def test_rejects_unreviewed_event_file(self) -> None:
        payload = json.loads(self.events_path.read_text(encoding="utf-8"))
        payload["source_note"] = "未复核"
        self.events_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "source_note"):
            load_weekly_events(self.events_path)

    def test_wrap_does_not_start_line_with_closing_punctuation(self) -> None:
        font = weekly._font(34)
        width = font.getlength("测试文本") + 0.1

        lines = weekly._wrap("测试文本。后续", font, width)

        self.assertFalse(any(line.startswith("。") for line in lines))
        self.assertEqual(lines[0], "测试文本。")

    def test_analyzer_reports_recent_structure(self) -> None:
        corpus = self.root / "corpus"
        corpus.mkdir()
        sample = "\n".join(
            (
                "# 十二星座一周运势",
                "① 重点星象",
                "![](/one.png)",
                "![](/two.png)",
                "本周提醒内容。",
            )
        )
        (corpus / "001 sample.md").write_text(sample, encoding="utf-8")
        (corpus / "002 sample.md").write_text(sample + "\n补充。", encoding="utf-8")

        report = summarize(corpus, recent=1)

        self.assertIn("全量 2 篇", report)
        self.assertIn("本次分析 1 篇", report)
        self.assertIn("图片：中位 2", report)


if __name__ == "__main__":
    unittest.main()
