#!/usr/bin/env python3
"""Create a complete title-writer-editor production packet."""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

from daily_elder_healing import build_topic_card, parse_calendar, slugify


BASE_DIR = Path(__file__).resolve().parent
ARTICLES_DIR = BASE_DIR / "articles"
PIPELINES_DIR = BASE_DIR / "runs"


def pick_calendar_topic(day: int) -> dict[str, str]:
    rows = parse_calendar()
    for row in rows:
        if int(row["day"]) == day:
            return row
    raise SystemExit(f"30 天游题表里没有第 {day} 天")


def build_title_task(topic: str, pillar: str) -> str:
    return f"""# 标题官任务

请调用 `elder-title-editor`，为下面主题生成起号标题组和选题卡。

主题：{topic}
主支柱：{pillar}

要求：

- 输出 12 个标题，分为强痛点型、温柔重启型、收藏转发型、评论共鸣型。
- 每个标题附 1 句钩子说明。
- 选择最推荐的 1 个标题，并生成完整选题卡。
- 不复用黄鹤于飞、悦漫先生原题。
- 不使用医疗断言、投资建议、亲子仇恨。
"""


def build_writer_task(topic: str, pillar: str, article_path: Path) -> str:
    row = {"day": "pipeline", "topic": topic, "pillar": pillar}
    card = build_topic_card(row)
    return f"""# 写手任务

请调用 `elder-healing-writer`，根据标题官最终选题卡写一篇原创养老疗愈公众号文章。

保存路径：`{article_path}`

最低要求：

- frontmatter 只写 `title`。
- 正文 700-1100 个中文字符。
- 前 120 字内击中痛点或出现具体生活现场。
- 至少出现 3 个生活物件或动作。
- 结尾停在一个具体动作上。
- 不复用参考博主标题、原句、署名、案例和段落。
- 不写医学承诺、投资建议、亲子仇恨。

备用选题卡：

{card}
"""


def build_editor_task(article_path: Path) -> str:
    return f"""# 主编二审任务

请调用 `elder-chief-editor`，审读并润色这篇文章：

文章路径：`{article_path}`

二审重点：

- 标题是否过近参考博主原题。
- 开头是否在 120 字内击中读者。
- 是否有药盒、饭碗、电话、退休金、体检单、厨房灯等具体生活细节。
- 是否把读者从怨气带回自我照顾。
- 是否有医疗、财务、亲子仇恨风险。
- 结尾是否停在具体动作上。

润色后覆盖原文件，再运行：

```bash
python elder_healing_agent/scripts/plan_article_illustrations.py {article_path} --apply
python elder_healing_agent/quality_gate.py {article_path}
python elder_healing_agent/ai_detector.py {article_path}
```
"""


def build_runbook(topic: str, pillar: str, article_path: Path, run_dir: Path) -> str:
    return f"""# 养老疗愈生产包

- 主题：{topic}
- 主支柱：{pillar}
- 文章路径：`{article_path}`
- 运行目录：`{run_dir}`

## 执行顺序

1. 打开 `01-title-task.md`，调用 `elder-title-editor` 产出标题组和最终选题卡。
2. 打开 `02-writer-task.md`，调用 `elder-healing-writer` 写原创初稿并保存。
3. 打开 `03-editor-task.md`，调用 `elder-chief-editor` 二审润色。
4. 运行插图规划，插入 3 张原创漫画插图位并生成出图 prompt：

```bash
python elder_healing_agent/scripts/plan_article_illustrations.py {article_path} --apply
```

5. 按 `images/illustrations/prompts/` 的 prompt 生成 3 张原创图片，保存到文章引用的本地路径。
6. 运行质检：

```bash
python elder_healing_agent/quality_gate.py {article_path}
python elder_healing_agent/ai_detector.py {article_path}
```

7. 发布前严格确认图片文件存在：

```bash
python elder_healing_agent/quality_gate.py {article_path} --require-image-files
```

8. 若分数低于 85，按错误和警告返工；90 分以上且本地中文 AIGC 检测通过，才进入人工发布前复核。

## 发布前人工看三眼

- 有没有医学、财务、亲子冲突风险。
- 有没有像参考博主原文。
- 有没有使用悦漫先生原图、印章、署名、图中文字或可识别构图。
- 三张插图是否原创、不重复、和文章段落贴合。
- 读完后是否让人想把自己照顾好，而不是只剩怨气。
- 本地中文 AIGC 检测是否通过，报告 hash 是否对应当前正文。
"""


def create_pipeline(topic: str, pillar: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = slugify(topic, "elder-healing-topic")
    run_dir = PIPELINES_DIR / f"{timestamp}_{slug}"
    article_path = ARTICLES_DIR / f"{timestamp[:8]}_{slug}.md"
    run_dir.mkdir(parents=True, exist_ok=True)
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    (run_dir / "00-runbook.md").write_text(build_runbook(topic, pillar, article_path, run_dir), encoding="utf-8")
    (run_dir / "01-title-task.md").write_text(build_title_task(topic, pillar), encoding="utf-8")
    (run_dir / "02-writer-task.md").write_text(build_writer_task(topic, pillar, article_path), encoding="utf-8")
    (run_dir / "03-editor-task.md").write_text(build_editor_task(article_path), encoding="utf-8")
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a complete elder-healing production packet.")
    parser.add_argument("--topic", help="Custom topic")
    parser.add_argument("--pillar", default="待主编判断", help="Content pillar")
    parser.add_argument("--calendar-day", type=int, help="Use topic from 30-day calendar")
    args = parser.parse_args()

    if args.calendar_day is None and not args.topic:
        parser.error("Provide --topic or --calendar-day")

    if args.calendar_day is not None:
        row = pick_calendar_topic(args.calendar_day)
        topic = row["topic"]
        pillar = row["pillar"]
    else:
        topic = re.sub(r"\s+", " ", args.topic or "").strip()
        pillar = args.pillar

    run_dir = create_pipeline(topic, pillar)
    print(f"created={run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
