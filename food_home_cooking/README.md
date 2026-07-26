# 家常美食公众号 Agent

基于本地“暖暖小厨”知识库抽象出的家常美食写作系统，用于生产原创公众号草稿。

## 当前配置

- 写手：`.claude/agents/home-food-writer.md`
- 风格拆解：`specs/nuannuan_style.md`
- 人设与地域：`specs/persona.md`
- 运营计划：`specs/food_track_plan.md`
- 选题卡模板：`specs/topic_card_template.md`
- 标题与去重：`specs/title_and_dedup_rules.md`
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

主编应调用 `home-food-writer` 生成 Markdown 草稿。发布前需要补齐自有实拍图片。

## 质检

生成草稿后先跑本地质检：

```bash
python quality_gate.py articles/20260726_夫妻二人18元午餐.md
```

质检会检查标题长度、知识库标题重复、图片是否连放、图片数量、花费明细、小失误、轻互动和禁用署名。

发布前再跑共用中文 AIGC 检测，当前发布线为 `human≥90%` 且 `ai≤10%`：

```bash
../.venv/Scripts/python.exe ../astrology_content/ai_detector.py articles/20260726_夫妻二人18元午餐.md --report reviews/auto/sample_ai_report.json
```

## 原创边界

这套配置只学习高层写法：标题结构、生活场景、做法密度和家常语气。不得复用知识库原文标题、段落、图片、署名或可识别表达。
