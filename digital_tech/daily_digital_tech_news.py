#!/usr/bin/env python3
"""
数码产品新闻评测自动化生成与发布脚本
支持定时执行或立即执行，可自定义文章数量
"""

import argparse
import subprocess
import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 配置日志
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 获取北京时间
def get_beijing_time():
    """获取北京时间"""
    return datetime.now(ZoneInfo("Asia/Shanghai"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'digital_tech_{get_beijing_time().strftime("%Y%m")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class DigitalTechAutomation:
    """数码产品新闻评测自动化处理类"""

    def __init__(self, working_dir: str = None, article_count: int = 5, verbose: bool = False):
        self.working_dir = working_dir or str(Path(__file__).parent)
        self.article_count = article_count
        self.verbose = verbose
        self.prompt_template = self._load_prompt_template()
        # save prompt to file
        with open(self.working_dir + "/prompt.md", "w") as f:
            f.write(self.prompt_template)

    def _load_prompt_template(self) -> str:
        """加载 prompt 模板"""
        return f"""# 数码产品评测内容生成任务

## 第一步：并行搜索 Google News（过去48小时）

使用 WebFetch 并行搜索以下关键词的 Google News（过去48小时），提取新闻标题、来源和链接：

**搜索 URL 格式**：`https://www.google.com/search?q=[关键词]&tbm=nws&tbs=qdr:d2`

**关键词列表**（并行搜索）：
1. "iPhone review"
2. "Samsung Galaxy"
3. "小米手机"
4. "华为 Mate"
5. "MacBook"
6. "笔记本电脑评测"
7. "AirPods"
8. "智能手表"
9. "折叠屏手机"
10. "相机评测"

每个搜索的 WebFetch prompt: "提取所有新闻标题、来源、发布时间和链接"

## 第二步：检查已有文章避免重复

- 使用 Glob 检查 `./articles/*.md`
- 用 Read 读取每篇文章的 title（frontmatter）
- 记录已写过的产品和主题关键词

## 第三步：从搜索结果中筛选 {self.article_count} 个具体新颖的主题

**筛选标准**：
- 必须是过去48小时内的新闻
- 必须与已有文章主题不重复
- 优先级：新品评测 > 产品对比 > 购买指南 > 技术分析

**重点关注**：
- 新品发布和首发评测
- 产品深度对比（iPhone vs 小米等）
- 购买建议和选购指南
- 真实使用体验和避坑指南

**如果去重后不足 {self.article_count} 个主题，就写实际找到的数量，宁缺毋滥**

## 第四步：并行启动 digital-tech-analyst agent

为每个筛选出的主题启动一个 digital-tech-analyst agent，传递主题描述。

每个 agent 需要：
1. 使用 WebSearch 深入搜索该产品/主题的详细信息
2. 查找官方参数、专业评测、用户反馈
3. 用 curl 下载 5-8 张高质量图片到 `./images/`（产品图、跑分图、实拍样张、对比图）
4. 写一篇 1500-2000 字的数码评测文章（含 frontmatter）
5. 保存为 `./articles/YYYYMMDD_HHMM_product_topic.md`
6. **立即**使用 `mcp__wenyan-mcp__publish_article_from_file` 发布到草稿箱（选择 agentera 系列主题）
7. **发布成功后**，提取文章中的所有图片路径，用 `mcp__wenyan-mcp__publish_image_message` 发布图片消息（简短评论1-2句话 + 3-5个话题标签）

**文章要求**：
- 标题吸引眼球（使用"评测"、"对比"、"值不值得买"等关键词）
- 包含真实体验、优缺点分析、购买建议
- 对比类文章要有参数对比表、价格分析、选购建议
- 1500-2000字，5-8张配图
- 结尾引导互动（开放性问题 + 点赞理由 + 分享动机）

**文章主题示例**：
- 新品评测: "iPhone 16 Pro深度体验：这3个优点和2个槽点你必须知道"
- 产品对比: "小米15 vs 华为Mate 70：拍照谁更强？"
- 购买指南: "3000元档手机推荐：这3款闭眼入不踩坑"
- 使用技巧: "MacBook续航优化：这5个设置能多用3小时"

**重要**：不要询问确认，直接执行所有步骤。并行运行所有 agent 提高效率。"""

    def generate_prompt(self) -> str:
        """生成当天的 prompt（使用北京时间）"""
        today = get_beijing_time().strftime("%Y年%m月%d日")
        return f"今天是北京时间 {today}。\n\n{self.prompt_template}"

    def run_claude_code(self):
        """执行 Claude Code 命令（headless 模式）"""
        try:
            logger.info("="*60)
            logger.info(f"开始执行数码产品评测自动化任务 - {get_beijing_time()}")
            logger.info(f"文章数量: {self.article_count} 篇")
            logger.info("="*60)

            prompt = self.generate_prompt()

            # 设置代理环境变量
            # os.environ['https_proxy'] = 'http://127.0.0.1:7890'
            # os.environ['http_proxy'] = 'http://127.0.0.1:7890'
            # os.environ['all_proxy'] = 'socks5://127.0.0.1:7890'
            # logger.info("✅ 已设置代理: http://127.0.0.1:7890")

            logger.info(f"工作目录: {self.working_dir}")
            logger.info(f"使用 headless 模式 (--print){' [实时输出]' if self.verbose else ''}")

            # 构造 Claude Code headless 命令
            cmd = [
                'claude',
                '-p', prompt,  # -p 参数传递 prompt
            ]

            # 如果开启 verbose，添加 --verbose 参数
            if self.verbose:
                cmd.append('--verbose')

            # 添加其他参数
            cmd.extend([
                '--permission-mode', 'bypassPermissions',  # 绕过所有权限检查（包括 MCP 工具）
                '--output-format', 'text'  # 文本输出
            ])

            # 执行命令
            if self.verbose:
                # verbose 模式：不捕获输出，直接显示 Claude 执行过程
                logger.info("⏳ 正在执行，将显示 Claude 详细执行过程...")
                logger.info("-" * 60)
                result = subprocess.run(
                    cmd,
                    cwd=self.working_dir,
                    timeout=3600
                )
                logger.info("-" * 60)
            else:
                # 静默模式：捕获输出，任务结束后显示
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
                        logger.info(f"输出:\n{result.stdout}")
                else:
                    logger.error(f"❌ 任务执行失败 (返回码: {result.returncode})")
                    if result.stderr:
                        logger.error(f"错误信息:\n{result.stderr}")

            # 检查返回码
            if self.verbose and result.returncode == 0:
                logger.info("✅ 任务执行成功")

            logger.info("="*60)
            logger.info(f"任务结束 - {get_beijing_time()}")
            logger.info("="*60)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            logger.error("❌ 任务执行超时（超过1小时）")
            return False
        except Exception as e:
            logger.error(f"❌ 执行过程中发生错误: {str(e)}")
            logger.exception(e)
            return False


def run_now(article_count: int, verbose: bool = False):
    """立即执行任务"""
    logger.info("🚀 立即执行模式")
    automation = DigitalTechAutomation(article_count=article_count, verbose=verbose)
    success = automation.run_claude_code()
    return 0 if success else 1


def beijing_to_utc(beijing_time_str: str) -> str:
    """将北京时间 HH:MM 转换为 UTC 时间 HH:MM"""
    hour, minute = map(int, beijing_time_str.split(':'))
    # 北京时间是 UTC+8，所以减去8小时
    utc_hour = (hour - 8) % 24
    return f"{utc_hour:02d}:{minute:02d}"


def run_scheduled(article_count: int, schedule_times: list = None, verbose: bool = False):
    """定时执行任务（支持多个时间点）- 使用北京时间"""
    import schedule
    import time
    from datetime import datetime, timedelta

    if schedule_times is None:
        schedule_times = ["08:00"]

    logger.info("⏰ 定时执行模式（北京时间）")
    logger.info(f"调度时间: 每天 {', '.join(schedule_times)} 北京时间")
    logger.info(f"文章数量: {article_count} 篇")
    logger.info(f"实时输出: {'开启' if verbose else '关闭'}")

    beijing_now = get_beijing_time()
    logger.info(f"当前北京时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"系统UTC时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

    def job():
        logger.info(f"🚀 定时任务触发 - 北京时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
        automation = DigitalTechAutomation(article_count=article_count, verbose=verbose)
        automation.run_claude_code()

    # 系统在 UTC 时区，需要将北京时间转换为 UTC 时间
    for beijing_time_str in schedule_times:
        utc_time_str = beijing_to_utc(beijing_time_str)
        schedule.every().day.at(utc_time_str).do(job)
        logger.info(f"✅ 已设置定时任务: 每天 {beijing_time_str} 北京时间 (UTC {utc_time_str})")

    # 显示下次执行时间
    if schedule.jobs:
        next_run_utc = schedule.jobs[0].next_run
        if next_run_utc:
            # 转换为北京时间显示
            next_run_beijing = datetime.fromtimestamp(
                next_run_utc.timestamp(),
                tz=ZoneInfo("Asia/Shanghai")
            )
            logger.info(f"📅 下次执行时间: 北京时间 {next_run_beijing.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"📅 下次执行时间: UTC {next_run_utc.strftime('%Y-%m-%d %H:%M:%S')}")

    logger.info("⏳ 等待调度...")
    logger.info("💡 系统时区为 UTC，已自动将北京时间转换为 UTC 调度")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        logger.info("\n👋 服务已停止")
        return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='数码产品新闻评测自动化生成与发布系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 立即生成 1 篇文章
  python daily_digital_tech_news.py --now --count 1

  # 立即生成 1 篇文章（实时显示执行过程）
  python daily_digital_tech_news.py --now --count 1 --verbose

  # 立即生成 3 篇文章
  python daily_digital_tech_news.py --now --count 3

  # 定时每天 08:00 生成 5 篇文章
  python daily_digital_tech_news.py --count 5

  # 定时每天 14:00 生成 2 篇文章（实时输出）
  python daily_digital_tech_news.py --time 14:00 --count 2 -v

  # 定时每天早上8点和晚上8点各生成 10 篇文章
  python daily_digital_tech_news.py --time 08:00 20:00 --count 10

  # 定时多个时间点生成文章（早中晚）
  python daily_digital_tech_news.py --time 08:00 12:00 20:00 --count 5
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
        default=5,
        help='生成文章数量（默认: 5）'
    )

    parser.add_argument(
        '--time',
        type=str,
        nargs='+',
        default=['08:00'],
        help='定时执行时间，格式 HH:MM，支持多个时间点用空格分隔（默认: 08:00）'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='实时显示 Claude 执行过程（实时输出模式）'
    )

    args = parser.parse_args()

    # 显示配置
    logger.info("="*60)
    logger.info("数码产品评测自动化系统")
    logger.info("="*60)
    logger.info(f"文章数量: {args.count} 篇")
    if args.now:
        logger.info(f"执行模式: 立即执行")
    else:
        times_str = ', '.join(args.time) if isinstance(args.time, list) else args.time
        logger.info(f"执行模式: 定时执行 ({times_str})")
    logger.info(f"实时输出: {'开启' if args.verbose else '关闭'}")
    logger.info("="*60)

    # 执行任务
    if args.now:
        return run_now(args.count, args.verbose)
    else:
        return run_scheduled(args.count, args.time, args.verbose)


if __name__ == "__main__":
    exit(main())
