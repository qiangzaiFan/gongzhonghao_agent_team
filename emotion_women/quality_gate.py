#!/usr/bin/env python3
"""Cheap local quality checks for emotion_women articles."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from validate_article_images import image_paths, parse_frontmatter


BASE_DIR = Path(__file__).parent
DRAMA_IMAGE_POOL = BASE_DIR / "drama_image_pool.txt"

BANNED_PHRASES = [
    "每个人都值得被爱",
    "时间会治愈一切",
    "我们应该认识到",
    "综上所述",
    "由此可见",
    "女性要学会",
    "正确的做法是",
]


def is_image_reference(value: str) -> bool:
    return (
        value.startswith("http://")
        or value.startswith("https://")
        or value.startswith("/")
        or value.startswith("./")
        or value.startswith("../")
        or value.startswith("photo-")
    )


def image_reference_to_markdown_path(value: str) -> str:
    if value.startswith("photo-"):
        return f"https://images.unsplash.com/{value}?w=900"
    return value


def drama_image_paths() -> set[str]:
    if not DRAMA_IMAGE_POOL.exists():
        return set()

    paths: set[str] = set()
    for raw_line in DRAMA_IMAGE_POOL.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not is_image_reference(line):
            continue
        paths.add(image_reference_to_markdown_path(line))
    return paths


def cjk_len(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def bold_or_quote_count(body: str) -> int:
    bold_count = len(re.findall(r"\*\*[^*\n]{8,80}\*\*", body))
    quote_count = len(re.findall(r"(?m)^>\s*.{8,80}$", body))
    return bold_count + quote_count


def heading_count(body: str) -> int:
    return len(re.findall(r"(?m)^##\s+\S", body))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查 emotion_women 文章是否达到发布前的低成本质量门槛",
    )
    parser.add_argument("file", help="文章 Markdown 路径")
    parser.add_argument("--min-cjk", type=int, default=900)
    parser.add_argument("--max-cjk", type=int, default=2800)
    parser.add_argument("--min-images", type=int, default=3)
    parser.add_argument("--min-golden", type=int, default=3)
    args = parser.parse_args()

    article_path = Path(args.file)
    if not article_path.is_absolute():
        article_path = Path.cwd() / article_path
    article_path = article_path.resolve()

    if not article_path.exists():
        print(f"错误：文章不存在：{article_path}", file=sys.stderr)
        return 1

    content = article_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(content)

    errors: list[str] = []
    title = meta.get("title", "").strip()
    if not title:
        errors.append("frontmatter 缺少 title")
    elif len(title) < 10:
        errors.append(f"title 太短：{title}")

    length = cjk_len(body)
    if length < args.min_cjk:
        errors.append(f"正文太短：{length} 个中文字符，至少 {args.min_cjk}")
    if length > args.max_cjk:
        errors.append(f"正文太长：{length} 个中文字符，最多 {args.max_cjk}")

    images = image_paths(body)
    if len(images) < args.min_images:
        errors.append(f"正文图片不足：{len(images)} 张，至少 {args.min_images} 张")

    drama_paths = drama_image_paths()
    if not drama_paths:
        errors.append(f"影视剧照图池为空：{DRAMA_IMAGE_POOL}")
    elif len(images) < 2:
        errors.append("封面后的第一张正文图缺失：正文至少需要封面图 + 影视剧照图")
    elif images[1] not in drama_paths:
        errors.append(f"封面后的第一张正文图不是影视剧照图池图片：{images[1]}")

    golden = bold_or_quote_count(body)
    if golden < args.min_golden:
        errors.append(f"金句不足：识别到 {golden} 条，至少 {args.min_golden} 条")

    headings = heading_count(body)
    if headings < 2:
        errors.append(f"小标题不足：识别到 {headings} 个，至少 2 个")

    for phrase in BANNED_PHRASES:
        if phrase in body:
            errors.append(f"包含低质/AI感表达：{phrase}")

    if errors:
        print("质量门槛未通过：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"质量门槛通过：{length} 中文字符，{len(images)} 张正文图，"
        f"{golden} 条金句，{headings} 个小标题"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
