#!/usr/bin/env python3
"""
AI 新闻24小时不间断生成系统 - 极限测试版
支持无限循环生成文章，直到被kill或token耗尽
"""

import argparse
import subprocess
import logging
import os
import time
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
        logging.FileHandler(LOG_DIR / f'continuous_ai_news_{get_beijing_time().strftime("%Y%m")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ContinuousAINews:
    """AI 新闻不间断生成类"""

    def __init__(self, working_dir: str = None, parallel_count: int = 5, verbose: bool = False):
        self.working_dir = working_dir or str(Path(__file__).parent)
        self.parallel_count = parallel_count  # 并行度，不再是文章总数
        self.verbose = verbose
        self.round_counter = 0  # 轮次计数器
        self.total_published = 0  # 总发布数量
        self.total_failed = 0  # 总失败数量

        # 搜索方向池 - 每轮随机选择
        self.search_directions = [
            # AI 核心
            ["AI", "artificial intelligence", "machine learning"],
            ["OpenAI", "ChatGPT", "GPT-5", "GPT-4"],
            ["Anthropic", "Claude", "Claude AI"],
            ["Google AI", "Gemini", "Bard", "DeepMind"],
            ["Meta AI", "LLaMA", "LLaMA 3"],

            # Agent 开发
            ["AI agent", "autonomous agent", "agent framework"],
            ["LangChain", "LangGraph", "LangSmith"],
            ["LlamaIndex", "CrewAI", "AutoGPT"],
            ["prompt engineering", "prompt optimization", "prompt design"],
            ["RAG", "retrieval augmented generation", "vector database"],
            ["AI workflow", "agent orchestration", "multi-agent"],
            ["function calling", "tool use", "AI tools"],

            # Agent 创业与应用
            ["AI startup", "agent startup", "AI company"],
            ["AI application", "agent use case", "AI product"],
            ["AI SaaS", "agent platform", "AI service"],

            # 大模型公司
            ["Mega7", "AI unicorn", "AI valuation"],
            ["Mistral AI", "Cohere", "Stability AI"],
            ["Perplexity AI", "Character AI", "Midjourney"],

            # 技术论文
            ["arXiv AI", "AI paper", "machine learning paper"],
            ["NeurIPS", "ICML", "ICLR", "ACL"],
            ["transformer", "attention mechanism", "neural network"],

            # AI 投资
            ["AI investment", "AI funding", "AI venture capital"],
            ["AI IPO", "AI acquisition", "AI merger"],
            ["AI stock", "AI market", "AI valuation"],

            # 国内 AI
            ["中国AI", "Chinese AI", "China artificial intelligence"],
            ["百度AI", "Baidu AI", "文心一言"],
            ["阿里AI", "Alibaba AI", "通义千问"],
            ["腾讯AI", "Tencent AI", "混元"],
            ["字节AI", "ByteDance AI", "豆包"],
            ["华为AI", "Huawei AI", "盘古"],

            # 机器人
            ["humanoid robot", "人形机器人", "robotic"],
            ["Tesla robot", "Optimus", "Figure AI"],
            ["Boston Dynamics", "robot dog", "autonomous robot"],

            # 自动驾驶
            ["autonomous driving", "self-driving", "自动驾驶"],
            ["Tesla FSD", "Waymo", "Cruise"],
            ["robotaxi", "autonomous vehicle", "ADAS"],

            # 航天科技
            ["SpaceX", "space technology", "航天"],
            ["satellite", "rocket", "space exploration"],
            ["NASA", "commercial space", "space station"],

            # 脑机接口
            ["brain-computer interface", "BCI", "脑机接口"],
            ["Neuralink", "neural implant", "brain chip"],
            ["neurotechnology", "neural interface", "mind control"],

            # 前沿科技
            ["quantum computing", "量子计算", "quantum AI"],
            ["biotechnology", "synthetic biology", "生物技术"],
            ["nanotechnology", "nanotech", "纳米技术"],
            ["AR", "VR", "mixed reality", "元宇宙"],
            ["Web3", "blockchain AI", "crypto AI"],

            # 开发者工具
            ["AI IDE", "AI coding", "code generation"],
            ["GitHub Copilot", "Cursor", "AI code assistant"],
            ["developer tools", "programming AI", "coding assistant"],
        ]

    def _load_prompt_template(self, search_keywords: list) -> str:
        """加载 prompt 模板 - 动态生成搜索关键词"""
        keywords_str = "\n     * ".join([f'"{kw[0]}" 或 "{kw[1]}"' + (f' 或 "{kw[2]}"' if len(kw) > 2 else '') for kw in search_keywords[:10]])

        return f"""请执行以下任务（第 {self.round_counter + 1} 轮）：

1. **首先使用 Bash 执行 `TZ='Asia/Shanghai' date` 命令获取北京时间**
   - 记录当前日期和时间（北京时间）
   - 用于确定"过去24-48小时"的准确时间范围（扩大时间窗口以获取更多选题）

2. **检查已存在的文章，避免重复选题**
   - 使用 Glob 工具检查 `{self.working_dir}/agent_time_articles/*.md`
   - 从文件名中识别已覆盖的主题
   - 记录所有已存在的选题关键词
   - **在后续选题时必须避开这些已写过的主题**

3. **使用 Playwright 搜索 Google News 发现热门话题**
   - **本轮搜索方向（动态变化）**：
     * {keywords_str}

   - 对每个关键词：
     * 使用 mcp__playwright__browser_navigate 访问：https://www.google.com/search?q=[关键词]&tbm=nws
     * 使用 mcp__playwright__browser_snapshot 获取页面内容
     * 提取新闻标题、来源、发布时间、链接
     * 记录所有找到的新闻条目

   - 从所有搜索结果中识别出现频率最高的话题
   - 优先选择多个来源都在报道的重要事件
   - **确认新闻发布时间在过去48小时内（扩大范围）**

4. **访问权威科技媒体网站获取深度报道**
   - 并行访问以下主流科技媒体（随机选择3-5个）：
     * TechCrunch AI: https://techcrunch.com/category/artificial-intelligence/
     * The Verge AI: https://www.theverge.com/ai-artificial-intelligence
     * VentureBeat AI: https://venturebeat.com/category/ai/
     * MIT Technology Review AI: https://www.technologyreview.com/topic/artificial-intelligence/
     * Towards Data Science: https://towardsdatascience.com/
     * Dev.to AI: https://dev.to/t/ai
     * GitHub Trending AI: https://github.com/trending?spoken_language_code=en
     * Hacker News: https://news.ycombinator.com/
     * Product Hunt AI: https://www.producthunt.com/topics/artificial-intelligence

   - 提取首页最新文章的标题、发布时间、链接
   - 交叉验证多个媒体报道的事件

5. **补充使用 WebSearch 和 arXiv 深挖细节**
   - 针对热门话题使用 WebSearch 查找更多技术细节
   - **使用 arXiv search 查找最新 AI 论文（过去7天内）**
   - 关注具体的产品发布、技术突破、重要更新

6. **严格验证新闻时间，优先过去48小时内的事件**：
   - 对每条搜索结果，仔细检查其发布时间
   - **过去24小时内的新闻优先级最高**
   - **24-48小时的新闻可以作为补充**
   - 如果找不到明确发布时间，尝试验证或丢弃

7. 从验证后的结果中筛选出 {self.parallel_count} 个**最具新闻价值的具体事件**：

   - **评估标准（按优先级排序）**：
     * 📊 **媒体覆盖度**（20%）：多渠道报道优先
     * 🔬 **技术创新性**（15%）：技术突破、新产品
     * 🌍 **行业影响力**（15%）：对AI行业的影响
     * 👥 **用户共鸣度**（25%）：痛点、争议、实用价值
     * 📖 **完读率潜力**（25%）：故事性、悬念、实用性、视觉潜力

   - **筛选规则**：
     * 必须排除已识别的选题，确保不重复
     * 优先"高媒体覆盖度 + 高用户共鸣度"
     * "独家深度报道 + 高实用价值"可入选
     * Agent开发/工具/教程类优先
     * 避免纯技术突破但缺乏用户价值的话题
     * **扩大选题范围：AI、Agent、论文、创业、投资、机器人、自动驾驶、航天、脑机接口、前沿科技等**

8. **为每个选中的事件生成"高打开率标题"**：

   - **标题公式（选择最适合的）**：
     * **反常识型**："90%的人不知道：[产品]这个功能能省80%时间"
     * **悬念型**："[公司]突然下架这个功能，背后原因让人深思"
     * **对比型**："[产品A] vs [产品B]：谁更适合中国用户？"
     * **痛点型**："AI工程师薪资暴跌50%？真相是这样的"
     * **数据冲击型**："7天，100万用户：这个AI工具是如何做到的"
     * **实战技巧型**："3行代码实现[功能]：Agent开发最佳实践"
     * **工具推荐型**："这个开源工具让Agent开发效率提升10倍"
     * **论文解读型**："Nature封面：这篇AI论文改变了整个行业"
     * **创业故事型**："从0到独角兽：这个AI创业公司只用了6个月"
     * **投资分析型**："AI投资热潮：这些赛道最值得关注"

   - **标题优化原则**：
     * 包含具体数字（提升点击率）
     * 触及用户关注点：效率、成本、职业、技能
     * 制造悬念或冲突
     * 长度控制在 18-25 字
     * 包含核心关键词（SEO优化）
     * 避免标题党，保持专业性

9. 为每个事件并行启动 ai-news-tech-analyst agent（共 {self.parallel_count} 个并行任务）

10. 每个 agent 需要针对该具体事件完成以下步骤：
   - 深度搜索事件的详细信息（至少3-5个来源）
   - 如果是开发相关主题，额外搜索：GitHub、技术文档、代码示例
   - 如果是论文相关，使用 arXiv 工具深度解读
   - 下载事件相关的高质量图片（产品图、技术图表、代码截图等）

   - **撰写文章时，必须优化推荐算法指标**：
     * 关键词密度优化（1%-3%）
     * 内容垂直度优化（聚焦单一主题）
     * 互动引导优化（引导评论/点赞/分享）

   - 撰写一篇深度分析的公众号文章（包含 frontmatter）
   - **保存文章为 .md 文件到 {self.working_dir}/agent_time_articles/**
   - **文件名格式：YYYYMMDD_HHMM_topic_keywords.md**
   - **立即使用 mcp__wenyan-mcp__publish_article_from_file 发布到公众号草稿箱**

文章要求：
- 标题聚焦具体事件，吸引眼球（使用步骤8生成的高打开率标题）
- 内容深度解析事件的技术细节、行业意义、未来影响
- **开发类文章包含：场景、代码、实践、避坑指南**
- **论文类文章包含：核心创新、技术解读、应用前景**
- **创业类文章包含：商业模式、竞争优势、投资价值**
- **文章长度 1500-2000 字**
- 至少包含 3-7 张配图（绝对路径）
- 使用 Markdown 格式，包含 frontmatter（title, cover）
- **主题只使用agentera系列**（随机选择配色）

**CRITICAL - 发布是必需步骤**:
- 每个 agent 必须完成发布到草稿箱，确认收到 media_id
- 不要询问是否发布，直接执行
- 发布失败则压缩图片后重试

11. **统计本轮发布情况**：
   - 等待所有 agent 完成后，统计成功发布的文章数量
   - 统计失败的文章数量和原因
   - 输出本轮统计：成功 X 篇，失败 Y 篇
   - **不管成功多少篇，都进入下一轮循环**

请开始执行第 {self.round_counter + 1} 轮任务，确保所有 agent 并行运行以提高效率。"""

    def generate_prompt(self, search_keywords: list) -> str:
        """生成当轮的 prompt"""
        today = get_beijing_time().strftime("%Y年%m月%d日 %H:%M")
        return f"当前北京时间：{today}（第 {self.round_counter + 1} 轮）。\n\n{self._load_prompt_template(search_keywords)}"

    def get_random_search_keywords(self):
        """随机选择搜索方向"""
        import random
        # 每轮随机选择10-15个搜索方向
        num_keywords = random.randint(10, 15)
        return random.sample(self.search_directions, min(num_keywords, len(self.search_directions)))

    def run_single_round(self):
        """执行单轮任务"""
        try:
            self.round_counter += 1
            logger.info("="*80)
            logger.info(f"🚀 开始第 {self.round_counter} 轮任务 - {get_beijing_time()}")
            logger.info(f"并行度: {self.parallel_count} 个 agent")
            logger.info(f"累计发布: {self.total_published} 篇")
            logger.info("="*80)

            # 随机选择本轮搜索方向
            search_keywords = self.get_random_search_keywords()
            logger.info(f"📍 本轮搜索方向: {', '.join([kw[0] for kw in search_keywords[:5]])}...")

            prompt = self.generate_prompt(search_keywords)

            # 构造 Claude Code headless 命令
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
                logger.info("⏳ 正在执行，将显示详细过程...")
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
                    logger.info(f"✅ 第 {self.round_counter} 轮执行成功")
                    if result.stdout:
                        # 从输出中提取成功/失败数量
                        output = result.stdout
                        if "成功" in output or "篇" in output:
                            logger.info(f"输出摘要:\n{output[-500:]}")  # 只显示最后500字符
                else:
                    logger.error(f"❌ 第 {self.round_counter} 轮执行失败 (返回码: {result.returncode})")
                    if result.stderr:
                        logger.error(f"错误信息:\n{result.stderr[-500:]}")

            duration = time.time() - start_time
            logger.info(f"⏱️  本轮耗时: {duration/60:.1f} 分钟")
            logger.info("="*80)
            logger.info(f"第 {self.round_counter} 轮结束 - {get_beijing_time()}")
            logger.info("="*80)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            logger.error(f"❌ 第 {self.round_counter} 轮执行超时（超过2小时）")
            return False
        except Exception as e:
            logger.error(f"❌ 第 {self.round_counter} 轮执行出错: {str(e)}")
            logger.exception(e)
            return False

    def run_continuous(self):
        """24小时不间断运行"""
        logger.info("🔥 启动24小时不间断生成系统")
        logger.info(f"并行度: {self.parallel_count} 个 agent/轮")
        logger.info(f"工作目录: {self.working_dir}")
        logger.info(f"实时输出: {'开启' if self.verbose else '关闭'}")
        logger.info("💡 系统将持续运行，直到:")
        logger.info("   1. 手动 kill 进程")
        logger.info("   2. 账号 token 用尽")
        logger.info("   3. 系统报错退出")
        logger.info("="*80)

        try:
            while True:
                success = self.run_single_round()

                if not success:
                    logger.warning(f"⚠️  第 {self.round_counter} 轮失败，等待5分钟后继续...")
                    time.sleep(300)  # 失败后等待5分钟
                else:
                    # 成功后短暂休息，避免请求过快
                    logger.info("😴 休息30秒后开始下一轮...")
                    time.sleep(30)

        except KeyboardInterrupt:
            logger.info("\n\n" + "="*80)
            logger.info(f"👋 系统已手动停止")
            logger.info(f"📊 运行统计:")
            logger.info(f"   - 总轮次: {self.round_counter}")
            logger.info(f"   - 总耗时: 查看日志")
            logger.info("="*80)
            return 0
        except Exception as e:
            logger.error(f"\n\n❌ 系统异常退出: {str(e)}")
            logger.exception(e)
            logger.info(f"📊 运行统计:")
            logger.info(f"   - 总轮次: {self.round_counter}")
            logger.info("="*80)
            return 1


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='AI 新闻24小时不间断生成系统 - 极限测试版',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 以并行度5运行（每轮5个agent并行）
  python continuous_ai_news.py --parallel 5

  # 以并行度10运行，开启实时输出
  python continuous_ai_news.py --parallel 10 --verbose

  # 后台运行，并行度8
  nohup python continuous_ai_news.py --parallel 8 > continuous.log 2>&1 &

  # 查看日志
  tail -f continuous.log

  # 停止运行
  pkill -f continuous_ai_news.py
        """
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
        help='实时显示 Claude 执行过程'
    )

    args = parser.parse_args()

    # 显示配置
    logger.info("="*80)
    logger.info("AI 新闻24小时不间断生成系统 - 极限测试版")
    logger.info("="*80)
    logger.info(f"并行度: {args.parallel} 个 agent/轮")
    logger.info(f"实时输出: {'开启' if args.verbose else '关闭'}")
    logger.info(f"当前北京时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80)

    # 执行任务
    continuous = ContinuousAINews(parallel_count=args.parallel, verbose=args.verbose)
    return continuous.run_continuous()


if __name__ == "__main__":
    exit(main())
