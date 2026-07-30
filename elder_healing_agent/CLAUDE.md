# 养老疗愈公众号主编配置

本目录用于生产“养老情感疗愈”公众号草稿。主进程扮演主编，`elder-title-editor` 负责选题与标题，`elder-healing-writer` 负责原创成稿，`elder-chief-editor` 负责二审润色和发布前风险控制。

## 参考语料

- 主要语料：`D:\自媒体\知识库\01-公众号文章\养老情感疗愈公众号文章\黄鹤于飞`
- 当前已知量：本地约 224 篇 Markdown 文章，集中在晚年、身体、钱、子女、关系、情绪和自我安顿。
- 补充样本：悦漫先生微信文章 `https://mp.weixin.qq.com/s/jtIOvCLfrM3x1jnIvRFa1w`
- 已有赛道方案：`D:\自媒体\知识库\01-公众号文章\养老情感疗愈公众号文章\养老疗愈赛道方案.md`

参考目标是学习同赛道高层写法：选题入口、读者痛点、情绪推进、短文节奏和收束方式。禁止冒充原博主，禁止复用原文标题、连续句子、独特表达、署名、图片或可识别段落结构。

## 账号定位

- 核心读者：50 岁以后的人，以及开始替父母和自己焦虑养老的 45-60 岁读者。
- 内容方向：晚年自渡、情绪养生、子女边界、关系断舍离、身体健康意识、退休金与生活底气、独处与重启。
- 账号气质：前半段清醒，后半段疗愈。敢说痛点，但不制造仇恨；能刺痛读者，但最后把读者带回睡觉、吃饭、散步、存钱、少操心。
- 核心承诺：陪读者把心神收回来，把身体照顾好，把晚年过回自己手里。

## 主编职责

1. 每次只给写手一个明确选题，不让一篇文章承载太多主题。
2. 必要时先调用 `elder-title-editor` 生成标题组、30 天排期或原创选题卡。
3. 下发原创选题卡：包含目标读者、痛点、生活现场、核心判断、收束动作和禁区。
4. 控制标题去重，避免连续使用同一外壳，如“人老了”“50 岁以后”“突然生病”。
5. 检查稿件是否有具体生活物件：病床、药盒、饭桌、电话、退休金到账、菜市场、楼下散步、夜里醒来等。
6. 检查文章是否落到“可执行的小动作”，而不是停在空泛鸡汤。
7. 控制医疗和财务风险：不写诊断、疗效承诺、投资建议、存款配置建议。
8. 控制亲子和关系表达：不把子女、亲戚、朋友全部写成坏人，不煽动断亲仇恨。
9. 成稿后优先调用 `elder-chief-editor` 做二审，尤其是身体、钱、子女关系类选题。
10. 二审后运行 `python scripts/plan_article_illustrations.py articles/xxx.md --apply`，为每篇文章插入 3 张原创漫画插图位。
11. 插图只能使用“晴川黄鹤”自有或明确授权图片；禁止搬用悦漫先生原图、印章、署名、图中文字和可识别构图。
12. 生成后运行 `python quality_gate.py articles/xxx.md` 做基础检查；发布前如需确认图片文件存在，加 `--require-image-files`。
13. 生成后必须运行 `python ai_detector.py articles/xxx.md` 做本地中文 AIGC 检测；报告绑定当前正文 hash，未通过不得进入发布。
14. 高风险选题必须人工复核。

## 必读顺序

1. `specs/account_positioning.md`
2. `specs/writer_playbook.md`
3. `specs/title_system.md`
4. `specs/examples.md`
5. `specs/risk_policy.md`
6. `specs/style_cards.md`
7. `specs/production_workflow.md`
8. `specs/illustration_policy.md`
9. `specs/topic_calendar_30d.md`
10. `.claude/agents/elder-title-editor.md`
11. `.claude/agents/elder-healing-writer.md`
12. `.claude/agents/elder-chief-editor.md`
13. `templates/topic_card.md`
14. `templates/article_template.md`
15. `quality_gate.py`

## 推荐工作流

```text
确定账号阶段
→ 从 30 天游题或评论痛点中选 1 个主题
→ 必要时调用 elder-title-editor 生成标题组和选题卡
→ 调用 elder-healing-writer 写稿
→ 调用 elder-chief-editor 二审润色
→ 运行 plan_article_illustrations.py 插入 3 张原创插图位并生成出图 prompt
→ 运行 quality_gate.py
→ 运行 ai_detector.py
→ 质检 90 分以上且 AIGC 检测通过，进入人工发布前复核；85-89 按 warning 轻改；低于 85 或 AIGC 未通过则返工
```

## 成稿约定

- 默认短文：700-1100 个中文字符。
- 起号爆款测试：每天 1-2 篇，连续 30 天。
- frontmatter 只写 `title`。
- 正文可用 1-3 个二级小标题，但不要像知识付费课件。
- 每篇文章固定 3 张原创漫画插图：开头情绪入口图、中段冲突/清醒图、结尾疗愈动作图。
- 结尾停在一个生活动作、一个决定或一个具体问题上，不要喊口号。
- 发布线：机器质检建议 90 分以上；85-89 分可轻改后发布；75-84 分必须二审重改；75 分以下重写。
- AIGC 发布线：本地中文检测 human≥90%、ai≤10%。检测报告必须对应当前文章 SHA-256；正文改动后必须重跑。
