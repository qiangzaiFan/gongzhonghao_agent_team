#!/usr/bin/env python3
"""Create an original emotion_women draft from a popular article URL."""

from __future__ import annotations

import argparse
import html as html_module
import json
import re
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib import error, request
from urllib.parse import urlparse

from daily_emotion_women import (
    ARTICLES_DIR,
    BASE_DIR,
    DEFAULT_OPENAI_MODEL,
    PUBLISH_THEME,
    EmotionWomenAutomation,
    choose_images,
    get_beijing_time,
    normalize_markdown,
    parse_json_object,
    read_writer_style_digest,
    run_preflight,
    slugify,
    truncate_for_log,
)


DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_USER_AGENT = "Mozilla/5.0 emotion-women-rewrite/1.0"
WECHAT_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
    "Mobile/15E148 Safari/604.1"
)
MAX_SOURCE_CHARS = 14000
OVERLAP_WARN_THRESHOLD = 0.08
MIN_SOURCE_CJK = 800
SOURCE_SNAPSHOT_DIR = BASE_DIR / "sources"
SOURCE_NOISE_PHRASES = [
    "微信扫一扫",
    "取消允许",
    "预览时标签不可点",
    "使用小程序",
    "在小说阅读器",
    "点击预约直播间",
    "环境异常",
    "当前环境异常",
    "完成验证后即可继续访问",
    "微信公众平台",
    "赞，轻点两下取消赞",
    "在看，轻点两下取消在看",
    "作者提示:内容由AI生成",
]
SOURCE_AD_CONTEXT_PHRASES = [
    "点击预约直播间",
    "在小说阅读器",
    "去阅读",
]


class ArticleHTMLParser(HTMLParser):
    """Small dependency-free extractor for article-like pages."""

    BLOCK_TAGS = {
        "article",
        "blockquote",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "li",
        "p",
        "section",
    }
    SKIP_TAGS = {"script", "style", "svg", "noscript", "iframe", "canvas"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.skip_depth = 0
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if tag == "title":
            self.in_title = True
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if tag == "title":
            self.in_title = False
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self.in_title:
            self.title_parts.append(text)
        if not self.skip_depth and not self.in_title:
            self.parts.append(text)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()

    @property
    def text(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines).strip()


class TargetElementTextParser(HTMLParser):
    """Extract text from a target element, such as WeChat's #js_content."""

    BLOCK_TAGS = ArticleHTMLParser.BLOCK_TAGS
    SKIP_TAGS = ArticleHTMLParser.SKIP_TAGS

    def __init__(self, target_id: str) -> None:
        super().__init__(convert_charrefs=True)
        self.target_id = target_id
        self.capture_depth = 0
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = {key.lower(): value for key, value in attrs if key}
        if self.capture_depth == 0 and attrs_dict.get("id") == self.target_id:
            self.capture_depth = 1
            self.parts.append("\n")
            return

        if self.capture_depth:
            self.capture_depth += 1
            if tag in self.SKIP_TAGS:
                self.skip_depth += 1
            if tag in self.BLOCK_TAGS:
                self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self.capture_depth:
            return
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")
        self.capture_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.capture_depth or self.skip_depth:
            return
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.parts.append(text)

    @property
    def text(self) -> str:
        return normalize_extracted_lines("".join(self.parts))


def normalize_extracted_lines(text: str) -> str:
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def is_wechat_url(url: str) -> bool:
    return urlparse(url).netloc.endswith("mp.weixin.qq.com")


def extract_meta_content(markup: str, key: str) -> str:
    for match in re.finditer(r"<meta\b[^>]*>", markup, re.I):
        tag = match.group(0)
        if re.search(rf"(?:property|name)\s*=\s*['\"]{re.escape(key)}['\"]", tag, re.I):
            content_match = re.search(r"content\s*=\s*(['\"])(.*?)\1", tag, re.I | re.S)
            if content_match:
                return html_module.unescape(content_match.group(2)).strip()
    return ""


def extract_js_string(markup: str, name: str) -> str:
    match = re.search(rf"\b{name}\s*=\s*(['\"])(.*?)\1", markup, re.S)
    if not match:
        return ""
    value = match.group(2)
    if "\\" in value:
        try:
            value = bytes(value, "utf-8").decode("unicode_escape")
        except UnicodeDecodeError:
            pass
    return html_module.unescape(value).strip()


def extract_title_from_html(markup: str, fallback: str = "") -> str:
    for candidate in (
        extract_meta_content(markup, "og:title"),
        extract_js_string(markup, "msg_title"),
    ):
        if candidate:
            return clean_title(candidate)

    parser = ArticleHTMLParser()
    parser.feed(markup)
    return clean_title(parser.title or fallback)


def clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", html_module.unescape(title)).strip()
    title = re.sub(r"\s*-\s*微信公众平台\s*$", "", title)
    return title


def extract_article_text_from_html(markup: str, prefer_wechat: bool = False) -> str:
    if prefer_wechat or "js_content" in markup:
        parser = TargetElementTextParser("js_content")
        parser.feed(markup)
        if cjk_len(parser.text) >= 200:
            return parser.text

    parser = ArticleHTMLParser()
    parser.feed(markup)
    return parser.text


def fetch_url_text(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("只支持 http/https 链接")

    user_agent = WECHAT_USER_AGENT if is_wechat_url(url) else DEFAULT_USER_AGENT
    req = request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with request.urlopen(req, timeout=DEFAULT_TIMEOUT_SECONDS) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
    except error.HTTPError as exc:
        raise RuntimeError(f"抓取链接失败：HTTP {exc.code}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"抓取链接失败：{exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("抓取链接超时") from exc

    markup = raw.decode(charset, errors="replace")
    title = extract_title_from_html(markup, fallback=url)
    text = extract_article_text_from_html(markup, prefer_wechat=is_wechat_url(url))
    return title, text


def read_source(args: argparse.Namespace) -> tuple[str, str]:
    if args.source_file:
        path = Path(args.source_file).expanduser()
        text = path.read_text(encoding="utf-8", errors="ignore")
        title, source_text = path.stem, clean_source_text(text)
        validate_source_text(source_text)
        return title, source_text

    title, text = fetch_url_text(args.url)
    source_text = clean_source_text(text)
    validate_source_text(source_text)
    return title or args.url, source_text


def clean_source_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return remove_source_noise(text).strip()


def remove_source_noise(text: str) -> str:
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    skip_indexes: set[int] = set()
    for index, line in enumerate(raw_lines):
        if any(phrase in line for phrase in SOURCE_AD_CONTEXT_PHRASES):
            for skip_index in range(max(0, index - 2), min(len(raw_lines), index + 3)):
                skip_indexes.add(skip_index)

    cleaned: list[str] = []
    for index, line in enumerate(raw_lines):
        if index in skip_indexes:
            continue
        if any(phrase in line for phrase in SOURCE_NOISE_PHRASES):
            continue
        if re.fullmatch(r"[▽▼△▲·.\-—_ ]{3,}", line):
            continue
        if re.search(r"^(来源|声明|作者|编辑|责编)\s*[|：:]", line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def cjk_len(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def validate_source_text(text: str) -> None:
    length = cjk_len(text)
    if length < MIN_SOURCE_CJK:
        raise RuntimeError(
            f"来源正文抽取不足：仅 {length} 个中文字符，至少需要 {MIN_SOURCE_CJK}。"
            "请确认链接能访问正文，或复制原文到 --source-file。"
        )

    noise_hits = sum(text.count(phrase) for phrase in SOURCE_NOISE_PHRASES)
    if noise_hits >= 8 and length < 1600:
        raise RuntimeError(
            "来源正文疑似主要是微信页面按钮/广告噪声，未可靠拿到原文。"
            "请复制原文到 --source-file 后再改写。"
        )


def save_source_snapshot(title: str, text: str, url: str) -> Path:
    SOURCE_SNAPSHOT_DIR.mkdir(exist_ok=True)
    slug_source = title or url or "source"
    slug = slugify(slug_source, "source")
    timestamp = get_beijing_time().strftime("%Y%m%d_%H%M")
    path = SOURCE_SNAPSHOT_DIR / f"{timestamp}_{slug}.txt"
    content = f"URL: {url}\nTITLE: {title}\nCJK_LENGTH: {cjk_len(text)}\n\n{text}\n"
    path.write_text(content, encoding="utf-8")
    return path


def source_preview(text: str, max_chars: int = 260) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:max_chars] + ("..." if len(compact) > max_chars else "")


def compact_source_text(text: str, max_chars: int = MAX_SOURCE_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2].strip()
    tail = text[-max_chars // 2 :].strip()
    return f"{head}\n\n[中间内容已截断，保留开头和结尾用于结构分析]\n\n{tail}"


def normalized_for_overlap(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"---.*?---", "", text, flags=re.S)
    return "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", text)).lower()


def shingle_overlap(source: str, draft: str, width: int = 18) -> float:
    source_norm = normalized_for_overlap(source)
    draft_norm = normalized_for_overlap(draft)
    if len(source_norm) < width or len(draft_norm) < width:
        return 0.0

    source_shingles = {source_norm[index : index + width] for index in range(len(source_norm) - width + 1)}
    draft_shingles = {draft_norm[index : index + width] for index in range(len(draft_norm) - width + 1)}
    if not source_shingles or not draft_shingles:
        return 0.0
    return len(source_shingles & draft_shingles) / min(len(source_shingles), len(draft_shingles))


def build_messages(source_title: str, source_text: str, url: str) -> list[dict]:
    style_digest = read_writer_style_digest()
    today = get_beijing_time().strftime("%Y年%m月%d日")
    source_excerpt = compact_source_text(source_text)

    system = """你是情感女性公众号的资深主编和原创改写编辑。
你的任务不是洗稿，而是把一篇爆款文章当作选题研究样本，提炼它为什么能打动读者，再写出一篇属于本账号的新文章。
必须尊重原创边界：不复用原标题、小标题、段落顺序、核心故事细节、独特比喻和连续表达。只输出 JSON。"""

    user = f"""今天是北京时间 {today}。

我拿到一篇爆款文章链接，想写同题材但明显属于我账号的新文章。
重要硬约束：你只能基于下面“来源正文抽取”做分析和原创转化。如果来源正文不足、像页面噪声、或无法判断原文内容，必须返回 JSON 并在 markdown 中说明无法改写，不要凭标题或链接脑补。

来源链接：{url}
来源标题：{source_title}

来源正文抽取：
{source_excerpt}

## 工作要求
1. 先分析来源文章为什么容易火：标题钩子、读者痛点、情绪推进、结构、金句类型、互动点。
2. 再进行原创转化：
   - 保留的只能是“大众痛点/情绪矛盾/选题方向”；
   - 必须更换标题、开头钩子、故事人物、故事场景、论证顺序、小标题、比喻、结尾互动；
   - 不要使用来源文章的连续表达、独特句子、专有故事细节；
   - 不要写成逐段改写，要像重新立项写一篇文章。
3. 按 emotion-writer 风格写：真实故事切入，观点犀利但温暖，目标读者是 25-45 岁女性，覆盖恋爱、婚姻、育儿、职场与家庭照护压力，像有阅历的女性朋友认真聊天。
4. 关于平台识别：不要提供“规避 AI 检测”的技巧；写作上用真人编辑标准提升质量，包括具体场景、非模板化表达、清晰价值判断、自然段落节奏、少用套话。

## 文章硬性要求
- 1200-1800 字中文。
- 标题 20 字以内，聚焦一个爆点。
- frontmatter 只写 title。
- 至少 2 个二级小标题。
- 至少 1 个完整故事场景，有动作、对话和冲突。
- 至少 3 条加粗或引用格式金句。
- 结尾包含开放性问题、点赞理由、分享动机。
- 文末不要列参考资料/来源链接。
- 不要出现这些 AI 感表达：每个人都值得被爱、时间会治愈一切、我们应该认识到、综上所述、由此可见、女性要学会、正确的做法是。

## 输出格式
只输出 JSON：
{{
  "source_analysis": {{
    "hot_reason": "为什么火",
    "reader_pain": "读者痛点",
    "structure": "来源结构摘要",
    "transformation_plan": "原创转化计划"
  }},
  "title": "新标题",
  "topic_slug": "英文小写短横线 slug",
  "originality_notes": "说明这篇文章与来源相比换了哪些关键元素",
  "markdown": "完整 Markdown"
}}

## emotion-writer 风格摘要
{style_digest}
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def generate_rewrite(source_title: str, source_text: str, url: str, model: str) -> dict:
    automation = EmotionWomenAutomation(article_count=1, provider="openai", openai_model=model)
    text = automation.openai_request(build_messages(source_title, source_text, url), use_web_search=False)
    data = parse_json_object(text)
    if not isinstance(data.get("markdown"), str):
        raise RuntimeError(f"OpenAI 返回缺少 markdown：{truncate_for_log(json.dumps(data, ensure_ascii=False))}")
    return data


def build_editor_polish_messages(data: dict, source_title: str, source_text: str, url: str) -> list[dict]:
    source_excerpt = compact_source_text(source_text, 6000)
    markdown = str(data.get("markdown") or "")
    title = str(data.get("title") or "")
    originality_notes = str(data.get("originality_notes") or "")

    system = """你是情感女性公众号的人工主编，负责把模型初稿改成更像真人主笔写过的原创稿。
你不是在规避检测器；你的目标是提升原创度、可读性、细节密度和账号辨识度。
必须尊重原创边界，不得复用来源文章的独特故事、连续表达、小标题和句式。只输出 JSON。"""

    user = f"""请对下面这篇“爆款链接原创转化稿”做第二轮人工主编润色。

来源链接：{url}
来源标题：{source_title}
来源正文摘录，仅用于避开重复和搬运：
{source_excerpt}

当前标题：{title}
原创转化说明：{originality_notes}

当前初稿：
{markdown}

## 润色目标
1. 保持主题和核心观点，但让文章更像本账号主笔的成稿。
2. 增加具体动作、生活物件、对话和心理停顿，减少抽象判断。
3. 删除或改写模板化表达、正确废话、口号式鸡汤。
4. 调整段落节奏：允许短句单独成段，避免每段都像“观点-解释-总结”。
5. 保持标题 20 字以内；可优化标题，但不要像来源标题。
6. 不要新增无法确认的真实人物、真实数据、真实新闻事实。
7. 不要把来源文章逐段换词；如果发现初稿和来源结构太像，要重排段落和故事重心。

## 必须保留
- frontmatter 只写 title。
- 1200-1800 字中文优先，最多不超过 2300 字。
- 至少 2 个二级小标题。
- 至少 3 条加粗或引用格式金句。
- 结尾包含开放性问题、点赞理由、分享动机。
- 文末不列来源、参考资料或链接。

## 避免这些 AI 感表达
每个人都值得被爱、时间会治愈一切、我们应该认识到、综上所述、由此可见、女性要学会、正确的做法是、这告诉我们、在这个快节奏时代。

只输出 JSON：
{{
  "title": "润色后的标题",
  "topic_slug": "英文小写短横线 slug",
  "editor_notes": "主编改了哪些地方",
  "markdown": "润色后的完整 Markdown"
}}
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def editor_polish(data: dict, source_title: str, source_text: str, url: str, model: str) -> dict:
    automation = EmotionWomenAutomation(article_count=1, provider="openai", openai_model=model)
    text = automation.openai_request(
        build_editor_polish_messages(data, source_title, source_text, url),
        use_web_search=False,
    )
    polished = parse_json_object(text)
    if not isinstance(polished.get("markdown"), str):
        raise RuntimeError(f"主编润色返回缺少 markdown：{truncate_for_log(json.dumps(polished, ensure_ascii=False))}")

    result = dict(data)
    for key in ("title", "topic_slug", "editor_notes", "markdown"):
        if polished.get(key):
            result[key] = polished[key]
    return result


STYLE_WARNING_PATTERNS = [
    r"首先[，,]",
    r"其次[，,]",
    r"最后[，,]",
    r"这告诉我们",
    r"在这个快节奏时代",
    r"毋庸置疑",
    r"不可否认",
    r"真正的[^。！？]{0,20}不是[^。！？]{0,40}而是",
]


def style_warnings(markdown: str) -> list[str]:
    warnings: list[str] = []
    for pattern in STYLE_WARNING_PATTERNS:
        count = len(re.findall(pattern, markdown))
        if count:
            warnings.append(f"{pattern}: {count}")
    return warnings


def save_article(data: dict, source_text: str) -> tuple[Path, float]:
    title = str(data.get("title") or "").strip()
    markdown = str(data.get("markdown") or "")
    slug = slugify(str(data.get("topic_slug") or title), "rewrite")
    timestamp = get_beijing_time().strftime("%Y%m%d_%H%M")
    path = ARTICLES_DIR / f"{timestamp}_{slug}.md"
    suffix = 2
    while path.exists():
        path = ARTICLES_DIR / f"{timestamp}_{slug}-{suffix}.md"
        suffix += 1

    image_urls = choose_images(1)[0]
    normalized = normalize_markdown(title, markdown, image_urls)
    overlap = shingle_overlap(source_text, normalized)
    path.write_text(normalized, encoding="utf-8")
    return path, overlap


def publish_path(article_path: Path, theme: str) -> tuple[bool, str]:
    result = subprocess.run(
        [
            sys.executable,
            str(BASE_DIR / "publish_existing_article.py"),
            str(article_path),
            "--theme",
            theme,
        ],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    return result.returncode == 0, output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从一篇爆款文章链接生成情感号原创转化稿",
    )
    parser.add_argument("url", nargs="?", default="", help="爆款文章链接")
    parser.add_argument(
        "--source-file",
        help="链接无法抓取时，传入复制好的原文 txt/md 文件",
    )
    parser.add_argument(
        "--openai-model",
        default=DEFAULT_OPENAI_MODEL,
        help=f"OpenAI API 模型，默认 {DEFAULT_OPENAI_MODEL}",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="生成并质检通过后发布到公众号草稿箱",
    )
    parser.add_argument(
        "--theme",
        default=PUBLISH_THEME,
        help=f"发布排版主题，默认 {PUBLISH_THEME}",
    )
    parser.add_argument(
        "--no-editor-polish",
        action="store_true",
        help="跳过默认的第二轮人工主编润色",
    )
    args = parser.parse_args()

    if not args.url and not args.source_file:
        parser.error("必须提供 url，或使用 --source-file 提供原文")

    start = time.perf_counter()
    ARTICLES_DIR.mkdir(exist_ok=True)

    print("读取来源文章...")
    source_title, source_text = read_source(args)
    snapshot_path = save_source_snapshot(source_title, source_text, args.url or str(args.source_file))
    print(f"来源标题：{source_title}")
    print(f"抽取正文：{len(source_text)} 字符，{cjk_len(source_text)} 个中文字符")
    print(f"来源快照：{snapshot_path}")
    print(f"正文预览：{source_preview(source_text)}")

    print("分析爆款结构并生成原创转化稿...")
    data = generate_rewrite(source_title, source_text, args.url or str(args.source_file), args.openai_model)
    if not args.no_editor_polish:
        print("执行第二轮人工主编润色...")
        data = editor_polish(data, source_title, source_text, args.url or str(args.source_file), args.openai_model)
    path, overlap = save_article(data, source_text)
    print(f"已保存：{path}")
    print(f"来源相似度指纹：{overlap:.2%}")
    if overlap >= OVERLAP_WARN_THRESHOLD:
        print("警告：与来源存在偏高的连续片段重合，建议人工再改一轮故事和表达。")
    warnings = style_warnings(path.read_text(encoding="utf-8"))
    if warnings:
        print("主编风格提示：")
        for warning in warnings:
            print(f"- {warning}")

    ok, output = run_preflight(path)
    if not ok:
        print("本地质检未通过：", file=sys.stderr)
        print(output, file=sys.stderr)
        return 1
    print(output)

    if args.publish:
        print("发布到公众号草稿箱...")
        published, publish_output = publish_path(path, args.theme)
        print(publish_output)
        if not published:
            return 1

    analysis = data.get("source_analysis", {})
    if isinstance(analysis, dict):
        print("爆款分析摘要：")
        for key in ("hot_reason", "reader_pain", "transformation_plan"):
            if analysis.get(key):
                print(f"- {analysis[key]}")
    if data.get("originality_notes"):
        print(f"原创转化说明：{data['originality_notes']}")
    if data.get("editor_notes"):
        print(f"主编润色说明：{data['editor_notes']}")

    elapsed = time.perf_counter() - start
    print(f"完成，耗时 {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
