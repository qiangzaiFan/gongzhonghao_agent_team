#!/usr/bin/env python3
"""Validate Markdown image paths before publishing with wenyan-mcp."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib import error, request
from urllib.parse import urlparse


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<meta>.*?)\n---\s*\n(?P<body>.*)\Z", re.S)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\((?P<path>[^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_IMAGE_RE = re.compile(r"<img\b[^>]*\bsrc=[\"'](?P<path>[^\"']+)[\"']", re.I)
REMOTE_TIMEOUT_SECONDS = 15


def is_url(value: str) -> bool:
    scheme = urlparse(value).scheme.lower()
    return scheme in {"http", "https"}


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(content)
    if not match:
        return {}, content

    meta: dict[str, str] = {}
    for line in match.group("meta").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = strip_quotes(value)
    return meta, match.group("body")


def image_paths(body: str) -> list[str]:
    paths = [strip_quotes(match.group("path")) for match in IMAGE_RE.finditer(body)]
    paths.extend(strip_quotes(match.group("path")) for match in HTML_IMAGE_RE.finditer(body))
    return paths


def local_image_path(article_path: Path, image_path: str) -> Path:
    path = Path(image_path).expanduser()
    if path.is_absolute():
        return path
    return (article_path.parent / path).resolve()


def validate_remote_image(image_url: str, label: str) -> list[str]:
    req = request.Request(
        image_url,
        headers={
            "User-Agent": "Mozilla/5.0 emotion-women-image-preflight",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Range": "bytes=0-0",
        },
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=REMOTE_TIMEOUT_SECONDS) as resp:
            status = resp.getcode()
            content_type = resp.headers.get("content-type", "").split(";", 1)[0].lower()
    except error.HTTPError as exc:
        return [f"{label} 远程图片不可访问：HTTP {exc.code} {image_url}"]
    except error.URLError as exc:
        return [f"{label} 远程图片不可访问：{exc.reason} {image_url}"]
    except TimeoutError:
        return [f"{label} 远程图片访问超时：{image_url}"]

    if status < 200 or status >= 300:
        return [f"{label} 远程图片不可访问：HTTP {status} {image_url}"]
    if content_type and not content_type.startswith("image/"):
        return [f"{label} 远程资源不是图片：{content_type} {image_url}"]
    return []


def validate_image_reference(
    article_path: Path,
    image_path: str,
    label: str,
    check_remote: bool = True,
) -> list[str]:
    errors: list[str] = []
    if not image_path:
        return [f"{label} 为空"]
    if is_url(image_path):
        if check_remote:
            return validate_remote_image(image_path, label)
        return []
    if image_path.startswith("data:") or image_path.startswith("asset://"):
        return []

    resolved = local_image_path(article_path, image_path)
    if resolved.suffix.lower() not in IMAGE_EXTENSIONS:
        errors.append(
            f"{label} 不是支持的图片格式：{image_path} "
            f"(仅支持 {', '.join(sorted(IMAGE_EXTENSIONS))})"
        )
    if not resolved.exists():
        errors.append(f"{label} 文件不存在：{image_path} -> {resolved}")
    elif resolved.stat().st_size == 0:
        errors.append(f"{label} 文件为空：{image_path} -> {resolved}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查 emotion_women 文章中的封面和正文图片是否可被 wenyan-mcp 上传",
    )
    parser.add_argument("file", help="文章 Markdown 路径")
    parser.add_argument(
        "--skip-remote-check",
        action="store_true",
        help="跳过远程图片 HTTP 探活，仅检查本地图片路径",
    )
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
    cover = meta.get("cover", "")
    body_images = image_paths(body)

    errors: list[str] = []
    if not meta.get("title"):
        errors.append("frontmatter 缺少 title")

    valid_cover = False
    if cover:
        cover_errors = validate_image_reference(
            article_path,
            cover,
            "cover",
            check_remote=not args.skip_remote_check,
        )
        errors.extend(cover_errors)
        valid_cover = not cover_errors

    valid_body_images = 0
    for index, path in enumerate(body_images, start=1):
        image_errors = validate_image_reference(
            article_path,
            path,
            f"正文图片 #{index}",
            check_remote=not args.skip_remote_check,
        )
        errors.extend(image_errors)
        if not image_errors:
            valid_body_images += 1

    if not valid_cover and valid_body_images == 0:
        errors.append("必须提供一张有效 cover，或在正文中至少引用一张有效图片")

    if errors:
        print("图片预检失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"图片预检通过：cover={'有' if valid_cover else '无'}，"
        f"正文有效图片 {valid_body_images} 张"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
