#!/usr/bin/env python3
"""Generate, score, and attach local ComfyUI images for food articles."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, parse, request

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageStat
except ImportError:  # pragma: no cover - surfaced with a useful message at runtime
    Image = None


ROOT = Path(__file__).resolve().parent
AI_IMAGE_DIR = ROOT / "images" / "ai"
CANDIDATE_DIR = AI_IMAGE_DIR / "candidates"
REVIEW_DIR = ROOT / "reviews" / "image_candidates"
PROFILE_PATH = ROOT / "comfy_model_profiles.json"
DEFAULT_ENDPOINT = "http://127.0.0.1:8188"
IMAGE_MARKDOWN_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<ref>[^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTTP_REF_RE = re.compile(r"^https?://", re.IGNORECASE)

NEGATIVE_PROMPT = (
    "text, watermark, logo, brand packaging, social media UI, menu typography, "
    "people, face, hands, fingers, chopsticks held by a hand, multiple cooking actions, "
    "restaurant advertising, luxury plating, distorted food, duplicated food, "
    "deformed bowls, blurry, overexposed, underexposed, plastic texture"
)
COMMON_PROMPT = (
    "普通中国家庭厨房里的真实手机随手拍美食照片，普通白瓷碗盘和日常厨房台面，"
    "自然窗光混合厨房顶灯，真实食物质感，有轻微油光和自然不完美，"
    "清晰对焦，构图简洁，非餐厅广告摄影。"
)


class PipelineError(RuntimeError):
    """Raised when the image pipeline cannot produce a safe final asset."""


@dataclass(frozen=True)
class ImageSlot:
    index: int
    line_number: int
    alt: str
    reference: str
    target_relative: str
    target_path: Path


@dataclass
class Candidate:
    slot_index: int
    candidate_index: int
    profile: str
    seed: int
    prompt: str
    path: str
    score: float
    metrics: dict[str, Any]
    warnings: list[str]
    semantic_score: float | None
    ocr_text: str | None


class ComfyClient:
    """Small dependency-free client for ComfyUI's local HTTP API."""

    def __init__(self, endpoint: str, timeout: int) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        self.client_id = f"food-home-cooking-{uuid.uuid4()}"

    def _url(self, path: str) -> str:
        return f"{self.endpoint}{path}"

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(self._url(path), data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise PipelineError(f"ComfyUI HTTP {exc.code}: {detail[:1000]}") from exc
        except error.URLError as exc:
            raise PipelineError(
                f"无法连接 ComfyUI {self.endpoint}：{exc.reason}。"
                "请先用 run_nvidia_gpu.bat --lowvram 启动本地服务。"
            ) from exc

    def preflight(self) -> dict[str, Any]:
        return self._request_json("/system_stats")

    def queue(self, workflow: dict[str, Any]) -> str:
        response = self._request_json(
            "/prompt",
            method="POST",
            payload={"prompt": workflow, "client_id": self.client_id},
        )
        prompt_id = str(response.get("prompt_id", "")).strip()
        if not prompt_id:
            error_message = response.get("error") or response
            raise PipelineError(f"ComfyUI 未接受工作流：{error_message}")
        return prompt_id

    def wait_for_images(
        self,
        prompt_id: str,
        *,
        max_wait_seconds: int,
        poll_seconds: float,
    ) -> list[dict[str, str]]:
        deadline = time.monotonic() + max_wait_seconds
        while time.monotonic() < deadline:
            history = self._request_json(f"/history/{parse.quote(prompt_id)}")
            record = history.get(prompt_id)
            if record:
                status = record.get("status", {})
                status_text = str(status.get("status_str", "")).lower()
                if status_text in {"error", "failed"}:
                    messages = status.get("messages", [])
                    raise PipelineError(f"ComfyUI 生成失败：{messages or record}")

                image_records: list[dict[str, str]] = []
                for output in record.get("outputs", {}).values():
                    for image_info in output.get("images", []):
                        filename = str(image_info.get("filename", ""))
                        if not filename:
                            continue
                        image_records.append(
                            {
                                "filename": filename,
                                "subfolder": str(image_info.get("subfolder", "")),
                                "type": str(image_info.get("type", "output")),
                            }
                        )
                if image_records:
                    return image_records
            time.sleep(poll_seconds)
        raise PipelineError(f"等待 ComfyUI 输出超时（{max_wait_seconds} 秒）：{prompt_id}")

    def download_image(self, image_info: dict[str, str], destination: Path) -> None:
        query = parse.urlencode(image_info)
        req = request.Request(self._url(f"/view?{query}"), headers={"Accept": "image/*"})
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                content_type = response.headers.get_content_type()
                if not content_type.startswith("image/"):
                    raise PipelineError(f"ComfyUI 输出不是图片：{content_type}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(response.read())
        except error.URLError as exc:
            raise PipelineError(f"无法从 ComfyUI 下载图片：{exc.reason}") from exc


class OptionalSemanticScorer:
    """Use OpenCLIP on CPU when installed; gracefully skip otherwise."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.available: bool | None = None
        self.error: str | None = None
        self.model: Any | None = None
        self.preprocess: Any | None = None
        self.tokenizer: Any | None = None
        self.torch: Any | None = None

    def _load(self) -> bool:
        if self.available is not None:
            return self.available
        if self.mode == "off":
            self.available = False
            return False
        try:
            import open_clip
            import torch

            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32",
                pretrained="laion2b_s34b_b79k",
                device="cpu",
            )
            self.model.eval()
            self.tokenizer = open_clip.get_tokenizer("ViT-B-32")
            self.torch = torch
            self.available = True
        except Exception as exc:  # noqa: BLE001 - optional runtime feature
            self.error = str(exc)
            self.available = False
            if self.mode == "require":
                raise PipelineError(
                    "语义评分不可用。请安装 open-clip-torch 并预先缓存模型，"
                    f"或改用 --semantic-check off：{exc}"
                ) from exc
        return self.available

    def score(self, image_path: Path, prompt: str) -> float | None:
        if not self._load():
            return None
        assert self.model is not None
        assert self.preprocess is not None
        assert self.tokenizer is not None
        assert self.torch is not None
        assert Image is not None

        with Image.open(image_path) as raw:
            image = raw.convert("RGB")
            image_tensor = self.preprocess(image).unsqueeze(0)
        text_tensor = self.tokenizer([prompt])
        with self.torch.no_grad():
            image_features = self.model.encode_image(image_tensor)
            text_features = self.model.encode_text(text_tensor)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            text_features /= text_features.norm(dim=-1, keepdim=True)
            return float((image_features @ text_features.T).item())


def require_pillow() -> None:
    if Image is None:
        raise PipelineError(
            "缺少 Pillow，无法做图片检查和 JPG 输出。"
            "请运行 python -m pip install -r requirements-imagegen.txt"
        )


def load_profiles() -> dict[str, dict[str, Any]]:
    try:
        profiles = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PipelineError(f"模型配置不存在：{PROFILE_PATH}") from exc
    if not isinstance(profiles, dict) or not profiles:
        raise PipelineError(f"模型配置无效：{PROFILE_PATH}")
    return profiles


def extract_image_slots(article_path: Path) -> tuple[str, list[ImageSlot]]:
    text = article_path.read_text(encoding="utf-8")
    slots: list[ImageSlot] = []
    for index, match in enumerate(IMAGE_MARKDOWN_RE.finditer(text), start=1):
        reference = match.group("ref").strip()
        if HTTP_REF_RE.match(reference):
            raise PipelineError(f"图片 #{index} 使用了远程地址，必须改为本地图片：{reference}")
        filename = Path(reference).name
        if not filename:
            raise PipelineError(f"图片 #{index} 缺少文件名：{reference}")
        target_relative = f"../images/ai/{filename}"
        line_number = text.count("\n", 0, match.start()) + 1
        slots.append(
            ImageSlot(
                index=index,
                line_number=line_number,
                alt=match.group("alt").strip() or f"示意图 {index}",
                reference=reference,
                target_relative=target_relative,
                target_path=AI_IMAGE_DIR / filename,
            )
        )
    if not slots:
        raise PipelineError("文章中没有 Markdown 图片位，无法生成配图。")
    return text, slots


def image_kind(alt: str) -> str:
    if any(word in alt for word in ["食材", "准备"]):
        return "ingredients"
    if any(word in alt for word in ["步骤", "下锅", "炒", "煮", "焖", "切", "盛出"]):
        return "step"
    if any(word in alt for word in ["成品", "近景", "细节", "上桌"]):
        return "detail"
    if any(word in alt for word in ["整餐", "搭配", "封面"]):
        return "cover"
    return "dish"


def build_prompt(slot: ImageSlot) -> str:
    kind = image_kind(slot.alt)
    subject = slot.alt.removeprefix("示意图：").removeprefix("步骤示意：").removeprefix("成品参考：")
    if kind == "cover":
        direction = (
            "只展示一顿简单家常饭的整餐搭配，最多三种食物，画面有一个明确视觉中心，"
            "不要拼贴，不要同时出现多个制作步骤。"
        )
    elif kind == "ingredients":
        direction = "只展示食材准备和普通砧板小碗，不出现成品菜和烹饪动作。"
    elif kind == "step":
        direction = "只展示一个锅或一个碗中的单一步骤状态，不出现手部和第二个烹饪动作。"
    elif kind == "detail":
        direction = "只展示一个主菜或一碗主食的近景细节，背景简洁，不出现复杂摆盘。"
    else:
        direction = "只展示一个明确的菜品状态，构图简洁。"
    return (
        f"{COMMON_PROMPT} 当前画面主题：{subject}。{direction}"
        "不要文字、不要水印、不要商标、不要人物正脸、不要手部。"
    )


def replace_workflow_values(value: Any, values: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: replace_workflow_values(item, values) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_workflow_values(item, values) for item in value]
    if isinstance(value, str) and value.startswith("__") and value.endswith("__"):
        key = value[2:-2]
        if key not in values:
            raise PipelineError(f"工作流缺少变量：{key}")
        return values[key]
    return value


def render_workflow(
    profiles: dict[str, dict[str, Any]],
    profile_name: str,
    *,
    prompt: str,
    seed: int,
    filename_prefix: str,
) -> dict[str, Any]:
    profile = profiles.get(profile_name)
    if not profile:
        raise PipelineError(f"未知模型配置：{profile_name}")
    workflow_path = ROOT / str(profile["workflow"])
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    values = dict(profile.get("variables", {}))
    values.update(
        {
            "PROMPT": prompt,
            "NEGATIVE_PROMPT": NEGATIVE_PROMPT,
            "SEED": seed,
            "FILENAME_PREFIX": filename_prefix,
        }
    )
    rendered = replace_workflow_values(workflow, values)
    rendered_json = json.dumps(rendered, ensure_ascii=False)
    if "__" in rendered_json:
        raise PipelineError(f"工作流仍存在未替换变量：{workflow_path}")
    return rendered


def brightness_and_sharpness(image_path: Path) -> tuple[float, float, float]:
    require_pillow()
    assert Image is not None
    assert ImageFilter is not None
    assert ImageStat is not None
    with Image.open(image_path) as source:
        image = source.convert("RGB")
        gray = ImageOps.grayscale(image)
        brightness = ImageStat.Stat(gray).mean[0] / 255.0
        contrast = math.sqrt(ImageStat.Stat(gray).var[0]) / 255.0
        edges = gray.filter(ImageFilter.FIND_EDGES)
        sharpness = math.sqrt(ImageStat.Stat(edges).var[0]) / 255.0
    return brightness, contrast, sharpness


def detect_ocr_text(image_path: Path) -> str | None:
    try:
        import pytesseract

        assert Image is not None
        with Image.open(image_path) as image:
            text = pytesseract.image_to_string(image, lang="eng+chi_sim")
        return re.sub(r"\s+", " ", text).strip()
    except Exception:  # noqa: BLE001 - OCR is an optional guard
        return None


def score_candidate(
    image_path: Path,
    *,
    prompt: str,
    semantic_scorer: OptionalSemanticScorer,
) -> tuple[float, dict[str, Any], list[str], float | None, str | None]:
    require_pillow()
    assert Image is not None
    with Image.open(image_path) as source:
        image = source.convert("RGB")
        width, height = image.size
        hsv = image.convert("HSV")
        saturation = ImageStat.Stat(hsv).mean[1] / 255.0

    brightness, contrast, sharpness = brightness_and_sharpness(image_path)
    warnings: list[str] = []
    score = 0.0

    if width >= 1536 and height >= 1024:
        score += 30
    elif width >= 960 and height >= 640:
        score += 20
        warnings.append("未达到最终 1536x1024，后续会重新裁切放大")
    else:
        warnings.append(f"尺寸过低：{width}x{height}")

    if 0.28 <= brightness <= 0.78:
        score += 15
    else:
        warnings.append(f"曝光异常：平均亮度 {brightness:.2f}")

    score += min(contrast / 0.25, 1.0) * 15
    if sharpness < 0.08:
        warnings.append(f"画面可能偏糊：边缘清晰度 {sharpness:.2f}")
    score += min(sharpness / 0.17, 1.0) * 20

    if 0.12 <= saturation <= 0.72:
        score += 10
    else:
        warnings.append(f"色彩饱和度异常：{saturation:.2f}")

    ocr_text = detect_ocr_text(image_path)
    if ocr_text:
        warnings.append(f"检测到疑似图片文字：{ocr_text[:80]}")
        score -= 25
    else:
        score += 5

    semantic_score = semantic_scorer.score(image_path, prompt)
    if semantic_score is not None:
        normalized = max(0.0, min(1.0, (semantic_score + 0.1) / 0.42))
        score += normalized * 15

    metrics = {
        "width": width,
        "height": height,
        "brightness": round(brightness, 4),
        "contrast": round(contrast, 4),
        "sharpness": round(sharpness, 4),
        "saturation": round(saturation, 4),
    }
    return round(max(0.0, min(100.0, score)), 2), metrics, warnings, semantic_score, ocr_text


def postprocess_to_final(source_path: Path, target_path: Path) -> None:
    require_pillow()
    assert Image is not None
    assert ImageEnhance is not None
    assert ImageFilter is not None
    with Image.open(source_path) as source:
        image = source.convert("RGB")
        source_ratio = image.width / image.height
        target_ratio = 1.5
        if source_ratio > target_ratio:
            crop_width = int(image.height * target_ratio)
            left = (image.width - crop_width) // 2
            image = image.crop((left, 0, left + crop_width, image.height))
        elif source_ratio < target_ratio:
            crop_height = int(image.width / target_ratio)
            top = (image.height - crop_height) // 2
            image = image.crop((0, top, image.width, top + crop_height))
        image = image.resize((1536, 1024), Image.Resampling.LANCZOS)
        image = ImageEnhance.Color(image).enhance(1.03)
        image = ImageEnhance.Contrast(image).enhance(1.02)
        image = image.filter(ImageFilter.UnsharpMask(radius=1.6, percent=105, threshold=3))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(target_path, format="JPEG", quality=93, optimize=True, progressive=True)


def article_slug(article_path: Path) -> str:
    clean = re.sub(r"[^\w.-]+", "-", article_path.stem, flags=re.UNICODE).strip("-")
    return clean or "article"


def make_contact_sheet(candidates: list[Candidate], output_path: Path) -> None:
    require_pillow()
    assert Image is not None
    assert ImageDraw is not None
    if not candidates:
        return
    thumb_width, thumb_height = 320, 214
    columns = 3
    rows = math.ceil(len(candidates) / columns)
    sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + 30)), "white")
    draw = ImageDraw.Draw(sheet)
    for position, candidate in enumerate(candidates):
        with Image.open(candidate.path) as raw:
            thumb = ImageOps.fit(raw.convert("RGB"), (thumb_width, thumb_height), Image.Resampling.LANCZOS)
        x = (position % columns) * thumb_width
        y = (position // columns) * (thumb_height + 30)
        sheet.paste(thumb, (x, y))
        draw.text(
            (x + 6, y + thumb_height + 6),
            f"#{candidate.slot_index}-{candidate.candidate_index}  {candidate.score:.1f}",
            fill="black",
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="JPEG", quality=90, optimize=True)


def rewrite_article_paths(text: str, slots: list[ImageSlot]) -> str:
    replacements = {slot.reference: slot.target_relative for slot in slots}

    def replace(match: re.Match[str]) -> str:
        reference = match.group("ref")
        target = replacements.get(reference)
        if not target:
            return match.group(0)
        return f"![{match.group('alt')}]({target})"

    return IMAGE_MARKDOWN_RE.sub(replace, text)


def write_manifest(
    *,
    article_path: Path,
    profile: str,
    candidates: list[Candidate],
    failures: list[str],
    semantic_scorer: OptionalSemanticScorer,
) -> Path:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REVIEW_DIR / f"{article_slug(article_path)}.json"
    payload = {
        "article": str(article_path),
        "profile": profile,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "semantic_scorer": {
            "mode": semantic_scorer.mode,
            "available": semantic_scorer.available,
            "error": semantic_scorer.error,
        },
        "candidates": [asdict(candidate) for candidate in candidates],
        "failures": failures,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def append_provenance(
    *,
    article_path: Path,
    profile: str,
    candidates: list[Candidate],
    selected: dict[int, Candidate],
) -> None:
    source_path = AI_IMAGE_DIR / "SOURCES.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        "# AI 图片来源记录",
        "",
        "本目录图片由本地 ComfyUI 工作流生成，不从内容平台下载或二改。",
        "",
    ]
    if source_path.exists():
        existing = source_path.read_text(encoding="utf-8").rstrip()
        if existing:
            lines = [existing, ""]
    lines.extend(
        [
            f"## {timestamp}",
            f"- 文章：`{article_path.name}`",
            f"- 模型配置：`{profile}`",
            "- 工作流：FLUX.2 Klein 4B 优先，SDXL Lightning 为显存不足降级。",
        ]
    )
    for slot_index, candidate in sorted(selected.items()):
        prompt_hash = hashlib.sha256(candidate.prompt.encode("utf-8")).hexdigest()[:12]
        lines.append(
            f"- 图片 #{slot_index}：`{Path(candidate.path).name}`；"
            f"候选 #{candidate.candidate_index}；提示词摘要哈希 `{prompt_hash}`"
        )
    source_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def candidate_seed(base_seed: int | None, slot_index: int, candidate_index: int) -> int:
    if base_seed is None:
        return random.SystemRandom().randint(1, 2**63 - 1)
    return base_seed + slot_index * 100 + candidate_index


def generate_candidate(
    *,
    client: ComfyClient,
    profiles: dict[str, dict[str, Any]],
    profile: str,
    slot: ImageSlot,
    candidate_index: int,
    seed: int,
    article_path: Path,
    candidate_root: Path,
    max_wait_seconds: int,
    poll_seconds: float,
    semantic_scorer: OptionalSemanticScorer,
) -> Candidate:
    prompt = build_prompt(slot)
    filename_prefix = (
        f"food_home_cooking/{article_slug(article_path)}/"
        f"slot-{slot.index:02d}-candidate-{candidate_index}"
    )
    workflow = render_workflow(
        profiles,
        profile,
        prompt=prompt,
        seed=seed,
        filename_prefix=filename_prefix,
    )
    prompt_id = client.queue(workflow)
    images = client.wait_for_images(
        prompt_id,
        max_wait_seconds=max_wait_seconds,
        poll_seconds=poll_seconds,
    )
    destination = candidate_root / f"slot-{slot.index:02d}-candidate-{candidate_index}.png"
    client.download_image(images[-1], destination)
    score, metrics, warnings, semantic_score, ocr_text = score_candidate(
        destination,
        prompt=prompt,
        semantic_scorer=semantic_scorer,
    )
    return Candidate(
        slot_index=slot.index,
        candidate_index=candidate_index,
        profile=profile,
        seed=seed,
        prompt=prompt,
        path=str(destination),
        score=score,
        metrics=metrics,
        warnings=warnings,
        semantic_score=semantic_score,
        ocr_text=ocr_text,
    )


def generate_slot(
    *,
    client: ComfyClient,
    profiles: dict[str, dict[str, Any]],
    profile: str,
    fallback_profile: str | None,
    slot: ImageSlot,
    candidate_count: int,
    base_seed: int | None,
    article_path: Path,
    candidate_root: Path,
    max_wait_seconds: int,
    poll_seconds: float,
    semantic_scorer: OptionalSemanticScorer,
) -> tuple[list[Candidate], list[str]]:
    candidates: list[Candidate] = []
    failures: list[str] = []
    profiles_to_try = [profile]
    if fallback_profile and fallback_profile != profile:
        profiles_to_try.append(fallback_profile)

    for candidate_index in range(1, candidate_count + 1):
        seed = candidate_seed(base_seed, slot.index, candidate_index)
        candidate: Candidate | None = None
        for profile_name in profiles_to_try:
            try:
                candidate = generate_candidate(
                    client=client,
                    profiles=profiles,
                    profile=profile_name,
                    slot=slot,
                    candidate_index=candidate_index,
                    seed=seed,
                    article_path=article_path,
                    candidate_root=candidate_root,
                    max_wait_seconds=max_wait_seconds,
                    poll_seconds=poll_seconds,
                    semantic_scorer=semantic_scorer,
                )
                break
            except PipelineError as exc:
                failures.append(
                    f"图片 #{slot.index} 候选 {candidate_index} 使用 {profile_name} 失败：{exc}"
                )
        if candidate:
            candidates.append(candidate)
    return candidates, failures


def run(args: argparse.Namespace) -> int:
    require_pillow()
    article_path = args.article.resolve()
    if not article_path.exists():
        raise PipelineError(f"文章不存在：{article_path}")
    if article_path.parent != ROOT / "articles":
        raise PipelineError(f"文章必须位于 {ROOT / 'articles'}：{article_path}")

    source_text, slots = extract_image_slots(article_path)
    if args.limit_slots is not None:
        slots = slots[: args.limit_slots]
    profiles = load_profiles()
    if args.profile not in profiles:
        raise PipelineError(f"模型配置不存在：{args.profile}")
    if args.fallback_profile and args.fallback_profile not in profiles:
        raise PipelineError(f"降级模型配置不存在：{args.fallback_profile}")

    if args.dry_run:
        print(f"DRY RUN article={article_path.name} slots={len(slots)} profile={args.profile}")
        for slot in slots:
            print(f"#{slot.index} {slot.target_relative}")
            print(build_prompt(slot))
        return 0

    client = ComfyClient(args.endpoint, timeout=args.request_timeout)
    system_stats = client.preflight()
    devices = system_stats.get("devices", [])
    if devices:
        device_name = devices[0].get("name", "unknown")
        print(f"ComfyUI connected: {device_name}")
    else:
        print("ComfyUI connected")

    candidate_root = CANDIDATE_DIR / article_slug(article_path)
    candidate_root.mkdir(parents=True, exist_ok=True)
    semantic_scorer = OptionalSemanticScorer(args.semantic_check)
    all_candidates: list[Candidate] = []
    failures: list[str] = []
    selected: dict[int, Candidate] = {}

    for slot in slots:
        if slot.target_path.exists() and not args.overwrite:
            print(f"Skip existing final image: {slot.target_path.name}")
            continue
        print(f"Generating image #{slot.index}/{len(slots)}: {slot.alt}")
        candidates, slot_failures = generate_slot(
            client=client,
            profiles=profiles,
            profile=args.profile,
            fallback_profile=None if args.no_fallback else args.fallback_profile,
            slot=slot,
            candidate_count=args.candidate_count,
            base_seed=args.seed,
            article_path=article_path,
            candidate_root=candidate_root,
            max_wait_seconds=args.max_wait,
            poll_seconds=args.poll_seconds,
            semantic_scorer=semantic_scorer,
        )
        all_candidates.extend(candidates)
        failures.extend(slot_failures)
        valid = [candidate for candidate in candidates if candidate.score >= args.min_score]
        if valid:
            selected[slot.index] = max(valid, key=lambda candidate: candidate.score)
        else:
            failures.append(
                f"图片 #{slot.index} 没有通过质量门（阈值 {args.min_score}），"
                "文章路径未写回。"
            )

    contact_sheet_path = REVIEW_DIR / f"{article_slug(article_path)}.jpg"
    make_contact_sheet(all_candidates, contact_sheet_path)
    manifest_path = write_manifest(
        article_path=article_path,
        profile=args.profile,
        candidates=all_candidates,
        failures=failures,
        semantic_scorer=semantic_scorer,
    )

    pending = [slot for slot in slots if not slot.target_path.exists() or args.overwrite]
    if failures or len(selected) != len(pending):
        print(f"FAILED: {len(failures)} issue(s). Article was not changed.")
        print(f"Candidate sheet: {contact_sheet_path}")
        print(f"Manifest: {manifest_path}")
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1

    for slot in pending:
        candidate = selected[slot.index]
        postprocess_to_final(Path(candidate.path), slot.target_path)
        print(f"Finalized: {slot.target_path.name} (score {candidate.score:.1f})")

    article_path.write_text(rewrite_article_paths(source_text, slots), encoding="utf-8")
    append_provenance(
        article_path=article_path,
        profile=args.profile,
        candidates=all_candidates,
        selected=selected,
    )
    print(f"PASS: updated {article_path.name}")
    print(f"Candidate sheet: {contact_sheet_path}")
    print(f"Manifest: {manifest_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate local AI illustrations for a food article through ComfyUI."
    )
    parser.add_argument("article", type=Path, help="article path under food_home_cooking/articles")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="ComfyUI endpoint")
    parser.add_argument("--profile", default="flux2_klein", help="primary model profile")
    parser.add_argument(
        "--fallback-profile",
        default="sdxl_lightning",
        help="profile used after a primary ComfyUI generation failure",
    )
    parser.add_argument("--no-fallback", action="store_true", help="do not use fallback profile")
    parser.add_argument("--candidate-count", type=int, default=3, help="candidates per image slot")
    parser.add_argument("--limit-slots", type=int, help="only process the first N image slots")
    parser.add_argument("--min-score", type=float, default=56.0, help="minimum automatic selection score")
    parser.add_argument("--seed", type=int, help="base seed; default uses secure random seeds")
    parser.add_argument("--max-wait", type=int, default=600, help="maximum wait per ComfyUI job")
    parser.add_argument("--poll-seconds", type=float, default=1.5, help="ComfyUI history poll interval")
    parser.add_argument("--request-timeout", type=int, default=60, help="HTTP request timeout")
    parser.add_argument(
        "--semantic-check",
        choices=["auto", "off", "require"],
        default="auto",
        help="use OpenCLIP if installed; require fails when it is unavailable",
    )
    parser.add_argument("--overwrite", action="store_true", help="replace existing final local images")
    parser.add_argument("--dry-run", action="store_true", help="print prompts without contacting ComfyUI")
    args = parser.parse_args()
    if args.candidate_count < 1:
        parser.error("--candidate-count must be at least 1")
    if args.limit_slots is not None and args.limit_slots < 1:
        parser.error("--limit-slots must be at least 1")
    if args.max_wait < 1:
        parser.error("--max-wait must be positive")
    try:
        return run(args)
    except PipelineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
