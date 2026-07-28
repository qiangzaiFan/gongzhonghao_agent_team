# 安夏星座短文号工作区

本目录用于生产“安夏式星座短文号”本地草稿：每日 3 篇单星座短文，加 1 篇十二星座日运；标题有钩子，正文稳健原创。

## 工作区内容

- `CLAUDE.md`：安夏短文号主编职责和操作约定。
- `.claude/agents/astrology-writer.md`：安夏短文写手 Agent。
- `specs/anxia_style.md`：安夏短文风格画像。
- `specs/`：账号定位、文章质量、来源和工作流规则。
- `articles/`：本地 Markdown 短文草稿。
- `assets/daily_fortune_cards/`：十二星座每日好运的信息卡 SVG 图片，每天 12 张。
- `anxia_analyze.py`：分析安夏知识库语料。
- `anxia_calendar.py`：生成每日 3 篇单星座选题排期。
- `anxia_generate.py`：默认额外生成一篇“十二星座每日好运”四象日运稿。
- `content_record.py`：保存每篇的选题卡、来源模式、标题/开头候选和正文变体。
- `performance_tracker.py`：记录发布后的曝光、阅读和互动数据，并按主题、标题、开头和正文变体复盘。
- `quality_gate.py`：默认使用 `anxia_short` 质检 profile。

## 常用命令

分析安夏星座知识库，生成近期短文号运营画像：

```bash
python3 anxia_analyze.py \
  "D:\自媒体\知识库\01-公众号文章\星座公众号文章\安夏星座" \
  --since 2026-06-01
```

生成安夏短文号 7 天单星座排期，默认每日 3 篇：

```bash
python3 anxia_calendar.py --days 7 --daily 3 --profile anxia_short
```

排期会读取 `reviews/performance.jsonl`。某个“星座 × 主题”至少有 3 篇有效表现记录后，才会在不打破星座均衡的前提下获得优先级；可用 `--performance-min-samples` 调整门槛。
单日运行也会按日期继续十二星座轮播，不会每天重新从同一组星座开始。

一步生成 3 天文章量（默认每天 3 篇单星座稿 + 1 篇十二星座日运，共 12 篇），并自动质检：

```bash
python3 anxia_generate.py --days 3
```

生成器会同时写入 `reviews/editorial/` 中与文章同名的编辑记录。每篇记录保留 3-4 个标题版本、2 个开头版本和当前默认选项；发布时可在表现录入命令中标记实际采用的版本。记录绑定当前文章摘要，文章修改后需要重新生成或更新记录，避免选题卡、标题备选和实际成稿脱节。

一步生成 7 天文章量（默认每天 3 篇单星座稿 + 1 篇十二星座日运，共 28 篇），并自动质检：

```bash
python3 anxia_generate.py --days 7
```

日运标题采用 `十二星座每日好运丨YYYY.MM.DD`，按火象、土象、风象、水象分四组覆盖全部 12 个星座。默认会同步生成 12 张粉色信息卡 SVG，并在正文对应四象分组下引用；图片保存在 `assets/daily_fortune_cards/YYYYMMDD/`。该栏目使用独立的 `daily_fortune` 质检 profile，保留 3 个标题版本、2 个开头版本和编辑记录；正文和卡片文案均为原创，不复用外部文章句子、段落或图片。

只生成原有单星座短文时：

```bash
python3 anxia_generate.py --days 7 --no-daily-fortune
```

只提前生成一周十二星座日运时：

```bash
python3 anxia_generate.py --date 2026-07-28 --days 7 --daily-fortune-only
```

如果只想生成日运正文、不生成卡片图片：

```bash
python3 anxia_generate.py --date 2026-07-28 --days 7 --daily-fortune-only --no-daily-card-assets
```

如果要优先直接使用知识库里重复出现过的热标题：

```bash
python3 anxia_generate.py \
  --days 3 \
  --daily 3 \
  --mode hot-source \
  --hot-title-min-count 2
```

指定日期生成：

```bash
python3 anxia_generate.py --date 2026-07-27 --days 3
```

默认知识库路径为 `D:\自媒体\知识库\01-公众号文章\星座公众号文章\安夏星座`，默认模式为 `viral-safe`。`--daily 3` 表示每天 3 篇单星座短文，日运默认额外增加 1 篇。若当天文件已存在，会自动跳过；需要重写已存在草稿时添加 `--overwrite`。

生成命令结束后会自动输出 AI 质检合格率，例如 `AI质检合格率：9/9 = 100.00%`。结果默认只用于定位需要人工复核的短文，不会让整个批次失败；需要严格阻断时添加 `--strict-ai-check`。只想生成不跑 AI 检测时添加 `--skip-ai-check`。

生成前默认会与输出目录中目标日期之前 30 天的草稿比较正文，忽略通用“接好运”收尾后检查连续重合和分片重合。发现相似时会自动切换同主题的另一正文变体；三种变体都过高时拒绝生成。可用 `--history-dir` 和 `--recent-days` 调整范围。

检查安夏短文稿，并用知识库做原标题和全库相似度保护：

```bash
python3 quality_gate.py articles/ARTICLE.md \
  --source-dir "D:\自媒体\知识库\01-公众号文章\星座公众号文章\安夏星座"
```

统一预检：

```bash
python3 preflight.py articles/ARTICLE.md \
  --source-dir "D:\自媒体\知识库\01-公众号文章\星座公众号文章\安夏星座" \
  --release
```

日运稿发布前使用：

```bash
python3 preflight.py articles/DAILY_FORTUNE.md \
  --profile daily_fortune \
  --release
```

`anxia_short` 面向 120-260 个中文字符的短平快稿件，允许 300-450 字扩展稿；不强制配图和二级小标题。强刺激词允许使用并提示复核；默认拦截普通原标题复用，`--allow-hot-titles` 或 `--mode hot-source` 可放行热标题。连续 30 字相同、18 字分片重合率达到 5% 仍会驳回。

`daily_fortune` 面向十二星座日运：标题 14-36 个可见字符，正文 700-1400 个中文字符，4 个二级小标题（火象、土象、风象、水象）和 14-16 个正文段落；默认包含 12 张本地 SVG 信息卡，质检会校验本地图片是否存在及尺寸是否达标。

发布级预检默认要求有效的编辑记录，并会让 `corpus_style` 稿件带上 `--source-dir` 做全库原创度检查。历史草稿可临时使用 `--allow-untracked`，但新稿不建议跳过记录。自动 AIGC 检测默认是复核提示；确需把它作为硬门槛时添加 `--strict-ai`。

手工创建或更新一篇独立稿的编辑记录：

```bash
python3 content_record.py create articles/ARTICLE.md \
  --source-mode independent \
  --scheduled-for 2026-07-28 --slot 1 \
  --sign 天秤 --theme 关系/性格 \
  --angle "从回应是否对等切入" \
  --title-candidate "天秤别再替沉默找理由" \
  --title-candidate "天秤最累的关系，是总要自己解释" \
  --title-candidate "天秤该把感受放回优先级了" \
  --variant-key stop-explaining \
  --hook "总是你先解释和缓和" \
  --focus "看真实回应，不替沉默找理由" \
  --closing "把真心留给愿意回应的人"
```

发布后记录表现并查看复盘：

```bash
python3 performance_tracker.py record articles/ARTICLE.md \
  --impressions 10000 --reads 1800 --likes 96 \
  --shares 21 --comments 14 --follows 8 \
  --title-variant title-2 \
  --opening-variant detail-observation
python3 performance_tracker.py report
python3 performance_tracker.py postmortem
```

`--title-variant` 和 `--opening-variant` 不填时使用编辑记录里的默认版本。`postmortem` 在至少 5 篇有效样本后，以阅读率 40% + 互动率 60% 的账号中位表现为基线，默认只收录综合表现达到基线 1.5 倍的文章，输出选题、标题公式、开头版本、正文变体和发布时间。

发布级预检可运行本地中文 AIGC 检测器：

```bash
../.venv/bin/pip install -r requirements-ai-detector.txt
../.venv/bin/python preflight.py articles/ARTICLE.md \
  --source-dir "D:\自媒体\知识库\01-公众号文章\星座公众号文章\安夏星座" \
  --release
```

默认模型是 MIT 许可的
[`AnxForever/chinese-ai-detector-bert`](https://huggingface.co/AnxForever/chinese-ai-detector-bert)。
检测结果只是编辑风险信号，不是作者身份证明。只有显式传入 `--strict-ai` 或 `--strict-ai-check` 时才作为阻断条件。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

默认只生成本地短文草稿，不自动调用公众号发布接口。发布前仍要做事实、原创度和人工阅读复核。
