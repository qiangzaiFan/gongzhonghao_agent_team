from __future__ import annotations

import unittest

from quality_gate import highlighted_sentence_errors, structure_skeleton


class TemplateVariationTests(unittest.TestCase):
    def test_same_template_order_ignores_paragraph_length(self) -> None:
        first = """![](cover.jpg)

晚上，她没回消息。

![](scene.jpg)

## 冲突

短段。

**“这次我不转。”**

![](body-1.jpg)

## 后来

正文。

![](body-2.jpg)

窗外只剩水声。
"""
        second = """![](cover-2.jpg)

周日，她把一段很长的解释删掉，又重新写了一遍。

另一段铺垫。

![](scene-2.jpg)

## 另一件事

长度完全不同的正文。

**“我今天不做饭。”**

![](body-3.jpg)

## 当天晚上

另一段正文。

![](body-4.jpg)

阳台外有风声。
"""
        self.assertEqual(structure_skeleton(first), structure_skeleton(second))

    def test_highlight_position_changes_skeleton(self) -> None:
        middle = """![](a.jpg)

普通开头。

## 第一节

正文。

**“现场原话。”**

![](b.jpg)

## 第二节

正文。
"""
        opening = """![](a.jpg)

**“现场原话。”**

普通开头。

## 第一节

正文。

![](b.jpg)

## 第二节

正文。
"""
        self.assertNotEqual(structure_skeleton(middle), structure_skeleton(opening))

    def test_rejects_generic_highlight(self) -> None:
        body = "**很多女人不是讨厌家庭，她只是厌倦了付出。**"
        self.assertTrue(highlighted_sentence_errors(body))

    def test_accepts_scene_dialogue_highlight(self) -> None:
        body = "**“三万我拿不出，五千可以。”**"
        self.assertEqual(highlighted_sentence_errors(body), [])


if __name__ == "__main__":
    unittest.main()
