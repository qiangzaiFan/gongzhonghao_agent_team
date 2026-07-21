from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quality_gate import (
    LONGEST_MATCH_REJECT,
    OVERLAP_REJECT_THRESHOLD,
    longest_common_substring_length,
    parse_article,
    shingle_overlap,
    validate_article,
)


PNG_HEADER_1024 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x04\x00\x00\x00\x04\x00"
)


class QualityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in ("cover.png", "body-1.png", "body-2.png"):
            (self.root / name).write_bytes(PNG_HEADER_1024)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_article(self, body_text: str, title: str = "水象反复回头，是还爱还是没说完？") -> Path:
        article = self.root / "article.md"
        article.write_text(
            "\n".join(
                [
                    "---",
                    f"title: {title}",
                    "---",
                    "",
                    "![](cover.png)",
                    "",
                    "手机里的聊天记录被删掉了。" + body_text[:300],
                    "",
                    "![](body-1.png)",
                    "",
                    "## 第一个现场",
                    "",
                    body_text[300:650],
                    "",
                    "![](body-2.png)",
                    "",
                    "## 第二个现场",
                    "",
                    body_text[650:],
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return article

    def test_valid_article_shape_passes(self) -> None:
        path = self.write_article("水" * 940)
        result = validate_article(parse_article(path))
        self.assertEqual(result.errors, [])

    def test_absolute_prediction_is_rejected(self) -> None:
        path = self.write_article("水" * 500 + "你们一定会复合" + "水" * 430)
        result = validate_article(parse_article(path))
        self.assertTrue(any("绝对预测词" in item for item in result.errors))

    def test_thirty_character_match_is_rejected(self) -> None:
        shared = "巨蟹把旧照片放回相册后又在深夜里一张一张重新点开然后关掉手机走到客厅倒了一杯水"
        self.assertGreaterEqual(longest_common_substring_length(shared, shared), LONGEST_MATCH_REJECT)

    def test_high_shingle_overlap_is_rejected(self) -> None:
        source = "巨蟹常常记得那些已经改变的生活细节" * 10
        draft = source[:240] + "新的文章结尾"
        self.assertGreaterEqual(shingle_overlap(source, draft), OVERLAP_REJECT_THRESHOLD)


if __name__ == "__main__":
    unittest.main()
