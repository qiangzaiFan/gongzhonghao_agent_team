#!/usr/bin/env python3
"""Finalize approved persona candidates as tracked high-quality JPEG assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ImageFilter, ImageOps, ImageStat
except ImportError as exc:  # pragma: no cover - environment setup failure
    raise SystemExit(
        "缺少 Pillow。请在仓库根目录运行："
        ".venv/bin/python -m pip install -r requirements-imagegen.txt"
    ) from exc


BASE_DIR = Path(__file__).resolve().parent
PERSONA_DIR = BASE_DIR / "images" / "persona"
SCENES_DIR = PERSONA_DIR / "scenes"
METADATA_DIR = PERSONA_DIR / "metadata"
IDENTITY_REFERENCE = "images/persona/master/persona_master_glam_v3.png"
MIN_BRIGHTNESS = 45.0
MAX_BRIGHTNESS = 235.0
MIN_SATURATION = 18.0
MIN_EDGE_RMS = 14.0
MIN_SHORT_EDGE = 768
MIN_PIXELS = 1_200_000
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*(?:-v[0-9]{2})?$")
SIZE_RE = re.compile(r"^([1-9][0-9]*)x([1-9][0-9]*)$")


def metrics(image: Image.Image) -> dict[str, float]:
    rgb = image.convert("RGB")
    gray = rgb.convert("L")
    return {
        "brightness": round(ImageStat.Stat(gray).mean[0], 2),
        "saturation": round(ImageStat.Stat(rgb.convert("HSV").split()[1]).mean[0], 2),
        "edge_rms": round(ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).rms[0], 2),
        "width": float(rgb.width),
        "height": float(rgb.height),
    }


def quality_errors(values: dict[str, float]) -> list[str]:
    errors: list[str] = []
    brightness = values["brightness"]
    if brightness < MIN_BRIGHTNESS or brightness > MAX_BRIGHTNESS:
        errors.append(
            f"亮度 {brightness:.1f} 不在 {MIN_BRIGHTNESS:.0f}-{MAX_BRIGHTNESS:.0f} 范围"
        )
    if values["saturation"] < MIN_SATURATION:
        errors.append(
            f"平均饱和度 {values['saturation']:.1f} 低于 {MIN_SATURATION:.0f}"
        )
    if values["edge_rms"] < MIN_EDGE_RMS:
        errors.append(f"清晰度 {values['edge_rms']:.1f} 低于 {MIN_EDGE_RMS:.0f}")
    width = int(values["width"])
    height = int(values["height"])
    if min(width, height) < MIN_SHORT_EDGE or width * height < MIN_PIXELS:
        errors.append(
            f"分辨率 {width}x{height} 过低：短边至少 {MIN_SHORT_EDGE}px，"
            f"总像素至少 {MIN_PIXELS}"
        )
    return errors


def validate_slug(value: str) -> str:
    slug = value.strip().lower()
    if not SLUG_RE.fullmatch(slug):
        raise argparse.ArgumentTypeError(
            "slug 只能包含小写英文、数字和连字符，版本后缀使用 -v02"
        )
    return slug


def parse_size(value: str) -> tuple[int, int]:
    match = SIZE_RE.fullmatch(value.strip().lower())
    if not match:
        raise argparse.ArgumentTypeError("尺寸格式必须是 WIDTHxHEIGHT，例如 900x600")
    return int(match.group(1)), int(match.group(2))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (BASE_DIR / path).resolve()


def finalize(args: argparse.Namespace) -> int:
    source = resolve_path(args.candidate)
    if not source.is_file():
        print(f"错误：候选图不存在：{source}", file=sys.stderr)
        return 1
    if source.stat().st_size == 0:
        print(f"错误：候选图为空：{source}", file=sys.stderr)
        return 1

    output = (
        resolve_path(args.out)
        if args.out
        else SCENES_DIR / f"{args.slug}.jpg"
    )
    metadata_output = (
        resolve_path(args.metadata_out)
        if args.metadata_out
        else METADATA_DIR / f"{args.slug}.json"
    )
    for path in (output, metadata_output):
        if path.exists() and not args.force:
            print(f"错误：文件已存在，不会覆盖：{path}", file=sys.stderr)
            return 1

    prompt_path: Path | None = None
    prompt = ""
    if args.prompt_file:
        prompt_path = resolve_path(args.prompt_file)
        if not prompt_path.is_file():
            print(f"错误：prompt 文件不存在：{prompt_path}", file=sys.stderr)
            return 1
        prompt = prompt_path.read_text(encoding="utf-8").strip()

    try:
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            original_size = image.size
            if args.size:
                final = ImageOps.fit(
                    image,
                    args.size,
                    method=Image.Resampling.LANCZOS,
                    centering=(args.focus_x, args.focus_y),
                )
            else:
                final = image.copy()
            final = final.filter(ImageFilter.UnsharpMask(radius=1.0, percent=105, threshold=3))
    except OSError as exc:
        print(f"错误：无法读取候选图：{source}：{exc}", file=sys.stderr)
        return 1

    values = metrics(final)
    errors = quality_errors(values)
    if errors and not args.allow_quality_warning:
        print("质量检查失败，未写入正式图池：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print("确认视觉上可接受时可追加 --allow-quality-warning。", file=sys.stderr)
        return 2

    output.parent.mkdir(parents=True, exist_ok=True)
    metadata_output.parent.mkdir(parents=True, exist_ok=True)
    final.save(output, format="JPEG", quality=96, optimize=True, progressive=True)

    metadata = {
        "schema_version": 1,
        "persona_id": "emotion_woman_v1",
        "identity_reference": IDENTITY_REFERENCE,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_candidate": str(source),
        "source_sha256": file_sha256(source),
        "source_size": list(original_size),
        "output": str(output),
        "output_size": list(final.size),
        "output_sha256": file_sha256(output),
        "prompt_file": str(prompt_path) if prompt_path else None,
        "prompt_sha256": (
            hashlib.sha256(prompt.encode("utf-8")).hexdigest() if prompt else None
        ),
        "prompt": prompt or None,
        "metrics": values,
        "quality_warnings": errors,
        "human_identity_review_required": True,
        "approved_for_pool": False,
    }
    metadata_output.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = {
        "image": str(output),
        "metadata": str(metadata_output),
        "metrics": values,
        "warnings": errors,
        "next_step": "人工对照母图确认身份后，才可加入 image_pool.txt",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="将已审核的人设候选图转成高质量 JPG，并记录来源和质量指标",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    finalize_parser = subparsers.add_parser("finalize", help="整理一张正式人设图片")
    finalize_parser.add_argument("candidate", help="候选 PNG/JPEG 路径")
    finalize_parser.add_argument("--slug", required=True, type=validate_slug)
    finalize_parser.add_argument("--prompt-file", help="生成该图片使用的 prompt 文件")
    finalize_parser.add_argument("--out", help="自定义 JPG 输出路径")
    finalize_parser.add_argument("--metadata-out", help="自定义元数据 JSON 路径")
    finalize_parser.add_argument(
        "--size",
        type=parse_size,
        help="可选裁切尺寸，例如 900x600；默认保留候选图原分辨率",
    )
    finalize_parser.add_argument(
        "--focus-x",
        type=float,
        default=0.5,
        choices=[index / 10 for index in range(11)],
        help="横向裁切中心，0 为最左，1 为最右，默认 0.5",
    )
    finalize_parser.add_argument(
        "--focus-y",
        type=float,
        default=0.5,
        choices=[index / 10 for index in range(11)],
        help="纵向裁切中心，0 为最上，1 为最下，默认 0.5",
    )
    finalize_parser.add_argument(
        "--allow-quality-warning",
        action="store_true",
        help="保留质量警告但仍写入；不代表身份审核通过",
    )
    finalize_parser.add_argument(
        "--force",
        action="store_true",
        help="明确覆盖同名文件",
    )
    finalize_parser.set_defaults(handler=finalize)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
