#!/usr/bin/env python3
"""Render existing Markdown articles as WeChat image-post drafts."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from validate_article_images import image_paths, local_image_path, parse_frontmatter


BASE_DIR = Path(__file__).parent
ARTICLES_DIR = BASE_DIR / "articles"
OUTPUT_DIR = ARTICLES_DIR / "image_posts"
CARD_SIZE = (900, 1200)
COVER_SIZE = (900, 600)
FONT_PATH = Path("/System/Library/Fonts/PingFang.ttc")
FALLBACK_FONT_PATH = Path("/System/Library/Fonts/STHeiti Medium.ttc")
MAX_CARD_CJK = 175


def font(size: int) -> ImageFont.FreeTypeFont:
    path = FONT_PATH if FONT_PATH.exists() else FALLBACK_FONT_PATH
    if not path.exists():
        raise FileNotFoundError("找不到可用的中文字体（PingFang/STHeiti）")
    return ImageFont.truetype(str(path), size=size)


def clean_markdown(text: str) -> str:
    text = re.sub(r"!\[[^]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("__", "")
    return text.strip()


def content_blocks(body: str) -> list[tuple[str, str]]:
    """Return (optional section heading, paragraph) blocks in source order."""
    blocks: list[tuple[str, str]] = []
    heading = ""
    for raw in re.split(r"\n\s*\n", body):
        value = clean_markdown(raw)
        if not value:
            continue
        if value.startswith("## "):
            lines = value.splitlines()
            heading = lines[0][3:].strip()
            value = "\n".join(lines[1:]).strip()
            if not value:
                continue
        blocks.append((heading, value))
        heading = ""
    return blocks


def cjk_len(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def split_long_text(text: str, limit: int) -> list[str]:
    if cjk_len(text) <= limit:
        return [text]
    sentences = [part.strip() for part in re.split(r"(?<=[。！？!?])", text) if part.strip()]
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if current and cjk_len(current + sentence) > limit:
            pieces.append(current)
            current = sentence
        else:
            current += sentence
    if current:
        pieces.append(current)
    return pieces


def make_pages(body: str) -> list[tuple[str, list[str]]]:
    pages: list[tuple[str, list[str]]] = []
    page_heading = ""
    paragraphs: list[str] = []
    length = 0

    for heading, paragraph in content_blocks(body):
        for piece_index, piece in enumerate(split_long_text(paragraph, MAX_CARD_CJK)):
            piece_heading = heading if piece_index == 0 else ""
            piece_length = cjk_len(piece)
            if paragraphs and (length + piece_length > MAX_CARD_CJK or piece_heading):
                pages.append((page_heading, paragraphs))
                page_heading, paragraphs, length = "", [], 0
            if piece_heading:
                page_heading = piece_heading
            paragraphs.append(piece)
            length += piece_length
    if paragraphs:
        pages.append((page_heading, paragraphs))
    return pages


def crop_photo(source: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(source) as opened:
        image = opened.convert("RGB")
    scale = max(size[0] / image.width, size[1] / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


def wrap_text(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph_line in text.splitlines() or [""]:
        current = ""
        for char in paragraph_line:
            candidate = current + char
            if current and draw.textlength(candidate, font=text_font) > width:
                lines.append(current)
                current = char
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def render_card(
    destination: Path,
    photo_path: Path,
    title: str,
    heading: str,
    paragraphs: list[str],
    page_number: int,
    total_pages: int,
) -> None:
    canvas = Image.new("RGB", CARD_SIZE, "#F7F8F6")
    photo = crop_photo(photo_path, (900, 355))
    photo = ImageEnhance.Color(photo).enhance(0.88)
    photo = ImageEnhance.Contrast(photo).enhance(0.94)
    canvas.paste(photo, (0, 0))

    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 355, 14, 1200), fill="#D45745")
    draw.rectangle((14, 355, 900, 365), fill="#2F6B5D")

    small_font = font(25)
    heading_font = font(39)
    body_font = font(35)
    footer_font = font(23)
    draw.text((62, 405), title, fill="#68716C", font=small_font)
    draw.text((792, 405), f"{page_number:02d}", fill="#D45745", font=heading_font)

    y = 472
    if heading:
        for line in wrap_text(draw, heading, heading_font, 690):
            draw.text((62, y), line, fill="#202522", font=heading_font)
            y += 56
        y += 18

    body_lines: list[tuple[str, bool]] = []
    for paragraph_index, paragraph in enumerate(paragraphs):
        if paragraph_index:
            body_lines.append(("", True))
        body_lines.extend((line, False) for line in wrap_text(draw, paragraph, body_font, 776))

    line_height = 54
    available = 1108 - y
    required = sum(28 if blank else line_height for _, blank in body_lines)
    if required > available:
        body_font = font(31)
        line_height = 48
        body_lines = []
        for paragraph_index, paragraph in enumerate(paragraphs):
            if paragraph_index:
                body_lines.append(("", True))
            body_lines.extend((line, False) for line in wrap_text(draw, paragraph, body_font, 776))

    for line, blank in body_lines:
        if blank:
            y += 24
            continue
        draw.text((62, y), line, fill="#242A27", font=body_font)
        y += line_height

    draw.line((62, 1133, 838, 1133), fill="#D8DDDA", width=2)
    draw.text((62, 1150), "把生活里的感受，认真说清楚", fill="#76807A", font=footer_font)
    draw.text((778, 1150), f"{page_number}/{total_pages}", fill="#76807A", font=footer_font)
    canvas.save(destination, format="JPEG", quality=92, optimize=True)


def convert_article(article_path: Path) -> Path:
    content = article_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(content)
    title = meta.get("title", article_path.stem).strip()
    sources = image_paths(body)
    local_sources = [
        local_image_path(article_path, value)
        for value in sources
        if not value.startswith(("http://", "https://", "data:", "asset://"))
        and local_image_path(article_path, value).exists()
    ]
    if not local_sources:
        raise ValueError(f"文章没有可用的本地配图：{article_path}")

    pages = make_pages(body)
    if not pages:
        raise ValueError(f"文章没有可渲染的正文：{article_path}")

    output = OUTPUT_DIR / article_path.stem
    output.mkdir(parents=True, exist_ok=True)
    cover_path = output / "00-cover.jpg"
    crop_photo(local_sources[0], COVER_SIZE).save(cover_path, "JPEG", quality=92, optimize=True)

    for index, (heading, paragraphs) in enumerate(pages, start=1):
        photo_path = local_sources[(index - 1) % len(local_sources)]
        render_card(
            output / f"{index:02d}-story.jpg",
            photo_path,
            title,
            heading,
            paragraphs,
            index,
            len(pages),
        )

    markdown_path = output / "image-post.md"
    image_lines = ["![](00-cover.jpg)"] + [
        f"![]({index:02d}-story.jpg)" for index in range(1, len(pages) + 1)
    ]
    markdown = (
        "---\n"
        f"title: {title}\n"
        "format: image-post\n"
        f"source: ../../{article_path.name}\n"
        "---\n\n"
        + "\n\n".join(image_lines)
        + "\n"
    )
    markdown_path.write_text(markdown, encoding="utf-8")
    return markdown_path


def latest_articles(count: int) -> list[Path]:
    files = list(ARTICLES_DIR.glob("*.md"))
    return sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)[:count]


def main() -> int:
    parser = argparse.ArgumentParser(description="把现有公众号文章转换成贴图版")
    parser.add_argument("files", nargs="*", help="要转换的 Markdown 文章")
    parser.add_argument("--latest", type=int, metavar="N", help="转换最新 N 篇文章")
    parser.add_argument("--publish", action="store_true", help="转换后发布到微信公众号草稿箱")
    parser.add_argument("--theme", default="orangeheart", help="公众号排版主题")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if bool(args.files) == bool(args.latest):
        parser.error("请指定文章文件，或使用 --latest N（二选一）")
    if args.latest is not None and args.latest < 1:
        parser.error("--latest 必须大于 0")

    articles = latest_articles(args.latest) if args.latest else [Path(value) for value in args.files]
    articles = [path if path.is_absolute() else (BASE_DIR / path) for path in articles]
    generated: list[Path] = []
    for article in articles:
        article = article.resolve()
        if not article.exists():
            print(f"错误：文章不存在：{article}", file=sys.stderr)
            return 1
        image_post = convert_article(article)
        generated.append(image_post)
        print(f"贴图版已生成：{image_post}")

    if args.publish:
        for image_post in generated:
            cmd = [
                sys.executable,
                str(BASE_DIR / "publish_existing_article.py"),
                str(image_post),
                "--theme",
                args.theme,
            ]
            if args.verbose:
                cmd.append("-v")
            print(f"正在发布：{image_post.parent.name}")
            result = subprocess.run(cmd, cwd=BASE_DIR)
            if result.returncode != 0:
                return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
