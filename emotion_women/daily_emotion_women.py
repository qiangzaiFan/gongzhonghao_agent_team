#!/usr/bin/env python3
"""
情感女性公众号自动化生成与发布脚本
支持定时执行或立即执行，可自定义文章数量
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib import error, request
from zoneinfo import ZoneInfo

# 配置日志
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
MCP_CONFIG = BASE_DIR / ".mcp.json"
PUBLISH_THEME = "orangeheart"
ARTICLES_DIR = BASE_DIR / "articles"
IMAGES_DIR = BASE_DIR / "images"
IMAGE_POOL = BASE_DIR / "image_pool.txt"
DRAMA_IMAGE_POOL = BASE_DIR / "drama_image_pool.txt"
MAX_LOG_OUTPUT_CHARS = 4000
DEFAULT_PROVIDER = os.getenv("EMOTION_PROVIDER", "claude").strip().lower() or "claude"
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5").strip() or "gpt-5.5"
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "3600"))
OPENAI_ENABLE_WEB_SEARCH = os.getenv("OPENAI_ENABLE_WEB_SEARCH", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}

BASE_TOOLS = [
    "WebSearch",
    "WebFetch",
    "Read",
    "Write",
    "Glob",
    "Grep",
    "Bash",
    "Task",
]
PUBLISH_TOOLS = [
    "mcp__wenyan-mcp__publish_article",
]


def get_beijing_time():
    """获取北京时间"""
    return datetime.now(ZoneInfo("Asia/Shanghai"))


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'emotion_women_{get_beijing_time().strftime("%Y%m")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def allowed_tools(publish: bool) -> str:
    tools = BASE_TOOLS + (PUBLISH_TOOLS if publish else [])
    return ",".join(tools)


def list_existing_titles(max_items: int = 30) -> list[str]:
    """读取本地已生成标题，避免让 Claude 再扫描全部文章。"""
    if not ARTICLES_DIR.exists():
        return []

    titles: list[str] = []
    files = sorted(ARTICLES_DIR.glob("*.md"), reverse=True)
    for path in files[:max_items]:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in content.splitlines()[:12]:
            line = line.strip()
            if line.startswith("title:"):
                titles.append(line.removeprefix("title:").strip().strip("'\""))
                break
    return titles


def truncate_for_log(text: str) -> str:
    if len(text) <= MAX_LOG_OUTPUT_CHARS:
        return text
    return text[-MAX_LOG_OUTPUT_CHARS:]


def strip_agent_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return text.strip()


def read_writer_style_digest() -> str:
    """读取 Claude agent，并压缩成 OpenAI 生成时需要遵守的核心风格。"""
    agent_path = BASE_DIR / ".claude" / "agents" / "emotion-writer.md"
    if not agent_path.exists():
        return ""

    content = strip_agent_frontmatter(agent_path.read_text(encoding="utf-8", errors="ignore"))
    keep_sections = [
        "核心定位",
        "关键气质",
        "写作铁律",
        "文章撰写",
        "开篇设计",
        "正文写作要求",
        "结尾设计",
    ]
    lines: list[str] = []
    keep = False
    for line in content.splitlines():
        if line.startswith("## "):
            keep = any(section in line for section in keep_sections)
        if keep:
            lines.append(line)
    digest = "\n".join(lines).strip()
    return digest[:12000]


def parse_image_pool() -> dict[str, list[str]]:
    """读取固定图池，返回 COVER/BODY 两段图片引用。"""
    pool = {"COVER": [], "BODY": []}
    if not IMAGE_POOL.exists():
        return pool

    current: str | None = None
    for raw_line in IMAGE_POOL.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("## COVER"):
            current = "COVER"
            continue
        if upper.startswith("## BODY"):
            current = "BODY"
            continue
        if line.startswith("#"):
            continue
        if current and is_image_reference(line):
            pool[current].append(line)
    return pool


def is_image_reference(value: str) -> bool:
    return (
        value.startswith("http://")
        or value.startswith("https://")
        or value.startswith("/")
        or value.startswith("./")
        or value.startswith("../")
        or value.startswith("photo-")
    )


def parse_drama_image_pool() -> list[str]:
    """读取影视/生活剧男女主合照图池，一行一个 URL 或本地路径。"""
    if not DRAMA_IMAGE_POOL.exists():
        return []

    images: list[str] = []
    for raw_line in DRAMA_IMAGE_POOL.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if is_image_reference(line):
            images.append(line)
    return images


def image_reference_to_markdown_path(value: str) -> str:
    if value.startswith("photo-"):
        return f"https://images.unsplash.com/{value}?w=900"
    return value


def recent_image_refs(max_articles: int = 5) -> set[str]:
    refs: set[str] = set()
    if not ARTICLES_DIR.exists():
        return refs
    image_re = re.compile(r"photo-[0-9]+")
    markdown_image_re = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
    for path in sorted(ARTICLES_DIR.glob("*.md"), reverse=True)[:max_articles]:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        refs.update(image_re.findall(content))
        refs.update(markdown_image_re.findall(content))
    return refs


def article_snapshot() -> dict[Path, int]:
    snapshot: dict[Path, int] = {}
    if not ARTICLES_DIR.exists():
        return snapshot
    for path in ARTICLES_DIR.glob("*.md"):
        try:
            snapshot[path.resolve()] = path.stat().st_mtime_ns
        except OSError:
            continue
    return snapshot


def changed_article_paths(before: dict[Path, int]) -> list[Path]:
    changed: list[Path] = []
    if not ARTICLES_DIR.exists():
        return changed
    for path in ARTICLES_DIR.glob("*.md"):
        resolved = path.resolve()
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            continue
        if resolved not in before or before[resolved] != mtime_ns:
            changed.append(path)
    return sorted(changed, key=lambda item: item.stat().st_mtime_ns)


def rotate_candidates(items: list[str], offset: int) -> list[str]:
    if not items:
        return []
    offset = offset % len(items)
    return items[offset:] + items[:offset]


def candidates_with_recent_fallback(items: list[str], used_recent: set[str], offset: int, needed: int) -> list[str]:
    rotated = rotate_candidates(items, offset)
    available = [item for item in rotated if item not in used_recent]
    if len(available) >= needed:
        return available
    return rotated


def choose_images(article_count: int) -> list[list[str]]:
    """为每篇文章分配封面图、影视剧照、正文氛围图。"""
    pool = parse_image_pool()
    used_recent = recent_image_refs()
    if not pool["COVER"] or len(pool["BODY"]) < 2:
        raise RuntimeError(f"图片池不足，请检查 {IMAGE_POOL}")

    offset = int(get_beijing_time().strftime("%d%H%M"))
    drama_source = parse_drama_image_pool()
    if not drama_source:
        raise RuntimeError(f"影视剧照图池为空，请先维护 {DRAMA_IMAGE_POOL}")

    covers = candidates_with_recent_fallback(pool["COVER"], used_recent, offset, article_count)
    dramas = candidates_with_recent_fallback(drama_source, used_recent, 0, article_count)
    bodies = candidates_with_recent_fallback(pool["BODY"], used_recent, offset, article_count * 2)

    allocations: list[list[str]] = []
    for index in range(article_count):
        cover = covers[index % len(covers)]
        start = (index * 2) % len(bodies)
        body_ids = [bodies[(start + body_index) % len(bodies)] for body_index in range(2)]
        drama = dramas[index % len(dramas)]
        ids = [cover, drama] + body_ids
        urls = [image_reference_to_markdown_path(image_id) for image_id in ids]
        allocations.append(urls)
    return allocations


def slugify(value: str, fallback: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:48] or fallback


def strip_code_fence(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json|markdown|md)?\s*(.*?)\s*```$", text, re.S)
    return match.group(1).strip() if match else text


def extract_response_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]

    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    if chunks:
        return "\n".join(chunks)

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "text" and isinstance(value, str):
                    chunks.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return "\n".join(dict.fromkeys(chunks)).strip()


def parse_json_object(text: str) -> dict:
    text = strip_code_fence(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return json.loads(match.group(0))
        raise


def split_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", markdown.strip(), re.S)
    if not match:
        return {}, markdown.strip()
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip("'\"")
    return meta, match.group(2).strip()


def normalize_markdown(title: str, markdown: str, image_urls: list[str]) -> str:
    """统一成与 Claude agent 一致的 frontmatter + 正文配图格式。"""
    markdown = strip_code_fence(markdown)
    meta, body = split_frontmatter(markdown)
    title = (title or meta.get("title") or "她终于不哄了").strip().strip("'\"")

    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if re.match(r"^!\[[^\]]*\]\([^)]+\)\s*$", stripped):
            continue
        if stripped.startswith("# "):
            continue
        lines.append(line.rstrip())
    body = "\n".join(lines).strip()

    body_lines = body.splitlines()
    insert_positions = [
        index for index, line in enumerate(body_lines) if line.startswith("## ")
    ][1:4]

    if len(insert_positions) < 3:
        paragraph_positions = [
            index
            for index, line in enumerate(body_lines)
            if line.strip() and not line.startswith(">") and not line.startswith("## ")
        ]
        for ratio in (0.35, 0.6, 0.8):
            if not paragraph_positions:
                break
            insert_positions.append(paragraph_positions[min(int(len(paragraph_positions) * ratio), len(paragraph_positions) - 1)])
        insert_positions = sorted(set(insert_positions))[:3]

    for url, position in sorted(zip(image_urls[1:], insert_positions), key=lambda item: item[1], reverse=True):
        body_lines[position:position] = ["", f"![]({url})", ""]

    if len(insert_positions) < 3:
        for url in image_urls[1 + len(insert_positions):]:
            body_lines.extend(["", f"![]({url})", ""])

    normalized_body = "\n".join(body_lines).strip()
    return f"---\ntitle: {title}\n---\n\n![]({image_urls[0]})\n\n{normalized_body}\n"


def normalize_generated_articles(article_paths: list[Path]) -> tuple[bool, list[tuple[Path, str]]]:
    """Rewrite generated drafts so image order follows cover -> drama still -> body images."""
    if not article_paths:
        return True, []

    image_allocations = choose_images(len(article_paths))
    results: list[tuple[Path, str]] = []
    all_ok = True
    for path, image_urls in zip(article_paths, image_allocations):
        content = path.read_text(encoding="utf-8")
        meta, _body = split_frontmatter(content)
        title = meta.get("title") or path.stem
        path.write_text(normalize_markdown(title, content, image_urls), encoding="utf-8")

        ok, output = run_preflight(path)
        results.append((path, output))
        all_ok = all_ok and ok
    return all_ok, results


def run_preflight(article_path: Path) -> tuple[bool, str]:
    outputs: list[str] = []
    for script in ("validate_article_images.py", "quality_gate.py"):
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / script), str(article_path)],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
        )
        outputs.append((result.stdout or "") + (result.stderr or ""))
        if result.returncode != 0:
            return False, "\n".join(outputs).strip()
    return True, "\n".join(outputs).strip()


def publish_article(article_path: Path, verbose: bool = False) -> tuple[bool, str]:
    cmd = [
        sys.executable,
        str(BASE_DIR / "publish_existing_article.py"),
        str(article_path),
        "--theme",
        PUBLISH_THEME,
    ]
    if verbose:
        cmd.append("--verbose")
    result = subprocess.run(cmd, cwd=BASE_DIR, capture_output=not verbose, text=True)
    output = "" if verbose else ((result.stdout or "") + (result.stderr or ""))
    return result.returncode == 0, output.strip()


class EmotionWomenAutomation:
    """情感女性公众号自动化处理类"""

    def __init__(
        self,
        working_dir: str = None,
        article_count: int = 3,
        verbose: bool = False,
        publish: bool = False,
        provider: str = DEFAULT_PROVIDER,
        openai_model: str = DEFAULT_OPENAI_MODEL,
    ):
        self.working_dir = working_dir or str(BASE_DIR)
        self.article_count = article_count
        self.verbose = verbose
        self.publish = publish
        self.provider = provider.strip().lower()
        self.openai_model = openai_model.strip()
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """加载 prompt 模板"""
        existing_titles = list_existing_titles()
        if existing_titles:
            dedup_block = "\n".join(f"- {title}" for title in existing_titles)
        else:
            dedup_block = "- 暂无"

        if self.publish and self.provider != "claude":
            publish_step = f"""- 保存后依次运行：
  `python3 validate_article_images.py <文章绝对路径>`
  `python3 quality_gate.py <文章绝对路径>`
- 两个本地检查都通过后，调用 `mcp__wenyan-mcp__publish_article`，参数：`file=<文章绝对路径>`、`theme_id={PUBLISH_THEME}`。
- 不要传 `app_id`；不要群发；发布失败只记录原因并继续下一篇。"""
            publish_summary = "、草稿箱 media_id 或发布失败原因"
            publish_note = "- 本次需要发布到微信公众号草稿箱，但不直接群发，最终由人工在公众号后台审核后发布。"
        elif self.publish:
            publish_step = """- 保存后运行 `python3 validate_article_images.py <文章绝对路径>` 与 `python3 quality_gate.py <文章绝对路径>`。
- 不调用 wenyan-mcp，不发布；主脚本会在生成结束后统一重排配图、复检并发布到公众号草稿箱。"""
            publish_summary = "、本地质检结果"
            publish_note = "- 本次需要发布到微信公众号草稿箱，但发布动作由主脚本在配图后处理通过后统一执行。"
        else:
            publish_step = "- 保存后运行 `python3 validate_article_images.py <文章绝对路径>` 与 `python3 quality_gate.py <文章绝对路径>`；不调用 wenyan-mcp。"
            publish_summary = ""
            publish_note = "- 本次只生成本地草稿，不调用 wenyan-mcp，不触碰微信公众号。"

        return f"""# 情感女性公众号内容生成任务（热点兼容 + 图池省时版）

## 第一步：轻量定选题

1. 先扫已发文章标题去重（只读标题，不读全文）：
   ```bash
   rg -N '^title:' articles/*.md | sort -u
   ```
2. 允许最多 4 次 WebSearch 获取近期热点钩子，总搜索词从这些里选最相关的组合：`微博 情感 热搜`、`女性成长 热议`、`亲密关系 边界感`、`分手 心理 内耗`、`婚姻 情绪价值`。不要展开无关网页。
3. 筛出 {self.article_count} 个题。优先“热点钩子 + 普世痛点 + 反常识洞察”，热点只是引子，不为追热点牺牲文章完成度。与已发标题去重，宁缺毋滥。
4. 每个选题都要整理好：
   - 选题标题/方向
   - 热点钩子：今天为什么值得写，相关事件/话题/讨论是什么
   - 女性读者的情绪入口
   - 核心反常识洞察
   - 1-2 条参考链接或素材摘要

## 第二步：并行启动 emotion-writer agent

为每个选定主题启动一个 emotion-writer agent，传递上面的选题信息和输出文件路径。

每个 agent 需要：
1. 不重复热点广搜；仅在素材不足、需要确认最新表述、或需要找真实讨论入口时，最多 1 次精准 WebSearch。
2. 配图全部从固定图池直接挑：封面图从 `image_pool.txt` 的 COVER 段挑 1 张；封面后的第一张正文图优先从 `drama_image_pool.txt` 挑 1 张影视/生活剧男女主合照或官方剧照；其余正文图从 `image_pool.txt` 的 BODY 段挑 2 张，分散穿插进正文。
   - 图池条目可以是完整 URL、本地图片路径，或旧的 `photo-...` ID；写入正文时直接使用已分配好的图片路径。
   - 严禁临时搜图、严禁下载图片、严禁跑 Python/PIL 做图像分析。
   - 去重只需避开最近 5 篇已用图片 URL/ID。
3. 写一篇 1200-1800 字的情感深度文章。
4. 保存为 `./articles/YYYYMMDD_HHMM_topic.md`。
{publish_step}

**文章要求**：
- 标题 ≤20 字，只聚焦一个爆点，含敏感词，套用 8 个标题模板之一，不要写"论…""如何…""关于…的思考"这类概括式标题。
- 开篇 3 秒抓住读者，前 3 句必须制造悬念或共鸣。
- 全文套用 4 个框架结构之一（观点+N事例 / 大观点+N小观点 / 观点+N角度 / 观点+人物N故事），主线清晰。
- 至少 1 个完整故事场景，有冲突、有情绪爆点、用具象细节而非情绪标签。
- 至少 3 个值得截图的金句。
- 结尾有力量，并补齐互动引导三件套：开放性问题 + 点赞理由 + 分享动机。
- 文末绝不列「参考资料/参考来源/资料来源/References」等出处链接清单，资料用大白话融进正文即可。
- 无 AI 鸡汤味。
- 正文配图至少 4 张（含封面），封面按 COVER 段原规则；封面后第一张正文图用影视/生活剧男女主合照或官方剧照；其余正文图分散穿插在正文中间；frontmatter 只写 title，不写 cover。

## 第三步：汇总结果

所有 agent 完成后，汇报每篇文章的标题、文件路径、一句话摘要{publish_summary}。

**重要**：
{publish_note}
- 不要询问确认，直接执行所有步骤。
- 并行运行所有 agent 提高效率。"""

    def generate_prompt(self) -> str:
        """生成当天的 prompt（使用北京时间）"""
        today = get_beijing_time().strftime("%Y年%m月%d日")
        return f"今天是北京时间 {today}。\n\n{self.prompt_template}"

    def run(self) -> bool:
        if self.provider == "claude":
            return self.run_claude_code()
        if self.provider == "openai":
            return self.run_openai_api()
        logger.error(f"❌ 不支持的 provider: {self.provider}，可选 claude/openai")
        return False

    def openai_request(self, messages: list[dict], use_web_search: bool = False) -> str:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("缺少 OPENAI_API_KEY，请先在环境变量中配置")

        body: dict = {
            "model": self.openai_model,
            "input": messages,
            "max_output_tokens": min(max(6000 * self.article_count, 8000), 24000),
        }
        if use_web_search and OPENAI_ENABLE_WEB_SEARCH:
            body["tools"] = [
                {
                    "type": "web_search_preview",
                    "search_context_size": "low",
                }
            ]

        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{OPENAI_BASE_URL}/responses",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=OPENAI_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            if use_web_search and ("web_search" in detail or "tool" in detail):
                logger.warning("OpenAI web_search 不可用，降级为无联网生成")
                return self.openai_request(messages, use_web_search=False)
            raise RuntimeError(f"OpenAI API 请求失败: HTTP {exc.code}\n{truncate_for_log(detail)}") from exc

        text = extract_response_text(data)
        if not text:
            raise RuntimeError(f"OpenAI API 未返回文本: {truncate_for_log(json.dumps(data, ensure_ascii=False))}")
        return text

    def build_openai_prompt(self, image_allocations: list[list[str]]) -> list[dict]:
        existing_titles = "\n".join(f"- {title}" for title in list_existing_titles()) or "- 暂无"
        style_digest = read_writer_style_digest()
        today = get_beijing_time().strftime("%Y年%m月%d日")
        image_plan = "\n".join(
            f"{index + 1}. 封面：{urls[0]}；封面后第一张正文图：{urls[1]}；正文图：{', '.join(urls[2:])}"
            for index, urls in enumerate(image_allocations)
        )

        system = """你是情感女性公众号的资深主编和主笔。
你要生成可直接保存为微信公众号草稿的 Markdown 文章，风格与 emotion-writer agent 保持一致：真实故事切入，观点犀利但温暖，像经历丰富的闺蜜深夜聊天，不像 AI 课堂。
只输出 JSON，不要输出解释、代码围栏、参考资料列表。"""

        user = f"""今天是北京时间 {today}。请一次生成 {self.article_count} 篇情感女性公众号文章。

## 热点兼容
- 允许使用 OpenAI web search 获取近期热点钩子，但最多做 4 次热点广搜。
- 热点只做引子，不写成新闻复述；优先“热点钩子 + 普世痛点 + 反常识洞察”。
- 如果无法联网，也要基于普世情感痛点完成文章。

## 已发标题，必须避开近似选题
{existing_titles}

## 固定配图
每篇文章必须使用对应的 4 张图片。正文第一张图是封面，按封面原规则；封面后的第一张正文图优先是影视/生活剧男女主合照或官方剧照；后 2 张是正文氛围图。frontmatter 只写 title，不写 cover。
{image_plan}

## 输出格式
只输出一个 JSON 对象：
{{
  "articles": [
    {{
      "title": "20字以内的标题",
      "topic_slug": "英文小写短横线 slug",
      "summary": "一句话摘要",
      "markdown": "完整 Markdown，包含 frontmatter 和正文"
    }}
  ]
}}

## 每篇硬性要求
- 1200-1800 字中文，标题≤20字，聚焦一个爆点，不要“论/如何/关于...的思考”。
- 开篇 3 句必须抓人，有悬念或共鸣。
- 至少 1 个完整故事场景，有冲突、有动作、有细节。
- 至少 3 条加粗或引用格式金句。
- 至少 2 个二级小标题。
- 结尾包含开放性问题、点赞理由、分享动机。
- 文末绝不列参考资料/来源链接。
- 不要出现这些 AI 感表达：每个人都值得被爱、时间会治愈一切、我们应该认识到、综上所述、由此可见、女性要学会、正确的做法是。

## emotion-writer 风格摘要
{style_digest}
"""
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def repair_with_openai(self, title: str, markdown: str, image_urls: list[str], errors_text: str) -> str:
        messages = [
            {
                "role": "system",
                "content": "你是公众号文章质检修稿编辑。只输出 JSON，不要解释。",
            },
            {
                "role": "user",
                "content": f"""下面文章未通过本地质检，请在保持标题、主题、风格和图片 URL 不变的前提下修复。

质检错误：
{errors_text}

必须满足：
- 1200-1800 字中文；
- 至少 4 张正文图片，且只用这些 URL：{', '.join(image_urls)}；
- 至少 3 条加粗或引用格式金句；
- 至少 2 个二级小标题；
- frontmatter 只写 title。

只输出：
{{"markdown":"修复后的完整 Markdown"}}

原标题：{title}
原文：
{markdown}
""",
            },
        ]
        text = self.openai_request(messages, use_web_search=False)
        data = parse_json_object(text)
        return str(data.get("markdown") or markdown)

    def save_openai_articles(self, articles: list[dict], image_allocations: list[list[str]]) -> list[tuple[Path, str, str]]:
        saved: list[tuple[Path, str, str]] = []
        timestamp = get_beijing_time().strftime("%Y%m%d_%H%M")
        for index, article in enumerate(articles[: self.article_count]):
            title = str(article.get("title") or "").strip()
            slug = slugify(str(article.get("topic_slug") or title), f"openai-{index + 1}")
            path = ARTICLES_DIR / f"{timestamp}_{slug}.md"
            if path.exists():
                path = ARTICLES_DIR / f"{timestamp}_{slug}-{index + 1}.md"

            markdown = normalize_markdown(title, str(article.get("markdown") or ""), image_allocations[index])
            path.write_text(markdown, encoding="utf-8")
            saved.append((path, title, str(article.get("summary") or "").strip()))
        return saved

    def run_openai_api(self) -> bool:
        start = time.perf_counter()
        logger.info("=" * 60)
        logger.info(f"开始执行 情感女性公众号 OpenAI API 自动化任务 - {get_beijing_time()}")
        logger.info(f"文章数量: {self.article_count} 篇")
        logger.info(f"OpenAI 模型: {self.openai_model}")
        logger.info(f"发布模式: {'发布到公众号草稿箱' if self.publish else '仅生成本地草稿'}")
        logger.info("=" * 60)

        try:
            ARTICLES_DIR.mkdir(exist_ok=True)
            image_allocations = choose_images(self.article_count)
            messages = self.build_openai_prompt(image_allocations)
            logger.info("调用 OpenAI API 生成文章...")
            text = self.openai_request(messages, use_web_search=True)
            data = parse_json_object(text)
            articles = data.get("articles", [])
            if not isinstance(articles, list) or len(articles) < self.article_count:
                raise RuntimeError(f"OpenAI 返回文章数量不足：{len(articles) if isinstance(articles, list) else 0}/{self.article_count}")

            saved = self.save_openai_articles(articles, image_allocations)
            all_ok = True
            for index, (path, title, summary) in enumerate(saved):
                ok, output = run_preflight(path)
                if not ok:
                    logger.warning(f"文章质检未通过，尝试修复：{path.name}\n{truncate_for_log(output)}")
                    repaired = self.repair_with_openai(
                        title,
                        path.read_text(encoding="utf-8"),
                        image_allocations[index],
                        output,
                    )
                    path.write_text(normalize_markdown(title, repaired, image_allocations[index]), encoding="utf-8")
                    ok, output = run_preflight(path)

                if ok:
                    logger.info(f"✅ 文章通过质检：{path}")
                else:
                    all_ok = False
                    logger.error(f"❌ 文章仍未通过质检：{path}\n{truncate_for_log(output)}")
                    continue

                if self.publish:
                    published, publish_output = publish_article(path, self.verbose)
                    if published:
                        logger.info(f"✅ 已发布到公众号草稿箱：{path.name}")
                    else:
                        all_ok = False
                        logger.error(f"❌ 发布失败：{path.name}\n{truncate_for_log(publish_output)}")

                logger.info(f"结果：标题={title or path.stem}；摘要={summary or '无'}；路径={path}")

            elapsed = time.perf_counter() - start
            logger.info(f"OpenAI API 自动化任务结束，耗时 {elapsed:.1f}s")
            logger.info("=" * 60)
            return all_ok
        except Exception as exc:
            logger.error(f"❌ OpenAI API 自动化任务失败: {exc}")
            logger.exception(exc)
            return False

    def run_claude_code(self):
        """执行 Claude Code 命令（headless 模式）"""
        try:
            logger.info("=" * 60)
            logger.info(f"开始执行 情感女性公众号 自动化任务 - {get_beijing_time()}")
            logger.info(f"文章数量: {self.article_count} 篇")
            logger.info(f"发布模式: {'发布到公众号草稿箱' if self.publish else '仅生成本地草稿'}")
            logger.info("=" * 60)

            ARTICLES_DIR.mkdir(exist_ok=True)
            IMAGES_DIR.mkdir(exist_ok=True)
            before_articles = article_snapshot()
            prompt = self.generate_prompt()
            tools = allowed_tools(False)

            logger.info(f"工作目录: {self.working_dir}")
            logger.info(f"使用 headless 模式{' [实时输出]' if self.verbose else ''}")
            logger.info(f"允许工具: {tools}")

            # 构造 Claude Code headless 命令
            cmd = [
                'claude',
                '-p', prompt,
                '--allowedTools', tools,
            ]

            if self.verbose:
                cmd.append('--verbose')

            cmd.extend([
                '--permission-mode', 'bypassPermissions',
                '--output-format', 'text'
            ])

            # 执行命令
            if self.verbose:
                logger.info("⏳ 正在执行，将显示 Claude 详细执行过程...")
                logger.info("-" * 60)
                result = subprocess.run(
                    cmd,
                    cwd=self.working_dir,
                    timeout=3600
                )
                logger.info("-" * 60)
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=self.working_dir,
                    timeout=3600
                )

                if result.returncode == 0:
                    logger.info("✅ 任务执行成功")
                    if result.stdout:
                        logger.info(f"输出尾部:\n{truncate_for_log(result.stdout)}")
                else:
                    logger.error(f"❌ 任务执行失败 (返回码: {result.returncode})")
                    if result.stderr:
                        logger.error(f"错误信息:\n{truncate_for_log(result.stderr)}")

            if self.verbose and result.returncode == 0:
                logger.info("✅ 任务执行成功")

            generated_paths = changed_article_paths(before_articles)
            success = result.returncode == 0
            if not generated_paths:
                if success:
                    logger.error("❌ Claude 执行成功，但没有发现本轮新增或修改的文章")
                success = False
            else:
                if result.returncode != 0:
                    logger.warning("Claude 返回码非 0，但发现本轮文章，继续尝试统一重排配图并复检")
                logger.info(f"发现本轮生成/修改文章 {len(generated_paths)} 篇，开始统一重排配图并复检")
                postprocess_ok, preflight_results = normalize_generated_articles(generated_paths)
                for path, output in preflight_results:
                    if "质量门槛未通过" in output or "图片预检失败" in output:
                        logger.error(f"❌ 后处理质检未通过：{path.name}\n{truncate_for_log(output)}")
                    else:
                        logger.info(f"✅ 后处理质检通过：{path.name}")
                success = postprocess_ok

            if success and self.publish:
                for path in generated_paths:
                    published, publish_output = publish_article(path, self.verbose)
                    if published:
                        logger.info(f"✅ 已发布到公众号草稿箱：{path.name}")
                    else:
                        logger.error(f"❌ 发布失败：{path.name}\n{truncate_for_log(publish_output)}")
                        success = False

            logger.info("=" * 60)
            logger.info(f"任务结束 - {get_beijing_time()}")
            logger.info("=" * 60)

            return success

        except subprocess.TimeoutExpired:
            logger.error("❌ 任务执行超时（超过1小时）")
            return False
        except Exception as e:
            logger.error(f"❌ 执行过程中发生错误: {str(e)}")
            logger.exception(e)
            return False


def run_now(
    article_count: int,
    verbose: bool = False,
    publish: bool = False,
    provider: str = DEFAULT_PROVIDER,
    openai_model: str = DEFAULT_OPENAI_MODEL,
):
    """立即执行任务"""
    logger.info("🚀 立即执行模式")
    automation = EmotionWomenAutomation(
        article_count=article_count,
        verbose=verbose,
        publish=publish,
        provider=provider,
        openai_model=openai_model,
    )
    success = automation.run()
    return 0 if success else 1


def beijing_to_utc(beijing_time_str: str) -> str:
    """将北京时间 HH:MM 转换为 UTC 时间 HH:MM"""
    hour, minute = map(int, beijing_time_str.split(':'))
    utc_hour = (hour - 8) % 24
    return f"{utc_hour:02d}:{minute:02d}"


def run_scheduled(
    article_count: int,
    schedule_times: list = None,
    verbose: bool = False,
    publish: bool = False,
    provider: str = DEFAULT_PROVIDER,
    openai_model: str = DEFAULT_OPENAI_MODEL,
):
    """定时执行任务（支持多个时间点）- 使用北京时间"""
    import schedule
    import time

    if schedule_times is None:
        schedule_times = ["09:00"]

    logger.info("⏰ 定时执行模式（北京时间）")
    logger.info(f"调度时间: 每天 {', '.join(schedule_times)} 北京时间")
    logger.info(f"文章数量: {article_count} 篇")
    logger.info(f"生成 provider: {provider}")
    if provider == "openai":
        logger.info(f"OpenAI 模型: {openai_model}")
    logger.info(f"实时输出: {'开启' if verbose else '关闭'}")
    logger.info(f"发布模式: {'发布到公众号草稿箱' if publish else '仅生成本地草稿'}")

    beijing_now = get_beijing_time()
    logger.info(f"当前北京时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}")

    def job():
        logger.info(f"🚀 定时任务触发 - 北京时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
        automation = EmotionWomenAutomation(
            article_count=article_count,
            verbose=verbose,
            publish=publish,
            provider=provider,
            openai_model=openai_model,
        )
        automation.run()

    for beijing_time_str in schedule_times:
        utc_time_str = beijing_to_utc(beijing_time_str)
        schedule.every().day.at(utc_time_str).do(job)
        logger.info(f"✅ 已设置定时任务: 每天 {beijing_time_str} 北京时间 (UTC {utc_time_str})")

    logger.info("⏳ 等待调度...")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("\n👋 服务已停止")
        return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='情感女性公众号自动化生成与发布系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 立即生成 1 篇文章
  python daily_emotion_women.py --now --count 1

  # 使用 OpenAI API 生成 1 篇文章（需 OPENAI_API_KEY）
  python daily_emotion_women.py --now --count 1 --provider openai

  # 立即生成 1 篇文章（实时显示执行过程）
  python daily_emotion_women.py --now --count 1 --verbose

  # 立即生成 3 篇文章
  python daily_emotion_women.py --now --count 3

  # 立即生成 1 篇并发布到公众号草稿箱
  python daily_emotion_women.py --now --count 1 --publish

  # 定时每天 09:00 和 21:00 各生成 3 篇文章
  python daily_emotion_women.py --time 09:00 21:00 --count 3

  # 定时每天晚上9点生成 2 篇文章（实时输出）
  python daily_emotion_women.py --time 21:00 --count 2 -v
        """
    )

    parser.add_argument(
        '--now',
        action='store_true',
        help='立即执行任务（不等待定时）'
    )

    parser.add_argument(
        '--count',
        type=int,
        default=3,
        help='生成文章数量（默认: 3）'
    )

    parser.add_argument(
        '--time',
        type=str,
        nargs='+',
        default=['09:00'],
        help='定时执行时间，格式 HH:MM，支持多个时间点（默认: 09:00）'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='实时显示 Claude 执行过程'
    )

    parser.add_argument(
        '--publish',
        action='store_true',
        help='成稿后通过 wenyan-mcp 发布到微信公众号草稿箱（需配置 emotion_women/.mcp.json）'
    )

    parser.add_argument(
        '--provider',
        choices=['claude', 'openai'],
        default=DEFAULT_PROVIDER if DEFAULT_PROVIDER in {'claude', 'openai'} else 'claude',
        help='生成调度方式：claude 保持原 Claude Code 流程；openai 使用 OpenAI API（默认: claude，可用 EMOTION_PROVIDER 覆盖）'
    )

    parser.add_argument(
        '--openai-model',
        default=DEFAULT_OPENAI_MODEL,
        help=f'OpenAI API 模型（默认: {DEFAULT_OPENAI_MODEL}，可用 OPENAI_MODEL 覆盖）'
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("情感女性公众号自动化系统")
    logger.info("=" * 60)
    logger.info(f"文章数量: {args.count} 篇")
    if args.now:
        logger.info("执行模式: 立即执行")
    else:
        times_str = ', '.join(args.time) if isinstance(args.time, list) else args.time
        logger.info(f"执行模式: 定时执行 ({times_str})")
    logger.info(f"生成 provider: {args.provider}")
    if args.provider == "openai":
        logger.info(f"OpenAI 模型: {args.openai_model}")
    logger.info(f"实时输出: {'开启' if args.verbose else '关闭'}")
    logger.info(f"发布模式: {'发布到公众号草稿箱' if args.publish else '仅生成本地草稿'}")
    logger.info("=" * 60)

    if args.now:
        return run_now(args.count, args.verbose, args.publish, args.provider, args.openai_model)
    else:
        return run_scheduled(args.count, args.time, args.verbose, args.publish, args.provider, args.openai_model)


if __name__ == "__main__":
    exit(main())
