"""Generate Wanxiang persona scenes and sync finished images into image_pool.txt."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib import error, request

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


BASE_DIR = Path(__file__).resolve().parent
BACKLOG_PATH = BASE_DIR / "images" / "persona" / "wanxiang_scene_backlog.md"
SCENES_DIR = BASE_DIR / "images" / "persona" / "scenes"
IMAGE_POOL_PATH = BASE_DIR / "image_pool.txt"
PROMPT_EXPORT_PATH = BASE_DIR / "images" / "persona" / "wanxiang_generation_tasks.md"
DEFAULT_MASTER_REFERENCE = BASE_DIR / "images" / "persona" / "master" / "persona_master_glam_v3.png"
DEFAULT_MASTER_SEED_REFERENCE = BASE_DIR / "images" / "persona" / "master" / "persona_master_natural_source.png"
DEFAULT_WANXIANG_MODEL = "wan2.6-image"
DEFAULT_WANXIANG_SIZE = "2K"
DEFAULT_TIMEOUT = 180

MIN_WIDTH = 900
MIN_HEIGHT = 600
MIN_ASPECT = 1.25
MAX_ASPECT = 1.95
NEGATIVE_PROMPT = (
    "低俗，露点，裸露敏感部位，透明衣物，内衣特写，色情姿势，挑逗动作，"
    "未成年，幼态，学生制服，年龄偏大，老态，疲惫憔悴，法令纹重，眼袋重，"
    "露点，裸露敏感部位，内衣特写，透明衣物，夸张解剖比例，低俗挑逗姿势，"
    "成熟夜店风，表情僵硬，表情单调，所有图片同一表情，夸张浓妆，塑料皮肤，过度磨皮，夸张滤镜，畸形五官，遮挡脸，"
    "墨镜，帽子，口罩，影楼写真，AI感，水印，文字"
)
YOUTH_MASTER_PROMPT = (
    "以参考图的脸型、五官比例和齐肩黑发为唯一身份基础，保持 28-32 岁亚洲成年女性；"
    "正面高清生活人像，精致日常妆容，清晰眉形，克制眼线，暖色腮红，玫瑰豆沙唇，五官无遮挡，"
    "酒红方领修身针织上衣，肩颈和锁骨线条自然，健康曲线，温暖直视，自信轻熟，"
    "柔和窗光，干净暖色生活背景，真实毛孔和皮肤纹理，眼睛和人脸锐利对焦，高分辨率，"
    "完整着装，不幼态，不低俗，不夸张解剖比例，不像影楼写真，无文字无水印"
)


def load_env_files() -> None:
    """Load simple KEY=VALUE pairs from local .env files without overriding the shell."""
    for env_path in (BASE_DIR.parent / ".env", BASE_DIR / ".env"):
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().lstrip("\ufeff")
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


@dataclass(frozen=True)
class WanxiangTask:
    index: int
    name: str
    filename: str
    uses: tuple[str, ...]
    prompt: str

    @property
    def image_path(self) -> Path:
        return SCENES_DIR / self.filename

    @property
    def pool_ref(self) -> str:
        return f"../images/persona/scenes/{self.filename}"


def modernize_legacy_prompt(value: str) -> str:
    """将旧清单中的幼态化表述升级为 v3 轻熟人设。"""
    replacements = (
        ("情感号_青春靓丽_01", "情感号_轻熟妩媚_03"),
        ("22 岁", "30 岁"),
        ("22岁", "30岁"),
        ("自然淡妆", "精致日常妆容"),
        ("青春活力", "轻熟自信"),
        ("元气满满", "神态生动"),
        ("元气自然", "自信自然"),
        ("元气笑容", "自信微笑"),
        ("初入职场清爽感", "成熟通勤质感"),
    )
    result = value
    for before, after in replacements:
        result = result.replace(before, after)
    return (
        "v3统一人设：30 岁虚构亚洲成年女性，精致日常妆容，"
        "轻熟妩媚、自信温暖，健康自然曲线，人脸和眼睛锐利对焦，"
        "完整着装，无低俗姿势；" + result
    )


def parse_tasks(backlog_path: Path) -> list[WanxiangTask]:
    text = backlog_path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^###\s+(\d+)\.\s+(.+?)\s*$", text))
    tasks: list[WanxiangTask] = []

    for position, match in enumerate(matches):
        start = match.end()
        end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
        block = text[start:end]

        filename_match = re.search(r"文件名：\s*```text\s*(.*?)\s*```", block, re.S)
        uses_match = re.search(r"用途：(.+)", block)
        prompt_match = re.search(r"提示词：\s*```text\s*(.*?)\s*```", block, re.S)

        if not filename_match or not uses_match or not prompt_match:
            continue

        uses = tuple(re.findall(r"`(COVER_[A-Z_]+)`", uses_match.group(1)))
        tasks.append(
            WanxiangTask(
                index=int(match.group(1)),
                name=match.group(2).strip(),
                filename=filename_match.group(1).strip(),
                uses=uses,
                prompt=modernize_legacy_prompt(prompt_match.group(1).strip()),
            )
        )

    return tasks


def validate_image(path: Path) -> list[str]:
    if not path.exists():
        return [f"缺失：{path.name}"]
    if path.stat().st_size <= 0:
        return [f"空文件：{path.name}"]
    if Image is None:
        return []

    try:
        with Image.open(path) as image:
            width, height = image.size
    except OSError as exc:
        return [f"无法读取：{path.name} ({exc})"]

    errors: list[str] = []
    aspect = width / height if height else 0
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        errors.append(f"尺寸过小：{path.name} 为 {width}x{height}，至少 {MIN_WIDTH}x{MIN_HEIGHT}")
    if aspect < MIN_ASPECT or aspect > MAX_ASPECT:
        errors.append(f"比例不适合：{path.name} 为 {width}x{height}，宽高比 {aspect:.2f}")
    return errors


def export_prompts(tasks: list[WanxiangTask], export_path: Path) -> None:
    lines = [
        "# 通义万相批量生成任务",
        "",
        "> v3：使用 28-32 岁、精致日常妆容、轻熟妩媚的虚构成年女性与 persona_master_glam_v3.png。",
        "",
        "使用方式：按每条提示词里的主体名称生成；导出后按目标文件名保存到 `emotion_women/images/persona/scenes/`。",
        "",
    ]

    for task in tasks:
        lines.extend(
            [
                f"## {task.index}. {task.name}",
                "",
                f"- 目标文件：`emotion_women/images/persona/scenes/{task.filename}`",
                f"- 入池栏目：{', '.join(f'`{use}`' for use in task.uses)}",
                "",
                "```text",
                task.prompt,
                "```",
                "",
            ]
        )

    export_path.write_text("\n".join(lines), encoding="utf-8")


def data_uri(path: Path) -> str:
    content_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def wanxiang_base_url() -> str:
    explicit = os.getenv("DASHSCOPE_BASE_URL", "").strip().rstrip("/")
    if explicit:
        return explicit

    workspace_id = os.getenv("DASHSCOPE_WORKSPACE_ID", "").strip()
    region = os.getenv("DASHSCOPE_REGION", "cn-beijing").strip() or "cn-beijing"
    if workspace_id:
        return f"https://{workspace_id}.{region}.maas.aliyuncs.com/api/v1"

    return "https://dashscope.aliyuncs.com/api/v1"


def api_prompt(task: WanxiangTask) -> str:
    prompt = re.sub(r"^调用主体库：[^，]+，?", "", task.prompt).strip()
    return (
        "参考图中的同一位 30 岁虚构亚洲成年女性，保持五官、脸型、发型、肤色、年龄和整体气质一致；"
        "使用清晰眉形、克制眼线、暖色腮红和玫瑰豆沙唇的精致日常妆容，轻熟妩媚、自信温暖，健康自然曲线；"
        "只改变场景、服装、动作和光线，人脸和眼睛必须锐利对焦。"
        f"{prompt}。构图为公众号封面可用横图，人物脸部不要贴边，画面干净，无文字无水印。"
    )


def find_image_urls(value: object) -> list[str]:
    urls: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"image", "url"} and isinstance(nested, str):
                if nested.startswith(("http://", "https://", "data:image/")):
                    urls.append(nested)
            else:
                urls.extend(find_image_urls(nested))
    elif isinstance(value, list):
        for item in value:
            urls.extend(find_image_urls(item))
    return urls


def call_wanxiang(
    *,
    task: WanxiangTask,
    api_key: str,
    reference_image: Path,
    model: str,
    size: str,
    timeout: int,
) -> str:
    endpoint = f"{wanxiang_base_url()}/services/aigc/multimodal-generation/generation"
    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": data_uri(reference_image)},
                        {"text": api_prompt(task)},
                    ],
                }
            ]
        },
        "parameters": {
            "negative_prompt": NEGATIVE_PROMPT,
            "n": 1,
            "size": size,
            "watermark": False,
        },
    }
    req = request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            response_data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"万相 API 请求失败：HTTP {exc.code} {detail}") from exc

    urls = find_image_urls(response_data)
    if not urls:
        raise RuntimeError(f"万相 API 未返回图片链接：{json.dumps(response_data, ensure_ascii=False)[:1000]}")
    return urls[0]


def call_wanxiang_text(
    *,
    prompt: str,
    api_key: str,
    model: str,
    size: str,
    timeout: int,
) -> str:
    endpoint = f"{wanxiang_base_url()}/services/aigc/multimodal-generation/generation"
    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"text": prompt},
                    ],
                }
            ]
        },
        "parameters": {
            "negative_prompt": NEGATIVE_PROMPT,
            "n": 1,
            "size": size,
            "watermark": False,
        },
    }
    req = request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            response_data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"万相 API 请求失败：HTTP {exc.code} {detail}") from exc

    urls = find_image_urls(response_data)
    if not urls:
        raise RuntimeError(f"万相 API 未返回图片链接：{json.dumps(response_data, ensure_ascii=False)[:1000]}")
    return urls[0]


def call_wanxiang_reference(
    *,
    prompt: str,
    api_key: str,
    reference_image: Path,
    model: str,
    size: str,
    timeout: int,
) -> str:
    endpoint = f"{wanxiang_base_url()}/services/aigc/multimodal-generation/generation"
    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": data_uri(reference_image)},
                        {"text": prompt},
                    ],
                }
            ]
        },
        "parameters": {
            "negative_prompt": NEGATIVE_PROMPT,
            "n": 1,
            "size": size,
            "watermark": False,
        },
    }
    req = request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            response_data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"万相 API 请求失败：HTTP {exc.code} {detail}") from exc

    urls = find_image_urls(response_data)
    if not urls:
        raise RuntimeError(f"万相 API 未返回图片链接：{json.dumps(response_data, ensure_ascii=False)[:1000]}")
    return urls[0]


def download_bytes(url: str, timeout: int) -> bytes:
    if url.startswith("data:image/"):
        _, encoded = url.split(",", 1)
        return base64.b64decode(encoded)
    req = request.Request(url, headers={"User-Agent": "emotion-women-wanxiang-pool/1.0"})
    with request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def save_jpeg(image_bytes: bytes, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if Image is None:
        output_path.write_bytes(image_bytes)
        return
    with Image.open(BytesIO(image_bytes)) as image:
        image.convert("RGB").save(output_path, format="JPEG", quality=94, optimize=True)


def generate_wanxiang_images(
    tasks: list[WanxiangTask],
    *,
    reference_image: Path,
    model: str,
    size: str,
    overwrite: bool,
    limit: int | None,
    timeout: int,
    interval: float,
) -> tuple[int, list[str]]:
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        return 0, [
            "缺少环境变量 DASHSCOPE_API_KEY。请先在当前终端设置后重试，例如："
            "$env:DASHSCOPE_API_KEY='你的DashScope API Key'"
        ]
    if not reference_image.exists():
        return 0, [f"参考图不存在：{reference_image}"]

    selected = tasks[:limit] if limit else tasks
    generated = 0
    messages: list[str] = []
    for task in selected:
        if task.image_path.exists() and not overwrite:
            messages.append(f"跳过已存在：{task.filename}")
            continue
        try:
            image_url = call_wanxiang(
                task=task,
                api_key=api_key,
                reference_image=reference_image,
                model=model,
                size=size,
                timeout=timeout,
            )
            save_jpeg(download_bytes(image_url, timeout), task.image_path)
            errors = validate_image(task.image_path)
            if errors:
                messages.extend(errors)
                continue
            generated += 1
            messages.append(f"已生成：{task.filename}")
            if interval > 0:
                time.sleep(interval)
        except Exception as exc:  # noqa: BLE001 - keep batch moving and report each failed scene
            messages.append(f"生成失败：{task.filename} ({exc})")
    return generated, messages


def generate_master_reference(
    *,
    output_path: Path,
    model: str,
    size: str,
    overwrite: bool,
    timeout: int,
) -> tuple[bool, str]:
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        return False, "缺少环境变量 DASHSCOPE_API_KEY"
    if output_path.exists() and not overwrite:
        return True, f"跳过已存在基准图：{output_path}"
    if not DEFAULT_MASTER_SEED_REFERENCE.exists():
        return False, f"基准种子图不存在：{DEFAULT_MASTER_SEED_REFERENCE}"
    try:
        image_url = call_wanxiang_reference(
            prompt=YOUTH_MASTER_PROMPT,
            api_key=api_key,
            reference_image=DEFAULT_MASTER_SEED_REFERENCE,
            model=model,
            size=size,
            timeout=timeout,
        )
        save_jpeg(download_bytes(image_url, timeout), output_path)
        errors = validate_image(output_path)
        if errors:
            return False, "；".join(errors)
        return True, f"已生成轻熟妩媚基准图：{output_path}"
    except Exception as exc:  # noqa: BLE001
        return False, f"生成轻熟妩媚基准图失败：{exc}"


def section_key(line: str) -> str | None:
    if not line.startswith("## "):
        return None
    title = line[3:].strip()
    return title.split("（", 1)[0].strip()


def sync_image_pool(tasks: list[WanxiangTask], pool_path: Path) -> tuple[int, list[str]]:
    lines = pool_path.read_text(encoding="utf-8").splitlines()
    valid_refs_by_section: dict[str, list[str]] = {}
    messages: list[str] = []

    for task in tasks:
        errors = validate_image(task.image_path)
        if errors:
            messages.extend(errors)
            continue
        for use in task.uses:
            valid_refs_by_section.setdefault(use, []).append(task.pool_ref)

    if not valid_refs_by_section:
        return 0, messages

    existing_by_section: dict[str, set[str]] = {}
    current: str | None = None
    for raw in lines:
        key = section_key(raw)
        if key:
            current = key
            existing_by_section.setdefault(current, set())
            continue
        stripped = raw.strip()
        if current and stripped and not stripped.startswith("#"):
            existing_by_section.setdefault(current, set()).add(stripped)

    additions_by_section: dict[str, list[str]] = {}
    for section, refs in valid_refs_by_section.items():
        existing = existing_by_section.get(section, set())
        for ref in refs:
            if ref not in existing:
                additions_by_section.setdefault(section, []).append(ref)

    if not additions_by_section:
        return 0, messages

    output: list[str] = []
    current = None
    for raw in lines:
        key = section_key(raw)
        if key and current in additions_by_section:
            output.extend(additions_by_section[current])
        if key:
            current = key
        output.append(raw)

    if current in additions_by_section:
        output.extend(additions_by_section[current])

    pool_path.write_text("\n".join(output) + "\n", encoding="utf-8")
    added = sum(len(refs) for refs in additions_by_section.values())
    return added, messages


def main() -> int:
    load_env_files()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-prompts", action="store_true", help="导出通义万相复制用任务表")
    parser.add_argument("--generate-master", action="store_true", help="生成 28-32 岁轻熟妩媚基准参考图")
    parser.add_argument("--generate-wanxiang", action="store_true", help="调用通义万相 API 生成缺失的人设场景图")
    parser.add_argument("--sync", action="store_true", help="把已存在且合格的人设图写入 image_pool.txt")
    parser.add_argument("--strict", action="store_true", help="存在缺失或不合格图片时返回失败")
    parser.add_argument("--reference-image", type=Path, default=DEFAULT_MASTER_REFERENCE, help="同一人设参考图")
    parser.add_argument("--model", default=DEFAULT_WANXIANG_MODEL, help="通义万相模型名")
    parser.add_argument("--size", default=DEFAULT_WANXIANG_SIZE, help="通义万相输出尺寸，例如 2K")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在场景图")
    parser.add_argument("--limit", type=int, default=None, help="只生成前 N 张，便于先试跑")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="API 和下载超时时间，秒")
    parser.add_argument("--interval", type=float, default=1.0, help="每张图生成后的间隔秒数")
    args = parser.parse_args()

    run_all = not args.export_prompts and not args.generate_master and not args.generate_wanxiang and not args.sync
    tasks = parse_tasks(BACKLOG_PATH)
    if not tasks:
        print(f"未从清单解析到任务：{BACKLOG_PATH}")
        return 1

    if args.export_prompts or run_all:
        export_prompts(tasks, PROMPT_EXPORT_PATH)
        print(f"已导出通义万相生成任务：{PROMPT_EXPORT_PATH}")

    if args.generate_master:
        ok, message = generate_master_reference(
            output_path=args.reference_image,
            model=args.model,
            size=args.size,
            overwrite=args.overwrite,
            timeout=args.timeout,
        )
        print(message)
        if args.strict and not ok:
            return 1

    if args.generate_wanxiang:
        generated, generate_messages = generate_wanxiang_images(
            tasks,
            reference_image=args.reference_image,
            model=args.model,
            size=args.size,
            overwrite=args.overwrite,
            limit=args.limit,
            timeout=args.timeout,
            interval=args.interval,
        )
        print(f"已生成通义万相图片：{generated} 张")
        for message in generate_messages:
            print(f"- {message}")
        if args.strict and generated == 0 and generate_messages:
            return 1

    messages: list[str] = []
    added = 0
    if args.sync or args.generate_wanxiang or run_all:
        added, messages = sync_image_pool(tasks, IMAGE_POOL_PATH)
        print(f"已写入图池新增引用：{added} 条")
        if messages:
            print("待处理图片：")
            for message in messages:
                print(f"- {message}")

    if args.strict and messages:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
