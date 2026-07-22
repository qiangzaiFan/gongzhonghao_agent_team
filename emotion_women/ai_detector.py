#!/usr/bin/env python3
"""Run the shared local Chinese AIGC detector for emotion articles.

The model implementation lives in ``astrology_content/ai_detector.py`` so the
two writing workspaces use the same labels, thresholds and report schema.
This wrapper owns emotion-specific report paths and report reuse.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ARTICLES_DIR = BASE_DIR / "articles"
REPORT_DIR = BASE_DIR / "reviews" / "auto"
SHARED_DETECTOR = ROOT_DIR / "astrology_content" / "ai_detector.py"
VENV_PYTHON = ROOT_DIR / ".venv" / "bin" / "python"
DEFAULT_MODEL = "AnxForever/chinese-ai-detector-bert"
DEFAULT_HUMAN_MIN = 80.0
DEFAULT_AI_MAX = 10.0


def resolve_article_path(value: Path) -> Path:
    path = value if value.is_absolute() else BASE_DIR / value
    return path.resolve()


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


def print_cached_result(
    report: dict[str, Any],
    report_path: Path,
    *,
    human_min: float,
    ai_max: float,
) -> int:
    ratios = report.get("ratios") or {}
    human = float(ratios.get("human", 0.0))
    suspected = float(ratios.get("suspected", 0.0))
    ai = float(ratios.get("ai", 100.0))
    passed = bool(report.get("passed")) and human >= human_min and ai <= ai_max
    print("自动 AIGC 检测：" + ("通过（复用当前报告）" if passed else "未通过（复用当前报告）"))
    print(f"human={human:.2f}%，suspected={suspected:.2f}%，ai={ai:.2f}%")
    print(f"报告：{report_path}")
    return 0 if passed else 1


def build_detector_command(
    target: Path,
    report_path: Path,
    *,
    model: str,
    human_min: float,
    ai_max: float,
) -> list[str]:
    python = VENV_PYTHON if VENV_PYTHON.is_file() else Path(sys.executable)
    return [
        str(python),
        str(SHARED_DETECTOR),
        str(target),
        "--model",
        model,
        "--human-min",
        str(human_min),
        "--ai-max",
        str(ai_max),
        "--report",
        str(report_path),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="情感文章自动 AIGC 检测门禁")
    parser.add_argument("article", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--human-min", type=float, default=DEFAULT_HUMAN_MIN)
    parser.add_argument("--ai-max", type=float, default=DEFAULT_AI_MAX)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--force", action="store_true", help="忽略当前报告并重新推理")
    args = parser.parse_args()

    article_path = resolve_article_path(args.article)
    if not article_path.is_file():
        parser.error(f"文章不存在：{article_path}")
    if not SHARED_DETECTOR.is_file():
        print(f"缺少共用检测器：{SHARED_DETECTOR}", file=sys.stderr)
        return 2
    target = article_path

    report_path = args.report or default_report_path(target)
    if not report_path.is_absolute():
        report_path = (BASE_DIR / report_path).resolve()
    if not args.force:
        current = read_current_report(
            target,
            report_path,
            model=args.model,
            human_min=args.human_min,
            ai_max=args.ai_max,
        )
        if current is not None:
            return print_cached_result(
                current,
                report_path,
                human_min=args.human_min,
                ai_max=args.ai_max,
            )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("HF_HUB_DISABLE_XET", "1")
    command = build_detector_command(
        target,
        report_path,
        model=args.model,
        human_min=args.human_min,
        ai_max=args.ai_max,
    )
    return subprocess.run(command, cwd=SHARED_DETECTOR.parent, env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
