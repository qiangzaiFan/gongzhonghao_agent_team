#!/usr/bin/env python3
"""
Publish an existing emotion_women Markdown article to WeChat draft box.

Use this after an article has already been generated under articles/ and the
previous publish step failed, for example because the current IP was not in the
WeChat Official Account IP allowlist.
"""

import argparse
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).parent
MCP_CONFIG = BASE_DIR / ".mcp.json"
DEFAULT_THEME = "purple"


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
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="显示 Claude Code 详细执行过程",
    )
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

    prompt = f"""请使用 wenyan-mcp 将已有 Markdown 文章发布到微信公众号草稿箱。

文章路径：{article_path}
排版主题：{args.theme}

要求：
1. 调用 `mcp__wenyan-mcp__publish_article_from_file`。
2. 文件路径使用上面的绝对路径。
3. theme_id 使用 `{args.theme}`。
4. 只发布到草稿箱，不直接群发。
5. 成功后输出草稿箱 media_id；失败则输出完整失败原因。"""

    cmd = [
        "claude",
        "-p",
        prompt,
        "--mcp-config",
        str(MCP_CONFIG),
        "--strict-mcp-config",
        "--permission-mode",
        "bypassPermissions",
        "--output-format",
        "text",
    ]
    if args.verbose:
        cmd.append("--verbose")

    result = subprocess.run(cmd, cwd=BASE_DIR)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
