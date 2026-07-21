#!/usr/bin/env python3
"""Render existing Markdown articles as WeChat image-post drafts."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
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
FONT_PATHS = (
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
)
MAX_CARD_CJK = 150
INK = "#342B3A"
TITLE_MAX_CHARS = 20
IMAGE_POST_COVERS = (
    BASE_DIR / "images" / "persona" / "master" / "persona_master_glam_v3.png",
    BASE_DIR / "images" / "persona" / "scenes" / "20260720-pool-cycling-river-cover.jpg",
    BASE_DIR / "images" / "persona" / "scenes" / "20260720-pool-hiking-trail-cover.jpg",
    BASE_DIR / "images" / "persona" / "scenes" / "20260720-pool-market-morning-cover.jpg",
    BASE_DIR / "images" / "persona" / "scenes" / "20260720-pool-baking-kitchen-cover.jpg",
    BASE_DIR / "images" / "persona" / "scenes" / "20260720-pool-yoga-studio-cover.jpg",
    BASE_DIR / "images" / "cover" / "cover_sensual_city_editorial_900x600.jpg",
    BASE_DIR / "images" / "cover" / "cover_sensual_life_morning_900x600.jpg",
    BASE_DIR / "images" / "cover" / "cover_sensual_life_commute_900x600.jpg",
    BASE_DIR / "images" / "cover" / "cover_sensual_life_cafe_900x600.jpg",
    BASE_DIR / "images" / "cover" / "cover_sensual_life_home_900x600.jpg",
)
CARD_PALETTES = (
    {
        "top": "#FDE6DE",
        "bottom": "#FFFDF4",
        "accent": "#E76F86",
        "accent_2": "#2995A5",
        "ink": "#3A2D3D",
        "muted": "#846F7E",
    },
    {
        "top": "#E9DDFB",
        "bottom": "#FDF7FF",
        "accent": "#6D4AA1",
        "accent_2": "#F08D9E",
        "ink": "#31283F",
        "muted": "#7B6B8E",
    },
    {
        "top": "#F8F1A9",
        "bottom": "#FFFBEF",
        "accent": "#87671A",
        "accent_2": "#F5A145",
        "ink": "#3B3324",
        "muted": "#81775E",
    },
)


def font(size: int) -> ImageFont.FreeTypeFont:
    path = next((candidate for candidate in FONT_PATHS if candidate.exists()), None)
    if path is None:
        raise FileNotFoundError("找不到可用的中文字体（微软雅黑/黑体/PingFang）")
    return ImageFont.truetype(str(path), size=size)


def clean_markdown(text: str) -> str:
    text = re.sub(r"!\[[^]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("__", "")
    return text.strip()


def normalize_rewritten_title(value: str, original: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        return ""
    title = re.sub(r"^(?:标题|新标题|改写标题)\s*[：:]\s*", "", lines[0])
    title = title.strip("`#*'\"“”《》 ")
    if not 6 <= len(title) <= TITLE_MAX_CHARS or title == original:
        return ""
    return title


def local_title_rewrite(title: str, body: str) -> str:
    rewritten = title
    replacements = (
        ("还在用她的会员", "竟还在蹭她的会员"),
        ("不肯再去", "死活不肯再去"),
        ("这次，她没", "她第一次没"),
        ("这次，她不", "她第一次不"),
    )
    for before, after in replacements:
        if before in rewritten:
            rewritten = rewritten.replace(before, after, 1)
            break
    if rewritten == title and len(title) <= 17:
        rewritten = f"没想到，{title}"
    if rewritten != title:
        return rewritten[:TITLE_MAX_CHARS]

    plain_body = clean_markdown(body)
    first_scene = re.split(r"[。！？!?]", plain_body, maxsplit=1)[0].strip()
    if len(first_scene) > TITLE_MAX_CHARS:
        comma_at = max(first_scene.rfind("，", 0, TITLE_MAX_CHARS), first_scene.rfind(",", 0, TITLE_MAX_CHARS))
        first_scene = first_scene[:comma_at] if comma_at >= 8 else first_scene[: TITLE_MAX_CHARS - 1] + "…"
    return first_scene if 6 <= len(first_scene) <= TITLE_MAX_CHARS else f"没想到，{title}"[:TITLE_MAX_CHARS]


def cached_image_post_title(output: Path, source_title: str) -> str:
    markdown_path = output / "image-post.md"
    if not markdown_path.exists():
        return ""
    meta, _body = parse_frontmatter(markdown_path.read_text(encoding="utf-8", errors="ignore"))
    candidate = meta.get("title", "").strip()
    if meta.get("source_title", "").strip() != source_title:
        return ""
    return normalize_rewritten_title(candidate, source_title)


def rewrite_image_post_title(source_title: str, body: str, output: Path) -> str:
    cached = cached_image_post_title(output, source_title)
    if cached:
        return cached

    claude = shutil.which("claude")
    if claude:
        clean_body = clean_markdown(body)
        prompt = f"""把下面的公众号文章标题改写成一个新的贴图版标题。

硬性要求：
- 6到20个汉字或字符
- 与原标题明显不同，不能只增删标点
- 从正文最具体的冲突、动作或现场对话切入，点击感更强
- 不改变人物关系和事实，不编造数字、身份或结果
- 不用低俗、色情、震惊体，不写标题党承诺
- 只输出一行新标题，不要引号、解释或前缀

原标题：{source_title}

正文：
{clean_body[:3000]}
"""
        try:
            result = subprocess.run(
                [claude, "-p", prompt, "--output-format", "text"],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode == 0:
                rewritten = normalize_rewritten_title(result.stdout, source_title)
                if rewritten:
                    return rewritten
        except (OSError, subprocess.TimeoutExpired):
            pass

    return local_title_rewrite(source_title, body)


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


def impact_photo(source: Path, size: tuple[int, int]) -> Image.Image:
    """Give source photos a punchier treatment suited to feed thumbnails."""
    image = crop_photo(source, size)
    image = ImageEnhance.Color(image).enhance(1.24)
    image = ImageEnhance.Contrast(image).enhance(1.14)
    image = ImageEnhance.Sharpness(image).enhance(1.3)
    return image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=115, threshold=3))


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def vertical_gradient(
    size: tuple[int, int],
    top_color: str,
    bottom_color: str,
) -> Image.Image:
    top = hex_rgb(top_color)
    bottom = hex_rgb(bottom_color)
    image = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(image)
    denominator = max(1, size[1] - 1)
    for y in range(size[1]):
        ratio = y / denominator
        color = tuple(round(start + (end - start) * ratio) for start, end in zip(top, bottom))
        draw.line((0, y, size[0], y), fill=color)
    return image


def photo_sticker(
    source: Path,
    size: tuple[int, int],
    radius: int = 30,
    border: int = 9,
) -> Image.Image:
    photo = impact_photo(source, size).convert("RGBA")
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    sticker_size = (size[0] + border * 2, size[1] + border * 2)
    sticker = Image.new("RGBA", sticker_size, (255, 255, 255, 0))
    sticker_draw = ImageDraw.Draw(sticker)
    sticker_draw.rounded_rectangle(
        (0, 0, sticker_size[0] - 1, sticker_size[1] - 1),
        radius=radius + border,
        fill=(255, 255, 255, 250),
    )
    sticker.paste(photo, (border, border), mask)
    return sticker


def paste_sticker(
    canvas: Image.Image,
    source: Path,
    position: tuple[int, int],
    size: tuple[int, int],
    angle: float = 0,
) -> None:
    sticker = photo_sticker(source, size)
    if angle:
        sticker = sticker.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    canvas.alpha_composite(sticker, position)


def draw_sparkle(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    radius: int,
    color: str,
) -> None:
    x, y = center
    points = (
        (x, y - radius),
        (x + radius // 4, y - radius // 4),
        (x + radius, y),
        (x + radius // 4, y + radius // 4),
        (x, y + radius),
        (x - radius // 4, y + radius // 4),
        (x - radius, y),
        (x - radius // 4, y - radius // 4),
    )
    draw.polygon(points, fill=color)


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


def page_hook(heading: str, paragraphs: list[str], limit: int = 18) -> str:
    text = "".join(paragraphs)
    quote = re.search(r"[“\"]([^”\"\n]{4,30})[”\"]", text)
    hook = quote.group(1) if quote else heading
    if not hook:
        hook = re.split(r"[。！？!?]", text, maxsplit=1)[0]
    hook = re.sub(r"\s+", "", hook).strip("：:，,。！？!?“”\"")
    return hook if len(hook) <= limit else hook[:limit] + "…"


def balanced_title_lines(
    draw: ImageDraw.ImageDraw,
    title: str,
    max_width: int,
) -> tuple[list[str], ImageFont.FreeTypeFont]:
    size = 62
    title_font = font(size)
    if draw.textlength(title, font=title_font) <= max_width:
        return [title], title_font

    split_at = (len(title) + 1) // 2
    lines = [title[:split_at].strip(), title[split_at:].strip()]
    while size > 46 and any(draw.textlength(line, font=title_font) > max_width for line in lines):
        size -= 2
        title_font = font(size)
    return lines, title_font


def render_cover(destination: Path, photo_paths: list[Path], title: str, hook: str) -> None:
    palette = CARD_PALETTES[0]
    canvas = vertical_gradient(COVER_SIZE, palette["top"], palette["bottom"]).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((30, 28, 870, 572), radius=36, outline="#FFFFFF", width=5)
    draw.ellipse((48, 45, 102, 99), fill="#F4A8B6")
    draw.ellipse((76, 62, 91, 77), fill="#FFFFFF")
    draw_sparkle(draw, (408, 68), 20, palette["accent_2"])
    draw_sparkle(draw, (452, 522), 15, palette["accent"])

    sources = photo_paths or []
    if sources:
        while len(sources) < 3:
            sources.append(sources[len(sources) % len(sources)])
        paste_sticker(canvas, sources[1], (405, 54), (188, 208), angle=-4)
        paste_sticker(canvas, sources[0], (505, 70), (330, 446), angle=2)
        paste_sticker(canvas, sources[2], (390, 315), (210, 212), angle=-2)

    draw = ImageDraw.Draw(canvas)
    badge_font = font(24)
    draw.rounded_rectangle((54, 116, 318, 160), radius=22, fill="#FFFFFFE8")
    draw.text((76, 123), "一个成熟女人的真实日常", fill=palette["muted"], font=badge_font)

    title_lines, title_font = balanced_title_lines(draw, title, 360)
    y = 188
    for line_index, line in enumerate(title_lines):
        color = palette["accent"] if line_index == 0 else palette["ink"]
        draw.text((54, y), line, fill=color, font=title_font, stroke_width=1, stroke_fill="#FFF8FA")
        y += 78

    hook_font = font(25)
    hook_text = hook or "把情绪放回具体的生活里"
    hook_lines = wrap_text(draw, hook_text, hook_font, 318)
    hook_y = max(y + 18, 420)
    for line in hook_lines[:2]:
        draw.text((58, hook_y), line, fill=palette["muted"], font=hook_font)
        hook_y += 38

    canvas.convert("RGB").save(destination, format="JPEG", quality=96, optimize=True)


def render_card(
    destination: Path,
    background_paths: list[Path],
    title: str,
    heading: str,
    paragraphs: list[str],
    page_number: int,
    total_pages: int,
) -> None:
    palette = CARD_PALETTES[(page_number - 1) % len(CARD_PALETTES)]
    canvas = vertical_gradient(CARD_SIZE, palette["top"], palette["bottom"]).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((28, 26, 872, 1172), radius=42, outline="#FFFFFF", width=5)
    draw_sparkle(draw, (818, 128), 18, palette["accent"])
    draw_sparkle(draw, (82, 355), 16, palette["accent_2"])
    draw.ellipse((770, 315, 806, 351), fill="#FFFFFFB8")
    draw.ellipse((806, 346, 825, 365), fill=palette["accent_2"])

    small_font = font(22)
    heading_font = font(34)
    body_font = font(31)
    footer_font = font(21)
    hook_font = font(44)
    hook = page_hook(heading, paragraphs, limit=24)
    hook_lines = wrap_text(draw, hook, hook_font, 700)
    hook_y = 52
    for line in hook_lines[:2]:
        draw.text((58, hook_y), line, fill=palette["accent"], font=hook_font, stroke_width=1, stroke_fill="#FFF9FB")
        hook_y += 58
    draw.rounded_rectangle((778, 42, 848, 92), radius=22, fill="#FFFFFFD8")
    draw.text((790, 47), f"{page_number:02d}", fill=palette["muted"], font=heading_font)

    sources = [path for path in background_paths if path.exists()]
    if sources:
        while len(sources) < 3:
            sources.append(sources[len(sources) % len(sources)])
        paste_sticker(canvas, sources[0], (48, 176), (248, 292), angle=-3)
        paste_sticker(canvas, sources[1], (314, 160), (266, 318), angle=2)
        paste_sticker(canvas, sources[2], (600, 185), (244, 282), angle=-2)
    else:
        draw = ImageDraw.Draw(canvas)
        for box in ((48, 176, 296, 468), (314, 160, 580, 478), (600, 185, 844, 467)):
            draw.rounded_rectangle(box, radius=30, fill="#FFFFFFA8")

    draw = ImageDraw.Draw(canvas)
    draw.text((60, 505), title, fill=palette["muted"], font=small_font)
    y = 548
    if heading:
        for line in wrap_text(draw, heading, heading_font, 740):
            draw.text((62, y), line, fill=palette["ink"], font=heading_font)
            y += 48
        y += 12

    body_lines: list[tuple[str, bool]] = []
    for paragraph_index, paragraph in enumerate(paragraphs):
        if paragraph_index:
            body_lines.append(("", True))
        body_lines.extend((line, False) for line in wrap_text(draw, paragraph, body_font, 770))

    line_height = 47
    available = 1096 - y
    required = sum(28 if blank else line_height for _, blank in body_lines)
    if required > available:
        body_font = font(28)
        line_height = 43
        body_lines = []
        for paragraph_index, paragraph in enumerate(paragraphs):
            if paragraph_index:
                body_lines.append(("", True))
            body_lines.extend((line, False) for line in wrap_text(draw, paragraph, body_font, 770))

    for line, blank in body_lines:
        if blank:
            y += 24
            continue
        draw.text((62, y), line, fill=palette["ink"], font=body_font)
        y += line_height

    draw.line((62, 1128, 838, 1128), fill="#FFFFFF", width=3)
    draw.text((62, 1144), "今天也在认真生活", fill=palette["muted"], font=footer_font)
    draw.text((790, 1144), f"{page_number}/{total_pages}", fill=palette["muted"], font=footer_font)
    canvas.convert("RGB").save(destination, format="JPEG", quality=95, optimize=True)


def stable_cover_index(value: str, cover_count: int) -> int:
    if cover_count <= 0:
        return 0
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "big") % cover_count


def convert_article(
    article_path: Path,
    rewrite_title: bool = True,
    cover_index_override: int | None = None,
) -> Path:
    content = article_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(content)
    source_title = meta.get("title", article_path.stem).strip()
    sources = image_paths(body)
    local_sources = [
        local_image_path(article_path, value)
        for value in sources
        if not value.startswith(("http://", "https://", "data:", "asset://"))
        and local_image_path(article_path, value).exists()
    ]
    pages = make_pages(body)
    if not pages:
        raise ValueError(f"文章没有可渲染的正文：{article_path}")

    output = OUTPUT_DIR / article_path.stem
    output.mkdir(parents=True, exist_ok=True)
    title = rewrite_image_post_title(source_title, body, output) if rewrite_title else source_title
    if title != source_title:
        print(f"贴图标题：{source_title} -> {title}")
    cover_path = output / "00-cover.jpg"
    image_post_covers = [path for path in IMAGE_POST_COVERS if path.exists()]
    persona_sources = [
        path
        for path in local_sources
        if "/images/persona/scenes/" in path.as_posix()
    ]
    use_article_persona_set = len(persona_sources) >= 3
    visual_sources = list(
        dict.fromkeys(
            (persona_sources + image_post_covers)
            if use_article_persona_set
            else (image_post_covers + local_sources)
        )
    )
    if visual_sources:
        cover_index = 0 if use_article_persona_set else (
            cover_index_override % len(visual_sources)
            if cover_index_override is not None
            else stable_cover_index(source_title, len(visual_sources))
        )
        cover_sources = [
            visual_sources[(cover_index + offset) % len(visual_sources)]
            for offset in range(min(3, len(visual_sources)))
        ]
    else:
        raise ValueError(f"找不到贴图专用封面或文章本地封面：{article_path}")
    first_heading, first_paragraphs = pages[0]
    render_cover(
        cover_path,
        cover_sources,
        title,
        page_hook(first_heading, first_paragraphs, limit=22),
    )

    for index, (heading, paragraphs) in enumerate(pages, start=1):
        background_paths = [
            visual_sources[(cover_index + index + offset) % len(visual_sources)]
            for offset in range(min(3, len(visual_sources)))
        ]
        render_card(
            output / f"{index:02d}-story.jpg",
            background_paths,
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
        f"source_title: {source_title}\n"
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
    parser.add_argument("--keep-title", action="store_true", help="贴图版沿用原标题，不自动改写")
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
    image_post_covers = [path for path in IMAGE_POST_COVERS if path.exists()]
    used_cover_indexes: set[int] = set()
    for article in articles:
        article = article.resolve()
        if not article.exists():
            print(f"错误：文章不存在：{article}", file=sys.stderr)
            return 1
        cover_index: int | None = None
        if image_post_covers:
            content = article.read_text(encoding="utf-8", errors="ignore")
            meta, _body = parse_frontmatter(content)
            source_title = meta.get("title", article.stem).strip()
            if len(used_cover_indexes) >= len(image_post_covers):
                used_cover_indexes.clear()
            cover_index = stable_cover_index(source_title, len(image_post_covers))
            while cover_index in used_cover_indexes:
                cover_index = (cover_index + 1) % len(image_post_covers)
            used_cover_indexes.add(cover_index)
        image_post = convert_article(
            article,
            rewrite_title=not args.keep_title,
            cover_index_override=cover_index,
        )
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
