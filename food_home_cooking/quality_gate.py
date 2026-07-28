#!/usr/bin/env python3
"""Quality gate for home-cooking WeChat drafts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - reported as a quality-gate error
    Image = None


ROOT = Path(__file__).resolve().parent
KB_PATH = Path(r"D:\自媒体\知识库\01-公众号文章\美食公众号文章\暖暖小厨")

FORBIDDEN = ["暖暖", "暖暖小厨", "暖暖小厨房"]
MEAL_WORDS = ["早餐", "午餐", "晚餐", "工作餐", "宵夜", "早午餐"]
MONEY_RE = re.compile(r"\d+\s*元")
TIME_RE = re.compile(r"\d+\s*分钟")
IMAGE_RE = re.compile(r"^\s*!\[[^\]]*\]\([^)]+\)\s*$")
IMAGE_ALT_RE = re.compile(r"^\s*!\[([^\]]*)\]\([^)]+\)\s*$")
IMAGE_REF_RE = re.compile(r"^\s*!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)\s*$")
TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
AI_ALT_HINTS = ["示意图", "参考图", "搭配图", "步骤示意", "成品参考"]
MISLEADING_IMAGE_WORDS = ["实拍图", "我拍的", "现场图", "真实厨房全过程", "原图"]
PLATFORM_WORDS = ["小红书", "微博", "抖音", "公众号截图", "视频号"]
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_title(text: str) -> str:
    match = TITLE_RE.search(text)
    if match:
        return match.group(1).strip().strip('"')
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def strip_frontmatter(text: str) -> str:
    return re.sub(r"^---[\s\S]*?---", "", text).strip()


def chinese_len(text: str) -> int:
    return len(CHINESE_RE.findall(text))


def image_lines(lines: list[str]) -> list[int]:
    return [i for i, line in enumerate(lines) if IMAGE_RE.match(line)]


def image_alts(lines: list[str]) -> list[str]:
    alts: list[str] = []
    for line in lines:
        match = IMAGE_ALT_RE.match(line)
        if match:
            alts.append(match.group(1).strip())
    return alts


def image_references(lines: list[str]) -> list[tuple[int, str, str]]:
    refs: list[tuple[int, str, str]] = []
    for index, line in enumerate(lines, start=1):
        match = IMAGE_REF_RE.match(line)
        if match:
            refs.append((index, match.group(1).strip(), match.group(2).strip()))
    return refs


def is_within_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


def check_image_files(
    article_path: Path,
    references: list[tuple[int, str, str]],
    *,
    image_mode: str,
) -> tuple[list[str], list[str], list[dict[str, object]]]:
    errors: list[str] = []
    warnings: list[str] = []
    files: list[dict[str, object]] = []
    if not references:
        return errors, warnings, files

    if Image is None:
        return ["缺少 Pillow，无法验证本地图片。请安装 requirements-imagegen.txt"], warnings, files

    min_width, min_height = (1536, 1024) if image_mode == "ai" else (600, 400)
    for line_number, alt, reference in references:
        if re.match(r"^[a-z][a-z0-9+.-]*://", reference, flags=re.IGNORECASE):
            errors.append(f"第 {line_number} 行图片必须是本地文件，不允许远程地址：{reference}")
            continue

        image_path = (article_path.parent / reference).resolve()
        if not is_within_root(image_path):
            errors.append(f"第 {line_number} 行图片路径超出 food_home_cooking：{reference}")
            continue
        if image_path.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
            errors.append(f"第 {line_number} 行图片格式不支持：{reference}")
            continue
        if not image_path.exists():
            errors.append(f"第 {line_number} 行图片文件不存在：{reference}")
            continue

        try:
            with Image.open(image_path) as image:
                image.verify()
            with Image.open(image_path) as image:
                width, height = image.size
                image_format = image.format or image_path.suffix.lstrip(".").upper()
        except Exception as exc:  # noqa: BLE001 - present the damaged local asset
            errors.append(f"第 {line_number} 行图片无法读取：{reference} ({exc})")
            continue

        if width < min_width or height < min_height:
            errors.append(
                f"第 {line_number} 行图片分辨率不足：{reference} 为 {width}x{height}，"
                f"至少需要 {min_width}x{min_height}"
            )
        if image_mode == "ai" and (width != 1536 or height != 1024):
            warnings.append(
                f"第 {line_number} 行 AI 图片建议输出为 1536x1024，当前 {width}x{height}"
            )
        files.append(
            {
                "line": line_number,
                "alt": alt,
                "reference": reference,
                "path": str(image_path),
                "width": width,
                "height": height,
                "format": image_format,
            }
        )
    return errors, warnings, files


def adjacent_image_pairs(lines: list[str]) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    imgs = image_lines(lines)
    for prev, cur in zip(imgs, imgs[1:]):
        between = [line for line in lines[prev + 1 : cur] if line.strip()]
        if not between:
            pairs.append((prev + 1, cur + 1))
    return pairs


def load_kb_titles() -> set[str]:
    if not KB_PATH.exists():
        return set()
    titles: set[str] = set()
    for path in KB_PATH.glob("*.md"):
        titles.add(path.stem.split(" - ", 1)[-1].strip())
        text = read_text(path)
        title = extract_title(text)
        if title:
            titles.add(title)
    return titles


def detect_title_type(title: str) -> str:
    if "江苏" in title or any(x in title for x in ["毛豆", "茭白", "丝瓜", "苋菜", "河虾", "鲫鱼", "梅雨"]):
        return "江苏家常型"
    if "河南" in title or any(x in title for x in ["捞面", "烩面", "蒸菜", "发面", "包子", "花卷"]):
        return "河南/北方面食型"
    if "网友" in title or "值吗" in title or "贵吗" in title:
        return "网友争议型"
    if any(x in title for x in ["孩子", "老公", "家人"]):
        return "孩子/家人爱吃型"
    if TIME_RE.search(title) or any(x in title for x in ["快手", "快速", "搞定"]):
        return "快手型"
    if MONEY_RE.search(title) or any(x in title for x in ["省钱", "划算", "外卖"]):
        return "省钱型"
    return "普通晒餐型"


def check(path: Path, image_mode: str = "real") -> dict:
    text = read_text(path)
    body = strip_frontmatter(text)
    lines = text.splitlines()
    title = extract_title(text)
    kb_titles = load_kb_titles()

    errors: list[str] = []
    warnings: list[str] = []

    if not title:
        errors.append("缺少 frontmatter title 或 H1 标题")
    elif not 18 <= chinese_len(title) <= 36:
        errors.append(f"标题中文长度应为 18-36，当前 {chinese_len(title)}")

    title_infos = 0
    title_infos += int(any(word in title for word in MEAL_WORDS))
    title_infos += int(bool(MONEY_RE.search(title)))
    title_infos += int(bool(TIME_RE.search(title)))
    title_infos += int(bool(re.search(r"\d+\s*(样|道|菜|汤|主食)", title)))
    title_infos += int(any(x in title for x in ["一家三口", "两个人", "夫妻", "一个人", "孩子", "老公"]))
    title_infos += int(any(x in title for x in ["舒服", "下饭", "清爽", "省事", "好吃", "不油腻"]))
    if title and title_infos < 2:
        errors.append("标题至少需要 2 个具体信息：人数/餐次/金额/时间/菜品数量/口感等")

    if title in kb_titles:
        errors.append("标题与暖暖小厨知识库已有标题重复")

    for word in FORBIDDEN:
        if word in body or word in title:
            errors.append(f"出现禁用署名或原博主标识：{word}")

    refs = image_references(lines)
    img_count = len(refs)
    alts = image_alts(lines)
    image_errors, image_warnings, image_files = check_image_files(
        path,
        refs,
        image_mode=image_mode,
    )
    errors.extend(image_errors)
    warnings.extend(image_warnings)
    if image_mode == "ai":
        if not 5 <= img_count <= 8:
            warnings.append(f"AI 示意图模式建议 5-8 张，当前 {img_count}")
        if img_count > 12:
            errors.append(f"AI 示意图模式不建议堆大量步骤图，当前 {img_count} 张，超过 12 张")
        if alts and not any(any(hint in alt for hint in AI_ALT_HINTS) for alt in alts):
            warnings.append("AI 示意图模式建议至少部分图片 alt 使用“示意图/参考图/步骤示意”等中性表述")
        for alt in alts:
            for word in MISLEADING_IMAGE_WORDS:
                if word in alt:
                    errors.append(f"AI 示意图模式图片 alt 不应冒充实拍：{word}")
            for word in PLATFORM_WORDS:
                if word in alt:
                    errors.append(f"图片 alt 出现平台来源词，确认未搬运二改：{word}")
    else:
        if not 16 <= img_count <= 22:
            warnings.append(f"实拍模式图片数建议 16-22 张，当前 {img_count}")

    adjacent = adjacent_image_pairs(lines)
    if adjacent:
        errors.append(f"存在连续图片，中间缺少文字：{adjacent}")

    if not MONEY_RE.search(body):
        warnings.append("正文缺少花费金额")
    if "花费" not in body and "算下来" not in body and "元" not in body:
        warnings.append("省钱/晒餐文章建议加入食材花费明细")
    if len(MONEY_RE.findall(text)) > 8:
        warnings.append("金额出现次数偏多，确认是否显得刻意省钱")

    numbered_steps = len(re.findall(r"(?m)^\s*\d+、", body))
    if numbered_steps < 8:
        warnings.append(f"步骤编号建议不少于 8 个，当前 {numbered_steps}")
    if "【食材准备】" not in body and "【食材明细】" not in body:
        warnings.append("缺少【食材准备】或【食材明细】模块")

    if not TIME_RE.search(body):
        warnings.append("正文缺少耗时信息")

    if not any(x in body for x in ["有点老", "卖相", "做多", "没提前", "稍微", "临时", "不够", "有点干"]):
        warnings.append("缺少小失误或不完美细节")

    if not any(x in body for x in ["你家", "大家", "你们", "觉得"]):
        warnings.append("结尾缺少轻互动")

    if "江苏" in body and "河南" in body:
        warnings.append("同篇同时出现江苏和河南，确认地域元素是否自然")

    score = 100 - len(errors) * 20 - len(warnings) * 5
    score = max(0, min(100, score))

    return {
        "file": str(path),
        "title": title,
        "title_type": detect_title_type(title),
        "image_mode": image_mode,
        "score": score,
        "image_count": img_count,
        "image_files": image_files,
        "numbered_steps": numbered_steps,
        "adjacent_image_pairs": adjacent,
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check home-cooking article quality.")
    parser.add_argument("article", type=Path)
    parser.add_argument(
        "--image-mode",
        choices=["real", "ai"],
        default="real",
        help="real=16-22 self-shot images; ai=5-8 AI original reference images",
    )
    parser.add_argument("--json", action="store_true", help="print JSON report")
    args = parser.parse_args()

    report = check(args.article, image_mode=args.image_mode)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"{status} score={report['score']} title_type={report['title_type']} image_mode={report['image_mode']}")
        print(f"title: {report['title']}")
        print(f"images: {report['image_count']}")
        for error in report["errors"]:
            print(f"ERROR: {error}")
        for warning in report["warnings"]:
            print(f"WARN: {warning}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
