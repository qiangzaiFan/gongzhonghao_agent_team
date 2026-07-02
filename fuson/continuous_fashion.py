#!/usr/bin/env python3
"""
时尚内容24小时不间断生成系统
支持指定生成数量，使用fashion-editor agent生成时尚相关公众号文章
"""

import argparse
import subprocess
import logging
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import random

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
        logging.FileHandler(LOG_DIR / f'continuous_fashion_{get_beijing_time().strftime("%Y%m")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ContinuousFashion:
    """时尚内容不间断生成类"""

    def __init__(self, working_dir: str = None, parallel_count: int = 5, verbose: bool = False, run_now: bool = False):
        self.working_dir = working_dir or str(Path(__file__).parent)
        self.parallel_count = parallel_count
        self.verbose = verbose
        self.run_now = run_now  # 是否立即执行一次

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

        assert len(self.fashion_keywords) >= 100, f"关键词不足100个，当前: {len(self.fashion_keywords)}"
        logger.info(f"✅ 已加载 {len(self.fashion_keywords)} 个毛衫针织关键词")

    def create_fashion_prompt(self, keywords: list, round_num: int) -> str:
        """创建时尚内容生成prompt"""
        keywords_str = '", "'.join(keywords)

        return f"""今天是北京时间 {get_beijing_time().strftime("%Y年%m月%d日 %H:%M")}（第 {round_num} 轮）。

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

4. **筛选 {self.parallel_count} 个最佳毛衫针织选题**：
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

5. **并行启动 {self.parallel_count} 个 fashion-editor agent**：
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

    def run_single_round(self, round_num: int, keywords: list) -> bool:
        """执行单轮任务"""
        try:
            logger.info("="*80)
            logger.info(f"🧶 第 {round_num} 轮毛衫针织内容任务开始 - {get_beijing_time()}")
            logger.info(f"🔍 针织关键词: {', '.join(keywords[:5])}...")
            logger.info(f"📊 并行度: {self.parallel_count} 个 fashion-editor agent")
            logger.info("="*80)

            # 生成本轮prompt
            prompt = self.create_fashion_prompt(keywords, round_num)

            # 构造Claude命令
            cmd = [
                'claude',
                '-p', prompt,
                '--permission-mode', 'bypassPermissions',
                '--output-format', 'text'
            ]

            if self.verbose:
                cmd.append('--verbose')

            # 执行命令
            start_time = time.time()

            if self.verbose:
                logger.info("⏳ 执行中（详细模式）...")
                result = subprocess.run(cmd, cwd=self.working_dir, timeout=7200)
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=self.working_dir,
                    timeout=7200
                )

            duration = time.time() - start_time

            # 记录结果
            if result.returncode == 0:
                logger.info(f"✅ 第 {round_num} 轮完成")
                if not self.verbose and result.stdout:
                    summary = result.stdout[-300:] if len(result.stdout) > 300 else result.stdout
                    logger.info(f"输出摘要: ...{summary}")
            else:
                logger.error(f"❌ 第 {round_num} 轮失败 (返回码: {result.returncode})")
                if not self.verbose and result.stderr:
                    logger.error(f"错误: {result.stderr[-300:]}")

            logger.info(f"⏱️  耗时: {duration/60:.1f} 分钟")
            logger.info("="*80)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            logger.error(f"❌ 第 {round_num} 轮超时（>2小时）")
            return False
        except Exception as e:
            logger.error(f"❌ 第 {round_num} 轮出错: {str(e)}")
            return False

    def run_once_or_continuous(self, target_count: int = None):
        """
        运行模式：
        - 如果指定了target_count，则生成指定数量的文章后退出
        - 如果没有指定，则24小时不间断运行
        """
        if target_count:
            logger.info(f"🎯 目标生成模式: {target_count} 篇毛衫针织文章")
            logger.info(f"📊 每轮并行度: {self.parallel_count} 个 agent")
            logger.info(f"🔢 预计轮次: {(target_count + self.parallel_count - 1) // self.parallel_count}")
        else:
            logger.info("🔥 启动24小时不间断生成系统（毛衫针织专题）")
            logger.info(f"📊 并行度: {self.parallel_count} 个 agent/轮")

        logger.info(f"📦 关键词池: {len(self.fashion_keywords)} 个针织关键词")
        logger.info("="*80)

        round_num = 0
        success_count = 0
        fail_count = 0
        total_articles = 0

        try:
            # 根据是否指定target_count决定循环条件
            while target_count is None or total_articles < target_count:
                round_num += 1

                # 随机选择3-5个关键词作为本轮搜索方向
                num_keywords = random.randint(3, 5)
                selected_keywords = random.sample(self.fashion_keywords, num_keywords)

                # 如果有目标数量，调整本轮并行度
                current_parallel = self.parallel_count
                if target_count:
                    remaining = target_count - total_articles
                    current_parallel = min(self.parallel_count, remaining)
                    if current_parallel <= 0:
                        break

                # 临时修改并行度（如果需要）
                original_parallel = self.parallel_count
                self.parallel_count = current_parallel

                # 执行单轮任务
                success = self.run_single_round(round_num, selected_keywords)

                # 恢复并行度
                self.parallel_count = original_parallel

                if success:
                    success_count += 1
                    total_articles += current_parallel
                    logger.info(f"📈 累计已生成: {total_articles} 篇文章")

                    # 如果达到目标，退出
                    if target_count and total_articles >= target_count:
                        logger.info(f"🎉 已完成目标：生成 {total_articles} 篇毛衫针织文章")
                        break

                    logger.info("😴 休息30秒后继续...")
                    time.sleep(30)
                else:
                    fail_count += 1
                    logger.warning("⚠️  失败，等待5分钟后继续...")
                    time.sleep(300)

                # 每10轮输出统计
                if round_num % 10 == 0:
                    logger.info(f"\n📈 累计统计: 成功 {success_count} 轮，失败 {fail_count} 轮，约 {total_articles} 篇文章\n")

        except KeyboardInterrupt:
            logger.info("\n\n" + "="*80)
            logger.info("👋 系统已手动停止")
            logger.info(f"📊 最终统计:")
            logger.info(f"   - 总轮次: {round_num}")
            logger.info(f"   - 成功: {success_count} 轮")
            logger.info(f"   - 失败: {fail_count} 轮")
            logger.info(f"   - 约生成文章: {total_articles} 篇")
            logger.info("="*80)
            return 0
        except Exception as e:
            logger.error(f"\n\n❌ 系统异常: {str(e)}")
            logger.info(f"📊 运行统计: {round_num} 轮 ({success_count} 成功, {fail_count} 失败)")
            return 1

        # 正常完成
        logger.info("\n\n" + "="*80)
        logger.info("✅ 任务完成")
        logger.info(f"📊 最终统计:")
        logger.info(f"   - 总轮次: {round_num}")
        logger.info(f"   - 成功: {success_count} 轮")
        logger.info(f"   - 失败: {fail_count} 轮")
        logger.info(f"   - 约生成文章: {total_articles} 篇")
        logger.info("="*80)
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='时尚内容24小时不间断生成系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 立即生成5篇时尚文章，每轮1篇
  python continuous_fashion.py --now --count 5 --parallel 1

  # 立即生成5篇，每轮并行生成5篇（只需1轮）
  python continuous_fashion.py --now --count 5 --parallel 5

  # 并行度5，无限循环（24小时不间断）
  python continuous_fashion.py --parallel 5

  # 后台运行，生成10篇后退出
  nohup python continuous_fashion.py --now --count 10 --parallel 5 > fashion.log 2>&1 &

  # 查看日志
  tail -f fashion.log

  # 停止
  pkill -f continuous_fashion.py
        """
    )

    parser.add_argument(
        '--now',
        action='store_true',
        help='立即执行（否则只是准备好，不自动运行）'
    )

    parser.add_argument(
        '--count', '-c',
        type=int,
        default=None,
        help='目标生成数量（默认: 无限循环）'
    )

    parser.add_argument(
        '--parallel', '-p',
        type=int,
        default=5,
        help='并行度：每轮同时运行的agent数量（默认: 5）'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='实时显示执行过程'
    )

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("毛衫针织内容24小时不间断生成系统")
    logger.info("="*80)
    logger.info(f"运行模式: {'立即执行' if args.now else '准备就绪（加 --now 运行）'}")
    logger.info(f"目标数量: {args.count if args.count else '无限循环'}")
    logger.info(f"并行度: {args.parallel}")
    logger.info(f"实时输出: {'开启' if args.verbose else '关闭'}")
    logger.info(f"北京时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80)

    # 如果没有--now参数，只显示信息不执行
    if not args.now:
        logger.info("⚠️  未指定 --now 参数，脚本不会自动运行")
        logger.info("💡 使用方法：")
        logger.info("   python continuous_fashion.py --now --count 5")
        logger.info("   或后台运行：")
        logger.info("   nohup python continuous_fashion.py --now --count 5 > fashion.log 2>&1 &")
        return 0

    continuous = ContinuousFashion(
        parallel_count=args.parallel,
        verbose=args.verbose,
        run_now=args.now
    )
    return continuous.run_once_or_continuous(target_count=args.count)


if __name__ == "__main__":
    exit(main())
