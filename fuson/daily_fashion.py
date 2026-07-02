#!/usr/bin/env python3
"""
时尚内容定时自动化生成与发布脚本
支持定时执行或立即执行，可自定义文章数量
基于 fashion-editor agent 生成毛衫针织专业内容
"""

import argparse
import subprocess
import logging
import random
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 配置日志
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

def get_beijing_time():
    """获取北京时间"""
    return datetime.now(ZoneInfo("Asia/Shanghai"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'daily_fashion_{get_beijing_time().strftime("%Y%m")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class DailyFashionAutomation:
    """时尚内容定时自动化类"""

    def __init__(self, working_dir: str = None, article_count: int = 5, verbose: bool = False):
        self.working_dir = working_dir or str(Path(__file__).parent)
        self.article_count = article_count
        self.verbose = verbose

        # 毛衫针织品类搜索关键词池 - 100个针织相关关键词
        self.fashion_keywords = [
            # 核心针织术语 (15个)
            "knitwear", "sweater", "knit", "cardigan", "pullover",
            "cashmere sweater", "wool knit", "merino wool", "chunky knit",
            "cable knit", "ribbed knit", "intarsia knit", "jacquard knit",
            "knitted dress", "knit coat",

            # 针织工艺 (12个)
            "hand knit", "machine knit", "circular knit", "flat knit",
            "knitting technique", "knit pattern", "knit texture",
            "3D knitting", "seamless knit", "fully fashioned knit",
            "knit structure", "gauge knitting",

            # 毛衫面料 (15个)
            "cashmere", "merino wool", "alpaca wool", "mohair",
            "angora", "lambswool", "yak wool", "cotton knit",
            "silk blend knit", "wool blend", "recycled yarn",
            "organic wool", "sustainable knit", "performance knit", "technical knit",

            # 毛衫款式 (15个)
            "oversized sweater", "cropped sweater", "turtleneck sweater",
            "V-neck sweater", "crew neck sweater", "mock neck sweater",
            "cardigan coat", "knit vest", "knit polo", "sweater dress",
            "knit skirt", "knit pants", "knit set", "knit co-ord", "knit suit",

            # 针织设计元素 (12个)
            "cable pattern", "fair isle", "argyle pattern", "rib knit",
            "honeycomb knit", "waffle knit", "basketweave knit",
            "colorblock knit", "striped sweater", "gradient knit",
            "cut-out knit", "open knit",

            # 奢侈品牌针织 (12个)
            "Loro Piana cashmere", "Brunello Cucinelli knit", "Hermès knit",
            "Max Mara knit", "The Row knit", "Chanel knit", "Prada knit",
            "Bottega Veneta knit", "Loewe knit", "Jil Sander knit",
            "Gabriela Hearst knit", "Khaite knit",

            # 针织趋势 (10个)
            "oversized knitwear trend", "sheer knit", "layered knitwear",
            "knit as outerwear", "statement sweater", "luxury basics",
            "sustainable knitwear", "vintage knit", "granny chic",
            "quiet luxury knit",

            # 中国针织品牌 (5个)
            "Erdos cashmere", "Shokay yak wool", "1436 cashmere",
            "Angel Chen knit", "Uma Wang knit",

            # 针织搭配 (4个)
            "sweater styling", "knitwear layering", "knit outfit",
            "sweater outfit ideas"
        ]

        logger.info(f"✅ 已加载 {len(self.fashion_keywords)} 个毛衫针织关键词")

    def create_fashion_prompt(self, keywords: list) -> str:
        """创建时尚内容生成prompt"""
        keywords_str = '", "'.join(keywords)

        return f"""今天是北京时间 {get_beijing_time().strftime("%Y年%m月%d日 %H:%M")}。

请执行以下任务：

1. **获取北京时间**：运行 `TZ='Asia/Shanghai' date`

2. **检查已发布文章**：使用 Glob 检查 `{self.working_dir}/articles/*.md`，避免重复选题

3. **搜索毛衫针织热门话题**：
   - 本轮针织关键词："{keywords_str}"
   - 使用 WebSearch 搜索最新毛衫针织资讯（优先过去7-30天）
   - 访问时尚媒体：Vogue Knit, WWD Knitwear, BoF Textiles, Knitting Industry
   - 访问针织品牌官网：Loro Piana, Brunello Cucinelli, The Row, Max Mara等
   - 访问中国羊绒品牌：鄂尔多斯(Erdos)、1436、Shokay等
   - 优先选择：针织系列、毛衫工艺、羊绒材质、针织趋势、搭配指南

4. **筛选 {self.article_count} 个最佳毛衫针织选题**：
   - 评估标准：
     * 视觉吸引力（30%）：针织质感、纹理细节、搭配效果图
     * 工艺价值（25%）：编织技法、面料品质、制作工艺的独特性
     * 实用性（20%）：穿搭场景、保暖性能、护理建议
     * 趋势相关性（15%）：当下针织流行趋势
     * 材质科普（10%）：羊绒、美丽诺羊毛、羊驼毛等材质知识

   - 选题类型（每轮必须聚焦毛衫针织，至少涵盖2-3种）：
     * 品牌毛衫系列解析（Loro Piana、Max Mara、The Row新品）
     * 针织工艺深度解读（手工编织、3D针织、无缝工艺）
     * 羊绒材质科普（山羊绒、羊驼毛、美丽诺羊毛对比）
     * 毛衫搭配指南（不同场合的毛衫造型）
     * 可持续针织（有机羊毛、再生纱线、环保染色）
     * 中国羊绒品牌聚焦（鄂尔多斯、1436等）
     * 毛衫护理养护（羊绒保养、洗涤技巧、收纳方法）
     * 针织趋势分析（oversized毛衫、镂空针织、拼色设计）

   - 排除已发布的选题
   - 生成高打开率标题（18-25字，聚焦针织/毛衫/羊绒关键词）
     * 示例："这件羊绒衫凭什么卖3万？Loro Piana工艺揭秘"
     * 示例："5种针法打造经典毛衫：从cable到intarsia"
     * 示例："山羊绒vs羊驼毛：顶级毛衫材质怎么选"

5. **并行启动 {self.article_count} 个 fashion-editor agent**：
   - 每个 agent 必须聚焦**毛衫针织品类**：
     * 深度搜索针织相关信息（至少4-8个来源）
     * **下载5-8张高质量毛衫针织图片**（必须包含）：
       - 针织成品图（毛衫穿搭效果）
       - 质感细节图（编织纹理、针法特写）
       - 材质对比图（羊绒、羊毛、羊驼毛）
       - 工艺流程图（编织过程、制作细节）
       - 品牌lookbook（Loro Piana、Max Mara等）
       - 搭配示范图（街拍或造型图）
     * 使用 WebFetch 从品牌官网/时尚媒体提取图片URL
     * 使用 curl 下载原始高清图片
     * **使用 Read 工具验证每张图片的质量（针织质感是否清晰）**
     * 压缩大图片（>1MB）使用 sips 命令
     * 撰写1200-1800字的**毛衫针织专业文章**
     * 文章必须视觉先行（图片占60-70%，每200-300字配一张图）
     * 保存到 {self.working_dir}/articles/YYYYMMDD_knitwear_topic.md
     * **立即发布到公众号草稿箱**（使用 mcp__wenyan-mcp__publish_article_from_file）
     * 主题：agentera-rose（时尚内容首选）或agentera-mint（清新风格）

6. **完成即可**：等待所有 agent 发布完成，输出统计信息

毛衫针织文章要求：
- 包含 frontmatter（title, cover）
- **至少5-8张高质量针织图片**（绝对路径，必须体现针织质感）
- 每张图片都要先用 Read 验证质量
- 图片caption突出针织特色（针法、材质、工艺）
- **专业针织分析**（必须包含）：
  * 编织技法（cable、ribbed、intarsia等）
  * 面料材质（羊绒、美丽诺、羊驼毛纤维特性）
  * 纱线支数、密度、柔软度
  * 针织结构、版型设计
  * 保暖性能、透气性
- 毛衫护理建议（洗涤、晾晒、收纳）
- 搭配场景（通勤、休闲、正式场合）
- 不要询问，直接发布
- 失败则压缩图片重试

开始执行！"""

    def generate_prompt(self) -> str:
        """生成当天的时尚内容 prompt（使用北京时间）"""
        # 随机选择3-5个关键词作为搜索方向
        num_keywords = random.randint(3, 5)
        selected_keywords = random.sample(self.fashion_keywords, num_keywords)

        logger.info(f"🔍 本次选择的针织关键词: {', '.join(selected_keywords)}")

        return self.create_fashion_prompt(selected_keywords)

    def run_claude_code(self):
        """执行 Claude Code 命令"""
        try:
            logger.info("="*80)
            logger.info(f"🧶 开始执行时尚内容自动化任务 - {get_beijing_time()}")
            logger.info(f"📊 文章数量: {self.article_count} 篇")
            logger.info("="*80)

            prompt = self.generate_prompt()

            logger.info(f"📁 工作目录: {self.working_dir}")
            logger.info(f"⚙️  模式: {'实时输出' if self.verbose else '静默模式'}")

            # 构造 Claude Code 命令
            cmd = [
                'claude',
                '-p', prompt,
                '--permission-mode', 'bypassPermissions',
                '--output-format', 'text'
            ]

            if self.verbose:
                cmd.append('--verbose')

            # 执行命令
            start_time = datetime.now()

            if self.verbose:
                logger.info("⏳ 执行中（详细模式）...")
                logger.info("-" * 80)
                result = subprocess.run(
                    cmd,
                    cwd=self.working_dir,
                    timeout=7200  # 2小时超时
                )
                logger.info("-" * 80)
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=self.working_dir,
                    timeout=7200
                )

                if result.returncode == 0:
                    logger.info("✅ 任务执行成功")
                    if result.stdout:
                        # 只显示最后300字符的摘要
                        summary = result.stdout[-300:] if len(result.stdout) > 300 else result.stdout
                        logger.info(f"输出摘要:\n...{summary}")
                else:
                    logger.error(f"❌ 任务执行失败 (返回码: {result.returncode})")
                    if result.stderr:
                        logger.error(f"错误信息:\n{result.stderr[-300:]}")

            duration = datetime.now() - start_time
            logger.info(f"⏱️  耗时: {duration.total_seconds()/60:.1f} 分钟")

            if self.verbose and result.returncode == 0:
                logger.info("✅ 任务执行成功")

            logger.info("="*80)
            logger.info(f"任务结束 - {get_beijing_time()}")
            logger.info("="*80)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            logger.error("❌ 任务执行超时（超过2小时）")
            return False
        except Exception as e:
            logger.error(f"❌ 执行过程中发生错误: {str(e)}")
            logger.exception(e)
            return False


def run_now(article_count: int, verbose: bool = False):
    """立即执行任务"""
    logger.info("🚀 立即执行模式")
    automation = DailyFashionAutomation(article_count=article_count, verbose=verbose)
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
    from datetime import datetime

    if schedule_times is None:
        schedule_times = ["09:00"]

    logger.info("⏰ 定时执行模式（北京时间）")
    logger.info(f"⏰ 调度时间: 每天 {', '.join(schedule_times)} 北京时间")
    logger.info(f"📊 文章数量: {article_count} 篇")
    logger.info(f"⚙️  实时输出: {'开启' if verbose else '关闭'}")

    beijing_now = get_beijing_time()
    logger.info(f"🕐 当前北京时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🕐 当前UTC时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

    def job():
        logger.info(f"🚀 定时任务触发 - 北京时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
        automation = DailyFashionAutomation(article_count=article_count, verbose=verbose)
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
        description='时尚内容定时自动化生成与发布系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 立即生成 1 篇时尚文章
  python daily_fashion.py --now --count 1

  # 立即生成 3 篇时尚文章（实时显示执行过程）
  python daily_fashion.py --now --count 3 --verbose

  # 立即生成 5 篇时尚文章
  python daily_fashion.py --now --count 5

  # 定时每天 09:00 生成 5 篇文章
  python daily_fashion.py --count 5

  # 定时每天 14:00 生成 3 篇文章（实时输出）
  python daily_fashion.py --time 14:00 --count 3 -v

  # 定时每天早上9点和下午3点各生成 5 篇文章
  python daily_fashion.py --time 09:00 15:00 --count 5

  # 后台运行定时任务
  nohup python daily_fashion.py --time 09:00 --count 5 > fashion.log 2>&1 &

  # 查看日志
  tail -f fashion.log

  # 停止后台任务
  pkill -f daily_fashion.py
        """
    )

    parser.add_argument(
        '--now',
        action='store_true',
        help='立即执行任务（不等待定时）'
    )

    parser.add_argument(
        '--count', '-c',
        type=int,
        default=5,
        help='生成文章数量（默认: 5）'
    )

    parser.add_argument(
        '--time', '-t',
        type=str,
        nargs='+',
        default=['09:00'],
        help='定时执行时间（北京时间），格式 HH:MM，支持多个时间点用空格分隔（默认: 09:00）'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='实时显示 Claude 执行过程（实时输出模式）'
    )

    args = parser.parse_args()

    # 显示配置
    logger.info("="*80)
    logger.info("🧶 时尚内容定时自动化系统")
    logger.info("="*80)
    logger.info(f"📊 文章数量: {args.count} 篇")
    if args.now:
        logger.info(f"⚙️  执行模式: 立即执行")
    else:
        times_str = ', '.join(args.time) if isinstance(args.time, list) else args.time
        logger.info(f"⚙️  执行模式: 定时执行 ({times_str})")
    logger.info(f"⚙️  实时输出: {'开启' if args.verbose else '关闭'}")
    logger.info(f"🕐 北京时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80)

    # 执行任务
    if args.now:
        return run_now(args.count, args.verbose)
    else:
        return run_scheduled(args.count, args.time, args.verbose)


if __name__ == "__main__":
    exit(main())
