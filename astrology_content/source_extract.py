#!/usr/bin/env python3
"""Fetch an article into the ignored sources directory for private analysis."""

from __future__ import annotations

import argparse
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib import error, request
from urllib.parse import urlparse

from quality_gate import cjk_len
from reference_policy import extract_page_title


BASE_DIR = Path(__file__).parent
SOURCES_DIR = BASE_DIR / "sources"
MIN_SOURCE_CJK = 500
MAX_BYTES = 5_000_000


class ArticleParser(HTMLParser):
    BLOCKS = {"article", "blockquote", "br", "div", "h1", "h2", "h3", "li", "p", "section"}
    SKIP = {"script", "style", "svg", "noscript", "iframe", "canvas"}

    def __init__(self, target_id: str | None = None) -> None:
        super().__init__(convert_charrefs=True)
        self.target_id = target_id
        self.target_depth = 0
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = dict(attrs)
        if tag in self.SKIP:
            self.skip_depth += 1
            return
        if self.target_id and attrs_dict.get("id") == self.target_id:
            self.target_depth = 1
        elif self.target_depth:
            self.target_depth += 1
        if tag in self.BLOCKS and (not self.target_id or self.target_depth):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
            return
        if tag in self.BLOCKS and (not self.target_id or self.target_depth):
            self.parts.append("\n")
        if self.target_depth:
            self.target_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth or (self.target_id and not self.target_depth):
            return
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.parts.append(text)

    @property
    def text(self) -> str:
        text = "".join(self.parts)
        lines = [line.strip() for line in re.sub(r"\n{3,}", "\n\n", text).splitlines()]
        return "\n".join(line for line in lines if line).strip()


NOISE_PHRASES = (
    "微信扫一扫",
    "取消允许",
    "预览时标签不可点",
    "在小说阅读器",
    "点击预约直播间",
    "环境异常",
    "微信公众平台",
    "赞，轻点两下取消赞",
    "在看，轻点两下取消在看",
)


def clean_text(text: str) -> str:
    cleaned: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", html.unescape(raw_line)).strip()
        if not line or any(phrase in line for phrase in NOISE_PHRASES):
            continue
        if re.search(r"^(来源|声明|作者|编辑|责编)\s*[|：:]", line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def fetch(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("只支持 HTTP/HTTPS 链接")
    user_agent = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1 astrology-source/1.0"
    )
    req = request.Request(url, headers={"User-Agent": user_agent, "Accept": "text/html"})
    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read(MAX_BYTES)
            charset = response.headers.get_content_charset() or "utf-8"
    except error.HTTPError as exc:
        raise RuntimeError(f"抓取失败：HTTP {exc.code}") from exc
    except (error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"抓取失败：{exc}") from exc
    markup = raw.decode(charset, errors="replace")
    title = extract_page_title(markup) or url

    targeted = ArticleParser(target_id="js_content")
    targeted.feed(markup)
    text = targeted.text
    if cjk_len(text) < MIN_SOURCE_CJK:
        generic = ArticleParser()
        generic.feed(markup)
        text = generic.text
    return title, clean_text(text)


def slugify(title: str) -> str:
    latin = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()
    return latin[:48] or "reference-source"


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取参考正文到已忽略的 sources 目录")
    parser.add_argument("url")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        title, text = fetch(args.url)
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    length = cjk_len(text)
    if length < MIN_SOURCE_CJK:
        print(
            f"抓取正文不足：{length} 个中文字符，至少需要 {MIN_SOURCE_CJK}。"
            "请将原文复制到本地文件。",
            file=sys.stderr,
        )
        return 1
    output = args.output or SOURCES_DIR / f"{slugify(title)}.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"URL: {args.url}\nTITLE: {title}\nCJK_LENGTH: {length}\n\n{text}\n", encoding="utf-8")
    print(f"来源标题：{title}")
    print(f"正文长度：{length} 个中文字符")
    print(f"已保存：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
