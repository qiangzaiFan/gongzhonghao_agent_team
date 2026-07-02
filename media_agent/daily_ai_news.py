#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 科技资讯公众号 —— 每日自动生成脚本

架构：Python 调度层 → Claude Code 主进程（主编 Agent Manager）
      → ai-news-writer 子智能体（写手）→ 输出 Markdown 草稿到 output/

本脚本通过 subprocess 无头调用 Claude Code (`claude -p`)，
注入动态 Prompt（当前北京时间、24h 新闻窗口、去重规则），
由主编搜热点 → 筛选选题 → 分派写手撰写 → 保存草稿。

用法：
    python daily_ai_news.py --now --count 1 --verbose        # 立即生成 1 篇
    python daily_ai_news.py --time 08:00 20:00 --count 3     # 定时每天两次各 3 篇
"""

import argparse
import datetime
import os
import subprocess
import sys
import time
import zoneinfo

# ---------------------------------------------------------------------------
# 路径与常量
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
BEIJING_TZ = zoneinfo.ZoneInfo("Asia/Shanghai")

# Claude Code 允许使用的工具（主编 + 子智能体调度所需）
BASE_TOOLS = [
    "WebSearch",
    "WebFetch",
    "Read",
    "Write",
    "Glob",
    "Grep",
    "Bash",
    "Task",  # 用于分派给 ai-news-writer 子智能体
]

# 发布模式下额外放开的 wenyan-mcp 工具（发到微信公众号草稿箱）
PUBLISH_TOOLS = [
    "mcp__wenyan-mcp__publish_article",
    "mcp__wenyan-mcp__list_themes",
]

# 发布主题（wenyan-mcp 内置主题之一）
PUBLISH_THEME = "lapis"

# .mcp.json 路径（供 --publish 模式加载 wenyan-mcp）
MCP_CONFIG = os.path.join(BASE_DIR, ".mcp.json")


def allowed_tools(publish: bool) -> str:
    tools = BASE_TOOLS + (PUBLISH_TOOLS if publish else [])
    return ",".join(tools)


def beijing_now() -> datetime.datetime:
    return datetime.datetime.now(BEIJING_TZ)


def list_existing_titles(max_items: int = 40) -> list[str]:
    """读取 output/ 下已生成文章的标题，供主编去重。"""
    if not os.path.isdir(OUTPUT_DIR):
        return []
    titles: list[str] = []
    files = sorted(
        (f for f in os.listdir(OUTPUT_DIR) if f.endswith(".md")),
        reverse=True,
    )
    for fname in files[:max_items]:
        fpath = os.path.join(OUTPUT_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("title:"):
                        titles.append(line[len("title:"):].strip())
                        break
        except OSError:
            continue
    return titles


def build_prompt(count: int, publish: bool = False) -> str:
    """构造注入给主编（Claude 主进程）的动态 Prompt。"""
    now = beijing_now()
    now_str = now.strftime("%Y-%m-%d %H:%M")
    window_start = (now - datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")

    existing = list_existing_titles()
    if existing:
        dedup_block = "已发布过的文章标题（禁止重复选题）：\n" + "\n".join(
            f"  - {t}" for t in existing
        )
    else:
        dedup_block = "目前还没有已发布文章，无需去重。"

    if publish:
        publish_block = f"""### 第四步：发布到公众号草稿箱
每篇文章成稿并保存后，用 `wenyan-mcp` 的 `publish_article` 工具把它发布到微信公众号**草稿箱**：
  - 传 `file` 参数为该文章的本地绝对路径（省 token，且 frontmatter 会被正确解析）。
  - 传 `theme_id` 为 `{PUBLISH_THEME}`（本项目指定的排版主题）。
  - **不要**传 `app_id` 参数（本地模式下传它会报错；AppID 已通过环境变量配置）。
  - 若某篇发布失败，记录错误原因并继续处理其余文章，不要中断整批。

### 第五步：汇总"""
        publish_note = "- 发布只到**草稿箱**，不直接群发。人工在公众号后台审核后再正式发布。"
    else:
        publish_block = "### 第四步：汇总"
        publish_note = "- 本次不发布到微信公众号，只生成本地 Markdown 草稿。"

    return f"""你是这个 AI 科技资讯公众号的**主编（Agent Manager）**。当前北京时间：{now_str}。

## 你的任务
今天要产出 {count} 篇高质量的 AI 科技资讯文章。请严格按以下流程执行：

### 第一步：搜索热点
用 WebSearch 搜索 **{window_start} 至 {now_str}（最近 24 小时内）** 的 AI / 科技领域重要资讯。
关注：主流模型发布与更新、AI 产品与功能、重要论文、行业融资与并购、监管政策、算力与芯片。
优先英文一手信源（官方博客、arXiv、Reuters、Bloomberg、TechCrunch、The Verge 等）。

### 第二步：筛选选题
- 从搜索结果中挑出 {count} 个**最有价值、时效性强**的选题。
- 过滤掉：营销软文、无实质信息的传闻、与 24h 窗口无关的旧闻。
- **去重**：不要与下列已发布文章重复选题。
{dedup_block}

### 第三步：分派写手撰写
对**每一个**选定的选题，用 Task 工具调用 `ai-news-writer` 子智能体，让它做深度研究并撰写文章。
在给写手的指令中必须明确：
  1. 具体选题（一句话说清楚写什么）。
  2. 输出路径：`{OUTPUT_DIR}/<YYYYMMDD-HHMM>-<英文短slug>.md`（slug 用小写英文+连字符，例如 `openai-gpt5-release`）。
  3. 要求写手研究后按其自身风格规范写成 Markdown 并保存到该路径。

一个写手只负责一个选题，可以依次分派 {count} 个。

{publish_block}
所有写手完成后，向我报告：每篇文章的标题、文件路径、一句话摘要{"、发布状态（草稿箱 media_id 或失败原因）" if publish else ""}。
如果某个选题因资料不足无法完成，说明原因并跳过，不要编造。

## 硬性规则
- 输出目录 `{OUTPUT_DIR}` 必须存在（若不存在请用 Bash `mkdir -p` 创建）。
- 严禁编造新闻或数据，所有事实必须来自可查证的信源。
{publish_note}
"""


def run_claude(prompt: str, verbose: bool, publish: bool = False) -> int:
    """无头调用 Claude Code 主进程。返回退出码。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    tools = allowed_tools(publish)
    cmd = [
        "claude",
        "-p", prompt,
        "--allowedTools", tools,
        "--permission-mode", "acceptEdits",
    ]
    if publish:
        # 发布模式：加载 .mcp.json 中的 wenyan-mcp，并只信任该配置
        cmd += ["--mcp-config", MCP_CONFIG, "--strict-mcp-config"]
    if verbose:
        cmd += ["--verbose", "--output-format", "stream-json"]

    ts = beijing_now().strftime("%Y-%m-%d %H:%M:%S")
    mode = "发布到草稿箱" if publish else "仅生成本地草稿"
    print(f"[{ts}] 启动主编（Claude Code）—— {mode}……", flush=True)
    if verbose:
        print(f"[cmd] claude -p ... (--allowedTools {tools})", flush=True)

    try:
        # cwd 设为脚本目录，确保 .claude/agents 与 .mcp.json 被自动发现
        result = subprocess.run(cmd, cwd=BASE_DIR)
        return result.returncode
    except FileNotFoundError:
        print("错误：找不到 `claude` 命令，请先安装 Claude Code CLI。", file=sys.stderr)
        return 127
    except KeyboardInterrupt:
        print("\n已中断。", file=sys.stderr)
        return 130


def job(count: int, verbose: bool, publish: bool = False) -> None:
    prompt = build_prompt(count, publish)
    code = run_claude(prompt, verbose, publish)
    ts = beijing_now().strftime("%Y-%m-%d %H:%M:%S")
    if code == 0:
        dest = "已发布到公众号草稿箱" if publish else f"草稿已保存到 {OUTPUT_DIR}/"
        print(f"[{ts}] 完成，{dest}", flush=True)
    else:
        print(f"[{ts}] Claude 退出码 {code}，请检查日志。", file=sys.stderr, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI 科技资讯公众号每日自动生成脚本",
    )
    parser.add_argument("--now", action="store_true",
                        help="立即执行一次，不等待定时调度")
    parser.add_argument("--count", type=int, default=1,
                        help="每次执行生成的文章篇数（默认 1）")
    parser.add_argument("--time", nargs="+", metavar="HH:MM",
                        help="设定每日执行的北京时间，可多个，例如 --time 08:00 20:00")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="输出详细日志")
    parser.add_argument("--publish", action="store_true",
                        help="成稿后通过 wenyan-mcp 发布到微信公众号草稿箱"
                             "（需在 .mcp.json 配好 AppID/Secret 与 wenyan-mcp 路径）")
    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count 必须 >= 1")

    # 立即执行模式
    if args.now or not args.time:
        job(args.count, args.verbose, args.publish)
        if not args.time:
            return

    # 定时调度模式
    if args.time:
        try:
            import schedule
        except ImportError:
            print("错误：定时调度需要 schedule 库，请先 `pip install schedule`。",
                  file=sys.stderr)
            sys.exit(1)

        for t in args.time:
            try:
                datetime.datetime.strptime(t, "%H:%M")
            except ValueError:
                parser.error(f"--time 参数格式错误：{t}（应为 HH:MM）")
            schedule.every().day.at(t, "Asia/Shanghai").do(
                job, args.count, args.verbose, args.publish)

        print(f"已设定定时任务：每天北京时间 {', '.join(args.time)} "
              f"各生成 {args.count} 篇。按 Ctrl+C 退出。", flush=True)
        try:
            while True:
                schedule.run_pending()
                time.sleep(30)
        except KeyboardInterrupt:
            print("\n定时调度已停止。", flush=True)


if __name__ == "__main__":
    main()
