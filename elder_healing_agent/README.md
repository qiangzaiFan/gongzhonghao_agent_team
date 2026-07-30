# 养老疗愈公众号 Agent

这是一个项目内的“养老情感疗愈”公众号写作 agent 工作区，用来参考 `黄鹤于飞` 与用户提供的 `悦漫先生` 样本，生产原创公众号文章、标题和起号选题。

## 核心定位

> 写给 50 岁以后的人：少生气，留住钱，照顾身体，把晚年过回自己手里。

内容不是普通养老资讯，也不是医学养生号，而是“晚年自渡 + 情绪养生 + 关系边界”的公众号。

## 目录结构

```text
elder_healing_agent/
├── CLAUDE.md
├── README.md
├── quality_gate.py
├── ai_detector.py
├── daily_elder_healing.py
├── pipeline.py
├── .claude/agents/elder-healing-writer.md
├── .claude/agents/elder-title-editor.md
├── .claude/agents/elder-chief-editor.md
├── specs/
│   ├── account_positioning.md
│   ├── writer_playbook.md
│   ├── title_system.md
│   ├── examples.md
│   ├── risk_policy.md
│   ├── style_cards.md
│   ├── production_workflow.md
│   ├── illustration_policy.md
│   └── topic_calendar_30d.md
├── scripts/
│   ├── analyze_reference_corpus.py
│   ├── batch_quality.py
│   ├── compose_quote_cards.py
│   └── plan_article_illustrations.py
├── references/
│   └── corpus_report.md
├── data/
│   ├── content_matrix.json
│   ├── style_stats.json
│   ├── reference_titles.txt
│   └── illustration_manifest.json
├── templates/
│   ├── topic_card.md
│   ├── article_template.md
│   ├── comment_pain_points.md
│   ├── scorecard.md
│   └── weekly_review.md
├── prompts/
├── images/
├── runs/
├── reviews/
└── articles/
```

## 如何使用

在 Codex 或 Claude Code 中可以这样下达任务：

```text
使用 elder_healing_agent 的 elder-healing-writer，
写一篇养老疗愈公众号文章。
主题：突然生病以后，才知道身体不能再硬扛。
保存到 elder_healing_agent/articles/。
```

也可以先让主编出题：

```text
参考 elder_healing_agent/specs/topic_calendar_30d.md，
帮我生成今天的养老疗愈账号选题卡，再调用写手成稿。
```

## 三段式起号工作流

```text
elder-title-editor
→ 生成标题组与选题卡
→ elder-healing-writer
→ 写原创初稿
→ elder-chief-editor
→ 二审润色、降风险、增强生活细节
→ plan_article_illustrations.py
→ 插入 3 张原创漫画插图位、生成出图 prompt、写入去重清单
→ quality_gate.py
→ 基础质检
→ ai_detector.py
→ 本地中文 AIGC 检测
```

## 原创插图系统

每篇文章固定 3 张原创漫画插图：

- 图 1：开头情绪入口图。
- 图 2：中段冲突/清醒图。
- 图 3：结尾疗愈动作图。

先生成插图计划并写入文章：

```bash
cd elder_healing_agent
python scripts/plan_article_illustrations.py articles/文章名.md --apply
```

脚本会输出：

- 文章中的 3 个 Markdown 插图位。
- `images/illustrations/prompts/` 下的 3 个出图 prompt。
- `data/illustration_manifest.json` 下的去重记录。

推荐两步生产：

1. 按 prompt 生成无字水彩主体图，保存到 `images/illustrations/sources/xxx_base.png`。
2. 运行 `python scripts/compose_quote_cards.py`，自动叠加准确中文大字、自有红章和署名，生成文章引用的最终 PNG。

正式图片必须用 AI 出图或手绘方式生成，不能用本地扁平占位图冒充。发布前运行 `quality_gate.py --require-image-files`，缺少成品 PNG 时不得发布。

插图边界：

- 只学习参考博主的高层方法：纸纹、水彩漫画、图文强贴合、温柔幽默。
- 不下载、不搬运、不二改悦漫先生原图。
- 不使用其红色印章、署名、Yue Man 字样、图中文字和可识别构图。
- 发布前图片必须是自有或明确授权资产。

详细视觉拆解见 `references/illustration_reference_analysis.md`。

## 95 分生产包

创建一个完整生产包，包含标题官任务、写手任务、主编二审任务和质检命令：

```bash
cd elder_healing_agent
python pipeline.py --calendar-day 1
```

自定义主题：

```bash
python pipeline.py --topic "突然生病以后，才知道身体不能再硬扛" --pillar "重启"
```

生产包会输出到 `runs/`，按 `00-runbook.md` 执行即可。

## 一键生成写手任务

从 30 天起号表生成 1 个写手任务：

```bash
cd elder_healing_agent
python daily_elder_healing.py --calendar-day 1
```

生成 3 个任务：

```bash
python daily_elder_healing.py --calendar-day 1 --count 3
```

使用自定义选题：

```bash
python daily_elder_healing.py --topic "突然生病以后，才知道身体不能再硬扛"
```

脚本会把规范选题卡和写手指令保存到 `prompts/`，再交给 `elder-healing-writer` 成稿。

## 语料分析

生成参考语料统计报告：

```bash
cd elder_healing_agent
python scripts/analyze_reference_corpus.py
```

输出：

- `references/corpus_report.md`
- `data/style_stats.json`
- `data/reference_titles.txt`

## 质检

生成文章后运行：

```bash
cd elder_healing_agent
python quality_gate.py articles/文章名.md
python ai_detector.py articles/文章名.md
```

质检会输出 100 分制评分、风险等级、标题/正文原创距离、历史稿去重、标题、篇幅、frontmatter、禁用风险表达和公众号常见机器稿味。

本地中文 AIGC 检测会输出 human/suspected/ai 比例，报告保存到 `reviews/auto/`，并绑定当前正文 SHA-256。正文改动后必须重跑。

发布建议：

- 95-100：标杆稿。
- 90-94：高可用，可发布前人工扫读。
- 85-89：可用，但建议按 warning 轻改。
- 75-84：必须二审重改。
- 75 以下：重写。
- AIGC 发布线：human≥90%，ai≤10%。未通过不得进入发布。

默认还会读取参考语料目录，检查标题是否撞题、正文是否有连续片段重合。需要临时跳过时：

```bash
python quality_gate.py articles/文章名.md --skip-reference-check
```

批量质检全部草稿：

```bash
python scripts/batch_quality.py
```

输出：

- `reviews/quality_summary.json`
- `reviews/quality_summary.md`

## 原创边界

这个 agent 只学习参考博主的高层方法：选题机制、情绪节奏、短文密度和读者痛点。不复制原文标题、段落、独特表达、案例和署名。

目标是写出“同赛道强账号”的原创稿，而不是逐句仿写某一个博主。
