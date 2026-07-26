from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_detector import ANXIA_SHORT_MIN_TOTAL_CHARS, article_chunks, article_digest, validate_report
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
                    "thresholds": {"human_min": 90, "ai_max": 10},
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
            json.dumps(
                {
                    "article_sha256": "old",
                    "thresholds": {"human_min": 90, "ai_max": 10},
                    "passed": True,
                    "ratios": {},
                }
            ),
            encoding="utf-8",
        )
        self.assertTrue(any("已过期" in item for item in validate_report(self.article, report)))

    def test_old_automatic_report_threshold_is_rejected(self) -> None:
        report = self.root / "old_threshold.json"
        report.write_text(
            json.dumps(
                {
                    "article_sha256": article_digest(self.article),
                    "thresholds": {"human_min": 80, "ai_max": 10},
                    "passed": True,
                    "ratios": {"human": 85, "suspected": 10, "ai": 5},
                }
            ),
            encoding="utf-8",
        )
        self.assertTrue(any("human_min" in item for item in validate_report(self.article, report)))

    def test_anxia_short_article_can_be_chunked_for_detection(self) -> None:
        body = (
            "天秤这段时间要注意一个细节，别把所有人的情绪都放在自己身上。\n\n"
            "你越想照顾全场，越容易忽略真正该处理的事。关系里先看行动，工作里先看结果，别急着替别人解释。\n\n"
            "接下来把节奏收回来，少一点消耗，多一点判断。钱的事先看清边界，消息来了也别立刻答应。"
            "刷到接好运，愿你稳稳接住这次变化。"
        )
        self.article.write_text(f"---\ntitle: 天秤注意，本月这个习惯要改了\n---\n{body}\n", encoding="utf-8")

        chunks = article_chunks(self.article, min_total_chars=ANXIA_SHORT_MIN_TOTAL_CHARS)

        self.assertGreaterEqual(sum(len(chunk) for chunk in chunks), ANXIA_SHORT_MIN_TOTAL_CHARS)

    def test_optional_zhuque_record_checks_thresholds_and_proof(self) -> None:
        proof = self.root / "zhuque.png"
        proof.write_bytes(b"proof")
        record = self.root / "zhuque.json"
        record.write_text(
            json.dumps(
                {
                    "rounds": [
                        {
                            "human": 90,
                            "suspected": 3,
                            "ai": 7,
                            "report": str(proof),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(latest_errors(record), [])

    def test_optional_zhuque_record_rejects_below_90_human(self) -> None:
        proof = self.root / "zhuque.png"
        proof.write_bytes(b"proof")
        record = self.root / "zhuque.json"
        record.write_text(
            json.dumps(
                {
                    "rounds": [
                        {
                            "human": 89,
                            "suspected": 5,
                            "ai": 6,
                            "report": str(proof),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.assertTrue(any("90.0" in item for item in latest_errors(record)))


if __name__ == "__main__":
    unittest.main()
