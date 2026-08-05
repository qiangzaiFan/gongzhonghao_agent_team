#!/usr/bin/env python3
"""Generate Anxia-style short article drafts in one command."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import math
from base64 import b64encode
from html import escape
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:  # pragma: no cover - surfaced with a useful message at runtime
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageOps = None

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
FOOD_DIR = ROOT_DIR / "food_home_cooking"


def load_comfy_image_module():
    module_path = FOOD_DIR / "generate_article_images.py"
    spec = importlib.util.spec_from_file_location("food_home_cooking_generate_article_images", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 ComfyUI 图片模块：{module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


comfy_images = load_comfy_image_module()

from ai_detector import ANXIA_SHORT_MIN_TOTAL_CHARS, DetectorUnavailable, default_report_path, detect_article
from anxia_calendar import CalendarItem, generate_calendar
from anxia_corpus import DEFAULT_CORPUS_DIR, SIGN_TERMS, hot_titles_by_reuse, load_corpus, normalized_title
from content_record import DEFAULT_RECORD_DIR, write_generated_record
from performance_tracker import DEFAULT_LOG_PATH, load_entries
from quality_gate import (
    format_result,
    load_source_dir,
    longest_common_substring_length,
    markdown_to_plain,
    parse_article,
    shingle_overlap,
    validate_article,
)


ARTICLES_DIR = BASE_DIR / "articles"
DEFAULT_DAILY_SHORT_ARTICLES = 2
RECENT_DRAFT_DAYS = 30
RECENT_DRAFT_LONGEST_MATCH = 55
RECENT_DRAFT_OVERLAP = 0.14
DAILY_RECENT_DRAFT_LONGEST_MATCH = 75
DAILY_RECENT_DRAFT_OVERLAP = 0.35
PET_COVER_ASSET_DIR = BASE_DIR / "assets" / "pet_covers"
PET_COVER_SIZE = (1200, 800)
DEFAULT_COMFY_ENDPOINT = "http://127.0.0.1:8188"
DEFAULT_COMFY_PROFILE = "flux2_klein"
PET_COVER_BASE_PROMPT = (
    "healing cute pet editorial cover for a Chinese horoscope WeChat short article, "
    "warm and soothing mood, adorable companion animal, clean cozy scene, soft natural light, "
    "gentle pastel accents, realistic photography, high detail fur texture, bright clear eyes, "
    "calm expression, uncluttered background, horizontal 3:2 composition, generous quiet negative space, "
    "premium lifestyle magazine photo, no text, no watermark, no logo"
)
PET_COVER_NEGATIVE_PROMPT = (
    "text, watermark, logo, typography, Chinese characters, zodiac symbols, horoscope wheel, tarot cards, "
    "crystal ball, poster, collage, social media UI, human, face, hands, scary, aggressive, dirty, cage, "
    "medical scene, deformed animal, extra legs, extra eyes, distorted paws, blurry, low quality, overexposed, "
    "underexposed, oversaturated neon color, harsh flash, messy background, anime, cartoon, illustration"
)
PET_COVER_PETS = {
    "白羊": "a fluffy white puppy sitting on a soft blanket, curious and bright",
    "金牛": "a golden retriever puppy resting beside a warm window, peaceful and loyal",
    "双子": "two tiny kittens leaning together on a clean sofa, lively but gentle",
    "巨蟹": "a cream-colored kitten curled near a cushion, safe and comforting",
    "狮子": "a fluffy orange kitten sitting proudly in soft sunlight, cute and confident",
    "处女": "a small white rabbit on a tidy linen blanket, delicate and clean",
    "天秤": "a graceful ragdoll kitten beside simple flowers, soft and balanced",
    "天蝎": "a black kitten with bright eyes in warm low light, mysterious but sweet",
    "射手": "a corgi puppy looking toward a sunlit doorway, cheerful and free",
    "摩羯": "a calm shiba puppy resting on a simple rug, steady and warm",
    "水瓶": "a silver-gray kitten near a pale blue cushion, fresh and clever",
    "双鱼": "a tiny lop-eared rabbit beside a soft blue blanket, dreamy and healing",
}


@dataclass(frozen=True)
class Draft:
    item: CalendarItem
    body: str
    title_candidates: tuple[str, ...]
    title_variants: tuple[dict[str, str], ...]
    body_variant: dict[str, str]
    opening_variant: dict[str, str]
    opening_candidates: tuple[dict[str, str], ...]
    title_override: str | None = None
    recent_conflict: str | None = None

    @property
    def title(self) -> str:
        return self.title_override or self.item.title


@dataclass(frozen=True)
class AiCheckResult:
    path: Path
    passed: bool
    ratios: dict[str, float]
    mean_ai_probability: float | None = None
    error: str | None = None


@dataclass(frozen=True)
class RecentSimilarity:
    source_name: str
    longest_match: int
    overlap: float

    @property
    def conflicts(self) -> bool:
        return self.conflicts_with(
            longest_match=RECENT_DRAFT_LONGEST_MATCH,
            overlap=RECENT_DRAFT_OVERLAP,
        )

    def conflicts_with(self, *, longest_match: int, overlap: float) -> bool:
        return self.longest_match >= longest_match or self.overlap >= overlap


@dataclass(frozen=True)
class DailyFortuneCard:
    sign: str
    summary: str
    score: int
    matches: tuple[str, str]
    advice: str
    avoid: str
    metrics: tuple[tuple[str, str], ...]
    luck_rows: tuple[tuple[str, str], ...]
    actions: tuple[str, str, str]
    slogan: str


@dataclass(frozen=True)
class DailyCardTheme:
    key: str
    label: str
    stripe_base: str
    stripe_band: str
    frame_start: str
    frame_end: str
    frame_stroke: str
    title: str
    panel_bg: str
    panel_stroke: str
    pill_bg: str
    pill_stroke: str
    pill_label_bg: str
    pill_label_text: str
    pill_value_text: str
    bar_fill: str
    bar_label_bg: str
    bar_label_text: str
    bar_text: str
    action_bg: str
    action_stroke: str
    action_text: str
    avatar_panel_bg: str
    avatar_panel_stroke: str
    avatar_accent: str
    footer: str


SIGN_TRAITS = {
    "白羊": ("行动快", "讨厌拖拉", "适合先把决定做小"),
    "金牛": ("看重稳定", "在意实际回报", "适合把账算清楚"),
    "双子": ("反应快", "信息很灵", "容易被新机会点亮"),
    "巨蟹": ("人际敏感", "看重安全感", "容易被旧习惯影响"),
    "狮子": ("要面子", "愿意扛事", "适合主动争取资源"),
    "处女": ("重视细节", "怕失控", "适合重新排优先级"),
    "天秤": ("看重关系平衡", "怕伤人和气", "需要减少无效照顾"),
    "天蝎": ("判断深", "不爱说破", "适合看清真实动机"),
    "射手": ("心气会动", "喜欢新方向", "适合筛掉旧圈子"),
    "摩羯": ("目标感强", "愿意长期投入", "适合守住边界"),
    "水瓶": ("想法跳得快", "不喜欢被催", "容易从变化里找到出口"),
    "双鱼": ("感受细腻", "共情很强", "需要把感受落到行动"),
}


VIRAL_TITLES = {
    "运势/提醒": (
        "{sign}座下半年躲不掉的三大转折！",
        "{sign}座本月必须警惕的一个信号！",
        "{sign}座，{month}有三个变化正在靠近",
        "{sign}座接下来整体运势开始走高！",
    ),
    "关系/性格": (
        "{sign}座这辈子最该珍惜的三种真心！",
        "能让{sign}座彻底清醒的两种关系！",
        "{sign}座下半年必须远离的两种消耗！",
        "真正旺{sign}座的三类人！",
    ),
    "财运/贵人": (
        "{sign}座，{month}有一个财运机会正在靠近！",
        "{sign}座下半年躲不掉的三大财务变化！",
        "{sign}座本月最容易忽略的一个贵人！",
        "{sign}座接下来事业上会出现的三个机会！",
    ),
}

BODY_VARIANTS = {
    "运势/提醒": (
        {
            "key": "three-areas",
            "hook": "工作、钱和关系会同时出现新的信号",
            "focus": "从三个具体变化判断接下来的节奏",
            "closing": "把三处变化逐一接稳",
        },
        {
            "key": "career-turn",
            "hook": "事业上的一次重新分工会带来后续变化",
            "focus": "看清任务、资源和选择权怎样变化",
            "closing": "先接住真正能积累的机会",
        },
        {
            "key": "momentum-rise",
            "hook": "前段时间卡住的事会陆续出现反馈",
            "focus": "从结果、进账和人际支持中确认运势回升",
            "closing": "把回升的节奏稳稳延续下去",
        },
    ),
    "关系/性格": (
        {
            "key": "steady-support",
            "hook": "真正值得珍惜的人会在三处细节里给你底气",
            "focus": "看行动、分寸和低谷时的支持",
            "closing": "把真心留给经得起时间的人",
        },
        {
            "key": "draining-patterns",
            "hook": "两种消耗型关系正在变得越来越明显",
            "focus": "远离只索取和反复否定你的相处模式",
            "closing": "把位置留给真正尊重你的人",
        },
        {
            "key": "mutual-growth",
            "hook": "真正旺你的人会带来三种正向变化",
            "focus": "靠近愿意分享信息、兑现承诺和鼓励成长的人",
            "closing": "让好的关系带着彼此向前",
        },
    ),
    "财运/贵人": (
        {
            "key": "income-window",
            "hook": "旧项目和新邀约里可能出现一笔增量",
            "focus": "留意结算、合作和可持续的小收入",
            "closing": "把能落地的财运机会接稳",
        },
        {
            "key": "resource-person",
            "hook": "一个低调的贵人会带来信息和资源",
            "focus": "识别愿意给方法、介绍机会和兑现支持的人",
            "closing": "珍惜真正帮你打开局面的人",
        },
        {
            "key": "money-reset",
            "hook": "三处财务变化会让现金流重新变清楚",
            "focus": "收回旧款、减少漏支出并筛选稳定机会",
            "closing": "让每一笔钱都回到清楚的位置",
        },
    ),
}

BODY_TITLE_TEMPLATES = {
    "three-areas": (
        "{sign}座，{month}有三个变化正在靠近！",
        "{sign}座接下来最明显的三个变化！",
        "{month}开始，{sign}座要接住这三次转折！",
        "{sign}座近期工作、钱和关系都会有变化",
    ),
    "career-turn": (
        "{sign}座本月必须警惕的一个事业信号！",
        "{sign}座事业上一个关键信号，别忽略！",
        "{month}，{sign}座要看清这次工作变化！",
        "{sign}座接下来要把事业主动权拿回来！",
    ),
    "momentum-rise": (
        "{sign}座接下来整体运势开始走高！",
        "{sign}座最近开始顺了，三个信号很明显！",
        "{month}起，{sign}座的整体运势慢慢走高！",
        "{sign}座前段时间卡住的事，开始有回音了！",
    ),
    "steady-support": (
        "{sign}座这辈子最该珍惜的三种真心！",
        "这三种真心，{sign}座遇到一定要珍惜！",
        "{sign}座真正需要的关系，都有这三个细节",
        "能让{sign}座安心做自己的人，别错过！",
    ),
    "draining-patterns": (
        "能让{sign}座彻底清醒的两种关系！",
        "{sign}座下半年要远离的两种关系！",
        "这两种人，最容易让{sign}座慢慢心累！",
        "{sign}座一旦看清这两个细节，就不会再勉强",
    ),
    "mutual-growth": (
        "真正旺{sign}座的三类人！",
        "{sign}座真正的贵人，往往是这三类人！",
        "能让{sign}座越过越顺的三种关系！",
        "{sign}座身边值得长期靠近的三类人",
    ),
    "income-window": (
        "{sign}座，{month}有一个财运机会正在靠近！",
        "{sign}座近期有三个进账线索，别错过！",
        "{month}，{sign}座要留意这几个财运机会！",
        "{sign}座的钱和机会，正在这三处出现变化",
    ),
    "resource-person": (
        "{sign}座本月最容易忽略的一个贵人！",
        "{sign}座真正的贵人，会给你这三种帮助！",
        "{month}，{sign}座要认出这个低调贵人！",
        "{sign}座接下来能打开局面的关键人物",
    ),
    "money-reset": (
        "{sign}座下半年躲不掉的三大财务变化！",
        "{sign}座下半年现金流会有三个新变化！",
        "{month}起，{sign}座这三笔钱要重新理清！",
        "{sign}座接下来最该看清的三个财务信号！",
    ),
}

OPENING_STYLES = (
    {"key": "direct-alert", "label": "直接提醒"},
    {"key": "detail-observation", "label": "细节观察"},
)
DAILY_FORTUNE_THEME = "每日运势"
DAILY_FORTUNE_SIGN = "十二星座"
DAILY_FORTUNE_GROUPS = (
    ("火象", ("白羊", "狮子", "射手")),
    ("土象", ("金牛", "处女", "摩羯")),
    ("风象", ("双子", "天秤", "水瓶")),
    ("水象", ("巨蟹", "天蝎", "双鱼")),
)
DAILY_FORTUNE_VARIANTS = (
    {
        "key": "steady-progress",
        "hook": "把节奏稳住，再推进最关键的一步",
        "focus": "先稳后动",
        "closing": "把能控制的事情往前推一点",
    },
    {
        "key": "clear-boundaries",
        "hook": "把回应和边界说清楚，少替别人补答案",
        "focus": "看清反馈",
        "closing": "把精力留给稳定的关系和安排",
    },
    {
        "key": "practical-gains",
        "hook": "把注意力放到真正能积累的机会和资源上",
        "focus": "做有效选择",
        "closing": "让小动作慢慢沉淀成收获",
    },
)
DAILY_FORTUNE_SIGNALS = (
    {
        "label": "推进",
        "lead": "手上的关键任务适合往前推一点",
        "fit": "先完成最卡的一步",
        "caution": "别让临时消息替你决定优先级",
    },
    {
        "label": "沟通",
        "lead": "关系里的真实反馈比猜测更重要",
        "fit": "把需要确认的话说清楚",
        "caution": "不必替沉默找太多理由",
    },
    {
        "label": "机会",
        "lead": "小机会更可能藏在日常邀约里",
        "fit": "多看一眼能积累资源的安排",
        "caution": "别为了热闹接下所有事情",
    },
    {
        "label": "财务",
        "lead": "钱和资源的边界值得提前确认",
        "fit": "把支出、分摊或回款理清",
        "caution": "不必为了面子把账算得含糊",
    },
    {
        "label": "减法",
        "lead": "今天更需要从忙乱里收回一点注意力",
        "fit": "删掉一件低回报的消耗",
        "caution": "别把忙碌误当成进展",
    },
    {
        "label": "收尾",
        "lead": "反复出现的旧问题需要一个明确收口",
        "fit": "把搁置的沟通或流程定下来",
        "caution": "少让拖延把情绪越拉越长",
    },
    {
        "label": "表达",
        "lead": "适合把真实想法放到台面上",
        "fit": "用简洁的话说出自己的需求",
        "caution": "不需要急着证明每一个判断",
    },
    {
        "label": "关系",
        "lead": "人际距离需要跟着真实感受微调",
        "fit": "把回应稳定的人放在前面",
        "caution": "别把照顾所有人的期待变成任务",
    },
)
DAILY_FORTUNE_ACTIONS = (
    "先写下今天最重要的一件事",
    "发出那句需要确认的话",
    "收回一项不必要的支出",
    "结束一段重复沟通",
    "给自己留二十分钟安静整理",
    "把一个小邀约认真听完",
    "把未完成的事标出截止点",
    "把注意力从比较里收回来",
)
DAILY_CARD_ASSET_DIR = Path(__file__).parent / "assets" / "daily_fortune_cards"
DAILY_CARD_CHARACTER_DIR = Path(__file__).parent / "assets" / "zodiac_characters"
DAILY_CARD_WIDTH = 960
DAILY_CARD_HEIGHT = 1280
DAILY_FORTUNE_COVER_ASSET_DIR = BASE_DIR / "assets" / "daily_fortune_covers"
DAILY_FORTUNE_COVER_WIDTH = 900
DAILY_FORTUNE_COVER_HEIGHT = 380
DAILY_FORTUNE_COVER_EXPORT_SCALE = 2
DAILY_FORTUNE_FOLLOW_ASSET_DIR = BASE_DIR / "assets" / "daily_fortune_follow"
DAILY_FORTUNE_FOLLOW_WIDTH = 900
DAILY_FORTUNE_FOLLOW_HEIGHT = 360
DAILY_FORTUNE_FOLLOW_EXPORT_SCALE = 2
DAILY_FORTUNE_FOLLOW_LINES = (
    "运势早知晓，好运常相伴。",
    "点击关注，每日为您解锁专属好运～",
)
DAILY_CARD_SIGN_ORDER = tuple(
    sign
    for _, group_signs in DAILY_FORTUNE_GROUPS
    for sign in group_signs
)
DAILY_CARD_ZODIAC = {
    "白羊": "♈︎",
    "金牛": "♉︎",
    "双子": "♊︎",
    "巨蟹": "♋︎",
    "狮子": "♌︎",
    "处女": "♍︎",
    "天秤": "♎︎",
    "天蝎": "♏︎",
    "射手": "♐︎",
    "摩羯": "♑︎",
    "水瓶": "♒︎",
    "双鱼": "♓︎",
}
DAILY_CARD_AVATAR_FILL = {
    "白羊": "#e67874",
    "金牛": "#d8a94a",
    "双子": "#bf7fc5",
    "巨蟹": "#7aa6cf",
    "狮子": "#d38a45",
    "处女": "#d990b6",
    "天秤": "#75a9bd",
    "天蝎": "#8c6aa8",
    "射手": "#6ba37b",
    "摩羯": "#8f7b68",
    "水瓶": "#5f9fc7",
    "双鱼": "#8aa3d8",
}
DAILY_CARD_COMPATIBILITY = {
    "白羊": ("狮子", "射手", "双子", "水瓶"),
    "金牛": ("处女", "摩羯", "巨蟹", "双鱼"),
    "双子": ("天秤", "水瓶", "白羊", "狮子"),
    "巨蟹": ("天蝎", "双鱼", "金牛", "处女"),
    "狮子": ("白羊", "射手", "双子", "天秤"),
    "处女": ("金牛", "摩羯", "巨蟹", "天蝎"),
    "天秤": ("双子", "水瓶", "狮子", "射手"),
    "天蝎": ("巨蟹", "双鱼", "处女", "摩羯"),
    "射手": ("白羊", "狮子", "天秤", "水瓶"),
    "摩羯": ("金牛", "处女", "天蝎", "双鱼"),
    "水瓶": ("双子", "天秤", "白羊", "射手"),
    "双鱼": ("巨蟹", "天蝎", "金牛", "摩羯"),
}
DAILY_CARD_SUMMARIES = (
    "行动感回升日",
    "稳住节奏日",
    "寻找平衡日",
    "整理能量日",
    "贵人靠近日",
    "关系转明日",
    "小财进账日",
    "灵感闪现日",
)
DAILY_CARD_ADVICE = (
    "先做最关键的小事",
    "把话说清楚一点",
    "给自己留出余地",
    "先确认再答应",
    "慢一点更容易赢",
    "把边界放在前面",
    "选择能沉淀的机会",
    "别被情绪带节奏",
)
DAILY_CARD_AVOID = (
    "临时冲动消费",
    "过度解释自己",
    "把所有事都揽下",
    "在旧问题里打转",
    "为了面子硬撑",
    "替别人补答案",
    "太快做最终决定",
    "熬夜刷消息",
)
DAILY_CARD_METRICS = {
    "财富": ("小额进账", "理性消费", "支出收紧", "人脉破财", "账目转清", "优惠谨慎"),
    "事业": ("效率回升", "合作推进", "家庭分心", "流程卡顿", "贵人助力", "适合收尾"),
    "感情": ("轻松互动", "暗流流动", "回应变暖", "减少试探", "旧事松动", "边界清晰"),
    "健康": ("睡眠问题", "注意颈肩", "补水放松", "少点外卖", "早点休息", "慢走舒展"),
}
DAILY_CARD_LUCK = {
    "复合运": (
        "现实问题未解，联系只会有烦恼。",
        "先别急着追问，对方会慢慢给反馈。",
        "旧情绪还在，适合把话说短一点。",
        "别翻旧账，先看今天有没有行动。",
    ),
    "脱单运": (
        "朋友圈里看似热闹，但多是过眼云烟。",
        "轻松聊天更加分，别急着证明魅力。",
        "熟人介绍可听听，先观察稳定度。",
        "主动一点会有回应，但别过度迎合。",
    ),
    "求职运": (
        "需要多权衡利弊，别被条件带跑。",
        "适合改简历和投递最匹配岗位。",
        "面试前确认细节，会少掉很多慌乱。",
        "机会不止一个，先选能长期积累的。",
    ),
}
DAILY_CARD_ACTION_POOL = (
    "关掉手机，静心片刻。",
    "买一束喜欢的鲜花。",
    "推掉无意义的聚会吧。",
    "写下今天最重要的一件事。",
    "把一笔支出记清楚。",
    "给重要的人回一句准话。",
    "收拾桌面十分钟。",
    "提前半小时休息。",
)
DAILY_CARD_SLOGANS = (
    "拒绝绑架，顺从自己的内心吧~",
    "先稳住自己，好运才有地方落脚~",
    "把边界说清楚，关系会更轻松~",
    "今天少一点内耗，多一点确定感~",
    "别急着证明，慢慢来也是答案~",
    "把能掌控的小事先做好~",
)
DEFAULT_DAILY_CARD_THEME = "mint"
PNG_RENDERERS = ("auto", "resvg", "rsvg-convert", "cairosvg", "chrome")
DAILY_CARD_THEMES = {
    "pink": DailyCardTheme(
        key="pink",
        label="桃粉",
        stripe_base="#fff8fb",
        stripe_band="#fff0f4",
        frame_start="#f5b2c1",
        frame_end="#e58da3",
        frame_stroke="#f7d5dd",
        title="#d4667f",
        panel_bg="#fff5f8",
        panel_stroke="#e7a3b3",
        pill_bg="#fff8fb",
        pill_stroke="#cb6079",
        pill_label_bg="#cf5f7a",
        pill_label_text="#ffffff",
        pill_value_text="#bd5970",
        bar_fill="#cf5f7a",
        bar_label_bg="#fff8fb",
        bar_label_text="#bd5970",
        bar_text="#ffffff",
        action_bg="#fff8fb",
        action_stroke="#cf5f7a",
        action_text="#bd5970",
        avatar_panel_bg="#fff5f8",
        avatar_panel_stroke="#e7a3b3",
        avatar_accent="#cf5f7a",
        footer="#ffffff",
    ),
    "mint": DailyCardTheme(
        key="mint",
        label="薄荷绿",
        stripe_base="#f8fdf9",
        stripe_band="#edf8f1",
        frame_start="#bfe8cf",
        frame_end="#86d3a4",
        frame_stroke="#d5efdc",
        title="#4f9f72",
        panel_bg="#f6fcf8",
        panel_stroke="#97d7aa",
        pill_bg="#fbfffc",
        pill_stroke="#70bd89",
        pill_label_bg="#66b985",
        pill_label_text="#ffffff",
        pill_value_text="#3f8962",
        bar_fill="#66b985",
        bar_label_bg="#fbfffc",
        bar_label_text="#3f8962",
        bar_text="#ffffff",
        action_bg="#fbfffc",
        action_stroke="#66b985",
        action_text="#3f8962",
        avatar_panel_bg="#f6fcf8",
        avatar_panel_stroke="#97d7aa",
        avatar_accent="#d36a82",
        footer="#ffffff",
    ),
}

ZODIAC_CHARACTER_BASE_PROMPT = (
    "Use case: stylized-concept. Asset type: zodiac daily-fortune card character. "
    "Create one original full-body Chinese anime chibi character, polished 2D illustration, "
    "clean linework, expressive bright eyes, natural hands, clear silhouette, centered pose, "
    "soft mint-green and white studio backdrop, gentle daylight, premium editorial finish, "
    "portrait 2:3 composition with generous padding around the complete character"
)
ZODIAC_CHARACTER_NEGATIVE_PROMPT = (
    "text, letters, Chinese characters, caption, watermark, logo, zodiac glyph, horoscope wheel, "
    "tarot card, photorealistic, 3d render, multiple people, duplicate character, cropped head, "
    "cropped feet, extra arms, extra legs, extra fingers, malformed hands, distorted face, blurry, "
    "low quality, dark background, neon background, cluttered scene, weapon, violence, suggestive pose"
)
ZODIAC_CHARACTER_VISUALS = {
    "白羊": "energetic young adventurer with short coral hair and subtle ram-horn hair ornaments, confident warm smile",
    "金牛": "calm elegant gardener with chestnut hair, small golden horn-shaped hair clips and a green cream outfit",
    "双子": "lively clever character with two-tone lavender hair ribbons and a playful layered outfit suggesting duality",
    "巨蟹": "gentle caretaker with moon-silver hair, shell-shaped accessories and a pale aqua capelet",
    "狮子": "radiant confident character with fluffy golden hair like a soft mane and a warm amber outfit",
    "处女": "refined book-loving character with neat rose-brown hair, tiny flower pin and clean ivory outfit",
    "天秤": "graceful diplomatic character with balanced symmetrical accessories, pearl-white hair and mint-gold outfit",
    "天蝎": "mysterious sweet character with dark plum hair, subtle curved tail motif and deep violet accents",
    "射手": "cheerful explorer with high ponytail, small star compass accessory and practical teal travel outfit",
    "摩羯": "steady composed character with charcoal hair, subtle curved horn hair ornaments and tailored earth-tone outfit",
    "水瓶": "inventive airy character with silver-blue bob hair, translucent water-ribbon accessory and modern aqua outfit",
    "双鱼": "dreamy gentle character with long sea-blue hair, twin fish-shaped hair clips and flowing mint-lilac outfit",
}


def daily_card_theme(theme: str) -> DailyCardTheme:
    try:
        return DAILY_CARD_THEMES[theme]
    except KeyError as exc:
        supported = ", ".join(sorted(DAILY_CARD_THEMES))
        raise ValueError(f"不支持的信息卡主题：{theme}，可选：{supported}") from exc


def slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", text).strip("-")
    return slug[:48] or "anxia-draft"


def pet_cover_prompt(draft: Draft) -> str:
    pet_scene = PET_COVER_PETS.get(draft.item.sign, "an adorable fluffy kitten in soft natural light")
    return (
        f"{PET_COVER_BASE_PROMPT}. Main pet: {pet_scene}. "
        f"Article mood: {draft.item.sign} {draft.item.theme}, {draft.item.angle}. "
        "The image should feel comforting, cute, clean, and suitable as a WeChat cover."
    )


def stable_seed(text: str) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % 1_000_000_000


def zodiac_character_prompt(sign: str) -> str:
    return (
        f"{ZODIAC_CHARACTER_BASE_PROMPT}. Sign concept: {sign}; "
        f"{ZODIAC_CHARACTER_VISUALS[sign]}. "
        "The character must remain the only subject and must contain no written text or symbol."
    )


def resize_zodiac_character(image_path: Path, size: tuple[int, int] = (640, 960)) -> None:
    if Image is None or ImageOps is None:
        raise RuntimeError("缺少 Pillow，无法裁切十二星座动漫人物")
    with Image.open(image_path) as source:
        image = ImageOps.fit(
            source.convert("RGB"),
            size,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        image.save(image_path, format="PNG", optimize=True)


def refresh_zodiac_characters_with_comfyui(
    *,
    asset_dir: Path,
    endpoint: str,
    model_profile: str,
    max_wait: int,
    poll_seconds: float,
) -> dict[str, Path]:
    profiles = comfy_images.load_profiles()
    client = comfy_images.ComfyClient(endpoint, timeout=30)
    client.preflight()
    asset_dir.parent.mkdir(parents=True, exist_ok=True)
    batch_id = datetime.now().strftime("%Y%m%d%H%M%S")
    generated: dict[str, Path] = {}

    with tempfile.TemporaryDirectory(prefix="zodiac-characters-", dir=asset_dir.parent) as tmpdir:
        staging_dir = Path(tmpdir)
        for sign in DAILY_CARD_SIGN_ORDER:
            prompt = zodiac_character_prompt(sign)
            previous_negative = comfy_images.NEGATIVE_PROMPT
            comfy_images.NEGATIVE_PROMPT = ZODIAC_CHARACTER_NEGATIVE_PROMPT
            try:
                workflow = comfy_images.render_workflow(
                    profiles,
                    model_profile,
                    prompt=prompt,
                    seed=stable_seed(f"zodiac-character:{sign}:{batch_id}"),
                    filename_prefix=f"astrology_content/zodiac_characters/{batch_id}/{sign}",
                )
            finally:
                comfy_images.NEGATIVE_PROMPT = previous_negative

            print(f"生成十二星座动漫人物 {len(generated) + 1}/12：{sign}座")
            prompt_id = client.queue(workflow)
            images = client.wait_for_images(
                prompt_id,
                max_wait_seconds=max_wait,
                poll_seconds=poll_seconds,
            )
            staged_path = staging_dir / f"{sign}座.png"
            client.download_image(images[-1], staged_path)
            resize_zodiac_character(staged_path)
            generated[sign] = staged_path

        asset_dir.mkdir(parents=True, exist_ok=True)
        final_paths: dict[str, Path] = {}
        for sign, staged_path in generated.items():
            final_path = asset_dir / f"{sign}座.png"
            os.replace(staged_path, final_path)
            final_paths[sign] = final_path

    print(f"已刷新十二星座动漫人物：{asset_dir}（批次 {batch_id}）")
    return final_paths


def require_pillow_for_pet_cover() -> None:
    if Image is None:
        raise RuntimeError("缺少 Pillow，无法裁切萌宠封面。请运行 python -m pip install Pillow")


def resize_center_crop(image_path: Path, size: tuple[int, int]) -> None:
    require_pillow_for_pet_cover()
    assert Image is not None
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        target_w, target_h = size
        src_w, src_h = image.size
        scale = max(target_w / src_w, target_h / src_h)
        resized = image.resize((round(src_w * scale), round(src_h * scale)), Image.Resampling.LANCZOS)
        left = (resized.width - target_w) // 2
        top = (resized.height - target_h) // 2
        cropped = resized.crop((left, top, left + target_w, top + target_h))
        cropped.save(image_path, format="JPEG", quality=94, optimize=True, progressive=True)


def pet_cover_path(asset_dir: Path, draft: Draft) -> Path:
    return asset_dir / draft.item.day.strftime("%Y%m%d") / f"{draft.item.slot:02d}_{slugify(draft.title)}.jpg"


def markdown_ref(image_path: Path, *, article_dir: Path) -> str:
    return Path(os.path.relpath(image_path, article_dir)).as_posix()


def pet_cover_markdown_ref(image_path: Path, *, article_dir: Path) -> str:
    return markdown_ref(image_path, article_dir=article_dir)


def write_pet_cover_with_comfyui(
    draft: Draft,
    *,
    asset_dir: Path,
    endpoint: str,
    model_profile: str,
    max_wait: int,
    poll_seconds: float,
) -> Path:
    output_path = pet_cover_path(asset_dir, draft)
    if output_path.is_file() and output_path.stat().st_size > 0:
        return output_path

    profiles = comfy_images.load_profiles()
    prompt = pet_cover_prompt(draft)
    client = comfy_images.ComfyClient(endpoint, timeout=30)
    client.preflight()
    previous_negative = comfy_images.NEGATIVE_PROMPT
    comfy_images.NEGATIVE_PROMPT = PET_COVER_NEGATIVE_PROMPT
    try:
        workflow = comfy_images.render_workflow(
            profiles,
            model_profile,
            prompt=prompt,
            seed=stable_seed(f"{draft.item.day}:{draft.item.slot}:{draft.title}:{prompt}"),
            filename_prefix=f"astrology_content/pet_covers/{draft.item.day:%Y%m%d}/{slugify(draft.title)}",
        )
    finally:
        comfy_images.NEGATIVE_PROMPT = previous_negative

    print(f"生成治愈系萌宠封面：{output_path.name}")
    print("正向 Prompt：")
    print(prompt)
    print("反向 Prompt：")
    print(PET_COVER_NEGATIVE_PROMPT)
    prompt_id = client.queue(workflow)
    images = client.wait_for_images(
        prompt_id,
        max_wait_seconds=max_wait,
        poll_seconds=poll_seconds,
    )
    client.download_image(images[-1], output_path)
    resize_center_crop(output_path, PET_COVER_SIZE)
    return output_path


def title_for_item(item: CalendarItem, mode: str) -> str:
    if mode in {"balanced", "hot-source"}:
        return item.title
    titles = VIRAL_TITLES[item.theme]
    index = (item.day.toordinal() + item.slot) % len(titles)
    month = f"{item.day.month}月"
    return titles[index].format(sign=item.sign, month=month)


def title_candidates_for_item(
    item: CalendarItem,
    selected_title: str,
    *,
    body_variant_key: str,
) -> tuple[str, ...]:
    month = f"{item.day.month}月"
    templates = BODY_TITLE_TEMPLATES[body_variant_key]
    options = [
        selected_title,
        *(template.format(sign=item.sign, month=month) for template in templates),
    ]
    candidates: list[str] = []
    seen: set[str] = set()
    for option in options:
        title = option.strip()
        key = re.sub(r"[\s，。！？、：；,.!?:;]+", "", title)
        if title and key not in seen:
            candidates.append(title)
            seen.add(key)
    return tuple(candidates[:4])


def title_formula(title: str, theme: str) -> str:
    if theme == DAILY_FORTUNE_THEME:
        return "全星座日运型"
    if theme == "关系/性格":
        if any(term in title for term in ("远离", "消耗", "清醒", "心累", "勉强")):
            return "关系避坑型"
        if any(term in title for term in ("旺", "贵人", "越过越顺", "长期靠近")):
            return "关系助力型"
        return "真心识别型"
    if theme == "财运/贵人":
        if "贵人" in title or "关键人物" in title:
            return "贵人资源型"
        if any(term in title for term in ("财务", "现金流", "三笔钱")):
            return "财务变化型"
        return "财运机会型"
    if any(term in title for term in ("警惕", "提醒", "忽略", "事业信号")):
        return "事业警示型"
    if any(term in title for term in ("运势", "走高", "开始顺", "有回音")):
        return "运势走高型"
    return "多点变化型"


def title_pattern(title: str) -> str:
    if any(term in title for term in ("必须", "警惕", "远离", "别", "忽略")):
        return "风险提醒型"
    if any(term in title for term in ("一个", "这个", "关键人物")):
        return "单点悬念型"
    if any(
        term in title
        for term in ("三大", "三个", "三种", "三类", "三笔", "三次", "两种", "两个", "几个")
    ):
        return "数字清单型"
    if any(term in title for term in ("靠近", "开始", "走高", "变化", "回音", "越过越顺")):
        return "趋势预告型"
    return "场景判断型"


def title_variants_for_item(
    item: CalendarItem,
    selected_title: str,
    *,
    body_variant_key: str,
) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "key": f"title-{index}",
            "text": title,
            "formula": title_formula(title, item.theme),
            "pattern": title_pattern(title),
        }
        for index, title in enumerate(
            title_candidates_for_item(
                item,
                selected_title,
                body_variant_key=body_variant_key,
            ),
            start=1,
        )
    )


def daily_fortune_title_variants(day: date) -> tuple[dict[str, str], ...]:
    formatted_day = day.strftime("%Y.%m.%d")
    return (
        {
            "key": "title-1",
            "text": f"十二星座每日好运丨{formatted_day}",
            "formula": "全星座日运型",
            "pattern": "日期日运型",
        },
        {
            "key": "title-2",
            "text": f"十二星座今日好运指南丨{formatted_day}",
            "formula": "全星座日运型",
            "pattern": "日期日运型",
        },
        {
            "key": "title-3",
            "text": f"{formatted_day} 十二星座日运提醒",
            "formula": "全星座日运型",
            "pattern": "日期日运型",
        },
    )


def hot_source_title_for_item(item: CalendarItem, corpus_dir: Path | None, *, min_count: int) -> str | None:
    if corpus_dir is None:
        return None
    try:
        articles = load_corpus(corpus_dir)
    except FileNotFoundError:
        return None
    hot_normalized = hot_titles_by_reuse(articles, min_count=min_count)
    candidates = [article.title for article in articles if normalized_title(article.title) in hot_normalized]
    theme_terms = {
        "运势/提醒": ("运势", "提醒", "注意", "躲不掉", "警惕", "下半年", "本月", "一定会", "喜事"),
        "关系/性格": ("珍惜", "清醒", "离开", "回头", "真心", "关系", "性格"),
        "财运/贵人": ("财运", "贵人", "发财", "好运", "机会", "收获", "收入"),
    }[item.theme]

    same_sign = [title for title in candidates if item.sign in title and any(term in title for term in theme_terms)]
    pool = same_sign or [
        title
        for title in candidates
        if not any(sign in title for sign in SIGN_TERMS) and any(term in title for term in theme_terms)
    ]
    if not pool:
        return None
    return pool[(item.day.toordinal() + item.slot) % len(pool)]


def _preferred_variant_index(item: CalendarItem, title: str | None) -> int:
    if not title:
        sign_index = SIGN_TERMS.index(item.sign) if item.sign in SIGN_TERMS else 0
        return (item.day.toordinal() + sign_index) % len(BODY_VARIANTS[item.theme])
    if item.theme == "运势/提醒":
        if any(term in title for term in ("三大", "三个", "三次")):
            return 0
        if any(term in title for term in ("事业", "警惕", "提醒")):
            return 1
        return 2
    if item.theme == "关系/性格":
        if any(term in title for term in ("两种", "远离", "消耗")):
            return 1
        if any(term in title for term in ("旺", "三类")):
            return 2
        return 0
    if "贵人" in title:
        return 1
    if any(term in title for term in ("财务", "三大变化")):
        return 2
    return 0


def _variant_for_item(
    item: CalendarItem,
    *,
    title: str | None = None,
    offset: int = 0,
) -> dict[str, str]:
    variants = BODY_VARIANTS[item.theme]
    return variants[(_preferred_variant_index(item, title) + offset) % len(variants)]


def _title_for_body_variant(item: CalendarItem, variant_key: str) -> str:
    month = f"{item.day.month}月"
    titles = {
        "three-areas": f"{item.sign}座，{month}有三个变化正在靠近！",
        "career-turn": f"{item.sign}座本月必须警惕的一个事业信号！",
        "momentum-rise": f"{item.sign}座接下来整体运势开始走高！",
        "steady-support": f"{item.sign}座这辈子最该珍惜的三种真心！",
        "draining-patterns": f"能让{item.sign}座彻底清醒的两种关系！",
        "mutual-growth": f"真正旺{item.sign}座的三类人！",
        "income-window": f"{item.sign}座，{month}有一个财运机会正在靠近！",
        "resource-person": f"{item.sign}座本月最容易忽略的一个贵人！",
        "money-reset": f"{item.sign}座下半年躲不掉的三大财务变化！",
    }
    return titles[variant_key]


def _opening_for_item(
    item: CalendarItem,
    body_variant: dict[str, str],
    *,
    offset: int = 0,
) -> dict[str, str]:
    style = OPENING_STYLES[(item.day.toordinal() + item.slot + offset) % len(OPENING_STYLES)]
    hook = body_variant["hook"].rstrip("。！？!")
    sign_label = f"{item.sign}座"
    if style["key"] == "detail-observation":
        suffix = {
            "运势/提醒": "这些变化会落到具体生活里",
            "关系/性格": "看行动会比猜态度更准",
            "财运/贵人": "真正的机会会留下实际线索",
        }[item.theme]
        text = f"{sign_label}这段时间会慢慢看清：{hook}，{suffix}。"
    else:
        prefix = {
            "运势/提醒": "接下来要留意",
            "关系/性格": "在关系里要看清",
            "财运/贵人": "最近在钱和机会上的重点是",
        }[item.theme]
        text = f"{sign_label}{prefix}：{hook}。"
    return {**style, "text": text}


def opening_candidates_for_item(
    item: CalendarItem,
    body_variant: dict[str, str],
    *,
    selected_key: str,
) -> tuple[dict[str, str], ...]:
    variants = [
        _opening_for_item(item, body_variant, offset=offset)
        for offset in range(len(OPENING_STYLES))
    ]
    variants.sort(key=lambda variant: variant["key"] != selected_key)
    return tuple(variants)


def render_body_with_variant(
    item: CalendarItem,
    *,
    mode: str = "viral-safe",
    selected_title: str | None = None,
    variant_offset: int = 0,
    opening_offset: int = 0,
) -> tuple[str, dict[str, str], dict[str, str]]:
    trait_a, trait_b, trait_c = SIGN_TRAITS.get(item.sign, ("状态敏感", "需要稳住节奏", "适合看清重点"))
    sign = item.sign
    sign_label = f"{sign}座"
    variant = _variant_for_item(item, title=selected_title, offset=variant_offset)
    opening = _opening_for_item(item, variant, offset=opening_offset)
    if item.theme == "运势/提醒":
        if variant["key"] == "career-turn":
            paragraphs = [
                f"{sign_label}接下来要注意，事业上的一次重新分工会带来后续变化。",
                f"一是手里的任务会重新排顺序，过去总被打断的事，终于有机会完整推进。{trait_a}是优势，但别把所有临时活都接走。",
                "二是资源会跟着任务一起出现。愿意把信息、方法和关键联系人告诉你的人，比只会催进度的人更值得靠近。",
                "三是选择权会变多。先看哪件事能留下成果，再决定把时间压在哪里。",
                f"刷到接好运！祝{sign_label}接住真正能积累的事业机会，把主动权拿回来。",
            ]
        elif variant["key"] == "momentum-rise":
            paragraphs = [
                f"{sign_label}前段时间卡住的事，接下来会陆续出现反馈，整体节奏有机会往上走。",
                f"工作上，搁置的安排会重新启动。你们{trait_a}，收到明确回复后要尽快落下一步，别让机会再次停在讨论里。",
                "钱的安排也会更清楚，可能是旧款有了进度，或一项合作终于谈到实际回报。先确认细节，不急着把期待算成收入。",
                "关系里会有人给出更稳定的支持。能兑现承诺、愿意一起解决问题的人，会让你少走弯路。",
                f"刷到接好运！祝{sign_label}稳稳延续这段回升节奏，把好状态变成真进展。",
            ]
        else:
            paragraphs = [
                f"{sign_label}接下来会在三个地方看到变化：工作、钱的安排和身边关系。",
                f"工作上，拖了很久的任务开始出现明确节点。你们{trait_a}，这次要把决定落到行动，不再只等别人通知。",
                "钱的节奏上，一笔旧支出或待确认的回款会重新进入视线。先核清数字，能省的省，能收的及时跟进。",
                "关系里，热闹的人会变少，真正愿意提供信息和支持的人会更清楚。把时间留给能一起往前走的人。",
                f"刷到接好运！祝{sign_label}把三处变化逐一接稳，下半年的路越走越清楚。",
            ]
    elif item.theme == "关系/性格":
        if variant["key"] == "draining-patterns":
            paragraphs = [
                f"{sign_label}下半年要看清两种消耗型关系，越早拉开距离，心里越轻松。",
                "一种是只在需要帮忙时靠近，平时很少回应。你的时间和能力被当成现成资源，付出却得不到基本尊重。",
                "另一种是反复否定你的选择。你一有新计划，对方先泼冷水；你做出成绩，他又把它说成运气。",
                f"你们{trait_b}，容易为旧情分多留一步。但真正适合留下的人，会尊重你的边界，也愿意看见你的成长。",
                f"刷到接好运！祝{sign_label}远离两种消耗，把位置留给真正尊重你的人。",
            ]
        elif variant["key"] == "mutual-growth":
            paragraphs = [
                f"真正旺{sign_label}的人，通常会带来三种正向变化，不只是在嘴上夸你。",
                "第一类愿意分享信息，让你少走弯路；第二类说到做到，关键时刻能给稳定支持；第三类鼓励你成长，不怕你变得更好。",
                f"你们{trait_b}，对关系里的细微变化很敏感。别只看一时热情，要看对方能不能长期兑现。",
                "好的关系不会替你做决定，却会让你更有底气做自己的决定。",
                f"刷到接好运！祝{sign_label}靠近真正旺你的人，彼此带着对方向前走。",
            ]
        else:
            paragraphs = [
                f"{sign_label}这辈子最该珍惜的真心，往往藏在三处不显眼的细节里。",
                "一是你低落时不催你表态，愿意给你时间；二是发生分歧也守住分寸，不拿你的脆弱伤你；三是答应的事会尽力做到。",
                f"你们{trait_b}，很会分辨热闹和真心。真正值得留下的人，不一定天天出现，却会在关键时候站稳。",
                "关系不必多，能让你安心做自己，比一时的热烈更难得。",
                f"刷到接好运！祝{sign_label}珍惜三种真心，让信任在时间里慢慢长稳。",
            ]
    else:
        if variant["key"] == "resource-person":
            paragraphs = [
                f"{sign_label}本月容易忽略的贵人，不一定高调，但会给你实际的信息和资源。",
                "他可能提醒你一个时间节点，介绍一个靠谱的合作，或把自己走过的弯路直接告诉你。这些帮助不热闹，却能打开局面。",
                f"你们{trait_c}，判断时别只看对方说得多好，要看信息能不能核实、承诺能不能兑现。",
                "收到帮助后及时反馈结果，也把自己的专业和信用拿出来，贵人关系才能走得长。",
                f"刷到接好运！祝{sign_label}认出真正的贵人，把新机会稳稳落到行动上。",
            ]
        elif variant["key"] == "money-reset":
            paragraphs = [
                f"{sign_label}下半年会看到三处财务变化，重点不是突然暴富，而是现金流开始变得清楚。",
                "一是拖着的旧款或报销有机会出现进度，该补的材料及时补；二是自动续费和零碎支出更容易被发现，能关掉的尽快处理。",
                "三是新合作会谈到具体回报。先确认周期、投入和结算方式，再判断值不值得接。",
                f"你们{trait_c}，越早把数字写清楚，越不容易被表面的优惠和热闹带偏。",
                f"刷到接好运！祝{sign_label}接稳三处财务变化，让每一笔钱都回到清楚的位置。",
            ]
        else:
            paragraphs = [
                f"{sign_label}最近的钱和机会，会从旧项目结算、新合作邀约和一项可持续的小收入里出现线索。",
                "第一个线索是旧项目的待确认款项，该补的材料和该问的进度要及时跟上。",
                "第二个线索是熟人带来的新合作，有具体需求、周期和回报，才值得继续谈。",
                f"第三个线索是可持续的小收入。你们{trait_c}，但也要把成本算进去，只讲回报不讲风险的先多核实一步。",
                f"刷到接好运！祝{sign_label}把能落地的财运机会接稳，慢慢增加自己的底气。",
            ]
    paragraphs[0] = opening["text"]
    return "\n\n".join(paragraphs), variant, opening


def render_body(item: CalendarItem, *, mode: str = "viral-safe") -> str:
    selected_title = title_for_item(item, mode)
    body, _, _ = render_body_with_variant(
        item,
        mode=mode,
        selected_title=selected_title,
    )
    return body


def _daily_fortune_variant(day: date, *, offset: int = 0) -> dict[str, str]:
    return DAILY_FORTUNE_VARIANTS[(day.toordinal() + offset) % len(DAILY_FORTUNE_VARIANTS)]


def _daily_fortune_opening(
    day: date,
    body_variant: dict[str, str],
    *,
    offset: int = 0,
) -> dict[str, str]:
    style = (
        {"key": "daily-keyword", "label": "日运关键词"},
        {"key": "daily-compass", "label": "十二星座总览"},
    )[(day.toordinal() + offset) % 2]
    if style["key"] == "daily-compass":
        text = (
            f"{day.month}月{day.day}日，把今天拆成十二个小提醒。"
            f"先围绕“{body_variant['focus']}”安排节奏，比急着追答案更有用。"
        )
    else:
        text = (
            f"{day.month}月{day.day}日的十二星座日运关键词是“{body_variant['focus']}”。"
            "下面按四象星座整理今天更适合抓住的一件小事。"
        )
    return {**style, "text": text}


def daily_fortune_opening_candidates(
    day: date,
    body_variant: dict[str, str],
    *,
    selected_key: str,
) -> tuple[dict[str, str], ...]:
    candidates = [_daily_fortune_opening(day, body_variant, offset=index) for index in range(2)]
    candidates.sort(key=lambda candidate: candidate["key"] != selected_key)
    return tuple(candidates)


def _daily_sign_paragraph(
    sign: str,
    *,
    day: date,
    body_variant: dict[str, str],
) -> str:
    sign_index = SIGN_TERMS.index(sign)
    day_number = day.toordinal()
    signal = DAILY_FORTUNE_SIGNALS[(day_number * 3 + sign_index * 5) % len(DAILY_FORTUNE_SIGNALS)]
    action = DAILY_FORTUNE_ACTIONS[(day_number * 5 + sign_index * 3) % len(DAILY_FORTUNE_ACTIONS)]
    trait_a, trait_b, trait_c = SIGN_TRAITS[sign]
    pattern = (day_number + sign_index * 2 + len(body_variant["key"])) % 3
    if pattern == 0:
        return (
            f"**{sign}**：{signal['lead']}。你本来{trait_a}，今天{signal['fit']}会更顺。"
            f"{signal['caution']}。好运动作：{action}。"
        )
    if pattern == 1:
        return (
            f"**{sign}**：今天更适合{signal['fit']}。{trait_b}会让你对外界反馈格外敏感，"
            f"{signal['caution']}。好运动作：{action}。"
        )
    return (
        f"**{sign}**：{signal['label']}是今天的关键词。你们{trait_c}，先{_daily_first_step(signal['fit'])}，"
        f"再决定要不要加码。{signal['caution']}。好运动作：{action}。"
    )


def _daily_first_step(text: str) -> str:
    return text[1:] if text.startswith("先") else text


def _daily_card_pick(options: tuple[str, ...], day: date, sign: str, *, salt: int = 0) -> str:
    sign_index = SIGN_TERMS.index(sign)
    return options[(day.toordinal() + sign_index * 7 + salt) % len(options)]


def build_daily_fortune_card(sign: str, day: date) -> DailyFortuneCard:
    sign_index = SIGN_TERMS.index(sign)
    match_options = DAILY_CARD_COMPATIBILITY[sign]
    match_start = (day.toordinal() + sign_index) % len(match_options)
    matches = (
        match_options[match_start],
        match_options[(match_start + 1) % len(match_options)],
    )
    metrics = tuple(
        (
            label,
            _daily_card_pick(tuple(values), day, sign, salt=index * 3),
        )
        for index, (label, values) in enumerate(DAILY_CARD_METRICS.items())
    )
    luck_rows = tuple(
        (
            label,
            _daily_card_pick(tuple(values), day, sign, salt=index * 5),
        )
        for index, (label, values) in enumerate(DAILY_CARD_LUCK.items())
    )
    actions = tuple(
        DAILY_CARD_ACTION_POOL[
            (day.toordinal() + sign_index * 4 + action_index * 2) % len(DAILY_CARD_ACTION_POOL)
        ]
        for action_index in range(3)
    )
    return DailyFortuneCard(
        sign=sign,
        summary=_daily_card_pick(DAILY_CARD_SUMMARIES, day, sign),
        score=66 + ((day.toordinal() + sign_index * 5) % 23),
        matches=matches,
        advice=_daily_card_pick(DAILY_CARD_ADVICE, day, sign, salt=2),
        avoid=_daily_card_pick(DAILY_CARD_AVOID, day, sign, salt=4),
        metrics=metrics,
        luck_rows=luck_rows,
        actions=actions,
        slogan=_daily_card_pick(DAILY_CARD_SLOGANS, day, sign, salt=6),
    )


def _wrap_text(text: str, width: int) -> list[str]:
    if len(text) <= width:
        return [text]
    return [text[index : index + width] for index in range(0, len(text), width)]


def _svg_text_lines(
    text: str,
    *,
    x: int,
    y: int,
    width: int,
    size: int,
    fill: str = "#bf5870",
    weight: int = 700,
    line_gap: int | None = None,
    anchor: str = "start",
) -> str:
    gap = line_gap or int(size * 1.28)
    lines = _wrap_text(text, width)
    return "\n".join(
        (
            f'<text x="{x}" y="{y + index * gap}" text-anchor="{anchor}" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}">'
            f"{escape(line)}</text>"
        )
        for index, line in enumerate(lines)
    )


def _daily_metric_pill_svg(index: int, label: str, value: str, theme: DailyCardTheme) -> str:
    column = index % 2
    row = index // 2
    x = 94 + column * 392
    y = 548 + row * 76
    return "\n".join(
        (
            f'<rect x="{x}" y="{y}" width="342" height="56" rx="22" fill="{theme.pill_bg}" '
            f'stroke="{theme.pill_stroke}" stroke-width="3"/>',
            f'<rect x="{x}" y="{y}" width="110" height="56" rx="22" fill="{theme.pill_label_bg}"/>',
            f'<text x="{x + 55}" y="{y + 38}" text-anchor="middle" font-size="33" '
            f'font-weight="800" fill="{theme.pill_label_text}">{escape(label)}</text>',
            f'<text x="{x + 226}" y="{y + 38}" text-anchor="middle" font-size="31" '
            f'font-weight="700" fill="{theme.pill_value_text}">{escape(value)}</text>',
        )
    )


def _daily_luck_row_svg(index: int, label: str, value: str, theme: DailyCardTheme) -> str:
    y = 712 + index * 76
    return "\n".join(
        (
            f'<rect x="94" y="{y}" width="772" height="56" rx="22" fill="{theme.bar_fill}"/>',
            f'<rect x="94" y="{y}" width="148" height="56" rx="22" fill="{theme.bar_label_bg}" '
            f'stroke="{theme.action_stroke}" stroke-width="3"/>',
            f'<text x="168" y="{y + 38}" text-anchor="middle" font-size="34" '
            f'font-weight="800" fill="{theme.bar_label_text}">{escape(label)}</text>',
            f'<text x="270" y="{y + 38}" font-size="30" font-weight="700" '
            f'fill="{theme.bar_text}">{escape(value)}</text>',
        )
    )


def _daily_action_line_svg(index: int, text: str, theme: DailyCardTheme) -> str:
    center_y = 974 + index * 48
    text_y = center_y + 10
    return "\n".join(
        (
            f'<circle cx="282" cy="{center_y}" r="14" fill="none" stroke="{theme.action_stroke}" stroke-width="4"/>',
            f'<path d="M274 {center_y - 2} L281 {center_y + 6} L295 {center_y - 11}" fill="none" '
            f'stroke="{theme.action_stroke}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>',
            f'<text x="316" y="{text_y}" font-size="31" font-weight="700" '
            f'fill="{theme.action_text}">{escape(text)}</text>',
        )
    )


def daily_card_character_path(
    sign: str,
    *,
    character_asset_dir: Path | None = None,
) -> Path | None:
    directory = character_asset_dir or DAILY_CARD_CHARACTER_DIR
    candidate = directory / f"{sign}座.png"
    return candidate if candidate.is_file() else None


def _daily_avatar_asset_svg(
    sign: str,
    *,
    character_asset_dir: Path | None = None,
) -> str | None:
    asset_path = daily_card_character_path(sign, character_asset_dir=character_asset_dir)
    if asset_path is None:
        return None
    encoded = b64encode(asset_path.read_bytes()).decode("ascii")
    return (
        f'<image x="114" y="220" width="230" height="270" '
        f'preserveAspectRatio="xMidYMid slice" clip-path="url(#avatarPanelClip)" '
        f'href="data:image/png;base64,{encoded}"/>'
    )


def _daily_avatar_svg(sign: str, fill: str, accent: str = "#cf5f7a") -> str:
    skin = "#fff0da"
    outline = "#e3bb7a"
    line = "#705368"
    glyph = escape(DAILY_CARD_ZODIAC[sign])
    if sign == "双子":
        return f"""
  <path d="M150 462 C166 412 214 390 229 426 C244 390 292 412 308 462 Z" fill="{fill}"/>
  <circle cx="194" cy="334" r="48" fill="{skin}" stroke="{outline}" stroke-width="3"/>
  <circle cx="264" cy="334" r="48" fill="{skin}" stroke="{outline}" stroke-width="3"/>
  <path d="M154 306 C174 276 214 276 234 306" fill="none" stroke="#e3c060" stroke-width="16" stroke-linecap="round"/>
  <path d="M224 306 C244 276 284 276 304 306" fill="none" stroke="#e3c060" stroke-width="16" stroke-linecap="round"/>
  <circle cx="181" cy="334" r="6" fill="{line}"/>
  <circle cx="207" cy="334" r="6" fill="{line}"/>
  <circle cx="251" cy="334" r="6" fill="{line}"/>
  <circle cx="277" cy="334" r="6" fill="{line}"/>
  <path d="M184 356 C192 364 201 364 209 356" fill="none" stroke="{line}" stroke-width="4" stroke-linecap="round"/>
  <path d="M254 356 C262 364 271 364 279 356" fill="none" stroke="{line}" stroke-width="4" stroke-linecap="round"/>
  <text x="229" y="452" text-anchor="middle" font-size="54" font-weight="900" fill="#ffffff">{glyph}</text>"""

    behind = ""
    front = ""
    if sign == "白羊":
        behind = f"""
  <path d="M156 300 C126 260 158 230 194 270" fill="none" stroke="#f4d47c" stroke-width="16" stroke-linecap="round"/>
  <path d="M302 300 C332 260 300 230 264 270" fill="none" stroke="#f4d47c" stroke-width="16" stroke-linecap="round"/>"""
    elif sign == "金牛":
        behind = f"""
  <path d="M156 292 C118 250 134 224 190 266" fill="none" stroke="#d9b65e" stroke-width="18" stroke-linecap="round"/>
  <path d="M302 292 C340 250 324 224 268 266" fill="none" stroke="#d9b65e" stroke-width="18" stroke-linecap="round"/>"""
    elif sign == "巨蟹":
        front = f"""
  <path d="M150 392 C122 370 122 334 154 324" fill="none" stroke="{accent}" stroke-width="12" stroke-linecap="round"/>
  <path d="M308 392 C336 370 336 334 304 324" fill="none" stroke="{accent}" stroke-width="12" stroke-linecap="round"/>
  <circle cx="142" cy="324" r="15" fill="#fff5f8" stroke="{accent}" stroke-width="6"/>
  <circle cx="316" cy="324" r="15" fill="#fff5f8" stroke="{accent}" stroke-width="6"/>"""
    elif sign == "狮子":
        behind = """
  <circle cx="229" cy="332" r="88" fill="#f1b957"/>
  <path d="M229 230 L248 274 L296 260 L270 302 L314 324 L266 336 L286 382 L244 356 L229 404 L214 356 L172 382 L192 336 L144 324 L188 302 L162 260 L210 274 Z" fill="#e89b45"/>"""
    elif sign == "处女":
        front = f"""
  <path d="M292 286 C318 274 326 298 308 314 C330 318 326 346 300 342 C294 364 270 352 280 332 C260 326 266 302 288 308 Z" fill="#ffd6e4" stroke="{accent}" stroke-width="4"/>
  <circle cx="296" cy="322" r="10" fill="#f0c45d"/>"""
    elif sign == "天秤":
        front = f"""
  <path d="M176 406 H282" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>
  <path d="M229 384 V434" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>
  <path d="M190 406 C180 428 166 428 156 406" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="round"/>
  <path d="M302 406 C292 428 278 428 268 406" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="round"/>"""
    elif sign == "天蝎":
        front = f"""
  <path d="M292 422 C336 414 342 372 312 362 C350 354 354 320 324 306" fill="none" stroke="{accent}" stroke-width="10" stroke-linecap="round"/>
  <path d="M324 306 L342 306 L332 322 Z" fill="{accent}"/>"""
    elif sign == "射手":
        front = """
  <path d="M166 434 L296 344" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>
  <path d="M274 344 H308 V378" fill="none" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>
  <path d="M178 398 C200 376 224 376 244 398" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="round"/>"""
    elif sign == "摩羯":
        behind = f"""
  <path d="M184 276 C170 240 206 238 214 274" fill="none" stroke="#d6c17b" stroke-width="14" stroke-linecap="round"/>
  <path d="M274 276 C288 240 252 238 244 274" fill="none" stroke="#d6c17b" stroke-width="14" stroke-linecap="round"/>"""
        front = """
  <path d="M286 452 C326 448 328 410 300 400 C326 392 326 368 304 358" fill="none" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>"""
    elif sign == "水瓶":
        front = f"""
  <path d="M284 292 L322 310 L296 364 L258 346 Z" fill="#a9d8ee" stroke="{accent}" stroke-width="4"/>
  <path d="M176 424 C196 410 216 438 236 424 C256 410 276 438 296 424" fill="none" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>
  <path d="M178 448 C198 434 218 462 238 448 C258 434 278 462 298 448" fill="none" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>"""
    elif sign == "双鱼":
        front = """
  <path d="M178 424 C198 400 230 400 250 424 C230 448 198 448 178 424Z" fill="#ffffff" opacity="0.95"/>
  <path d="M280 424 C260 400 228 400 208 424 C228 448 260 448 280 424Z" fill="#ffffff" opacity="0.95"/>
  <circle cx="202" cy="421" r="4" fill="#6d9ec9"/>
  <circle cx="256" cy="421" r="4" fill="#6d9ec9"/>"""

    return f"""
  {behind}
  <circle cx="229" cy="332" r="72" fill="{skin}" stroke="{outline}" stroke-width="3"/>
  <path d="M154 286 C190 236 268 236 304 286 C262 272 196 272 154 286Z" fill="#e3c060"/>
  <path d="M174 414 C190 376 268 376 286 414 L314 470 H144Z" fill="{fill}"/>
  <circle cx="205" cy="334" r="7" fill="{line}"/>
  <circle cx="253" cy="334" r="7" fill="{line}"/>
  <path d="M214 364 C224 374 238 374 248 364" fill="none" stroke="{line}" stroke-width="5" stroke-linecap="round"/>
  {front}
  <text x="229" y="462" text-anchor="middle" font-size="54" font-weight="900" fill="#ffffff">{glyph}</text>"""


def render_daily_fortune_card_svg(
    card: DailyFortuneCard,
    day: date,
    *,
    card_theme: str = DEFAULT_DAILY_CARD_THEME,
    character_asset_dir: Path | None = None,
) -> str:
    sign_title = f"{card.sign}座"
    match_text = "、".join(f"{sign}座" for sign in card.matches)
    theme = daily_card_theme(card_theme)
    avatar_fill = DAILY_CARD_AVATAR_FILL[card.sign]
    metric_svg = "\n".join(
        _daily_metric_pill_svg(index, label, value, theme)
        for index, (label, value) in enumerate(card.metrics)
    )
    luck_svg = "\n".join(
        _daily_luck_row_svg(index, label, value, theme)
        for index, (label, value) in enumerate(card.luck_rows)
    )
    action_svg = "\n".join(
        _daily_action_line_svg(index, text, theme)
        for index, text in enumerate(card.actions)
    )
    avatar_svg = _daily_avatar_asset_svg(
        card.sign,
        character_asset_dir=character_asset_dir,
    ) or _daily_avatar_svg(card.sign, avatar_fill, accent=theme.avatar_accent)
    info_lines = "\n".join(
        (
            _svg_text_lines(f"今日简述：{card.summary}", x=390, y=254, width=14, size=38, fill=theme.action_text),
            _svg_text_lines(f"今日分数：{card.score}", x=390, y=314, width=14, size=38, fill=theme.action_text),
            _svg_text_lines(f"合拍星座：{match_text}", x=390, y=374, width=14, size=38, fill=theme.action_text),
            _svg_text_lines(f"建议：{card.advice}", x=390, y=434, width=14, size=38, fill=theme.action_text),
            _svg_text_lines(f"避免：{card.avoid}", x=390, y=494, width=14, size=38, fill=theme.action_text),
        )
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{DAILY_CARD_WIDTH}" height="{DAILY_CARD_HEIGHT}" viewBox="0 0 {DAILY_CARD_WIDTH} {DAILY_CARD_HEIGHT}" role="img" aria-label="{escape(sign_title)}每日好运卡">
  <defs>
    <style>
      text {{
        font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif;
      }}
    </style>
    <pattern id="stripe" width="18" height="18" patternUnits="userSpaceOnUse" patternTransform="rotate(35)">
      <rect width="18" height="18" fill="{theme.stripe_base}"/>
      <rect width="8" height="18" fill="{theme.stripe_band}"/>
    </pattern>
    <linearGradient id="cardFrame" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{theme.frame_start}"/>
      <stop offset="1" stop-color="{theme.frame_end}"/>
    </linearGradient>
    <clipPath id="avatarPanelClip">
      <rect x="114" y="220" width="230" height="270" rx="24"/>
    </clipPath>
  </defs>
  <rect x="38" y="24" width="884" height="1232" rx="56" fill="url(#cardFrame)"/>
  <rect x="68" y="70" width="824" height="1124" rx="8" fill="url(#stripe)" stroke="{theme.frame_stroke}" stroke-width="4"/>
  <path d="M70 128 H890" stroke="#ffffff" stroke-width="8" opacity="0.9"/>
  <text x="480" y="156" text-anchor="middle" font-size="84" font-weight="900" fill="{theme.title}">{escape(sign_title)}</text>
  <text x="280" y="134" text-anchor="middle" font-size="42" fill="{theme.title}">✧</text>
  <text x="690" y="150" text-anchor="middle" font-size="42" fill="{theme.title}">✦</text>
  <rect x="110" y="216" width="238" height="278" rx="28" fill="{theme.avatar_panel_bg}" stroke="{theme.avatar_panel_stroke}" stroke-width="4"/>
  {avatar_svg}
  {info_lines}
  {metric_svg}
  {luck_svg}
  <rect x="94" y="928" width="772" height="188" rx="18" fill="{theme.action_bg}" stroke="{theme.action_stroke}" stroke-width="4"/>
  <text x="168" y="1004" text-anchor="middle" font-size="44" font-weight="900" fill="{theme.action_text}">今日</text>
  <text x="168" y="1072" text-anchor="middle" font-size="44" font-weight="900" fill="{theme.action_text}">必做</text>
  <path d="M242 952 V1092" stroke="{theme.action_stroke}" stroke-width="4"/>
  {action_svg}
  <text x="94" y="1182" font-size="39" font-weight="900" fill="{theme.action_text}">好运口号：</text>
  <text x="292" y="1182" font-size="36" font-weight="800" fill="{theme.action_text}">{escape(card.slogan)}</text>
  <text x="480" y="1226" text-anchor="middle" font-size="24" fill="{theme.footer}">······  ✧  ······</text>
</svg>
"""


def daily_fortune_cover_content(day: date) -> tuple[str, tuple[DailyFortuneCard, ...]]:
    focus = _daily_fortune_variant(day)["focus"]
    cards = tuple(build_daily_fortune_card(sign, day) for sign in SIGN_TERMS)
    ranked = sorted(cards, key=lambda card: card.score, reverse=True)
    return focus, tuple(ranked[:3])


def render_daily_fortune_cover_svg(
    day: date,
    *,
    card_theme: str = DEFAULT_DAILY_CARD_THEME,
) -> str:
    theme = daily_card_theme(card_theme)
    palette = daily_fortune_cover_palette(theme)
    focus, top_cards = daily_fortune_cover_content(day)
    date_text = f"{day:%m.%d} · 周{'一二三四五六日'[day.weekday()]}"
    ranking_svg = "\n".join(
        f'''  <circle cx="696" cy="{148 + index * 62}" r="18" fill="{palette['gold'] if index == 1 else palette['mint']}"/>
  <text x="696" y="{156 + index * 62}" text-anchor="middle" font-size="21" font-weight="900" fill="{palette['highlight']}">{index}</text>
  <text x="730" y="{157 + index * 62}" font-size="27" font-weight="800" fill="{palette['ink']}">{escape(card.sign)}</text>
  <text x="838" y="{156 + index * 62}" text-anchor="end" font-size="21" font-weight="700" fill="{palette['muted']}">{card.score}分</text>'''
        for index, card in enumerate(top_cards, start=1)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{DAILY_FORTUNE_COVER_WIDTH}" height="{DAILY_FORTUNE_COVER_HEIGHT}" viewBox="0 0 {DAILY_FORTUNE_COVER_WIDTH} {DAILY_FORTUNE_COVER_HEIGHT}" role="img" aria-label="夏野日运 十二星座每日好运封面">
  <defs>
    <style>
      text {{
        font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif;
      }}
    </style>
  </defs>
  <rect width="900" height="380" fill="{palette['background']}"/>
  <rect x="24" y="24" width="852" height="332" rx="24" fill="{palette['highlight']}" stroke="{palette['border']}" stroke-width="2"/>
  <rect x="24" y="24" width="218" height="332" rx="24" fill="{palette['panel']}"/>
  <path d="M218 24 H242 V356 H218" fill="{palette['panel']}"/>
  <path d="M242 48 V332" stroke="{palette['border']}" stroke-width="2"/>
  <path d="M650 48 V332" stroke="{palette['border']}" stroke-width="2"/>
  <circle cx="68" cy="70" r="7" fill="{palette['gold']}"/>
  <text x="86" y="79" font-size="27" font-weight="900" fill="{palette['ink']}">夏野日运</text>
  <text x="58" y="151" font-size="23" font-weight="700" fill="{palette['muted']}">感情</text>
  <text x="58" y="203" font-size="23" font-weight="700" fill="{palette['muted']}">事业</text>
  <text x="58" y="255" font-size="23" font-weight="700" fill="{palette['muted']}">财运</text>
  <circle cx="130" cy="143" r="4" fill="{palette['mint']}"/><circle cx="130" cy="195" r="4" fill="{palette['gold']}"/><circle cx="130" cy="247" r="4" fill="{palette['mint']}"/>
  <text x="58" y="318" font-size="20" font-weight="700" fill="{palette['muted']}">每日 12 星座指南</text>
  <text x="446" y="78" text-anchor="middle" font-size="25" font-weight="800" fill="{palette['muted']}">{date_text}</text>
  <text x="446" y="126" text-anchor="middle" font-size="27" font-weight="900" fill="{palette['gold']}">十二星座每日好运</text>
  <text x="446" y="218" text-anchor="middle" font-size="72" font-weight="900" fill="{palette['ink']}">今日好运</text>
  <rect x="292" y="251" width="308" height="62" rx="31" fill="{palette['background']}" stroke="{palette['mint']}" stroke-width="2"/>
  <text x="446" y="291" text-anchor="middle" font-size="28" font-weight="800" fill="{palette['ink']}">关键词 · {escape(focus)}</text>
  <text x="682" y="91" font-size="27" font-weight="900" fill="{palette['ink']}">好运前三</text>
  <path d="M682 105 H838" stroke="{palette['gold']}" stroke-width="3"/>
{ranking_svg}
  <text x="682" y="329" font-size="18" font-weight="700" fill="{palette['muted']}">完整运势见正文</text>
</svg>
"""


def daily_fortune_cover_path(
    day: date,
    *,
    asset_dir: Path = DAILY_FORTUNE_COVER_ASSET_DIR,
    image_format: str = "png",
    card_theme: str = DEFAULT_DAILY_CARD_THEME,
) -> Path:
    extension = _daily_card_extension(image_format)
    daily_card_theme(card_theme)
    dirname = day.strftime("%Y%m%d")
    if card_theme != DEFAULT_DAILY_CARD_THEME:
        dirname = f"{dirname}_{card_theme}"
    return asset_dir / dirname / f"夏野日运.{extension}"


def daily_fortune_follow_path(
    *,
    asset_dir: Path = DAILY_FORTUNE_FOLLOW_ASSET_DIR,
) -> Path:
    return asset_dir / "夏野星座关注指引.png"


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    clean = value.lstrip("#")
    return tuple(int(clean[index : index + 2], 16) for index in (0, 2, 4))


def _blend_color(a: tuple[int, int, int], b: tuple[int, int, int], ratio: float) -> tuple[int, int, int]:
    return tuple(round(a[index] * (1 - ratio) + b[index] * ratio) for index in range(3))


def _cover_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if ImageFont is None:
        raise RuntimeError("缺少 Pillow，无法绘制日运封面")
    candidates = (
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    )
    for candidate in candidates:
        try:
            if candidate and Path(candidate).is_file():
                return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _cover_display_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if ImageFont is None:
        raise RuntimeError("缺少 Pillow，无法绘制日运封面")
    candidates = (
        "C:/Windows/Fonts/simsun.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    )
    for candidate in candidates:
        try:
            if Path(candidate).is_file():
                return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return _cover_font(size, bold=True)


def render_daily_fortune_follow_png(output_path: Path) -> None:
    if Image is None or ImageDraw is None:
        raise RuntimeError("缺少 Pillow，无法绘制日运关注指引。请运行 python -m pip install Pillow")

    scale = DAILY_FORTUNE_FOLLOW_EXPORT_SCALE
    width = DAILY_FORTUNE_FOLLOW_WIDTH * scale
    height = DAILY_FORTUNE_FOLLOW_HEIGHT * scale
    background = _hex_to_rgb("#edf8f1")
    ink = _hex_to_rgb("#24483a")
    muted = _hex_to_rgb("#526f62")
    mint = _hex_to_rgb("#70ad8b")
    border = _hex_to_rgb("#a9cbbc")
    gold = _hex_to_rgb("#ad8d58")
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)

    def p(value: int) -> int:
        return value * scale

    frame_points = (
        (p(72), p(96)),
        (p(72), p(56)),
        (p(790), p(56)),
        (p(828), p(94)),
        (p(828), p(304)),
        (p(110), p(304)),
        (p(72), p(266)),
    )
    draw.line(frame_points, fill=border, width=p(2), joint="curve")
    draw.line((p(790), p(48), p(838), p(96)), fill=mint, width=p(2))
    draw.line((p(62), p(256), p(120), p(314)), fill=mint, width=p(2))
    draw.line((p(392), p(124), p(508), p(124)), fill=gold, width=p(2))
    draw.ellipse((p(445), p(119), p(455), p(129)), fill=gold)
    draw.ellipse((p(92), p(76), p(98), p(82)), fill=mint)
    draw.ellipse((p(802), p(278), p(808), p(284)), fill=gold)

    title_font = _cover_display_font(p(37))
    subtitle_font = _cover_font(p(28), bold=False)
    title, subtitle = DAILY_FORTUNE_FOLLOW_LINES
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    draw.text(
        ((width - (title_bbox[2] - title_bbox[0])) / 2, p(148)),
        title,
        font=title_font,
        fill=ink,
    )
    draw.text(
        ((width - (subtitle_bbox[2] - subtitle_bbox[0])) / 2, p(211)),
        subtitle,
        font=subtitle_font,
        fill=muted,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)


def write_daily_fortune_follow(
    *,
    asset_dir: Path = DAILY_FORTUNE_FOLLOW_ASSET_DIR,
) -> Path:
    output_path = daily_fortune_follow_path(asset_dir=asset_dir)
    render_daily_fortune_follow_png(output_path)
    return output_path


def daily_fortune_cover_palette(theme: DailyCardTheme) -> dict[str, str]:
    if theme.key == "mint":
        return {
            "background": "#dfeee5",
            "panel": "#d3e7db",
            "highlight": "#edf7f1",
            "ink": "#24483a",
            "muted": "#526f62",
            "mint": "#70ad8b",
            "gold": "#ad8d58",
            "border": "#a9cbbc",
        }
    return {
        "background": "#fbf7f8",
        "panel": "#f3e8eb",
        "highlight": "#fffafb",
        "ink": "#573641",
        "muted": "#82646e",
        "mint": "#d39aaa",
        "gold": "#b59a68",
        "border": "#e3d2d7",
    }


def render_daily_fortune_cover_png(
    day: date,
    output_path: Path,
    *,
    card_theme: str = DEFAULT_DAILY_CARD_THEME,
) -> None:
    if Image is None or ImageDraw is None:
        raise RuntimeError("缺少 Pillow，无法绘制日运封面。请运行 python -m pip install Pillow")
    theme = daily_card_theme(card_theme)
    palette = daily_fortune_cover_palette(theme)
    width = DAILY_FORTUNE_COVER_WIDTH
    height = DAILY_FORTUNE_COVER_HEIGHT
    image = Image.new("RGB", (width, height), _hex_to_rgb(palette["background"]))
    draw = ImageDraw.Draw(image)
    ink = _hex_to_rgb(palette["ink"])
    muted = _hex_to_rgb(palette["muted"])
    mint = _hex_to_rgb(palette["mint"])
    gold = _hex_to_rgb(palette["gold"])
    border = _hex_to_rgb(palette["border"])
    panel = _hex_to_rgb(palette["panel"])
    highlight = _hex_to_rgb(palette["highlight"])
    focus, top_cards = daily_fortune_cover_content(day)
    date_text = f"{day:%m.%d} · 周{'一二三四五六日'[day.weekday()]}"

    draw.rounded_rectangle((24, 24, 876, 356), radius=24, fill=highlight, outline=border, width=2)
    draw.rounded_rectangle((24, 24, 242, 356), radius=24, fill=panel)
    draw.rectangle((218, 24, 242, 356), fill=panel)
    draw.line((242, 48, 242, 332), fill=border, width=2)
    draw.line((650, 48, 650, 332), fill=border, width=2)

    draw.ellipse((61, 63, 75, 77), fill=gold)
    draw.text((86, 50), "夏野日运", font=_cover_font(27, bold=True), fill=ink)
    small_font = _cover_font(23, bold=True)
    for index, label in enumerate(("感情", "事业", "财运")):
        y = 124 + index * 52
        draw.text((58, y), label, font=small_font, fill=muted)
        color = gold if index == 1 else mint
        draw.ellipse((126, y + 15, 134, y + 23), fill=color)
    draw.text((58, 294), "每日 12 星座指南", font=_cover_font(20, bold=True), fill=muted)

    draw.text((446, 65), date_text, font=_cover_font(25, bold=True), fill=muted, anchor="mm")
    draw.text((446, 113), "十二星座每日好运", font=_cover_font(27, bold=True), fill=gold, anchor="mm")
    draw.text((446, 187), "今日好运", font=_cover_font(72, bold=True), fill=ink, anchor="mm")
    draw.rounded_rectangle((292, 251, 600, 313), radius=31, fill=_hex_to_rgb(palette["background"]), outline=mint, width=2)
    draw.text((446, 282), f"关键词 · {focus}", font=_cover_font(28, bold=True), fill=ink, anchor="mm")

    draw.text((682, 66), "好运前三", font=_cover_font(27, bold=True), fill=ink)
    draw.line((682, 105, 838, 105), fill=gold, width=3)
    rank_font = _cover_font(21, bold=True)
    sign_font = _cover_font(27, bold=True)
    score_font = _cover_font(21, bold=True)
    for index, card in enumerate(top_cards, start=1):
        center_y = 148 + (index - 1) * 62
        badge = gold if index == 1 else mint
        draw.ellipse((678, center_y - 18, 714, center_y + 18), fill=badge)
        draw.text((696, center_y), str(index), font=rank_font, fill=highlight, anchor="mm")
        draw.text((730, center_y), card.sign, font=sign_font, fill=ink, anchor="lm")
        draw.text((838, center_y), f"{card.score}分", font=score_font, fill=muted, anchor="rm")
    draw.text((682, 307), "完整运势见正文", font=_cover_font(18, bold=True), fill=muted)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_size = (
        DAILY_FORTUNE_COVER_WIDTH * DAILY_FORTUNE_COVER_EXPORT_SCALE,
        DAILY_FORTUNE_COVER_HEIGHT * DAILY_FORTUNE_COVER_EXPORT_SCALE,
    )
    image.resize(export_size, Image.Resampling.LANCZOS).save(
        output_path,
        format="PNG",
        optimize=True,
    )


def _fit_card_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    max_width: int,
    size: int,
    min_size: int = 22,
    bold: bool = True,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    while size > min_size:
        font = _cover_font(size, bold=bold)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 2
    return _cover_font(min_size, bold=bold)


def _draw_centered_card_text(
    draw: ImageDraw.ImageDraw,
    center_x: int,
    y: int,
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((center_x - (bbox[2] - bbox[0]) / 2, y), text, font=font, fill=fill)


def _paste_daily_card_character(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    sign: str,
    *,
    character_asset_dir: Path | None,
    theme: DailyCardTheme,
) -> None:
    panel_box = (114, 220, 344, 490)
    character_path = daily_card_character_path(sign, character_asset_dir=character_asset_dir)
    if character_path is not None and ImageOps is not None:
        with Image.open(character_path) as source:
            character = ImageOps.fit(
                source.convert("RGB"),
                (230, 270),
                method=Image.Resampling.LANCZOS,
            )
        mask = Image.new("L", character.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 229, 269), radius=24, fill=255)
        image.paste(character, panel_box[:2], mask)
        return

    draw.rounded_rectangle(panel_box, radius=24, fill=DAILY_CARD_AVATAR_FILL[sign])
    fallback_font = _cover_font(54, bold=True)
    _draw_centered_card_text(
        draw,
        229,
        320,
        f"{sign}座",
        font=fallback_font,
        fill=theme.pill_label_text,
    )


def render_daily_fortune_card_png(
    card: DailyFortuneCard,
    day: date,
    output_path: Path,
    *,
    card_theme: str = DEFAULT_DAILY_CARD_THEME,
    character_asset_dir: Path | None = None,
) -> None:
    if Image is None or ImageDraw is None or ImageFont is None:
        raise RuntimeError("缺少 Pillow，无法绘制日运卡。请运行 python -m pip install Pillow")

    theme = daily_card_theme(card_theme)
    width = DAILY_CARD_WIDTH
    height = DAILY_CARD_HEIGHT
    image = Image.new("RGB", (width, height), _hex_to_rgb(theme.stripe_base))

    frame = Image.new("RGB", (884, 1232), _hex_to_rgb(theme.frame_start))
    frame_draw = ImageDraw.Draw(frame)
    frame_start = _hex_to_rgb(theme.frame_start)
    frame_end = _hex_to_rgb(theme.frame_end)
    for y in range(frame.height):
        ratio = y / max(frame.height - 1, 1)
        frame_draw.line((0, y, frame.width, y), fill=_blend_color(frame_start, frame_end, ratio))
    frame_mask = Image.new("L", frame.size, 0)
    ImageDraw.Draw(frame_mask).rounded_rectangle((0, 0, 883, 1231), radius=56, fill=255)
    image.paste(frame, (38, 24), frame_mask)

    panel = Image.new("RGB", (824, 1124), _hex_to_rgb(theme.stripe_base))
    panel_draw = ImageDraw.Draw(panel)
    for offset in range(-panel.height, panel.width, 36):
        panel_draw.line(
            (offset, panel.height, offset + panel.height, 0),
            fill=_hex_to_rgb(theme.stripe_band),
            width=10,
        )
    panel_mask = Image.new("L", panel.size, 0)
    ImageDraw.Draw(panel_mask).rounded_rectangle((0, 0, 823, 1123), radius=8, fill=255)
    image.paste(panel, (68, 70), panel_mask)

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((68, 70, 892, 1194), radius=8, outline=theme.frame_stroke, width=4)
    draw.line((70, 128, 890, 128), fill="#ffffff", width=8)

    title_font = _cover_font(84, bold=True)
    _draw_centered_card_text(draw, 480, 73, f"{card.sign}座", font=title_font, fill=theme.title)
    for cx, cy in ((280, 118), (690, 136)):
        draw.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=theme.title)
        draw.line((cx - 18, cy, cx + 18, cy), fill=theme.title, width=3)
        draw.line((cx, cy - 18, cx, cy + 18), fill=theme.title, width=3)

    draw.rounded_rectangle(
        (110, 216, 348, 494),
        radius=28,
        fill=theme.avatar_panel_bg,
        outline=theme.avatar_panel_stroke,
        width=4,
    )
    _paste_daily_card_character(
        image,
        draw,
        card.sign,
        character_asset_dir=character_asset_dir,
        theme=theme,
    )

    match_text = "、".join(f"{sign}座" for sign in card.matches)
    info_rows = (
        f"今日简述：{card.summary}",
        f"今日分数：{card.score}",
        f"合拍星座：{match_text}",
        f"建议：{card.advice}",
        f"避免：{card.avoid}",
    )
    for index, text in enumerate(info_rows):
        font = _fit_card_font(draw, text, max_width=470, size=38, min_size=26)
        draw.text((390, 222 + index * 60), text, font=font, fill=theme.action_text)

    for index, (label, value) in enumerate(card.metrics):
        column = index % 2
        row = index // 2
        x = 94 + column * 392
        y = 548 + row * 76
        draw.rounded_rectangle((x, y, x + 342, y + 56), radius=22, fill=theme.pill_bg, outline=theme.pill_stroke, width=3)
        draw.rounded_rectangle((x, y, x + 110, y + 56), radius=22, fill=theme.pill_label_bg)
        label_font = _fit_card_font(draw, label, max_width=96, size=33, min_size=25)
        value_font = _fit_card_font(draw, value, max_width=210, size=31, min_size=23)
        _draw_centered_card_text(draw, x + 55, y + 8, label, font=label_font, fill=theme.pill_label_text)
        _draw_centered_card_text(draw, x + 226, y + 9, value, font=value_font, fill=theme.pill_value_text)

    for index, (label, value) in enumerate(card.luck_rows):
        y = 712 + index * 76
        draw.rounded_rectangle((94, y, 866, y + 56), radius=22, fill=theme.bar_fill)
        draw.rounded_rectangle((94, y, 242, y + 56), radius=22, fill=theme.bar_label_bg, outline=theme.action_stroke, width=3)
        label_font = _fit_card_font(draw, label, max_width=132, size=34, min_size=25)
        value_font = _fit_card_font(draw, value, max_width=570, size=30, min_size=21)
        _draw_centered_card_text(draw, 168, y + 7, label, font=label_font, fill=theme.bar_label_text)
        draw.text((270, y + 9), value, font=value_font, fill=theme.bar_text)

    draw.rounded_rectangle((94, 928, 866, 1116), radius=18, fill=theme.action_bg, outline=theme.action_stroke, width=4)
    action_label_font = _cover_font(44, bold=True)
    for label, center_y in (("今日", 988), ("必做", 1056)):
        bbox = draw.textbbox((0, 0), label, font=action_label_font)
        label_x = 168 - (bbox[2] - bbox[0]) / 2 - bbox[0]
        label_y = center_y - (bbox[3] - bbox[1]) / 2 - bbox[1]
        draw.text((label_x, label_y), label, font=action_label_font, fill=theme.action_text)
    draw.line((242, 952, 242, 1092), fill=theme.action_stroke, width=4)
    for index, text in enumerate(card.actions):
        center_y = 974 + index * 48
        draw.ellipse((268, center_y - 14, 296, center_y + 14), outline=theme.action_stroke, width=4)
        draw.line((274, center_y - 2, 281, center_y + 6), fill=theme.action_stroke, width=5)
        draw.line((281, center_y + 6, 295, center_y - 11), fill=theme.action_stroke, width=5)
        font = _fit_card_font(draw, text, max_width=520, size=31, min_size=23)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_y = center_y - (bbox[3] - bbox[1]) / 2 - bbox[1]
        draw.text((316, text_y), text, font=font, fill=theme.action_text)

    slogan_label_font = _cover_font(39, bold=True)
    slogan_font = _fit_card_font(draw, card.slogan, max_width=560, size=36, min_size=23)
    draw.text((94, 1138), "好运口号：", font=slogan_label_font, fill=theme.action_text)
    draw.text((292, 1141), card.slogan, font=slogan_font, fill=theme.action_text)
    footer_font = _cover_font(24)
    _draw_centered_card_text(draw, 480, 1200, "······  +  ······", font=footer_font, fill=theme.footer)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)


def write_daily_fortune_cover(
    day: date,
    *,
    asset_dir: Path = DAILY_FORTUNE_COVER_ASSET_DIR,
    image_format: str = "png",
    chrome_path: Path | None = None,
    card_theme: str = DEFAULT_DAILY_CARD_THEME,
    png_renderer: str = "auto",
) -> Path:
    extension = _daily_card_extension(image_format)
    path = daily_fortune_cover_path(
        day,
        asset_dir=asset_dir,
        image_format=extension,
        card_theme=card_theme,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    svg_text = render_daily_fortune_cover_svg(day, card_theme=card_theme)
    if extension == "svg":
        path.write_text(svg_text, encoding="utf-8")
    else:
        render_daily_fortune_cover_png(day, path, card_theme=card_theme)
    return path


def daily_fortune_card_paths(
    day: date,
    *,
    asset_dir: Path = DAILY_CARD_ASSET_DIR,
    image_format: str = "png",
    card_theme: str = DEFAULT_DAILY_CARD_THEME,
) -> dict[str, Path]:
    extension = _daily_card_extension(image_format)
    daily_card_theme(card_theme)
    dirname = day.strftime("%Y%m%d")
    if card_theme != DEFAULT_DAILY_CARD_THEME:
        dirname = f"{dirname}_{card_theme}"
    output_dir = asset_dir / dirname
    return {sign: output_dir / f"{sign}座.{extension}" for sign in DAILY_CARD_SIGN_ORDER}


def _daily_card_extension(image_format: str) -> str:
    normalized = image_format.lower().lstrip(".")
    if normalized not in {"png", "svg"}:
        raise ValueError(f"不支持的信息卡格式：{image_format}")
    return normalized


def chrome_binary(explicit: Path | None = None) -> Path:
    if explicit is not None:
        if explicit.is_file():
            return explicit
        raise FileNotFoundError(f"Chrome 可执行文件不存在：{explicit}")
    env_value = os.environ.get("CHROME_BIN")
    if env_value:
        candidate = Path(env_value)
        if candidate.is_file():
            return candidate
    candidates = (
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    for command in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(command)
        if found:
            return Path(found)
    raise FileNotFoundError("未找到 Chrome/Chromium，无法把日运卡图导出为 PNG")


def render_svg_to_png(
    svg_text: str,
    png_path: Path,
    *,
    chrome_path: Path | None = None,
    renderer: str = "auto",
    width: int = DAILY_CARD_WIDTH,
    height: int = DAILY_CARD_HEIGHT,
) -> None:
    if renderer not in PNG_RENDERERS:
        raise ValueError(f"不支持的 PNG 渲染器：{renderer}")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    renderers = PNG_RENDERERS[1:] if renderer == "auto" else (renderer,)
    for candidate in renderers:
        try:
            if candidate == "resvg":
                _render_svg_to_png_resvg(svg_text, png_path, width=width, height=height)
            elif candidate == "rsvg-convert":
                _render_svg_to_png_rsvg_convert(svg_text, png_path, width=width, height=height)
            elif candidate == "cairosvg":
                _render_svg_to_png_cairosvg(svg_text, png_path, width=width, height=height)
            elif candidate == "chrome":
                _render_svg_to_png_chrome(svg_text, png_path, chrome_path=chrome_path, width=width, height=height)
            return
        except FileNotFoundError as exc:
            if renderer != "auto":
                raise RuntimeError(str(exc)) from exc
            errors.append(str(exc))
        except RuntimeError as exc:
            if renderer != "auto":
                raise
            errors.append(str(exc))
    detail = "；".join(error for error in errors if error)
    raise RuntimeError(detail or f"PNG 导出失败：{png_path.resolve()}")


def _render_svg_to_png_cairosvg(
    svg_text: str,
    png_path: Path,
    *,
    width: int,
    height: int,
) -> None:
    try:
        import cairosvg  # type: ignore[import-not-found]
    except (ImportError, OSError) as exc:
        raise FileNotFoundError(f"CairoSVG 不可用，跳过 cairosvg PNG 渲染器：{exc}") from exc
    try:
        cairosvg.svg2png(
            bytestring=svg_text.encode("utf-8"),
            write_to=str(png_path.resolve()),
            output_width=width,
            output_height=height,
        )
    except Exception as exc:
        raise RuntimeError(f"CairoSVG PNG 导出失败：{exc}") from exc
    _ensure_png_created(png_path, renderer="cairosvg")


def _render_svg_to_png_resvg(
    svg_text: str,
    png_path: Path,
    *,
    width: int,
    height: int,
) -> None:
    resvg = shutil.which("resvg")
    if not resvg:
        raise FileNotFoundError("未找到 resvg，跳过 resvg PNG 渲染器")
    with tempfile.TemporaryDirectory(prefix="daily-fortune-card-") as tmpdir:
        svg_path = Path(tmpdir) / "card.svg"
        svg_path.write_text(svg_text, encoding="utf-8")
        _run_png_renderer_command(
            [
                resvg,
                "--width",
                str(width),
                "--height",
                str(height),
                str(svg_path),
                str(png_path.resolve()),
            ],
            renderer="resvg",
            png_path=png_path,
        )


def _render_svg_to_png_rsvg_convert(
    svg_text: str,
    png_path: Path,
    *,
    width: int,
    height: int,
) -> None:
    rsvg_convert = shutil.which("rsvg-convert")
    if not rsvg_convert:
        raise FileNotFoundError("未找到 rsvg-convert，跳过 rsvg-convert PNG 渲染器")
    with tempfile.TemporaryDirectory(prefix="daily-fortune-card-") as tmpdir:
        svg_path = Path(tmpdir) / "card.svg"
        svg_path.write_text(svg_text, encoding="utf-8")
        _run_png_renderer_command(
            [
                rsvg_convert,
                "-w",
                str(width),
                "-h",
                str(height),
                "-o",
                str(png_path.resolve()),
                str(svg_path),
            ],
            renderer="rsvg-convert",
            png_path=png_path,
        )


def _run_png_renderer_command(command: list[str], *, renderer: str, png_path: Path) -> None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        output = "\n".join(
            part.strip()
            for part in (exc.stderr, exc.stdout)
            if isinstance(part, str) and part.strip()
        )
        detail = output or f"{renderer} PNG 导出超时：{png_path.resolve()}"
        raise RuntimeError(detail) from exc
    if completed.returncode != 0:
        output = "\n".join(
            part.strip()
            for part in (completed.stderr, completed.stdout)
            if part and part.strip()
        )
        raise RuntimeError(output or f"{renderer} exit={completed.returncode}")
    _ensure_png_created(png_path, renderer=renderer)


def _ensure_png_created(png_path: Path, *, renderer: str) -> None:
    if not png_path.is_file():
        raise RuntimeError(f"{renderer} 未生成文件：{png_path.resolve()}")


def _render_svg_to_png_chrome(
    svg_text: str,
    png_path: Path,
    *,
    chrome_path: Path | None = None,
    width: int,
    height: int,
) -> None:
    browser = chrome_binary(chrome_path)
    with tempfile.TemporaryDirectory(prefix="daily-fortune-card-") as tmpdir:
        svg_path = Path(tmpdir) / "card.svg"
        profile_dir = Path(tmpdir) / "chrome-profile"
        svg_path.write_text(svg_text, encoding="utf-8")
        png_target = png_path.resolve()
        command = [
            str(browser),
            "--headless",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--hide-scrollbars",
            "--no-first-run",
            f"--user-data-dir={profile_dir}",
            "--force-device-scale-factor=1",
            f"--screenshot={png_target}",
            f"--window-size={width},{height}",
            svg_path.as_uri(),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
        except subprocess.TimeoutExpired as exc:
            output = "\n".join(
                part.strip()
                for part in (exc.stderr, exc.stdout)
                if isinstance(part, str) and part.strip()
            )
            detail = output or f"Chrome PNG 导出超时：{png_path.resolve()}"
            raise RuntimeError(detail) from exc
    if completed.returncode != 0 or not png_path.is_file():
        output = "\n".join(
            part.strip()
            for part in (completed.stderr, completed.stdout)
            if part and part.strip()
        )
        detail = output or f"Chrome exit={completed.returncode}，未生成文件：{png_path.resolve()}"
        raise RuntimeError(detail)


def write_daily_fortune_cards(
    day: date,
    *,
    asset_dir: Path = DAILY_CARD_ASSET_DIR,
    image_format: str = "png",
    chrome_path: Path | None = None,
    card_theme: str = DEFAULT_DAILY_CARD_THEME,
    png_renderer: str = "auto",
    character_asset_dir: Path | None = None,
) -> dict[str, Path]:
    extension = _daily_card_extension(image_format)
    paths = daily_fortune_card_paths(
        day,
        asset_dir=asset_dir,
        image_format=extension,
        card_theme=card_theme,
    )
    if paths:
        next(iter(paths.values())).parent.mkdir(parents=True, exist_ok=True)
    for sign, path in paths.items():
        card = build_daily_fortune_card(sign, day)
        if extension == "svg":
            svg_text = render_daily_fortune_card_svg(
                card,
                day,
                card_theme=card_theme,
                character_asset_dir=character_asset_dir,
            )
            path.write_text(svg_text, encoding="utf-8")
        else:
            render_daily_fortune_card_png(
                card,
                day,
                path,
                card_theme=card_theme,
                character_asset_dir=character_asset_dir,
            )
    return paths


def daily_card_markdown_refs(
    card_paths: dict[str, Path],
    *,
    article_dir: Path,
) -> dict[str, str]:
    base = article_dir.resolve()
    return {
        sign: os.path.relpath(path.resolve(), start=base).replace(os.sep, "/")
        for sign, path in card_paths.items()
    }


def insert_daily_card_images(body: str, image_refs: dict[str, str]) -> str:
    if not image_refs:
        return body
    group_signs = {
        f"## {group_name}星座": signs
        for group_name, signs in DAILY_FORTUNE_GROUPS
    }
    output: list[str] = []
    for line in body.splitlines():
        output.append(line)
        signs = group_signs.get(line.strip())
        if not signs:
            continue
        output.append("")
        for sign in signs:
            reference = image_refs.get(sign)
            if reference:
                output.append(f"![{sign}座每日好运卡]({reference})")
        output.append("")
    return "\n".join(output)


def render_daily_fortune_with_variant(
    day: date,
    *,
    variant_offset: int = 0,
    opening_offset: int = 0,
) -> tuple[str, dict[str, str], dict[str, str]]:
    body_variant = _daily_fortune_variant(day, offset=variant_offset)
    opening = _daily_fortune_opening(day, body_variant, offset=opening_offset)
    paragraphs = [opening["text"]]
    for group_name, signs in DAILY_FORTUNE_GROUPS:
        paragraphs.append(f"## {group_name}星座")
        paragraphs.extend(
            _daily_sign_paragraph(sign, day=day, body_variant=body_variant)
            for sign in signs
        )
    paragraphs.append(
        f"今日收束：{body_variant['closing']}。把注意力放回可以行动的部分，"
        "稳定一点，今天的状态就会更容易接住。"
    )
    return "\n\n".join(paragraphs), body_variant, opening


def _select_daily_fortune_variant(
    day: date,
    *,
    recent_drafts: list[tuple[str, str]],
) -> tuple[str, dict[str, str], dict[str, str], RecentSimilarity | None, bool]:
    candidates: list[
        tuple[str, dict[str, str], dict[str, str], RecentSimilarity | None, bool]
    ] = []
    for variant_offset in range(len(DAILY_FORTUNE_VARIANTS)):
        for opening_offset in range(2):
            body, body_variant, opening = render_daily_fortune_with_variant(
                day,
                variant_offset=variant_offset,
                opening_offset=opening_offset,
            )
            similarity = recent_similarity(body, recent_drafts)
            conflicts = similarity is not None and similarity.conflicts_with(
                longest_match=DAILY_RECENT_DRAFT_LONGEST_MATCH,
                overlap=DAILY_RECENT_DRAFT_OVERLAP,
            )
            candidates.append((body, body_variant, opening, similarity, conflicts))
            if not conflicts:
                return body, body_variant, opening, similarity, False
    return min(
        candidates,
        key=lambda candidate: (
            candidate[3].overlap if candidate[3] is not None else 0.0,
            candidate[3].longest_match if candidate[3] is not None else 0,
        ),
    )


def build_daily_fortune_drafts(
    day: date,
    *,
    days: int,
    slot: int,
    recent_drafts: list[tuple[str, str]] | None = None,
) -> list[Draft]:
    drafts: list[Draft] = []
    historical = list(recent_drafts or [])
    batch_recent: list[tuple[str, str]] = []
    for day_offset in range(days):
        scheduled_for = day + timedelta(days=day_offset)
        body, body_variant, opening_variant, similarity, conflicts = _select_daily_fortune_variant(
            scheduled_for,
            recent_drafts=historical + batch_recent,
        )
        title_variants = daily_fortune_title_variants(scheduled_for)
        item = CalendarItem(
            day=scheduled_for,
            slot=slot,
            sign=DAILY_FORTUNE_SIGN,
            theme=DAILY_FORTUNE_THEME,
            title=title_variants[0]["text"],
            angle="按火土风水四组整理十二星座的原创日运提醒，给出可执行的小动作。",
        )
        drafts.append(
            Draft(
                item=item,
                title_candidates=tuple(variant["text"] for variant in title_variants),
                title_variants=title_variants,
                body=body,
                body_variant=body_variant,
                opening_variant=opening_variant,
                opening_candidates=daily_fortune_opening_candidates(
                    scheduled_for,
                    body_variant,
                    selected_key=opening_variant["key"],
                ),
                recent_conflict=(
                    f"{similarity.source_name}（连续 {similarity.longest_match} 字，"
                    f"分片 {similarity.overlap:.2%}）"
                    if conflicts and similarity
                    else None
                ),
            )
        )
        if not conflicts:
            batch_recent.append((f"daily:{scheduled_for.isoformat()}", body))
    return drafts


def render_markdown(
    draft: Draft,
    *,
    daily_card_images: dict[str, str] | None = None,
    daily_fortune_cover_image: str | None = None,
    daily_fortune_follow_image: str | None = None,
    pet_cover_image: str | None = None,
) -> str:
    body = draft.body
    if draft.item.theme == DAILY_FORTUNE_THEME and daily_card_images:
        body = insert_daily_card_images(body, daily_card_images)
    if draft.item.theme == DAILY_FORTUNE_THEME and daily_fortune_follow_image:
        body = f"{body}\n\n![每日好运关注指引]({daily_fortune_follow_image})"
    if draft.item.theme == DAILY_FORTUNE_THEME and daily_fortune_cover_image:
        body = f"![夏野日运封面]({daily_fortune_cover_image})\n\n{body}"
    elif draft.item.theme != DAILY_FORTUNE_THEME and pet_cover_image:
        body = f"![{draft.item.sign}治愈系萌宠封面]({pet_cover_image})\n\n{body}"
    return f"---\ntitle: {draft.title}\n---\n\n{body}\n"


def output_path(output_dir: Path, draft: Draft) -> Path:
    return output_dir / (
        f"{draft.item.day.strftime('%Y%m%d')}_{draft.item.slot:02d}_"
        f"{slugify(draft.title)}.md"
    )


def _draft_date(path: Path) -> date | None:
    match = re.match(r"(?P<day>\d{8})_", path.name)
    if not match:
        return None
    try:
        return date.fromisoformat(
            f"{match.group('day')[:4]}-{match.group('day')[4:6]}-{match.group('day')[6:]}"
        )
    except ValueError:
        return None


def load_recent_drafts(
    drafts_dir: Path,
    *,
    before: date,
    days: int,
) -> list[tuple[str, str]]:
    if days <= 0 or not drafts_dir.is_dir():
        return []
    start_ordinal = before.toordinal() - days
    recent: list[tuple[str, str]] = []
    for path in sorted(drafts_dir.glob("*.md")):
        published = _draft_date(path)
        if published is None or not start_ordinal <= published.toordinal() < before.toordinal():
            continue
        try:
            recent.append((path.name, parse_article(path).body))
        except OSError:
            continue
    return recent


def _comparison_text(body: str) -> str:
    text = markdown_to_plain(body)
    return re.sub(r"刷到接好运[！!]?\s*祝[^。！？!]*[。！？!]?", "", text)


def recent_similarity(
    body: str,
    recent_drafts: list[tuple[str, str]],
) -> RecentSimilarity | None:
    candidate = _comparison_text(body)
    if not candidate:
        return None
    worst: RecentSimilarity | None = None
    for source_name, source_body in recent_drafts:
        source = _comparison_text(source_body)
        if not source:
            continue
        score = RecentSimilarity(
            source_name=source_name,
            longest_match=longest_common_substring_length(source, candidate),
            overlap=shingle_overlap(source, candidate),
        )
        if worst is None or (score.overlap, score.longest_match) > (
            worst.overlap,
            worst.longest_match,
        ):
            worst = score
    return worst


def _select_body_variant(
    item: CalendarItem,
    *,
    mode: str,
    selected_title: str,
    lock_to_title: bool,
    recent_drafts: list[tuple[str, str]],
) -> tuple[str, dict[str, str], dict[str, str], RecentSimilarity | None]:
    candidates: list[tuple[str, dict[str, str], dict[str, str], RecentSimilarity | None]] = []
    variant_offsets = (0,) if lock_to_title else range(len(BODY_VARIANTS[item.theme]))
    for offset in variant_offsets:
        for opening_offset in range(len(OPENING_STYLES)):
            body, variant, opening = render_body_with_variant(
                item,
                mode=mode,
                selected_title=selected_title,
                variant_offset=offset,
                opening_offset=opening_offset,
            )
            similarity = recent_similarity(body, recent_drafts)
            candidates.append((body, variant, opening, similarity))
            if similarity is None or not similarity.conflicts:
                return body, variant, opening, similarity

    return min(
        candidates,
        key=lambda candidate: (
            candidate[3].overlap if candidate[3] is not None else 0.0,
            candidate[3].longest_match if candidate[3] is not None else 0,
        ),
    )


def build_drafts(
    day: date,
    daily: int,
    corpus_dir: Path | None,
    *,
    days: int = 1,
    mode: str = "viral-safe",
    hot_title_min_count: int = 2,
    performance_entries: list[dict[str, object]] | None = None,
    performance_min_samples: int = 3,
    recent_drafts: list[tuple[str, str]] | None = None,
) -> list[Draft]:
    items = generate_calendar(
        days=days,
        daily=daily,
        start=day,
        profile="anxia_short",
        corpus_dir=corpus_dir,
        performance_entries=performance_entries,
        performance_min_samples=performance_min_samples,
    )
    drafts: list[Draft] = []
    historical = list(recent_drafts or [])
    batch_recent: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for item in items:
        title = None
        if mode == "hot-source":
            title = hot_source_title_for_item(item, corpus_dir, min_count=hot_title_min_count)
        selected_title = title or title_for_item(item, mode if mode != "hot-source" else "viral-safe")
        body, body_variant, opening_variant, similarity = _select_body_variant(
            item,
            mode="viral-safe" if mode == "hot-source" else mode,
            selected_title=selected_title,
            lock_to_title=mode in {"balanced", "hot-source"},
            recent_drafts=historical + batch_recent.get((item.sign, item.theme), []),
        )
        preferred_key = BODY_VARIANTS[item.theme][
            _preferred_variant_index(item, selected_title)
        ]["key"]
        if mode == "viral-safe" and body_variant["key"] != preferred_key:
            selected_title = _title_for_body_variant(item, body_variant["key"])
        title_variants = title_variants_for_item(
            item,
            selected_title,
            body_variant_key=body_variant["key"],
        )
        drafts.append(
            Draft(
                item=item,
                title_override=selected_title,
                title_candidates=tuple(variant["text"] for variant in title_variants),
                title_variants=title_variants,
                body=body,
                body_variant=body_variant,
                opening_variant=opening_variant,
                opening_candidates=opening_candidates_for_item(
                    item,
                    body_variant,
                    selected_key=opening_variant["key"],
                ),
                recent_conflict=(
                    f"{similarity.source_name}（连续 {similarity.longest_match} 字，"
                    f"分片 {similarity.overlap:.2%}）"
                    if similarity and similarity.conflicts
                    else None
                ),
            )
        )
        if not similarity or not similarity.conflicts:
            batch_recent.setdefault((item.sign, item.theme), []).append(
                (f"batch:{item.day.isoformat()}:{item.slot}", body)
            )
    return drafts


def project_venv_python() -> Path | None:
    root = Path(__file__).resolve().parent.parent
    candidates = (
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _report_to_ai_result(article_path: Path, report_path: Path) -> AiCheckResult:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    return AiCheckResult(
        path=article_path,
        passed=bool(data.get("passed")),
        ratios={key: float(value) for key, value in (data.get("ratios") or {}).items()},
        mean_ai_probability=float(data.get("mean_ai_probability", 0.0)),
    )


def _run_ai_detector_subprocess(article_path: Path, python_path: Path) -> AiCheckResult:
    report_path = default_report_path(article_path)
    if report_path.exists():
        report_path.unlink()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    command = [
        str(python_path),
        str(Path(__file__).resolve().parent / "ai_detector.py"),
        str(article_path),
        "--min-total-chars",
        str(ANXIA_SHORT_MIN_TOTAL_CHARS),
    ]
    completed = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if report_path.is_file():
        return _report_to_ai_result(article_path, report_path)
    output = "\n".join(part for part in (completed.stderr.strip(), completed.stdout.strip()) if part)
    return AiCheckResult(
        path=article_path,
        passed=False,
        ratios={},
        error=output or f"AI 检测进程退出码 {completed.returncode}",
    )


def check_article_ai(article_path: Path, ai_python: Path | None = None) -> AiCheckResult:
    report_path = default_report_path(article_path)
    if report_path.exists():
        report_path.unlink()
    try:
        result = detect_article(
            article_path,
            min_total_chars=ANXIA_SHORT_MIN_TOTAL_CHARS,
            report_path=report_path,
        )
        return AiCheckResult(
            path=article_path,
            passed=result.passed,
            ratios={key: float(value) for key, value in result.report["ratios"].items()},
            mean_ai_probability=float(result.report["mean_ai_probability"]),
        )
    except DetectorUnavailable:
        python_path = ai_python or project_venv_python()
        if python_path is None or Path(sys.executable).resolve() == python_path.resolve():
            return AiCheckResult(
                path=article_path,
                passed=False,
                ratios={},
                error="缺少本地 AI 检测依赖，且未找到项目 .venv",
            )
        return _run_ai_detector_subprocess(article_path, python_path)
    except Exception as exc:
        return AiCheckResult(path=article_path, passed=False, ratios={}, error=str(exc))


def print_ai_summary(
    paths: list[Path],
    ai_python: Path | None = None,
    *,
    strict: bool = False,
) -> int:
    unique_paths = list(dict.fromkeys(path for path in paths if path.is_file()))
    if not unique_paths:
        print("AI质检：没有可检测文章")
        return 0

    results = [check_article_ai(path, ai_python=ai_python) for path in unique_paths]
    passed = sum(1 for item in results if item.passed)
    total = len(results)
    rate = passed / total * 100 if total else 0.0
    print(f"AI质检合格率：{passed}/{total} = {rate:.2f}%（发布线 human≥90%、ai≤10%）")
    for item in results:
        if item.ratios:
            human = item.ratios.get("human", 0.0)
            suspected = item.ratios.get("suspected", 0.0)
            ai = item.ratios.get("ai", 0.0)
            status = "通过" if item.passed else "未通过"
            print(
                f"- {status} {item.path.name}："
                f"human={human:.2f}%，suspected={suspected:.2f}%，ai={ai:.2f}%"
            )
        else:
            print(f"- 未完成 {item.path.name}：{item.error or '未知错误'}")
    failed = total - passed
    if failed and not strict:
        print("AI质检结果仅作编辑复核提示；如需阻断批次，请使用 --strict-ai-check。")
    return failed if strict else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="一步生成安夏短文号草稿")
    parser.add_argument("--date", default=date.today().isoformat(), help="起始日期 YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=1, help="连续生成天数，默认 1")
    parser.add_argument(
        "--daily",
        type=int,
        default=DEFAULT_DAILY_SHORT_ARTICLES,
        help=f"每天生成单星座短文篇数，默认 {DEFAULT_DAILY_SHORT_ARTICLES}",
    )
    daily_fortune_group = parser.add_mutually_exclusive_group()
    daily_fortune_group.add_argument(
        "--include-daily-fortune",
        dest="include_daily_fortune",
        action="store_true",
        help="额外生成一篇十二星座每日好运，默认开启",
    )
    daily_fortune_group.add_argument(
        "--no-daily-fortune",
        dest="include_daily_fortune",
        action="store_false",
        help="只生成单星座短文，不生成十二星座每日好运",
    )
    parser.set_defaults(include_daily_fortune=True)
    parser.add_argument(
        "--daily-fortune-only",
        action="store_true",
        help="只生成十二星座每日好运，适合提前补一周日运",
    )
    parser.add_argument(
        "--mode",
        choices=("viral-safe", "balanced", "hot-source"),
        default="viral-safe",
        help="viral-safe 更强标题和结尾钩子；balanced 更克制；hot-source 优先直接使用热标题",
    )
    parser.add_argument("--hot-title-min-count", type=int, default=2, help="热标题最少重复次数，默认 2")
    parser.add_argument("--output-dir", type=Path, default=ARTICLES_DIR)
    parser.add_argument("--record-dir", type=Path, default=DEFAULT_RECORD_DIR)
    parser.add_argument("--card-dir", type=Path, default=DAILY_CARD_ASSET_DIR)
    parser.add_argument(
        "--card-format",
        choices=("png", "svg"),
        default="png",
        help="日运信息卡输出格式，默认 png；调试模板时可用 svg",
    )
    parser.add_argument(
        "--card-theme",
        choices=tuple(DAILY_CARD_THEMES),
        default=DEFAULT_DAILY_CARD_THEME,
        help="日运信息卡主题，默认 mint；可用 pink 生成桃粉 A/B 版",
    )
    parser.add_argument(
        "--png-renderer",
        choices=PNG_RENDERERS,
        default="auto",
        help="日运 PNG 渲染器，默认 auto：优先 resvg/rsvg-convert/cairosvg，最后回退 Chrome",
    )
    parser.add_argument("--chrome-bin", type=Path, help="指定用于导出 PNG 的 Chrome/Chromium 可执行文件")
    card_group = parser.add_mutually_exclusive_group()
    card_group.add_argument(
        "--daily-card-assets",
        dest="daily_card_assets",
        action="store_true",
        help="为十二星座每日好运生成 12 张本地 PNG 信息卡，默认开启",
    )
    card_group.add_argument(
        "--no-daily-card-assets",
        dest="daily_card_assets",
        action="store_false",
        help="只生成日运正文，不生成或引用信息卡图片",
    )
    parser.set_defaults(daily_card_assets=True)
    parser.add_argument("--zodiac-character-dir", type=Path, default=DAILY_CARD_CHARACTER_DIR)
    parser.add_argument(
        "--refresh-zodiac-characters",
        action="store_true",
        help="先用本地 ComfyUI 重新生成完整的十二星座动漫人物，再生成日运卡",
    )
    parser.add_argument("--character-comfy-endpoint", default=DEFAULT_COMFY_ENDPOINT)
    parser.add_argument("--character-comfy-profile", default=DEFAULT_COMFY_PROFILE, choices=("flux2_klein",))
    parser.add_argument("--character-max-wait", type=int, default=600)
    parser.add_argument("--character-poll-seconds", type=float, default=1.5)
    parser.add_argument("--daily-fortune-cover-dir", type=Path, default=DAILY_FORTUNE_COVER_ASSET_DIR)
    daily_fortune_cover_group = parser.add_mutually_exclusive_group()
    daily_fortune_cover_group.add_argument(
        "--daily-fortune-cover-assets",
        dest="daily_fortune_cover_assets",
        action="store_true",
        help="为十二星座每日好运生成夏野日运横向封面，默认开启",
    )
    daily_fortune_cover_group.add_argument(
        "--no-daily-fortune-cover-assets",
        dest="daily_fortune_cover_assets",
        action="store_false",
        help="只生成日运正文和卡片，不生成或引用夏野日运封面",
    )
    parser.set_defaults(daily_fortune_cover_assets=True)
    parser.add_argument("--daily-fortune-follow-dir", type=Path, default=DAILY_FORTUNE_FOLLOW_ASSET_DIR)
    daily_fortune_follow_group = parser.add_mutually_exclusive_group()
    daily_fortune_follow_group.add_argument(
        "--daily-fortune-follow-assets",
        dest="daily_fortune_follow_assets",
        action="store_true",
        help="为十二星座每日好运生成并引用薄荷绿关注指引，默认开启",
    )
    daily_fortune_follow_group.add_argument(
        "--no-daily-fortune-follow-assets",
        dest="daily_fortune_follow_assets",
        action="store_false",
        help="不生成或引用每日好运关注指引",
    )
    parser.set_defaults(daily_fortune_follow_assets=True)
    parser.add_argument("--pet-cover-dir", type=Path, default=PET_COVER_ASSET_DIR)
    pet_cover_group = parser.add_mutually_exclusive_group()
    pet_cover_group.add_argument(
        "--pet-cover-assets",
        dest="pet_cover_assets",
        action="store_true",
        help="为非每日好运的单星座短文生成本地 ComfyUI 治愈系萌宠封面，默认开启",
    )
    pet_cover_group.add_argument(
        "--no-pet-cover-assets",
        dest="pet_cover_assets",
        action="store_false",
        help="只生成单星座正文，不生成或引用萌宠封面",
    )
    parser.set_defaults(pet_cover_assets=True)
    parser.add_argument("--pet-comfy-endpoint", default=DEFAULT_COMFY_ENDPOINT)
    parser.add_argument("--pet-comfy-profile", default=DEFAULT_COMFY_PROFILE, choices=("flux2_klein",))
    parser.add_argument("--pet-cover-max-wait", type=int, default=600)
    parser.add_argument("--pet-cover-poll-seconds", type=float, default=1.5)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--performance-log", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--performance-min-samples", type=int, default=3)
    parser.add_argument("--history-dir", type=Path, help="近稿去重目录，默认与 --output-dir 相同")
    parser.add_argument("--recent-days", type=int, default=RECENT_DRAFT_DAYS)
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在草稿")
    parser.add_argument("--skip-ai-check", action="store_true", help="生成后不运行 AI 质检")
    parser.add_argument("--strict-ai-check", action="store_true", help="AI 质检未通过时使批次失败")
    parser.add_argument("--ai-python", type=Path, help="指定运行 AI 检测的 Python")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写入文件")
    args = parser.parse_args()

    try:
        day = date.fromisoformat(args.date)
    except ValueError as exc:
        parser.error(f"--date 必须是 YYYY-MM-DD：{exc}")
    if args.recent_days <= 0:
        parser.error("--recent-days 必须大于 0")
    if args.performance_min_samples <= 0:
        parser.error("--performance-min-samples 必须大于 0")
    if args.daily_fortune_only and not args.include_daily_fortune:
        parser.error("--daily-fortune-only 不能与 --no-daily-fortune 同时使用")
    if args.refresh_zodiac_characters and not args.include_daily_fortune:
        parser.error("--refresh-zodiac-characters 需要启用十二星座每日好运")

    try:
        performance_entries = load_entries(args.performance_log)
    except ValueError as exc:
        parser.error(str(exc))
    history_dir = args.history_dir or args.output_dir
    recent_drafts = load_recent_drafts(
        history_dir,
        before=day,
        days=args.recent_days,
    )

    drafts = []
    if not args.daily_fortune_only:
        drafts = build_drafts(
            day,
            args.daily,
            args.source_dir,
            days=args.days,
            mode=args.mode,
            hot_title_min_count=args.hot_title_min_count,
            performance_entries=performance_entries,
            performance_min_samples=args.performance_min_samples,
            recent_drafts=recent_drafts,
        )
    if args.include_daily_fortune:
        drafts.extend(
            build_daily_fortune_drafts(
                day,
                days=args.days,
                slot=args.daily + 1,
                recent_drafts=recent_drafts,
            )
        )
    forbidden_titles = None
    source_texts = None
    if args.source_dir and not args.daily_fortune_only:
        try:
            forbidden_titles, source_texts = load_source_dir(args.source_dir)
            if args.mode == "hot-source":
                forbidden_titles, source_texts = load_source_dir(
                    args.source_dir,
                    allow_hot_titles=True,
                    hot_title_min_count=args.hot_title_min_count,
                )
        except FileNotFoundError as exc:
            parser.error(str(exc))

    failures = 0
    written = 0
    skipped = 0
    batch_paths: list[Path] = []
    if not args.dry_run:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        if args.refresh_zodiac_characters:
            refresh_zodiac_characters_with_comfyui(
                asset_dir=args.zodiac_character_dir,
                endpoint=args.character_comfy_endpoint,
                model_profile=args.character_comfy_profile,
                max_wait=args.character_max_wait,
                poll_seconds=args.character_poll_seconds,
            )
    for draft in drafts:
        if draft.recent_conflict:
            print(
                f"近稿相似度过高，无法找到可用正文变体：{draft.item.day} "
                f"{draft.item.sign} {draft.item.theme}，命中 {draft.recent_conflict}",
                file=sys.stderr,
            )
            failures += 1
            continue
        path = output_path(args.output_dir, draft)
        if args.dry_run:
            daily_card_images = None
            daily_fortune_cover_image = None
            daily_fortune_follow_image = None
            pet_cover_image = None
            if draft.item.theme == DAILY_FORTUNE_THEME:
                if args.daily_fortune_cover_assets:
                    daily_fortune_cover_image = markdown_ref(
                        daily_fortune_cover_path(
                            draft.item.day,
                            asset_dir=args.daily_fortune_cover_dir,
                            image_format=args.card_format,
                            card_theme=args.card_theme,
                        ),
                        article_dir=path.parent,
                    )
                if args.daily_fortune_follow_assets:
                    daily_fortune_follow_image = markdown_ref(
                        daily_fortune_follow_path(asset_dir=args.daily_fortune_follow_dir),
                        article_dir=path.parent,
                    )
                if args.daily_card_assets:
                    daily_card_images = daily_card_markdown_refs(
                        daily_fortune_card_paths(
                            draft.item.day,
                            asset_dir=args.card_dir,
                            image_format=args.card_format,
                            card_theme=args.card_theme,
                        ),
                        article_dir=path.parent,
                    )
            elif draft.item.theme != DAILY_FORTUNE_THEME and args.pet_cover_assets:
                pet_cover_image = pet_cover_markdown_ref(
                    pet_cover_path(args.pet_cover_dir, draft),
                    article_dir=path.parent,
                )
            content = render_markdown(
                draft,
                daily_card_images=daily_card_images,
                daily_fortune_cover_image=daily_fortune_cover_image,
                daily_fortune_follow_image=daily_fortune_follow_image,
                pet_cover_image=pet_cover_image,
            )
            print(f"\n# {path.name}\n{content}")
            continue
        if path.exists() and not args.overwrite:
            print(f"草稿已存在，跳过：{path}", file=sys.stderr)
            skipped += 1
            batch_paths.append(path)
            continue
        daily_card_images = None
        daily_fortune_cover_image = None
        daily_fortune_follow_image = None
        pet_cover_image = None
        if draft.item.theme == DAILY_FORTUNE_THEME:
            if args.daily_fortune_cover_assets:
                cover_path = write_daily_fortune_cover(
                    draft.item.day,
                    asset_dir=args.daily_fortune_cover_dir,
                    image_format=args.card_format,
                    chrome_path=args.chrome_bin,
                    card_theme=args.card_theme,
                    png_renderer=args.png_renderer,
                )
                daily_fortune_cover_image = markdown_ref(cover_path, article_dir=path.parent)
                print(f"已生成日运封面：{cover_path}")
            if args.daily_card_assets:
                card_paths = write_daily_fortune_cards(
                    draft.item.day,
                    asset_dir=args.card_dir,
                    image_format=args.card_format,
                    chrome_path=args.chrome_bin,
                    card_theme=args.card_theme,
                    png_renderer=args.png_renderer,
                    character_asset_dir=args.zodiac_character_dir,
                )
                daily_card_images = daily_card_markdown_refs(card_paths, article_dir=path.parent)
                print(f"已生成日运卡图：{next(iter(card_paths.values())).parent}")
            if args.daily_fortune_follow_assets:
                follow_path = write_daily_fortune_follow(asset_dir=args.daily_fortune_follow_dir)
                daily_fortune_follow_image = markdown_ref(follow_path, article_dir=path.parent)
                print(f"已生成关注指引：{follow_path}")
        elif draft.item.theme != DAILY_FORTUNE_THEME and args.pet_cover_assets:
            cover_path = write_pet_cover_with_comfyui(
                draft,
                asset_dir=args.pet_cover_dir,
                endpoint=args.pet_comfy_endpoint,
                model_profile=args.pet_comfy_profile,
                max_wait=args.pet_cover_max_wait,
                poll_seconds=args.pet_cover_poll_seconds,
            )
            pet_cover_image = pet_cover_markdown_ref(cover_path, article_dir=path.parent)
            print(f"已生成萌宠封面：{cover_path}")
        content = render_markdown(
            draft,
            daily_card_images=daily_card_images,
            daily_fortune_cover_image=daily_fortune_cover_image,
            daily_fortune_follow_image=daily_fortune_follow_image,
            pet_cover_image=pet_cover_image,
        )
        path.write_text(content, encoding="utf-8")
        written += 1
        batch_paths.append(path)
        profile = "daily_fortune" if draft.item.theme == DAILY_FORTUNE_THEME else "anxia_short"
        result = validate_article(
            parse_article(path),
            profile=profile,
            forbidden_titles=forbidden_titles,
            source_texts=source_texts,
        )
        print(f"已生成：{path}")
        print(format_result(result))
        if not result.ok:
            failures += 1
            continue
        record_path = write_generated_record(
            path,
            item=draft.item,
            title_candidates=draft.title_candidates,
            body_variant=draft.body_variant,
            source_dir=None if draft.item.theme == DAILY_FORTUNE_THEME else args.source_dir,
            record_dir=args.record_dir,
            title_variants=draft.title_variants,
            opening_variants=draft.opening_candidates,
            selected_title_variant=draft.title_variants[0]["key"],
            selected_opening_variant=draft.opening_variant["key"],
        )
        print(f"已写入编辑记录：{record_path}")
    if not args.dry_run:
        print(f"完成：新增/覆盖 {written} 篇，跳过 {skipped} 篇，失败 {failures} 篇")
        if not args.skip_ai_check:
            failures += print_ai_summary(
                batch_paths,
                ai_python=args.ai_python,
                strict=args.strict_ai_check,
            )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
