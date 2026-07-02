#!/usr/bin/env python3
"""
arXiv 论文深度解读自动化脚本
从 arXiv 搜索最新的 AI 研究论文（大模型、Agent、预训练、后训练、RL 等方向）
使用 AI agent 撰写深度解读文章并自动发布到微信公众号
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
        logging.FileHandler(LOG_DIR / f'arxiv_papers_{get_beijing_time().strftime("%Y%m")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ArxivPaperAutomation:
    """arXiv 论文深度解读自动化处理类"""

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
        # 获取当前北京时间
        from datetime import timedelta
        beijing_now = get_beijing_time()
        current_time_str = beijing_now.strftime("%Y年%m月%d日 %H:%M:%S")
        # arXiv 论文通常使用7天作为"最新"的窗口期
        cutoff_time = beijing_now - timedelta(days=7)
        cutoff_time_str = cutoff_time.strftime("%Y年%m月%d日")
        cutoff_date_arxiv = cutoff_time.strftime("%Y-%m-%d")

        return f"""⏰ **当前北京时间: {current_time_str}**
📅 **论文时间窗口: 最近7天（{cutoff_time_str} 之后）**

🎓 **任务目标: arXiv 论文深度解读**

本任务旨在从 arXiv 上发现最新、最有价值的 AI 研究论文，并撰写深度解读文章。

请执行以下任务：

1. **确认时间窗口**
   - 当前北京时间: {current_time_str}
   - 论文搜索起始日期: {cutoff_date_arxiv}
   - 只关注最近7天内发布的论文

2. **检查已存在的文章，避免重复选题**
   - 使用 Glob 工具检查 `{self.working_dir}/articles/*.md`
   - 从文件名中识别已解读过的论文（例如：20251102_1430_transformer_optimization.md）
   - 记录所有已存在的选题关键词
   - **在后续选题时必须避开这些已写过的论文主题**

3. **使用 arXiv MCP 工具并行搜索多个研究方向的最新论文**

   使用 `mcp__arxiv__search_papers` 工具，并行搜索以下研究主题：

   **核心搜索主题（每个主题搜索 max_results=15）：**

   a) **大语言模型 (LLM) 基础研究**：
      - 查询: `("large language model" OR "LLM" OR "transformer") AND ("architecture" OR "scaling" OR "optimization")`
      - 分类: `["cs.CL", "cs.LG", "cs.AI"]`
      - 时间: `date_from="{cutoff_date_arxiv}"`

   b) **AI Agent 与多智能体系统**：
      - 查询: `("AI agent" OR "autonomous agent" OR "multi-agent") AND ("reasoning" OR "planning" OR "tool use")`
      - 分类: `["cs.AI", "cs.MA", "cs.CL"]`
      - 时间: `date_from="{cutoff_date_arxiv}"`

   c) **预训练 (Pretraining) 技术**：
      - 查询: `("pretraining" OR "pre-training" OR "self-supervised learning") AND ("language model" OR "transformer")`
      - 分类: `["cs.LG", "cs.CL", "cs.AI"]`
      - 时间: `date_from="{cutoff_date_arxiv}"`

   d) **后训练 (Post-training) 与对齐**：
      - 查询: `("RLHF" OR "reinforcement learning from human feedback" OR "instruction tuning" OR "alignment" OR "post-training")`
      - 分类: `["cs.LG", "cs.AI", "cs.CL"]`
      - 时间: `date_from="{cutoff_date_arxiv}"`

   e) **强化学习 (RL) 在 AI 中的应用**：
      - 查询: `("reinforcement learning") AND ("language model" OR "agent" OR "decision making")`
      - 分类: `["cs.LG", "cs.AI"]`
      - 时间: `date_from="{cutoff_date_arxiv}"`

   f) **提示工程与上下文学习**：
      - 查询: `("prompt engineering" OR "in-context learning" OR "few-shot learning") AND "language model"`
      - 分类: `["cs.CL", "cs.AI", "cs.LG"]`
      - 时间: `date_from="{cutoff_date_arxiv}"`

   g) **检索增强生成 (RAG)**：
      - 查询: `("retrieval augmented generation" OR "RAG" OR "retrieval-based") AND "language model"`
      - 分类: `["cs.CL", "cs.IR", "cs.AI"]`
      - 时间: `date_from="{cutoff_date_arxiv}"`

   h) **模型推理与效率优化**：
      - 查询: `("inference" OR "compression" OR "quantization" OR "distillation") AND "language model"`
      - 分类: `["cs.LG", "cs.CL", "cs.PF"]`
      - 时间: `date_from="{cutoff_date_arxiv}"`

   **搜索技巧**：
   - 对每个主题使用 `sort_by="relevance"` 获取最相关的论文
   - 总共会得到约 120 篇候选论文（8个主题 × 15篇）
   - 记录每篇论文的：arXiv ID、标题、作者、发布日期、摘要、分类、PDF链接

4. **交叉验证与筛选高质量论文**

   从所有搜索结果中筛选出最具价值的论文，评估标准：

   - **技术创新性**（40%权重）：
     * 是否提出新的架构、算法或方法
     * 是否解决了重要的技术难题
     * 是否有理论突破或实证发现

   - **实用价值**（30%权重）：
     * 是否可以应用到实际开发中
     * 是否提供了代码实现或工具
     * 是否对 AI 开发者/研究者有指导意义

   - **学术影响力**（20%权重）：
     * 作者团队是否来自知名机构（OpenAI, Anthropic, Google, Meta等）
     * 是否在社区引起讨论（可通过 WebSearch 搜索论文标题验证）
     * 是否与当前热点方向相关

   - **可读性与解读价值**（10%权重）：
     * 是否有清晰的实验结果和可视化
     * 是否适合撰写深度解读文章
     * 是否能吸引非专业读者

   **⚠️ 重要：质量优先策略**
   - 如果最近7天内的高质量论文不足 {self.article_count} 篇，**自动采用质量优先策略**
   - 宁可发布较少但高质量的论文解读，也不要凑数发布低质量内容
   - 最低标准：至少选择 3 篇真正优质的论文
   - 如果7天内论文不足，自动扩展到14天时间窗口
   - **不需要人工决策，系统自动判断并执行**

5. **使用 WebSearch 和 GitHub 补充论文背景信息**

   对筛选出的候选论文：
   - 搜索论文标题，查找是否有媒体报道、技术博客解读
   - 搜索作者和机构，了解研究背景
   - 如果论文提到开源代码，访问 GitHub 查看项目活跃度
   - 查找相关的讨论（Twitter/X, Reddit, HackerNews等）

6. **最终选题确定（自动质量优先策略）**

   **核心原则：质量 > 数量，自动决策，无需人工干预**

   从候选论文中选出高质量论文进行深度解读：

   - **自动扩展时间窗口策略**：
     * 第一轮：搜索最近7天的论文
     * 如果7天内高质量论文 < 3 篇：自动扩展到14天
     * 如果14天内高质量论文 < 3 篇：自动扩展到21天
     * **最终目标**：至少找到 3-5 篇真正优质的论文
     * **上限目标**：最多 {self.article_count} 篇（如果有足够多的优质论文）

   - **优先级排序**：
     * 第一优先级：知名机构最新突破性研究（OpenAI, Anthropic, Google DeepMind等）
     * 第二优先级：热门方向的实用性研究（Agent开发、RAG优化、模型推理加速等）
     * 第三优先级：有开源代码的研究（方便读者复现和学习）
     * 第四优先级：理论创新但有实际应用潜力的研究

   - **多样性要求**：
     * 避免所有论文都来自同一个研究方向
     * 尽量覆盖 2-3 个不同的主题领域
     * 平衡"基础研究"和"应用研究"

   - **避免重复**：
     * 排除步骤2中已解读过的论文主题
     * 如果多篇论文研究相似问题，只选最优秀的一篇

   - **质量底线**：
     * 每篇论文必须满足至少 2 个高权重评估标准（技术创新性或实用价值）
     * 不要为了凑够数量而选择低质量论文
     * 系统会自动选择实际找到的优质论文数量，可能少于 {self.article_count} 篇

7. **为每篇选中的论文生成"高打开率标题"**（在交给 agent 之前）：

   **论文解读文章的标题公式**：

   a) **技术突破型**（适用于创新性研究）：
      - 格式："[机构]重磅：[技术名称]让[性能指标]提升X倍"
      - 例："OpenAI新研究：这个方法让GPT推理速度提升10倍"
      - 例："Anthropic突破：Constitutional AI如何实现更安全的对齐"

   b) **问题解决型**（适用于解决已知难题的研究）：
      - 格式："解决了！[研究]终于攻克[难题]"
      - 例："解决了！这篇论文终于攻克AI幻觉问题"
      - 例："Agent的记忆难题有解了：这个框架值得关注"

   c) **对比分析型**（适用于比较研究）：
      - 格式："[方法A] vs [方法B]：谁才是[任务]的最优解？"
      - 例："RLHF vs DPO：后训练对齐谁更强？"
      - 例："稠密检索 vs 稀疏检索：RAG系统该如何选择？"

   d) **深度剖析型**（适用于机制研究）：
      - 格式："揭秘：[模型/技术]为什么能[达成效果]"
      - 例："揭秘：GPT-4为什么能理解复杂指令？最新研究给出答案"
      - 例："Transformer注意力机制深度剖析：这些细节你可能不知道"

   e) **实用指南型**（适用于可落地的研究）：
      - 格式："[技术]实战：如何用[方法]提升[指标]X%"
      - 例："RAG实战：如何用这个技巧让检索准确率提升40%"
      - 例："Prompt优化实战：5个技巧让模型输出质量翻倍"

   f) **趋势洞察型**（适用于前沿方向）：
      - 格式："[研究方向]新趋势：[关键发现]将改变AI开发"
      - 例："大模型压缩新趋势：1bit量化如何保持99%性能"
      - 例："Multi-Agent协作新范式：这个框架让AI团队效率提升5倍"

   **标题优化原则**：
   - 包含具体数字或性能指标（提升可信度）
   - 突出技术亮点或实用价值
   - 使用"揭秘"、"突破"、"实战"等动作词
   - 长度控制在 20-30 字（保证信息完整性）
   - 包含核心技术关键词（LLM、Agent、RAG、RLHF等）
   - 保持学术严谨性，避免过度夸张

   **标题质量检查**：
   - [ ] 是否清晰传达论文的核心贡献
   - [ ] 是否包含技术关键词（便于搜索）
   - [ ] 是否有吸引技术读者的亮点
   - [ ] 是否体现实用价值或技术深度
   - [ ] 长度是否合适（20-30字）

8. **为每篇论文并行启动 ai-news-tech-analyst agent**

   为选中的每篇论文启动一个独立的 agent，并行处理以提高效率。

   **传递给每个 agent 的信息必须包含**：
   - 论文 arXiv ID（如：2401.12345）
   - 论文标题（原始英文 + 中文翻译）
   - 作者和机构信息
   - 论文发布日期
   - 论文摘要（英文）
   - arXiv PDF 链接
   - 优化后的中文标题（步骤7生成的吸引人的标题）
   - 论文分类（cs.CL, cs.AI等）
   - 补充信息（如有开源代码、媒体报道等）

9. **每个 agent 需要完成的深度解读任务**

   **阶段1：论文深度阅读与分析**

   - **下载并阅读论文**：
     * 使用 `mcp__arxiv__download_paper` 下载论文
     * 使用 `mcp__arxiv__read_paper` 阅读论文全文
     * 重点关注：摘要、引言、方法、实验、结论

   - **提取核心信息**：
     * 研究动机：解决什么问题？为什么重要？
     * 核心方法：提出了什么新方法/架构/算法？
     * 关键创新：与现有方法的主要区别是什么？
     * 实验结果：在哪些数据集/任务上取得了什么效果？
     * 局限性：论文自身承认的不足或未来工作方向

   **阶段2：补充背景信息和外部资源**

   - **使用 WebSearch 搜索相关信息**：
     * 搜索论文标题，查找是否有技术博客、媒体报道
     * 搜索作者姓名，了解研究背景和以往工作
     * 搜索关键技术术语，寻找相关教程和解释

   - **如果论文提供开源代码**：
     * 使用 WebSearch 或直接访问 GitHub
     * 查看代码仓库的 README、文档
     * 记录 Star 数、Fork 数、最近更新时间
     * 查找使用示例和最佳实践

   - **寻找可视化素材**：
     * 从论文中提取关键图表（架构图、实验结果图）
     * 使用 WebSearch 查找相关的技术图解、流程图
     * 优先选择高清、信息丰富的配图

   **阶段3：撰写深度解读文章**

   文章必须包含以下部分：

   1. **引言**（200-300字）：
      - 用通俗语言介绍论文要解决的问题
      - 说明为什么这个问题重要
      - 引出论文的核心贡献

   2. **背景与动机**（300-400字）：
      - 当前技术的局限性或存在的问题
      - 为什么现有方法不够好
      - 论文的研究动机

   3. **核心方法详解**（500-700字）：
      - 详细解释论文提出的方法/架构
      - 使用图表辅助说明（必须包含）
      - 与现有方法的对比
      - 技术创新点剖析

   4. **实验结果分析**（300-400字）：
      - 在哪些任务/数据集上进行了实验
      - 取得了哪些性能提升（具体数字）
      - 与 baseline 的对比
      - 消融实验的发现

   5. **实用价值与应用前景**（200-300字）：
      - 这个研究对 AI 开发者有什么启发
      - 可能的应用场景
      - 如何在实际项目中借鉴
      - 开源代码和工具推荐（如有）

   6. **局限性与未来展望**（150-200字）：
      - 论文的局限性
      - 未来可能的改进方向
      - 对相关研究的启示

   7. **总结**（100-150字）：
      - 一句话总结论文核心贡献
      - 对读者的建议（是否值得深入研究/使用）
      - 互动引导（引导评论、点赞、分享）

   **文章写作要求**：
   - 总字数：2000-2500 字（论文解读需要更深入）
   - 配图：至少 5-8 张（论文架构图、实验结果图、技术流程图等）
   - 语言风格：专业但易懂，避免过多数学公式，多用类比和示例
   - 使用 Markdown 格式，包含 frontmatter（title, cover）
   - **关键词优化**：在标题、小标题、正文中自然融入技术关键词
   - **主题选择**：使用 agentera 系列主题（agentera-blue 适合学术风格）

   **阶段4：发布文章**

   - **保存文章**：
     * 文件路径：`{self.working_dir}/articles/`
     * 文件名格式：`YYYYMMDD_HHMM_paper_arxiv_id.md`
     * 例如：`20251103_1430_paper_2401_12345.md`

   - **发布到公众号草稿箱**：
     * 使用 `mcp__wenyan-mcp__publish_article_from_file` 发布
     * 作者设置为 "Agent" 或 "AI研究解读"
     * 主题使用 agentera-blue 或其他 agentera 系列
     * **不要询问是否发布，直接执行**
     * 确认收到 media_id 后任务才算完成

   - **发布图片消息到朋友圈**（可选，根据配图质量决定）：
     * 提取文章中最重要的 2-5 张配图
     * 撰写简短评论（1-2句话）+ 话题标签
     * 例如："这篇论文的方法很有意思，值得深入研究。#大模型 #AI研究 #arXiv"

10. **统计成功发布数量（质量优先，无需强制凑数）**

   - **检查方法**：
     * 使用 Glob 检查 `{self.working_dir}/articles/*.md`
     * 统计本次任务新增的文章数量（文件名中包含今天日期）
     * 统计收到的 media_id 数量

   - **自动补充策略**：
     * 如果成功发布数量 < 3 篇（最低底线）：
       - 自动扩大时间窗口（从7天到14天，再到21天）
       - 从候选论文中选择新的论文
       - 启动新一轮 agent 处理
       - 最多循环 2 轮
     * 如果成功发布数量 >= 3 篇但 < {self.article_count} 篇：
       - **直接完成任务，不再补充**
       - 输出说明：已发布 X 篇高质量论文解读（质量优先原则）
     * 如果成功发布数量 >= {self.article_count} 篇：
       - 任务完美完成

   - **成功标准（灵活）**：
     * 理想目标：{self.article_count} 篇
     * 最低底线：3 篇高质量论文
     * **实际发布数量由论文质量决定，系统自动判断**
     * 输出最终统计：成功 X 篇，失败 Y 篇（如有），循环 Z 轮（如有）

---

📋 **任务完成总结**（任务结束时必须输出）：

- 当前北京时间: {current_time_str}
- 论文搜索时间窗口: 初始 {cutoff_date_arxiv} 至今（如有扩展会自动说明）
- 成功发布的文章列表：
  * 文章1标题 - 论文ID：arXiv:XXXX.XXXXX - 发布时间：YYYY-MM-DD ✅
  * 文章2标题 - 论文ID：arXiv:XXXX.XXXXX - 发布时间：YYYY-MM-DD ✅
  * ...
- 搜索的研究方向：LLM基础、Agent、Pretraining、Post-training、RL、Prompt工程、RAG、模型优化
- 候选论文总数：XXX 篇
- 实际发布论文数：X 篇（采用质量优先策略，可能少于目标 {self.article_count} 篇）

请开始执行，确保所有 agent 并行运行以提高效率。

⚠️ **重要提醒**：
- 使用 arXiv MCP 工具进行论文搜索和下载
- 每篇文章必须深度阅读论文全文，不能仅基于摘要
- 文章要有技术深度，但要保持可读性
- 必须包含丰富的配图和技术图表
- **采用质量优先策略：宁缺毋滥，不需要人工决策**
- **自动扩展时间窗口以寻找高质量论文**
- **至少发布3篇，最多发布{self.article_count}篇，由实际论文质量决定**
- 任务结束时输出详细的统计信息"""

    def generate_prompt(self) -> str:
        """生成当天的 prompt（使用北京时间）"""
        today = get_beijing_time().strftime("%Y年%m月%d日")
        return f"今天是北京时间 {today}。\n\n{self.prompt_template}"

    def run_claude_code(self):
        """执行 Claude Code 命令（headless 模式）"""
        try:
            logger.info("="*60)
            logger.info(f"开始执行 arXiv 论文深度解读任务 - {get_beijing_time()}")
            logger.info(f"论文解读文章数量: {self.article_count} 篇")
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
    automation = ArxivPaperAutomation(article_count=article_count, verbose=verbose)
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
    logger.info(f"系统UTC时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def job():
        logger.info(f"🚀 定时任务触发 - 北京时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
        automation = ArxivPaperAutomation(article_count=article_count, verbose=verbose)
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
            next_run_beijing = next_run_utc.replace(tzinfo=None)
            next_run_beijing = datetime.fromtimestamp(
                next_run_utc.timestamp(),
                tz=ZoneInfo("Asia/Shanghai")
            )
            logger.info(f"📅 下次执行时间: 北京时间 {next_run_beijing.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"📅 下次执行时间: UTC {next_run_utc.strftime('%Y-%m-%d %H:%M:%S')}")

    logger.info("⏳ 等待调度...")
    logger.info("💡 系统时区为 UTC，已将北京时间转换为 UTC 调度")

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
        description='arXiv 论文深度解读自动化系统 - 搜索最新 AI 研究论文并生成深度解读文章',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 立即生成 1 篇论文解读文章
  python daily_arxiv_papers.py --now --count 1

  # 立即生成 1 篇文章（实时显示执行过程）
  python daily_arxiv_papers.py --now --count 1 --verbose

  # 立即生成 3 篇论文解读文章
  python daily_arxiv_papers.py --now --count 3

  # 定时每天 08:00 生成 5 篇文章
  python daily_arxiv_papers.py --count 5

  # 定时每天 14:00 生成 2 篇文章（实时输出）
  python daily_arxiv_papers.py --time 14:00 --count 2 -v

  # 定时每天早上8点和晚上8点各生成 10 篇文章
  python daily_arxiv_papers.py --time 08:00 20:00 --count 10

  # 定时多个时间点生成文章（早中晚）
  python daily_arxiv_papers.py --time 08:00 12:00 20:00 --count 5

研究方向：
  - 大语言模型 (LLM) 基础研究
  - AI Agent 与多智能体系统
  - 预训练 (Pretraining) 技术
  - 后训练 (Post-training) 与对齐（RLHF等）
  - 强化学习 (RL) 在 AI 中的应用
  - 提示工程与上下文学习
  - 检索增强生成 (RAG)
  - 模型推理与效率优化
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
        help='生成论文解读文章数量（默认: 5）'
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
    logger.info("arXiv 论文深度解读自动化系统")
    logger.info("="*60)
    logger.info(f"论文解读文章数量: {args.count} 篇")
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
