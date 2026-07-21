#!/usr/bin/env python3
"""
情感女性公众号自动化生成与发布脚本
支持定时执行或立即执行，可自定义文章数量
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib import error, request
from zoneinfo import ZoneInfo

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional local color scoring
    Image = None

# 配置日志
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
MCP_CONFIG = BASE_DIR / ".mcp.json"
PUBLISH_THEME = "orangeheart"
ARTICLES_DIR = BASE_DIR / "articles"
IMAGES_DIR = BASE_DIR / "images"
IMAGE_POOL = BASE_DIR / "image_pool.txt"
DRAMA_IMAGE_POOL = BASE_DIR / "drama_image_pool.txt"
PUBLISH_HISTORY = LOG_DIR / "publish_history.jsonl"
SPECS_DIR = BASE_DIR / "specs"
MAX_LOG_OUTPUT_CHARS = 4000
RECENT_ARTICLES_FOR_DRAMA_IMAGES = 12
RECENT_ARTICLES_FOR_COVER_IMAGES = 12
MIN_COLORFUL_DRAMA_SCORE = 25.0
DEFAULT_PROVIDER = os.getenv("EMOTION_PROVIDER", "claude").strip().lower() or "claude"
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "3600"))
OPENAI_ENABLE_WEB_SEARCH = os.getenv("OPENAI_ENABLE_WEB_SEARCH", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}
ARTICLE_TARGET_CJK = 800
ARTICLE_MIN_CJK = 720
ARTICLE_MAX_CJK = 900
LIFESTYLE_SHARE = 0.4
MIN_LOCAL_IMAGE_SHORT_EDGE = 768
MIN_LOCAL_IMAGE_PIXELS = 1_200_000

BASE_TOOLS = [
    "WebSearch",
    "WebFetch",
    "Read",
    "Write",
    "Glob",
    "Grep",
    "Bash",
    "Task",
]
PUBLISH_TOOLS = [
    "mcp__wenyan-mcp__publish_article",
]
SPEC_FILES = [
    "account_positioning.md",
    "article_quality.md",
    "image_policy.md",
    "platform_rules.md",
    "workflow.md",
]


def get_beijing_time():
    """获取北京时间"""
    return datetime.now(ZoneInfo("Asia/Shanghai"))


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'emotion_women_{get_beijing_time().strftime("%Y%m")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def allowed_tools(publish: bool) -> str:
    tools = BASE_TOOLS + (PUBLISH_TOOLS if publish else [])
    return ",".join(tools)


def list_existing_titles(max_items: int = 30) -> list[str]:
    """读取本地已生成标题，避免让 Claude 再扫描全部文章。"""
    if not ARTICLES_DIR.exists():
        return []

    titles: list[str] = []
    files = sorted(ARTICLES_DIR.glob("*.md"), reverse=True)
    for path in files[:max_items]:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in content.splitlines()[:12]:
            line = line.strip()
            if line.startswith("title:"):
                titles.append(line.removeprefix("title:").strip().strip("'\""))
                break
    return titles


def planned_content_mix(article_count: int) -> tuple[int, int]:
    """返回（关系故事数，第一人称生活日记数）。"""
    if article_count <= 0:
        return 0, 0
    lifestyle_count = max(1, min(article_count, round(article_count * LIFESTYLE_SHARE)))
    return article_count - lifestyle_count, lifestyle_count


def format_content_mix_guidance(article_count: int) -> str:
    relationship_count, lifestyle_count = planned_content_mix(article_count)
    return f"""## 本批内容比例（必须执行）
- `relationship_story`：{relationship_count} 篇。第三人称的具体关系事件，保留冲突和实际后果。
- `lifestyle_diary`：{lifestyle_count} 篇。固定用第一人称“我”，从爬山、骑行、游泳、跑步、做饭、烘焙、逛菜场、吃小吃、逛街、整理房间中选一个当天行程。
- 生活日记必须有量化细节、感官/身体细节、小失误或临时变动、两次行程推进；感想不超过 20%。
- 不得把 `lifestyle_diary` 写成第三人称女主的关系冲突故事，也不得硬加“她终于学会爱自己”式觉醒。"""


TITLE_SURFACE_RECENT_WINDOW = 12
TITLE_SURFACE_AVOID_WINDOW = 6
TITLE_SURFACE_REPEAT_LIMIT = 2
TITLE_BANNED_PREFIXES = (
    "她不再",
    "她没有再",
    "她没",
    "她把",
    "这次，她",
)


def classify_title_surface(title: str) -> str:
    """Classify repeated title shells that make a batch feel samey."""
    compact = re.sub(r"\s+", "", title.strip().strip("'\""))
    compact = compact.removeprefix("title:").strip().strip("'\"")
    for prefix in TITLE_BANNED_PREFIXES:
        if compact.startswith(prefix):
            return prefix
    if re.match(r"^她[^，,]{0,5}(不|没|把|下班|终于|再)", compact):
        return "她 + 动作/否定"
    if compact.startswith("你"):
        return "你 + 判断"
    if compact.startswith("他"):
        return "他 + 行为"
    if re.match(r"^[那这有]\d|^这[一二三四五六七八九十0-9]", compact):
        return "数字/指代开头"
    if any(mark in compact for mark in ("「", "」", "“", "”", '"')):
        return "对话开头"
    if re.search(r"\d|[一二三四五六七八九十]+(?=天|年|次|句|双|元|个)", compact):
        return "时间/数字物件"
    return "其他"


def title_surface_counts(titles: list[str], window: int = TITLE_SURFACE_RECENT_WINDOW) -> dict[str, int]:
    counts: dict[str, int] = {}
    for title in titles[:window]:
        label = classify_title_surface(title)
        counts[label] = counts.get(label, 0) + 1
    return counts


def format_title_diversity_guidance(titles: list[str] | None = None) -> str:
    """Generate prompt guidance to avoid repeated title shells."""
    recent_titles = (titles if titles is not None else list_existing_titles(TITLE_SURFACE_RECENT_WINDOW))[
        :TITLE_SURFACE_RECENT_WINDOW
    ]
    if not recent_titles:
        return "最近无标题样本；标题仍需避免连续使用同一种开头。"

    recent_counts = title_surface_counts(recent_titles)
    avoid_counts = title_surface_counts(recent_titles, TITLE_SURFACE_AVOID_WINDOW)
    overloaded = [
        label
        for label, count in avoid_counts.items()
        if count >= TITLE_SURFACE_REPEAT_LIMIT or label in TITLE_BANNED_PREFIXES
    ]
    recent_brief = "\n".join(f"- {title}" for title in recent_titles)
    count_brief = "；".join(f"{label}{count}次" for label, count in sorted(recent_counts.items()))
    avoid_brief = "、".join(overloaded) if overloaded else "最近 6 篇暂无明显过载开头"
    examples = "\n".join(
        [
            "- 物件型：那双268元的鞋，她藏了三天",
            "- 对话型：「我没事」这句话最累",
            "- 时间型：分手半年，他还在用她的会员",
            "- 反常识型：婚姻里最怕的不是吵架",
            "- 动作后果型：饭局散后，她删了家庭群",
        ]
    )
    return f"""## 标题去同质化规则
最近 {TITLE_SURFACE_RECENT_WINDOW} 篇标题：
{recent_brief}

最近标题外壳统计：{count_brief}
本批必须避开的过载开头/外壳：{avoid_brief}

禁止只换物件复用“她不再.../她没有再.../她把.../这次，她...”这类女性主语开头；如果确实要用“她”，必须换成完全不同语序。
每篇先写 5 个不同外壳候选标题，再选最终标题：
{examples}

最终标题优先使用“具体物件/场景/时间 + 冲突”，不要连续使用同一种主语开头。"""


TITLE_TEMPLATE_RECENT_WINDOW = 12
TITLE_TEMPLATE_RECENT_AVOID = 3
TITLE_TEMPLATE_MIN_VARIETY = 3
TITLE_TEMPLATE_COMBO_SIZE = 3
TITLE_TEMPLATES = [
    {
        "name": "数字法",
        "short": "加入数字、比例、年龄、几句话/几点，增强具体感和点击冲动。",
        "example": "这3句话,90%的女生都说过",
    },
    {
        "name": "对比法",
        "short": "把两种反差状态并置，常用不是/却/一边一边/越越制造冲突。",
        "example": "你越懂事,他越不珍惜",
    },
    {
        "name": "热词法",
        "short": "把近期热点、热剧、热梗或高频情感词放进标题。",
        "example": "边界感火了,但很多人用错了",
    },
    {
        "name": "疑问法",
        "short": "用反常识问题收尾，让读者想确认答案。",
        "example": "你真以为沉默就是成熟吗",
    },
    {
        "name": "对话法",
        "short": "用一句生活里常见的话，加一句有力回应。",
        "example": "「我都是为你好」「那请你停下」",
    },
    {
        "name": "好奇法",
        "short": "话说一半，藏住关键答案，适合有一种/这几句/后来怎样。",
        "example": "有一种分手,说不出口却最痛",
    },
    {
        "name": "俗语法",
        "short": "借俗语、歌词、熟句改写，最好顺口、有记忆点。",
        "example": "懂事一生一起走,谁先心软谁先输",
    },
    {
        "name": "电影台词法",
        "short": "改编知名电影/台词/熟悉句式，让标题自带画面感。",
        "example": "其实我不是冷漠,我只是累了",
    },
]
TITLE_TEMPLATE_NAMES = [template["name"] for template in TITLE_TEMPLATES]


def classify_title_templates(title: str) -> list[str]:
    """用轻量启发式识别标题大致套用了哪些模板。"""
    title = title.strip()
    labels: list[str] = []

    if re.search(r"\d|[一二三四五六七八九十百千万]+(?=个|种|句|点|次|年|岁|%)", title):
        labels.append("数字法")

    if re.search(r"[?？]|(吗|呢|么)$|为什么|怎么|到底|哪天|值不值|去不去|该不该", title):
        labels.append("疑问法")

    if any(mark in title for mark in ("「", "」", "“", "”", '"')) or re.search(r".+[，,：:].+(关你|谢谢|够了|停下|算了)", title):
        labels.append("对话法")

    if re.search(r"不是|不再|别把|别再|却|一边.+一边|越.+越|只是不|而是|才是|和别人比|拿你.+比", title):
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
        "报复性熬夜",
    )
    if any(word in title for word in hot_words):
        labels.append("热词法")

    if re.search(r"有一种|这[0-9一二三四五六七八九十]+|那些|后来.+怎么样|最.+的|永远是|压根|其实", title):
        labels.append("好奇法")

    common_sayings = (
        "一生一起走",
        "各自安好",
        "来都来了",
        "万一",
        "谁先",
        "人间值得",
        "算了",
        "不撞南墙",
        "体面",
    )
    if any(phrase in title for phrase in common_sayings):
        labels.append("俗语法")

    movie_lines = (
        "其实我不是",
        "我不是一个",
        "我猜中了",
        "曾经有一份",
        "后来的我们",
        "如果爱有天意",
        "这个杀手不太冷",
    )
    if any(phrase in title for phrase in movie_lines):
        labels.append("电影台词法")

    return [name for name in TITLE_TEMPLATE_NAMES if name in labels] or ["未识别"]


def title_template_counts(titles: list[str]) -> dict[str, int]:
    counts = {name: 0 for name in TITLE_TEMPLATE_NAMES}
    for title in titles:
        for label in classify_title_templates(title):
            if label in counts:
                counts[label] += 1
    return counts


def select_title_templates(article_count: int, titles: list[str] | None = None) -> list[str]:
    """按最近使用情况为本批文章分配标题模板，优先补少用模板。"""
    if article_count <= 0:
        return []

    recent_titles = (titles if titles is not None else list_existing_titles(TITLE_TEMPLATE_RECENT_WINDOW))[
        :TITLE_TEMPLATE_RECENT_WINDOW
    ]
    counts = title_template_counts(recent_titles)
    recent_labels = {
        label
        for title in recent_titles[:TITLE_TEMPLATE_RECENT_AVOID]
        for label in classify_title_templates(title)
        if label in counts
    }

    ranked = sorted(
        TITLE_TEMPLATE_NAMES,
        key=lambda name: (
            1 if name in recent_labels else 0,
            counts[name],
            TITLE_TEMPLATE_NAMES.index(name),
        ),
    )
    unique_needed = min(len(TITLE_TEMPLATE_NAMES), article_count)
    selected = ranked[:unique_needed]
    while len(selected) < article_count:
        selected.append(ranked[len(selected) % len(ranked)])
    return selected[:article_count]


def select_title_template_combos(article_count: int, titles: list[str] | None = None) -> list[list[str]]:
    """为每篇文章分配 3 个标题模板，鼓励标题融合多个钩子。"""
    if article_count <= 0:
        return []

    recent_titles = (titles if titles is not None else list_existing_titles(TITLE_TEMPLATE_RECENT_WINDOW))[
        :TITLE_TEMPLATE_RECENT_WINDOW
    ]
    counts = title_template_counts(recent_titles)
    recent_labels = {
        label
        for title in recent_titles[:TITLE_TEMPLATE_RECENT_AVOID]
        for label in classify_title_templates(title)
        if label in counts
    }
    ranked = sorted(
        TITLE_TEMPLATE_NAMES,
        key=lambda name: (
            1 if name in recent_labels else 0,
            counts[name],
            TITLE_TEMPLATE_NAMES.index(name),
        ),
    )

    combos: list[list[str]] = []
    used_combo_keys: set[tuple[str, ...]] = set()
    for index in range(article_count):
        combo = [ranked[(index * TITLE_TEMPLATE_COMBO_SIZE + offset) % len(ranked)] for offset in range(TITLE_TEMPLATE_COMBO_SIZE)]
        combo_key = tuple(sorted(combo))
        shift = 1
        while combo_key in used_combo_keys and shift < len(ranked):
            combo = [ranked[(index * TITLE_TEMPLATE_COMBO_SIZE + offset + shift) % len(ranked)] for offset in range(TITLE_TEMPLATE_COMBO_SIZE)]
            combo_key = tuple(sorted(combo))
            shift += 1
        used_combo_keys.add(combo_key)
        combos.append(combo)
    return combos


def format_title_template_guidance(article_count: int, titles: list[str] | None = None) -> str:
    """生成可注入 Prompt 的标题模板组合说明。"""
    recent_titles = (titles if titles is not None else list_existing_titles(TITLE_TEMPLATE_RECENT_WINDOW))[
        :TITLE_TEMPLATE_RECENT_WINDOW
    ]
    counts = title_template_counts(recent_titles)
    plan = select_title_template_combos(article_count, recent_titles)
    template_brief = "\n".join(
        f"- {template['name']}：{template['short']}例：{template['example']}"
        for template in TITLE_TEMPLATES
    )
    count_brief = "；".join(f"{name}{counts[name]}次" for name in TITLE_TEMPLATE_NAMES)
    plan_brief = "\n".join(
        f"{index + 1}. 第 {index + 1} 篇必须融合：{' + '.join(combo)}"
        for index, combo in enumerate(plan)
    )
    examples = "\n".join(
        [
            "- 数字法 + 热词法 + 好奇法：分手半年，他还在用她的会员",
            "- 对话法 + 对比法 + 热词法：「我没事」才是婚姻里最累的话",
            "- 电影台词法 + 对比法 + 疑问法：其实我不是冷漠，你懂吗",
            "- 俗语法 + 数字法 + 对比法：这3次心软，谁先低头谁先累",
        ]
    )
    return f"""## 标题模板组合规则
每篇最终标题必须同时融合 8 个模板中的 {TITLE_TEMPLATE_COMBO_SIZE} 个，不是只选 1 个模板。优先补最近 {TITLE_TEMPLATE_RECENT_WINDOW} 篇里使用次数最低的模板；不要连续几篇都用同一种“你不是/别把/越...越...”风格。

最近 {TITLE_TEMPLATE_RECENT_WINDOW} 篇标题模板使用估算：{count_brief}

本批标题模板组合分配：
{plan_brief}

8 个可用标题模板：
{template_brief}

组合示例：
{examples}

每篇先按指定 3 模板组合写 5 个候选标题，再挑最自然、最有点击欲、最不像近期标题的 1 个作为最终 title；最终标题仍要 ≤20 字、只聚焦一个爆点。"""


def truncate_for_log(text: str) -> str:
    if len(text) <= MAX_LOG_OUTPUT_CHARS:
        return text
    return text[-MAX_LOG_OUTPUT_CHARS:]


def strip_agent_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return text.strip()


def read_project_specs_digest(max_chars: int = 16000) -> str:
    """Read stable account rules for non-file-aware providers."""
    if not SPECS_DIR.exists():
        return ""

    chunks: list[str] = []
    for name in SPEC_FILES:
        path = SPECS_DIR / name
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore").strip()
        if content:
            chunks.append(f"## specs/{name}\n{content}")

    digest = "\n\n".join(chunks).strip()
    return digest[:max_chars]


def read_writer_style_digest() -> str:
    """读取 Claude agent，并压缩成 OpenAI 生成时需要遵守的核心风格。"""
    agent_path = BASE_DIR / ".claude" / "agents" / "emotion-writer.md"
    if not agent_path.exists():
        return ""

    content = strip_agent_frontmatter(agent_path.read_text(encoding="utf-8", errors="ignore"))
    keep_sections = [
        "双轨内容模式",
        "不变的成稿模板",
        "素材边界",
        "同一模板里的结构轮换",
        "人物要像生活里的人",
        "语言要求",
        "唯一加粗句",
        "标题规则",
        "二次编辑",
        "格式与配图",
        "交稿检查",
    ]
    lines: list[str] = []
    keep = False
    for line in content.splitlines():
        if line.startswith("## "):
            keep = any(section in line for section in keep_sections)
        if keep:
            lines.append(line)
    digest = "\n".join(lines).strip()
    return digest[:12000]


def parse_image_pool() -> dict[str, list[str]]:
    """读取固定图池，返回 COVER/COVER_* 和 BODY 图片引用。"""
    pool = {"COVER": [], "BODY": []}
    if not IMAGE_POOL.exists():
        return pool

    current: str | None = None
    for raw_line in IMAGE_POOL.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("## COVER"):
            match = re.match(r"##\s+(COVER(?:_[A-Z0-9]+)?)", upper)
            current = match.group(1) if match else "COVER"
            pool.setdefault(current, [])
            continue
        if upper.startswith("## BODY"):
            current = "BODY"
            continue
        if line.startswith("#"):
            continue
        if current and is_image_reference(line):
            pool[current].append(line)
            if current.startswith("COVER_") and current != "COVER_LEGACY":
                pool["COVER"].append(line)
    return pool


def is_image_reference(value: str) -> bool:
    return (
        value.startswith("http://")
        or value.startswith("https://")
        or value.startswith("/")
        or value.startswith("./")
        or value.startswith("../")
        or value.startswith("photo-")
    )


def parse_drama_image_pool() -> list[str]:
    """读取影视/生活剧男女主合照图池，一行一个本地高清图片路径。"""
    if not DRAMA_IMAGE_POOL.exists():
        return []

    images: list[str] = []
    for raw_line in DRAMA_IMAGE_POOL.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if is_image_reference(line):
            images.append(line)
    return images


def image_reference_to_markdown_path(value: str) -> str:
    if value.startswith("photo-"):
        return f"https://images.unsplash.com/{value}?w=900"
    return value


def is_remote_image_reference(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://") or value.startswith("data:")


def local_image_path_from_reference(value: str) -> Path | None:
    if is_remote_image_reference(value) or value.startswith("photo-") or value.startswith("asset://"):
        return None

    candidate = Path(value)
    if candidate.is_absolute():
        return candidate

    if value.startswith("../") or value.startswith("./"):
        return (ARTICLES_DIR / candidate).resolve()
    return (BASE_DIR / candidate).resolve()


def image_meets_new_resolution(value: str) -> bool:
    """新文优先分配高清本地图；远程图和无 Pillow 环境交给后续校验。"""
    if Image is None:
        return True
    path = local_image_path_from_reference(value)
    if path is None or not path.exists():
        return True
    try:
        with Image.open(path) as image:
            width, height = image.size
    except OSError:
        return False
    return min(width, height) >= MIN_LOCAL_IMAGE_SHORT_EDGE and width * height >= MIN_LOCAL_IMAGE_PIXELS


@lru_cache(maxsize=256)
def drama_image_colorfulness(value: str) -> float:
    if Image is None:
        return 0.0

    path = local_image_path_from_reference(value)
    if not path or not path.exists():
        return 0.0

    try:
        with Image.open(path).convert("RGB") as im:
            sample = im.resize((180, 120))
            pixels = list(sample.getdata())
    except OSError:
        return 0.0

    rg = [red - green for red, green, _blue in pixels]
    yb = [0.5 * (red + green) - blue for red, green, blue in pixels]
    mean_rg = sum(rg) / len(rg)
    mean_yb = sum(yb) / len(yb)
    std_rg = math.sqrt(sum((value - mean_rg) ** 2 for value in rg) / len(rg))
    std_yb = math.sqrt(sum((value - mean_yb) ** 2 for value in yb) / len(yb))
    return math.sqrt(std_rg**2 + std_yb**2) + 0.3 * math.sqrt(mean_rg**2 + mean_yb**2)


def drama_source_group(value: str) -> str:
    stem = Path(value.split("?", 1)[0]).stem.lower()
    stem = re.sub(r"_900x600$", "", stem)
    stem = re.sub(r"_(left|right|center)$", "", stem)
    return stem


COVER_THEME_KEYWORDS = {
    "BREAKUP": (
        "分手",
        "前任",
        "失恋",
        "断联",
        "挽回",
        "放下",
        "体面",
        "秒回",
        "脑补",
        "深夜",
    ),
    "MARRIAGE": (
        "婚姻",
        "结婚",
        "老公",
        "丈夫",
        "妻子",
        "婆婆",
        "婆媳",
        "家务",
        "家庭",
        "孩子",
        "育儿",
        "妈妈",
        "女儿",
    ),
    "WORK": (
        "职场",
        "工作",
        "外派",
        "涨薪",
        "加班",
        "老板",
        "同事",
        "办公室",
        "辞职",
        "裸辞",
    ),
    "FRIENDSHIP": (
        "闺蜜",
        "朋友",
        "友情",
        "室友",
        "社交",
        "姐妹",
    ),
    "RELATIONSHIP": (
        "恋爱",
        "爱",
        "他",
        "男友",
        "伴侣",
        "边界感",
        "情绪价值",
        "冷淡",
        "比较",
        "别人比",
        "PUA",
        "恋爱脑",
    ),
    "SELF": (
        "独立",
        "内耗",
        "完美主义",
        "懂事",
        "成长",
        "松弛感",
        "焦虑",
        "怕",
        "求救",
        "讨厌",
        "冷漠",
    ),
}


def cover_theme_for_title(title: str) -> str:
    """根据标题关键词粗分封面主题。"""
    compact = re.sub(r"\s+", "", title or "")
    for theme, keywords in COVER_THEME_KEYWORDS.items():
        if any(keyword in compact for keyword in keywords):
            return theme
    return "SELF"


def recent_image_refs(max_articles: int = 5) -> set[str]:
    refs: set[str] = set()
    if not ARTICLES_DIR.exists():
        return refs
    image_re = re.compile(r"photo-[0-9]+")
    markdown_image_re = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
    for path in sorted(ARTICLES_DIR.glob("*.md"), reverse=True)[:max_articles]:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        refs.update(image_re.findall(content))
        refs.update(markdown_image_re.findall(content))
    return refs


def recent_cover_usage(max_articles: int = RECENT_ARTICLES_FOR_COVER_IMAGES) -> dict[str, int]:
    """Count covers from actual successful publishes, falling back to local articles."""
    usage: dict[str, int] = {}
    if PUBLISH_HISTORY.exists():
        records: list[dict] = []
        for line in PUBLISH_HISTORY.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and record.get("cover"):
                records.append(record)
        for record in records[-max_articles:]:
            cover = str(record["cover"])
            usage[cover] = usage.get(cover, 0) + 1
        if records:
            return usage

    if not ARTICLES_DIR.exists():
        return usage

    markdown_image_re = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
    for path in sorted(ARTICLES_DIR.glob("*.md"), reverse=True)[:max_articles]:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = markdown_image_re.search(content)
        if match:
            cover = match.group(1)
            usage[cover] = usage.get(cover, 0) + 1
    return usage


def article_snapshot() -> dict[Path, int]:
    snapshot: dict[Path, int] = {}
    if not ARTICLES_DIR.exists():
        return snapshot
    for path in ARTICLES_DIR.glob("*.md"):
        try:
            snapshot[path.resolve()] = path.stat().st_mtime_ns
        except OSError:
            continue
    return snapshot


def changed_article_paths(before: dict[Path, int]) -> list[Path]:
    changed: list[Path] = []
    if not ARTICLES_DIR.exists():
        return changed
    for path in ARTICLES_DIR.glob("*.md"):
        resolved = path.resolve()
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            continue
        if resolved not in before or before[resolved] != mtime_ns:
            changed.append(path)
    return sorted(changed, key=lambda item: item.stat().st_mtime_ns)


def rotate_candidates(items: list[str], offset: int) -> list[str]:
    if not items:
        return []
    offset = offset % len(items)
    return items[offset:] + items[:offset]


def candidates_with_recent_fallback(items: list[str], used_recent: set[str], offset: int, needed: int) -> list[str]:
    rotated = rotate_candidates(items, offset)
    available = [item for item in rotated if item not in used_recent]
    if len(available) >= needed:
        return available
    return rotated


def color_ranked_drama_candidates(items: list[str], offset: int) -> list[str]:
    """Prefer same-persona life scenes, then colorful local drama stills."""
    rotated = rotate_candidates(items, offset)
    order = {item: index for index, item in enumerate(rotated)}

    def sort_key(item: str) -> tuple[int, int, float, int]:
        color_score = drama_image_colorfulness(item)
        persona_bucket = 0 if "/images/persona/scenes/" in item.replace("\\", "/") else 1
        color_bucket = 0 if color_score >= MIN_COLORFUL_DRAMA_SCORE else 1
        return (persona_bucket, color_bucket, -color_score, order[item])

    return sorted(rotated, key=sort_key)


def choose_drama_sequence(
    items: list[str],
    used_recent: set[str],
    offset: int,
    needed: int,
) -> list[str]:
    """Pick drama stills with color, recent-use, and same-source diversity."""
    ranked = color_ranked_drama_candidates(items, offset)
    if not ranked or needed <= 0:
        return []

    selected: list[str] = []
    selected_items: set[str] = set()
    selected_groups: set[str] = set()

    def take(avoid_recent: bool, avoid_groups: bool, require_colorful: bool = False) -> bool:
        for candidate in ranked:
            if candidate in selected_items:
                continue
            if require_colorful and drama_image_colorfulness(candidate) < MIN_COLORFUL_DRAMA_SCORE:
                continue
            if avoid_recent and candidate in used_recent:
                continue
            group = drama_source_group(candidate)
            if avoid_groups and group in selected_groups:
                continue
            selected.append(candidate)
            selected_items.add(candidate)
            selected_groups.add(group)
            if len(selected) >= needed:
                return True
        return False

    passes = (
        (True, True, True),
        (True, False, True),
        (False, True, True),
        (False, False, True),
        (True, True, False),
        (True, False, False),
        (False, True, False),
        (False, False, False),
    )
    for avoid_recent, avoid_groups, require_colorful in passes:
        if take(avoid_recent, avoid_groups, require_colorful):
            return selected

    while len(selected) < needed:
        selected.append(ranked[len(selected) % len(ranked)])
    return selected


def choose_cover(
    pool: dict[str, list[str]],
    title: str,
    recent_usage: dict[str, int],
    used_batch: set[str],
    offset: int,
    index: int,
) -> str:
    theme = cover_theme_for_title(title)
    themed_key = f"COVER_{theme}"
    all_candidates = list(dict.fromkeys(pool["COVER"]))
    candidates = list(dict.fromkeys(pool.get(themed_key) or all_candidates))
    candidates = rotate_candidates(candidates, offset + index)
    all_candidates = rotate_candidates(all_candidates, offset + index)
    themed_candidates = set(candidates)
    order = {candidate: position for position, candidate in enumerate(all_candidates)}
    available = [candidate for candidate in all_candidates if candidate not in used_batch]
    ranked = sorted(
        available or all_candidates,
        key=lambda candidate: (
            recent_usage.get(candidate, 0),
            0 if candidate in themed_candidates else 1,
            order[candidate],
        ),
    )
    cover = ranked[0] if ranked else ""
    if not cover:
        raise RuntimeError(f"封面图池为空，请检查 {IMAGE_POOL}")
    used_batch.add(cover)
    return cover


def choose_images(article_count: int, titles: list[str] | None = None) -> list[list[str]]:
    """为每篇文章分配封面、同一人设生活分镜和正文氛围图。"""
    pool = parse_image_pool()
    pool = {
        key: [item for item in items if image_meets_new_resolution(item)]
        for key, items in pool.items()
    }
    used_recent = recent_image_refs()
    cover_usage = recent_cover_usage()
    used_recent_drama = recent_image_refs(max_articles=RECENT_ARTICLES_FOR_DRAMA_IMAGES)
    if not pool["COVER"] or not pool["BODY"]:
        raise RuntimeError(f"图片池不足，请检查 {IMAGE_POOL}")

    offset = int(get_beijing_time().strftime("%d%H%M"))
    drama_source = [item for item in parse_drama_image_pool() if image_meets_new_resolution(item)]
    if not drama_source:
        raise RuntimeError(f"影视剧照图池为空，请先维护 {DRAMA_IMAGE_POOL}")

    dramas = choose_drama_sequence(drama_source, used_recent_drama, offset, article_count)
    bodies = candidates_with_recent_fallback(pool["BODY"], used_recent, offset, article_count)

    allocations: list[list[str]] = []
    used_batch_covers: set[str] = set()
    for index in range(article_count):
        title = titles[index] if titles and index < len(titles) else ""
        cover = choose_cover(pool, title, cover_usage, used_batch_covers, offset, index)
        body_ids = [bodies[index % len(bodies)]]
        drama = dramas[index % len(dramas)]
        ids = [cover, drama] + body_ids
        urls = [image_reference_to_markdown_path(image_id) for image_id in ids]
        allocations.append(urls)
    return allocations


def slugify(value: str, fallback: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:48] or fallback


def strip_code_fence(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json|markdown|md)?\s*(.*?)\s*```$", text, re.S)
    return match.group(1).strip() if match else text


def extract_response_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]

    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    if chunks:
        return "\n".join(chunks)

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "text" and isinstance(value, str):
                    chunks.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return "\n".join(dict.fromkeys(chunks)).strip()


def parse_json_object(text: str) -> dict:
    text = strip_code_fence(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return json.loads(match.group(0))
        raise


def split_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", markdown.strip(), re.S)
    if not match:
        return {}, markdown.strip()
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip("'\"")
    return meta, match.group(2).strip()


def normalize_markdown(title: str, markdown: str, image_urls: list[str]) -> str:
    """统一成与 Claude agent 一致的 frontmatter + 正文配图格式。"""
    markdown = strip_code_fence(markdown)
    meta, body = split_frontmatter(markdown)
    title = (title or meta.get("title") or "她终于不哄了").strip().strip("'\"")

    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if re.match(r"^!\[[^\]]*\]\([^)]+\)\s*$", stripped):
            continue
        if stripped.startswith("# "):
            continue
        lines.append(line.rstrip())
    body = "\n".join(lines).strip()

    body_lines = body.splitlines()
    body_image_count = max(0, len(image_urls) - 1)
    insert_positions = [
        index for index, line in enumerate(body_lines) if line.startswith("## ")
    ][1 : 1 + body_image_count]

    if len(insert_positions) < body_image_count:
        paragraph_positions = [
            index
            for index, line in enumerate(body_lines)
            if line.strip() and not line.startswith(">") and not line.startswith("## ")
        ]
        ratios = [
            (position + 1) / (body_image_count + 1)
            for position in range(body_image_count)
        ]
        for ratio in ratios:
            if not paragraph_positions:
                break
            insert_positions.append(paragraph_positions[min(int(len(paragraph_positions) * ratio), len(paragraph_positions) - 1)])
        insert_positions = sorted(set(insert_positions))[:body_image_count]

    for url, position in sorted(zip(image_urls[1:], insert_positions), key=lambda item: item[1], reverse=True):
        body_lines[position:position] = ["", f"![]({url})", ""]

    if len(insert_positions) < body_image_count:
        for url in image_urls[1 + len(insert_positions):]:
            body_lines.extend(["", f"![]({url})", ""])

    normalized_body = "\n".join(body_lines).strip()
    return f"---\ntitle: {title}\n---\n\n![]({image_urls[0]})\n\n{normalized_body}\n"


def normalize_generated_articles(article_paths: list[Path]) -> tuple[bool, list[tuple[Path, str]]]:
    """Rewrite generated drafts so image order follows cover -> drama still -> body images."""
    if not article_paths:
        return True, []

    titles: list[str] = []
    for path in article_paths:
        content = path.read_text(encoding="utf-8")
        meta, _body = split_frontmatter(content)
        titles.append(meta.get("title") or path.stem)
    image_allocations = choose_images(len(article_paths), titles)
    results: list[tuple[Path, str]] = []
    all_ok = True
    for path, title, image_urls in zip(article_paths, titles, image_allocations):
        content = path.read_text(encoding="utf-8")
        path.write_text(normalize_markdown(title, content, image_urls), encoding="utf-8")

        ok, output = run_preflight(path)
        results.append((path, output))
        all_ok = all_ok and ok
    return all_ok, results


def run_preflight(
    article_path: Path,
    *,
    min_title: int = 6,
    max_title: int = 20,
) -> tuple[bool, str]:
    outputs: list[str] = []
    for script in ("validate_article_images.py", "quality_gate.py"):
        command = [sys.executable, str(BASE_DIR / script), str(article_path)]
        if script == "quality_gate.py":
            command.extend(["--min-title", str(min_title), "--max-title", str(max_title)])
        result = subprocess.run(
            command,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
        )
        outputs.append((result.stdout or "") + (result.stderr or ""))
        if result.returncode != 0:
            return False, "\n".join(outputs).strip()
    return True, "\n".join(outputs).strip()


def publish_article(article_path: Path, verbose: bool = False) -> tuple[bool, str]:
    cmd = [
        sys.executable,
        str(BASE_DIR / "publish_existing_article.py"),
        str(article_path),
        "--theme",
        PUBLISH_THEME,
    ]
    if verbose:
        cmd.append("--verbose")
    result = subprocess.run(cmd, cwd=BASE_DIR, capture_output=not verbose, text=True)
    output = "" if verbose else ((result.stdout or "") + (result.stderr or ""))
    return result.returncode == 0, output.strip()


class EmotionWomenAutomation:
    """情感女性公众号自动化处理类"""

    def __init__(
        self,
        working_dir: str = None,
        article_count: int = 3,
        verbose: bool = False,
        publish: bool = False,
        provider: str = DEFAULT_PROVIDER,
        openai_model: str = DEFAULT_OPENAI_MODEL,
    ):
        self.working_dir = working_dir or str(BASE_DIR)
        self.article_count = article_count
        self.verbose = verbose
        self.publish = publish
        self.provider = provider.strip().lower()
        self.openai_model = openai_model.strip()
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """加载 prompt 模板"""
        existing_titles = list_existing_titles()
        if existing_titles:
            dedup_block = "\n".join(f"- {title}" for title in existing_titles)
        else:
            dedup_block = "- 暂无"
        title_diversity = format_title_diversity_guidance(existing_titles)
        title_template_guidance = format_title_template_guidance(self.article_count, existing_titles)
        content_mix = format_content_mix_guidance(self.article_count)

        if self.publish and self.provider != "claude":
            publish_step = f"""- 保存后依次运行：
  `python3 validate_article_images.py <文章绝对路径>`
  `python3 quality_gate.py <文章绝对路径>`
- 两个本地检查都通过后，调用 `mcp__wenyan-mcp__publish_article`，参数：`file=<文章绝对路径>`、`theme_id={PUBLISH_THEME}`。
- 不要传 `app_id`；不要群发；发布失败只记录原因并继续下一篇。"""
            publish_summary = "、草稿箱 media_id 或发布失败原因"
            publish_note = "- 本次需要发布到微信公众号草稿箱，但不直接群发，最终由人工在公众号后台审核后发布。"
        elif self.publish:
            publish_step = """- 保存后运行 `python3 validate_article_images.py <文章绝对路径>` 与 `python3 quality_gate.py <文章绝对路径>`。
- 不调用 wenyan-mcp，不发布；主脚本会在生成结束后统一重排配图、复检并发布到公众号草稿箱。"""
            publish_summary = "、本地质检结果"
            publish_note = "- 本次需要发布到微信公众号草稿箱，但发布动作由主脚本在配图后处理通过后统一执行。"
        else:
            publish_step = "- 保存后运行 `python3 validate_article_images.py <文章绝对路径>` 与 `python3 quality_gate.py <文章绝对路径>`；不调用 wenyan-mcp。"
            publish_summary = ""
            publish_note = "- 本次只生成本地草稿，不调用 wenyan-mcp，不触碰微信公众号。"

        return f"""# 情感女性公众号内容生成任务（热点兼容 + 图池省时版）

## 第一步：轻量定选题

1. 先扫已发文章标题去重（只读标题，不读全文）：
   ```bash
   rg -N '^title:' articles/*.md | sort -u
   ```
2. 允许最多 4 次 WebSearch 获取近期热点钩子，总搜索词从这些里选最相关的组合：`微博 情感 热搜`、`女性成长 热议`、`亲密关系 边界感`、`分手 心理 内耗`、`婚姻 情绪价值`。不要展开无关网页。
3. 筛出 {self.article_count} 个题。优先“热点钩子 + 普世痛点 + 反常识洞察”，热点只是引子，不为追热点牺牲文章完成度。与已发标题去重，宁缺毋滥。
4. 每个选题都要整理好：
   - 内容类型：`relationship_story` 或 `lifestyle_diary`
   - 选题标题/方向
   - 热点钩子：今天为什么值得写，相关事件/话题/讨论是什么
   - 女性读者的情绪入口
   - 核心反常识洞察
   - 1-2 条参考链接或素材摘要

{content_mix}

## 已发标题，必须避开近似选题
{dedup_block}

## 标题要求
标题从文章里最具体的冲突或动作提炼。按“一种方法做主要外壳、另外两种只补信息或语气”的方式融合 3 种方法，不把数字、疑问、对比并排堆砌。本批标题的句式和长度要自然变化。

{title_template_guidance}

{title_diversity}

## 长期规则文件
账号定位、文章质量、图片策略、平台规则和职责边界已沉淀到 `specs/`：
- `specs/account_positioning.md`
- `specs/article_quality.md`
- `specs/image_policy.md`
- `specs/platform_rules.md`
- `specs/workflow.md`

如临时 prompt 与 `specs/` 冲突，以更具体、更靠近当前任务的规则为准；不要为了确认通用规则去读取 README 全文。

## 第二步：并行启动 emotion-writer agent

为每个选定主题启动一个 emotion-writer agent，传递上面的选题信息、明确的内容类型和输出文件路径。写手不得自行把 `lifestyle_diary` 改成关系故事。

每个 agent 需要：
1. 不重复热点广搜；仅在素材不足、需要确认最新表述、或需要找真实讨论入口时，最多 1 次精准 WebSearch。
2. 配图全部从固定图池直接挑：每篇共 3 张，包含封面 1 张和正文图 2 张。封面从 `image_pool.txt` 的 COVER_* 高清本地人设池挑 1 张；第二张优先从 `drama_image_pool.txt` 挑同一人设的生活分镜，第三张从 BODY 段挑同一人设的结尾/氛围图。人设图不足才兜底彩色现代剧照。
   - 图池条目可以是完整 URL、本地图片路径，或旧的 `photo-...` ID；写入正文时直接使用已分配好的图片路径。
   - 严禁临时搜图、严禁下载图片、严禁跑 Python/PIL 做图像分析。
   - 同一批文章的影视剧照优先使用年轻、现代、彩色、生活剧关系感图片；尽量避开最近 12 篇已用影视剧照，并尽量避免同一来源场景。不要使用年代感强的黑白老片剧照。
3. 写一篇约 {ARTICLE_TARGET_CJK} 个中文字符的情感文章，成稿必须在 {ARTICLE_MIN_CJK}-{ARTICLE_MAX_CJK} 个中文字符之间（Markdown 与图片地址不计）。
4. 保存为 `./articles/YYYYMMDD_HHMM_topic.md`。
{publish_step}

**文章要求**：
- 标题 ≤20 字，只聚焦一个具体矛盾；不硬塞热词，不写"论…""如何…""关于…的思考"这类概括式标题。
- 前 80 个中文字符内进入具体矛盾；一篇只写一个核心判断，不套固定三段式。
- `relationship_story` 必须有一条完整故事线，故事占正文至少 75%。`lifestyle_diary` 必须用第一人称记录一次具体生活行程，现场细节占至少 80%，不强行对话或人际冲突。
- 素材没有真人案例时允许写场景化故事；正文不插入“人物虚构/情节合成”免责声明，也不声称来自朋友、读者投稿或咨询案例。
- 固定使用 2 个具体事件小标题和 1 处加粗；加粗必须是人物现场说的话或带具体物件的句子，不能是普适道理。
- 作者分析最多两小段、每段不超过 60 个中文字符；结尾停在动作、对话、环境声或物件上，不解释故事意义。
- 保留上述模板数量，但同批文章的开头方式、加粗位置、图片落点、冲突结果和结尾类型必须轮换；不得复用近期文章的段落功能顺序。
- 关系文的人物改变以后保留至少一个实际后果；生活日记只需保留腿酸、迷路、做糊、突然下雨或白跑一趟等真实阻力，不得为了戏剧性硬编伴侣/朋友冲突。
- 加粗句若是“有些女人/很多女人/真正的关系/好的婚姻/让人失眠的关系”一类万能判断，直接重写成现场原话或带物件的句子。
- “忽然、终于、第一次、那一刻、她明白了”全文合计不超过 2 次；不总用精确钟点开场，不总用水声、风声、绿植、账单和灯光收尾。
- 结尾在观点落地处自然停住，最多留 1 个具体问题，不同时索要评论、点赞和转发。
- 删除排比升华、成串反问、机械枚举，以及“不是……而是……”“真正的……是……”等连续口号句。
- 文末绝不列「参考资料/参考来源/资料来源/References」等出处链接清单，资料用大白话融进正文即可。
- 无 AI 鸡汤味。
- 每篇固定 3 张图（含封面）：第一张为 28-32 岁成年女性的轻熟妩媚高清封面，精致日常妆容、人脸和眼睛锐利对焦，完整着装且不低俗；后两张优先同一人设的生活分镜，不足时才兜底彩色现代剧照；frontmatter 只写 title。

## 第三步：汇总结果

所有 agent 完成后，汇报每篇文章的标题、文件路径、一句话摘要{publish_summary}。

**重要**：
{publish_note}
- 不要询问确认，直接执行所有步骤。
- 并行运行所有 agent 提高效率。"""

    def generate_prompt(self) -> str:
        """生成当天的 prompt（使用北京时间）"""
        today = get_beijing_time().strftime("%Y年%m月%d日")
        return f"今天是北京时间 {today}。\n\n{self.prompt_template}"

    def run(self) -> bool:
        if self.provider == "claude":
            return self.run_claude_code()
        if self.provider == "openai":
            return self.run_openai_api()
        logger.error(f"❌ 不支持的 provider: {self.provider}，可选 claude/openai")
        return False

    def openai_request(self, messages: list[dict], use_web_search: bool = False) -> str:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("缺少 OPENAI_API_KEY，请先在环境变量中配置")

        body: dict = {
            "model": self.openai_model,
            "input": messages,
            "max_output_tokens": min(max(6000 * self.article_count, 8000), 24000),
        }
        if use_web_search and OPENAI_ENABLE_WEB_SEARCH:
            body["tools"] = [
                {
                    "type": "web_search_preview",
                    "search_context_size": "low",
                }
            ]

        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{OPENAI_BASE_URL}/responses",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=OPENAI_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            if use_web_search and ("web_search" in detail or "tool" in detail):
                logger.warning("OpenAI web_search 不可用，降级为无联网生成")
                return self.openai_request(messages, use_web_search=False)
            raise RuntimeError(f"OpenAI API 请求失败: HTTP {exc.code}\n{truncate_for_log(detail)}") from exc

        text = extract_response_text(data)
        if not text:
            raise RuntimeError(f"OpenAI API 未返回文本: {truncate_for_log(json.dumps(data, ensure_ascii=False))}")
        return text

    def build_openai_prompt(self, image_allocations: list[list[str]] | None = None) -> list[dict]:
        existing_title_list = list_existing_titles()
        existing_titles = "\n".join(f"- {title}" for title in existing_title_list) or "- 暂无"
        title_diversity = format_title_diversity_guidance(existing_title_list)
        title_template_guidance = format_title_template_guidance(self.article_count, existing_title_list)
        content_mix = format_content_mix_guidance(self.article_count)
        project_specs = read_project_specs_digest()
        style_digest = read_writer_style_digest()
        today = get_beijing_time().strftime("%Y年%m月%d日")
        if image_allocations:
            image_plan = "\n".join(
                f"{index + 1}. 封面：{urls[0]}；封面后第一张正文图：{urls[1]}；正文图：{', '.join(urls[2:])}"
                for index, urls in enumerate(image_allocations)
            )
        else:
            image_plan = "保存时由脚本按标题主题自动匹配：封面从 COVER_* 本地精选池选，且优先使用 images/persona/scenes/ 同一人设图；第二张从 drama_image_pool.txt 选，第三张从 BODY 选。"

        system = """你是情感女性公众号的资深主编和主笔。
你要生成可直接保存为微信公众号草稿的 Markdown 文章。账号同时包含关系故事和第一人称生活日记。模板只控制标题、篇幅、小标题、加粗和配图数量，不能让同批文章拥有相同的开头、转折、重点句位置和结尾。不扮演专家，不虚构案例冒充真人经历，不把生活日记硬写成第三人称觉醒故事。
只输出 JSON，不要输出解释、代码围栏、参考资料列表。"""

        user = f"""今天是北京时间 {today}。请一次生成 {self.article_count} 篇情感女性公众号文章。

## 热点兼容
- 允许使用 OpenAI web search 获取近期热点钩子，但最多做 4 次热点广搜。
- 热点只做引子，不写成新闻复述；优先“热点钩子 + 普世痛点 + 反常识洞察”。
- 如果无法联网，也要基于普世情感痛点完成文章。

## 已发标题，必须避开近似选题
{existing_titles}

## 标题要求
标题从文章里最具体的冲突或动作提炼。按“一种方法做主要外壳、另外两种只补信息或语气”的方式融合 3 种方法，不把数字、疑问、对比并排堆砌。本批标题的句式和长度要自然变化。

{title_template_guidance}

{title_diversity}

{content_mix}

## 长期规则摘要
{project_specs}

## 固定配图
每篇文章保存时会统一插入 3 张高清图片：第一张是同一成年女性人设封面，后两张优先同一人设的生活分镜；人设图不足才兜底彩色现代剧照。frontmatter 只写 title。
{image_plan}

## 输出格式
只输出一个 JSON 对象：
{{
  "articles": [
    {{
      "title": "20字以内的标题",
      "content_type": "relationship_story 或 lifestyle_diary",
      "topic_slug": "英文小写短横线 slug",
      "summary": "一句话摘要",
      "markdown": "完整 Markdown，包含 frontmatter 和正文"
    }}
  ]
}}

## 每篇硬性要求
- 正文目标 {ARTICLE_TARGET_CJK} 个中文字符，必须在 {ARTICLE_MIN_CJK}-{ARTICLE_MAX_CJK} 个中文字符之间（Markdown 与图片地址不计）；标题≤20字，只写一个具体矛盾。
- 前 80 个中文字符内进入具体矛盾，不以泛泛提问、宏大判断或情绪标签开场。
- `relationship_story`：写一条占正文至少 75% 的完整故事线，有起因、具体冲突、人物反应、变化、对话和实际后果。
- `lifestyle_diary`：固定用“我”的第一人称，现场细节占至少 80%；包含 1 个量化细节、1 个身体/味觉/触感细节、1 个小失误或临时变动、2 次行程推进；不强制对话或人际冲突，感想不超过 20%。
- 没有真人素材时允许写场景化故事；正文不插入“人物虚构/情节合成”免责声明，也不声称来自朋友经历、读者投稿或咨询案例。
- 固定 2 个具体事件小标题、1 处加粗；加粗必须来自人物现场对话或具体物件，不能是脱离故事也成立的道理。
- 作者分析最多两小段、每段不超过 60 个中文字符；结尾停在动作、对话、环境声或物件上，不解释故事意义。
- 同批文章必须轮换开头方式、加粗位置、3 张图片在段落中的落点、冲突结果和结尾类型；不得复用“精确时间开场—冲突对话—万能金句—第二天立边界—物件升华”。
- 关系文作出改变后至少留下一个不方便的后果。生活日记只需保留腿酸、迷路、做糊、突然下雨、白跑一趟等真实阻力，不得硬编人际对抗。
- 唯一加粗句必须是现场原话、短信原句或带明确物件和动作的句子；禁止“有些女人/很多女人/真正的关系/好的婚姻/让人失眠的关系”等万能金句。
- “忽然、终于、第一次、那一刻、她明白了”全文合计不超过 2 次；最近文章用过的水声、风声、绿植、账单和灯光不再换词复用为象征性收尾。
- 不列三条建议，不用整齐的“观点-解释-总结”段落，不连续使用反问、排比或“不是……而是……”句式。
- 结尾自然停止，最多留一个具体问题，不同时索要评论、点赞和转发，不写“愿你”“请相信”式祝福。
- 文末绝不列参考资料/来源链接。
- 不要出现这些模型化表达：每个人都值得被爱、时间会治愈一切、我们应该认识到、综上所述、由此可见、女性要学会、正确的做法是、这告诉我们、在这个快节奏的时代、你有没有发现、真正的爱从来不是。

## emotion-writer 风格摘要
{style_digest}
"""
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def repair_with_openai(self, title: str, markdown: str, image_urls: list[str], errors_text: str) -> str:
        messages = [
            {
                "role": "system",
                "content": "你是公众号文章质检修稿编辑。只输出 JSON，不要解释。",
            },
            {
                "role": "user",
                "content": f"""下面文章未通过本地质检，请在保持标题、主题、风格和图片 URL 不变的前提下修复。

质检错误：
{errors_text}

必须满足：
- 正文目标 {ARTICLE_TARGET_CJK} 个中文字符，保持在 {ARTICLE_MIN_CJK}-{ARTICLE_MAX_CJK} 个中文字符之间；
- 固定使用 3 张图片（含封面），且只用这些 URL：{', '.join(image_urls)}；
- 固定 2 个具体事件小标题和 1 处来自故事现场的加粗句；
- 只修复质检指出的问题，不用套话扩字，不新增虚构案例；
- 删除机械枚举、排比升华、互动三件套、万能加粗句和重复总结；
- 改变与近期文章重复的开头、加粗/图片位置、转折和结尾，但仍保持 2 个小标题、1 处加粗和 3 张图片；
- 不把冲突修成一句话解决，至少保留一个人物需要承担的实际后果；
- frontmatter 只写 title。

只输出：
{{"markdown":"修复后的完整 Markdown"}}

原标题：{title}
原文：
{markdown}
""",
            },
        ]
        text = self.openai_request(messages, use_web_search=False)
        data = parse_json_object(text)
        return str(data.get("markdown") or markdown)

    def save_openai_articles(self, articles: list[dict], image_allocations: list[list[str]]) -> list[tuple[Path, str, str]]:
        saved: list[tuple[Path, str, str]] = []
        timestamp = get_beijing_time().strftime("%Y%m%d_%H%M")
        for index, article in enumerate(articles[: self.article_count]):
            title = str(article.get("title") or "").strip()
            slug = slugify(str(article.get("topic_slug") or title), f"openai-{index + 1}")
            path = ARTICLES_DIR / f"{timestamp}_{slug}.md"
            if path.exists():
                path = ARTICLES_DIR / f"{timestamp}_{slug}-{index + 1}.md"

            markdown = normalize_markdown(title, str(article.get("markdown") or ""), image_allocations[index])
            path.write_text(markdown, encoding="utf-8")
            saved.append((path, title, str(article.get("summary") or "").strip()))
        return saved

    def run_openai_api(self) -> bool:
        start = time.perf_counter()
        logger.info("=" * 60)
        logger.info(f"开始执行 情感女性公众号 OpenAI API 自动化任务 - {get_beijing_time()}")
        logger.info(f"文章数量: {self.article_count} 篇")
        logger.info(f"OpenAI 模型: {self.openai_model}")
        logger.info(f"发布模式: {'发布到公众号草稿箱' if self.publish else '仅生成本地草稿'}")
        logger.info("=" * 60)

        try:
            ARTICLES_DIR.mkdir(exist_ok=True)
            messages = self.build_openai_prompt()
            logger.info("调用 OpenAI API 生成文章...")
            text = self.openai_request(messages, use_web_search=True)
            data = parse_json_object(text)
            articles = data.get("articles", [])
            if not isinstance(articles, list) or len(articles) < self.article_count:
                raise RuntimeError(f"OpenAI 返回文章数量不足：{len(articles) if isinstance(articles, list) else 0}/{self.article_count}")

            titles = [str(article.get("title") or "").strip() for article in articles[: self.article_count]]
            image_allocations = choose_images(self.article_count, titles)
            saved = self.save_openai_articles(articles, image_allocations)
            all_ok = True
            for index, (path, title, summary) in enumerate(saved):
                ok, output = run_preflight(path)
                if not ok:
                    logger.warning(f"文章质检未通过，尝试修复：{path.name}\n{truncate_for_log(output)}")
                    repaired = self.repair_with_openai(
                        title,
                        path.read_text(encoding="utf-8"),
                        image_allocations[index],
                        output,
                    )
                    path.write_text(normalize_markdown(title, repaired, image_allocations[index]), encoding="utf-8")
                    ok, output = run_preflight(path)

                if ok:
                    logger.info(f"✅ 文章通过质检：{path}")
                else:
                    all_ok = False
                    logger.error(f"❌ 文章仍未通过质检：{path}\n{truncate_for_log(output)}")
                    continue

                if self.publish:
                    published, publish_output = publish_article(path, self.verbose)
                    if published:
                        logger.info(f"✅ 已发布到公众号草稿箱：{path.name}")
                    else:
                        all_ok = False
                        logger.error(f"❌ 发布失败：{path.name}\n{truncate_for_log(publish_output)}")

                logger.info(f"结果：标题={title or path.stem}；摘要={summary or '无'}；路径={path}")

            elapsed = time.perf_counter() - start
            logger.info(f"OpenAI API 自动化任务结束，耗时 {elapsed:.1f}s")
            logger.info("=" * 60)
            return all_ok
        except Exception as exc:
            logger.error(f"❌ OpenAI API 自动化任务失败: {exc}")
            logger.exception(exc)
            return False

    def run_claude_code(self):
        """执行 Claude Code 命令（headless 模式）"""
        try:
            logger.info("=" * 60)
            logger.info(f"开始执行 情感女性公众号 自动化任务 - {get_beijing_time()}")
            logger.info(f"文章数量: {self.article_count} 篇")
            logger.info(f"发布模式: {'发布到公众号草稿箱' if self.publish else '仅生成本地草稿'}")
            logger.info("=" * 60)

            ARTICLES_DIR.mkdir(exist_ok=True)
            IMAGES_DIR.mkdir(exist_ok=True)
            before_articles = article_snapshot()
            prompt = self.generate_prompt()
            tools = allowed_tools(False)

            logger.info(f"工作目录: {self.working_dir}")
            logger.info(f"使用 headless 模式{' [实时输出]' if self.verbose else ''}")
            logger.info(f"允许工具: {tools}")

            # 构造 Claude Code headless 命令
            cmd = [
                'claude',
                '-p', prompt,
                '--allowedTools', tools,
            ]

            if self.verbose:
                cmd.append('--verbose')

            cmd.extend([
                '--permission-mode', 'bypassPermissions',
                '--output-format', 'text'
            ])

            # 执行命令
            if self.verbose:
                logger.info("⏳ 正在执行，将显示 Claude 详细执行过程...")
                logger.info("-" * 60)
                result = subprocess.run(
                    cmd,
                    cwd=self.working_dir,
                    timeout=3600
                )
                logger.info("-" * 60)
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=self.working_dir,
                    timeout=3600
                )

                if result.returncode == 0:
                    logger.info("✅ 任务执行成功")
                    if result.stdout:
                        logger.info(f"输出尾部:\n{truncate_for_log(result.stdout)}")
                else:
                    logger.error(f"❌ 任务执行失败 (返回码: {result.returncode})")
                    if result.stderr:
                        logger.error(f"错误信息:\n{truncate_for_log(result.stderr)}")

            if self.verbose and result.returncode == 0:
                logger.info("✅ 任务执行成功")

            generated_paths = changed_article_paths(before_articles)
            success = result.returncode == 0
            if not generated_paths:
                if success:
                    logger.error("❌ Claude 执行成功，但没有发现本轮新增或修改的文章")
                success = False
            else:
                if result.returncode != 0:
                    logger.warning("Claude 返回码非 0，但发现本轮文章，继续尝试统一重排配图并复检")
                logger.info(f"发现本轮生成/修改文章 {len(generated_paths)} 篇，开始统一重排配图并复检")
                postprocess_ok, preflight_results = normalize_generated_articles(generated_paths)
                for path, output in preflight_results:
                    if "质量门槛未通过" in output or "图片预检失败" in output:
                        logger.error(f"❌ 后处理质检未通过：{path.name}\n{truncate_for_log(output)}")
                    else:
                        logger.info(f"✅ 后处理质检通过：{path.name}")
                success = postprocess_ok

            if success and self.publish:
                for path in generated_paths:
                    published, publish_output = publish_article(path, self.verbose)
                    if published:
                        logger.info(f"✅ 已发布到公众号草稿箱：{path.name}")
                    else:
                        logger.error(f"❌ 发布失败：{path.name}\n{truncate_for_log(publish_output)}")
                        success = False

            logger.info("=" * 60)
            logger.info(f"任务结束 - {get_beijing_time()}")
            logger.info("=" * 60)

            return success

        except subprocess.TimeoutExpired:
            logger.error("❌ 任务执行超时（超过1小时）")
            return False
        except Exception as e:
            logger.error(f"❌ 执行过程中发生错误: {str(e)}")
            logger.exception(e)
            return False


def run_now(
    article_count: int,
    verbose: bool = False,
    publish: bool = False,
    provider: str = DEFAULT_PROVIDER,
    openai_model: str = DEFAULT_OPENAI_MODEL,
):
    """立即执行任务"""
    logger.info("🚀 立即执行模式")
    automation = EmotionWomenAutomation(
        article_count=article_count,
        verbose=verbose,
        publish=publish,
        provider=provider,
        openai_model=openai_model,
    )
    success = automation.run()
    return 0 if success else 1


def beijing_to_utc(beijing_time_str: str) -> str:
    """将北京时间 HH:MM 转换为 UTC 时间 HH:MM"""
    hour, minute = map(int, beijing_time_str.split(':'))
    utc_hour = (hour - 8) % 24
    return f"{utc_hour:02d}:{minute:02d}"


def run_scheduled(
    article_count: int,
    schedule_times: list = None,
    verbose: bool = False,
    publish: bool = False,
    provider: str = DEFAULT_PROVIDER,
    openai_model: str = DEFAULT_OPENAI_MODEL,
):
    """定时执行任务（支持多个时间点）- 使用北京时间"""
    import schedule
    import time

    if schedule_times is None:
        schedule_times = ["09:00"]

    logger.info("⏰ 定时执行模式（北京时间）")
    logger.info(f"调度时间: 每天 {', '.join(schedule_times)} 北京时间")
    logger.info(f"文章数量: {article_count} 篇")
    logger.info(f"生成 provider: {provider}")
    if provider == "openai":
        logger.info(f"OpenAI 模型: {openai_model}")
    logger.info(f"实时输出: {'开启' if verbose else '关闭'}")
    logger.info(f"发布模式: {'发布到公众号草稿箱' if publish else '仅生成本地草稿'}")

    beijing_now = get_beijing_time()
    logger.info(f"当前北京时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}")

    def job():
        logger.info(f"🚀 定时任务触发 - 北京时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
        automation = EmotionWomenAutomation(
            article_count=article_count,
            verbose=verbose,
            publish=publish,
            provider=provider,
            openai_model=openai_model,
        )
        automation.run()

    for beijing_time_str in schedule_times:
        utc_time_str = beijing_to_utc(beijing_time_str)
        schedule.every().day.at(utc_time_str).do(job)
        logger.info(f"✅ 已设置定时任务: 每天 {beijing_time_str} 北京时间 (UTC {utc_time_str})")

    logger.info("⏳ 等待调度...")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("\n👋 服务已停止")
        return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='情感女性公众号自动化生成与发布系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 立即生成 1 篇文章
  python daily_emotion_women.py --now --count 1

  # 使用 OpenAI API 生成 1 篇文章（需 OPENAI_API_KEY）
  python daily_emotion_women.py --now --count 1 --provider openai

  # 立即生成 1 篇文章（实时显示执行过程）
  python daily_emotion_women.py --now --count 1 --verbose

  # 立即生成 3 篇文章
  python daily_emotion_women.py --now --count 3

  # 立即生成 1 篇并发布到公众号草稿箱
  python daily_emotion_women.py --now --count 1 --publish

  # 定时每天 09:00 和 21:00 各生成 3 篇文章
  python daily_emotion_women.py --time 09:00 21:00 --count 3

  # 定时每天晚上9点生成 2 篇文章（实时输出）
  python daily_emotion_women.py --time 21:00 --count 2 -v
        """
    )

    parser.add_argument(
        '--now',
        action='store_true',
        help='立即执行任务（不等待定时）'
    )

    parser.add_argument(
        '--count',
        type=int,
        default=3,
        help='生成文章数量（默认: 3）'
    )

    parser.add_argument(
        '--time',
        type=str,
        nargs='+',
        default=['09:00'],
        help='定时执行时间，格式 HH:MM，支持多个时间点（默认: 09:00）'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='实时显示 Claude 执行过程'
    )

    parser.add_argument(
        '--publish',
        action='store_true',
        help='成稿后通过 wenyan-mcp 发布到微信公众号草稿箱（需配置 emotion_women/.mcp.json）'
    )

    parser.add_argument(
        '--provider',
        choices=['claude', 'openai'],
        default=DEFAULT_PROVIDER if DEFAULT_PROVIDER in {'claude', 'openai'} else 'claude',
        help='生成调度方式：claude 保持原 Claude Code 流程；openai 使用 OpenAI API（默认: claude，可用 EMOTION_PROVIDER 覆盖）'
    )

    parser.add_argument(
        '--openai-model',
        default=DEFAULT_OPENAI_MODEL,
        help=f'OpenAI API 模型（默认: {DEFAULT_OPENAI_MODEL}，可用 OPENAI_MODEL 覆盖）'
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("情感女性公众号自动化系统")
    logger.info("=" * 60)
    logger.info(f"文章数量: {args.count} 篇")
    if args.now:
        logger.info("执行模式: 立即执行")
    else:
        times_str = ', '.join(args.time) if isinstance(args.time, list) else args.time
        logger.info(f"执行模式: 定时执行 ({times_str})")
    logger.info(f"生成 provider: {args.provider}")
    if args.provider == "openai":
        logger.info(f"OpenAI 模型: {args.openai_model}")
    logger.info(f"实时输出: {'开启' if args.verbose else '关闭'}")
    logger.info(f"发布模式: {'发布到公众号草稿箱' if args.publish else '仅生成本地草稿'}")
    logger.info("=" * 60)

    if args.now:
        return run_now(args.count, args.verbose, args.publish, args.provider, args.openai_model)
    else:
        return run_scheduled(args.count, args.time, args.verbose, args.publish, args.provider, args.openai_model)


if __name__ == "__main__":
    exit(main())
