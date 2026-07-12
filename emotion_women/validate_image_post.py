#!/usr/bin/env python3
"""Validate a generated WeChat image-post Markdown file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from validate_article_images import image_paths, local_image_path, parse_frontmatter


def main() -> int:
    parser = argparse.ArgumentParser(description="检查公众号贴图版文章")
    parser.add_argument("file")
    args = parser.parse_args()
    article = Path(args.file).resolve()
    if not article.exists():
        print(f"错误：贴图版不存在：{article}", file=sys.stderr)
        return 1

    meta, body = parse_frontmatter(article.read_text(encoding="utf-8"))
    images = image_paths(body)
    errors: list[str] = []
    if not meta.get("title"):
        errors.append("frontmatter 缺少 title")
    if meta.get("format") != "image-post":
        errors.append("frontmatter 的 format 必须是 image-post")
    if len(images) < 4:
        errors.append(f"贴图不足：当前 {len(images)} 张，至少需要封面和 3 张正文图")

    for index, value in enumerate(images):
        path = local_image_path(article, value)
        expected = (900, 600) if index == 0 else (900, 1200)
        if not path.exists():
            errors.append(f"图片不存在：{value}")
            continue
        try:
            with Image.open(path) as image:
                if image.size != expected:
                    errors.append(
                        f"图片尺寸错误：{value} 为 {image.width}x{image.height}，"
                        f"应为 {expected[0]}x{expected[1]}"
                    )
        except OSError as exc:
            errors.append(f"图片无法读取：{value}（{exc}）")

    if errors:
        print("贴图版校验失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"贴图版校验通过：封面 1 张，正文贴图 {len(images) - 1} 张")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
