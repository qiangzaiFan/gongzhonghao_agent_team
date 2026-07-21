#!/usr/bin/env python3
"""Score similarity to the project's abstract viral-astrology style profile.

The score measures reusable editorial characteristics, not copied wording.
Text overlap is reported separately when a source file is supplied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from quality_gate import (
    cjk_len,
    markdown_to_plain,
    parse_article,
    shingle_overlap,
)


STYLE_PASS_SCORE = 75
DEFAULT_PROFILE = Path(__file__).parent / "specs" / "benchmark_style.md"
SIGN_TERMS = (
    "星座",
    "水象",
    "火象",
    "土象",
    "风象",
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
TITLE_TENSION_TERMS = (
    "回头",
    "放下",
    "还爱",
    "变心",
    "错过",
    "试探",
    "误解",
    "真正",
    "为什么",
    "怎么",
    "需要",
    "关卡",
    "治愈",
    "包容",
)
JUDGMENT_MARKERS = (
    "被理解成",
    "常常被",
    "经常被",
    "这个判断",
    "更准确",
    "事实上",
    "其实",
    "不只是",
    "往往",
    "容易",
)
MECHANISM_TERMS = (
    "因为",
    "所以",
    "本质",
    "意味",
    "安全感",
    "信任",
    "控制",
    "习惯",
    "需要",
    "想象",
    "依赖",
    "判断",
    "细节",
    "表现",
    "反差",
    "矛盾",
    "关系",
)
RELATION_BEHAVIORS = (
    "消息",
    "聊天框",
    "沉默",
    "回头",
    "分手",
    "复合",
    "联系",
    "靠近",
    "撤退",
    "试探",
    "承诺",
    "约定",
    "争执",
    "冷淡",
    "投入",
)
STORY_MARKERS = (
    r"那天(?:晚上)?",
    r"第二天",
    r"一个月后",
    r"我的朋友",
    r"读者给我留言",
    r"咨询者",
    r"小[A-Z]",
    r"[苏林陈李王张]遥",
)
ENGAGEMENT_TERMS = ("点赞", "转发", "关注我", "留言区", "评论区")


@dataclass
class StyleScore:
    total: int
    dimensions: dict[str, int]
    notes: list[str]
    text_overlap: float | None = None


def _count_terms(text: str, terms: tuple[str, ...]) -> int:
    return sum(text.count(term) for term in terms)


def score_article(article_path: Path, source_text: str | None = None) -> StyleScore:
    article = parse_article(article_path)
    plain = markdown_to_plain(article.body)
    opening = plain[:180]
    ending = plain[-240:]
    notes: list[str] = []
    dimensions: dict[str, int] = {}

    # 15: title immediately identifies the reader/sign group and one tension.
    title_identity = 8 if any(term in article.title for term in SIGN_TERMS) else 0
    title_tension = 5 if any(term in article.title for term in TITLE_TENSION_TERMS) else 0
    title_question = 2 if "？" in article.title or "?" in article.title else 0
    dimensions["标题代入"] = title_identity + title_tension + title_question
    if dimensions["标题代入"] < 10:
        notes.append("标题需要更明确的星座身份和关系矛盾")

    # 15: opening behaves like commentary: misconception + new judgment.
    opening_sign = 5 if any(term in opening for term in SIGN_TERMS) else 0
    judgment_hits = _count_terms(opening, JUDGMENT_MARKERS)
    opening_judgment = min(8, judgment_hits * 4)
    opening_behavior = 2 if any(term in opening for term in RELATION_BEHAVIORS) else 0
    dimensions["开头判断"] = opening_sign + opening_judgment + opening_behavior
    if dimensions["开头判断"] < 10:
        notes.append("前两段还不够像“误解 + 新判断”的星座评论开头")

    # 20: prefer analytical commentary and penalize full narrative scaffolding.
    story_hits = sum(len(re.findall(pattern, plain)) for pattern in STORY_MARKERS)
    dialogue_hits = len(re.findall(r"[“「][^”」\n]{4,60}[”」]", plain))
    commentary_score = max(0, 20 - story_hits * 4 - max(0, dialogue_hits - 3) * 2)
    dimensions["评论而非故事"] = commentary_score
    if commentary_score < 16:
        notes.append("叙事人物或时间线偏多，需改成星座机制评论")

    # 20: mechanism explanations plus observable relationship behaviors.
    mechanism_hits = _count_terms(plain, MECHANISM_TERMS)
    behavior_hits = _count_terms(plain, RELATION_BEHAVIORS)
    dimensions["机制与关系表现"] = min(12, mechanism_hits) + min(8, behavior_hits)
    if dimensions["机制与关系表现"] < 14:
        notes.append("性格机制或关系行为密度偏低")

    # 10: multiple signs need genuine differentiation; single-sign pieces get full credit via depth.
    named_signs = [term for term in SIGN_TERMS[5:] if term in plain]
    unique_signs = len(set(named_signs))
    if unique_signs >= 3:
        differentiation = 10
    elif unique_signs == 2:
        differentiation = 8
    elif unique_signs == 1:
        differentiation = 7 if mechanism_hits >= 8 else 5
    else:
        differentiation = 0
    dimensions["星座差异"] = differentiation
    if differentiation < 7:
        notes.append("没有建立清晰的单星座深度或多星座差异")

    # 10: mobile structure with 2-4 headings and non-fragmented paragraphs.
    heading_count = len(re.findall(r"(?m)^##\s+\S", article.body))
    paragraphs = [part for part in re.split(r"\n\s*\n", article.body) if cjk_len(part) >= 20]
    tiny_paragraphs = sum(1 for part in paragraphs if cjk_len(part) < 35)
    structure = 6 if 2 <= heading_count <= 4 else 2
    structure += 4 if len(paragraphs) >= 7 and tiny_paragraphs <= len(paragraphs) // 2 else 2
    dimensions["手机阅读节奏"] = structure

    # 10: close by distinguishing the original question, not engagement bait.
    closing = 0
    if any(term in ending for term in ("分清", "区分", "究竟", "哪一", "是还", "还是")):
        closing += 6
    if "？" in ending or "?" in ending:
        closing += 2
    if not any(term in ending for term in ENGAGEMENT_TERMS):
        closing += 2
    dimensions["结尾收束"] = closing
    if closing < 7:
        notes.append("结尾需回到开头的核心区分，减少泛化升华")

    total = sum(dimensions.values())
    overlap = shingle_overlap(source_text, article.body) if source_text is not None else None
    return StyleScore(total=total, dimensions=dimensions, notes=notes, text_overlap=overlap)


def format_score(score: StyleScore) -> str:
    lines = [f"爆款星座风格相似度：{score.total}/100"]
    lines.extend(f"- {name}: {value}" for name, value in score.dimensions.items())
    if score.text_overlap is not None:
        lines.append(f"正文 18 字分片重合率：{score.text_overlap:.2%}")
    if score.notes:
        lines.append("可改进项：")
        lines.extend(f"- {note}" for note in score.notes)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="评估文章与爆款星座样本风格画像的相似度")
    parser.add_argument("article", type=Path)
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE,
        help="用于记录评分口径的抽象风格画像",
    )
    parser.add_argument("--source-file", type=Path, help="可选：同时报告与某篇来源的文字重合率")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not args.article.is_file():
        parser.error(f"文章不存在：{args.article}")
    if not args.profile.is_file():
        parser.error(f"风格画像不存在：{args.profile}")
    source_text = None
    if args.source_file:
        if not args.source_file.is_file():
            parser.error(f"来源文件不存在：{args.source_file}")
        source_text = args.source_file.read_text(encoding="utf-8", errors="ignore")
    score = score_article(args.article, source_text=source_text)
    print(format_score(score))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(
                {
                    "profile": str(args.profile.resolve()),
                    "profile_sha256": hashlib.sha256(args.profile.read_bytes()).hexdigest(),
                    "source_file": str(args.source_file.resolve()) if args.source_file else None,
                    "source_sha256": (
                        hashlib.sha256(args.source_file.read_bytes()).hexdigest()
                        if args.source_file
                        else None
                    ),
                    "style_similarity": score.total,
                    "dimensions": score.dimensions,
                    "notes": score.notes,
                    "text_overlap": score.text_overlap,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0 if score.total >= STYLE_PASS_SCORE else 1


if __name__ == "__main__":
    raise SystemExit(main())
