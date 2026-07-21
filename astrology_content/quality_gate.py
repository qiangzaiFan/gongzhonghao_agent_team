#!/usr/bin/env python3
"""Local format, style, image, and source-overlap checks for astrology articles."""

from __future__ import annotations

import argparse
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


ARTICLE_MIN_CJK = 900
ARTICLE_MAX_CJK = 1200
TITLE_MAX_VISIBLE = 20
MIN_HEADINGS = 2
MAX_HEADINGS = 4
REQUIRED_IMAGES = 3
MIN_IMAGE_SHORT_EDGE = 600
MIN_IMAGE_PIXELS = 900 * 600
SHINGLE_WIDTH = 18
OVERLAP_REWRITE_THRESHOLD = 0.05
OVERLAP_REJECT_THRESHOLD = 0.08
LONGEST_MATCH_REJECT = 30

BANNED_PHRASES = (
    "在这个快节奏的时代",
    "你有没有发现",
    "真正的爱从来不是",
    "这告诉我们",
    "时间会治愈一切",
    "学会爱自己",
    "请相信",
    "愿你",
)
ABSOLUTE_PREDICTIONS = (
    "注定",
    "一定会",
    "百分百",
    "必定",
    "马上转运",
    "绝对",
    "肯定复合",
    "永远不会",
)
ENUMERATION_PATTERNS = (
    r"首先[,，]",
    r"其次[,，]",
    r"最后[,，]",
    r"第一[,，：:]",
    r"第二[,，：:]",
    r"第三[,，：:]",
    r"一方面[,，]",
    r"另一方面[,，]",
)
CONCRETE_OPENING_TERMS = (
    "手机",
    "聊天",
    "消息",
    "相册",
    "照片",
    "收藏",
    "路线",
    "钥匙",
    "订单",
    "备忘录",
    "门",
    "桌",
    "衣服",
    "删",
    "点开",
    "绕路",
    "取消",
    "退出",
    "放回",
)


@dataclass
class Article:
    path: Path
    frontmatter: dict[str, str]
    body: str

    @property
    def title(self) -> str:
        return self.frontmatter.get("title", "")


@dataclass
class GateResult:
    errors: list[str]
    warnings: list[str]
    metrics: dict[str, float | int]

    @property
    def ok(self) -> bool:
        return not self.errors


def parse_article(path: Path) -> Article:
    content = path.read_text(encoding="utf-8", errors="strict")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", content, re.S)
    if not match:
        return Article(path=path, frontmatter={}, body=content)

    frontmatter: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            frontmatter[line] = ""
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip("'\"")
    return Article(path=path, frontmatter=frontmatter, body=match.group(2))


def markdown_to_plain(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)
    text = re.sub(r"[*_`>~]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def cjk_len(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def visible_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def image_references(body: str) -> list[str]:
    return re.findall(r"!\[[^\]]*\]\(([^)]+)\)", body)


def _png_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) >= 24 and header[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", header[16:24])
    return None


def _jpeg_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as handle:
        if handle.read(2) != b"\xff\xd8":
            return None
        while True:
            marker_start = handle.read(1)
            if not marker_start:
                return None
            if marker_start != b"\xff":
                continue
            marker = handle.read(1)
            while marker == b"\xff":
                marker = handle.read(1)
            if not marker or marker in {b"\xd8", b"\xd9"}:
                continue
            length_bytes = handle.read(2)
            if len(length_bytes) != 2:
                return None
            segment_length = struct.unpack(">H", length_bytes)[0]
            if marker[0] in {
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            }:
                data = handle.read(5)
                if len(data) != 5:
                    return None
                height, width = struct.unpack(">HH", data[1:5])
                return width, height
            handle.seek(max(0, segment_length - 2), 1)


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        return _png_size(path) or _jpeg_size(path)
    except OSError:
        return None


def normalize_for_overlap(text: str) -> str:
    text = re.sub(r"\A---.*?---", "", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)
    return "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text)).lower()


def shingle_overlap(source: str, draft: str, width: int = SHINGLE_WIDTH) -> float:
    source_norm = normalize_for_overlap(source)
    draft_norm = normalize_for_overlap(draft)
    if len(source_norm) < width or len(draft_norm) < width:
        return 0.0
    source_parts = {
        source_norm[index : index + width]
        for index in range(len(source_norm) - width + 1)
    }
    draft_parts = {
        draft_norm[index : index + width]
        for index in range(len(draft_norm) - width + 1)
    }
    return len(source_parts & draft_parts) / min(len(source_parts), len(draft_parts))


def longest_common_substring_length(source: str, draft: str) -> int:
    """Return the longest continuous normalized match using O(min(m, n)) memory."""
    left = normalize_for_overlap(source)
    right = normalize_for_overlap(draft)
    if len(left) < len(right):
        left, right = right, left
    previous = [0] * (len(right) + 1)
    longest = 0
    for left_char in left:
        current = [0] * (len(right) + 1)
        for index, right_char in enumerate(right, start=1):
            if left_char == right_char:
                current[index] = previous[index - 1] + 1
                longest = max(longest, current[index])
        previous = current
    return longest


def paragraph_lengths(body: str) -> list[int]:
    lengths: list[int] = []
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if not block or block.startswith("!") or block.startswith("##"):
            continue
        length = cjk_len(markdown_to_plain(block))
        if length:
            lengths.append(length)
    return lengths


def validate_article(article: Article, source_text: str | None = None) -> GateResult:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, float | int] = {}

    if set(article.frontmatter) != {"title"}:
        errors.append("frontmatter 必须存在且只包含 title")
    if not article.title:
        errors.append("title 不能为空")
    title_length = visible_len(article.title)
    metrics["title_visible_chars"] = title_length
    if title_length > TITLE_MAX_VISIBLE:
        errors.append(f"title 长度为 {title_length}，最多 {TITLE_MAX_VISIBLE} 个可见字符")

    plain = markdown_to_plain(article.body)
    length = cjk_len(plain)
    metrics["body_cjk"] = length
    if not ARTICLE_MIN_CJK <= length <= ARTICLE_MAX_CJK:
        errors.append(
            f"正文中文字符为 {length}，要求 {ARTICLE_MIN_CJK}-{ARTICLE_MAX_CJK}"
        )

    headings = re.findall(r"(?m)^##\s+\S", article.body)
    metrics["h2_count"] = len(headings)
    if not MIN_HEADINGS <= len(headings) <= MAX_HEADINGS:
        errors.append(f"二级小标题为 {len(headings)}，要求 {MIN_HEADINGS}-{MAX_HEADINGS} 个")

    images = image_references(article.body)
    metrics["image_count"] = len(images)
    if len(images) != REQUIRED_IMAGES:
        errors.append(f"图片为 {len(images)} 张，要求恰好 {REQUIRED_IMAGES} 张")
    for reference in images:
        if re.match(r"https?://", reference):
            errors.append(f"图片必须为本地文件：{reference}")
            continue
        image_path = (article.path.parent / reference).resolve()
        if not image_path.is_file():
            errors.append(f"本地图片不存在：{reference}")
            continue
        dimensions = image_size(image_path)
        if dimensions is None:
            errors.append(f"无法识别图片格式或尺寸：{reference}")
            continue
        width, height = dimensions
        if min(width, height) < MIN_IMAGE_SHORT_EDGE or width * height < MIN_IMAGE_PIXELS:
            errors.append(
                f"图片分辨率过低：{reference} ({width}x{height})，"
                f"短边至少 {MIN_IMAGE_SHORT_EDGE}、总像素至少 {MIN_IMAGE_PIXELS}"
            )

    for phrase in BANNED_PHRASES:
        if phrase in plain:
            errors.append(f"出现模板化禁用语：{phrase}")
    for phrase in ABSOLUTE_PREDICTIONS:
        if phrase in plain:
            errors.append(f"出现绝对预测词：{phrase}")

    enumeration_count = sum(len(re.findall(pattern, plain)) for pattern in ENUMERATION_PATTERNS)
    metrics["enumeration_markers"] = enumeration_count
    if enumeration_count >= 2:
        errors.append(f"机械枚举连接词为 {enumeration_count} 个，需要重写段落推进")

    question_count = len(re.findall(r"[?？]", plain))
    metrics["question_marks"] = question_count
    if question_count > 5:
        errors.append(f"问句过多：{question_count} 个，最多 5 个")

    contrast_count = len(re.findall(r"不是[^。！？\n]{0,40}而是", plain))
    metrics["not_but_patterns"] = contrast_count
    if contrast_count > 2:
        errors.append(f"“不是……而是……”重复 {contrast_count} 次，最多 2 次")

    opening = "".join(re.findall(r"[\u4e00-\u9fff]", plain))[:100]
    if not any(term in opening for term in CONCRETE_OPENING_TERMS):
        warnings.append("前 100 个中文字未识别到常见的具体动作/物件，请人工复核开头")

    lengths = paragraph_lengths(article.body)
    if len(lengths) >= 6 and max(lengths) - min(lengths) < 25:
        warnings.append("段落长度过于整齐，建议按信息量重新分段")

    if source_text is not None:
        longest = longest_common_substring_length(source_text, article.body)
        overlap = shingle_overlap(source_text, article.body)
        metrics["longest_source_match"] = longest
        metrics["source_shingle_overlap"] = round(overlap, 6)
        if longest >= LONGEST_MATCH_REJECT:
            errors.append(
                f"与来源存在 {longest} 个连续规范化字符相同，"
                f"达到驳回线 {LONGEST_MATCH_REJECT}"
            )
        if overlap >= OVERLAP_REJECT_THRESHOLD:
            errors.append(f"18 字分片重合率 {overlap:.2%}，达到 8% 驳回线")
        elif overlap >= OVERLAP_REWRITE_THRESHOLD:
            errors.append(f"18 字分片重合率 {overlap:.2%}，处于 5%-8% 人工重写区间")

    return GateResult(errors=errors, warnings=warnings, metrics=metrics)


def format_result(result: GateResult) -> str:
    lines = ["本地质检：" + ("通过" if result.ok else "未通过")]
    lines.append("指标：" + "，".join(f"{key}={value}" for key, value in result.metrics.items()))
    if result.errors:
        lines.append("错误：")
        lines.extend(f"- {item}" for item in result.errors)
    if result.warnings:
        lines.append("提示：")
        lines.extend(f"- {item}" for item in result.warnings)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="检查星座公众号 Markdown 草稿")
    parser.add_argument("article", type=Path, help="Markdown 文章路径")
    parser.add_argument("--source-file", type=Path, help="可选的来源正文，用于原创度比较")
    args = parser.parse_args()

    if not args.article.is_file():
        parser.error(f"文章不存在：{args.article}")
    source_text = None
    if args.source_file:
        if not args.source_file.is_file():
            parser.error(f"来源文件不存在：{args.source_file}")
        source_text = args.source_file.read_text(encoding="utf-8", errors="ignore")

    result = validate_article(parse_article(args.article), source_text=source_text)
    print(format_result(result))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
