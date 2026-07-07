#!/usr/bin/env python3
"""
Publish an existing emotion_women Markdown article to WeChat draft box.

Use this after an article has already been generated under articles/ and the
previous publish step failed, for example because the current IP was not in the
WeChat Official Account IP allowlist.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


BASE_DIR = Path(__file__).parent
MCP_CONFIG = BASE_DIR / ".mcp.json"
DEFAULT_THEME = "purple"
NODE_CANDIDATES = [
    Path("/Users/xiao/.nvm/versions/node/v22.22.1/bin/node"),
    Path.home() / ".nvm/versions/node/v22.22.2/bin/node",
    Path("/opt/homebrew/bin/node"),
    Path("/usr/local/bin/node"),
]


def node_major(path: Path) -> int:
    try:
        result = subprocess.run(
            [str(path), "-p", "process.versions.node.split('.')[0]"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return int(result.stdout.strip())
    except Exception:
        return 0


def find_node() -> str:
    nvm_bin = os.environ.get("NVM_BIN")
    if nvm_bin:
        candidate = Path(nvm_bin) / "node"
        if candidate.exists():
            return str(candidate)

    nvm_nodes = sorted(
        (Path.home() / ".nvm/versions/node").glob("*/bin/node"),
        key=node_major,
        reverse=True,
    )
    for candidate in nvm_nodes:
        if candidate.exists() and node_major(candidate) >= 20:
            return str(candidate)

    for candidate in NODE_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return "node"


def load_wenyan_config() -> tuple[str, dict[str, str]]:
    with MCP_CONFIG.open("r", encoding="utf-8") as fh:
        config = json.load(fh)
    server = config["mcpServers"]["wenyan-mcp"]
    index_path = server["args"][0]
    env = server.get("env", {})
    return index_path, {
        "WECHAT_APP_ID": env["WECHAT_APP_ID"],
        "WECHAT_APP_SECRET": env["WECHAT_APP_SECRET"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="发布已有 Markdown 文章到微信公众号草稿箱",
    )
    parser.add_argument("file", help="文章 Markdown 路径，例如 articles/xxx.md")
    parser.add_argument(
        "--theme",
        default=DEFAULT_THEME,
        help=f"wenyan-mcp 排版主题，默认 {DEFAULT_THEME}",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细执行过程")
    args = parser.parse_args()

    article_path = Path(args.file)
    if not article_path.is_absolute():
        article_path = BASE_DIR / article_path
    article_path = article_path.resolve()

    if not article_path.exists():
        print(f"错误：文章不存在：{article_path}")
        return 1
    if not MCP_CONFIG.exists():
        print(f"错误：找不到 MCP 配置：{MCP_CONFIG}")
        return 1

    image_preflight = subprocess.run(
        [sys.executable, str(BASE_DIR / "validate_article_images.py"), str(article_path)],
        cwd=BASE_DIR,
    )
    if image_preflight.returncode != 0:
        print("错误：图片预检未通过，已停止发布。请修复图片后重试。")
        return image_preflight.returncode

    quality_preflight = subprocess.run(
        [sys.executable, str(BASE_DIR / "quality_gate.py"), str(article_path)],
        cwd=BASE_DIR,
    )
    if quality_preflight.returncode != 0:
        print("错误：质量门槛未通过，已停止发布。请修复文章后重试。")
        return quality_preflight.returncode

    wenyan_index, wechat_env = load_wenyan_config()
    # publishArticle 从 dist/publish.js 导出（dist/index.js 只是 MCP server 入口）
    wenyan_module = Path(wenyan_index).resolve().with_name("publish.js")
    if not wenyan_module.exists():
        wenyan_module = Path(wenyan_index).resolve()
    script = f"""
import {{ publishArticle }} from {json.dumps(str(wenyan_module))};

const file = {json.dumps(str(article_path))};
const theme = {json.dumps(args.theme)};

try {{
  const res = await publishArticle("", file, "", theme, undefined, "direct-cli");
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
    cmd = [find_node(), temp_script]
    if args.verbose:
        print(f"发布文件：{article_path}")
        print(f"排版主题：{args.theme}")
    try:
        result = subprocess.run(cmd, cwd=BASE_DIR, env=env)
    finally:
        Path(temp_script).unlink(missing_ok=True)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
