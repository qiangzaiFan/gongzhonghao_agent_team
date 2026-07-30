#!/usr/bin/env python3
"""Plan three non-repeating original illustration briefs for an article."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
ARTICLES_DIR = BASE_DIR / "articles"
IMAGE_DIR = BASE_DIR / "images" / "illustrations"
PROMPT_DIR = IMAGE_DIR / "prompts"
SOURCE_DIR = IMAGE_DIR / "sources"
MANIFEST_PATH = BASE_DIR / "data" / "illustration_manifest.json"


SCENE_LIBRARY: dict[str, dict[str, list[dict[str, str]]]] = {
    "body_restart": {
        "opening": [
            {
                "key": "bedside-medicine-water",
                "summary": "床头药盒和温水旁，一只淡金色小鹤安静坐着",
                "scene": "a small pale-gold crane mascot sitting quietly beside a bedside table with a medicine box, a glass of warm water, and a softly glowing lamp",
            },
            {
                "key": "medical-report-glasses",
                "summary": "体检单、老花镜和半杯温水放在米白桌面上",
                "scene": "a medical checkup report, reading glasses, and a half glass of warm water on a simple off-white table, no readable text on the paper",
            },
        ],
        "conflict": [
            {
                "key": "phone-rice-bowl-tired",
                "summary": "亮起的手机旁放着没吃完的饭，情绪有点堵",
                "scene": "a glowing phone beside an unfinished bowl of rice and a small medicine packet, a quiet feeling of being interrupted and tired",
            },
            {
                "key": "crane-carrying-threads",
                "summary": "小鹤背着几根松开的线，正在慢慢放下",
                "scene": "a pale-gold crane mascot gently putting down loose tangled threads from its back, symbolizing letting go of burdens",
            },
        ],
        "closing": [
            {
                "key": "lights-off-warm-water",
                "summary": "睡前关灯，床头只留一杯温水",
                "scene": "a calm bedroom corner before sleep, the light just turned off, a cup of warm water on the bedside table, peaceful and safe",
            },
            {
                "key": "hot-noodle-phone-face-down",
                "summary": "一碗热面冒着气，手机扣在桌上",
                "scene": "a steaming bowl of plain warm noodles on a kitchen table, a phone placed face down beside it, soft morning light",
            },
        ],
    },
    "children_boundary": {
        "opening": [
            {
                "key": "short-phone-call-kitchen",
                "summary": "厨房小灯下，手机刚挂断，饭碗还放在桌上",
                "scene": "under a small kitchen lamp, a phone call has just ended, a simple rice bowl sits on the table, quiet and slightly empty",
            },
            {
                "key": "door-key-parent-pause",
                "summary": "门口的钥匙和布包，老人没有急着出门",
                "scene": "a house key and a cloth bag by the doorway, suggesting an older parent pausing before rushing out to help",
            },
        ],
        "conflict": [
            {
                "key": "bank-card-medicine-bowl",
                "summary": "银行卡、药盒和饭碗放在同一张桌上",
                "scene": "a bank card, a medicine box, and a warm rice bowl arranged on the same modest table, symbolizing money, health, and daily life",
            },
            {
                "key": "crane-holding-key-card",
                "summary": "小鹤一手拿钥匙，一手护着银行卡",
                "scene": "a pale-gold crane mascot calmly holding a house key and protecting a small bank card close to its chest",
            },
        ],
        "closing": [
            {
                "key": "phone-on-table-warm-dinner",
                "summary": "手机放桌边，一顿简单晚饭还热着",
                "scene": "a phone resting quietly at the edge of a table while a simple warm dinner is still steaming, peaceful boundary",
            },
            {
                "key": "crane-walking-under-streetlamp",
                "summary": "小鹤在楼下路灯旁慢慢散步",
                "scene": "a pale-gold crane mascot walking slowly under a neighborhood streetlamp beside a quiet river path",
            },
        ],
    },
    "money_security": {
        "opening": [
            {
                "key": "pension-message-teacup",
                "summary": "退休金到账短信、茶杯和老花镜",
                "scene": "a phone showing an unreadable pension deposit notification, a teacup, and reading glasses on textured paper-like table",
            }
        ],
        "conflict": [
            {
                "key": "wallet-medicine-taxi",
                "summary": "钱包、药费单和一张打车小票",
                "scene": "a small wallet, a medicine receipt without readable text, and a taxi receipt on a calm table",
            }
        ],
        "closing": [
            {
                "key": "crane-small-purse-window",
                "summary": "小鹤把小钱包放在窗边，阳光照进来",
                "scene": "a pale-gold crane mascot placing a small purse by a sunny window, gentle and secure",
            }
        ],
    },
    "emotion_health": {
        "opening": [
            {
                "key": "awake-at-night-ceiling",
                "summary": "夜里醒来，床头灯很低，心里有事",
                "scene": "a quiet night bedroom, a low bedside lamp, a blanket slightly open, conveying waking up with thoughts",
            }
        ],
        "conflict": [
            {
                "key": "tangled-thread-teacup",
                "summary": "茶杯旁一团线慢慢松开",
                "scene": "a teacup beside a tangled ball of thread slowly loosening, symbolic but simple",
            }
        ],
        "closing": [
            {
                "key": "wash-face-towel",
                "summary": "洗手台旁一条干净毛巾，像把情绪放下",
                "scene": "a clean towel beside a washbasin, soft light, suggesting washing the face and letting emotions settle",
            }
        ],
    },
    "solitude_self_rescue": {
        "opening": [
            {
                "key": "one-person-table-lamp",
                "summary": "一个人的饭桌，灯光很暖",
                "scene": "a one-person dinner table with a warm lamp, a rice bowl, chopsticks, and a quiet chair",
            }
        ],
        "conflict": [
            {
                "key": "empty-chair-plant",
                "summary": "空椅子旁有一盆小绿植，不冷清",
                "scene": "an empty chair beside a small green plant, calm solitude rather than loneliness",
            }
        ],
        "closing": [
            {
                "key": "sunny-window-breakfast",
                "summary": "清晨窗边，一碗热粥和阳光",
                "scene": "a bowl of warm porridge by a sunny morning window, simple and peaceful",
            }
        ],
    },
}

PILLAR_KEYWORDS = [
    ("children_boundary", ["孩子", "子女", "儿女", "父母", "电话", "帮忙"]),
    ("money_security", ["钱", "退休金", "存款", "银行卡", "住院费"]),
    ("body_restart", ["身体", "生病", "病", "药", "医院", "体检", "睡"]),
    ("emotion_health", ["情绪", "生气", "内耗", "堵心", "委屈"]),
    ("solitude_self_rescue", ["独处", "一个人", "清净", "自渡"]),
]

QUOTE_LIBRARY: dict[str, dict[str, list[str]]] = {
    "body_restart": {
        "opening": ["后半生别再\n把身体借给别人", "身体撑不住时\n先把自己收回来"],
        "conflict": ["别把命\n用在不值得的人和事上", "身体是晚年\n最大的本钱"],
        "closing": ["今晚早点关灯\n把命放回自己手里", "先吃饭先睡觉\n日子才会慢慢稳"],
    },
    "children_boundary": {
        "opening": ["孩子再忙\n你也要留条退路", "爱孩子\n也要有分寸"],
        "conflict": ["钱和身体\n都要留在自己手里", "帮孩子之前\n先看看自己的退路"],
        "closing": ["爱还在\n日子要先稳住自己", "孩子有路\n你也要过好自己"],
    },
    "money_security": {
        "opening": ["晚年的底气\n藏在手里的钱里", "钱不是贪心\n是晚年的退路"],
        "conflict": ["看清一个人\n有时要谈钱", "该留的钱\n别轻易拿出去"],
        "closing": ["守住选择权\n心里才安稳", "钱留一点\n日子就稳一点"],
    },
    "emotion_health": {
        "opening": ["最伤身体的\n是长期生闷气", "别人的脸色\n别放进自己心里"],
        "conflict": ["情绪堵久了\n身体会提醒你", "少争一口气\n多睡一个好觉"],
        "closing": ["洗把脸睡一觉\n心就慢慢松了", "少想一点\n今晚先好好睡"],
    },
    "solitude_self_rescue": {
        "opening": ["一个人吃饭\n也能把日子过暖", "清净不是孤独\n是把心收回来"],
        "conflict": ["朋友圈变小\n日子反而安静", "不合群没关系\n别委屈自己"],
        "closing": ["把饭吃热\n把心放稳", "一个人也要\n好好过日子"],
    },
}


def read_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "assignments": []}
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(manifest: dict[str, Any], path: Path = MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extract_article(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    title_match = re.search(r"(?m)^title:\s*['\"]?(.+?)['\"]?\s*$", text)
    title = title_match.group(1).strip() if title_match else path.stem
    body = re.sub(r"(?s)^---\n.*?\n---\n", "", text).strip()
    return title, body


def infer_pillar(title: str, body: str) -> str:
    haystack = f"{title}\n{body[:1200]}"
    scores: dict[str, int] = {}
    for pillar, keywords in PILLAR_KEYWORDS:
        scores[pillar] = sum(haystack.count(keyword) for keyword in keywords)
    best = max(scores, key=scores.get)
    return best if scores[best] else "body_restart"


def short_slug(text: str, fallback: str) -> str:
    mapping = {
        "身体": "body",
        "生病": "illness",
        "孩子": "children",
        "子女": "children",
        "钱": "money",
        "情绪": "emotion",
        "独处": "solitude",
        "晚年": "later-life",
    }
    parts = [value for key, value in mapping.items() if key in text]
    if parts:
        return "-".join(dict.fromkeys(parts))
    ascii_slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return ascii_slug[:48] or fallback


def choose_scene(pillar: str, slot: str, used_keys: set[str]) -> dict[str, str]:
    scenes = SCENE_LIBRARY.get(pillar, SCENE_LIBRARY["body_restart"]).get(slot, [])
    fallback_scenes = SCENE_LIBRARY["body_restart"].get(slot, [])
    for scene in scenes + fallback_scenes:
        if scene["key"] not in used_keys:
            return scene
    return scenes[0] if scenes else fallback_scenes[0]


def choose_quote(pillar: str, slot: str, used_quotes: set[str], title: str) -> str:
    quotes = QUOTE_LIBRARY.get(pillar, QUOTE_LIBRARY["body_restart"]).get(slot, [])
    for quote in quotes:
        if quote not in used_quotes:
            return quote
    compact_title = re.sub(r"[，。、“”\"'：:；;！？!\?\s]+", "\n", title).strip()
    parts = [part for part in compact_title.splitlines() if part]
    if len(parts) >= 2:
        return "\n".join(parts[:2])
    return title[:14]


def build_prompt(title: str, scene: dict[str, str], slot: str, quote: str, source_name: str) -> str:
    return f"""Original illustration quote-card brief for 晴川黄鹤.

Article title: {title}
Image slot: {slot}
Scene summary: {scene['summary']}
Final card quote text:
{quote}

Target effect:
Square Chinese WeChat watercolor comic quote-card, similar category to a hand-painted collectible article illustration card, but fully original to 晴川黄鹤.

Canvas and layout:
- 1:1 square card.
- Full warm off-white rough rice-paper texture background.
- Upper/middle 55%-65%: detailed hand-drawn watercolor comic scene.
- Bottom 30%-40%: large dark gray / ink-black Chinese brush-calligraphy quote area.
- Lower right: small original red seal for 晴川黄鹤 only. Do not use Yue Man or any copied mark.

Illustration scene:
{scene['scene']}.

Visual style:
Hand-drawn ink outline, visible watercolor wash, paper grain, warm muted colors, gentle humor, mature healing feeling, not childish, not flat vector, not PowerPoint icon style.

Typography instruction:
The final Chinese card text must read exactly:
"{quote.replace(chr(10), ' / ')}"
If the image model cannot render Chinese perfectly, generate the illustration without text but reserve the bottom quote area for post-production text overlay.

Recommended stable production:
1. Generate a no-text watercolor base illustration with the same paper texture and bottom empty quote area.
2. Save that base art as:
   images/illustrations/sources/{source_name}
3. Run:
   python scripts/compose_quote_cards.py
4. The compositor will overlay exact Chinese brush text and the 晴川黄鹤 red seal into the final PNG.

Avoid:
No Yue Man mark, no Yue Man signature, no copied composition from reference images, no copied red stamp, no watermark, no garbled Chinese, no random extra characters, no frightening hospital scene, no exaggerated tears, no low-quality flat vector placeholder.
"""


def article_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_plan(article_path: Path, apply: bool = False, force: bool = False) -> list[dict[str, str]]:
    article_path = article_path.resolve()
    title, body = extract_article(article_path)
    pillar = infer_pillar(title, body)
    manifest = read_manifest()
    existing = [
        item
        for item in manifest.get("assignments", [])
        if Path(item.get("article", "")).resolve() != article_path
    ]
    used_keys = {item.get("scene_key", "") for item in existing}
    used_quotes = {item.get("quote", "") for item in existing}
    date = datetime.now().strftime("%Y%m%d")
    base_slug = short_slug(title, article_path.stem)
    slots = [("01", "opening"), ("02", "conflict"), ("03", "closing")]
    assignments: list[dict[str, str]] = []

    for number, slot in slots:
        scene = choose_scene(pillar, slot, used_keys)
        used_keys.add(scene["key"])
        quote = choose_quote(pillar, slot, used_quotes, title)
        used_quotes.add(quote)
        filename = f"{date}_{base_slug}_{number}_{slot}.png"
        target = IMAGE_DIR / filename
        source = SOURCE_DIR / f"{Path(filename).stem}_base.png"
        prompt_path = PROMPT_DIR / f"{Path(filename).stem}.prompt.md"
        prompt = build_prompt(title, scene, slot, quote, source.name)
        PROMPT_DIR.mkdir(parents=True, exist_ok=True)
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        SOURCE_DIR.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt, encoding="utf-8")
        assignment = {
            "article": str(article_path),
            "article_sha256": article_sha(article_path),
            "title": title,
            "pillar": pillar,
            "slot": slot,
            "number": number,
            "scene_key": scene["key"],
            "summary": scene["summary"],
            "quote": quote,
            "target": str(target),
            "source": str(source),
            "source_relative_target": f"../images/illustrations/sources/{source.name}",
            "article_relative_target": f"../images/illustrations/{filename}",
            "prompt_path": str(prompt_path),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        assignments.append(assignment)

    if apply:
        insert_illustrations(article_path, assignments, force=force)
        new_article_sha = article_sha(article_path)
        for assignment in assignments:
            assignment["article_sha256"] = new_article_sha

    manifest["assignments"] = existing + assignments
    write_manifest(manifest)
    return assignments


def remove_existing_blocks(markdown: str) -> str:
    pattern = r"\n?<!-- qingchuan-illustration-slot: .*? -->\n!\[原创漫画插图：.*?\]\(.*?\)\n?"
    return re.sub(pattern, "\n", markdown, flags=re.S)


def insert_illustrations(article_path: Path, assignments: list[dict[str, str]], force: bool = False) -> None:
    markdown = article_path.read_text(encoding="utf-8")
    if "<!-- qingchuan-illustration-slot:" in markdown:
        if not force:
            raise SystemExit("文章已有插图位；如需重写请加 --force")
        markdown = remove_existing_blocks(markdown)

    frontmatter = ""
    body = markdown
    match = re.match(r"(?s)^(---\n.*?\n---\n)(.*)$", markdown)
    if match:
        frontmatter = match.group(1)
        body = match.group(2).strip()

    parts = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    if len(parts) < 5:
        positions = [1, max(2, len(parts) // 2), max(3, len(parts) - 1)]
    else:
        positions = [2, max(4, len(parts) // 2 + 1), max(5, len(parts) - 1)]

    blocks: dict[int, str] = {}
    for index, assignment in zip(positions, assignments):
        blocks[index] = (
            f"<!-- qingchuan-illustration-slot: {assignment['number']} {assignment['slot']} -->\n"
            f"![原创漫画插图：{assignment['summary']}]({assignment['article_relative_target']})"
        )

    output: list[str] = []
    for index, part in enumerate(parts, start=1):
        output.append(part)
        if index in blocks:
            output.append(blocks[index])

    article_path.write_text(frontmatter + "\n\n".join(output).strip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan three original illustrations for an article.")
    parser.add_argument("article", type=Path)
    parser.add_argument("--apply", action="store_true", help="Insert the three image slots into the article")
    parser.add_argument("--force", action="store_true", help="Replace existing generated image slots")
    args = parser.parse_args()

    article_path = args.article if args.article.is_absolute() else BASE_DIR / args.article
    if not article_path.exists():
        fallback = args.article if args.article.is_absolute() else Path.cwd() / args.article
        article_path = fallback
    if not article_path.exists():
        raise SystemExit(f"文章不存在：{args.article}")

    assignments = make_plan(article_path.resolve(), apply=args.apply, force=args.force)
    for item in assignments:
        print(f"{item['number']} {item['slot']} scene={item['scene_key']} target={item['target']}")
        print(f"prompt={item['prompt_path']}")
    if args.apply:
        print(f"updated={article_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
