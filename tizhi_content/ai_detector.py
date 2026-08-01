#!/usr/bin/env python3
"""体制内公众号文章的本地中文 AIGC 检测入口。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ARTICLES_DIR = BASE_DIR / "articles"
REPORT_DIR = BASE_DIR / "reviews" / "auto"
SHARED_DETECTOR = ROOT_DIR / "astrology_content" / "ai_detector.py"
DEFAULT_MODEL = "AnxForever/chinese-ai-detector-bert"
DEFAULT_HUMAN_MIN = 90.0
DEFAULT_AI_MAX = 10.0


def resolve_article_path(value: Path) -> Path:
    candidates = [value] if value.is_absolute() else [BASE_DIR / value, ROOT_DIR / value]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return candidates[0].resolve()


def default_report_path(target: Path) -> Path:
    try:
        relative = target.resolve().relative_to(ARTICLES_DIR.resolve())
        return REPORT_DIR / relative.with_suffix(".json")
    except ValueError:
        suffix = hashlib.sha256(str(target).encode("utf-8")).hexdigest()[:12]
        return REPORT_DIR / f"{target.stem}-{suffix}.json"


def article_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_current_report(
    target: Path,
    report_path: Path,
    *,
    model: str,
    human_min: float,
    ai_max: float,
) -> dict[str, Any] | None:
    if not report_path.is_file():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    thresholds = report.get("thresholds") or {}
    if report.get("article_sha256") != article_digest(target):
        return None
    if report.get("model") != model:
        return None
    if float(thresholds.get("human_min", -1)) != human_min:
        return None
    if float(thresholds.get("ai_max", -1)) != ai_max:
        return None
    return report


def print_result(report: dict[str, Any], report_path: Path, *, cached: bool) -> int:
    ratios = report.get("ratios") or {}
    human = float(ratios.get("human", 0.0))
    suspected = float(ratios.get("suspected", 0.0))
    ai = float(ratios.get("ai", 100.0))
    mean_ai = float(report.get("mean_ai_probability", 100.0))
    passed = bool(report.get("passed"))
    suffix = "（复用当前报告）" if cached else ""
    print("本地中文 AIGC 检测：" + ("通过" if passed else "未通过") + suffix)
    print(
        f"human={human:.2f}%，suspected={suspected:.2f}%，"
        f"ai={ai:.2f}%，平均 AI 概率={mean_ai:.2f}%"
    )
    print(f"报告：{report_path}")
    return 0 if passed else 1


def python_executable() -> Path:
    candidates = [
        ROOT_DIR / ".venv" / "bin" / "python",
        ROOT_DIR / ".venv" / "Scripts" / "python.exe",
    ]
    return next((path for path in candidates if path.is_file()), Path(sys.executable))


def main() -> int:
    parser = argparse.ArgumentParser(description="体制内公众号本地中文 AIGC 检测")
    parser.add_argument("article", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--human-min", type=float, default=DEFAULT_HUMAN_MIN)
    parser.add_argument("--ai-max", type=float, default=DEFAULT_AI_MAX)
    parser.add_argument("--report", type=Path, help="自定义报告路径")
    parser.add_argument("--force", action="store_true", help="忽略当前报告，重新检测")
    args = parser.parse_args()

    target = resolve_article_path(args.article)
    if not target.is_file():
        print(f"文章不存在：{target}", file=sys.stderr)
        return 2
    if not SHARED_DETECTOR.is_file():
        print(f"共享检测器不存在：{SHARED_DETECTOR}", file=sys.stderr)
        return 2

    report_path = (args.report if args.report else default_report_path(target)).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if not args.force:
        current = read_current_report(
            target,
            report_path,
            model=args.model,
            human_min=args.human_min,
            ai_max=args.ai_max,
        )
        if current is not None:
            return print_result(current, report_path, cached=True)

    command = [
        str(python_executable()),
        str(SHARED_DETECTOR),
        str(target),
        "--model",
        args.model,
        "--human-min",
        str(args.human_min),
        "--ai-max",
        str(args.ai_max),
        "--report",
        str(report_path),
    ]
    result = subprocess.run(command, cwd=ROOT_DIR, text=True)
    if result.returncode not in {0, 1}:
        return result.returncode

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(f"检测完成但报告无法读取：{report_path}", file=sys.stderr)
        return 2
    return print_result(report, report_path, cached=False)


if __name__ == "__main__":
    raise SystemExit(main())
