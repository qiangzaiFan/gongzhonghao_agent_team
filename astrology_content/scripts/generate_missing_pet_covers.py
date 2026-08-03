#!/usr/bin/env python3
"""Generate missing ComfyUI pet covers for existing short astrology drafts."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from anxia_corpus import DEFAULT_CORPUS_DIR  # noqa: E402
from anxia_generate import (  # noqa: E402
    DEFAULT_COMFY_ENDPOINT,
    DEFAULT_COMFY_PROFILE,
    PET_COVER_ASSET_DIR,
    build_drafts,
    write_pet_cover_with_comfyui,
)
from quality_gate import parse_article  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="为已有单星座短文补齐治愈系萌宠封面")
    parser.add_argument("--start", required=True, help="起始日期 YYYY-MM-DD")
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument("--daily", type=int, default=2)
    parser.add_argument("--endpoint", default=DEFAULT_COMFY_ENDPOINT)
    parser.add_argument("--profile", default=DEFAULT_COMFY_PROFILE, choices=("flux2_klein",))
    parser.add_argument("--max-wait", type=int, default=600)
    parser.add_argument("--poll-seconds", type=float, default=1.5)
    parser.add_argument("--retry-token", help="重试时改变提示词与稳定种子，避免复现同一张瑕疵图")
    args = parser.parse_args()

    drafts = build_drafts(
        date.fromisoformat(args.start),
        args.daily,
        DEFAULT_CORPUS_DIR,
        days=args.days,
        recent_drafts=[],
    )
    for draft in drafts:
        pattern = f"{draft.item.day:%Y%m%d}_{draft.item.slot:02d}_*.md"
        matches = sorted((BASE_DIR / "articles").glob(pattern))
        if len(matches) != 1:
            raise RuntimeError(f"{pattern} 应匹配 1 篇文章，实际为 {len(matches)} 篇")
        article_path = matches[0]
        current = replace(draft, title_override=parse_article(article_path).title)
        if args.retry_token:
            current = replace(
                current,
                item=replace(
                    current.item,
                    angle=f"{current.item.angle} Retry variation: {args.retry_token}; absolutely no text-like marks.",
                ),
            )
        cover_path = write_pet_cover_with_comfyui(
            current,
            asset_dir=PET_COVER_ASSET_DIR,
            endpoint=args.endpoint,
            model_profile=args.profile,
            max_wait=args.max_wait,
            poll_seconds=args.poll_seconds,
        )
        print(f"已生成：{cover_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
