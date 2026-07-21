#!/usr/bin/env python3
"""One-command local and release preflight for astrology articles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ai_detector import (
    DetectorUnavailable,
    default_report_path,
    detect_article,
    print_result,
    validate_report,
)
from quality_gate import format_result, parse_article, validate_article
from reference_policy import load_record, validate_record
from style_similarity import STYLE_PASS_SCORE, format_score, score_article
from zhuque_gate import latest_errors as zhuque_errors


def main() -> int:
    parser = argparse.ArgumentParser(description="星座文章发布前统一检查")
    parser.add_argument("article", type=Path)
    parser.add_argument("--source-file", type=Path)
    parser.add_argument("--reference-record", type=Path)
    parser.add_argument("--ai-report", type=Path, help="复用与当前文章摘要一致的自动检测报告")
    parser.add_argument("--zhuque-record", type=Path, help="可选的朱雀人工检测补充记录")
    parser.add_argument("--release", action="store_true", help="运行自动 AIGC 检测并按发布门槛验收")
    args = parser.parse_args()

    if not args.article.is_file():
        parser.error(f"文章不存在：{args.article}")

    source_text = None
    if args.source_file:
        if not args.source_file.is_file():
            parser.error(f"来源文件不存在：{args.source_file}")
        source_text = args.source_file.read_text(encoding="utf-8", errors="ignore")

    article = parse_article(args.article)
    result = validate_article(article, source_text=source_text)
    print(format_result(result))
    errors = list(result.errors)

    style_score = score_article(args.article, source_text=source_text)
    print(format_score(style_score))
    if args.release and style_score.total < STYLE_PASS_SCORE:
        errors.append(
            f"爆款星座风格相似度 {style_score.total}/100 低于发布线 {STYLE_PASS_SCORE}/100"
        )

    if args.reference_record:
        if not args.reference_record.is_file():
            errors.append(f"参考记录不存在：{args.reference_record}")
        else:
            record = load_record(args.reference_record)
            errors.extend(
                validate_record(
                    record,
                    args.reference_record,
                    expected_title=article.title if record.get("keep_title") is True else None,
                    check_url=False,
                )
            )

    if args.release and not errors:
        if args.ai_report:
            detector_errors = validate_report(args.article, args.ai_report)
            errors.extend(detector_errors)
            if not detector_errors:
                print(f"自动 AIGC 报告通过：{args.ai_report}")
        else:
            report_path = default_report_path(args.article)
            try:
                detection = detect_article(args.article, report_path=report_path)
            except (DetectorUnavailable, ValueError) as exc:
                errors.append(str(exc))
            else:
                print_result(detection, report_path)
                if not detection.passed:
                    errors.append("自动 AIGC 检测未达到 human≥80%、ai≤10% 的发布线")

    if args.zhuque_record:
        manual_errors = zhuque_errors(args.zhuque_record)
        errors.extend(manual_errors)
        if not manual_errors:
            print(f"朱雀人工记录通过：{args.zhuque_record}")

    if errors:
        print("统一预检未通过：", file=sys.stderr)
        for item in errors:
            print(f"- {item}", file=sys.stderr)
        return 1
    print("统一预检通过" + ("，可进入发布流程" if args.release else "，可继续编辑"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
