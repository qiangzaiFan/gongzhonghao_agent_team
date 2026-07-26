from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from anxia_analyze import build_report
from anxia_corpus import load_corpus


class AnxiaAnalyzeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "安夏星座.md").write_text("# index\n", encoding="utf-8")
        (self.root / "安夏星座文章索引.md").write_text("# index\n", encoding="utf-8")
        for index in range(1, 4):
            (self.root / f"000{index}_2026-07-23_白羊座7月财运突破_{2247485500 + index}_{index}.md").write_text(
                "---\n"
                "title: 白羊座7月财运突破\n"
                "---\n\n"
                "# 白羊座7月财运突破\n\n"
                "- 公众号文章：[[安夏星座]]\n"
                "- 发布时间：2026-07-23\n\n"
                "白羊这段时间有机会看见财务变化。\n\n"
                "稳住节奏，愿你接住机会。\n",
                encoding="utf-8",
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_load_corpus_excludes_index_files(self) -> None:
        self.assertEqual(len(load_corpus(self.root)), 3)

    def test_report_contains_daily_count_and_length_bucket(self) -> None:
        report = build_report(self.root, date(2026, 6, 1))
        self.assertIn("- 全量文章：3", report)
        self.assertIn("- 3 篇/天：1 天", report)
        self.assertIn("- <120：3", report)


if __name__ == "__main__":
    unittest.main()
