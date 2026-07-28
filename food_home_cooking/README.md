# 家常美食公众号 Agent

基于本地“暖暖小厨”知识库抽象出的家常美食写作系统，用于生产原创公众号草稿。

## 当前配置

- 写手：`.claude/agents/home-food-writer.md`
- 风格拆解：`specs/nuannuan_style.md`
- 人设与地域：`specs/persona.md`
- 运营计划：`specs/food_track_plan.md`
- 选题卡模板：`specs/topic_card_template.md`
- 标题与去重：`specs/title_and_dedup_rules.md`
- AI 示意图策略：`specs/image_ai_policy.md`
- 自动质检：`quality_gate.py`
- 首篇样稿：`articles/20260726_夫妻二人18元午餐.md`
- 主编入口：`CLAUDE.md`

## 使用方式

进入 `food_home_cooking/` 后，给主编一个明确选题卡，例如：

```text
写一篇家常美食文：
主题：晒晒夫妻二人的午餐
菜品：番茄鸡蛋捞面、蒜蓉空心菜、绿豆汤
预算：18元
场景：天热没胃口，下班晚了想快速吃点清爽的
要求：暖暖小厨类家常饭风格，但原创，不冒充原博主
```

主编应调用 `home-food-writer` 生成 Markdown 草稿。当前没有稳定实拍图时，默认使用 5-8 张 AI 原创示意图或图片占位；不得从小红书、微博、抖音等平台搬图后二改使用。若后续补齐自有实拍图，可切换回 16-22 张实拍步骤图节奏。

## 本地 AI 配图

高画质配图使用本地 ComfyUI：FLUX.2 Klein 4B 优先、SDXL Lightning 自动降级，候选图会先做清晰度和图片文字检查，再统一输出为 `1536x1024` JPG。

首次安装、模型位置和使用方式见 [本地配图流水线](specs/local_image_pipeline.md)。

生成当前文章的本地图片：

```bash
python generate_article_images.py articles/20260727_一个人12元早餐.md
```

## 质检

生成草稿后先跑本地质检：

```bash
python quality_gate.py articles/20260726_夫妻二人18元午餐.md
```

没有实拍图、使用 AI 示意图时：

```bash
python quality_gate.py articles/20260726_夫妻二人18元午餐.md --image-mode ai
```

质检会检查标题长度、知识库标题重复、图片是否连放、图片数量、实际图片文件、分辨率、花费明细、小失误、轻互动和禁用署名。

发布前再跑共用中文 AIGC 检测，当前发布线为 `human≥90%` 且 `ai≤10%`：

```bash
../.venv/Scripts/python.exe ../astrology_content/ai_detector.py articles/20260726_夫妻二人18元午餐.md --report reviews/auto/sample_ai_report.json
```

## 原创边界

这套配置只学习高层写法：标题结构、生活场景、做法密度和家常语气。不得复用知识库原文标题、段落、图片、署名或可识别表达。

图片同样遵守原创边界：可以研究成熟账号的构图和排版节奏，但不能下载他人图片后去水印、裁剪、滤镜化或改风格当作自有配图。
