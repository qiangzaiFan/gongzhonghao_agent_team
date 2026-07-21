from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_detector import article_digest, validate_report
from zhuque_gate import latest_errors


class DetectionGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.article = self.root / "article.md"
        self.article.write_text("---\ntitle: 测试\n---\n正文\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_current_automatic_report_passes(self) -> None:
        report = self.root / "auto.json"
        report.write_text(
            json.dumps(
                {
                    "article_sha256": article_digest(self.article),
                    "passed": True,
                    "ratios": {"human": 90, "suspected": 5, "ai": 5},
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(validate_report(self.article, report), [])

    def test_stale_automatic_report_is_rejected(self) -> None:
        report = self.root / "auto.json"
        report.write_text(
            json.dumps({"article_sha256": "old", "passed": True, "ratios": {}}),
            encoding="utf-8",
        )
        self.assertTrue(any("已过期" in item for item in validate_report(self.article, report)))

    def test_optional_zhuque_record_checks_thresholds_and_proof(self) -> None:
        proof = self.root / "zhuque.png"
        proof.write_bytes(b"proof")
        record = self.root / "zhuque.json"
        record.write_text(
            json.dumps(
                {
                    "rounds": [
                        {
                            "human": 84,
                            "suspected": 9,
                            "ai": 7,
                            "report": str(proof),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(latest_errors(record), [])


if __name__ == "__main__":
    unittest.main()
