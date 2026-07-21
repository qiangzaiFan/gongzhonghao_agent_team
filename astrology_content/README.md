# 星座公众号原创工作区

本目录用于生产“星座 × 情绪 × 关系”公众号文章。爆款文章只是选题研究样本，不做逐段换词或搬运。

## 工作区内容

- `CLAUDE.md`：主编职责和操作约定。
- `.claude/agents/astrology-writer.md`：星座专题写手 Agent。
- `specs/`：账号定位、文章质量、来源和工作流规则。
- `articles/`：本地 Markdown 草稿。
- `images/`：本账号的原创配图。
- `benchmarks/`：只保存来源元数据和结构分析，不保存来源全文。
- `reviews/zhuque/`：朱雀人工检测记录和报告截图。
- `sources/`：临时抓取的来源正文，已被根目录 `.gitignore` 忽略。

## 常用命令

抓取可访问的参考正文：

```bash
python3 source_extract.py "https://example.com/article"
```

登记参考文章：

```bash
python3 reference_policy.py register \
  --source-url "https://example.com/article" \
  --source-title "原标题" \
  --read-count 100000 \
  --proof /absolute/path/to/proof.png \
  --verified-at 2026-07-21 \
  --keep-title
```

`--keep-title` 只在来源链接可访问、阅读数不少于 100000、证明文件存在且标题一致时生效。条件不足会终止，不会悄悄换标题。网络验证因防爬失败时，可由主编核验后使用 `--skip-url-check`，并在记录中保留证明。

本地文章质检：

```bash
python3 quality_gate.py articles/ARTICLE.md
python3 quality_gate.py articles/ARTICLE.md --source-file sources/SOURCE.txt
```

评估与爆款星座样本的抽象风格相似度，并把来源文字重合率分开报告：

```bash
python3 style_similarity.py articles/ARTICLE.md --profile specs/benchmark_style.md
python3 style_similarity.py articles/ARTICLE.md --source-file sources/SOURCE.txt
```

风格分从标题代入、开头判断、评论而非故事、性格机制与关系表现、星座差异、手机阅读节奏和结尾收束七个维度汇总，发布线为 75/100。高风格分是目标，高文字重合率则会被原创度门禁驳回。

安装自动中文 AIGC 检测器：

```bash
../.venv/bin/pip install -r requirements-ai-detector.txt
```

自动检测文章：

```bash
../.venv/bin/python ai_detector.py articles/ARTICLE.md
```

默认模型是 MIT 许可的
[`AnxForever/chinese-ai-detector-bert`](https://huggingface.co/AnxForever/chinese-ai-detector-bert)。
工具把正文分段检测，汇总为 human / suspected / ai 三档，并保存包含文章 SHA-256 的报告。文章修改后旧报告会自动失效。

发布级预检（会自动运行 AIGC 模型）：

```bash
../.venv/bin/python preflight.py articles/ARTICLE.md \
  --source-file sources/SOURCE.txt \
  --release
```

发布门槛为 human 不低于 80%、ai 不高于 10%。该结果是编辑风险信号，不是作者身份证明，也不与腾讯朱雀等价。

如需偶尔用腾讯朱雀做人工抽检，可登记结果：

```bash
python3 zhuque_gate.py record \
  --record reviews/zhuque/ARTICLE.json \
  --human 84 --suspected 9 --ai 7 \
  --report /absolute/path/to/zhuque-report.png \
  --notes "官方网页第一轮检测"
```

朱雀记录是可选的附加门禁；传入 `--zhuque-record` 时，必须同样满足 human≥80%、ai≤10% 且报告截图存在。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

默认只生成本地草稿，本目录第一版不自动调用公众号发布接口。本地模型与所有 AIGC 检测器一样可能误判，发布前仍要做事实、原创度和人工阅读复核。
