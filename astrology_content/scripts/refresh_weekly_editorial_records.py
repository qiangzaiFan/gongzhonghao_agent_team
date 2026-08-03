from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from anxia_corpus import DEFAULT_CORPUS_DIR
from anxia_generate import build_daily_fortune_drafts, build_drafts
from content_record import DEFAULT_RECORD_DIR, write_generated_record
from quality_gate import markdown_to_plain, parse_article


def find_article(day: date, slot: int) -> Path:
    matches = sorted((BASE_DIR / "articles").glob(f"{day:%Y%m%d}_{slot:02d}_*.md"))
    if len(matches) != 1:
        raise RuntimeError(
            f"{day.isoformat()} slot {slot:02d} 应有且仅有一篇文章，实际为 {len(matches)} 篇"
        )
    return matches[0]


def manual_body_variant(article_path: Path, focus: str) -> dict[str, str]:
    article = parse_article(article_path)
    body = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", article.body)
    paragraphs = [
        markdown_to_plain(part).strip()
        for part in re.split(r"\n\s*\n", body)
        if markdown_to_plain(part).strip()
    ]
    return {
        "key": "manual-weekly",
        "hook": paragraphs[0],
        "focus": focus,
        "closing": paragraphs[-1],
    }


def refresh(start: date, days: int) -> list[Path]:
    short_drafts = build_drafts(
        start,
        2,
        DEFAULT_CORPUS_DIR,
        days=days,
        recent_drafts=[],
    )
    daily_drafts = build_daily_fortune_drafts(
        start,
        days=days,
        slot=3,
        recent_drafts=[],
    )
    written: list[Path] = []
    for draft in [*short_drafts, *daily_drafts]:
        article_path = find_article(draft.item.day, draft.item.slot)
        article = parse_article(article_path)
        title_candidates = tuple(
            dict.fromkeys((article.title, *draft.title_candidates))
        )
        written.append(
            write_generated_record(
                article_path,
                item=draft.item,
                title_candidates=title_candidates,
                body_variant=manual_body_variant(article_path, draft.item.angle),
                source_dir=(
                    None if draft.item.slot == 3 else DEFAULT_CORPUS_DIR
                ),
                record_dir=DEFAULT_RECORD_DIR,
            )
        )
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="刷新一周星座稿件的编辑记录")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, default=1)
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days 必须大于 0")
    for path in refresh(args.start, args.days):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
