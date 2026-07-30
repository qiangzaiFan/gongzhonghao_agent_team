# 95 分生产工作流

## 每日生产

1. 选题：从 `topic_calendar_30d.md`、评论复盘或临时热点里选 1 个主题。
2. 标题：调用 `elder-title-editor` 生成 12 个标题，选 1 个主标题，保留 2 个备选。
3. 风格卡：从 `style_cards.md` 选 1 张主卡。
4. 写稿：调用 `elder-healing-writer` 生成初稿。
5. 二审：调用 `elder-chief-editor` 润色，重点降风险、补细节、去机器味。
6. 插图：运行 `scripts/plan_article_illustrations.py ARTICLE.md --apply`，插入 3 张原创漫画插图位并生成出图 prompt。
7. 出图：按 prompt 生成 3 张不重复插图，放到 `images/illustrations/` 对应路径；图片必须自有或明确授权。
8. 质检：运行 `quality_gate.py`；发布前确认图片文件存在时加 `--require-image-files`。
9. AIGC 检测：运行 `ai_detector.py`，报告必须对应当前正文 hash。
10. 人工发布前复核：看标题、开头、结尾、插图、风险和原创度。
11. 发布后复盘：记录评论痛点和数据。

## 命令入口

创建完整生产包：

```bash
python elder_healing_agent/pipeline.py --calendar-day 1
```

自定义主题：

```bash
python elder_healing_agent/pipeline.py --topic "突然生病以后，才知道身体不能再硬扛" --pillar "重启"
```

生成参考语料分析：

```bash
python elder_healing_agent/scripts/analyze_reference_corpus.py
```

文章质检：

```bash
python elder_healing_agent/quality_gate.py elder_healing_agent/articles/ARTICLE.md
python elder_healing_agent/ai_detector.py elder_healing_agent/articles/ARTICLE.md
```

文章插图规划：

```bash
python elder_healing_agent/scripts/plan_article_illustrations.py elder_healing_agent/articles/ARTICLE.md --apply
```

无 AI 出图工具时，先生成原创占位插图：

```powershell
powershell -ExecutionPolicy Bypass -File elder_healing_agent/scripts/render_manifest_illustrations.ps1
```

发布前严格检查图片文件：

```bash
python elder_healing_agent/quality_gate.py elder_healing_agent/articles/ARTICLE.md --require-image-files
```

输出 JSON 评分：

```bash
python elder_healing_agent/quality_gate.py elder_healing_agent/articles/ARTICLE.md --json
```

## 评分解释

- 95-100：可作为标杆稿，发布前只做人工事实和风险扫读。
- 90-94：高可用，适合发布。
- 85-89：可用，但建议按 warnings 修一轮。
- 75-84：需要主编二审重改。
- 75 以下：不建议发布，重新选题或重写。

AIGC 发布线：human≥90%，ai≤10%。正文改动后必须重跑检测。

## 发布前 5 问

1. 这篇文章前 120 字能不能让读者停住？
2. 是否有至少 3 个具体物件或动作？
3. 是否有 3 张图文高度贴合、互不重复的原创插图？
4. 是否把读者从怨气带回自我照顾？
5. 是否避开医疗、财务、亲子仇恨风险？
6. 标题、正文、插图是否和参考博主拉开了足够距离？

## 周复盘

每周复盘 7 篇文章：

- 哪类标题点击最好。
- 哪类文章收藏和转发最好。
- 哪些评论出现最多。
- 哪些表达让评论区怨气太重。
- 下周要加强哪张风格卡。

复盘模板见 `templates/weekly_review.md`。
