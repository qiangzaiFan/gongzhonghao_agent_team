#!/usr/bin/env python3
"""Compose final quote-card illustrations from approved no-text base art."""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont


BASE_DIR = Path(__file__).resolve().parents[1]
MANIFEST_PATH = BASE_DIR / "data" / "illustration_manifest.json"
DEFAULT_SOURCE_DIR = BASE_DIR / "images" / "illustrations" / "sources"
CANVAS = 1080
PAPER_BG = (248, 244, 235)
INK = (56, 55, 52)
RED = (188, 39, 32)


@dataclass
class CardItem:
    article: str
    title: str
    slot: str
    summary: str
    quote: str
    source: Path
    target: Path


def load_manifest(path: Path) -> list[CardItem]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items: list[CardItem] = []
    for raw in data.get("assignments", []):
        target = Path(raw["target"])
        source = Path(raw.get("source", ""))
        if not source:
            source = DEFAULT_SOURCE_DIR / f"{target.stem}_base.png"
        items.append(
            CardItem(
                article=raw.get("article", ""),
                title=raw.get("title", ""),
                slot=raw.get("slot", ""),
                summary=raw.get("summary", ""),
                quote=raw.get("quote", raw.get("summary", "")),
                source=source,
                target=target,
            )
        )
    return items


def font_path(candidates: list[str]) -> str:
    font_dir = Path(r"C:\Windows\Fonts")
    for name in candidates:
        path = font_dir / name
        if path.exists():
            return str(path)
    raise SystemExit(f"找不到可用中文字体：{', '.join(candidates)}")


def load_font(size: int, kind: str = "quote") -> ImageFont.FreeTypeFont:
    if kind == "quote":
        candidates = ["simkai.ttf", "HYZhongHeiTi-197.ttf", "msyhbd.ttc", "simhei.ttf"]
    elif kind == "seal":
        candidates = ["simkai.ttf", "simhei.ttf", "msyhbd.ttc"]
    else:
        candidates = ["msyhbd.ttc", "simhei.ttf", "msyh.ttc"]
    return ImageFont.truetype(font_path(candidates), size=size)


def paper_texture(seed: int) -> Image.Image:
    rng = random.Random(seed)
    image = Image.new("RGB", (CANVAS, CANVAS), PAPER_BG)
    overlay = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for _ in range(1800):
        x = rng.randrange(CANVAS)
        y = rng.randrange(CANVAS)
        length = rng.randrange(7, 42)
        alpha = rng.randrange(8, 30)
        color = (190, 181, 163, alpha) if rng.random() < 0.55 else (255, 255, 255, alpha)
        draw.line((x, y, min(CANVAS, x + length), y + rng.randrange(-2, 3)), fill=color, width=1)

    for _ in range(120):
        x = rng.randrange(-60, CANVAS)
        y = rng.randrange(-60, CANVAS)
        w = rng.randrange(28, 120)
        h = rng.randrange(8, 32)
        alpha = rng.randrange(4, 13)
        draw.ellipse((x, y, x + w, y + h), fill=(173, 164, 144, alpha))

    overlay = overlay.filter(ImageFilter.GaussianBlur(0.25))
    return Image.alpha_composite(image.convert("RGBA"), overlay)


def cover_fit(image: Image.Image, width: int, height: int) -> Image.Image:
    source = image.convert("RGBA")
    ratio = max(width / source.width, height / source.height)
    new_size = (round(source.width * ratio), round(source.height * ratio))
    resized = source.resize(new_size, Image.Resampling.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def paste_base_art(canvas: Image.Image, base: Image.Image) -> None:
    art_w, art_h = 860, 570
    art = cover_fit(base, art_w, art_h)
    # Gently blend a full-square model output into the paper so the card still feels hand-made.
    feather = Image.new("L", (art_w, art_h), 0)
    feather_draw = ImageDraw.Draw(feather)
    feather_draw.rounded_rectangle((0, 0, art_w, art_h), radius=28, fill=235)
    mask = feather.filter(ImageFilter.GaussianBlur(6))
    canvas.paste(art, ((CANVAS - art_w) // 2, 86), mask)


def text_bbox(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, stroke_width: int = 0) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def fit_quote_font(draw: ImageDraw.ImageDraw, lines: list[str], max_width: int, max_height: int) -> ImageFont.FreeTypeFont:
    for size in range(118, 62, -4):
        font = load_font(size, "quote")
        widths = [text_bbox(draw, line, font, stroke_width=2)[0] for line in lines]
        line_h = max(text_bbox(draw, line, font, stroke_width=2)[1] for line in lines)
        total_h = line_h * len(lines) + 24 * (len(lines) - 1)
        if max(widths, default=0) <= max_width and total_h <= max_height:
            return font
    return load_font(62, "quote")


def draw_quote(canvas: Image.Image, quote: str) -> None:
    draw = ImageDraw.Draw(canvas)
    lines = [line.strip() for line in quote.splitlines() if line.strip()] or [quote.strip()]
    lines = lines[:3]
    font = fit_quote_font(draw, lines, max_width=900, max_height=320)
    line_heights = [text_bbox(draw, line, font, stroke_width=2)[1] for line in lines]
    total_h = sum(line_heights) + 28 * (len(lines) - 1)
    y = 690 + max(0, (260 - total_h) // 2)

    for line, line_h in zip(lines, line_heights):
        w, _ = text_bbox(draw, line, font, stroke_width=2)
        x = (CANVAS - w) // 2
        # Draw twice with a tiny offset to mimic heavier brush ink without losing readability.
        draw.text((x + 1, y + 1), line, font=font, fill=(72, 70, 66), stroke_width=2, stroke_fill=(72, 70, 66))
        draw.text((x, y), line, font=font, fill=INK, stroke_width=1, stroke_fill=INK)
        y += line_h + 28


def draw_seal(canvas: Image.Image) -> None:
    draw = ImageDraw.Draw(canvas)
    x, y, size = 828, 902, 78
    for offset in range(3):
        draw.rounded_rectangle((x + offset, y + offset, x + size - offset, y + size - offset), radius=5, outline=RED, width=3)
    seal_font = load_font(43, "seal")
    mark = "晴"
    bbox = draw.textbbox((0, 0), mark, font=seal_font)
    draw.text(
        (x + (size - (bbox[2] - bbox[0])) / 2, y + (size - (bbox[3] - bbox[1])) / 2 - 4),
        mark,
        font=seal_font,
        fill=RED,
        stroke_width=1,
        stroke_fill=RED,
    )
    brand_font = load_font(24, "brand")
    draw.text((x + size + 14, y + 18), "晴川黄鹤", font=brand_font, fill=(62, 57, 52))


def compose(item: CardItem, dry_run: bool = False) -> bool:
    if not item.source.exists():
        print(f"MISSING source={item.source} target={item.target}")
        return False
    if dry_run:
        print(f"READY source={item.source} target={item.target}")
        return True

    base = Image.open(item.source)
    canvas = paper_texture(seed=abs(hash(item.target.name)) % 1_000_000)
    paste_base_art(canvas, base)
    draw_quote(canvas, item.quote)
    draw_seal(canvas)
    item.target.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(item.target, quality=96)
    print(f"composed={item.target}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Compose 晴川黄鹤 quote-card illustrations from no-text base art.")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Only check that source images exist")
    parser.add_argument("--only-missing", action="store_true", help="Skip cards whose final target already exists")
    args = parser.parse_args()

    items = load_manifest(args.manifest)
    if not items:
        print("manifest 中没有插图记录", file=sys.stderr)
        return 2

    ok = True
    for item in items:
        if args.only_missing and item.target.exists():
            continue
        ok = compose(item, dry_run=args.dry_run) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
