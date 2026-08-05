#!/usr/bin/env python3
"""Summarize the local BaiTao weekly-horoscope corpus."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from statistics import mean, median

from baitao_weekly import WEEKLY_SOURCE_DIR


IMAGE_RE = re.compile(r"!\[[^]]*\]\([^)]+\)")
POSITION_RE = re.compile(r"^(\d+)")
EVENT_RE = re.compile(r"(?m)^\s*[\u2460-\u2466]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def corpus_files(source_dir: Path) -> list[Path]:
    files = [path for path in source_dir.glob("*.md") if POSITION_RE.match(path.name)]
    return sorted(files, key=lambda path: int(POSITION_RE.match(path.name).group(1)))  # type: ignore[union-attr]


def summarize(source_dir: Path, *, recent: int = 12) -> str:
    files = corpus_files(source_dir)
    if not files:
        raise FileNotFoundError(f"未找到白桃星座周运语料：{source_dir}")
    selected = files[-recent:] if recent > 0 else files
    texts = [path.read_text(encoding="utf-8", errors="strict") for path in selected]
    cjk_counts = [len(CJK_RE.findall(IMAGE_RE.sub("", text))) for text in texts]
    image_counts = [len(IMAGE_RE.findall(text)) for text in texts]
    event_counts = [len(EVENT_RE.findall(text)) for text in texts]
    return "\n".join(
        (
            f"白桃星座周运语料：全量 {len(files)} 篇，本次分析 {len(selected)} 篇",
            f"文本中文字符：中位 {median(cjk_counts):g}，平均 {mean(cjk_counts):.1f}，范围 {min(cjk_counts)}-{max(cjk_counts)}",
            f"图片：中位 {median(image_counts):g}，平均 {mean(image_counts):.1f}，范围 {min(image_counts)}-{max(image_counts)}",
            f"重点星象：中位 {median(event_counts):g}，平均 {mean(event_counts):.1f}，范围 {min(event_counts)}-{max(event_counts)}",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="分析白桃星座周运知识库")
    parser.add_argument("source_dir", nargs="?", type=Path, default=WEEKLY_SOURCE_DIR)
    parser.add_argument("--recent", type=int, default=12)
    args = parser.parse_args()
    try:
        print(summarize(args.source_dir, recent=args.recent))
    except (FileNotFoundError, UnicodeError) as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
