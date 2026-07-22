from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_detector
from daily_emotion_women import run_preflight


class EmotionAIDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.articles = self.root / "articles"
        self.reports = self.root / "reviews" / "auto"
        self.articles.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_article(self, relative: str, body: str = "这是一段待检测的情感文章正文。") -> Path:
        path = self.articles / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\ntitle: 测试文章\n---\n\n{body}\n", encoding="utf-8")
        return path

    def test_article_edit_invalidates_saved_report(self) -> None:
        article = self.write_article("draft.md")
        report_path = self.reports / "draft.json"
        report_path.parent.mkdir(parents=True)
        report_path.write_text(
            json.dumps(
                {
                    "article_sha256": hashlib.sha256(article.read_bytes()).hexdigest(),
                    "model": ai_detector.DEFAULT_MODEL,
                    "thresholds": {"human_min": 80.0, "ai_max": 10.0},
                    "ratios": {"human": 100.0, "suspected": 0.0, "ai": 0.0},
                    "passed": True,
                }
            ),
            encoding="utf-8",
        )
        current = ai_detector.read_current_report(
            article,
            report_path,
            model=ai_detector.DEFAULT_MODEL,
            human_min=80.0,
            ai_max=10.0,
        )
        self.assertIsNotNone(current)

        article.write_text(article.read_text(encoding="utf-8") + "实质修改。\n", encoding="utf-8")
        stale = ai_detector.read_current_report(
            article,
            report_path,
            model=ai_detector.DEFAULT_MODEL,
            human_min=80.0,
            ai_max=10.0,
        )
        self.assertIsNone(stale)

    def test_report_path_follows_article_relative_path(self) -> None:
        article = self.write_article("nested/draft.md")
        with patch.object(ai_detector, "ARTICLES_DIR", self.articles), patch.object(
            ai_detector, "REPORT_DIR", self.reports
        ):
            self.assertEqual(
                ai_detector.default_report_path(article),
                self.reports / "nested" / "draft.json",
            )

    @patch("daily_emotion_women.subprocess.run")
    def test_main_preflight_includes_ai_detector(self, mocked_run) -> None:
        mocked_run.return_value = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
        article = self.write_article("draft.md")
        ok, _output = run_preflight(article)
        self.assertTrue(ok)
        scripts = [Path(call.args[0][1]).name for call in mocked_run.call_args_list]
        self.assertEqual(
            scripts,
            ["validate_article_images.py", "quality_gate.py", "ai_detector.py"],
        )


if __name__ == "__main__":
    unittest.main()
