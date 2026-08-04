#!/usr/bin/env python3
"""Create and validate editorial records for Anxia short-form drafts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from quality_gate import parse_article


BASE_DIR = Path(__file__).parent
DEFAULT_RECORD_DIR = BASE_DIR / "reviews" / "editorial"
VALID_SOURCE_MODES = {"corpus_style", "independent"}
REQUIRED_TOPIC_FIELDS = ("scheduled_for", "slot", "sign", "theme", "angle")
REQUIRED_VARIANT_FIELDS = ("key", "hook", "focus", "closing")
REQUIRED_DISTRIBUTION_DIMENSIONS = ("title", "opening")


def article_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def default_record_path(article_path: Path, record_dir: Path = DEFAULT_RECORD_DIR) -> Path:
    return record_dir / f"{article_path.stem}.json"


def _stored_path(path: Path, record_path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return str(resolved.relative_to(record_path.parent.resolve()))
    except ValueError:
        return str(resolved)


def _resolve_path(record_path: Path, raw_path: object) -> Path:
    path = Path(str(raw_path)).expanduser()
    if path.is_absolute():
        return path
    return (record_path.parent / path).resolve()


def load_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_distribution_variants(
    values: list[dict[str, str]] | tuple[dict[str, str], ...] | None,
    *,
    fallback: list[dict[str, str]],
    required_field: str,
) -> list[dict[str, str]]:
    variants: list[dict[str, str]] = []
    for index, raw_variant in enumerate(values or fallback, start=1):
        key = str(raw_variant.get("key", "")).strip() or f"variant-{index}"
        text = str(raw_variant.get(required_field, "")).strip()
        if not text or any(item["key"] == key or item[required_field] == text for item in variants):
            continue
        variant = {"key": key, required_field: text}
        for optional_field in ("label", "formula", "pattern"):
            value = str(raw_variant.get(optional_field, "")).strip()
            if value:
                variant[optional_field] = value
        variants.append(variant)
    return variants


def _selected_variant_key(
    variants: list[dict[str, str]],
    *,
    selected_key: str | None,
    selected_text: str,
    text_field: str,
) -> str:
    requested_key = (selected_key or "").strip()
    if any(item["key"] == requested_key for item in variants):
        return requested_key
    for variant in variants:
        if variant[text_field] == selected_text:
            return variant["key"]
    return variants[0]["key"] if variants else ""


def build_record(
    article_path: Path,
    *,
    topic: dict[str, Any],
    title_candidates: tuple[str, ...] | list[str],
    body_variant: dict[str, str],
    source_mode: str,
    record_path: Path,
    source_dir: Path | None = None,
    title_variants: list[dict[str, str]] | tuple[dict[str, str], ...] | None = None,
    opening_variants: list[dict[str, str]] | tuple[dict[str, str], ...] | None = None,
    selected_title_variant: str | None = None,
    selected_opening_variant: str | None = None,
) -> dict[str, Any]:
    article = parse_article(article_path)
    if source_mode not in VALID_SOURCE_MODES:
        raise ValueError(f"不支持的来源模式：{source_mode}")

    source: dict[str, str] = {"mode": source_mode}
    if source_dir is not None:
        source["corpus_dir"] = _stored_path(source_dir, record_path)
    candidates = list(dict.fromkeys(item.strip() for item in title_candidates if item.strip()))
    if article.title and article.title not in candidates:
        candidates.insert(0, article.title)
    title_options = _normalize_distribution_variants(
        title_variants,
        fallback=[
            {"key": f"title-{index}", "text": candidate, "formula": "未标注"}
            for index, candidate in enumerate(candidates, start=1)
        ],
        required_field="text",
    )
    if article.title and all(item["text"] != article.title for item in title_options):
        title_options.insert(
            0,
            {
                "key": "title-selected",
                "text": article.title,
                "formula": "未标注",
            },
        )
    opening_options = _normalize_distribution_variants(
        opening_variants,
        fallback=[
            {
                "key": "opening-default",
                "text": str(body_variant.get("hook", "")).strip(),
                "label": "默认开头",
            },
            {
                "key": "opening-alternate",
                "text": f"从{str(body_variant.get('focus', '')).strip()}切入",
                "label": "补充开头",
            },
        ],
        required_field="text",
    )

    return {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "article": _stored_path(article_path, record_path),
        "article_sha256": article_digest(article_path),
        "source": source,
        "topic": topic,
        "titles": {
            "selected": article.title,
            "candidates": candidates,
        },
        "distribution": {
            "title": {
                "selected_key": _selected_variant_key(
                    title_options,
                    selected_key=selected_title_variant,
                    selected_text=article.title,
                    text_field="text",
                ),
                "variants": title_options,
            },
            "opening": {
                "selected_key": _selected_variant_key(
                    opening_options,
                    selected_key=selected_opening_variant,
                    selected_text=str(body_variant.get("hook", "")).strip(),
                    text_field="text",
                ),
                "variants": opening_options,
            },
        },
        "body_variant": body_variant,
    }


def write_record(record_path: Path, record: dict[str, Any]) -> None:
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_generated_record(
    article_path: Path,
    *,
    item: Any,
    title_candidates: tuple[str, ...] | list[str],
    body_variant: dict[str, str],
    source_dir: Path | None,
    record_dir: Path = DEFAULT_RECORD_DIR,
    title_variants: list[dict[str, str]] | tuple[dict[str, str], ...] | None = None,
    opening_variants: list[dict[str, str]] | tuple[dict[str, str], ...] | None = None,
    selected_title_variant: str | None = None,
    selected_opening_variant: str | None = None,
) -> Path:
    record_path = default_record_path(article_path, record_dir)
    topic = {
        "scheduled_for": item.day.isoformat(),
        "slot": item.slot,
        "sign": item.sign,
        "theme": item.theme,
        "angle": item.angle,
    }
    record = build_record(
        article_path,
        topic=topic,
        title_candidates=title_candidates,
        body_variant=body_variant,
        source_mode="corpus_style" if source_dir is not None else "independent",
        source_dir=source_dir,
        record_path=record_path,
        title_variants=title_variants,
        opening_variants=opening_variants,
        selected_title_variant=selected_title_variant,
        selected_opening_variant=selected_opening_variant,
    )
    write_record(record_path, record)
    return record_path


def validate_record(
    article_path: Path,
    record_path: Path,
    *,
    source_dir: Path | None = None,
    require_corpus_check: bool = False,
) -> list[str]:
    if not record_path.is_file():
        return [f"编辑记录不存在：{record_path}"]
    try:
        record = load_record(record_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"编辑记录无效：{exc}"]

    errors: list[str] = []
    if record.get("schema_version") != 1:
        errors.append("编辑记录 schema_version 必须为 1")

    stored_article = record.get("article")
    if not stored_article:
        errors.append("编辑记录缺少 article")
    elif _resolve_path(record_path, stored_article) != article_path.resolve():
        errors.append("编辑记录绑定的 article 与当前文章不一致")
    if record.get("article_sha256") != article_digest(article_path):
        errors.append("编辑记录已过期：文章内容在记录后发生了变化")

    source = record.get("source")
    if not isinstance(source, dict):
        errors.append("编辑记录缺少 source")
    else:
        mode = source.get("mode")
        if mode not in VALID_SOURCE_MODES:
            errors.append("source.mode 必须是 corpus_style 或 independent")
        if mode == "corpus_style":
            corpus_dir = source.get("corpus_dir")
            if not corpus_dir:
                errors.append("corpus_style 记录必须标注 corpus_dir")
            if require_corpus_check and source_dir is None:
                errors.append("corpus_style 发布预检必须传入 --source-dir 执行全库原创度检查")
    topic = record.get("topic")
    if not isinstance(topic, dict):
        errors.append("编辑记录缺少 topic")
    else:
        missing = [key for key in REQUIRED_TOPIC_FIELDS if not topic.get(key)]
        if missing:
            errors.append("topic 缺少字段：" + "、".join(missing))

    titles = record.get("titles")
    if not isinstance(titles, dict):
        errors.append("编辑记录缺少 titles")
    else:
        candidates = titles.get("candidates")
        if not isinstance(candidates, list) or len(set(candidates)) < 3:
            errors.append("titles.candidates 至少保留 3 个不重复标题")
        if titles.get("selected") != parse_article(article_path).title:
            errors.append("titles.selected 与文章标题不一致")

    distribution = record.get("distribution")
    if distribution is not None:
        if not isinstance(distribution, dict):
            errors.append("distribution 必须是对象")
        else:
            for dimension in REQUIRED_DISTRIBUTION_DIMENSIONS:
                details = distribution.get(dimension)
                if not isinstance(details, dict):
                    errors.append(f"distribution.{dimension} 缺失")
                    continue
                variants = details.get("variants")
                if not isinstance(variants, list):
                    errors.append(f"distribution.{dimension}.variants 必须是列表")
                    continue
                minimum = 3 if dimension == "title" else 2
                if len(variants) < minimum:
                    errors.append(
                        f"distribution.{dimension}.variants 至少保留 {minimum} 个版本"
                    )
                    continue
                keys: list[str] = []
                texts: list[str] = []
                for variant_item in variants:
                    if not isinstance(variant_item, dict):
                        errors.append(f"distribution.{dimension}.variants 包含无效版本")
                        continue
                    key = str(variant_item.get("key", "")).strip()
                    text = str(variant_item.get("text", "")).strip()
                    if not key or not text:
                        errors.append(f"distribution.{dimension}.variants 的 key 和 text 不能为空")
                    keys.append(key)
                    texts.append(text)
                if len(set(keys)) != len(keys) or len(set(texts)) != len(texts):
                    errors.append(f"distribution.{dimension}.variants 不能有重复 key 或 text")
                selected_key = str(details.get("selected_key", "")).strip()
                if selected_key not in keys:
                    errors.append(f"distribution.{dimension}.selected_key 不在候选版本中")
                if dimension == "title" and titles and titles.get("selected") not in texts:
                    errors.append("distribution.title 必须包含当前文章标题")

    variant = record.get("body_variant")
    if not isinstance(variant, dict):
        errors.append("编辑记录缺少 body_variant")
    else:
        missing = [key for key in REQUIRED_VARIANT_FIELDS if not variant.get(key)]
        if missing:
            errors.append("body_variant 缺少字段：" + "、".join(missing))

    return errors


def _split_candidates(values: list[str]) -> list[str]:
    candidates: list[str] = []
    for value in values:
        candidates.extend(item.strip() for item in value.split("|") if item.strip())
    return candidates


def create(args: argparse.Namespace) -> int:
    if not args.article.is_file():
        print(f"文章不存在：{args.article}", file=sys.stderr)
        return 1
    record_path = args.out or default_record_path(args.article)
    candidates = _split_candidates(args.title_candidate)
    topic = {
        "scheduled_for": args.scheduled_for,
        "slot": args.slot,
        "sign": args.sign,
        "theme": args.theme,
        "angle": args.angle,
    }
    variant = {
        "key": args.variant_key,
        "hook": args.hook,
        "focus": args.focus,
        "closing": args.closing,
    }
    try:
        record = build_record(
            args.article,
            topic=topic,
            title_candidates=candidates,
            body_variant=variant,
            source_mode=args.source_mode,
            source_dir=args.source_dir,
            record_path=record_path,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    write_record(record_path, record)
    print(f"已写入编辑记录：{record_path}")
    return 0


def check(args: argparse.Namespace) -> int:
    errors = validate_record(args.article, args.record, source_dir=args.source_dir)
    if errors:
        print("编辑记录未通过：")
        print("\n".join(f"- {item}" for item in errors))
        return 1
    print("编辑记录通过")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="创建或校验安夏短文编辑记录")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("article", type=Path)
    create_parser.add_argument("--source-mode", choices=sorted(VALID_SOURCE_MODES), default="independent")
    create_parser.add_argument("--source-dir", type=Path)
    create_parser.add_argument("--scheduled-for", required=True)
    create_parser.add_argument("--slot", required=True, type=int)
    create_parser.add_argument("--sign", required=True)
    create_parser.add_argument("--theme", required=True)
    create_parser.add_argument("--angle", required=True)
    create_parser.add_argument("--title-candidate", action="append", default=[], required=True)
    create_parser.add_argument("--variant-key", required=True)
    create_parser.add_argument("--hook", required=True)
    create_parser.add_argument("--focus", required=True)
    create_parser.add_argument("--closing", required=True)
    create_parser.add_argument("--out", type=Path)
    create_parser.set_defaults(func=create)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("article", type=Path)
    check_parser.add_argument("record", type=Path)
    check_parser.add_argument("--source-dir", type=Path)
    check_parser.set_defaults(func=check)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
