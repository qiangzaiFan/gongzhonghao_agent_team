#!/usr/bin/env python3
"""Publish an astrology Markdown article to the WeChat draft box."""

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


BASE_DIR = Path(__file__).resolve().parent
MCP_CONFIG = BASE_DIR / ".mcp.json"
DEFAULT_THEME = "agentera-mint"
DEFAULT_AUTHOR = "夏野星座"
PUBLISH_HISTORY = BASE_DIR / "logs" / "publish_history.jsonl"
PLACEHOLDER_RE = re.compile(r"(填|你的|AppID|AppSecret)")
WEEKLY_TABLE_STYLE = (
    "border-collapse:collapse;border-spacing:0;margin:1.2em auto;width:100%;"
    "max-width:100%;table-layout:fixed;overflow:visible;"
)
WEEKLY_CELL_STYLE = "padding:0 2px;border:0;vertical-align:top;font-size:0;line-height:0;"


def load_wenyan_config() -> tuple[str, dict[str, str]]:
    with MCP_CONFIG.open("r", encoding="utf-8-sig") as fh:
        config = json.load(fh)
    server = config["mcpServers"]["wenyan-mcp"]
    env = server.get("env", {})
    app_id = env.get("WECHAT_APP_ID", "")
    app_secret = env.get("WECHAT_APP_SECRET", "")
    if not app_id or not app_secret or PLACEHOLDER_RE.search(app_id + app_secret):
        raise RuntimeError("请先在 astrology_content/.mcp.json 配置星座公众号凭证")
    return server["args"][0], {
        "WECHAT_APP_ID": app_id,
        "WECHAT_APP_SECRET": app_secret,
    }


def article_title(article_path: Path) -> str:
    content = article_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"(?m)^title:\s*[\"']?(.+?)[\"']?\s*$", content)
    if match:
        return match.group(1)
    return article_path.stem


def profile_for(article_path: Path) -> str:
    if "十二星座每日好运" in article_path.name:
        return "daily_fortune"
    if "十二星座一周运势" in article_path.name:
        return "weekly_fortune"
    return "anxia_short"


def preflight(article_path: Path) -> None:
    command = [
        sys.executable,
        str(BASE_DIR / "preflight.py"),
        str(article_path),
        "--profile",
        profile_for(article_path),
        "--release",
        "--allow-untracked",
    ]
    result = subprocess.run(command, cwd=BASE_DIR)
    if result.returncode != 0:
        raise RuntimeError("星座文章发布预检未通过")


def publish_to_draft(article_path: Path, *, theme: str, author: str) -> str:
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
const weeklyTableStyle = {json.dumps(WEEKLY_TABLE_STYLE)};
const weeklyCellStyle = {json.dumps(WEEKLY_CELL_STYLE)};
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
  if (file.includes("十二星座一周运势")) {{
    gzhContent.content = gzhContent.content
      .replace(/<thead>[\\s\\S]*?<\\/thead>/g, "")
      .replace(/<table style="[^"]*">/g, `<table style="${{weeklyTableStyle}}">`)
      .replace(/<td[^>]*>/g, `<td style="${{weeklyCellStyle}}">`);
  }}
  const result = await publishToDraft(
    gzhContent.title ?? "Untitled",
    gzhContent.content,
    gzhContent.cover ?? "",
    author
  );
  console.log(JSON.stringify(result));
}} catch (error) {{
  console.error(error && error.stack ? error.stack : error);
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
            [os.environ.get("NODE_BIN", "node"), temp_script],
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
        raise RuntimeError(f"发布返回无法解析：{output}") from exc
    media_id = payload.get("media_id")
    if not media_id:
        raise RuntimeError(f"发布返回缺少 media_id：{output}")
    return str(media_id)


def update_draft_author(media_id: str, *, author: str, index: int = 0) -> None:
    _, wechat_env = load_wenyan_config()
    script = f"""
const tokenUrl = "https://api.weixin.qq.com/cgi-bin/token";
const getUrl = "https://api.weixin.qq.com/cgi-bin/draft/get";
const updateUrl = "https://api.weixin.qq.com/cgi-bin/draft/update";
const appId = process.env.WECHAT_APP_ID || "";
const appSecret = process.env.WECHAT_APP_SECRET || "";
const mediaId = {json.dumps(media_id)};
const author = {json.dumps(author)};
const index = {index};

try {{
  const tokenResponse = await fetch(`${{tokenUrl}}?grant_type=client_credential&appid=${{appId}}&secret=${{appSecret}}`);
  const tokenPayload = await tokenResponse.json();
  if (!tokenPayload.access_token) throw new Error(JSON.stringify(tokenPayload));
  const accessToken = tokenPayload.access_token;

  const getResponse = await fetch(`${{getUrl}}?access_token=${{accessToken}}`, {{
    method: "POST",
    body: JSON.stringify({{ media_id: mediaId }}),
  }});
  const draft = await getResponse.json();
  if (draft.errcode) throw new Error(JSON.stringify(draft));
  const source = draft.news_item?.[index];
  if (!source) throw new Error(`草稿不存在第 ${{index}} 篇图文`);

  const article = {{
    title: source.title,
    author,
    digest: source.digest || "",
    content: source.content,
    content_source_url: source.content_source_url || "",
    thumb_media_id: source.thumb_media_id,
    need_open_comment: source.need_open_comment ?? 1,
    only_fans_can_comment: source.only_fans_can_comment ?? 0,
  }};
  const updateResponse = await fetch(`${{updateUrl}}?access_token=${{accessToken}}`, {{
    method: "POST",
    body: JSON.stringify({{ media_id: mediaId, index, articles: article }}),
  }});
  const result = await updateResponse.json();
  if (result.errcode !== 0) throw new Error(JSON.stringify(result));
  const verifyResponse = await fetch(`${{getUrl}}?access_token=${{accessToken}}`, {{
    method: "POST",
    body: JSON.stringify({{ media_id: mediaId }}),
  }});
  const verifiedDraft = await verifyResponse.json();
  const verifiedArticle = verifiedDraft.news_item?.[index];
  if (!verifiedArticle || verifiedArticle.author !== author) {{
    throw new Error(`作者回读校验失败：${{JSON.stringify(verifiedDraft)}}`);
  }}
  console.log(JSON.stringify({{ errcode: 0, author: verifiedArticle.author, title: verifiedArticle.title }}));
}} catch (error) {{
  console.error(error && error.stack ? error.stack : error);
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
            [os.environ.get("NODE_BIN", "node"), temp_script],
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
        raise RuntimeError(output or f"更新草稿作者进程退出码 {result.returncode}")


def record(article_path: Path, theme: str, media_id: str, author: str) -> None:
    PUBLISH_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with PUBLISH_HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "published_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "article": str(article_path),
                    "title": article_title(article_path),
                    "theme": theme,
                    "media_id": media_id,
                    "account": author,
                    "author": author,
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def record_author_update(media_id: str, author: str) -> None:
    PUBLISH_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with PUBLISH_HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "action": "author_update",
                    "media_id": media_id,
                    "account": author,
                    "author": author,
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="发布星座文章到微信公众号草稿箱")
    parser.add_argument("file", type=Path, nargs="?")
    parser.add_argument("--theme", default=DEFAULT_THEME)
    parser.add_argument("--author", default=DEFAULT_AUTHOR)
    parser.add_argument("--update-media-id", help="原位更新现有草稿作者，不新增草稿")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    if args.update_media_id:
        try:
            update_draft_author(args.update_media_id, author=args.author)
            record_author_update(args.update_media_id, args.author)
        except Exception as exc:
            print(f"更新草稿作者失败：{exc}", file=sys.stderr)
            return 1
        print(f"已更新草稿作者：media_id={args.update_media_id} author={args.author}")
        return 0
    if args.file is None:
        parser.error("必须提供文章文件，或使用 --update-media-id")
    article_path = args.file if args.file.is_absolute() else BASE_DIR / args.file
    article_path = article_path.resolve()
    if not article_path.is_file():
        print(f"文章不存在：{article_path}", file=sys.stderr)
        return 1
    try:
        if not args.skip_preflight:
            preflight(article_path)
        media_id = publish_to_draft(article_path, theme=args.theme, author=args.author)
        record(article_path, args.theme, media_id, args.author)
    except Exception as exc:
        print(f"发布失败：{exc}", file=sys.stderr)
        return 1
    print(f"已发布到草稿箱：{article_path.name}")
    if args.verbose:
        print(f"media_id={media_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
