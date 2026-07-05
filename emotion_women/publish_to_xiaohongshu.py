#!/usr/bin/env python3
"""
把一篇「小红书笔记」发布到小红书，通过本地运行的 xiaohongshu-mcp 服务
（默认 http://localhost:18060/mcp）调用其 publish_content 工具。

与公众号不同：小红书没有草稿箱，publish_content 是直接发布。为安全起见，
本脚本默认以 `仅自己可见` 发布（--visibility 可改）。确认没问题后，再用
`--visibility 公开可见` 正式公开。

输入是一个「笔记文件」（Markdown + frontmatter），而不是公众号长文，例如
articles/xhs/xxx.xhs.md：

    ---
    title: 20字以内的小红书标题
    images:
      - https://images.unsplash.com/photo-xxxx?w=1080&q=80
      - /Users/xiao/.../images/local.jpg
    tags:
      - 独处
      - 情绪疗愈
    visibility: 仅自己可见   # 可选，缺省用命令行 --visibility
    ---
    正文（<=1000 字，可含 emoji、换行）...

用法：
    python publish_to_xiaohongshu.py articles/xhs/solo-recovery.xhs.md
    python publish_to_xiaohongshu.py articles/xhs/solo-recovery.xhs.md --visibility 公开可见 -v
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).parent
DEFAULT_MCP_URL = "http://localhost:18060/mcp"
TITLE_LIMIT = 20
CONTENT_LIMIT = 1000
VALID_VISIBILITY = ("仅自己可见", "公开可见", "仅互关好友可见")

def parse_note(path: Path) -> dict:
    """解析笔记文件：frontmatter(YAML 子集) + 正文。不依赖第三方库。"""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("笔记文件必须以 YAML frontmatter（--- 开头）起始")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("frontmatter 格式错误：需要一对 --- 包裹")
    fm_raw, body = parts[1], parts[2]

    meta: dict = {"title": None, "images": [], "tags": [], "visibility": None}
    current_list = None
    for line in fm_raw.splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith("- "):
            item = line.lstrip()[2:].strip().strip('"').strip("'")
            if current_list is not None and item:
                meta[current_list].append(item)
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key in ("images", "tags"):
                current_list = key
                if val:  # 支持行内 [a, b] 或单值
                    val = val.strip("[]")
                    meta[key] = [v.strip().strip('"').strip("'")
                                 for v in val.split(",") if v.strip()]
            elif key in ("title", "visibility"):
                current_list = None
                meta[key] = val
            else:
                current_list = None
    meta["content"] = body.strip()
    return meta


def mcp_call_tool(url: str, tool: str, arguments: dict, verbose: bool = False) -> dict:
    """通过 streamable-HTTP 走一次 MCP JSON-RPC：initialize -> tools/call。"""
    session_id = {"value": None}

    def _post(payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        if session_id["value"]:
            req.add_header("Mcp-Session-Id", session_id["value"])
        with urllib.request.urlopen(req, timeout=180) as resp:
            sid = resp.headers.get("Mcp-Session-Id")
            if sid:
                session_id["value"] = sid
            raw = resp.read().decode("utf-8")
        return _parse_response(raw)

    # 1) initialize
    init = _post({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "emotion-women-publisher", "version": "1.0"},
        },
    })
    if verbose:
        print(f"[mcp] initialized, session={session_id['value']}")
    # 2) notifications/initialized（无返回）
    try:
        _post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
    except urllib.error.HTTPError:
        pass  # 部分实现对通知返回 202/空，忽略
    # 3) tools/call
    result = _post({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    })
    return result


def _parse_response(raw: str) -> dict:
    """兼容纯 JSON 与 SSE（text/event-stream: data: {...}）两种返回。"""
    raw = raw.strip()
    if not raw:
        return {}
    if raw.startswith("{"):
        return json.loads(raw)
    # SSE：取最后一个 data: 行
    last = None
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            last = line[len("data:"):].strip()
    if last:
        return json.loads(last)
    raise ValueError(f"无法解析 MCP 响应：{raw[:200]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="发布小红书笔记（经 xiaohongshu-mcp）")
    parser.add_argument("file", help="笔记文件路径，例如 articles/xhs/xxx.xhs.md")
    parser.add_argument("--url", default=DEFAULT_MCP_URL, help=f"MCP 地址，默认 {DEFAULT_MCP_URL}")
    parser.add_argument("--visibility", default="仅自己可见", choices=VALID_VISIBILITY,
                        help="可见范围，默认『仅自己可见』（验证用），公开请传『公开可见』")
    parser.add_argument("--yes", action="store_true", help="跳过发布前确认（默认需人工确认）")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细过程")
    args = parser.parse_args()

    note_path = Path(args.file)
    if not note_path.is_absolute():
        note_path = BASE_DIR / note_path
    note_path = note_path.resolve()
    if not note_path.exists():
        print(f"错误：笔记文件不存在：{note_path}")
        return 1

    meta = parse_note(note_path)
    title = (meta.get("title") or "").strip()
    content = (meta.get("content") or "").strip()
    images = meta.get("images") or []
    tags = meta.get("tags") or []
    visibility = (meta.get("visibility") or args.visibility).strip()

    # 校验小红书硬约束
    errors = []
    if not title:
        errors.append("缺少标题")
    elif len(title) > TITLE_LIMIT:
        errors.append(f"标题 {len(title)} 字，超过 {TITLE_LIMIT} 字上限")
    if not content:
        errors.append("缺少正文")
    elif len(content) > CONTENT_LIMIT:
        errors.append(f"正文 {len(content)} 字，超过 {CONTENT_LIMIT} 字上限")
    if not images:
        errors.append("至少需要 1 张图片")
    if visibility not in VALID_VISIBILITY:
        errors.append(f"visibility 非法：{visibility}")
    if errors:
        print("发布前校验失败：")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("=" * 56)
    print(f"标题（{len(title)}字）：{title}")
    print(f"正文（{len(content)}字）：")
    print(content)
    print(f"图片（{len(images)}）：")
    for im in images:
        print(f"  - {im}")
    print(f"话题：{' '.join('#' + t for t in tags) if tags else '（无）'}")
    print(f"可见范围：{visibility}")
    print("=" * 56)

    if not args.yes:
        ans = input("确认发布到小红书？(y/N) ").strip().lower()
        if ans not in ("y", "yes"):
            print("已取消。")
            return 0

    arguments = {
        "title": title,
        "content": content,
        "images": images,
        "tags": tags,
        "visibility": visibility,
    }
    try:
        resp = mcp_call_tool(args.url, "publish_content", arguments, verbose=args.verbose)
    except urllib.error.URLError as e:
        print(f"连接 MCP 失败（{args.url}）：{e}")
        print("请确认 xiaohongshu-mcp 已启动，且已完成扫码登录。")
        return 1

    if "error" in resp:
        print("发布失败：")
        print(json.dumps(resp["error"], ensure_ascii=False, indent=2))
        return 1
    result = resp.get("result", resp)
    if result.get("isError"):
        print("发布失败：")
    else:
        print("发布调用完成：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
