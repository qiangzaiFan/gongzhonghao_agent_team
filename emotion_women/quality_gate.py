#!/usr/bin/env python3
"""Cheap local quality checks for emotion_women articles."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from validate_article_images import image_paths, is_url, local_image_path, parse_frontmatter

try:
    from PIL import Image, ImageFilter, ImageStat
except ImportError:  # pragma: no cover - optional local image dimension check
    Image = None
    ImageFilter = None
    ImageStat = None


BASE_DIR = Path(__file__).parent
IMAGE_POOL = BASE_DIR / "image_pool.txt"
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
EXPECTED_LOCAL_IMAGE_SIZE = (900, 600)
MIN_LOCAL_COVER_EDGE_RMS = 10.0
MIN_LOCAL_COVER_BRIGHTNESS = 45.0
MAX_LOCAL_COVER_BRIGHTNESS = 235.0
MIN_LOCAL_COVER_SATURATION = 18.0
MIN_LOCAL_DRAMA_EDGE_RMS = 15.0


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


def cover_image_paths() -> set[str]:
    if not IMAGE_POOL.exists():
        return set()

    paths: set[str] = set()
    in_cover = False
    for raw_line in IMAGE_POOL.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        upper = line.upper()
        if upper.startswith("## COVER"):
            in_cover = True
            continue
        if upper.startswith("## BODY"):
            in_cover = False
            continue
        if not in_cover or not line or line.startswith("#") or not is_image_reference(line):
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


def validate_local_image_dimensions(article_path: Path, images: list[str]) -> list[str]:
    if Image is None:
        return []

    errors: list[str] = []
    for index, image in enumerate(images, start=1):
        if is_url(image) or image.startswith("data:") or image.startswith("asset://"):
            continue
        resolved = local_image_path(article_path, image)
        if not resolved.exists():
            continue
        try:
            with Image.open(resolved) as im:
                size = im.size
        except OSError:
            continue
        if size != EXPECTED_LOCAL_IMAGE_SIZE:
            errors.append(
                f"正文图片 #{index} 本地尺寸不统一：{image} 为 {size[0]}x{size[1]}，"
                f"应为 {EXPECTED_LOCAL_IMAGE_SIZE[0]}x{EXPECTED_LOCAL_IMAGE_SIZE[1]}"
            )
    return errors


def validate_local_cover_quality(article_path: Path, images: list[str]) -> list[str]:
    if Image is None or ImageFilter is None or ImageStat is None or not images:
        return []

    cover_image = images[0]
    if is_url(cover_image) or cover_image.startswith("data:") or cover_image.startswith("asset://"):
        return ["封面图必须使用本地精选封面池图片，不能直接使用远程链接"]

    resolved = local_image_path(article_path, cover_image)
    if not resolved.exists():
        return []

    try:
        with Image.open(resolved).convert("RGB") as im:
            gray = im.convert("L")
            brightness = ImageStat.Stat(gray).mean[0]
            edge_rms = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).rms[0]
            saturation = ImageStat.Stat(im.convert("HSV").split()[1]).mean[0]
    except OSError:
        return []

    errors: list[str] = []
    if brightness < MIN_LOCAL_COVER_BRIGHTNESS or brightness > MAX_LOCAL_COVER_BRIGHTNESS:
        errors.append(
            f"封面图亮度不适合：{cover_image} brightness={brightness:.1f}，"
            f"应在 {MIN_LOCAL_COVER_BRIGHTNESS:.0f}-{MAX_LOCAL_COVER_BRIGHTNESS:.0f}"
        )
    if edge_rms < MIN_LOCAL_COVER_EDGE_RMS:
        errors.append(
            f"封面图清晰度偏低：{cover_image} edge_rms={edge_rms:.2f}，"
            f"至少 {MIN_LOCAL_COVER_EDGE_RMS:.1f}"
        )
    if saturation < MIN_LOCAL_COVER_SATURATION:
        errors.append(
            f"封面图色彩吸引力偏弱：{cover_image} saturation={saturation:.1f}，"
            f"至少 {MIN_LOCAL_COVER_SATURATION:.1f}"
        )
    return errors


def validate_local_drama_clarity(article_path: Path, images: list[str]) -> list[str]:
    if Image is None or ImageFilter is None or ImageStat is None or len(images) < 2:
        return []

    drama_image = images[1]
    resolved = local_image_path(article_path, drama_image)
    if not resolved.exists():
        return []

    try:
        with Image.open(resolved).convert("L") as im:
            edge_rms = ImageStat.Stat(im.filter(ImageFilter.FIND_EDGES)).rms[0]
    except OSError:
        return []

    if edge_rms < MIN_LOCAL_DRAMA_EDGE_RMS:
        return [
            f"封面后的影视剧照清晰度偏低：{drama_image} edge_rms={edge_rms:.2f}，"
            f"至少 {MIN_LOCAL_DRAMA_EDGE_RMS:.1f}。请换高清源图裁成 900x600"
        ]
    return []


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

    cover_paths = cover_image_paths()
    if not cover_paths:
        errors.append(f"封面图池为空：{IMAGE_POOL}")
    elif not images:
        errors.append("封面图缺失：正文第一张图片必须作为公众号封面")
    elif images[0] not in cover_paths:
        errors.append(f"正文第一张图不是精选封面图池图片：{images[0]}")

    drama_paths = drama_image_paths()
    if not drama_paths:
        errors.append(f"影视剧照图池为空：{DRAMA_IMAGE_POOL}")
    elif len(images) < 2:
        errors.append("封面后的第一张正文图缺失：正文至少需要封面图 + 影视剧照图")
    elif images[1] not in drama_paths:
        errors.append(f"封面后的第一张正文图不是影视剧照图池图片：{images[1]}")
    elif is_url(images[1]) or images[1].startswith("data:") or images[1].startswith("asset://"):
        errors.append("封面后的影视剧照必须使用本地高清缓存图，不能直接使用远程链接")

    errors.extend(validate_local_image_dimensions(article_path, images))
    errors.extend(validate_local_cover_quality(article_path, images))
    errors.extend(validate_local_drama_clarity(article_path, images))

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
