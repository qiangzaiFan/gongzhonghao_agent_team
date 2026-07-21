#!/usr/bin/env python3
"""Optional audit records for manual Tencent Zhuque checks."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


HUMAN_MIN = 80.0
AI_MAX = 10.0
MAX_ROUNDS = 3


def load_record(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "provider": "Tencent Zhuque (manual)", "rounds": []}
    return json.loads(path.read_text(encoding="utf-8"))


def latest_errors(path: Path) -> list[str]:
    if not path.is_file():
        return [f"朱雀记录不存在：{path}"]
    try:
        data = load_record(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"朱雀记录无效：{exc}"]
    rounds = data.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        return ["朱雀记录没有检测轮次"]
    latest = rounds[-1]
    errors: list[str] = []
    if len(rounds) > MAX_ROUNDS:
        errors.append(f"朱雀检测已超过 {MAX_ROUNDS} 轮，应转人工作者深改")
    total = sum(float(latest.get(key, 0)) for key in ("human", "suspected", "ai"))
    if abs(total - 100.0) > 0.2:
        errors.append(f"最新一轮三项比例合计为 {total:.2f}%，应约等于 100%")
    if float(latest.get("human", 0)) < HUMAN_MIN:
        errors.append(f"人类创作 {latest.get('human')}% 低于 {HUMAN_MIN}%")
    if float(latest.get("ai", 100)) > AI_MAX:
        errors.append(f"AI 生成 {latest.get('ai')}% 高于 {AI_MAX}%")
    report = Path(str(latest.get("report", ""))).expanduser()
    if not report.is_absolute():
        report = (path.parent / report).resolve()
    if not report.is_file():
        errors.append(f"朱雀报告截图不存在：{report}")
    return errors


def record_round(args: argparse.Namespace) -> int:
    values = [args.human, args.suspected, args.ai]
    if any(value < 0 or value > 100 for value in values):
        print("比例必须在 0-100 之间", file=sys.stderr)
        return 1
    if abs(sum(values) - 100.0) > 0.2:
        print("人类、疑似、AI 三项比例必须合计为 100%", file=sys.stderr)
        return 1
    report = args.report.expanduser().resolve()
    if not report.is_file():
        print(f"报告截图不存在：{report}", file=sys.stderr)
        return 1
    try:
        data = load_record(args.record)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"无法读取朱雀记录：{exc}", file=sys.stderr)
        return 1
    rounds = data.setdefault("rounds", [])
    if len(rounds) >= MAX_ROUNDS:
        print(f"已有 {MAX_ROUNDS} 轮记录，请转人工作者深改", file=sys.stderr)
        return 1
    rounds.append(
        {
            "round": len(rounds) + 1,
            "detected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "human": args.human,
            "suspected": args.suspected,
            "ai": args.ai,
            "report": str(report),
            "notes": args.notes,
        }
    )
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = latest_errors(args.record)
    print(f"已写入朱雀第 {len(rounds)} 轮记录：{args.record}")
    if errors:
        print("朱雀人工检测未通过：")
        print("\n".join(f"- {item}" for item in errors))
        return 1
    print("朱雀人工检测通过")
    return 0


def check(args: argparse.Namespace) -> int:
    errors = latest_errors(args.record)
    if errors:
        print("朱雀人工检测未通过：")
        print("\n".join(f"- {item}" for item in errors))
        return 1
    print("朱雀人工检测通过")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="记录或检查可选的朱雀人工检测")
    subparsers = parser.add_subparsers(dest="command", required=True)
    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--record", required=True, type=Path)
    record_parser.add_argument("--human", required=True, type=float)
    record_parser.add_argument("--suspected", required=True, type=float)
    record_parser.add_argument("--ai", required=True, type=float)
    record_parser.add_argument("--report", required=True, type=Path)
    record_parser.add_argument("--notes", default="")
    record_parser.set_defaults(func=record_round)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("record", type=Path)
    check_parser.set_defaults(func=check)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
