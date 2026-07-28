#!/usr/bin/env python3
"""Generate Anxia-style short article drafts in one command."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
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


def render_markdown(draft: Draft) -> str:
    return f"---\ntitle: {draft.title}\n---\n\n{draft.body}\n"


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
    parser.add_argument("--daily", type=int, default=3, help="每天生成篇数，默认 3")
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
        content = render_markdown(draft)
        path = output_path(args.output_dir, draft)
        if args.dry_run:
            print(f"\n# {path.name}\n{content}")
            continue
        if path.exists() and not args.overwrite:
            print(f"草稿已存在，跳过：{path}", file=sys.stderr)
            skipped += 1
            batch_paths.append(path)
            continue
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
