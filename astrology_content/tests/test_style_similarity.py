from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from style_similarity import score_article


class StyleSimilarityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, name: str, title: str, body: str) -> Path:
        path = self.root / name
        path.write_text(f"---\ntitle: {title}\n---\n\n{body}\n", encoding="utf-8")
        return path

    def test_commentary_scores_higher_than_story(self) -> None:
        commentary = self.write(
            "commentary.md",
            "水象回头，是还爱吗？",
            """
水象在关系结束后打开旧消息，经常被理解成还爱。这个判断只说对一半。

## 习惯与信任

巨蟹容易留恋习惯，因为关系和安全感已经放在同一个生活秩序里。天蝎关心信任为什么失效，双鱼则容易留在想象过的未来里。

## 分清缺口

所以回头并不只是复合信号。要分清自己寻找的究竟是人、事实，还是没发生的以后？
""",
        )
        story = self.write(
            "story.md",
            "一段关系结束后",
            """
那天晚上，小A又收到了一条消息。第二天，她告诉我的朋友，自己已经想明白了。

## 那天之后

一个月后，小A走出房间，她已经学会了彻底放下。
""",
        )
        self.assertGreater(score_article(commentary).total, score_article(story).total)


if __name__ == "__main__":
    unittest.main()
