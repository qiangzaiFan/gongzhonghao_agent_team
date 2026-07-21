from __future__ import annotations

import unittest

from daily_emotion_women import planned_content_mix
from sync_wanxiang_persona_pool import modernize_legacy_prompt


class ContentMixTests(unittest.TestCase):
    def test_three_articles_include_one_lifestyle_diary(self) -> None:
        self.assertEqual(planned_content_mix(3), (2, 1))

    def test_five_articles_include_two_lifestyle_diaries(self) -> None:
        self.assertEqual(planned_content_mix(5), (3, 2))

    def test_legacy_persona_prompt_is_upgraded(self) -> None:
        result = modernize_legacy_prompt("调用主体库：情感号_青春靓丽_01，22 岁亚洲成年女性，青春活力")
        self.assertIn("30 岁", result)
        self.assertIn("精致日常妆容", result)
        self.assertIn("轻熟妩媚", result)
        self.assertNotIn("22 岁", result)


if __name__ == "__main__":
    unittest.main()
