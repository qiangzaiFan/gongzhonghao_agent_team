from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from anxia_calendar import CalendarItem
from content_record import load_record, validate_record, write_generated_record


class ContentRecordTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_generated_record_binds_article_and_editorial_choices(self) -> None:
        item = CalendarItem(
            day=date(2026, 7, 28),
            slot=2,
            sign="天秤",
            theme="关系/性格",
            title="天秤别再替沉默找理由",
            angle="从回应是否对等切入",
        )
        record_path = write_generated_record(
            self.article,
            item=item,
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
            source_dir=None,
            record_dir=self.root / "records",
        )

        self.assertEqual(validate_record(self.article, record_path), [])
        record = load_record(record_path)
        self.assertEqual(len(record["distribution"]["title"]["variants"]), 3)
        self.assertEqual(len(record["distribution"]["opening"]["variants"]), 2)
        self.assertEqual(
            record["distribution"]["title"]["selected_key"],
            "title-1",
        )

    def test_article_change_invalidates_record(self) -> None:
        item = CalendarItem(
            day=date(2026, 7, 28),
            slot=2,
            sign="天秤",
            theme="关系/性格",
            title="天秤别再替沉默找理由",
            angle="从回应是否对等切入",
        )
        record_path = write_generated_record(
            self.article,
            item=item,
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
            source_dir=None,
            record_dir=self.root / "records",
        )
        self.article.write_text(self.article.read_text(encoding="utf-8") + "\n多一段新内容。\n", encoding="utf-8")

        errors = validate_record(self.article, record_path)

        self.assertTrue(any("已过期" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
