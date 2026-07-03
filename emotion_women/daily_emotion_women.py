#!/usr/bin/env python3
"""
情感女性公众号自动化生成与发布脚本
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
MCP_CONFIG = Path(__file__).parent / ".mcp.json"
PUBLISH_THEME = "purple"


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


class EmotionWomenAutomation:
    """情感女性公众号自动化处理类"""

    def __init__(
        self,
        working_dir: str = None,
        article_count: int = 3,
        verbose: bool = False,
        publish: bool = False,
    ):
        self.working_dir = working_dir or str(Path(__file__).parent)
        self.article_count = article_count
        self.verbose = verbose
        self.publish = publish
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """加载 prompt 模板"""
        if self.publish:
            publish_step = f"""5. 使用 `mcp__wenyan-mcp__publish_article_from_file` 发布到微信公众号草稿箱：
   - `file_path` 传文章 Markdown 的本地绝对路径
   - `theme_id` 传 `{PUBLISH_THEME}`
   - 不要直接群发，只进入草稿箱
   - 发布失败时记录错误原因，继续处理其他文章"""
            publish_summary = "、草稿箱 media_id 或发布失败原因"
            publish_note = "- 本次需要发布到微信公众号草稿箱，但不直接群发，最终由人工在公众号后台审核后发布。"
        else:
            publish_step = "5. 不发布到公众号，只保存本地 Markdown 草稿"
            publish_summary = ""
            publish_note = "- 本次只生成本地草稿，不调用 wenyan-mcp，不触碰微信公众号。"

        return f"""# 情感女性公众号内容生成任务

## 第一步：搜索情感热点话题

使用 WebSearch 搜索以下方向的近期热点（过去24-48小时），找到有深度切入角度的话题：

**搜索关键词列表**（并行搜索）：
1. "微博 情感 热搜" OR "两性关系 热议"
2. "女性 独立 话题" OR "女性成长"
3. "分手 心理" OR "离婚 女性"
4. "恋爱 困惑" OR "婚姻 问题"
5. "PUA" OR "情感操控" OR "边界感"
6. "内耗" OR "讨好型人格" OR "情绪管理"
7. "原生家庭" OR "亲密关系 模式"
8. site:douban.com "情感" OR "两性"

## 第二步：检查已有文章避免重复

- 检查 `./articles/*.md` 已有文章
- 读取每篇文章的 title（frontmatter）
- 确保新选题与已发布内容不重复

## 第三步：筛选 {self.article_count} 个有深度的选题

**筛选标准**：
- 必须有明确的情感洞察点（不只是表面故事）
- 必须能引发"这说的就是我"的共鸣感
- 优先级：反常识洞察 > 普世痛点 > 热点解读

**选题方向**：
- 两性关系中的隐性问题（控制欲、情绪勒索、沉没成本）
- 女性成长的关键转折（经济独立、人格觉醒、边界建立）
- 情绪与心理健康（内耗识别、自我疗愈、允许不完美）
- 社会热点的女性视角（影视剧解读、社会事件、文化现象）

**如果去重后不足 {self.article_count} 个主题，就写实际找到的数量，宁缺毋滥**

## 第四步：并行启动 emotion-writer agent

为每个筛选出的主题启动一个 emotion-writer agent，传递：
- 选题描述（含切入角度）
- 参考素材/热点链接
- 输出文件路径

每个 agent 需要：
1. 使用 WebSearch 深入研究该话题（心理学背景、真实案例、社会讨论）
2. 从 Unsplash/Pexels 下载 3-5 张氛围配图到 `./images/`
3. 写一篇 1200-1800 字的情感深度文章
4. 保存为 `./articles/YYYYMMDD_HHMM_topic.md`
{publish_step}

**文章要求**：
- 标题有情绪张力（反常识/金句式/悬念）
- 开篇3秒抓住读者（场景代入/反常识/提问/金句）
- 至少1个完整故事场景
- 至少3个值得截图的金句
- 观点犀利但有温度
- 结尾有力量，不烂尾
- 无AI鸡汤味

**选题示例**（仅参考风格，不要直接使用）：
- "那些在朋友圈秀恩爱的人，后来都怎么样了"
- "30岁以后，我学会了一个字：不"
- "他说'我养你'的时候，其实在说'我要控制你'"
- "讨好型人格的人，在爱情里有多累"
- "分手后还做朋友，是成熟还是不甘心"

## 第五步：汇总结果

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

            prompt = self.generate_prompt()

            logger.info(f"工作目录: {self.working_dir}")
            logger.info(f"使用 headless 模式{' [实时输出]' if self.verbose else ''}")

            # 构造 Claude Code headless 命令
            cmd = [
                'claude',
                '-p', prompt,
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
                        logger.info(f"输出:\n{result.stdout}")
                else:
                    logger.error(f"❌ 任务执行失败 (返回码: {result.returncode})")
                    if result.stderr:
                        logger.error(f"错误信息:\n{result.stderr}")

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
    automation = EmotionWomenAutomation(article_count=article_count, verbose=verbose, publish=publish)
    success = automation.run_claude_code()
    return 0 if success else 1


def beijing_to_utc(beijing_time_str: str) -> str:
    """将北京时间 HH:MM 转换为 UTC 时间 HH:MM"""
    hour, minute = map(int, beijing_time_str.split(':'))
    utc_hour = (hour - 8) % 24
    return f"{utc_hour:02d}:{minute:02d}"


def run_scheduled(article_count: int, schedule_times: list = None, verbose: bool = False, publish: bool = False):
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
        automation = EmotionWomenAutomation(article_count=article_count, verbose=verbose, publish=publish)
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
