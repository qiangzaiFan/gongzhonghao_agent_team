#!/usr/bin/env python3
"""Generate Anxia-style short article drafts in one command."""

from __future__ import annotations

import argparse
from html import escape
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

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


ARTICLES_DIR = Path(__file__).parent / "articles"
DEFAULT_DAILY_SHORT_ARTICLES = 2
RECENT_DRAFT_DAYS = 30
RECENT_DRAFT_LONGEST_MATCH = 55
RECENT_DRAFT_OVERLAP = 0.14
DAILY_RECENT_DRAFT_LONGEST_MATCH = 75
DAILY_RECENT_DRAFT_OVERLAP = 0.35


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
        "{sign}注意：本月这个习惯必须改！",
        "{sign}下半年这个转折很关键！",
        "{month}，给{sign}一个重要提醒！",
        "{sign}整体运势马上开始走高！",
    ),
    "关系/性格": (
        "能让{sign}瞬间清醒的一个细节",
        "{sign}这辈子最该珍惜的贵人",
        "真正懂{sign}的人，藏不住了",
        "{sign}别再为这种关系委屈自己",
    ),
    "财运/贵人": (
        "{sign}在{month}有个贵人正在靠近！",
        "{sign}接下来必定迎来一波收获",
        "{sign}这个财务信号千万别忽略！",
        "{sign}最近贵人运开始强了！",
    ),
}

BODY_VARIANTS = {
    "运势/提醒": (
        {
            "key": "restore-priority",
            "hook": "拖了很久的事已经需要重新整理",
            "focus": "减少人情和重复沟通带来的注意力消耗",
            "closing": "把节奏拿回来",
        },
        {
            "key": "screen-requests",
            "hook": "临时请求会变多，别每一件都立刻接下",
            "focus": "先分清真正能推进的合作与无效消耗",
            "closing": "把时间留给值得推进的方向",
        },
        {
            "key": "finish-loops",
            "hook": "旧问题反复出现，是因为还没有真正收尾",
            "focus": "把卡住的流程、承诺和沟通逐个落地",
            "closing": "先完成一件最关键的小事",
        },
    ),
    "关系/性格": (
        {
            "key": "uneven-response",
            "hook": "一个细节看多了，心里自然会有答案",
            "focus": "识别只在需要时靠近、平时缺少回应的关系",
            "closing": "把真心留给稳定回应的人",
        },
        {
            "key": "stop-explaining",
            "hook": "总是你先解释和缓和的关系，会慢慢让人疲惫",
            "focus": "停止替对方补全态度，把注意力放回真实行动",
            "closing": "别再替沉默找借口",
        },
        {
            "key": "boundary-reset",
            "hook": "关系里最消耗人的，不是争执，是默认你会让步",
            "focus": "把可接受和不可接受的边界说清楚",
            "closing": "把自己的感受放回优先级",
        },
    ),
    "财运/贵人": (
        {
            "key": "subscription-audit",
            "hook": "付款前多停十分钟，能避开不少小漏财",
            "focus": "检查自动续费、拼单和旧会员支出",
            "closing": "把账算清楚再决定",
        },
        {
            "key": "small-opportunity",
            "hook": "真正有价值的小机会，常常藏在不起眼的邀约里",
            "focus": "分辨能积累资源的合作和一时热闹",
            "closing": "先接住能沉淀的机会",
        },
        {
            "key": "money-boundary",
            "hook": "钱的事越含糊，后面越容易尴尬",
            "focus": "把分摊、借用和回款的边界提前说清楚",
            "closing": "该收回来的别再拖",
        },
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
DAILY_CARD_WIDTH = 960
DAILY_CARD_HEIGHT = 1280
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
DEFAULT_DAILY_CARD_THEME = "pink"
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


def daily_card_theme(theme: str) -> DailyCardTheme:
    try:
        return DAILY_CARD_THEMES[theme]
    except KeyError as exc:
        supported = ", ".join(sorted(DAILY_CARD_THEMES))
        raise ValueError(f"不支持的信息卡主题：{theme}，可选：{supported}") from exc


def slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", text).strip("-")
    return slug[:48] or "anxia-draft"


def title_for_item(item: CalendarItem, mode: str) -> str:
    if mode in {"balanced", "hot-source"}:
        return item.title
    titles = VIRAL_TITLES[item.theme]
    index = (item.day.toordinal() + item.slot) % len(titles)
    month = f"{item.day.month}月"
    return titles[index].format(sign=item.sign, month=month)


def title_candidates_for_item(item: CalendarItem, selected_title: str) -> tuple[str, ...]:
    month = f"{item.day.month}月"
    templates = VIRAL_TITLES[item.theme]
    options = [
        selected_title,
        item.title,
        *(template.format(sign=item.sign, month=month) for template in templates),
    ]
    candidates = list(dict.fromkeys(option.strip() for option in options if option.strip()))
    return tuple(candidates[:4])


def title_formula(title: str, theme: str) -> str:
    if theme == DAILY_FORTUNE_THEME:
        return "全星座日运型"
    if theme == "关系/性格":
        return "关系洞察型"
    if theme == "财运/贵人":
        return "财务提醒型" if any(term in title for term in ("提醒", "忽略", "注意")) else "机会型"
    return "提醒型" if any(term in title for term in ("注意", "提醒", "忽略", "必须")) else "变化预告型"


def title_variants_for_item(item: CalendarItem, selected_title: str) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "key": f"title-{index}",
            "text": title,
            "formula": title_formula(title, item.theme),
        }
        for index, title in enumerate(title_candidates_for_item(item, selected_title), start=1)
    )


def daily_fortune_title_variants(day: date) -> tuple[dict[str, str], ...]:
    formatted_day = day.strftime("%Y.%m.%d")
    return (
        {
            "key": "title-1",
            "text": f"十二星座每日好运丨{formatted_day}",
            "formula": "全星座日运型",
        },
        {
            "key": "title-2",
            "text": f"十二星座今日好运指南丨{formatted_day}",
            "formula": "全星座日运型",
        },
        {
            "key": "title-3",
            "text": f"{formatted_day} 十二星座日运提醒",
            "formula": "全星座日运型",
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


def _variant_for_item(item: CalendarItem, *, offset: int = 0) -> dict[str, str]:
    sign_index = SIGN_TERMS.index(item.sign) if item.sign in SIGN_TERMS else 0
    variants = BODY_VARIANTS[item.theme]
    return variants[(item.day.toordinal() + sign_index + offset) % len(variants)]


def _opening_for_item(
    item: CalendarItem,
    body_variant: dict[str, str],
    *,
    offset: int = 0,
) -> dict[str, str]:
    style = OPENING_STYLES[(item.day.toordinal() + item.slot + offset) % len(OPENING_STYLES)]
    hook = body_variant["hook"].rstrip("。！？!")
    if style["key"] == "detail-observation":
        suffix = {
            "运势/提醒": "别把它当成小事",
            "关系/性格": "你的感受已经在给答案",
            "财运/贵人": "判断时多给自己十分钟",
        }[item.theme]
        text = f"{item.sign}这段时间会慢慢看清：{hook}，{suffix}。"
    else:
        prefix = {
            "运势/提醒": "最近要注意",
            "关系/性格": "最近在关系里要留意",
            "财运/贵人": "最近在钱和机会上的提醒是",
        }[item.theme]
        text = f"{item.sign}{prefix}：{hook}。"
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
    variant_offset: int = 0,
    opening_offset: int = 0,
) -> tuple[str, dict[str, str], dict[str, str]]:
    trait_a, trait_b, trait_c = SIGN_TRAITS.get(item.sign, ("状态敏感", "需要稳住节奏", "适合看清重点"))
    sign = item.sign
    variant = _variant_for_item(item, offset=variant_offset)
    opening = _opening_for_item(item, variant, offset=opening_offset)
    if item.theme == "运势/提醒":
        if variant["key"] == "screen-requests":
            paragraphs = [
                f"{sign}最近要注意：临时找上门的事会变多，不是每一件都值得你立刻答应。",
                f"你们本来就{trait_a}，别人一句“就差你了”很容易让你多接一份任务。先看这件事能不能推进自己，再决定要不要投入。",
                "真正值得留住的合作，会把方向说清楚；只靠情绪催你的人，多半会继续消耗你的时间。",
                f"刷到接好运！祝{sign}把时间留给值得推进的方向，稳住自己的节奏。",
            ]
        elif variant["key"] == "finish-loops":
            paragraphs = [
                f"{sign}这段时间别忽略反复冒出来的旧问题，它提醒你有件事还没有真正收尾。",
                f"你们{trait_a}，越是悬着不处理，越容易在心里来回想。工作流程、没说开的承诺、搁置的决定，都该挑一件先落地。",
                "别急着一次解决全部。先完成最关键的那一步，后面的变化才会慢慢顺起来。",
                f"刷到接好运！祝{sign}稳住心气，先完成一件最关键的小事。",
            ]
        else:
            paragraphs = [
                f"{sign}最近别小看一个变化：有些拖了很久的事，已经到了必须整理的时候。",
                f"你们本来就{trait_a}，但这段时间容易被琐事分走注意力。临时安排、人情请求、重复沟通，都会一点点消耗状态。",
                "真正要抓住的，是能让你往前走的事。该拒绝的别硬撑，该推进的别再等，先把节奏拿回来。",
                f"刷到接好运！祝{sign}稳住这口气，把这个月的好状态一点点找回来。",
            ]
    elif item.theme == "关系/性格":
        if variant["key"] == "stop-explaining":
            paragraphs = [
                f"{sign}最容易累的关系，不一定是吵得凶，而是每次都要你先解释、先缓和。",
                f"你们{trait_b}，所以总想给对方留一点余地。但真正重视你的人，不会把回应变成一次次需要你追着要的事。",
                "别再替沉默找理由，也别把懂事当成只能退让。看行动，比反复猜态度更有用。",
                f"刷到接好运！祝{sign}少一点内耗，把真心留给愿意回应你的人。",
            ]
        elif variant["key"] == "boundary-reset":
            paragraphs = [
                f"{sign}在关系里真正该留意的，是别人是不是默认你会一直让步。",
                f"你们{trait_b}，很多时候不想把话说重，宁愿自己消化。可一段关系如果总靠你往后退，心里迟早会失衡。",
                "把可接受和不可接受的部分说清楚，不是冷淡，是让彼此都知道该怎么靠近。",
                f"刷到接好运！祝{sign}把自己的感受放回优先级，关系也会更轻松。",
            ]
        else:
            paragraphs = [
                f"{sign}不是突然变冷，很多时候是一个细节看多了，心里自然有了答案。",
                f"你们{trait_b}，一开始会给对方余地，也愿意替关系找理由。但只在需要时靠近、平时很少回应的人，最容易让{sign}慢慢清醒。",
                "别再把自己的退后解释成小题大做。谁是真心，谁只是顺手消耗，其实你早就感觉到了。",
                f"刷到接好运！祝{sign}把真心留给稳定回应你的人，少一点内耗。",
            ]
    else:
        if variant["key"] == "small-opportunity":
            paragraphs = [
                f"{sign}最近别只盯着大消息，有些不起眼的邀约，反而可能带来新的机会。",
                f"你们{trait_c}，能很快判断一件事值不值得做。有人介绍的合作、临时出现的项目、一个愿意分享资源的人，都可以多听两句。",
                "但别为了热闹什么都接。能让你积累经验、人脉或稳定回报的，才值得认真跟进。",
                f"刷到接好运！祝{sign}先接住能沉淀的机会，把小变化做成真收获。",
            ]
        elif variant["key"] == "money-boundary":
            paragraphs = [
                f"{sign}最近在钱上要多一点直接，含糊过去的小事，后面最容易变成尴尬。",
                f"你们{trait_c}，但分摊、借用、回款这些问题不能只靠默契。该确认金额就确认，该约时间就约时间，别一直替别人留空白。",
                "把话说清楚不是计较，反而能让关系和合作都更轻松。",
                f"刷到接好运！祝{sign}把边界讲明白，该收回来的别再拖。",
            ]
        else:
            paragraphs = [
                f"{sign}今天先别急着付款。看到优惠、链接、群里的临时拼单，停十分钟再点。",
                f"你们{trait_c}，但最近消息太杂，容易顺手答应。以前说好的分摊、会员、订阅，翻出来看一眼，别让小钱悄悄漏掉。",
                "少花一笔不丢人，该收回来的也别一直拖。把账说清楚，反而省掉后面的尴尬。",
                f"刷到接好运！祝{sign}把钱包看稳，接下来该来的小进账别错过。",
            ]
    paragraphs[0] = opening["text"]
    return "\n\n".join(paragraphs), variant, opening


def render_body(item: CalendarItem, *, mode: str = "viral-safe") -> str:
    body, _, _ = render_body_with_variant(item, mode=mode)
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
    y = 984 + index * 48
    return "\n".join(
        (
            f'<circle cx="282" cy="{y - 10}" r="14" fill="none" stroke="{theme.action_stroke}" stroke-width="4"/>',
            f'<path d="M274 {y - 12} L281 {y - 4} L295 {y - 21}" fill="none" '
            f'stroke="{theme.action_stroke}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>',
            f'<text x="316" y="{y}" font-size="31" font-weight="700" '
            f'fill="{theme.action_text}">{escape(text)}</text>',
        )
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
  </defs>
  <rect x="38" y="24" width="884" height="1232" rx="56" fill="url(#cardFrame)"/>
  <rect x="68" y="70" width="824" height="1124" rx="8" fill="url(#stripe)" stroke="{theme.frame_stroke}" stroke-width="4"/>
  <path d="M70 128 H890" stroke="#ffffff" stroke-width="8" opacity="0.9"/>
  <text x="480" y="156" text-anchor="middle" font-size="84" font-weight="900" fill="{theme.title}">{escape(sign_title)}</text>
  <text x="280" y="134" text-anchor="middle" font-size="42" fill="{theme.title}">✧</text>
  <text x="690" y="150" text-anchor="middle" font-size="42" fill="{theme.title}">✦</text>
  <rect x="110" y="216" width="238" height="278" rx="28" fill="{theme.avatar_panel_bg}" stroke="{theme.avatar_panel_stroke}" stroke-width="4"/>
  {_daily_avatar_svg(card.sign, avatar_fill, accent=theme.avatar_accent)}
  {info_lines}
  {metric_svg}
  {luck_svg}
  <rect x="94" y="928" width="772" height="188" rx="18" fill="{theme.action_bg}" stroke="{theme.action_stroke}" stroke-width="4"/>
  <text x="168" y="1002" text-anchor="middle" font-size="44" font-weight="900" fill="{theme.action_text}">今日</text>
  <text x="168" y="1058" text-anchor="middle" font-size="44" font-weight="900" fill="{theme.action_text}">必做</text>
  <path d="M242 952 V1092" stroke="{theme.action_stroke}" stroke-width="4"/>
  {action_svg}
  <text x="94" y="1182" font-size="39" font-weight="900" fill="{theme.action_text}">好运口号：</text>
  <text x="292" y="1182" font-size="36" font-weight="800" fill="{theme.action_text}">{escape(card.slogan)}</text>
  <text x="480" y="1226" text-anchor="middle" font-size="24" fill="{theme.footer}">······  ✧  ······</text>
</svg>
"""


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
) -> None:
    if renderer not in PNG_RENDERERS:
        raise ValueError(f"不支持的 PNG 渲染器：{renderer}")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    renderers = PNG_RENDERERS[1:] if renderer == "auto" else (renderer,)
    for candidate in renderers:
        try:
            if candidate == "resvg":
                _render_svg_to_png_resvg(svg_text, png_path)
            elif candidate == "rsvg-convert":
                _render_svg_to_png_rsvg_convert(svg_text, png_path)
            elif candidate == "cairosvg":
                _render_svg_to_png_cairosvg(svg_text, png_path)
            elif candidate == "chrome":
                _render_svg_to_png_chrome(svg_text, png_path, chrome_path=chrome_path)
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


def _render_svg_to_png_cairosvg(svg_text: str, png_path: Path) -> None:
    try:
        import cairosvg  # type: ignore[import-not-found]
    except (ImportError, OSError) as exc:
        raise FileNotFoundError(f"CairoSVG 不可用，跳过 cairosvg PNG 渲染器：{exc}") from exc
    try:
        cairosvg.svg2png(
            bytestring=svg_text.encode("utf-8"),
            write_to=str(png_path.resolve()),
            output_width=DAILY_CARD_WIDTH,
            output_height=DAILY_CARD_HEIGHT,
        )
    except Exception as exc:
        raise RuntimeError(f"CairoSVG PNG 导出失败：{exc}") from exc
    _ensure_png_created(png_path, renderer="cairosvg")


def _render_svg_to_png_resvg(svg_text: str, png_path: Path) -> None:
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
                str(DAILY_CARD_WIDTH),
                "--height",
                str(DAILY_CARD_HEIGHT),
                str(svg_path),
                str(png_path.resolve()),
            ],
            renderer="resvg",
            png_path=png_path,
        )


def _render_svg_to_png_rsvg_convert(svg_text: str, png_path: Path) -> None:
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
                str(DAILY_CARD_WIDTH),
                "-h",
                str(DAILY_CARD_HEIGHT),
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
            f"--window-size={DAILY_CARD_WIDTH},{DAILY_CARD_HEIGHT}",
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
        svg_text = render_daily_fortune_card_svg(card, day, card_theme=card_theme)
        if extension == "svg":
            path.write_text(svg_text, encoding="utf-8")
        else:
            render_svg_to_png(
                svg_text,
                path,
                chrome_path=chrome_path,
                renderer=png_renderer,
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
) -> str:
    body = draft.body
    if draft.item.theme == DAILY_FORTUNE_THEME and daily_card_images:
        body = insert_daily_card_images(body, daily_card_images)
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
    recent_drafts: list[tuple[str, str]],
) -> tuple[str, dict[str, str], dict[str, str], RecentSimilarity | None]:
    candidates: list[tuple[str, dict[str, str], dict[str, str], RecentSimilarity | None]] = []
    for offset in range(len(BODY_VARIANTS[item.theme])):
        for opening_offset in range(len(OPENING_STYLES)):
            body, variant, opening = render_body_with_variant(
                item,
                mode=mode,
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
            recent_drafts=historical + batch_recent.get((item.sign, item.theme), []),
        )
        title_variants = title_variants_for_item(item, selected_title)
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
        help="日运信息卡主题，默认 pink；可用 mint 生成薄荷绿 A/B 版",
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
            if draft.item.theme == DAILY_FORTUNE_THEME and args.daily_card_assets:
                daily_card_images = daily_card_markdown_refs(
                    daily_fortune_card_paths(
                        draft.item.day,
                        asset_dir=args.card_dir,
                        image_format=args.card_format,
                        card_theme=args.card_theme,
                    ),
                    article_dir=path.parent,
                )
            content = render_markdown(draft, daily_card_images=daily_card_images)
            print(f"\n# {path.name}\n{content}")
            continue
        if path.exists() and not args.overwrite:
            print(f"草稿已存在，跳过：{path}", file=sys.stderr)
            skipped += 1
            batch_paths.append(path)
            continue
        daily_card_images = None
        if draft.item.theme == DAILY_FORTUNE_THEME and args.daily_card_assets:
            card_paths = write_daily_fortune_cards(
                draft.item.day,
                asset_dir=args.card_dir,
                image_format=args.card_format,
                chrome_path=args.chrome_bin,
                card_theme=args.card_theme,
                png_renderer=args.png_renderer,
            )
            daily_card_images = daily_card_markdown_refs(card_paths, article_dir=path.parent)
            print(f"已生成日运卡图：{next(iter(card_paths.values())).parent}")
        content = render_markdown(draft, daily_card_images=daily_card_images)
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
