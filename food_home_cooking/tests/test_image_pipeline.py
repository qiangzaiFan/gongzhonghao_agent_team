from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import generate_article_images as pipeline  # noqa: E402


def load_quality_gate():
    spec = importlib.util.spec_from_file_location("food_quality_gate", ROOT / "quality_gate.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


quality_gate = load_quality_gate()


class ImagePipelineTests(unittest.TestCase):
    def test_extract_slots_and_rewrite_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "draft.md"
            article.write_text(
                "# 测试\n\n![示意图：早餐整餐](images/ai/breakfast.jpg)\n",
                encoding="utf-8",
            )
            text, slots = pipeline.extract_image_slots(article)

            self.assertEqual(len(slots), 1)
            self.assertEqual(slots[0].target_relative, "../images/ai/breakfast.jpg")
            self.assertIn("../images/ai/breakfast.jpg", pipeline.rewrite_article_paths(text, slots))

    def test_flux_workflow_has_no_unresolved_variables(self) -> None:
        profiles = pipeline.load_profiles()
        workflow = pipeline.render_workflow(
            profiles,
            "flux2_klein",
            prompt="普通家庭厨房里的一碗青菜鸡蛋汤面",
            seed=1234,
            filename_prefix="food_home_cooking/test",
        )
        serialized = str(workflow)

        self.assertNotIn("__", serialized)
        self.assertEqual(workflow["66"]["inputs"]["width"], 960)
        self.assertEqual(workflow["82"]["inputs"]["width"], 1536)

    def test_score_candidate_accepts_sharp_final_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "candidate.jpg"
            image = Image.new("RGB", (1536, 1024), "#dba45e")
            draw = ImageDraw.Draw(image)
            for index in range(0, 1536, 64):
                draw.rectangle((index, 120, index + 24, 860), fill="#315b2c")
            draw.ellipse((480, 250, 1090, 850), fill="#f5e8ca", outline="#4f3a24", width=18)
            image.save(image_path, quality=94)

            scorer = pipeline.OptionalSemanticScorer("off")
            score, metrics, warnings, _, _ = pipeline.score_candidate(
                image_path,
                prompt="一碗青菜鸡蛋汤面",
                semantic_scorer=scorer,
            )

            self.assertGreaterEqual(score, 56)
            self.assertEqual(metrics["width"], 1536)
            self.assertEqual(metrics["height"], 1024)
            self.assertFalse(any("尺寸过低" in warning for warning in warnings))

    def test_quality_gate_requires_existing_local_ai_asset(self) -> None:
        image_name = "_test_food_pipeline_asset.jpg"
        article_name = "_test_food_pipeline_article.md"
        image_path = ROOT / "images" / "ai" / image_name
        article_path = ROOT / "articles" / article_name
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (1536, 1024), "#d6b273")
        image.save(image_path, quality=90)
        article_path.write_text(
            """---
title: 晒晒一个人的早餐，12元做4样，20分钟热乎端上桌
---

# 晒晒一个人的早餐，12元做4样，20分钟热乎端上桌

今天早上赶时间，花12元煮了一碗面，20分钟就端上桌。

![示意图：一碗早餐汤面](../images/ai/_test_food_pipeline_asset.jpg)

【食材准备】：鲜面条、鸡蛋、小白菜。

1、锅里加水煮开。
2、下鲜面条搅散。
3、面条快熟时放小白菜。
4、鸡蛋煎到边缘焦黄。
5、碗里加生抽和葱花。
6、舀两勺面汤冲开。
7、把面条和青菜盛进去。
8、最后放上煎鸡蛋。

今天青菜有点蔫，不过煮出来还是挺嫩的。你们早餐会这样吃吗？
""",
            encoding="utf-8",
        )
        try:
            report = quality_gate.check(article_path, image_mode="ai")
            self.assertFalse(report["errors"])
            self.assertEqual(report["image_files"][0]["width"], 1536)

            image_path.unlink()
            missing_report = quality_gate.check(article_path, image_mode="ai")
            self.assertTrue(any("图片文件不存在" in item for item in missing_report["errors"]))
        finally:
            image_path.unlink(missing_ok=True)
            article_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
