#!/usr/bin/env python3
"""Automatic local Chinese AIGC screening for astrology articles.

This is a quality signal, not proof of authorship. The default model is an
MIT-licensed Chinese BERT detector with modern-model training samples.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from quality_gate import markdown_to_plain, parse_article


DEFAULT_MODEL = "AnxForever/chinese-ai-detector-bert"
DEFAULT_TEMPERATURE = 0.8165
DEFAULT_HUMAN_MIN = 80.0
DEFAULT_AI_MAX = 10.0
HUMAN_PROBABILITY_CUTOFF = 0.50
AI_PROBABILITY_CUTOFF = 0.80
TARGET_CHUNK_CHARS = 190
MIN_CHUNK_CHARS = 60
MAX_CHUNKS = 12
BASE_DIR = Path(__file__).parent
DEFAULT_REPORT_DIR = BASE_DIR / "reviews" / "auto"


class DetectorUnavailable(RuntimeError):
    pass


@dataclass
class DetectionResult:
    report: dict[str, Any]

    @property
    def passed(self) -> bool:
        return bool(self.report.get("passed"))


def article_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _piece_text(text: str) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    pieces: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= TARGET_CHUNK_CHARS:
            pieces.append(paragraph)
            continue
        sentences = [item.strip() for item in re.split(r"(?<=[。！？!?])", paragraph) if item.strip()]
        current = ""
        for sentence in sentences:
            if current and len(current) + len(sentence) > TARGET_CHUNK_CHARS:
                pieces.append(current)
                current = sentence
            else:
                current += sentence
        if current:
            pieces.append(current)

    chunks: list[str] = []
    pending = ""
    for piece in pieces:
        if pending and len(pending) + len(piece) > TARGET_CHUNK_CHARS:
            chunks.append(pending)
            pending = piece
        else:
            pending += piece
        if len(pending) >= MIN_CHUNK_CHARS:
            chunks.append(pending)
            pending = ""
    if pending:
        if chunks:
            chunks[-1] += pending
        else:
            chunks.append(pending)
    if len(chunks) <= MAX_CHUNKS:
        return chunks

    # Keep full-article coverage while bounding inference time.
    stride = len(chunks) / MAX_CHUNKS
    return [chunks[min(len(chunks) - 1, math.floor(index * stride))] for index in range(MAX_CHUNKS)]


def article_chunks(article_path: Path) -> list[str]:
    article = parse_article(article_path)
    body = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", article.body)
    body = re.sub(r"(?m)^#{1,6}\s*", "", body)
    plain = markdown_to_plain(body)
    chunks = _piece_text(plain)
    if not chunks or sum(len(chunk) for chunk in chunks) < 200:
        raise ValueError("正文太短，无法进行稳定的自动 AIGC 检测")
    return chunks


def load_detector(model_id: str):
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise DetectorUnavailable(
            "缺少本地检测依赖。请运行："
            "../.venv/bin/pip install -r requirements-ai-detector.txt"
        ) from exc

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForSequenceClassification.from_pretrained(model_id)
    except Exception as exc:  # Model download/load errors differ by backend.
        raise DetectorUnavailable(f"无法加载本地检测模型 {model_id}：{exc}") from exc
    model.eval()
    return torch, tokenizer, model


def find_ai_index(model: Any) -> int:
    mapping = getattr(model.config, "id2label", {}) or {}
    for raw_index, raw_label in mapping.items():
        label = str(raw_label).lower()
        if "ai" in label and "human" not in label:
            return int(raw_index)
    return 1


def detect_article(
    article_path: Path,
    *,
    model_id: str = DEFAULT_MODEL,
    human_min: float = DEFAULT_HUMAN_MIN,
    ai_max: float = DEFAULT_AI_MAX,
    report_path: Path | None = None,
) -> DetectionResult:
    torch, tokenizer, model = load_detector(model_id)
    chunks = article_chunks(article_path)
    ai_index = find_ai_index(model)
    temperature = DEFAULT_TEMPERATURE if model_id == DEFAULT_MODEL else 1.0

    segments: list[dict[str, Any]] = []
    category_chars = {"human": 0, "suspected": 0, "ai": 0}
    weighted_ai_probability = 0.0
    total_chars = 0

    for order, chunk in enumerate(chunks, start=1):
        inputs = tokenizer(chunk, return_tensors="pt", truncation=True, max_length=256)
        with torch.no_grad():
            logits = model(**inputs).logits
            probabilities = torch.softmax(logits / temperature, dim=-1)[0]
        ai_probability = float(probabilities[ai_index].item())
        if ai_probability < HUMAN_PROBABILITY_CUTOFF:
            category = "human"
        elif ai_probability < AI_PROBABILITY_CUTOFF:
            category = "suspected"
        else:
            category = "ai"
        weight = len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", chunk)) or len(chunk)
        total_chars += weight
        category_chars[category] += weight
        weighted_ai_probability += ai_probability * weight
        segments.append(
            {
                "order": order,
                "chars": weight,
                "category": category,
                "ai_probability": round(ai_probability * 100, 2),
                "preview": chunk[:80],
            }
        )

    ratios = {
        key: round(value / total_chars * 100, 2) if total_chars else 0.0
        for key, value in category_chars.items()
    }
    mean_probability = weighted_ai_probability / total_chars * 100 if total_chars else 100.0
    passed = ratios["human"] >= human_min and ratios["ai"] <= ai_max
    report: dict[str, Any] = {
        "schema_version": 1,
        "detector": "local-chinese-bert",
        "model": model_id,
        "detected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "article": str(article_path.resolve()),
        "article_sha256": article_digest(article_path),
        "thresholds": {"human_min": human_min, "ai_max": ai_max},
        "ratios": ratios,
        "mean_ai_probability": round(mean_probability, 2),
        "passed": passed,
        "segments": segments,
        "limitations": (
            "该结果是本地模型的编辑风险信号，不是作者身份证明，"
            "也不等同于腾讯朱雀的判定。"
        ),
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return DetectionResult(report=report)


def default_report_path(article_path: Path) -> Path:
    return DEFAULT_REPORT_DIR / f"{article_path.stem}.json"


def validate_report(article_path: Path, report_path: Path) -> list[str]:
    if not report_path.is_file():
        return [f"自动 AIGC 报告不存在：{report_path}"]
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"自动 AIGC 报告无效：{exc}"]
    errors: list[str] = []
    if data.get("article_sha256") != article_digest(article_path):
        errors.append("自动 AIGC 报告已过期：文章内容在检测后发生了变化")
    if data.get("passed") is not True:
        ratios = data.get("ratios") or {}
        errors.append(
            "自动 AIGC 门禁未通过："
            f"human={ratios.get('human', '?')}%，ai={ratios.get('ai', '?')}%"
        )
    return errors


def print_result(result: DetectionResult, report_path: Path) -> None:
    ratios = result.report["ratios"]
    print("自动 AIGC 检测：" + ("通过" if result.passed else "未通过"))
    print(
        f"human={ratios['human']:.2f}%，"
        f"suspected={ratios['suspected']:.2f}%，"
        f"ai={ratios['ai']:.2f}%，"
        f"平均 AI 概率={result.report['mean_ai_probability']:.2f}%"
    )
    print(f"报告：{report_path}")
    flagged = [item for item in result.report["segments"] if item["category"] != "human"]
    if flagged:
        print("需要主编复核的片段：")
        for item in flagged:
            print(f"- #{item['order']} {item['category']} {item['ai_probability']}%: {item['preview']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="自动检测中文星座文章的 AIGC 风险")
    parser.add_argument("article", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--human-min", type=float, default=DEFAULT_HUMAN_MIN)
    parser.add_argument("--ai-max", type=float, default=DEFAULT_AI_MAX)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    if not args.article.is_file():
        parser.error(f"文章不存在：{args.article}")
    report_path = args.report or default_report_path(args.article)
    try:
        result = detect_article(
            args.article,
            model_id=args.model,
            human_min=args.human_min,
            ai_max=args.ai_max,
            report_path=report_path,
        )
    except (DetectorUnavailable, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print_result(result, report_path)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
