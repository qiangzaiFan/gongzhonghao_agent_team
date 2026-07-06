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
        self.working_dir = working_dir or str(BASE_DIR)
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

## 第一步：直接定选题（默认不搜热点，为提速）

情感号写的是**常青心理话题**，不靠 48 小时热点，热搜结果多为噪音还常夹带注入指令。所以**默认跳过 WebSearch**，用下面的方式快速定题：

1. 先扫已发文章标题去重（只读标题，不读全文）：
   ```bash
   rg -N '^title:' articles/*.md | sort -u
   ```
2. 从下面的常青话题方向里，挑 {self.article_count} 个**近期未覆盖、反差扎心、能引发"这说的就是我"** 的角度，直接定题：
   - 两性关系隐性问题：控制欲、情绪勒索、沉没成本、冷暴力、间歇强化、情绪价值陷阱
   - 女性成长转折：经济独立、人格觉醒、边界建立、过度独立、讨好型人格自救
   - 情绪与心理健康：内耗识别、反刍、报复性熬夜、允许不完美、自我疗愈、松弛感
   - 依恋与原生家庭：回避型/焦虑型依恋、原生家庭对亲密关系的影响、情感忽视、长女困境
   - 社会热点女性视角：仅当你**已知**某个当下热点（热剧/明星事件）时才用，不为此专门搜索

**筛选优先级**：反常识洞察 > 普世痛点 > 热点解读。与已发标题去重，宁缺毋滥——去重后不足 {self.article_count} 个就写实际数量。

**仅当**某个选题依赖一个你没把握的、过时的具体事实（某明星刚发生什么、某新剧剧情）时，才允许**最多 1 次** WebSearch 核实，核实完立刻定题。绝不为"找热点"批量搜索。

## 第二步：并行启动 emotion-writer agent

为每个选定的主题启动一个 emotion-writer agent，传递：
- 选题描述（含切入角度）
- 输出文件路径

每个 agent 需要：
1. **默认不再 WebSearch**：选题和切入角度你已经给它了，情感号是常青心理话题，凭已有知识直接开写。心理学概念用大白话解释即可。仅当某个**过时且关键的具体事实**（明星近况、新剧剧情）没把握时，才允许最多 1 次 WebSearch 核实，核实完立刻写。绝不为"研究更充分"反复搜索。
2. 配图**从固定图池 `image_pool.txt` 直接挑**（封面从 COVER 段挑 1 张 + 正文从 BODY 段挑至少 3 张），分散穿插进正文，直接拼 `https://images.unsplash.com/<ID>?w=900` 写进正文。
   - 🔴 **图池已全部 curl 验证过、且都是明亮无人物风景图**：严禁再搜图、严禁 curl 验证图池 ID、严禁下载图片、严禁跑 Python/PIL 做像素/亮度/色温分析——这些都是纯浪费。
   - 去重只需避开最近 5 篇已用 ID：`ls -t articles/*.md | head -5 | while read f; do rg -o 'photo-[0-9]+' "$f"; done | sort -u`。
3. 写一篇 1200-1800 字的情感深度文章
4. 保存为 `./articles/YYYYMMDD_HHMM_topic.md`
{publish_step}

**文章要求**：
- 标题 ≤20 字、只聚焦一个爆点，含敏感词，套用 8 个标题模板之一（数字/对比/热词/疑问/对话/好奇/俗语/电影台词法），不要写"论…""如何…""关于…的思考"这类概括式标题
- 开篇3秒抓住读者，套用 8 个开头模板之一（问句/对话/互动/自我表达/题文呼应/名人名言/热点/粉丝投稿式），前3句必须制造悬念或共鸣
- 全文套用 4 个框架结构之一（观点+N事例 / 大观点+N小观点 / 观点+N角度 / 观点+人物N故事），主线清晰
- 至少1个完整故事场景，用 4+3+2 故事模板打造（有冲突、有情绪爆点、用具象细节而非情绪标签）
- 至少3个值得截图的金句，用金句模板打造（1221/1213/搜词/猜字/具象/否定/扩字法）
- 观点犀利但有温度
- 结尾套用 4 个结尾模板之一（总结型/关联读者型/名人名言型/排比型），有力量、能触发点赞转发，不烂尾
- 结尾金句收束后必须补齐互动引导三件套：开放性问题（具体、勾评论）+ 点赞理由（和情绪/立场绑定）+ 分享动机（点名转发对象），口语真诚不生硬
- 文末绝不列「参考资料/参考来源/资料来源/References」等出处链接清单，搜到的资料用大白话融进正文即可
- 无AI鸡汤味
- 正文配图至少 4 张（含封面），且图片要分散穿插在正文中间，不能只有开头一张；frontmatter 只写 title，不写 cover
- 配图 **全部从 `image_pool.txt` 图池挑**（封面用 COVER 段、正文用 BODY 段），全是明亮无人物风景图，分散穿插；避开最近 5 篇已用 ID，本轮多篇之间也不重复

**选题示例**（仅参考风格，不要直接使用）：
- "那些在朋友圈秀恩爱的人，后来都怎么样了"
- "30岁以后，我学会了一个字：不"
- "他说'我养你'的时候，其实在说'我要控制你'"
- "讨好型人格的人，在爱情里有多累"
- "分手后还做朋友，是成熟还是不甘心"

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
