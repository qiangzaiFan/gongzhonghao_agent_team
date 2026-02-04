#!/usr/bin/env python3
"""
AI 新闻24小时不间断生成系统 V2 - 外部循环版
使用Python外部for循环，每次启动独立的Claude任务，避免context超长
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
        logging.FileHandler(LOG_DIR / f'continuous_v2_{get_beijing_time().strftime("%Y%m")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ContinuousAINewsV2:
    """AI 新闻不间断生成类 V2 - 外部循环版"""

    def __init__(self, working_dir: str = None, parallel_count: int = 5, verbose: bool = False):
        self.working_dir = working_dir or str(Path(__file__).parent)
        self.parallel_count = parallel_count
        self.verbose = verbose

        # 100个搜索关键词池 - 覆盖所有技术领域
        self.all_keywords = [
            # AI 核心 (10个)
            "AI", "artificial intelligence", "machine learning", "deep learning",
            "OpenAI", "ChatGPT", "GPT-5", "GPT-4", "Anthropic", "Claude",

            # Agent 开发 (15个)
            "AI agent", "autonomous agent", "agent framework", "LangChain",
            "LangGraph", "LlamaIndex", "CrewAI", "AutoGPT", "AgentGPT",
            "prompt engineering", "RAG", "retrieval augmented generation",
            "AI workflow", "agent orchestration", "multi-agent system",

            # 大模型公司 (12个)
            "Google AI", "Gemini", "DeepMind", "Meta AI", "LLaMA",
            "Mistral AI", "Cohere", "Stability AI", "Perplexity AI",
            "Character AI", "Midjourney", "Runway ML",

            # Agent 创业 (8个)
            "AI startup", "agent startup", "AI company", "AI unicorn",
            "AI SaaS", "agent platform", "AI funding", "AI investment",

            # 技术论文 (10个)
            "arXiv AI", "AI paper", "machine learning paper", "NeurIPS",
            "ICML", "ICLR", "ACL", "CVPR", "transformer", "attention mechanism",

            # 国内 AI (12个)
            "中国AI", "Chinese AI", "Kimi", "月之暗面",
            "Alibaba AI", "通义千问", "Tencent AI", "混元",
            "ByteDance AI", "豆包", "DeepSeek", "智谱", "MiniMax",

            # 机器人 (8个)
            "humanoid robot", "人形机器人", "Tesla robot", "Optimus",
            "Figure AI", "Boston Dynamics", "robot dog", "industrial robot",

            # 自动驾驶 (8个)
            "autonomous driving", "self-driving", "Tesla FSD", "Waymo",
            "Cruise", "robotaxi", "ADAS", "autonomous vehicle",

            # 航天科技 (6个)
            "SpaceX", "space technology", "satellite", "rocket",
            "commercial space", "space exploration",

            # 脑机接口 (5个)
            "brain-computer interface", "BCI", "Neuralink",
            "neural implant", "neurotechnology",

            # 前沿科技 (16个)
            "quantum computing", "quantum AI", "biotechnology",
            "synthetic biology", "nanotechnology", "AR", "VR",
            "mixed reality", "Web3", "blockchain AI", "crypto AI",
            "edge AI", "AI chip", "GPU", "TPU", "neuromorphic computing",
        ]

        # 确保有100个关键词
        assert len(self.all_keywords) >= 100, f"关键词数量不足100个，当前: {len(self.all_keywords)}"
        logger.info(f"✅ 已加载 {len(self.all_keywords)} 个搜索关键词")

    def create_single_task_prompt(self, keywords: list, round_num: int) -> str:
        """为单次任务创建prompt - 简洁版，避免context过长"""
        keywords_str = '", "'.join(keywords)

        return f"""今天是北京时间 {get_beijing_time().strftime("%Y年%m月%d日 %H:%M")}（第 {round_num} 轮）。

请执行以下任务：

1. **获取北京时间**：运行 `TZ='Asia/Shanghai' date`

2. **检查已发布文章**：使用 Glob 检查 `{self.working_dir}/agent_time_articles/*.md`，避免重复选题

3. **搜索热门话题**：
   - 本轮关键词："{keywords_str}"
   - 使用 Playwright 访问 Google News: https://www.google.com/search?q=[关键词]&tbm=nws
   - 访问 3-5 个科技媒体（TechCrunch, The Verge, VentureBeat等）
   - 使用 WebSearch 补充搜索
   - 优先过去24-48小时的新闻

4. **筛选 {self.parallel_count} 个最佳选题**：
   - 评估：媒体覆盖度、技术创新性、用户共鸣度、完读率潜力
   - 排除已发布的选题
   - 生成高打开率标题（18-25字，包含数字/悬念/对比）

5. **并行启动 {self.parallel_count} 个 ai-news-tech-analyst agent**：
   - 每个 agent 深度搜索、下载图片、撰写文章（1500-2000字）
   - 保存到 {self.working_dir}/agent_time_articles/YYYYMMDD_HHMM_topic.md
   - **立即发布到公众号草稿箱**（使用 mcp__wenyan-mcp__publish_article_from_file）
   - 主题：agentera系列（随机选择配色）

6. **完成即可**：等待所有 agent 发布完成，输出统计信息

要求：
- 文章包含 frontmatter（title, cover）
- 至少 3-7 张配图（绝对路径）
- 不要询问，直接发布
- 失败则压缩图片重试

开始执行！"""

    def run_single_round(self, round_num: int, keywords: list) -> bool:
        """执行单轮任务 - 每次启动独立的Claude进程"""
        try:
            logger.info("="*80)
            logger.info(f"🚀 第 {round_num} 轮任务开始 - {get_beijing_time()}")
            logger.info(f"🔍 关键词: {', '.join(keywords[:5])}...")
            logger.info(f"📊 并行度: {self.parallel_count} 个 agent")
            logger.info("="*80)

            # 生成本轮prompt
            prompt = self.create_single_task_prompt(keywords, round_num)

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
                    # 只显示最后300字符的摘要
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

    def run_continuous_loop(self, max_rounds: int = None):
        """外部for循环 - 每次使用不同关键词"""
        logger.info("🔥 启动24小时不间断生成系统 V2 (外部循环版)")
        logger.info(f"📦 关键词池: {len(self.all_keywords)} 个")
        logger.info(f"📊 并行度: {self.parallel_count} 个 agent/轮")
        logger.info(f"🔄 最大轮次: {'无限' if max_rounds is None else max_rounds}")
        logger.info("="*80)

        round_num = 0
        success_count = 0
        fail_count = 0

        try:
            # 无限循环或指定轮次
            while max_rounds is None or round_num < max_rounds:
                round_num += 1

                # 随机选择3-5个关键词作为本轮搜索方向
                num_keywords = random.randint(3, 5)
                selected_keywords = random.sample(self.all_keywords, num_keywords)

                # 执行单轮任务
                success = self.run_single_round(round_num, selected_keywords)

                if success:
                    success_count += 1
                    logger.info("😴 休息30秒后继续...")
                    time.sleep(30)
                else:
                    fail_count += 1
                    logger.warning("⚠️  失败，等待5分钟后继续...")
                    time.sleep(300)

                # 每10轮输出统计
                if round_num % 10 == 0:
                    logger.info(f"\n📈 累计统计: 成功 {success_count} 轮，失败 {fail_count} 轮\n")

        except KeyboardInterrupt:
            logger.info("\n\n" + "="*80)
            logger.info("👋 系统已手动停止")
            logger.info(f"📊 最终统计:")
            logger.info(f"   - 总轮次: {round_num}")
            logger.info(f"   - 成功: {success_count} 轮")
            logger.info(f"   - 失败: {fail_count} 轮")
            logger.info("="*80)
            return 0
        except Exception as e:
            logger.error(f"\n\n❌ 系统异常: {str(e)}")
            logger.info(f"📊 运行统计: {round_num} 轮 ({success_count} 成功, {fail_count} 失败)")
            return 1


def main():
    parser = argparse.ArgumentParser(
        description='AI 新闻24小时不间断生成系统 V2 - 外部循环版',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 并行度5，无限循环
  python continuous_ai_news_v2.py --parallel 5

  # 并行度10，最多100轮
  python continuous_ai_news_v2.py --parallel 10 --max-rounds 100

  # 后台运行
  nohup python continuous_ai_news_v2.py --parallel 8 > continuous_v2.log 2>&1 &

  # 停止
  pkill -f continuous_ai_news_v2.py
        """
    )

    parser.add_argument(
        '--parallel', '-p',
        type=int,
        default=5,
        help='并行度：每轮同时运行的agent数量（默认: 5）'
    )

    parser.add_argument(
        '--max-rounds',
        type=int,
        default=None,
        help='最大轮次（默认: 无限循环）'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='实时显示执行过程'
    )

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("AI 新闻24小时不间断生成系统 V2 - 外部循环版")
    logger.info("="*80)
    logger.info(f"并行度: {args.parallel}")
    logger.info(f"最大轮次: {'无限' if args.max_rounds is None else args.max_rounds}")
    logger.info(f"实时输出: {'开启' if args.verbose else '关闭'}")
    logger.info(f"北京时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80)

    continuous = ContinuousAINewsV2(
        parallel_count=args.parallel,
        verbose=args.verbose
    )
    return continuous.run_continuous_loop(max_rounds=args.max_rounds)


if __name__ == "__main__":
    exit(main())
