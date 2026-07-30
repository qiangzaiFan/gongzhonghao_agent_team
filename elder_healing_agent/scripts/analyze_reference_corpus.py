#!/usr/bin/env python3
"""Analyze local elder-healing reference articles and emit reusable style stats."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REFERENCE_DIR = Path(
    r"D:\自媒体\知识库\01-公众号文章\养老情感疗愈公众号文章\黄鹤于飞"
)
DEFAULT_REPORT = BASE_DIR / "references" / "corpus_report.md"
DEFAULT_STATS = BASE_DIR / "data" / "style_stats.json"
DEFAULT_TITLES = BASE_DIR / "data" / "reference_titles.txt"


THEME_KEYWORDS = {
    "身体与疾病": ["身体", "健康", "生病", "病", "免疫", "睡觉", "运动", "自理", "住院"],
    "情绪与内耗": ["情绪", "生气", "内耗", "心态", "快乐", "想开", "释怀", "堵心"],
    "钱与底气": ["钱", "赚钱", "存款", "经济", "退休金", "底气", "靠山"],
    "子女与家庭": ["子女", "孩子", "儿女", "家人", "亲人", "父母", "老伴"],
    "关系与边界": ["关系", "朋友", "亲戚", "善良", "底线", "欺负", "小人", "社交"],
    "独处与自渡": ["自己", "独处", "沉默", "少管", "自渡", "清净", "看淡"],
}

TITLE_STARTERS = [
    "人老了",
    "人到老年",
    "人活着",
    "人这一生",
    "50岁以后",
    "60岁以后",
    "真正",
    "永远",
    "不要",
    "千万",
    "当你",
    "有钱",
    "无论",
    "最好的",
]


@dataclass
class Article:
    path: Path
    date: str
    title: str
    cjk_length: int


def cjk_len(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def title_from_path(path: Path) -> tuple[str, str]:
    stem = path.stem
    match = re.match(r"(\d{4}-\d{2}-\d{2})\s+-\s+(.+)", stem)
    if match:
        return match.group(1), match.group(2).strip()
    return "", stem.strip()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def load_articles(reference_dir: Path) -> list[Article]:
    articles: list[Article] = []
    for path in sorted(reference_dir.rglob("*.md")):
        date, title = title_from_path(path)
        text = read_text(path)
        articles.append(Article(path=path, date=date, title=title, cjk_length=cjk_len(text)))
    return articles


def percentile(values: list[int], ratio: float) -> int:
    if not values:
        return 0
    values = sorted(values)
    index = round((len(values) - 1) * ratio)
    return values[index]


def theme_coverage(articles: list[Article]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for theme, keywords in THEME_KEYWORDS.items():
        matched = []
        keyword_counts = Counter()
        for article in articles:
            if any(keyword in article.title for keyword in keywords):
                matched.append(article.title)
            for keyword in keywords:
                if keyword in article.title:
                    keyword_counts[keyword] += 1
        result[theme] = {
            "count": len(matched),
            "coverage": round(len(matched) / len(articles), 4) if articles else 0,
            "top_keywords": keyword_counts.most_common(8),
            "sample_titles": matched[-8:],
        }
    return result


def starter_stats(articles: list[Article]) -> list[tuple[str, int]]:
    counts = Counter()
    for article in articles:
        matched = False
        for starter in TITLE_STARTERS:
            if article.title.startswith(starter):
                counts[starter] += 1
                matched = True
                break
        if not matched:
            counts[article.title[:4]] += 1
    return counts.most_common(20)


def build_stats(articles: list[Article], reference_dir: Path) -> dict[str, object]:
    lengths = [article.cjk_length for article in articles]
    dates = [article.date for article in articles if article.date]
    return {
        "reference_dir": str(reference_dir),
        "article_count": len(articles),
        "date_min": min(dates) if dates else "",
        "date_max": max(dates) if dates else "",
        "cjk_length": {
            "min": min(lengths) if lengths else 0,
            "p25": percentile(lengths, 0.25),
            "median": int(statistics.median(lengths)) if lengths else 0,
            "p75": percentile(lengths, 0.75),
            "max": max(lengths) if lengths else 0,
            "average": round(statistics.mean(lengths), 1) if lengths else 0,
        },
        "theme_coverage": theme_coverage(articles),
        "title_starters": starter_stats(articles),
        "latest_titles": [article.title for article in articles[-25:]],
    }


def write_report(stats: dict[str, object], report_path: Path) -> None:
    theme_stats = stats["theme_coverage"]
    lines = [
        "# 养老疗愈参考语料分析报告",
        "",
        "此报告由 `scripts/analyze_reference_corpus.py` 生成，用于辅助主编和写手理解参考语料的高层规律。报告只用于原创选题和风格抽象，不可用于搬运原文。",
        "",
        "## 总览",
        "",
        f"- 参考目录：`{stats['reference_dir']}`",
        f"- 文章数量：{stats['article_count']}",
        f"- 时间范围：{stats['date_min']} 至 {stats['date_max']}",
        "",
        "## 篇幅分布",
        "",
    ]
    length = stats["cjk_length"]
    for key in ("min", "p25", "median", "p75", "max", "average"):
        lines.append(f"- {key}: {length[key]}")

    lines.extend(["", "## 主题覆盖", ""])
    for theme, data in theme_stats.items():
        lines.append(f"### {theme}")
        lines.append("")
        lines.append(f"- 命中标题数：{data['count']}")
        lines.append(f"- 覆盖率：{data['coverage']:.1%}")
        if data["top_keywords"]:
            joined = "、".join(f"{item[0]}({item[1]})" for item in data["top_keywords"])
            lines.append(f"- 高频词：{joined}")
        lines.append("- 近期期目样本：")
        for title in data["sample_titles"]:
            lines.append(f"  - {title}")
        lines.append("")

    lines.extend(["## 标题开头分布", ""])
    for starter, count in stats["title_starters"]:
        lines.append(f"- {starter}: {count}")

    lines.extend(
        [
            "",
            "## 写作使用提示",
            "",
            "- 参考语料最强的主轴是“自己、身体、钱、健康、病、情绪、关系”。",
            "- 起号文章要保留痛点直给和短句节奏，但必须加入新生活现场、新标题和新收束动作。",
            "- 强痛点标题后，要用温柔重启型文章调节账号情绪，避免越写越怨。",
            "- 医疗、财务和亲子边界类文章只写生活建议，不写诊断、疗效承诺或投资建议。",
        ]
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_stats(stats: dict[str, object], stats_path: Path) -> None:
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_titles(articles: list[Article], titles_path: Path) -> None:
    titles_path.parent.mkdir(parents=True, exist_ok=True)
    titles = [article.title for article in articles]
    titles_path.write_text("\n".join(titles) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze elder-healing reference corpus.")
    parser.add_argument("--reference-dir", default=str(DEFAULT_REFERENCE_DIR), help="Reference article directory")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="Markdown report output path")
    parser.add_argument("--stats", default=str(DEFAULT_STATS), help="JSON stats output path")
    parser.add_argument("--titles", default=str(DEFAULT_TITLES), help="Reference title list output path")
    args = parser.parse_args()

    reference_dir = Path(args.reference_dir)
    if not reference_dir.exists():
        raise SystemExit(f"参考目录不存在：{reference_dir}")

    articles = load_articles(reference_dir)
    if not articles:
        raise SystemExit(f"参考目录没有 Markdown 文章：{reference_dir}")

    stats = build_stats(articles, reference_dir)
    write_report(stats, Path(args.report))
    write_stats(stats, Path(args.stats))
    write_titles(articles, Path(args.titles))

    print(f"analyzed={len(articles)}")
    print(f"report={Path(args.report)}")
    print(f"stats={Path(args.stats)}")
    print(f"titles={Path(args.titles)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
