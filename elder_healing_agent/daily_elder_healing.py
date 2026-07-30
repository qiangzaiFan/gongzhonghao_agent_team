#!/usr/bin/env python3
"""Create daily topic cards and writer prompts for the elder-healing account."""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CALENDAR_PATH = BASE_DIR / "specs" / "topic_calendar_30d.md"
PROMPTS_DIR = BASE_DIR / "prompts"
ARTICLES_DIR = BASE_DIR / "articles"


def slugify(text: str, fallback: str) -> str:
    ascii_text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    if ascii_text:
        return ascii_text[:60]
    mapping = {
        "身体": "body",
        "生病": "illness",
        "情绪": "emotion",
        "子女": "children",
        "孩子": "children",
        "钱": "money",
        "关系": "relationships",
        "独处": "solitude",
        "晚年": "later-life",
        "退休": "retirement",
        "重启": "restart",
    }
    parts = [value for key, value in mapping.items() if key in text]
    return "-".join(dict.fromkeys(parts)) or fallback


def parse_calendar(path: Path = CALENDAR_PATH) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line or "天数" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        if not cells[0].isdigit():
            continue
        rows.append({"day": cells[0], "topic": cells[1], "pillar": cells[2]})
    return rows


def pick_topics(count: int, calendar_day: int | None, topic: str | None) -> list[dict[str, str]]:
    if topic:
        return [{"day": "custom", "topic": topic, "pillar": "待主编判断"}]

    rows = parse_calendar()
    if calendar_day is not None:
        selected = [row for row in rows if int(row["day"]) >= calendar_day]
    else:
        today = datetime.now()
        start = ((today.day - 1) % max(len(rows), 1)) + 1
        selected = [row for row in rows if int(row["day"]) >= start] + [row for row in rows if int(row["day"]) < start]
    return selected[:count]


def build_topic_card(row: dict[str, str]) -> str:
    topic = row["topic"]
    pillar = row["pillar"]
    return f"""# 养老疗愈选题卡

## 基本信息

- 标题方向：{topic}
- 主支柱：{pillar}
- 目标读者：50 岁以后，正在被身体、子女、钱、关系或情绪消耗的人
- 文章长度：700-1100 字

## 读者痛点

- 表层痛点：被生活、人情或身体提醒，不能再一直硬扛
- 深层害怕：怕身体垮，怕钱不够，怕子女嫌，怕晚年没有退路
- 读者想听到但不敢说的话：我也该先照顾自己了

## 生活现场

- 场景：夜里醒来、饭桌前、孩子电话后、体检单前、退休金到账时任选一个
- 物件：药盒、饭碗、水杯、手机、体检单、医保卡、厨房灯、退休金短信
- 身体感：胸口堵、睡不踏实、饭吃不香、坐在床边缓一缓
- 一句可能出现的对话：先别忙了，你自己身体也要紧
- 插图方向：开头情绪入口图、中段冲突/清醒图、结尾疗愈动作图，各 1 张原创漫画插图

## 核心判断

- 最想让读者记住的一句话：晚年真正要守住的，是自己的身体、钱和心气
- 需要避开的极端表达：不要骂子女，不要医学断言，不要投资建议，不要仇恨式断亲

## 文章走向

1. 开头如何击中：用一句清醒判断或一个具体生活现场切入
2. 中段如何展开：写长期硬扛、憋气、舍不得和怕拖累人的真实心理
3. 最后如何疗愈：把读者带回今天能做的小动作

## 结尾动作

- 读者今天就能做的一件小事：早点关灯、把手机放远、给自己煮一碗热饭、下楼走一圈

## 禁区

- 不写医学承诺。
- 不写投资建议。
- 不煽动亲子仇恨。
- 不复用参考博主标题和原句。
"""


def build_writer_prompt(row: dict[str, str], article_path: Path) -> str:
    card = build_topic_card(row)
    return f"""请使用 `elder_healing_agent/.claude/agents/elder-healing-writer.md` 作为写手 agent，按下面选题卡写一篇原创养老疗愈公众号文章。

保存路径：`{article_path}`

硬性要求：

- frontmatter 只写 `title`。
- 正文 700-1100 个中文字符。
- 前 120 字内击中痛点或出现具体生活现场。
- 至少出现 3 个生活物件或动作。
- 写完后必须运行插图规划，为文章插入 3 张原创漫画插图位。
- 结尾停在一个具体动作上。
- 不复用黄鹤于飞、悦漫先生的标题、原句、署名、案例和段落。
- 不写医学承诺、投资建议、亲子仇恨。

{card}
"""


def write_prompt(row: dict[str, str], index: int) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    slug = slugify(row["topic"], f"elder-topic-{row['day']}-{index}")
    article_path = ARTICLES_DIR / f"{timestamp}_{slug}.md"
    prompt_path = PROMPTS_DIR / f"{timestamp}_{slug}.prompt.md"
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(build_writer_prompt(row, article_path), encoding="utf-8")
    return prompt_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create elder-healing writer prompts from calendar topics.")
    parser.add_argument("--count", type=int, default=1, help="Number of prompts to create")
    parser.add_argument("--calendar-day", type=int, help="Start from this 30-day calendar day")
    parser.add_argument("--topic", help="Custom topic instead of the 30-day calendar")
    args = parser.parse_args()

    if args.count < 1:
        raise SystemExit("--count must be >= 1")

    rows = pick_topics(args.count, args.calendar_day, args.topic)
    for index, row in enumerate(rows, start=1):
        prompt_path = write_prompt(row, index)
        print(f"created={prompt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
