#!/usr/bin/env python3
"""One-command local and release preflight for astrology articles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ai_detector import (
    ANXIA_SHORT_MIN_TOTAL_CHARS,
    DEFAULT_MIN_TOTAL_CHARS,
    DetectorUnavailable,
    default_report_path,
    detect_article,
    print_result,
    validate_report,
)
from content_record import DEFAULT_RECORD_DIR, default_record_path, validate_record
from quality_gate import DEFAULT_PROFILE, PROFILES, format_result, load_source_dir, parse_article, validate_article


def release_min_total_chars(profile: str, override: int | None) -> int:
    if override is not None:
        return override
    if profile == "anxia_short":
        return ANXIA_SHORT_MIN_TOTAL_CHARS
    return DEFAULT_MIN_TOTAL_CHARS


def main() -> int:
    parser = argparse.ArgumentParser(description="星座文章发布前统一检查")
    parser.add_argument("article", type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILES), default=DEFAULT_PROFILE)
    parser.add_argument("--min-total-chars", type=int, help="自动 AIGC 检测最小正文字符数")
    parser.add_argument("--source-file", type=Path)
    parser.add_argument("--source-dir", type=Path, help="可选：安夏知识库目录，用于原标题和全库原创度检查")
    parser.add_argument("--allow-hot-titles", action="store_true", help="允许复用知识库中重复出现过的热标题")
    parser.add_argument("--hot-title-min-count", type=int, default=2, help="热标题最少重复次数，默认 2")
    parser.add_argument("--allow-all-source-titles", action="store_true", help="允许复用任意知识库原标题")
    parser.add_argument("--editorial-record", type=Path, help="选题、来源和正文变体的编辑记录")
    parser.add_argument("--record-dir", type=Path, default=DEFAULT_RECORD_DIR)
    parser.add_argument("--allow-untracked", action="store_true", help="允许旧稿在未绑定编辑记录时发布")
    parser.add_argument("--ai-report", type=Path, help="复用与当前文章摘要一致的自动检测报告")
    parser.add_argument("--release", action="store_true", help="运行自动 AIGC 检测并按发布门槛验收")
    parser.add_argument("--strict-ai", action="store_true", help="将自动 AIGC 结果作为发布阻断条件")
    args = parser.parse_args()

    if not args.article.is_file():
        parser.error(f"文章不存在：{args.article}")

    source_text = None
    if args.source_file:
        if not args.source_file.is_file():
            parser.error(f"来源文件不存在：{args.source_file}")
        source_text = args.source_file.read_text(encoding="utf-8", errors="ignore")

    forbidden_titles = None
    source_texts = None
    if args.source_dir:
        try:
            forbidden_titles, source_texts = load_source_dir(
                args.source_dir,
                allow_hot_titles=args.allow_hot_titles,
                hot_title_min_count=args.hot_title_min_count,
                allow_all_source_titles=args.allow_all_source_titles,
            )
        except FileNotFoundError as exc:
            parser.error(str(exc))

    article = parse_article(args.article)
    result = validate_article(
        article,
        source_text=source_text,
        profile=args.profile,
        forbidden_titles=forbidden_titles,
        source_texts=source_texts,
    )
    print(format_result(result))
    errors = list(result.errors)

    print(f"质检 profile：{args.profile}")

    if args.release and not args.allow_untracked:
        record_path = args.editorial_record or default_record_path(args.article, args.record_dir)
        record_errors = validate_record(
            args.article,
            record_path,
            source_dir=args.source_dir,
            require_corpus_check=True,
        )
        if record_errors:
            errors.extend(record_errors)
        else:
            print(f"编辑记录通过：{record_path}")

    if args.release and not errors:
        ai_notes: list[str] = []
        if args.ai_report:
            detector_errors = validate_report(args.article, args.ai_report)
            ai_notes.extend(detector_errors)
            if not detector_errors:
                print(f"自动 AIGC 报告通过：{args.ai_report}")
        else:
            report_path = default_report_path(args.article)
            try:
                detection = detect_article(
                    args.article,
                    min_total_chars=release_min_total_chars(args.profile, args.min_total_chars),
                    report_path=report_path,
                )
            except (DetectorUnavailable, ValueError) as exc:
                ai_notes.append(str(exc))
            else:
                print_result(detection, report_path)
                if not detection.passed:
                    ai_notes.append("自动 AIGC 检测未达到 human≥90%、ai≤10% 的发布线")
        if ai_notes:
            print("自动 AIGC 复核提示：")
            for note in ai_notes:
                print(f"- {note}")
            if args.strict_ai:
                errors.extend(ai_notes)

    if errors:
        print("统一预检未通过：", file=sys.stderr)
        for item in errors:
            print(f"- {item}", file=sys.stderr)
        return 1

    print("统一预检通过" + ("，可进入发布流程" if args.release else "，可继续编辑"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
