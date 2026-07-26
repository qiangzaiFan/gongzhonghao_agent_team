from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quality_gate import (
    LONGEST_MATCH_REJECT,
    OVERLAP_REJECT_THRESHOLD,
    load_source_dir,
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

    def test_thirty_character_match_is_rejected(self) -> None:
        shared = "巨蟹把旧照片放回相册后又在深夜里一张一张重新点开然后关掉手机走到客厅倒了一杯水"
        self.assertGreaterEqual(longest_common_substring_length(shared, shared), LONGEST_MATCH_REJECT)

    def test_high_shingle_overlap_is_rejected(self) -> None:
        source = "巨蟹常常记得那些已经改变的生活细节" * 10
        draft = source[:240] + "新的文章结尾"
        self.assertGreaterEqual(shingle_overlap(source, draft), OVERLAP_REJECT_THRESHOLD)

    def write_short_article(self, title: str, paragraphs: list[str]) -> Path:
        article = self.root / "short.md"
        article.write_text(
            "---\n"
            f"title: {title}\n"
            "---\n\n"
            + "\n\n".join(paragraphs)
            + "\n",
            encoding="utf-8",
        )
        return article

    def test_anxia_short_shape_passes(self) -> None:
        path = self.write_short_article(
            "白羊7月有一个机会正在路上",
            [
                "白羊这段时间要重点看见身边出现的新机会，尤其是和工作协作、临时邀约有关的部分。",
                "你们行动快，别人还在犹豫时，你已经能先把方向试出来，这会让你比平时更容易被看见。",
                "但别急着一口气全接下来，先分清哪些能带来长期积累，哪些只是短暂热闹。",
                "稳住节奏，把精力放在真正能沉淀资源的事上，祝你接住这段时间的变化。",
            ],
        )
        result = validate_article(parse_article(path))
        self.assertEqual(result.errors, [])

    def test_long_article_is_rejected_by_default(self) -> None:
        path = self.write_short_article(
            "白羊7月值得留意的新机会",
            [
                "白羊这段时间要重点看见身边出现的新机会。" + "白羊需要稳住节奏" * 90,
                "把精力放在真正能沉淀资源的事上。",
                "祝你接住这段时间的变化。",
            ],
        )
        result = validate_article(parse_article(path))
        self.assertTrue(any("正文中文字符" in item for item in result.errors))

    def test_anxia_short_rejects_reused_corpus_title(self) -> None:
        title = "白羊7月有一个机会正在路上"
        path = self.write_short_article(
            title,
            [
                "白羊最近适合把注意力放回手头机会。",
                "别被临时情绪带着跑，也不要什么邀约都接。",
                "你越能分清轻重，越容易把好事落到实处。",
            ],
        )
        result = validate_article(parse_article(path), forbidden_titles={title})
        self.assertTrue(any("原标题" in item for item in result.errors))

    def test_anxia_short_rejects_corpus_overlap_from_source_dir(self) -> None:
        corpus = self.root / "corpus"
        corpus.mkdir()
        title = "白羊7月有一个机会正在路上"
        source = corpus / f"0001_2026-07-23_{title}_2247485522_1.md"
        shared = "白羊最近适合把注意力放回手头机会别被临时情绪带着跑也不要什么邀约都接"
        source.write_text(
            "---\n"
            f"title: {title}\n"
            "---\n\n"
            f"# {title}\n\n{shared}\n",
            encoding="utf-8",
        )
        path = self.write_short_article(
            "白羊7月值得留意的新机会",
            [
                shared,
                "你越能分清轻重，越容易把好事落到实处。",
                "祝你稳稳接住这段时间的变化。",
            ],
        )
        titles, sources = load_source_dir(corpus)
        result = validate_article(parse_article(path), forbidden_titles=titles, source_texts=sources)
        self.assertTrue(any("连续规范化字符" in item for item in result.errors))

    def test_anxia_short_allows_strong_prediction_words_with_warning(self) -> None:
        path = self.write_short_article(
            "白羊7月值得留意的新机会",
            [
                "白羊这个月绝对会更容易看见一件好事，很多变化都会围着你的行动展开。",
                "你只要保持推进，就能更快看见结果，尤其是工作协作、临时邀约、资源介绍这些小变化，都值得多留意。",
                "别急着怀疑自己的判断，把能推进的事先放到前面，机会出现时才不容易手忙脚乱，也别反复拖延。",
                "刷到接好运，祝你稳稳接住这段时间的变化。",
            ],
        )
        result = validate_article(parse_article(path))
        self.assertEqual(result.errors, [])
        self.assertTrue(any("强刺激星座词" in item for item in result.warnings))

    def test_repeated_hot_source_title_can_be_allowed(self) -> None:
        corpus = self.root / "hot-corpus"
        corpus.mkdir()
        title = "天蝎座7月一定会发生的三件喜事！"
        for index in range(2):
            (corpus / f"000{index + 1}_2026-07-2{index}_{title}_22474848{index}_1.md").write_text(
                "---\n"
                f"title: {title}\n"
                "---\n\n"
                "天蝎这段时间会看见新的变化。\n",
                encoding="utf-8",
            )
        path = self.write_short_article(
            title,
            [
                "天蝎这段时间可以多留意身边变化。",
                "有些机会不会声势很大，却会慢慢把你推到更合适的位置。",
                "刷到接好运，祝你稳稳接住这段时间的提醒。",
            ],
        )
        titles, sources = load_source_dir(corpus, allow_hot_titles=True, hot_title_min_count=2)
        result = validate_article(parse_article(path), forbidden_titles=titles, source_texts=sources)
        self.assertFalse(any("原标题" in item for item in result.errors))


if __name__ == "__main__":
    unittest.main()
