#!/usr/bin/env python3
"""Generate an original twelve-sign weekly horoscope from reviewed event data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - exercised by the CLI preflight
    Image = ImageDraw = ImageFont = None  # type: ignore[assignment]


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_ARTICLE_DIR = BASE_DIR / "articles"
DEFAULT_ASSET_DIR = BASE_DIR / "assets" / "weekly_fortune"
DEFAULT_REVIEW_DIR = BASE_DIR / "reviews" / "weekly"
WEEKLY_SOURCE_DIR = Path(r"D:\自媒体\知识库\01-公众号文章\星座公众号文章\白桃星座\周运")
BRAND_QR_PATH = BASE_DIR / "assets" / "brand" / "xiaye_wechat_qr.jpg"
CARD_SIZE = (1080, 5600)
COVER_SIZE = (1800, 900)
FOLLOW_SIZE = (1800, 720)

SIGNS = (
    "白羊",
    "金牛",
    "双子",
    "巨蟹",
    "狮子",
    "处女",
    "天秤",
    "天蝎",
    "射手",
    "摩羯",
    "水瓶",
    "双鱼",
)
ELEMENT_GROUPS = (
    ("火象星座", ("白羊", "狮子", "射手"), (191, 76, 73), (251, 235, 224)),
    ("土象星座", ("金牛", "处女", "摩羯"), (55, 104, 82), (236, 239, 215)),
    ("风象星座", ("双子", "天秤", "水瓶"), (53, 102, 143), (226, 239, 244)),
    ("水象星座", ("巨蟹", "天蝎", "双鱼"), (34, 116, 121), (231, 238, 235)),
)
WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
VALID_FOCUS = {"overall", "work", "relationship", "finance", "health"}
CLOSING_PUNCTUATION = frozenset("，。！？；：、）》」】")
OPENING_PUNCTUATION = frozenset("（《「【")
CARD_BODY_FIELDS = ("overall", "single", "partnered", "study", "work", "finance", "health")
MIN_CARD_CJK = 900
MAX_CARD_CJK = 1400

SIGN_PROFILES = {
    "白羊": ("先推进再调整", "临时变动", "把结论说清楚"),
    "金牛": ("稳定落地", "资源分配", "先核对成本"),
    "双子": ("整理信息", "消息过载", "抓住有用线索"),
    "巨蟹": ("安顿内外节奏", "替别人多想", "先照顾实际需求"),
    "狮子": ("主动表达", "面子压力", "用成果说话"),
    "处女": ("梳理细节", "反复修改", "先完成关键步骤"),
    "天秤": ("重新平衡", "选择过多", "给决定设截止时间"),
    "天蝎": ("深入判断", "过度防备", "把核心诉求说出来"),
    "射手": ("拓展方向", "安排过满", "为重点留出时间"),
    "摩羯": ("稳步积累", "独自承担", "提前协调资源"),
    "水瓶": ("换个思路", "节奏跳跃", "先验证再扩大"),
    "双鱼": ("收回注意力", "情绪牵动", "用小行动确认方向"),
}

SIGN_DETAILS = {
    "白羊": {
        "social": "朋友聚会、临时协作或短途出行",
        "relationship": "回应是否直接、行动是否跟得上表达",
        "study": "三十分钟冲刺、模拟练习和即时订正",
        "work": "新任务启动、进度推进和跨部门协调",
        "money": "交通、数码产品与即时消费",
        "health": "睡眠、眼睛、头颈紧张和运动拉伤",
        "lucky": "把力气用在最值得推进的一件事上",
    },
    "金牛": {
        "social": "熟人介绍、固定圈子或稳定合作",
        "relationship": "价值观是否一致、相处是否有持续性",
        "study": "重复练习、知识归档和基础能力巩固",
        "work": "成本核对、资源分配和长期项目推进",
        "money": "续费、分摊、回款与品质型消费",
        "health": "咽喉、肩颈、睡眠质量和久坐疲劳",
        "lucky": "先核对成本，再决定投入多少",
    },
    "双子": {
        "social": "社交平台、同学同事或信息交换场合",
        "relationship": "沟通是否顺畅、彼此能否接住话题",
        "study": "资料筛选、口头表达和多科目切换",
        "work": "信息整理、会议沟通和临时任务衔接",
        "money": "课程、通讯、电子设备和出行支出",
        "health": "呼吸道、手腕、睡眠和注意力过载",
        "lucky": "把信息筛一遍，再给出明确回复",
    },
    "巨蟹": {
        "social": "家庭聚会、老朋友联系或熟悉的生活圈",
        "relationship": "对方能否理解情绪并给出实际照顾",
        "study": "安静环境、阶段复盘和错题整理",
        "work": "团队照应、内部协调和服务细节",
        "money": "家居、家人、人情往来与日常储备",
        "health": "肠胃、睡眠、情绪性进食和水肿",
        "lucky": "先安顿好自己的需要，再回应别人",
    },
    "狮子": {
        "social": "公开活动、兴趣聚会或需要展示的场合",
        "relationship": "欣赏是否真诚、彼此能否大方回应",
        "study": "成果展示、重点突破和带着目标练习",
        "work": "汇报表达、项目主导和团队士气",
        "money": "形象、娱乐、礼物和社交型消费",
        "health": "心肺、背部、作息和高温疲劳",
        "lucky": "用清楚的成果代替反复证明",
    },
    "处女": {
        "social": "工作学习场合、共同任务或专业交流",
        "relationship": "细节是否可靠、承诺能否按时兑现",
        "study": "错题复盘、步骤拆解和资料校对",
        "work": "流程优化、质量检查和问题收尾",
        "money": "日用品、健康管理、报销和服务续费",
        "health": "肠胃、神经紧张、肩颈和过度劳累",
        "lucky": "先完成关键步骤，再继续精修",
    },
    "天秤": {
        "social": "朋友邀约、合作会面或审美兴趣场合",
        "relationship": "交流是否平等、决定是否照顾双方",
        "study": "同伴讨论、观点比较和表达训练",
        "work": "合作协商、关系维护和方案取舍",
        "money": "社交、服饰、美学体验和共同支出",
        "health": "腰背、睡眠、饮水和久坐循环",
        "lucky": "给重要决定设一个明确截止时间",
    },
    "天蝎": {
        "social": "深度交流、小范围聚会或共同研究",
        "relationship": "信任是否经得起细节、边界是否清楚",
        "study": "难点攻克、资料深挖和独立研究",
        "work": "风险判断、资源整合和隐性问题排查",
        "money": "保险、税务、借贷、分成与共同资产",
        "health": "睡眠、泌尿系统、压力积累和炎症",
        "lucky": "把真正的诉求说出来，不用靠猜",
    },
    "射手": {
        "social": "旅行、课程、跨圈交流或户外活动",
        "relationship": "彼此是否坦率、未来方向是否兼容",
        "study": "框架搭建、跨学科学习和实践应用",
        "work": "新方向探索、外部合作和视野拓展",
        "money": "旅行、课程、运动和体验型消费",
        "health": "大腿、髋部、肝脏代谢和运动过量",
        "lucky": "为真正想去的方向留出时间",
    },
    "摩羯": {
        "social": "职场往来、行业活动或长期合作关系",
        "relationship": "计划能否落地、双方是否愿意承担责任",
        "study": "长期计划、证书准备和规律训练",
        "work": "目标拆解、责任协调和进度管理",
        "money": "储蓄、固定支出、长期投入和职业回报",
        "health": "骨骼、膝盖、牙齿和长期疲劳",
        "lucky": "提前协调资源，不必独自扛下全部",
    },
    "水瓶": {
        "social": "社群活动、线上讨论或新领域交流",
        "relationship": "想法是否同频、彼此能否尊重独立空间",
        "study": "新工具尝试、逻辑推演和跨界连接",
        "work": "系统改造、创意验证和团队共创",
        "money": "科技产品、社群订阅和新项目试水",
        "health": "小腿、脚踝、循环、睡眠和神经兴奋",
        "lucky": "先小范围验证，再扩大新的做法",
    },
    "双鱼": {
        "social": "艺术活动、朋友倾诉或轻松的兴趣场合",
        "relationship": "情绪能否被理解、表达是否足够真诚",
        "study": "图像记忆、安静沉浸和灵感整理",
        "work": "创意表达、服务支持和模糊任务澄清",
        "money": "线上娱乐、兴趣疗愈和替人垫付",
        "health": "足部、免疫、睡眠和情绪性疲劳",
        "lucky": "用一个小行动确认真实方向",
    },
}

FOCUS_ADVICE = {
    "overall": "这次变化更适合用来重排优先级，别在消息刚出现时就急着下结论。",
    "work": "工作上先确认任务边界、截止时间和交付标准，再决定要不要加码。",
    "relationship": "关系里少猜一步，把自己真正在意的部分说明白，会比等对方自己领会更有用。",
    "finance": "钱和资源的安排要落到数字，尤其留意回款、分摊、续费和临时支出。",
    "health": "身体状态需要稳定作息来托底，不要用连续熬夜去换短时间的进度。",
}


@dataclass(frozen=True)
class WeeklyEvent:
    day: date
    name: str
    summary: str
    detail: str
    focus: str
    affected_signs: tuple[str, ...]


@dataclass(frozen=True)
class WeeklyCard:
    sign: str
    keyword: str
    overview: str
    overall: str
    single: str
    partnered: str
    study: str
    work: str
    finance: str
    health: str
    action: str
    lucky: str


@dataclass(frozen=True)
class WeeklyDraft:
    week_start: date
    week_end: date
    title: str
    events: tuple[WeeklyEvent, ...]
    cards: tuple[WeeklyCard, ...]


def require_pillow() -> None:
    if Image is None or ImageDraw is None or ImageFont is None:
        raise RuntimeError(
            "缺少 Pillow；请使用项目 .venv 执行 "
            ".\\.venv\\Scripts\\python.exe -m pip install -r astrology_content/requirements-card-render.txt"
        )


def _parse_day(value: object, label: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{label} 必须是 YYYY-MM-DD") from exc


def load_weekly_events(path: Path) -> tuple[date, tuple[WeeklyEvent, ...], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("周事件文件必须是 JSON 对象")
    week_start = _parse_day(payload.get("week_start"), "week_start")
    if week_start.weekday() != 0:
        raise ValueError("week_start 必须是周一")
    source_note = str(payload.get("source_note", "")).strip()
    if len(source_note) < 8:
        raise ValueError("source_note 必须说明星象事件的复核来源")
    raw_events = payload.get("events")
    if not isinstance(raw_events, list) or not 2 <= len(raw_events) <= 7:
        raise ValueError("events 必须包含 2-7 个已复核事件")

    events: list[WeeklyEvent] = []
    for index, raw in enumerate(raw_events, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"events[{index}] 必须是对象")
        event_day = _parse_day(raw.get("date"), f"events[{index}].date")
        if not week_start <= event_day <= week_start + timedelta(days=6):
            raise ValueError(f"events[{index}].date 不在目标周")
        name = str(raw.get("name", "")).strip()
        summary = str(raw.get("summary", "")).strip()
        detail = str(raw.get("detail", "")).strip()
        focus = str(raw.get("focus", "overall")).strip()
        affected = tuple(str(sign).removesuffix("座").strip() for sign in raw.get("affected_signs", []))
        if not 2 <= len(name) <= 30:
            raise ValueError(f"events[{index}].name 需要 2-30 个字符")
        if len(summary) < 15 or len(detail) < 40:
            raise ValueError(f"events[{index}] 的 summary/detail 过短")
        if focus not in VALID_FOCUS:
            raise ValueError(f"events[{index}].focus 不支持：{focus}")
        if any(sign not in SIGNS for sign in affected):
            raise ValueError(f"events[{index}].affected_signs 包含未知星座")
        events.append(
            WeeklyEvent(
                day=event_day,
                name=name,
                summary=summary,
                detail=detail,
                focus=focus,
                affected_signs=affected,
            )
        )
    if len({(event.day, event.name) for event in events}) != len(events):
        raise ValueError("events 存在重复日期和名称")
    return week_start, tuple(sorted(events, key=lambda item: item.day)), source_note


def _date_range(start: date, end: date) -> str:
    return f"{start.month:02d}.{start.day:02d}-{end.month:02d}.{end.day:02d}"


def _event_for_sign(sign: str, events: tuple[WeeklyEvent, ...], sign_index: int) -> WeeklyEvent:
    direct = [event for event in events if sign in event.affected_signs]
    return (direct or list(events))[(sign_index + len(events)) % len(direct or events)]


def _event_for_focus(
    sign: str,
    events: tuple[WeeklyEvent, ...],
    focus: str,
    sign_index: int,
) -> WeeklyEvent:
    focused = [event for event in events if event.focus == focus]
    direct = [event for event in focused if sign in event.affected_signs]
    candidates = direct or focused or [event for event in events if sign in event.affected_signs] or list(events)
    return candidates[sign_index % len(candidates)]


def build_weekly_card(sign: str, week_start: date, events: tuple[WeeklyEvent, ...]) -> WeeklyCard:
    sign_index = SIGNS.index(sign)
    strength, risk, action = SIGN_PROFILES[sign]
    details = SIGN_DETAILS[sign]
    event = _event_for_sign(sign, events, sign_index)
    relationship_event = _event_for_focus(sign, events, "relationship", sign_index)
    work_event = _event_for_focus(sign, events, "work", sign_index)
    finance_event = _event_for_focus(sign, events, "finance", sign_index)
    health_event = _event_for_focus(sign, events, "health", sign_index)
    keywords = ("重排", "协调", "落地", "筛选", "表达", "收尾")
    keyword = keywords[(week_start.toordinal() + sign_index * 5) % len(keywords)]
    overview = f"{sign}座本周关键词：{keyword}。"
    event_label = f"{event.day.month}月{event.day.day}日的{event.name}"
    relationship_label = f"{relationship_event.day.month}月{relationship_event.day.day}日的{relationship_event.name}"
    work_label = f"{work_event.day.month}月{work_event.day.day}日的{work_event.name}"
    finance_label = f"{finance_event.day.month}月{finance_event.day.day}日的{finance_event.name}"
    health_label = f"{health_event.day.month}月{health_event.day.day}日的{health_event.name}"
    direct_note = "这是本周与你关联更直接的节点" if sign in event.affected_signs else "你可以把它当作调整节奏的参考节点"

    def choose(options: tuple[str, ...], offset: int = 0) -> str:
        return options[(sign_index + offset) % len(options)]

    overall = choose(
        (
            f"这一周，{sign}座最先感受到的是节奏重新排列。{details['work']}会把你推到更明确的位置，而{details['money']}也需要重新衡量。{event_label}是一个转折点，{direct_note}。{event.summary}机会往往藏在{details['social']}，真正要留意的是{risk}让你过早做决定。发挥{strength}的优势，把力气留给能够产生结果的事情。{FOCUS_ADVICE[event.focus]}",
            f"对{sign}座来说，本周不是一味加速，而是分清什么值得继续。你会在{details['work']}上看见新的空间，也可能因为{details['money']}重新调整计划。{event_label}前后，{direct_note}，{event.summary}别因为{risk}否定已有进展；你真正可靠的能力仍是{strength}。先把最关键的一步走稳，后面的答案会比现在更清楚。{FOCUS_ADVICE[event.focus]}",
            f"{sign}座这一周会慢慢发现，很多变化并不是来打乱你，而是在帮你重新选择。{event_label}值得重点留意，{direct_note}。{event.summary}工作机会更容易从{details['work']}里出现，人际助力则可能来自{details['social']}。当{risk}开始干扰判断时，回到事实和现实条件；{strength}会让你稳住局面。{FOCUS_ADVICE[event.focus]}",
            f"本周的{sign}座像是在给生活重新排序。{details['work']}需要你拿出判断力，{details['money']}则提醒你别忽略长期成本。{event_label}会带来较明显的感受，{direct_note}，{event.summary}你不需要一次解决所有问题，尤其别让{risk}消耗真正重要的精力。借助{strength}，把可控的部分先做好。{FOCUS_ADVICE[event.focus]}",
        )
    )
    single = choose(
        (
            f"单身的{sign}座，本周容易在{details['social']}遇到值得多聊几句的人。{relationship_label}让互动更看重真实回应，你会比平时更在意{details['relationship']}。别只用聊天热度判断关系，看看对方是否愿意安排见面、记得你的需求，也能在意见不同时保持尊重。旧人若重新出现，不妨先观察现实条件是否已经改变，再决定要不要把心门打开。",
            f"感情还在空窗期的{sign}座，这周并不缺认识新人的机会，尤其是在{details['social']}。随着{relationship_label}展开，你可能突然看清自己真正想要的是{details['relationship']}。有人靠近时，给彼此一点自然发展的空间，不用为了显得洒脱而隐藏好感，也别为了维持联系承担全部主动。让关系有来有往，才值得继续期待。",
            f"单身的{sign}座会比之前更愿意回应感情信号。{relationship_label}可能带来一场聊得投机的交流，场景多半与{details['social']}有关。心动没有问题，但你还需要确认{details['relationship']}。若对方的表达和行动总是错位，就不必替他补全理由；真正合适的人，会让你感到好奇，也让你保有安心。",
            f"对于单身的{sign}座，本周感情更像一次筛选。{relationship_label}把注意力带回{details['relationship']}，你会发现有趣和合适并不完全相同。新的缘分可能从{details['social']}开始，先从轻松相处中了解彼此，不急着追问结果。过去的关系若再次敲门，也要看对方带来了实际改变，还是只带来了熟悉感。",
        )
    )
    partnered = choose(
        (
            f"有伴的{sign}座，本周关系里的重点是把彼此真正需要的东西说出来。{relationship_label}适合讨论时间安排、共同支出和下一阶段计划。你看重{details['relationship']}，却可能因为怕破坏气氛而少说半句。小分歧出现时先别急着争结论，讲清事实和感受，会比猜测对方态度更有效。忙碌之余留一段专心相处的时间，关系会重新变得柔软。",
            f"已经有伴的{sign}座，这周会更关注两个人是否走在同一个节奏里。{relationship_label}可能让一件拖着没谈的小事再次出现，它未必是坏事，反而给了你们修正相处方式的机会。关于{details['relationship']}，不要默认对方自然会懂。把期待说得具体，也听听对方最近真正承受的压力，许多误会会在坦白之后慢慢松开。",
            f"有伴的{sign}座可能在本周感受到关系里的温度回升。{relationship_label}有利于约会、和解，也适合商量现实安排。你们之间需要确认的是{details['relationship']}，而不是谁在一次争执里更有道理。若工作挤压了相处时间，提前约定一个共同空档；哪怕只是认真吃顿饭，也比一边陪伴一边处理消息更有意义。",
            f"本周有伴的{sign}座需要在亲密与个人节奏之间找到平衡。{relationship_label}会让双方更愿意表达，但也容易因为一句话的分寸产生情绪。你期待{details['relationship']}，对方也有自己的顾虑。先确认彼此想解决的是同一件事，再讨论做法。愿意给出回应、也允许对方保留空间，关系反而更容易稳定下来。",
        ),
        1,
    )
    study = choose(
        (
            f"学习方面，{details['study']}会比盲目增加时长更有效。{work_label}前后容易被临时消息打断，最好提前留出一段完整时间处理核心任务。遇到卡点时，把问题拆成一个可以回答的步骤，再去请教老师或同伴。你已经掌握的内容需要通过练习固定下来；这一周不是比谁开启得多，而是看谁能把重点真正留下。",
            f"学生党和备考中的{sign}座，本周学习状态会经历先散后稳。尝试{details['study']}，把资料分成必须掌握、需要练习和以后补充三层。{work_label}会带来一点赶进度的压力，但不要因此跳过基础。一次完整复盘、一次认真订正，可能比多刷一套题更有价值。周末回看本周成果，你会发现积累并没有想象中那么慢。",
            f"本周的学习关键词是理解，而不是堆数量。{sign}座可以用{details['study']}找回专注，尤其在{work_label}前后，先关掉无关提醒再进入任务。若要准备考试、汇报或面试，把知识说出来、写出来，会比只在脑中默念更容易发现漏洞。对暂时没学会的部分保持耐心，你需要的是第二次练习，不是给自己贴标签。",
            f"学习上的{sign}座会遇到一次重新安排计划的机会。{work_label}可能改变原定进度，保住最重要的目标就好。采用{details['study']}，每天留下一个可检查的成果，能够减少忙了很久却没有实感的焦虑。有人分享资料时先筛选再收藏，真正适合自己的方法不必很多。稳稳完成这一周，你会更知道下一步该往哪里用力。",
        ),
        2,
    )
    work = choose(
        (
            f"工作方面，{work_label}会明显推动{details['work']}。机会可能表现为新任务、公开展示或一次关键协作，但它也会考验你能否说清优先级和资源需求。别因为想证明能力就把全部责任揽下，先确认截止时间、交付标准和负责人。需要争取支持时，拿出已经完成的结果；{action}，别人更容易看见你的专业度。",
            f"职场中的{sign}座，本周容易碰到计划临时调整。{work_label}让{details['work']}加快，你可能被推到更需要表态的位置。先别被催促带着走，弄清楚哪件事真正影响结果，再安排顺序。合作里及时留下文字记录，既是减少返工，也是保护彼此边界。新的机会并不遥远，它更可能出现在你把旧问题处理漂亮之后。",
            f"本周事业运的亮点来自{details['work']}。{work_label}前后，一条消息、一次会议或一个人的反馈可能改变原来的推进方式。对{sign}座而言，这是展示{strength}的窗口，但{risk}也可能让你过度消耗。该确认的条件别含糊，该拒绝的额外任务也不必硬接。把成果做得可见，后续的认可和资源会更容易跟上。",
            f"工作上的{sign}座正在进入一个需要取舍的阶段。{work_label}把{details['work']}推到台前，有些事情必须尽快回应，有些则可以重新排期。判断标准不是谁催得最急，而是哪项交付最接近核心目标。遇到不同意见时先对齐事实，不用把讨论变成输赢。你若能{action}，本周很可能收获一次更明确的信任。",
        ),
        3,
    )
    finance = choose(
        (
            f"财运方面，{finance_label}提醒你重新看待{details['money']}。本周有机会收回一笔拖延的款项、确认报销或找到更合适的费用方案，但临时优惠也会增加冲动。大额决定先算长期成本，不把尚未落地的收益提前花掉。涉及借用、合作和共同消费时，把金额与时间讲清楚，反而更能保护关系。",
            f"{sign}座本周的钱包需要的是秩序，不是过度克制。{finance_label}会让{details['money']}成为重点，有些支出确实值得，有些只是情绪带来的即时选择。先清理续费、分摊和待报销，再安排新的预算。若有人带来合作或投资信息，先核对规则与退出条件；看得懂、承受得起，才是属于你的机会。",
            f"本周财务上可能出现一进一出的情况。{finance_label}让{details['money']}更容易产生变动，已确认的收入可以跟进，临时人情和计划外消费则要留出余量。你不需要为了省小钱接受模糊条件，也别因为熟人推荐就跳过核实。把数字落到纸面之后，原本让人焦虑的问题会变得更容易处理。",
            f"财务方面，{sign}座会更在意钱是否花在真正重要的地方。{finance_label}适合处理{details['money']}，也可能带来一次重新谈价格或分工的机会。面对诱人的方案，给自己一个冷静期，再看使用频率、风险和后续成本。未到账的收益保持保守预期，手里留有机动空间，会让你接下来的选择更从容。",
        )
    )
    health = choose(
        (
            f"健康方面，{health_label}会放大身体对疲劳的反馈，{details['health']}需要多一点照顾。忙起来时尤其要守住吃饭、饮水和睡眠，不要把周末补觉当成长期方案。运动以舒展和恢复为主，避免情绪上来后突然加量。身体不是在拖慢你，它只是提醒你重新分配精力；若不适持续，及时寻求专业帮助。",
            f"本周身体状态与情绪节奏联系得很紧。{health_label}前后，{sign}座要留意{details['health']}，连续盯屏幕或久坐时安排几次短暂活动。晚上减少密集信息，让大脑有一个真正结束工作的信号。无需追求一次完美作息，从今天早睡一点、规律吃一餐开始，恢复会比想象中更快。持续不适仍应咨询专业人士。",
            f"健康运提醒{sign}座别忽略那些看似很小的疲惫。{health_label}可能让{details['health']}更敏感，行程过密时给自己留一点缓冲。温和运动、规律饮食和减少熬夜比临时突击更有效。情绪紧绷时先离开屏幕、走动或做几次深呼吸。你不必靠硬撑证明状态良好，及时休息本身也是在保护进度。",
            f"这周适合把照顾身体放回日程，而不是等忙完再说。{health_label}提示{sign}座关注{details['health']}，尤其避免长时间保持同一姿势。工作与学习间隙做一点伸展，睡前给信息输入设下边界。若最近已经明显疲惫，就降低运动强度和无必要应酬。慢下来并不会耽误事情，反而能让你更稳定地完成它。",
        ),
        1,
    )

    return WeeklyCard(
        sign=sign,
        keyword=keyword,
        overview=overview,
        overall=overall,
        single=single,
        partnered=partnered,
        study=study,
        work=work,
        finance=finance,
        health=health,
        action=action,
        lucky=details["lucky"],
    )


def build_weekly_draft(week_start: date, events: tuple[WeeklyEvent, ...]) -> WeeklyDraft:
    week_end = week_start + timedelta(days=6)
    title = f"夏野星运｜十二星座一周运势（{_date_range(week_start, week_end)}）"
    cards = tuple(build_weekly_card(sign, week_start, events) for sign in SIGNS)
    for card in cards:
        body = "".join(str(getattr(card, field)) for field in CARD_BODY_FIELDS)
        cjk_count = sum("\u4e00" <= char <= "\u9fff" for char in body)
        if not MIN_CARD_CJK <= cjk_count <= MAX_CARD_CJK:
            raise RuntimeError(
                f"{card.sign}座周运卡正文为 {cjk_count} 个中文字符，"
                f"要求 {MIN_CARD_CJK}-{MAX_CARD_CJK}"
            )
    return WeeklyDraft(week_start, week_end, title, events, cards)


def _font(size: int, *, bold: bool = False) -> Any:
    require_pillow()
    candidates = (
        ("C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc")
        if bold
        else ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf")
    )
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _wrap(text: str, font: Any, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if current and font.getlength(candidate) > max_width:
            if char in CLOSING_PUNCTUATION:
                lines.append(candidate)
                current = ""
            elif current[-1] in OPENING_PUNCTUATION and len(current) > 1:
                lines.append(current[:-1])
                current = current[-1] + char
            else:
                lines.append(current)
                current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _palette_for_sign(sign: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    for _, signs, primary, soft in ELEMENT_GROUPS:
        if sign in signs:
            return primary, soft
    raise ValueError(sign)


def _draw_wrapped(
    draw: Any,
    text: str,
    *,
    xy: tuple[int, int],
    font: Any,
    fill: tuple[int, int, int],
    width: int,
    line_height: int,
) -> int:
    x, y = xy
    for line in _wrap(text, font, width):
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def _load_brand_qr(size: int) -> Any:
    require_pillow()
    if not BRAND_QR_PATH.is_file():
        raise FileNotFoundError(f"缺少公众号二维码：{BRAND_QR_PATH}")
    with Image.open(BRAND_QR_PATH) as source:
        return source.convert("RGB").resize((size, size), Image.Resampling.NEAREST)


def _draw_xiaye_mark(
    draw: Any,
    center: tuple[int, int],
    size: int,
    *,
    fill: tuple[int, int, int],
    core: tuple[int, int, int],
) -> None:
    x, y = center
    inner = max(8, size // 4)
    draw.ellipse((x - size, y - size, x + size, y + size), outline=fill, width=max(3, size // 12))
    draw.polygon(
        (
            (x, y - size),
            (x + inner, y - inner),
            (x + size, y),
            (x + inner, y + inner),
            (x, y + size),
            (x - inner, y + inner),
            (x - size, y),
            (x - inner, y - inner),
        ),
        fill=fill,
    )
    draw.ellipse((x - inner, y - inner, x + inner, y + inner), fill=core)


def render_weekly_card(card: WeeklyCard, draft: WeeklyDraft, output: Path) -> None:
    require_pillow()
    primary, soft = _palette_for_sign(card.sign)
    image = Image.new("RGB", CARD_SIZE, (250, 250, 247))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, CARD_SIZE[0], 555), fill=primary)
    draw.rectangle((0, 555, CARD_SIZE[0], 690), fill=soft)
    draw.text((82, 62), "夏野星座 · WEEKLY", font=_font(30, bold=True), fill=(245, 245, 240))
    _draw_xiaye_mark(draw, (930, 135), 44, fill=(255, 255, 255), core=soft)
    draw.text((82, 150), f"{card.sign}座", font=_font(96, bold=True), fill=(255, 255, 255))
    draw.text(
        (82, 310),
        f"{_date_range(draft.week_start, draft.week_end)}  每周运势",
        font=_font(38),
        fill=(245, 245, 240),
    )
    draw.text((82, 585), card.overview, font=_font(42, bold=True), fill=primary)

    body_font = _font(34)
    heading_font = _font(38, bold=True)
    y = 790
    sections = (
        ("整体节奏", card.overall),
        ("单身感情", card.single),
        ("有伴感情", card.partnered),
        ("学习运势", card.study),
        ("工作运势", card.work),
        ("财运提醒", card.finance),
        ("健康提醒", card.health),
    )
    for heading, content in sections:
        draw.rounded_rectangle((68, y - 10, 292, y + 57), radius=8, fill=soft)
        draw.text((96, y), heading, font=heading_font, fill=primary)
        y += 84
        y = _draw_wrapped(
            draw,
            content,
            xy=(96, y),
            font=body_font,
            fill=(47, 55, 58),
            width=888,
            line_height=55,
        )
        y += 58
    if y > 4740:
        raise RuntimeError(f"{card.sign}座周运卡文字超出安全区：{y}")
    draw.line((90, 4800, 990, 4800), fill=primary, width=3)
    draw.text((90, 4840), f"本周好运口号：{card.lucky}", font=_font(38, bold=True), fill=primary)

    draw.rectangle((0, 5000, CARD_SIZE[0], CARD_SIZE[1]), fill=primary)
    draw.text(
        (CARD_SIZE[0] // 2, 5060),
        "关注夏野星座，查看每日好运与每周运势",
        font=_font(31, bold=True),
        fill=(255, 255, 255),
        anchor="mm",
    )
    qr_size = 280
    qr_x = (CARD_SIZE[0] - qr_size) // 2
    qr_y = 5140
    draw.rounded_rectangle((qr_x - 18, qr_y - 18, qr_x + qr_size + 18, qr_y + qr_size + 18), radius=8, fill=(255, 255, 255))
    image.paste(_load_brand_qr(qr_size), (qr_x, qr_y))
    draw.text(
        (CARD_SIZE[0] // 2, 5485),
        "长按识别二维码  ·  @夏野星座",
        font=_font(28),
        fill=(245, 245, 240),
        anchor="mm",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)


def render_weekly_cover(draft: WeeklyDraft, output: Path) -> None:
    require_pillow()
    image = Image.new("RGB", COVER_SIZE, (244, 242, 235))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 500, COVER_SIZE[1]), fill=(44, 94, 112))
    draw.rectangle((500, 0, 535, COVER_SIZE[1]), fill=(203, 86, 75))
    _draw_xiaye_mark(draw, (395, 105), 42, fill=(255, 255, 255), core=(203, 86, 75))
    draw.text((110, 118), "夏野", font=_font(92, bold=True), fill=(255, 255, 255))
    draw.text((110, 258), "WEEKLY", font=_font(43, bold=True), fill=(236, 222, 180))
    draw.text((650, 150), "十二星座", font=_font(78, bold=True), fill=(38, 55, 61))
    draw.text((650, 280), "一周运势", font=_font(116, bold=True), fill=(44, 94, 112))
    draw.text(
        (655, 470),
        _date_range(draft.week_start, draft.week_end),
        font=_font(58, bold=True),
        fill=(203, 86, 75),
    )
    draw.line((655, 570, 1610, 570), fill=(38, 55, 61), width=3)
    draw.text((655, 625), "参考太阳星座与上升星座", font=_font(36), fill=(70, 78, 80))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)


def render_weekly_follow(output: Path) -> None:
    require_pillow()
    image = Image.new("RGB", FOLLOW_SIZE, (235, 241, 231))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 42, FOLLOW_SIZE[1]), fill=(203, 86, 75))
    draw.rectangle((42, 0, 480, FOLLOW_SIZE[1]), fill=(44, 94, 112))
    _draw_xiaye_mark(draw, (380, 120), 40, fill=(255, 255, 255), core=(203, 86, 75))
    draw.text((125, 170), "夏野", font=_font(94, bold=True), fill=(255, 255, 255))
    draw.text((555, 120), "运势早知晓，节奏心中有数", font=_font(55, bold=True), fill=(38, 55, 61))
    draw.text((555, 255), "关注夏野星座", font=_font(48, bold=True), fill=(203, 86, 75))
    draw.text((555, 365), "每日好运 · 每周运势 · 单星座提醒", font=_font(32), fill=(70, 78, 80))
    qr_size = 330
    qr_x, qr_y = 1390, 170
    draw.rounded_rectangle((qr_x - 18, qr_y - 18, qr_x + qr_size + 18, qr_y + qr_size + 18), radius=8, fill=(255, 255, 255))
    image.paste(_load_brand_qr(qr_size), (qr_x, qr_y))
    draw.text((1555, 555), "长按识别二维码", font=_font(28), fill=(70, 78, 80), anchor="mm")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)


def article_path(article_dir: Path, draft: WeeklyDraft) -> Path:
    date_range = _date_range(draft.week_start, draft.week_end).replace(".", "-")
    return article_dir / f"{draft.week_start:%Y%m%d}_05_十二星座一周运势丨{date_range}.md"


def render_markdown(draft: WeeklyDraft, *, article_dir: Path, asset_dir: Path) -> str:
    week_key = draft.week_start.strftime("%Y%m%d")
    week_assets = asset_dir / week_key

    def ref(path: Path) -> str:
        return os.path.relpath(path, start=article_dir).replace("\\", "/")

    lines = [
        "---",
        f'title: "{draft.title}"',
        "---",
        "",
        f"![夏野周运封面]({ref(week_assets / '夏野周运.png')})",
        "",
        "新的一周，先看清哪些日子适合推进，哪些日子更需要留出余地。下面的内容可结合太阳星座和上升星座阅读。",
        "",
        "## 本周星象日历",
        "",
    ]
    for event in draft.events:
        lines.extend(
            (
                f"**{event.day.month}月{event.day.day}日 {WEEKDAYS[event.day.weekday()]}｜{event.name}**",
                "",
                event.summary,
                "",
            )
        )
    lines.extend(("先记住和自己当前计划最相关的一两个节点，不必把每一条都当成确定结果。", ""))

    cards_by_sign = {card.sign: card for card in draft.cards}
    for group_name, signs, _, _ in ELEMENT_GROUPS:
        for sign in signs:
            if sign not in cards_by_sign:
                raise RuntimeError(f"缺少{sign}座周运卡")
        headings = " | ".join(f"{sign}座" for sign in signs)
        separators = " | ".join(":---:" for _ in signs)
        images = " | ".join(
            f"![{sign}座一周运势]({ref(week_assets / 'cards' / f'{sign}座.png')})"
            for sign in signs
        )
        lines.extend(
            (
                f"## {group_name}",
                "",
                "**点击查看大图**",
                "",
                f"| {headings} |",
                f"| {separators} |",
                f"| {images} |",
                "",
            )
        )

    impact_counts = {sign: 0 for sign in SIGNS}
    for event in draft.events:
        for sign in event.affected_signs:
            impact_counts[sign] += 1
    ranked_signs = sorted(SIGNS, key=lambda sign: (-impact_counts[sign], SIGNS.index(sign)))
    focus_signs = [sign for sign in ranked_signs if impact_counts[sign] > 0][:4]
    focus_text = "、".join(f"{sign}座" for sign in focus_signs)
    date_text = "、".join(f"{event.day.month}月{event.day.day}日" for event in draft.events)

    lines.extend(
        (
            "## 重点日期展开",
            "",
            f"本周相对更值得留意的是{focus_text}；关键节点集中在{date_text}。先看与自己现实计划最相关的部分，不需要把所有提示同时套在身上。",
            "",
        )
    )
    for event in draft.events:
        affected = "、".join(f"{sign}座" for sign in event.affected_signs)
        suffix = f"相对更值得留意的是{affected}。" if affected else "所有星座都可按自己的实际安排参考。"
        lines.extend(
            (
                f"**{WEEKDAYS[event.day.weekday()]}｜{event.name}**",
                "",
                f"{event.detail}{suffix}",
                "",
            )
        )
    lines.extend(
        (
            "星座运势是娱乐化的自我观察视角，不替代对工作、财务、关系和健康问题的专业判断。",
            "",
            f"![夏野星座关注指引]({ref(week_assets / '关注指引.png')})",
            "",
        )
    )
    return "\n".join(lines)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_weekly_package(
    draft: WeeklyDraft,
    *,
    article_dir: Path = DEFAULT_ARTICLE_DIR,
    asset_dir: Path = DEFAULT_ASSET_DIR,
    review_dir: Path = DEFAULT_REVIEW_DIR,
    source_note: str,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    article_dir.mkdir(parents=True, exist_ok=True)
    week_key = draft.week_start.strftime("%Y%m%d")
    week_assets = asset_dir / week_key
    output_article = article_path(article_dir, draft)
    output_review = review_dir / f"{output_article.stem}.json"
    expected = [
        output_article,
        output_review,
        week_assets / "夏野周运.png",
        week_assets / "关注指引.png",
        *(week_assets / "cards" / f"{sign}座.png" for sign in SIGNS),
    ]
    existing = [path for path in expected if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(f"目标已存在，使用 --overwrite 重写：{existing[0]}")

    render_weekly_cover(draft, week_assets / "夏野周运.png")
    render_weekly_follow(week_assets / "关注指引.png")
    for card in draft.cards:
        render_weekly_card(card, draft, week_assets / "cards" / f"{card.sign}座.png")
    output_article.write_text(
        render_markdown(draft, article_dir=article_dir, asset_dir=asset_dir),
        encoding="utf-8",
    )

    review_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "article": str(output_article.resolve()),
        "article_sha256": _sha256(output_article),
        "benchmark": "白桃星座周运栏目的高层结构，不复用原句和卡片版式",
        "source_corpus": str(WEEKLY_SOURCE_DIR),
        "event_source_note": source_note,
        "week_start": draft.week_start.isoformat(),
        "week_end": draft.week_end.isoformat(),
        "events": [asdict(event) | {"day": event.day.isoformat()} for event in draft.events],
        "cards": [asdict(card) for card in draft.cards],
        "assets": {
            str(path.relative_to(asset_dir.parent)).replace("\\", "/"): _sha256(path)
            for path in expected[2:]
        },
    }
    output_review.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_article, output_review


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成原创十二星座每周运势和 12 张长图卡")
    parser.add_argument("--events-file", type=Path, required=True, help="已人工复核的周星象 JSON")
    parser.add_argument("--article-dir", type=Path, default=DEFAULT_ARTICLE_DIR)
    parser.add_argument("--asset-dir", type=Path, default=DEFAULT_ASSET_DIR)
    parser.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        week_start, events, source_note = load_weekly_events(args.events_file)
        draft = build_weekly_draft(week_start, events)
        output_article, output_review = write_weekly_package(
            draft,
            article_dir=args.article_dir,
            asset_dir=args.asset_dir,
            review_dir=args.review_dir,
            source_note=source_note,
            overwrite=args.overwrite,
        )
    except (FileNotFoundError, FileExistsError, json.JSONDecodeError, RuntimeError, ValueError) as exc:
        print(f"生成失败：{exc}")
        return 1
    print(f"周运文章：{output_article}")
    print(f"复核记录：{output_review}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
