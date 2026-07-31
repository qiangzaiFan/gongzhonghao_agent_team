from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import plan_article_illustrations as planner  # noqa: E402


class IllustrationPromptTests(unittest.TestCase):
    def test_prompt_includes_required_negative_prompt(self) -> None:
        scene = {
            "summary": "床头药盒和温水旁，一只淡金色小鹤安静坐着",
            "scene": "a small pale-gold crane mascot sitting quietly beside a bedside table",
        }

        prompt = planner.build_prompt(
            "人到后半生，别再把身体借给别人",
            scene,
            "opening",
            "后半生别再\n把身体借给别人",
            "20260730_body_01_opening_base.png",
        )

        self.assertIn("Negative prompt:", prompt)
        self.assertIn(planner.NEGATIVE_PROMPT, prompt)


if __name__ == "__main__":
    unittest.main()
