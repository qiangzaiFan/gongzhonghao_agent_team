import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import publish_existing_article as publisher


class PublishExistingArticleTests(unittest.TestCase):
    def test_default_author_is_xiaye(self) -> None:
        self.assertEqual(publisher.DEFAULT_AUTHOR, "夏野星座")

    def test_weekly_article_uses_weekly_profile(self) -> None:
        article = Path("20260810_05_十二星座一周运势丨08-10-08-16.md")

        self.assertEqual(publisher.profile_for(article), "weekly_fortune")

    def test_weekly_table_styles_remove_default_borders(self) -> None:
        self.assertIn("border:0", publisher.WEEKLY_CELL_STYLE)
        self.assertIn("table-layout:fixed", publisher.WEEKLY_TABLE_STYLE)
        self.assertIn("width:100%", publisher.WEEKLY_TABLE_STYLE)

    def test_publish_history_records_supplied_author(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            article = root / "article.md"
            history = root / "publish_history.jsonl"
            article.write_text("---\ntitle: 测试文章\n---\n\n正文\n", encoding="utf-8")

            with patch.object(publisher, "PUBLISH_HISTORY", history):
                publisher.record(article, "agentera-mint", "media-id", "夏野星座")

            payload = json.loads(history.read_text(encoding="utf-8"))
            self.assertEqual(payload["account"], "夏野星座")
            self.assertEqual(payload["author"], "夏野星座")


if __name__ == "__main__":
    unittest.main()
