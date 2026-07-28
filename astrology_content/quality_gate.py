#!/usr/bin/env python3
"""Local format and source-overlap checks for Anxia-style short articles."""

from __future__ import annotations

import argparse
import re
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ARTICLE_MIN_CJK = 120
ARTICLE_MAX_CJK = 260
ARTICLE_EXTENDED_MAX_CJK = 450
TITLE_MIN_VISIBLE = 12
TITLE_MAX_VISIBLE = 28
MIN_HEADINGS = 0
MAX_HEADINGS = 0
REQUIRED_IMAGES = None
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
    metrics: dict[str, float | int | str]

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class GateProfile:
    name: str
    min_cjk: int
    max_cjk: int
    extended_max_cjk: int | None
    title_max_visible: int
    min_title_visible: int | None
    min_headings: int
    max_headings: int
    required_images: int | None
    opening_terms_required: bool
    banned_phrases: tuple[str, ...]
    enumeration_error_at: int
    overlap_rewrite_threshold: float
    overlap_reject_threshold: float


ANXIA_SHORT_PROFILE = GateProfile(
    name="anxia_short",
    min_cjk=ARTICLE_MIN_CJK,
    max_cjk=ARTICLE_MAX_CJK,
    extended_max_cjk=ARTICLE_EXTENDED_MAX_CJK,
    title_max_visible=TITLE_MAX_VISIBLE,
    min_title_visible=TITLE_MIN_VISIBLE,
    min_headings=MIN_HEADINGS,
    max_headings=MAX_HEADINGS,
    required_images=REQUIRED_IMAGES,
    opening_terms_required=False,
    banned_phrases=BANNED_PHRASES[:-1],
    enumeration_error_at=4,
    overlap_rewrite_threshold=0.05,
    overlap_reject_threshold=0.05,
)
DAILY_FORTUNE_PROFILE = GateProfile(
    name="daily_fortune",
    min_cjk=700,
    max_cjk=1400,
    extended_max_cjk=None,
    title_max_visible=36,
    min_title_visible=14,
    min_headings=4,
    max_headings=4,
    required_images=REQUIRED_IMAGES,
    opening_terms_required=False,
    banned_phrases=BANNED_PHRASES,
    enumeration_error_at=4,
    overlap_rewrite_threshold=0.05,
    overlap_reject_threshold=0.05,
)
STRONG_TITLE_TERMS = ABSOLUTE_PREDICTIONS
PROFILES = {
    ANXIA_SHORT_PROFILE.name: ANXIA_SHORT_PROFILE,
    DAILY_FORTUNE_PROFILE.name: DAILY_FORTUNE_PROFILE,
}
DEFAULT_PROFILE = ANXIA_SHORT_PROFILE.name


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
            if marker[0] in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                data = handle.read(5)
                if len(data) != 5:
                    return None
                height, width = struct.unpack(">HH", data[1:5])
                return width, height
            handle.seek(max(0, segment_length - 2), 1)


def _svg_size(path: Path) -> tuple[int, int] | None:
    if path.suffix.lower() != ".svg":
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    tag_match = re.search(r"<svg\b[^>]*>", text, flags=re.I | re.S)
    if not tag_match:
        return None
    attrs = dict(
        re.findall(
            r"([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*['\"]([^'\"]+)['\"]",
            tag_match.group(0),
        )
    )
    width = _svg_length(attrs.get("width", ""))
    height = _svg_length(attrs.get("height", ""))
    if width and height:
        return width, height
    view_box = attrs.get("viewBox") or attrs.get("viewbox")
    if not view_box:
        return None
    parts = [float(part) for part in re.findall(r"-?\d+(?:\.\d+)?", view_box)]
    if len(parts) != 4:
        return None
    return int(round(parts[2])), int(round(parts[3]))


def _svg_length(value: str) -> int | None:
    match = re.match(r"\s*(\d+(?:\.\d+)?)(?:px)?\s*\Z", value)
    if not match:
        return None
    return int(round(float(match.group(1))))


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        return _png_size(path) or _jpeg_size(path) or _svg_size(path)
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
    source_parts = {source_norm[index : index + width] for index in range(len(source_norm) - width + 1)}
    draft_parts = {draft_norm[index : index + width] for index in range(len(draft_norm) - width + 1)}
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


def corpus_article_paths(source_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in source_dir.glob("*.md")
        if re.match(r"\d{4}_\d{4}-\d{2}-\d{2}_", path.name)
    )


def load_source_dir(
    source_dir: Path,
    *,
    allow_hot_titles: bool = False,
    hot_title_min_count: int = 2,
    allow_all_source_titles: bool = False,
) -> tuple[set[str], list[tuple[str, str]]]:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"来源目录不存在：{source_dir}")
    titles: set[str] = set()
    title_counts: Counter[str] = Counter()
    sources: list[tuple[str, str]] = []
    for path in corpus_article_paths(source_dir):
        try:
            source_article = parse_article(path)
        except OSError:
            continue
        title = source_article.title
        if title:
            normalized = re.sub(r"\s+", "", title)
            titles.add(normalized)
            title_counts[normalized] += 1
        sources.append((path.name, source_article.body))
    if allow_all_source_titles:
        titles = set()
    elif allow_hot_titles:
        hot_titles = {title for title, count in title_counts.items() if count >= hot_title_min_count}
        titles -= hot_titles
    return titles, sources


def paragraph_count(body: str) -> int:
    count = 0
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if not block or block.startswith("!") or block.startswith("#"):
            continue
        if cjk_len(markdown_to_plain(block)):
            count += 1
    return count


def validate_article(
    article: Article,
    source_text: str | None = None,
    *,
    profile: str | GateProfile = DEFAULT_PROFILE,
    forbidden_titles: set[str] | None = None,
    source_texts: list[tuple[str, str]] | None = None,
) -> GateResult:
    gate_profile = PROFILES[profile] if isinstance(profile, str) else profile
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, float | int | str] = {"profile": gate_profile.name}

    if set(article.frontmatter) != {"title"}:
        errors.append("frontmatter 必须存在且只包含 title")
    if not article.title:
        errors.append("title 不能为空")
    title_length = visible_len(article.title)
    metrics["title_visible_chars"] = title_length
    if title_length > gate_profile.title_max_visible:
        errors.append(f"title 长度为 {title_length}，最多 {gate_profile.title_max_visible} 个可见字符")
    if gate_profile.min_title_visible and title_length < gate_profile.min_title_visible:
        warnings.append(f"title 长度为 {title_length}，建议不少于 {gate_profile.min_title_visible} 个可见字符")
    if forbidden_titles and re.sub(r"\s+", "", article.title) in forbidden_titles:
        errors.append("标题复用了安夏知识库原标题，必须重写")

    plain = markdown_to_plain(article.body)
    length = cjk_len(plain)
    metrics["body_cjk"] = length
    if length < gate_profile.min_cjk:
        errors.append(f"正文中文字符为 {length}，至少 {gate_profile.min_cjk}")
    elif length > gate_profile.max_cjk:
        if gate_profile.extended_max_cjk and length <= gate_profile.extended_max_cjk:
            warnings.append(f"正文中文字符为 {length}，超过目标 {gate_profile.max_cjk}，属于扩展稿")
        else:
            errors.append(f"正文中文字符为 {length}，要求 {gate_profile.min_cjk}-{gate_profile.max_cjk}")

    headings = re.findall(r"(?m)^##\s+\S", article.body)
    metrics["h2_count"] = len(headings)
    if not gate_profile.min_headings <= len(headings) <= gate_profile.max_headings:
        errors.append(f"二级小标题为 {len(headings)}，要求 {gate_profile.min_headings}-{gate_profile.max_headings} 个")

    paragraphs = paragraph_count(article.body)
    metrics["paragraph_count"] = paragraphs
    if gate_profile.name == "anxia_short" and not 3 <= paragraphs <= 6:
        errors.append(f"短文段落为 {paragraphs} 段，要求 3-6 段")
    if gate_profile.name == "daily_fortune" and not 14 <= paragraphs <= 16:
        errors.append(f"日运正文段落为 {paragraphs} 段，要求 14-16 段")

    images = image_references(article.body)
    metrics["image_count"] = len(images)
    if gate_profile.required_images is not None and len(images) != gate_profile.required_images:
        errors.append(f"图片为 {len(images)} 张，要求恰好 {gate_profile.required_images} 张")
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

    for phrase in gate_profile.banned_phrases:
        if phrase in plain:
            errors.append(f"出现模板化禁用语：{phrase}")
    strong_terms = [phrase for phrase in STRONG_TITLE_TERMS if phrase in article.title or phrase in plain]
    if strong_terms:
        warnings.append("出现强刺激星座词：" + "、".join(strong_terms))

    enumeration_count = sum(len(re.findall(pattern, plain)) for pattern in ENUMERATION_PATTERNS)
    metrics["enumeration_markers"] = enumeration_count
    if enumeration_count >= gate_profile.enumeration_error_at:
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
    if gate_profile.opening_terms_required and not any(term in opening for term in CONCRETE_OPENING_TERMS):
        warnings.append("前 100 个中文字未识别到常见的具体动作/物件，请人工复核开头")

    lengths = paragraph_lengths(article.body)
    if len(lengths) >= 6 and max(lengths) - min(lengths) < 25:
        warnings.append("段落长度过于整齐，建议按信息量重新分段")

    all_sources: list[tuple[str, str]] = []
    if source_text is not None:
        all_sources.append(("source-file", source_text))
    if source_texts:
        all_sources.extend(source_texts)

    max_longest = 0
    max_overlap = 0.0
    max_source_name = ""
    for source_name, candidate_source in all_sources:
        longest = longest_common_substring_length(candidate_source, article.body)
        overlap = shingle_overlap(candidate_source, article.body)
        if longest > max_longest or overlap > max_overlap:
            max_source_name = source_name
        max_longest = max(max_longest, longest)
        max_overlap = max(max_overlap, overlap)

    if all_sources:
        metrics["longest_source_match"] = max_longest
        metrics["source_shingle_overlap"] = round(max_overlap, 6)
        if max_source_name:
            metrics["source_count"] = len(all_sources)
        if max_longest >= LONGEST_MATCH_REJECT:
            errors.append(f"与来源存在 {max_longest} 个连续规范化字符相同，达到驳回线 {LONGEST_MATCH_REJECT}")
        if max_overlap >= gate_profile.overlap_reject_threshold:
            errors.append(f"18 字分片重合率 {max_overlap:.2%}，达到 {gate_profile.overlap_reject_threshold:.0%} 驳回线")
        elif max_overlap >= gate_profile.overlap_rewrite_threshold:
            errors.append(
                f"18 字分片重合率 {max_overlap:.2%}，处于 "
                f"{gate_profile.overlap_rewrite_threshold:.0%}-{gate_profile.overlap_reject_threshold:.0%} 人工重写区间"
            )

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
    parser = argparse.ArgumentParser(description="检查安夏短文号 Markdown 草稿")
    parser.add_argument("article", type=Path, help="Markdown 文章路径")
    parser.add_argument("--profile", choices=sorted(PROFILES), default=DEFAULT_PROFILE)
    parser.add_argument("--source-file", type=Path, help="可选的来源正文，用于原创度比较")
    parser.add_argument("--source-dir", type=Path, help="可选：安夏知识库目录，用于原标题和全库原创度检查")
    parser.add_argument("--allow-hot-titles", action="store_true", help="允许复用知识库中重复出现过的热标题")
    parser.add_argument("--hot-title-min-count", type=int, default=2, help="热标题最少重复次数，默认 2")
    parser.add_argument("--allow-all-source-titles", action="store_true", help="允许复用任意知识库原标题")
    args = parser.parse_args()

    if not args.article.is_file():
        parser.error(f"文章不存在：{args.article}")
    source_text = None
    if args.source_file:
        if not args.source_file.is_file():
            parser.error(f"来源文件不存在：{args.source_file}")
        source_text = args.source_file.read_text(encoding="utf-8", errors="ignore")
    forbidden_titles = None
    source_texts = None
    if args.source_dir:
        try:
            forbidden_titles, source_texts = load_source_dir(
                args.source_dir,
                allow_hot_titles=args.allow_hot_titles,
                hot_title_min_count=args.hot_title_min_count,
                allow_all_source_titles=args.allow_all_source_titles,
            )
        except FileNotFoundError as exc:
            parser.error(str(exc))

    result = validate_article(
        parse_article(args.article),
        source_text=source_text,
        profile=args.profile,
        forbidden_titles=forbidden_titles,
        source_texts=source_texts,
    )
    print(format_result(result))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
