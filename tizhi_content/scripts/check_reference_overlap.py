#!/usr/bin/env python3
"""检查草稿与参考语料的连续字符重合。"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path


IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def normalize(text: str) -> str:
    text = IMAGE_RE.sub("", text)
    text = LINK_RE.sub(r"\1", text)
    text = re.sub(r"^---.*?---", "", text, count=1, flags=re.S)
    text = re.sub(r"[*_#>`~\s\W]+", "", text)
    return text


def ngrams(text: str, size: int) -> set[str]:
    return {text[index : index + size] for index in range(max(0, len(text) - size + 1))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--size", type=int, default=18)
    args = parser.parse_args()

    if args.size < 12:
        parser.error("--size 不应低于12，否则通用表达会产生大量误报")
    if not args.draft.is_file():
        parser.error(f"草稿不存在: {args.draft}")
    if not args.corpus.is_dir():
        parser.error(f"语料目录不存在: {args.corpus}")

    draft_text = normalize(args.draft.read_text(encoding="utf-8", errors="replace"))
    draft_grams = ngrams(draft_text, args.size)
    matches: dict[str, list[str]] = defaultdict(list)

    for path in args.corpus.rglob("*.md"):
        corpus_text = normalize(path.read_text(encoding="utf-8", errors="replace"))
        for match in draft_grams.intersection(ngrams(corpus_text, args.size)):
            matches[match].append(str(path))

    print(f"draft_chars={len(draft_text)}")
    print(f"ngram_size={args.size}")
    print(f"overlap_count={len(matches)}")
    for match, paths in sorted(matches.items()):
        print(f"{match}\t{paths[0]}")

    raise SystemExit(1 if matches else 0)


if __name__ == "__main__":
    main()
