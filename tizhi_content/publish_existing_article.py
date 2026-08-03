#!/usr/bin/env python3
"""Publish an existing tizhi_content Markdown article to WeChat draft box."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from image_generation_spec import PUBLISH_AUTHOR, PUBLISH_THEME


BASE_DIR = Path(__file__).resolve().parent
MCP_CONFIG = BASE_DIR / ".mcp.json"
DEFAULT_THEME = PUBLISH_THEME
DEFAULT_AUTHOR = PUBLISH_AUTHOR
PUBLISH_HISTORY = BASE_DIR / "logs" / "publish_history.jsonl"
PLACEHOLDER_RE = re.compile(r"(填写|你的|AppID|AppSecret)")


def find_node() -> str:
    return os.environ.get("NODE_BIN", "node")


def load_wenyan_config() -> tuple[str, dict[str, str]]:
    with MCP_CONFIG.open("r", encoding="utf-8-sig") as fh:
        config = json.load(fh)
    server = config["mcpServers"]["wenyan-mcp"]
    index_path = server["args"][0]
    env = server.get("env", {})
    app_id = env.get("WECHAT_APP_ID", "")
    app_secret = env.get("WECHAT_APP_SECRET", "")
    if not app_id or not app_secret or PLACEHOLDER_RE.search(app_id + app_secret):
        raise RuntimeError(f"请先在 {MCP_CONFIG} 填写田间里的烟火公众号 AppID/AppSecret")
    return index_path, {
        "WECHAT_APP_ID": app_id,
        "WECHAT_APP_SECRET": app_secret,
    }


def resolve_article_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def article_title(article_path: Path) -> str:
    content = article_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"(?m)^title:\s*[\"']?(.+?)[\"']?\s*$", content)
    if match:
        return match.group(1)
    h1 = re.search(r"(?m)^#\s+(.+?)\s*$", content)
    return h1.group(1) if h1 else article_path.stem


def record_successful_publish(article_path: Path, theme: str, author: str, media_id: str) -> None:
    record = {
        "published_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "article": str(article_path),
        "title": article_title(article_path),
        "theme": theme,
        "media_id": media_id,
        "format": "article",
        "account": "田间里的烟火",
        "author": author,
    }
    PUBLISH_HISTORY.parent.mkdir(exist_ok=True)
    with PUBLISH_HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def cjk_len(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def run_local_checks(article_path: Path, *, skip_ai_check: bool) -> None:
    content = article_path.read_text(encoding="utf-8", errors="ignore")
    title = article_title(article_path)
    if not (8 <= len(title) <= 45):
        raise RuntimeError(f"标题长度异常：{title}")
    if "![](" not in content:
        raise RuntimeError("文章缺少封面图：正文第一张图片会作为公众号封面")
    body_chars = cjk_len(re.sub(r"---.*?---", "", content, count=1, flags=re.S))
    if body_chars < 800:
        raise RuntimeError(f"正文过短：中文字符 {body_chars}，至少需要 800")
    if skip_ai_check:
        return
    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "ai_detector.py"), str(article_path)],
        cwd=BASE_DIR,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("AIGC 检测未通过，已停止发布")


def publish_to_draft(article_path: Path, *, theme: str, author: str) -> str:
    if author != DEFAULT_AUTHOR:
        raise ValueError(f"体制内公众号作者必须为：{DEFAULT_AUTHOR}")
    wenyan_index, wechat_env = load_wenyan_config()
    wenyan_module = Path(wenyan_index).resolve().with_name("customPublish.js")
    if not wenyan_module.exists():
        wenyan_module = Path(wenyan_index).resolve()
    wrapper_module = Path(wenyan_index).resolve().with_name("customWrapper.js")
    if not wrapper_module.exists():
        raise RuntimeError(f"找不到 wenyan-mcp 自定义排版入口：{wrapper_module}")
    script = f"""
import {{ getGzhContent }} from {json.dumps(wrapper_module.as_uri())};
import {{ publishToDraft }} from {json.dumps(wenyan_module.as_uri())};
import {{ readFile }} from "fs/promises";
import {{ dirname, isAbsolute, resolve }} from "path";

const file = {json.dumps(str(article_path))};
const theme = {json.dumps(theme)};
const author = {json.dumps(author)};

try {{
  const articleDir = dirname(file);
  const markdown = (await readFile(file, "utf-8")).replace(
    /!\\[([^\\]]*)\\]\\(([^)]+)\\)/g,
    (match, alt, src) => {{
      if (/^(https?:|data:)/i.test(src) || isAbsolute(src)) return match;
      const absoluteSrc = resolve(articleDir, src).replace(/\\\\/g, "/");
      return `![${{alt}}](${{absoluteSrc}})`;
    }}
  );
  const gzhContent = await getGzhContent(markdown, theme, "solarized-light", true, true);
  const res = await publishToDraft(
    gzhContent.title ?? "Untitled",
    gzhContent.content,
    gzhContent.cover ?? "",
    author
  );
  console.log(JSON.stringify(res, null, 2));
}} catch (err) {{
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
}}
"""
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as fh:
        fh.write(script)
        temp_script = fh.name
    env = os.environ.copy()
    env.update(wechat_env)
    try:
        result = subprocess.run(
            [find_node(), temp_script],
            cwd=BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        Path(temp_script).unlink(missing_ok=True)
    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    if result.returncode != 0:
        raise RuntimeError(output or f"发布进程退出码 {result.returncode}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"发布成功但返回无法解析：{output}") from exc
    media_id = payload.get("media_id")
    if not media_id:
        raise RuntimeError(f"发布返回缺少 media_id：{output}")
    return str(media_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="发布体制内文章到微信公众号草稿箱")
    parser.add_argument("file", help="文章 Markdown 路径，例如 articles/xxx.md")
    parser.add_argument("--theme", default=DEFAULT_THEME)
    parser.add_argument("--author", default=DEFAULT_AUTHOR, choices=(DEFAULT_AUTHOR,))
    parser.add_argument("--skip-ai-check", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    article_path = resolve_article_path(args.file)
    if not article_path.is_file():
        print(f"文章不存在：{article_path}", file=sys.stderr)
        return 1
    try:
        run_local_checks(article_path, skip_ai_check=args.skip_ai_check)
        media_id = publish_to_draft(article_path, theme=args.theme, author=args.author)
        record_successful_publish(article_path, args.theme, args.author, media_id)
    except Exception as exc:
        print(f"发布失败：{exc}", file=sys.stderr)
        return 1
    if args.verbose:
        print(f"已发布到草稿箱：{article_path}")
        print(f"media_id={media_id}")
    else:
        print(media_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
