# 安夏星座短文号工作区

本目录用于生产“安夏式星座短文号”本地草稿：每日 3 篇、短平快、标题强钩子、正文稳健原创。旧的星座情绪长文号规则、白桃长文风格和固定配图要求已停用。

## 工作区内容

- `CLAUDE.md`：安夏短文号主编职责和操作约定。
- `.claude/agents/astrology-writer.md`：安夏短文写手 Agent。
- `specs/anxia_style.md`：安夏短文风格画像。
- `specs/`：账号定位、文章质量、来源和工作流规则。
- `articles/`：本地 Markdown 短文草稿。
- `anxia_analyze.py`：分析安夏知识库语料。
- `anxia_calendar.py`：生成每日 3 篇选题排期。
- `quality_gate.py`：默认使用 `anxia_short` 质检 profile。
- `sources/`：临时抓取的来源正文，已被根目录 `.gitignore` 忽略。

## 常用命令

分析安夏星座知识库，生成近期短文号运营画像：

```bash
python3 anxia_analyze.py \
  "D:\自媒体\知识库\01-公众号文章\星座公众号文章\安夏星座" \
  --since 2026-06-01
```

生成安夏短文号 7 天排期，默认每日 3 篇：

```bash
python3 anxia_calendar.py --days 7 --daily 3 --profile anxia_short
```

一步生成 3 天文章量（默认每天 3 篇，共 9 篇），并自动质检：

```bash
python3 anxia_generate.py --days 3
```

一步生成 7 天文章量（默认每天 3 篇，共 21 篇），并自动质检：

```bash
python3 anxia_generate.py --days 7
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

默认知识库路径为 `D:\自媒体\知识库\01-公众号文章\星座公众号文章\安夏星座`，默认模式为 `viral-safe`，默认每日 `3` 篇。若当天文件已存在，会自动跳过；需要重写已存在草稿时添加 `--overwrite`。

生成命令结束后会自动输出 AI 质检合格率，例如 `AI质检合格率：9/9 = 100.00%`。发布线为 `human≥90%、ai≤10%`。只想生成不跑 AI 检测时添加 `--skip-ai-check`。

检查安夏短文稿，并用知识库做原标题和全库相似度保护：

```bash
python3 quality_gate.py articles/ARTICLE.md \
  --source-dir "D:\自媒体\知识库\01-公众号文章\星座公众号文章\安夏星座"
```

统一预检：

```bash
python3 preflight.py articles/ARTICLE.md \
  --source-dir "D:\自媒体\知识库\01-公众号文章\星座公众号文章\安夏星座"
```

`anxia_short` 面向 120-260 个中文字符的短平快稿件，允许 300-450 字扩展稿；不强制配图和二级小标题。强刺激词允许使用并提示复核；默认拦截普通原标题复用，`--allow-hot-titles` 或 `--mode hot-source` 可放行热标题。连续 30 字相同、18 字分片重合率达到 5% 仍会驳回。

如需抓取可访问的参考正文：

```bash
python3 source_extract.py "https://example.com/article"
```

发布级预检可运行本地中文 AIGC 检测器：

```bash
../.venv/bin/pip install -r requirements-ai-detector.txt
../.venv/bin/python preflight.py articles/ARTICLE.md \
  --source-dir "D:\自媒体\知识库\01-公众号文章\星座公众号文章\安夏星座" \
  --release
```

默认模型是 MIT 许可的
[`AnxForever/chinese-ai-detector-bert`](https://huggingface.co/AnxForever/chinese-ai-detector-bert)。
检测结果只是编辑风险信号，不是作者身份证明，也不等同于腾讯朱雀。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

默认只生成本地短文草稿，不自动调用公众号发布接口。发布前仍要做事实、原创度和人工阅读复核。
