#!/usr/bin/env python3
"""
情感女性公众号自动化生成与发布脚本
支持定时执行或立即执行，可自定义文章数量
"""

import argparse
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 配置日志
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
MCP_CONFIG = BASE_DIR / ".mcp.json"
PUBLISH_THEME = "orangeheart"
ARTICLES_DIR = BASE_DIR / "articles"
IMAGES_DIR = BASE_DIR / "images"
MAX_LOG_OUTPUT_CHARS = 4000

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


class EmotionWomenAutomation:
    """情感女性公众号自动化处理类"""

    def __init__(
        self,
        working_dir: str = None,
        article_count: int = 3,
        verbose: bool = False,
        publish: bool = False,
    ):
        self.working_dir = working_dir or str(BASE_DIR)
        self.article_count = article_count
        self.verbose = verbose
        self.publish = publish
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """加载 prompt 模板"""
        existing_titles = list_existing_titles()
        if existing_titles:
            dedup_block = "\n".join(f"- {title}" for title in existing_titles)
        else:
            dedup_block = "- 暂无"

        if self.publish:
            publish_step = f"""- 保存后依次运行：
  `python3 validate_article_images.py <文章绝对路径>`
  `python3 quality_gate.py <文章绝对路径>`
- 两个本地检查都通过后，调用 `mcp__wenyan-mcp__publish_article`，参数：`file=<文章绝对路径>`、`theme_id={PUBLISH_THEME}`。
- 不要传 `app_id`；不要群发；发布失败只记录原因并继续下一篇。"""
            publish_summary = "、草稿箱 media_id 或发布失败原因"
            publish_note = "- 本次需要发布到微信公众号草稿箱，但不直接群发，最终由人工在公众号后台审核后发布。"
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
2. 配图全部从固定图池 `image_pool.txt` 直接挑：封面从 COVER 段挑 1 张，正文从 BODY 段挑至少 3 张，分散穿插进正文，直接拼 `https://images.unsplash.com/<ID>?w=900` 写进正文。
   - 图池已验证，严禁再搜图、严禁 curl 验证图池 ID、严禁下载图片、严禁跑 Python/PIL 做图像分析。
   - 去重只需避开最近 5 篇已用 ID：`ls -t articles/*.md | head -5 | while read f; do rg -o 'photo-[0-9]+' "$f"; done | sort -u`。
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
- 正文配图至少 4 张（含封面），且图片要分散穿插在正文中间；frontmatter 只写 title，不写 cover。

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
            prompt = self.generate_prompt()
            tools = allowed_tools(self.publish)

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

            if self.publish:
                cmd.extend([
                    '--mcp-config', str(MCP_CONFIG),
                    '--strict-mcp-config'
                ])

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

            logger.info("=" * 60)
            logger.info(f"任务结束 - {get_beijing_time()}")
            logger.info("=" * 60)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            logger.error("❌ 任务执行超时（超过1小时）")
            return False
        except Exception as e:
            logger.error(f"❌ 执行过程中发生错误: {str(e)}")
            logger.exception(e)
            return False


def run_now(article_count: int, verbose: bool = False, publish: bool = False):
    """立即执行任务"""
    logger.info("🚀 立即执行模式")
    automation = EmotionWomenAutomation(
        article_count=article_count, verbose=verbose, publish=publish,
    )
    success = automation.run_claude_code()
    return 0 if success else 1


def beijing_to_utc(beijing_time_str: str) -> str:
    """将北京时间 HH:MM 转换为 UTC 时间 HH:MM"""
    hour, minute = map(int, beijing_time_str.split(':'))
    utc_hour = (hour - 8) % 24
    return f"{utc_hour:02d}:{minute:02d}"


def run_scheduled(article_count: int, schedule_times: list = None, verbose: bool = False,
                  publish: bool = False):
    """定时执行任务（支持多个时间点）- 使用北京时间"""
    import schedule
    import time

    if schedule_times is None:
        schedule_times = ["09:00"]

    logger.info("⏰ 定时执行模式（北京时间）")
    logger.info(f"调度时间: 每天 {', '.join(schedule_times)} 北京时间")
    logger.info(f"文章数量: {article_count} 篇")
    logger.info(f"实时输出: {'开启' if verbose else '关闭'}")
    logger.info(f"发布模式: {'发布到公众号草稿箱' if publish else '仅生成本地草稿'}")

    beijing_now = get_beijing_time()
    logger.info(f"当前北京时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}")

    def job():
        logger.info(f"🚀 定时任务触发 - 北京时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
        automation = EmotionWomenAutomation(
            article_count=article_count, verbose=verbose, publish=publish,
        )
        automation.run_claude_code()

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
    logger.info(f"实时输出: {'开启' if args.verbose else '关闭'}")
    logger.info(f"发布模式: {'发布到公众号草稿箱' if args.publish else '仅生成本地草稿'}")
    logger.info("=" * 60)

    if args.now:
        return run_now(args.count, args.verbose, args.publish)
    else:
        return run_scheduled(args.count, args.time, args.verbose, args.publish)


if __name__ == "__main__":
    exit(main())
