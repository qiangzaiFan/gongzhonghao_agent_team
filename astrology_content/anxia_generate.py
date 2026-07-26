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
from datetime import date
from pathlib import Path

from ai_detector import ANXIA_SHORT_MIN_TOTAL_CHARS, DetectorUnavailable, default_report_path, detect_article
from anxia_calendar import CalendarItem, generate_calendar
from anxia_corpus import DEFAULT_CORPUS_DIR, SIGN_TERMS, hot_titles_by_reuse, load_corpus, normalized_title
from quality_gate import format_result, load_source_dir, parse_article, validate_article


ARTICLES_DIR = Path(__file__).parent / "articles"


@dataclass(frozen=True)
class Draft:
    item: CalendarItem
    body: str
    title_override: str | None = None

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


def render_body(item: CalendarItem, *, mode: str = "viral-safe") -> str:
    trait_a, trait_b, trait_c = SIGN_TRAITS.get(item.sign, ("状态敏感", "需要稳住节奏", "适合看清重点"))
    sign = item.sign
    if item.theme == "运势/提醒":
        paragraphs = [
            f"{sign}最近别小看一个变化：有些拖了很久的事，已经到了必须整理的时候。",
            f"你们本来就{trait_a}，但这段时间容易被琐事分走注意力。临时安排、人情请求、重复沟通，都会一点点消耗状态。",
            "真正要抓住的，是能让你往前走的事。该拒绝的别硬撑，该推进的别再等，先把节奏拿回来。",
            f"刷到接好运！祝{sign}稳住这口气，把这个月的好状态一点点找回来。",
        ]
    elif item.theme == "关系/性格":
        paragraphs = [
            f"{sign}不是突然变冷，很多时候是一个细节看多了，心里自然有了答案。",
            f"你们{trait_b}，一开始会给对方余地，也愿意替关系找理由。但只在需要时靠近、平时很少回应的人，最容易让{sign}慢慢清醒。",
            "别再把自己的退后解释成小题大做。谁是真心，谁只是顺手消耗，其实你早就感觉到了。",
            f"刷到接好运！祝{sign}把真心留给稳定回应你的人，少一点内耗。",
        ]
    else:
        paragraphs = [
            f"{sign}今天先别急着付款。看到优惠、链接、群里的临时拼单，停十分钟再点。",
            f"你们{trait_c}，但最近消息太杂，容易顺手答应。以前说好的分摊、会员、订阅，翻出来看一眼，别让小钱悄悄漏掉。",
            "少花一笔不丢人，该收回来的也别一直拖。把账说清楚，反而省掉后面的尴尬。",
            f"刷到接好运！祝{sign}把钱包看稳，接下来该来的小进账别错过。",
        ]
    return "\n\n".join(paragraphs)


def render_markdown(draft: Draft) -> str:
    return f"---\ntitle: {draft.title}\n---\n\n{draft.body}\n"


def output_path(output_dir: Path, draft: Draft) -> Path:
    return output_dir / (
        f"{draft.item.day.strftime('%Y%m%d')}_{draft.item.slot:02d}_"
        f"{slugify(draft.title)}.md"
    )


def build_drafts(
    day: date,
    daily: int,
    corpus_dir: Path | None,
    *,
    days: int = 1,
    mode: str = "viral-safe",
    hot_title_min_count: int = 2,
) -> list[Draft]:
    items = generate_calendar(
        days=days,
        daily=daily,
        start=day,
        profile="anxia_short",
        corpus_dir=corpus_dir,
    )
    drafts: list[Draft] = []
    for item in items:
        title = None
        if mode == "hot-source":
            title = hot_source_title_for_item(item, corpus_dir, min_count=hot_title_min_count)
        drafts.append(
            Draft(
                item=item,
                title_override=title or title_for_item(item, mode if mode != "hot-source" else "viral-safe"),
                body=render_body(item, mode="viral-safe" if mode == "hot-source" else mode),
            )
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


def print_ai_summary(paths: list[Path], ai_python: Path | None = None) -> int:
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
    return total - passed


def main() -> int:
    parser = argparse.ArgumentParser(description="一步生成安夏短文号草稿")
    parser.add_argument("--date", default=date.today().isoformat(), help="起始日期 YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=1, help="连续生成天数，默认 1")
    parser.add_argument("--daily", type=int, default=3, help="每天生成篇数，默认 3")
    parser.add_argument(
        "--mode",
        choices=("viral-safe", "balanced", "hot-source"),
        default="viral-safe",
        help="viral-safe 更强标题和结尾钩子；balanced 更克制；hot-source 优先直接使用热标题",
    )
    parser.add_argument("--hot-title-min-count", type=int, default=2, help="热标题最少重复次数，默认 2")
    parser.add_argument("--output-dir", type=Path, default=ARTICLES_DIR)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在草稿")
    parser.add_argument("--skip-ai-check", action="store_true", help="生成后不运行 AI 质检")
    parser.add_argument("--ai-python", type=Path, help="指定运行 AI 检测的 Python")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写入文件")
    args = parser.parse_args()

    try:
        day = date.fromisoformat(args.date)
    except ValueError as exc:
        parser.error(f"--date 必须是 YYYY-MM-DD：{exc}")

    drafts = build_drafts(
        day,
        args.daily,
        args.source_dir,
        days=args.days,
        mode=args.mode,
        hot_title_min_count=args.hot_title_min_count,
    )
    forbidden_titles = None
    source_texts = None
    if args.source_dir:
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
        result = validate_article(parse_article(path), forbidden_titles=forbidden_titles, source_texts=source_texts)
        print(f"已生成：{path}")
        print(format_result(result))
        if not result.ok:
            failures += 1
    if not args.dry_run:
        print(f"完成：新增/覆盖 {written} 篇，跳过 {skipped} 篇，失败 {failures} 篇")
        if not args.skip_ai_check:
            failures += print_ai_summary(batch_paths, ai_python=args.ai_python)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
