from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from anxia_calendar import CalendarItem
from content_record import write_generated_record
from performance_tracker import (
    append_entry,
    breakout_entries,
    build_entry,
    format_postmortem,
    format_report,
    load_entries,
    topic_performance_scores,
)


class PerformanceTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.article = self.root / "article.md"
        self.article.write_text(
            "---\n"
            "title: 天秤别再替沉默找理由\n"
            "---\n\n"
            "天秤最近要把注意力放回真实回应。\n\n"
            "别替沉默找理由。\n\n"
            "把感受放回优先级。\n",
            encoding="utf-8",
        )
        self.record = write_generated_record(
            self.article,
            item=CalendarItem(
                day=date(2026, 7, 28),
                slot=2,
                sign="天秤",
                theme="关系/性格",
                title="天秤别再替沉默找理由",
                angle="从回应是否对等切入",
            ),
            title_candidates=(
                "天秤别再替沉默找理由",
                "天秤最累的关系，是总要自己解释",
                "天秤该把感受放回优先级了",
            ),
            body_variant={
                "key": "stop-explaining",
                "hook": "总是你先解释和缓和",
                "focus": "看真实回应",
                "closing": "别再替沉默找借口",
            },
            source_dir=self.root / "corpus",
            record_dir=self.root / "records",
            title_variants=(
                {
                    "key": "title-1",
                    "text": "天秤别再替沉默找理由",
                    "formula": "关系洞察型",
                    "pattern": "风险提醒型",
                },
                {
                    "key": "title-2",
                    "text": "天秤最累的关系，是总要自己解释",
                    "formula": "关系洞察型",
                    "pattern": "场景判断型",
                },
                {
                    "key": "title-3",
                    "text": "天秤该把感受放回优先级了",
                    "formula": "提醒型",
                    "pattern": "场景判断型",
                },
            ),
            opening_variants=(
                {
                    "key": "direct-alert",
                    "text": "天秤最近在关系里要留意：总是你先解释和缓和。",
                    "label": "直接提醒",
                },
                {
                    "key": "detail-observation",
                    "text": "天秤这段时间会慢慢看清：总是你先解释和缓和，你的感受已经在给答案。",
                    "label": "细节观察",
                },
            ),
            selected_title_variant="title-1",
            selected_opening_variant="direct-alert",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_records_rates_and_reports_by_editorial_dimensions(self) -> None:
        entry = build_entry(
            self.article,
            self.record,
            published_at="2026-07-28T20:00:00+08:00",
            impressions=1000,
            reads=250,
            likes=20,
            shares=5,
            comments=3,
            follows=2,
            title_variant="title-2",
            opening_variant="detail-observation",
        )
        log = self.root / "performance.jsonl"
        append_entry(log, entry)

        entries = load_entries(log)
        report = format_report(entries)

        self.assertEqual(entries[0]["read_rate"], 0.25)
        self.assertEqual(entries[0]["engagement_rate"], 0.12)
        self.assertIn("关系/性格", report)
        self.assertIn("天秤", report)
        self.assertIn("stop-explaining", report)
        self.assertEqual(entries[0]["title_variant"], "title-2")
        self.assertEqual(entries[0]["title_pattern"], "场景判断型")
        self.assertEqual(entries[0]["opening_variant"], "detail-observation")
        self.assertEqual(entries[0]["published_title"], "天秤最累的关系，是总要自己解释")
        self.assertIn("标题公式", report)
        self.assertIn("开头版本", report)
        self.assertIn("样本不足", report)

    def test_title_report_uses_weighted_read_rate_and_click_order(self) -> None:
        entries = [
            {
                "title_formula": "高阅读率型",
                "impressions": 100,
                "reads": 50,
                "likes": 0,
                "shares": 0,
                "comments": 0,
                "follows": 0,
                "read_rate": 0.5,
                "engagement_rate": 0.0,
            },
            {
                "title_formula": "高阅读率型",
                "impressions": 900,
                "reads": 90,
                "likes": 0,
                "shares": 0,
                "comments": 0,
                "follows": 0,
                "read_rate": 0.1,
                "engagement_rate": 0.0,
            },
            {
                "title_formula": "高互动率型",
                "impressions": 1000,
                "reads": 100,
                "likes": 50,
                "shares": 0,
                "comments": 0,
                "follows": 0,
                "read_rate": 0.1,
                "engagement_rate": 0.5,
            },
        ]

        report = format_report(entries)
        title_section = report.split("## 标题公式表现", 1)[1].split("## 标题版本表现", 1)[0]

        self.assertLess(title_section.index("高阅读率型"), title_section.index("高互动率型"))
        self.assertIn("阅读率 14.00%", title_section)

    def test_topic_scores_need_enough_samples(self) -> None:
        entry = {
            "sign": "天秤",
            "theme": "关系/性格",
            "read_rate": 0.3,
            "engagement_rate": 0.1,
        }

        self.assertEqual(topic_performance_scores([entry, entry]), {})
        self.assertIn(
            ("天秤", "关系/性格"),
            topic_performance_scores([entry, entry, entry]),
        )

    def test_postmortem_selects_only_entries_well_above_baseline(self) -> None:
        regular = {
            "read_rate": 0.10,
            "engagement_rate": 0.10,
            "sign": "天秤",
            "theme": "关系/性格",
            "body_variant": "stop-explaining",
            "title_variant": "title-1",
            "title_formula": "关系洞察型",
            "opening_variant": "direct-alert",
            "opening_label": "直接提醒",
            "published_title": "常规表现标题",
            "published_at": "2026-07-28T20:00:00+08:00",
        }
        high = {
            **regular,
            "read_rate": 0.35,
            "engagement_rate": 0.40,
            "published_title": "高表现标题",
            "title_variant": "title-2",
            "opening_variant": "detail-observation",
            "opening_label": "细节观察",
        }

        baseline, threshold, selected = breakout_entries(
            [regular, regular, regular, regular, high],
            min_samples=5,
            multiplier=1.5,
        )
        report = format_postmortem(
            [regular, regular, regular, regular, high],
            min_samples=5,
            multiplier=1.5,
        )

        self.assertAlmostEqual(baseline or 0.0, 0.10)
        self.assertAlmostEqual(threshold or 0.0, 0.15)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["published_title"], "高表现标题")
        self.assertIn("高表现标题", report)
        self.assertIn("复盘卡 1", report)


if __name__ == "__main__":
    unittest.main()
