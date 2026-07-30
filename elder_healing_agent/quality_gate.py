#!/usr/bin/env python3
"""Quality scorecard for elder-healing WeChat drafts."""

from __future__ import annotations

import argparse
import json
from difflib import SequenceMatcher
import re
import sys
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_REFERENCE_DIR = Path(
    r"D:\自媒体\知识库\01-公众号文章\养老情感疗愈公众号文章\黄鹤于飞"
)
DEFAULT_TITLE_LIST = BASE_DIR / "data" / "reference_titles.txt"
DEFAULT_ARTICLES_DIR = BASE_DIR / "articles"

MIN_CJK = 650
MAX_CJK = 1300
MIN_TITLE_CJK = 8
MAX_TITLE_CJK = 38
TITLE_ERROR_SIMILARITY = 0.88
TITLE_WARN_SIMILARITY = 0.76
BODY_ERROR_OVERLAP = 0.10
BODY_WARN_OVERLAP = 0.06
HISTORY_TITLE_WARN_SIMILARITY = 0.80
HISTORY_BODY_WARN_OVERLAP = 0.08
REQUIRED_ILLUSTRATION_COUNT = 3
ILLUSTRATION_ALT_PREFIX = "原创漫画插图："

BANNED_PHRASES = [
    "综上所述",
    "由此可见",
    "我们应该认识到",
    "在这个快节奏的时代",
    "每个人都值得被爱",
    "愿你余生",
    "点赞",
    "转发",
    "关注该公众号",
    "本文由AI",
    "黄鹤于飞",
    "悦漫先生",
]

MEDICAL_RISK_PATTERNS = [
    r"一定.*治好",
    r"保证.*健康",
    r"百分之[一二三四五六七八九十百0-9]+.*疾病.*自愈",
    r"不吃药.*也能好",
    r"癌症.*都是.*情绪",
]

FINANCE_RISK_PATTERNS = [
    r"保证.*收益",
    r"稳赚",
    r"年化.*%",
    r"买.*基金",
    r"买.*股票",
]

REQUIRED_HINTS = [
    "身体",
    "钱",
    "子女",
    "孩子",
    "关系",
    "情绪",
    "生病",
    "睡",
    "晚年",
    "退休",
    "自己",
]

DETAIL_HINTS = [
    "药",
    "饭",
    "水",
    "灯",
    "床",
    "电话",
    "退休金",
    "体检",
    "医院",
    "散步",
    "手机",
    "厨房",
    "钥匙",
    "医保",
]

ACTION_ENDING_HINTS = [
    "关灯",
    "睡",
    "煮",
    "吃",
    "走",
    "散步",
    "放远",
    "泡脚",
    "休息",
    "留",
    "倒水",
]

HIGH_RISK_HINTS = [
    "癌症",
    "肿瘤",
    "免疫系统",
    "遗产",
    "房产",
    "借钱",
    "断亲",
    "不孝",
    "赶出家门",
    "住院费",
]

MEDIUM_RISK_HINTS = [
    "退休金",
    "存款",
    "子女",
    "孩子",
    "老伴",
    "亲戚",
    "生病",
    "医院",
]


def cjk_len(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def extract_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    if not markdown.startswith("---\n"):
        return {}, markdown
    end = markdown.find("\n---", 4)
    if end == -1:
        return {}, markdown
    raw = markdown[4:end].strip()
    body = markdown[end + 4 :].lstrip()
    data: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data, body


def normalized_title(title: str) -> str:
    title = re.sub(r"^\s*#\s*", "", title).strip()
    return title.strip('"')


def title_from_markdown(frontmatter: dict[str, str], body: str) -> str:
    title = normalized_title(frontmatter.get("title", ""))
    if title:
        return title
    heading = re.search(r"^#\s+(.+)$", body, flags=re.M)
    return normalized_title(heading.group(1)) if heading else ""


def normalize_for_match(text: str) -> str:
    return "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", text)).lower()


def title_from_reference_path(path: Path) -> str:
    stem = path.stem
    match = re.match(r"\d{4}-\d{2}-\d{2}\s+-\s+(.+)", stem)
    return match.group(1).strip() if match else stem.strip()


def shingle_set(text: str, width: int = 18) -> set[str]:
    norm = normalize_for_match(text)
    if len(norm) < width:
        return set()
    return {norm[index : index + width] for index in range(len(norm) - width + 1)}


def load_reference_titles(reference_dir: Path | None, title_list: Path | None) -> list[str]:
    titles: list[str] = []
    if title_list and title_list.exists():
        titles.extend(line.strip() for line in title_list.read_text(encoding="utf-8").splitlines() if line.strip())
    if reference_dir and reference_dir.exists():
        titles.extend(title_from_reference_path(path) for path in sorted(reference_dir.rglob("*.md")))
    return unique_titles(titles)


def unique_titles(titles: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for title in titles:
        norm = normalize_for_match(title)
        if norm and norm not in seen:
            seen.add(norm)
            unique.append(title)
    return unique


def load_markdown_bodies(directory: Path | None, exclude_path: Path | None = None) -> list[tuple[str, str, str]]:
    if not directory or not directory.exists():
        return []
    bodies: list[tuple[str, str, str]] = []
    for path in sorted(directory.rglob("*.md")):
        if exclude_path and path.resolve() == exclude_path.resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        frontmatter, body = extract_frontmatter(text)
        title = title_from_markdown(frontmatter, body) or title_from_reference_path(path)
        bodies.append((title, body, str(path)))
    return bodies


def max_title_similarity(title: str, reference_titles: list[str]) -> tuple[float, str]:
    title_norm = normalize_for_match(title)
    max_score = 0.0
    max_title = ""
    for ref_title in reference_titles:
        ref_norm = normalize_for_match(ref_title)
        if not ref_norm:
            continue
        score = SequenceMatcher(None, title_norm, ref_norm).ratio()
        if score > max_score:
            max_score = score
            max_title = ref_title
    return max_score, max_title


def max_body_overlap(body: str, candidates: list[tuple[str, str, str]]) -> tuple[float, str, str]:
    draft_shingles = shingle_set(body)
    if not draft_shingles:
        return 0.0, "", ""

    max_overlap = 0.0
    max_title = ""
    max_path = ""
    for title, candidate_body, candidate_path in candidates:
        candidate_shingles = shingle_set(candidate_body)
        if not candidate_shingles:
            continue
        overlap = len(draft_shingles & candidate_shingles) / len(draft_shingles)
        if overlap > max_overlap:
            max_overlap = overlap
            max_title = title
            max_path = candidate_path
    return max_overlap, max_title, max_path


def originality_checks(
    title: str,
    body: str,
    article_path: Path,
    reference_dir: Path | None,
    title_list: Path | None,
    articles_dir: Path | None,
    skip_reference_check: bool,
    skip_history_check: bool,
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {
        "reference_title_similarity": 0.0,
        "reference_title_match": "",
        "reference_body_overlap": 0.0,
        "reference_body_match": "",
        "history_title_similarity": 0.0,
        "history_title_match": "",
        "history_body_overlap": 0.0,
        "history_body_match": "",
    }

    if skip_reference_check:
        warnings.append("已跳过参考语料相似度检查")
    elif reference_dir and reference_dir.exists():
        reference_titles = load_reference_titles(reference_dir, title_list)
        ref_title_score, ref_title = max_title_similarity(title, reference_titles)
        metrics["reference_title_similarity"] = round(ref_title_score, 4)
        metrics["reference_title_match"] = ref_title
        if normalize_for_match(title) and any(normalize_for_match(title) == normalize_for_match(t) for t in reference_titles):
            errors.append(f"标题与参考语料重复：{ref_title}")
        elif ref_title_score >= TITLE_ERROR_SIMILARITY:
            errors.append(f"标题与参考语料过近：{ref_title_score:.0%} | {ref_title}")
        elif ref_title_score >= TITLE_WARN_SIMILARITY:
            warnings.append(f"标题与参考语料相似度偏高：{ref_title_score:.0%} | {ref_title}")

        reference_bodies = load_markdown_bodies(reference_dir)
        ref_overlap, ref_body_title, _ = max_body_overlap(body, reference_bodies)
        metrics["reference_body_overlap"] = round(ref_overlap, 4)
        metrics["reference_body_match"] = ref_body_title
        if ref_overlap >= BODY_ERROR_OVERLAP:
            errors.append(f"正文与参考语料连续片段重合偏高：{ref_overlap:.1%} | {ref_body_title}")
        elif ref_overlap >= BODY_WARN_OVERLAP:
            warnings.append(f"正文与参考语料有连续片段重合：{ref_overlap:.1%} | {ref_body_title}")
    else:
        warnings.append(f"参考目录不存在，已跳过相似度检查：{reference_dir}")

    if skip_history_check:
        warnings.append("已跳过本账号历史稿去重检查")
    elif articles_dir and articles_dir.exists():
        history = load_markdown_bodies(articles_dir, exclude_path=article_path)
        history_titles = unique_titles([item[0] for item in history])
        hist_title_score, hist_title = max_title_similarity(title, history_titles)
        metrics["history_title_similarity"] = round(hist_title_score, 4)
        metrics["history_title_match"] = hist_title
        if hist_title_score >= HISTORY_TITLE_WARN_SIMILARITY:
            warnings.append(f"标题与本账号历史稿相似度偏高：{hist_title_score:.0%} | {hist_title}")

        hist_overlap, hist_body_title, hist_path = max_body_overlap(body, history)
        metrics["history_body_overlap"] = round(hist_overlap, 4)
        metrics["history_body_match"] = hist_body_title or hist_path
        if hist_overlap >= HISTORY_BODY_WARN_OVERLAP:
            warnings.append(f"正文与本账号历史稿重合偏高：{hist_overlap:.1%} | {hist_body_title or hist_path}")

    return errors, warnings, metrics


def risk_level(markdown: str) -> tuple[str, list[str], list[str]]:
    high_hits = [hint for hint in HIGH_RISK_HINTS if hint in markdown]
    medium_hits = [hint for hint in MEDIUM_RISK_HINTS if hint in markdown]
    if high_hits:
        return "high", high_hits, medium_hits
    if medium_hits:
        return "medium", high_hits, medium_hits
    return "low", high_hits, medium_hits


def markdown_image_links(markdown: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for match in re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", markdown):
        links.append({"alt": match.group(1).strip(), "target": match.group(2).strip()})
    return links


def local_image_path(article_path: Path, target: str) -> Path | None:
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("//"):
        return None
    clean_target = target.split("#", 1)[0].split("?", 1)[0].strip()
    if not clean_target:
        return None
    return (article_path.parent / clean_target).resolve()


def illustration_checks(
    markdown: str,
    article_path: Path,
    require_image_files: bool,
) -> tuple[list[str], list[str], list[dict[str, str]], int]:
    errors: list[str] = []
    warnings: list[str] = []
    image_links = markdown_image_links(markdown)
    missing_files = 0

    if len(image_links) != REQUIRED_ILLUSTRATION_COUNT:
        errors.append(f"每篇文章必须正好 {REQUIRED_ILLUSTRATION_COUNT} 张插图，当前 {len(image_links)} 张")

    seen_targets: set[str] = set()
    for index, link in enumerate(image_links, start=1):
        target = link["target"]
        alt = link["alt"]
        if not alt.startswith(ILLUSTRATION_ALT_PREFIX):
            warnings.append(f"第 {index} 张插图 alt 建议以“{ILLUSTRATION_ALT_PREFIX}”开头")
        if target in seen_targets:
            errors.append(f"插图路径重复：{target}")
        seen_targets.add(target)

        resolved = local_image_path(article_path, target)
        if resolved is None:
            errors.append(f"第 {index} 张插图必须使用本地原创图片路径，当前：{target}")
            continue
        if not resolved.exists():
            missing_files += 1
            if require_image_files:
                errors.append(f"第 {index} 张插图文件尚不存在：{resolved}")

    return errors, warnings, image_links, missing_files


def score_report(errors: list[str], warnings: list[str], metrics: dict[str, Any], detail_count: int, body_cjk: int) -> int:
    score = 100
    score -= min(55, len(errors) * 22)
    score -= min(30, len(warnings) * 4)

    if body_cjk < MIN_CJK or body_cjk > MAX_CJK:
        score -= 6
    if detail_count < 3:
        score -= 6
    if metrics.get("reference_body_overlap", 0) >= BODY_WARN_OVERLAP:
        score -= 8
    if metrics.get("history_body_overlap", 0) >= HISTORY_BODY_WARN_OVERLAP:
        score -= 6
    if metrics.get("reference_title_similarity", 0) >= TITLE_WARN_SIMILARITY:
        score -= 5
    if metrics.get("history_title_similarity", 0) >= HISTORY_TITLE_WARN_SIMILARITY:
        score -= 4

    return max(0, min(100, score))


def analyze_article(
    path: Path,
    reference_dir: Path | None = DEFAULT_REFERENCE_DIR,
    title_list: Path | None = DEFAULT_TITLE_LIST,
    articles_dir: Path | None = DEFAULT_ARTICLES_DIR,
    skip_reference_check: bool = False,
    skip_history_check: bool = False,
    require_image_files: bool = False,
) -> dict[str, Any]:
    markdown = path.read_text(encoding="utf-8")
    frontmatter, body = extract_frontmatter(markdown)
    errors: list[str] = []
    warnings: list[str] = []

    title = title_from_markdown(frontmatter, body)
    if not frontmatter.get("title"):
        errors.append("frontmatter 缺少 title")

    title_cjk = cjk_len(title)
    if title_cjk < MIN_TITLE_CJK or title_cjk > MAX_TITLE_CJK:
        warnings.append(f"标题中文长度建议 {MIN_TITLE_CJK}-{MAX_TITLE_CJK}，当前 {title_cjk}")

    keys = sorted(frontmatter)
    if keys and keys != ["title"]:
        warnings.append(f"frontmatter 建议只保留 title，当前字段：{', '.join(keys)}")

    body_cjk = cjk_len(body)
    if body_cjk < MIN_CJK or body_cjk > MAX_CJK:
        warnings.append(f"正文中文长度建议 {MIN_CJK}-{MAX_CJK}，当前 {body_cjk}")

    for phrase in BANNED_PHRASES:
        if phrase in markdown:
            errors.append(f"出现禁用表达：{phrase}")

    for pattern in MEDICAL_RISK_PATTERNS:
        if re.search(pattern, markdown):
            errors.append(f"疑似医疗风险表达：{pattern}")

    for pattern in FINANCE_RISK_PATTERNS:
        if re.search(pattern, markdown):
            errors.append(f"疑似财务风险表达：{pattern}")

    core_hits = [hint for hint in REQUIRED_HINTS if hint in markdown]
    if not core_hits:
        warnings.append("文章缺少养老疗愈核心词：身体/钱/子女/关系/情绪/晚年等")

    detail_hits = [hint for hint in DETAIL_HINTS if hint in markdown]
    detail_count = len(detail_hits)
    if detail_count < 3:
        warnings.append(f"生活物件/动作偏少，建议至少 3 个，当前命中 {detail_count}")

    h2_count = len(re.findall(r"^##\s+", body, flags=re.M))
    if h2_count > 3:
        warnings.append("小标题超过 3 个，可能像课程讲义")

    risk, high_risk_hits, medium_risk_hits = risk_level(markdown)
    if risk == "high":
        warnings.append(f"发布风险：高风险主题需人工复核（{', '.join(high_risk_hits)}）")
    elif risk == "medium":
        warnings.append(f"发布风险：中风险主题，注意边界表达（{', '.join(medium_risk_hits[:6])}）")

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if paragraphs and cjk_len(paragraphs[0]) > 180:
        warnings.append("开头段偏长，建议前 120-180 字内击中痛点")

    ending = body[-260:]
    if ending and not any(hint in ending for hint in ACTION_ENDING_HINTS):
        warnings.append("结尾缺少具体动作，建议停在关灯、吃饭、散步、休息等生活动作上")

    image_errors, image_warnings, image_links, missing_image_count = illustration_checks(
        markdown,
        article_path=path,
        require_image_files=require_image_files,
    )
    errors.extend(image_errors)
    warnings.extend(image_warnings)

    orig_errors, orig_warnings, metrics = originality_checks(
        title=title,
        body=body,
        article_path=path,
        reference_dir=reference_dir,
        title_list=title_list,
        articles_dir=articles_dir,
        skip_reference_check=skip_reference_check,
        skip_history_check=skip_history_check,
    )
    errors.extend(orig_errors)
    warnings.extend(orig_warnings)

    score = score_report(errors, warnings, metrics, detail_count, body_cjk)
    status = "passed" if not errors and score >= 85 else "revise"
    if errors or score < 75:
        status = "failed"

    return {
        "path": str(path),
        "status": status,
        "score": score,
        "risk_level": risk,
        "title": title,
        "title_cjk": title_cjk,
        "body_cjk": body_cjk,
        "h2_count": h2_count,
        "image_count": len(image_links),
        "missing_image_count": missing_image_count,
        "image_links": image_links,
        "core_hits": core_hits,
        "detail_hits": detail_hits,
        "high_risk_hits": high_risk_hits,
        "medium_risk_hits": medium_risk_hits,
        "metrics": metrics,
        "errors": errors,
        "warnings": warnings,
    }


def check_article(
    path: Path,
    reference_dir: Path | None = DEFAULT_REFERENCE_DIR,
    title_list: Path | None = DEFAULT_TITLE_LIST,
    articles_dir: Path | None = DEFAULT_ARTICLES_DIR,
    skip_reference_check: bool = False,
    skip_history_check: bool = False,
    require_image_files: bool = False,
) -> tuple[list[str], list[str]]:
    report = analyze_article(
        path,
        reference_dir=reference_dir,
        title_list=title_list,
        articles_dir=articles_dir,
        skip_reference_check=skip_reference_check,
        skip_history_check=skip_history_check,
        require_image_files=require_image_files,
    )
    return list(report["errors"]), list(report["warnings"])


def print_report(report: dict[str, Any]) -> None:
    status = report["status"].upper()
    print(f"{status} score={report['score']} risk={report['risk_level']}")
    print(f"title={report['title']}")
    print(
        f"title_cjk={report['title_cjk']} body_cjk={report['body_cjk']} "
        f"h2={report['h2_count']} images={report['image_count']} missing_images={report['missing_image_count']}"
    )
    metrics = report["metrics"]
    print(
        "originality="
        f"ref_title:{metrics['reference_title_similarity']:.0%} "
        f"ref_body:{metrics['reference_body_overlap']:.1%} "
        f"history_title:{metrics['history_title_similarity']:.0%} "
        f"history_body:{metrics['history_body_overlap']:.1%}"
    )
    for item in report["errors"]:
        print(f"- ERROR: {item}")
    for item in report["warnings"]:
        print(f"- WARN: {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check elder-healing WeChat draft quality.")
    parser.add_argument("article", help="Path to a Markdown article")
    parser.add_argument(
        "--reference-dir",
        default=str(DEFAULT_REFERENCE_DIR),
        help="Reference article directory for originality checks",
    )
    parser.add_argument(
        "--title-list",
        default=str(DEFAULT_TITLE_LIST),
        help="Reference title list generated by analyze_reference_corpus.py",
    )
    parser.add_argument(
        "--articles-dir",
        default=str(DEFAULT_ARTICLES_DIR),
        help="Own article directory for history duplicate checks",
    )
    parser.add_argument(
        "--skip-reference-check",
        action="store_true",
        help="Skip title/body similarity checks against reference corpus",
    )
    parser.add_argument(
        "--skip-history-check",
        action="store_true",
        help="Skip title/body similarity checks against own history",
    )
    parser.add_argument(
        "--require-image-files",
        action="store_true",
        help="Fail if the three local illustration files do not exist",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON scorecard")
    args = parser.parse_args()

    path = Path(args.article)
    if not path.exists():
        print(f"文件不存在：{path}", file=sys.stderr)
        return 2

    reference_dir = None if args.skip_reference_check else Path(args.reference_dir)
    title_list = None if args.skip_reference_check else Path(args.title_list)
    articles_dir = None if args.skip_history_check else Path(args.articles_dir)
    report = analyze_article(
        path,
        reference_dir=reference_dir,
        title_list=title_list,
        articles_dir=articles_dir,
        skip_reference_check=args.skip_reference_check,
        skip_history_check=args.skip_history_check,
        require_image_files=args.require_image_files,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)

    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
