#!/usr/bin/env python3
"""Score all elder-healing drafts and write a review summary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from quality_gate import analyze_article  # noqa: E402


DEFAULT_ARTICLES_DIR = BASE_DIR / "articles"
DEFAULT_REVIEW_JSON = BASE_DIR / "reviews" / "quality_summary.json"
DEFAULT_REVIEW_MD = BASE_DIR / "reviews" / "quality_summary.md"


def markdown_files(directory: Path) -> list[Path]:
    return [path for path in sorted(directory.rglob("*.md")) if path.name != ".gitkeep"]


def write_markdown(reports: list[dict], output: Path) -> None:
    lines = [
        "# 养老疗愈文章质检汇总",
        "",
        "此汇总只覆盖 `quality_gate.py` 的结构、风险和原创距离评分。发布前还必须逐篇运行：",
        "",
        "```bash",
        "python elder_healing_agent/ai_detector.py elder_healing_agent/articles/ARTICLE.md",
        "```",
        "",
        "| 文件 | 分数 | 状态 | 风险 | 标题 |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for report in reports:
        path = Path(report["path"])
        lines.append(
            f"| `{path.name}` | {report['score']} | {report['status']} | "
            f"{report['risk_level']} | {report['title']} |"
        )

    failed = [report for report in reports if report["status"] != "passed"]
    if failed:
        lines.extend(["", "## 需要返工", ""])
        for report in failed:
            path = Path(report["path"])
            lines.append(f"### {path.name}")
            lines.append("")
            for error in report["errors"]:
                lines.append(f"- ERROR: {error}")
            for warning in report["warnings"][:8]:
                lines.append(f"- WARN: {warning}")
            lines.append("")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Score all elder-healing drafts.")
    parser.add_argument("--articles-dir", default=str(DEFAULT_ARTICLES_DIR), help="Article directory")
    parser.add_argument("--json-out", default=str(DEFAULT_REVIEW_JSON), help="JSON summary path")
    parser.add_argument("--md-out", default=str(DEFAULT_REVIEW_MD), help="Markdown summary path")
    parser.add_argument("--skip-reference-check", action="store_true", help="Skip reference corpus checks")
    args = parser.parse_args()

    articles_dir = Path(args.articles_dir)
    reports = [
        analyze_article(
            path,
            articles_dir=articles_dir,
            skip_reference_check=args.skip_reference_check,
        )
        for path in markdown_files(articles_dir)
    ]

    json_out = Path(args.json_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(reports, Path(args.md_out))

    passed = sum(1 for report in reports if report["status"] == "passed")
    print(f"articles={len(reports)} passed={passed} failed={len(reports)-passed}")
    print(f"json={json_out}")
    print(f"markdown={Path(args.md_out)}")
    return 0 if passed == len(reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
