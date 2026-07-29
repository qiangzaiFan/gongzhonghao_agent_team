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

    def test_cover_prompt_strengthens_local_object_constraints(self) -> None:
        slot = pipeline.ImageSlot(
            index=1,
            line_number=13,
            alt="示意图：一个人早餐的整餐搭配",
            reference="../images/ai/breakfast.jpg",
            target_relative="../images/ai/breakfast.jpg",
            target_path=ROOT / "images" / "ai" / "breakfast.jpg",
        )
        article_text = "今天做了鸡蛋青菜汤面、煎半根玉米、拌黄瓜和一杯豆浆。"

        prompt = pipeline.build_prompt(slot, article_text=article_text)

        self.assertIn("局部物体约束", prompt)
        self.assertIn("食物和餐具占画面70%到85%", prompt)
        self.assertIn("不要让水槽、窗户、橱柜和大面积空台面抢主体", prompt)
        self.assertIn("真实公众号配图而不是厨房环境照", prompt)
        self.assertIn("乳白色或象牙白", prompt)
        self.assertIn("不能画成茶、咖啡、奶茶、可可或透明水", prompt)
        self.assertIn("食材纹理、火候和调味线索", prompt)
        self.assertIn("避免死板摆拍", prompt)
        self.assertIn("正常浅盘或小菜碟", prompt)
        self.assertIn("不能只是几块很小的装饰或边角点缀", prompt)
        self.assertIn("少量蒜末、醋汁油光、盐渍水光、芝麻或辣椒点缀", prompt)
        self.assertIn("不要机械堆满佐料", prompt)
        self.assertIn("半根清楚可见的煎玉米", prompt)
        self.assertIn("玉米粒分明、颜色金黄", prompt)
        self.assertIn("不能大片糊黑", prompt)
        self.assertIn("不能画成米饭盖浇或肉菜盖饭", prompt)
        self.assertNotIn("最多三种食物", prompt)

    def test_noodle_prompt_keeps_henan_noodles_from_becoming_soup(self) -> None:
        slot = pipeline.ImageSlot(
            index=1,
            line_number=13,
            alt="示意图：河南家常番茄鸡蛋豆角捞面整餐",
            reference="../images/ai/noodles.jpg",
            target_relative="../images/ai/noodles.jpg",
            target_path=ROOT / "images" / "ai" / "noodles.jpg",
        )
        article_text = "主食是番茄鸡蛋豆角卤捞面，旁边配了一小碗蒜汁黄瓜。"

        prompt = pipeline.build_prompt(slot, article_text=article_text)

        self.assertIn("捞面应是少汤汁的拌面或浇卤面，不是汤面", prompt)
        self.assertIn("红色番茄块、黄色炒鸡蛋块和绿色长豆角段", prompt)
        self.assertIn("正常浅盘或小菜碟", prompt)
        self.assertIn("不要添加文章没有提到的饮品", prompt)

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
