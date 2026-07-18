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
TITLE_BANNED_PREFIXES = (
    "她不再",
    "她没有再",
    "她没",
    "她把",
    "这次，她",
)
TITLE_BANNED_SURFACE_RE = re.compile(r"^她[^，,]{0,5}(不|没|把|下班|终于|再)")
TITLE_TEMPLATE_MIN_COUNT = 3

BANNED_PHRASES = [
    "每个人都值得被爱",
    "时间会治愈一切",
    "我们应该认识到",
    "综上所述",
    "由此可见",
    "女性要学会",
    "正确的做法是",
    "这告诉我们",
    "在这个快节奏的时代",
    "在这个充满挑战的时代",
    "你有没有发现",
    "值得注意的是",
    "不难发现",
    "愿每一个女孩",
    "愿每个女孩",
    "请相信",
]
ENUMERATION_PATTERNS = [
    r"首先[，,]",
    r"其次[，,]",
    r"最后[，,]",
    r"第一[，,：:]",
    r"第二[，,：:]",
    r"第三[，,：:]",
    r"一方面[，,]",
    r"另一方面[，,]",
]
STORY_TIME_PATTERNS = (
    r"那天|当天|第二天|后来|几天后|一个月后|早上|中午|晚上|"
    r"凌晨|回到家|出门时|下班后|吃饭时"
)
AUTHOR_SUMMARY_PATTERNS = (
    r"忽然明白|终于明白|这说明|这意味着|归根结底|说到底|"
    r"本质上|本来就该|道理很简单|真正的[^。！？\n]{0,30}(?:是|在于)"
)
RECOMMENDED_LOCAL_IMAGE_SIZE = (900, 600)
MIN_LOCAL_IMAGE_WIDTH = 900
MIN_LOCAL_IMAGE_HEIGHT = 600
MIN_LOCAL_IMAGE_ASPECT = 1.25
MAX_LOCAL_IMAGE_ASPECT = 1.95
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
    in_legacy = False
    for raw_line in IMAGE_POOL.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        upper = line.upper()
        if upper.startswith("## COVER"):
            in_cover = True
            in_legacy = upper.startswith("## COVER_LEGACY")
            continue
        if upper.startswith("## BODY"):
            in_cover = False
            in_legacy = False
            continue
        if (
            not in_cover
            or in_legacy
            or not line
            or line.startswith("#")
            or not is_image_reference(line)
        ):
            continue
        paths.add(image_reference_to_markdown_path(line))
    return paths


def title_errors(title: str) -> list[str]:
    compact = re.sub(r"\s+", "", title.strip().strip("'\""))
    errors: list[str] = []
    for prefix in TITLE_BANNED_PREFIXES:
        if compact.startswith(prefix):
            errors.append(f"title 使用了近期已禁用的同质化开头：{prefix}")
            break
    if TITLE_BANNED_SURFACE_RE.match(compact):
        errors.append("title 仍是“她 + 动作/否定”的旧外壳，请改成物件/场景/对话/时间钩子")
    labels = classify_title_templates(compact)
    if len(labels) < TITLE_TEMPLATE_MIN_COUNT:
        errors.append(
            f"title 只识别到 {len(labels)} 种方法：{'、'.join(labels) or '无'}；"
            f"至少需要融合 {TITLE_TEMPLATE_MIN_COUNT} 种标题方法"
        )
    return errors


def classify_title_templates(title: str) -> list[str]:
    labels: list[str] = []
    if re.search(r"\d|[一二三四五六七八九十百千万]+(?=个|种|句|点|次|年|岁|万|元|%)", title):
        labels.append("数字法")
    if re.search(r"[?？]|(吗|呢|么)$|为什么|怎么|到底|哪天|值不值|去不去|该不该|凭什么|算什么", title):
        labels.append("疑问法")
    if any(mark in title for mark in ("「", "」", "“", "”", '"')) or re.search(
        r".+[，,：:].+(关你|谢谢|够了|停下|算了|凭什么|别装)",
        title,
    ):
        labels.append("对话法")
    if re.search(r"不是|不再|别把|别再|却|一边.+一边|越.+越|只是不|而是|才是|和别人比|拿你.+比|没必要", title):
        labels.append("对比法")

    hot_words = (
        "边界感",
        "情绪价值",
        "恋爱脑",
        "冷暴力",
        "PUA",
        "原生家庭",
        "前任",
        "分手",
        "婚姻",
        "离婚",
        "催婚",
        "婆媳",
        "彩礼",
        "断亲",
        "内耗",
        "松弛感",
        "娘家",
        "饭桌",
        "家庭",
        "姐姐",
        "丈夫",
        "婆婆",
    )
    if any(word in title for word in hot_words):
        labels.append("热词法")
    if re.search(r"有一种|这[0-9一二三四五六七八九十]+|那[张顿只句个]|那些|后来.+怎么样|最.+的|永远是|压根|其实|凭什么|算什么", title):
        labels.append("好奇法")
    if any(phrase in title for phrase in ("一生一起走", "各自安好", "来都来了", "万一", "谁先", "人间值得", "算了", "不撞南墙", "体面")):
        labels.append("俗语法")
    if any(phrase in title for phrase in ("其实我不是", "我不是一个", "我猜中了", "曾经有一份", "后来的我们", "如果爱有天意", "这个杀手不太冷")):
        labels.append("电影台词法")
    return labels


def cjk_len(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def bold_or_quote_count(body: str) -> int:
    bold_count = len(re.findall(r"\*\*[^*\n]{8,80}\*\*", body))
    quote_count = len(re.findall(r"(?m)^>\s*.{8,80}$", body))
    return bold_count + quote_count


def heading_count(body: str) -> int:
    return len(re.findall(r"(?m)^##\s+\S", body))


def style_errors(body: str) -> list[str]:
    """Catch repeated structural habits that make batch articles read mechanically."""
    errors: list[str] = []
    enumeration_count = sum(len(re.findall(pattern, body)) for pattern in ENUMERATION_PATTERNS)
    if enumeration_count >= 2:
        errors.append(f"机械枚举过多：识别到 {enumeration_count} 个顺序连接词")

    contrast_count = len(re.findall(r"不是[^。！？\n]{0,35}而是", body))
    if contrast_count >= 3:
        errors.append(f"“不是……而是……”句式重复：识别到 {contrast_count} 处，最多 2 处")

    question_count = len(re.findall(r"[？?]", body))
    if question_count > 5:
        errors.append(f"问句过多：识别到 {question_count} 个，最多 5 个")

    ending = body[-350:]
    engagement_hits = [word for word in ("评论", "点赞", "转发", "分享") if word in ending]
    if len(engagement_hits) >= 3:
        errors.append(f"结尾出现互动三件套：{', '.join(engagement_hits)}，最多保留一个自然互动动作")
    return errors


def narrative_errors(body: str) -> list[str]:
    errors: list[str] = []
    dialogue_count = len(re.findall(r"[“\"][^”\"\n]{2,80}[”\"]", body))
    time_count = len(re.findall(STORY_TIME_PATTERNS, body))
    if dialogue_count < 1:
        errors.append("故事缺少人物对话：至少需要 1 处推动冲突的对话")
    if time_count < 1:
        errors.append("故事缺少推进：至少需要 1 个时间或场景变化信号")
    return errors


def author_summary_errors(body: str) -> list[str]:
    errors: list[str] = []
    summary_count = len(re.findall(AUTHOR_SUMMARY_PATTERNS, body))
    if summary_count >= 2:
        errors.append(f"作者总结过多：识别到 {summary_count} 处，应改成人物动作或对话")

    prose_lines = [
        line.strip()
        for line in body.splitlines()
        if line.strip() and not line.startswith("!") and not line.startswith("##")
    ]
    ending = "".join(prose_lines[-2:])
    if re.search(AUTHOR_SUMMARY_PATTERNS, ending):
        errors.append("结尾仍在解释故事意义，应停在动作、对话、环境声或物件上")
    return errors


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
        width, height = size
        aspect = width / height if height else 0
        if width < MIN_LOCAL_IMAGE_WIDTH or height < MIN_LOCAL_IMAGE_HEIGHT:
            errors.append(
                f"正文图片 #{index} 本地尺寸过小：{image} 为 {width}x{height}，"
                f"至少 {MIN_LOCAL_IMAGE_WIDTH}x{MIN_LOCAL_IMAGE_HEIGHT}，推荐 "
                f"{RECOMMENDED_LOCAL_IMAGE_SIZE[0]}x{RECOMMENDED_LOCAL_IMAGE_SIZE[1]}"
            )
        if aspect < MIN_LOCAL_IMAGE_ASPECT or aspect > MAX_LOCAL_IMAGE_ASPECT:
            errors.append(
                f"正文图片 #{index} 横图比例不适合：{image} 为 {width}x{height}，"
                f"宽高比 {aspect:.2f}，建议保持 {MIN_LOCAL_IMAGE_ASPECT:.2f}-{MAX_LOCAL_IMAGE_ASPECT:.2f}"
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
            f"至少 {MIN_LOCAL_DRAMA_EDGE_RMS:.1f}。请换高清横图，推荐 900x600 或更高分辨率"
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查 emotion_women 文章是否达到发布前的低成本质量门槛",
    )
    parser.add_argument("file", help="文章 Markdown 路径")
    parser.add_argument("--min-cjk", type=int, default=720)
    parser.add_argument("--max-cjk", type=int, default=900)
    parser.add_argument("--min-images", type=int, default=4)
    parser.add_argument("--min-golden", type=int, default=1)
    parser.add_argument("--max-golden", type=int, default=1)
    parser.add_argument("--min-headings", type=int, default=2)
    parser.add_argument("--max-headings", type=int, default=2)
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
    elif len(title) < 6:
        errors.append(f"title 太短：{title}")
    elif len(title) > 20:
        errors.append(f"title 太长：{len(title)} 字，最多 20 字")
    errors.extend(title_errors(title))

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
        legacy_note = "；COVER_LEGACY 旧封面不再允许作为普通文章封面" if "images/cover/" in images[0] else ""
        errors.append(f"正文第一张图不是当前人设封面图池图片：{images[0]}{legacy_note}")

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
    for index, image in enumerate(images[2:], start=3):
        if is_url(image):
            errors.append(f"正文氛围图 #{index} 必须使用本地稳定素材，不能使用远程接口图：{image}")

    golden = bold_or_quote_count(body)
    if golden < args.min_golden:
        errors.append(f"金句不足：识别到 {golden} 条，至少 {args.min_golden} 条")
    if golden > args.max_golden:
        errors.append(f"刻意突出句过多：识别到 {golden} 条，最多 {args.max_golden} 条")

    headings = heading_count(body)
    if headings < args.min_headings:
        errors.append(f"小标题不足：识别到 {headings} 个，至少 {args.min_headings} 个")
    if headings > args.max_headings:
        errors.append(f"小标题过多：识别到 {headings} 个，最多 {args.max_headings} 个")

    for phrase in BANNED_PHRASES:
        if phrase in body:
            errors.append(f"包含低质/AI感表达：{phrase}")
    errors.extend(style_errors(body))
    errors.extend(narrative_errors(body))
    errors.extend(author_summary_errors(body))

    if errors:
        print("质量门槛未通过：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"质量门槛通过：{length} 中文字符，{len(images)} 张正文图，"
        f"{golden} 处重点句，{headings} 个小标题"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
