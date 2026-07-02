#!/usr/bin/env python3
"""
AI 新闻自动化生成与发布脚本
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
        logging.FileHandler(LOG_DIR / f'ai_news_{get_beijing_time().strftime("%Y%m")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class AINewsAutomation:
    """AI 新闻自动化处理类"""

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
        cutoff_time = beijing_now - timedelta(hours=24)
        cutoff_time_str = cutoff_time.strftime("%Y年%m月%d日 %H:%M:%S")

        return f"""⏰ **当前北京时间: {current_time_str}**
📅 **24小时截止时间: {cutoff_time_str}**

‼️ **CRITICAL - 时效性要求（最高优先级）**:
- ✅ 只接受 {cutoff_time_str} 之后发布的新闻
- ❌ 早于 {cutoff_time_str} 的新闻一律丢弃
- ❌ 找不到明确发布时间的新闻一律丢弃
- ⚠️ 宁可文章数量不足 {self.article_count} 篇，也绝不使用旧新闻
- 🔍 每条新闻必须人工验证发布时间，不能仅依赖"X小时前"这样的模糊表述

请执行以下任务：

1. **确认当前时间和24小时窗口**
   - 当前北京时间: {current_time_str}
   - 24小时前: {cutoff_time_str}
   - 只接受这个时间窗口内发布的新闻

2. **检查已存在的文章，避免重复选题**
   - 使用 Glob 工具检查 `{self.working_dir}/agent_time_articles/*.md`
   - 从文件名中识别已覆盖的主题（例如：20251002_1430_bolt_new_v2.md 表示已写过 bolt.new v2）
   - 记录所有已存在的选题关键词
   - **在后续选题时必须避开这些已写过的主题**

3. **使用 WebFetch 搜索 Google News 发现热门 AI 话题（必须附带时间过滤）**
   - ⚠️ **搜索时必须使用时间过滤参数**：在URL中添加 `&tbs=qdr:d` 参数（过去24小时）
   - 完整URL格式：`https://www.google.com/search?q=[关键词]&tbm=nws&tbs=qdr:d`
   - 并行搜索多个关键词组合（建议至少8个不同关键词）：
     * "AI" 或 "artificial intelligence"
     * "OpenAI" 或 "ChatGPT" 或 "GPT"
     * "Anthropic" 或 "Claude"
     * "LLM" 或 "large language model"
     * "machine learning" 或 "deep learning"
     * "AI agent" 或 "autonomous agent"
     * **"AI agent development" 或 "agent framework"（Agent开发框架）**
     * **"LangChain" 或 "LlamaIndex" 或 "CrewAI"（Agent开发工具）**
     * **"prompt engineering" 或 "prompt optimization"（Prompt工程技巧）**
     * **"RAG" 或 "retrieval augmented generation"（RAG技术）**
     * **"AI workflow" 或 "agent orchestration"（Agent编排）**
     * **"function calling" 或 "tool use"（工具调用技术）**
     * 其他相关热词（如特定公司/产品名）

   - 对每个关键词：
     * 使用 WebFetch 访问：https://www.google.com/search?q=[关键词]&tbm=nws&tbs=qdr:d
     * prompt 设置为："提取所有新闻标题、来源、发布时间和链接"
     * 提取新闻标题、来源、**精确发布时间**、链接
     * **立即验证发布时间**：必须是具体日期时间（如"2025-10-13 08:30"），拒绝模糊时间（如"5小时前"）
     * 只记录发布时间在 {cutoff_time_str} 之后的新闻条目

   - 从所有搜索结果中识别出现频率最高的话题
   - 优先选择多个来源都在报道的重要事件
   - **再次验证：所有保留的新闻发布时间必须晚于 {cutoff_time_str}**

4. **访问权威科技媒体网站获取深度报道**
   - 并行访问以下主流科技媒体（选择3-5个）：
     * TechCrunch AI: https://techcrunch.com/category/artificial-intelligence/
     * The Verge AI: https://www.theverge.com/ai-artificial-intelligence
     * Bloomberg Technology: https://www.bloomberg.com/technology
     * VentureBeat AI: https://venturebeat.com/category/ai/
     * MIT Technology Review AI: https://www.technologyreview.com/topic/artificial-intelligence/
     * Ars Technica AI: https://arstechnica.com/tag/artificial-intelligence/
     * Wired AI: https://www.wired.com/tag/artificial-intelligence/
     * CNBC Technology: https://www.cnbc.com/technology/
     * **Towards Data Science: https://towardsdatascience.com/ （Agent开发教程）**
     * **Dev.to AI: https://dev.to/t/ai （开发者实践分享）**
     * **GitHub Trending AI: https://github.com/trending?spoken_language_code=en （开源Agent项目）**

   - 对每个网站：
     * 使用 WebFetch 访问，prompt 设置为："提取首页最新文章的标题、发布时间和链接"
     * 提取首页最新文章的标题、**精确发布时间**、链接
     * **立即验证时间**：只保留发布时间在 {cutoff_time_str} 之后的文章
     * 丢弃所有无法确定具体发布时间的文章

   - 交叉验证：
     * 找出在多个权威媒体都有报道的事件（优先级最高）
     * 记录独家深度报道（技术分析价值高）
     * 整合 Google News 和科技媒体的发现
     * **最终保留的所有新闻必须晚于 {cutoff_time_str}**

5. **补充使用 WebSearch 深挖细节（必须验证时间）**
   - 针对在 Google News 中发现的热门话题
   - 使用 WebSearch 查找更多技术细节和官方信息
   - 搜索时使用具体日期过滤（如：after:{cutoff_time.strftime("%Y-%m-%d")}）
   - 关注具体的产品发布、技术突破、重要更新
   - **访问原文页面，获取精确发布时间，再次验证是否在24小时内**

6. **最终时间验证检查点（CRITICAL）**：
   - 当前时间：{current_time_str}
   - 24小时前：{cutoff_time_str}
   - 对每条候选新闻，执行三重验证：
     * ✅ 检查1：是否有明确的发布日期和时间
     * ✅ 检查2：发布时间是否晚于 {cutoff_time_str}
     * ✅ 检查3：如有疑问，访问原文页面再次确认
   - **如果任何一项检查失败，立即丢弃该新闻**
   - **宁可文章数量为 0，也绝不使用旧新闻或时间不明的新闻**

7. 从验证后的结果中筛选出最多 {self.article_count} 个**最具新闻价值的具体事件**：
   - ⚠️ **前提条件：所有候选事件的发布时间必须晚于 {cutoff_time_str}**
   - 每个事件应该是独立、明确的新闻（如：Thinking Machines Lab 发布 Tinker 产品）

   - **评估标准（按优先级排序，权重总计100%）**：
     * 📊 **媒体覆盖度**（权重 20%）：
       - 在多个渠道都有报道（Google News + 2个以上科技媒体）= 高优先级
     * 🔬 **技术创新性**（权重 15%）：技术突破、新产品发布、重大更新
     * 🌍 **行业影响力**（权重 15%）：对AI行业的潜在影响
     * 👥 **用户共鸣度**（权重 25%，核心指标）：
       - 话题是否触及用户痛点（效率提升、成本降低、职业焦虑、技能学习）
       - 是否有争议性/对比性（容易引发讨论和分享）
       - 是否有实用价值（读者能获得可操作的建议或启发）
       - **是否包含开发技巧/最佳实践（Agent开发者特别关注）**
       - 是否有情感共鸣（成功故事、失败教训、行业变革）
     * 📖 **完读率潜力**（权重 25%，核心指标）：
       - 故事性：是否有人物、冲突、转折、结局（叙事吸引力）
       - 悬念性：是否有未解之谜、结果揭秘、意外发现（好奇心驱动）
       - 实用性：读者读完能获得什么具体收获（工具推荐、方法论、行业洞察、**开发技巧**）
       - 视觉潜力：是否有丰富的图表、数据可视化、产品截图、**代码示例**（视觉停留点）

   - **筛选规则**：
     * ‼️ **第一优先级：时效性验证** - 所有选中事件发布时间必须晚于 {cutoff_time_str}
     * 必须排除步骤2中已识别的选题，确保选题不重复
     * 优先选择"高媒体覆盖度 + 高用户共鸣度"的话题（容易获得推荐流量）
     * "独家深度报道 + 高实用价值"的话题也可入选（搜一搜流量）
     * **"Agent开发技巧/工具发布 + 实用代码示例"优先入选（开发者受众）**
     * **Prompt工程、RAG优化、工具调用等技术实践类内容优先级提升**
     * 避免"纯技术突破但缺乏用户价值"的话题（完读率低）
     * **最终确认：输出选题时，必须同时输出每个事件的精确发布时间和来源**
     * 如果24小时内的新闻不足 {self.article_count} 个，只生成实际找到的数量
     * ⚠️ **绝对禁止使用超过24小时的旧新闻来凑数**

8. **为每个选中的事件生成"高打开率标题"**（在交给 agent 之前）：

   - **标题公式（选择最适合该事件的一种）**：
     * **反常识型**："90%的人不知道：[产品名]这个功能能省80%时间"
       - 适用场景：功能更新、使用技巧
       - 例："ChatGPT这个隐藏功能，90%的用户都不知道"

     * **悬念型**："[公司名]突然下架这个功能，背后原因让人深思"
       - 适用场景：产品变更、战略调整
       - 例："OpenAI为什么突然限制GPT-4的访问？"

     * **对比型**："[产品A] vs [产品B]：谁更适合中国用户？"
       - 适用场景：竞品分析、产品评测
       - 例："Claude vs ChatGPT：技术写作谁更强？"

     * **痛点型**："AI工程师薪资暴跌50%？真相是这样的"
       - 适用场景：行业变化、职业影响
       - 例："大模型让程序员失业？这5个岗位反而更吃香"

     * **数据冲击型**："7天，100万用户：这个AI工具是如何做到的"
       - 适用场景：增长故事、产品发布
       - 例："24小时获得10万star，这个开源项目凭什么？"

     * **实战技巧型**："3行代码实现[功能]：Agent开发最佳实践"（新增）
       - 适用场景：开发教程、技术分享、工具使用
       - 例："5分钟搭建RAG系统：LangChain实战指南"
       - 例："Prompt工程3大技巧：让Claude输出质量提升50%"

     * **工具推荐型**："这个开源工具让Agent开发效率提升10倍"（新增）
       - 适用场景：工具发布、框架更新、库推荐
       - 例："CrewAI vs AutoGPT：多Agent协作谁更强？"
       - 例："替代LangChain？这个新框架火了"

   - **标题优化原则**：
     * 包含具体数字（提升点击率30%）："3个技巧"、"提升50%效率"、"5分钟实现"
     * 触及用户关注点：效率、成本、职业、技能、**开发效率、代码质量**
     * 制造悬念或冲突："为什么..."、"真相是..."、"vs"、**"最佳实践"、"避坑指南"**
     * 长度控制在 18-25 字（移动端最佳显示）
     * 包含核心关键词（SEO优化）："ChatGPT"、"Claude"、"AI Agent"、**"Prompt工程"、"RAG"、"LangChain"**
     * 避免标题党，保持专业性（不夸大，有数据支撑）
     * **对于技术教程类，标题要体现"可操作性"和"实战性"**

   - **标题质量检查清单**：
     * [ ] 是否有具体数字或数据
     * [ ] 是否触及用户痛点或利益点
     * [ ] 是否制造悬念、冲突或好奇心
     * [ ] 长度是否在 18-25 字之间
     * [ ] 是否包含 1-2 个核心关键词
     * [ ] 是否避免了过度夸张

9. 为每个事件并行启动 ai-news-tech-analyst agent（共实际事件数量个并行任务）
   - **传递给每个 agent 的信息必须包含**：
     * 事件名称和描述
     * **事件的精确发布时间**（如：2025-10-13 08:30）
     * **信息来源**（新闻链接 / 两者）
     * 优化后的标题
     * 相关链接和资源

10. 每个 agent 需要针对该具体事件完成以下步骤（必须全部完成）：
   - **首先再次确认事件发布时间晚于 {cutoff_time_str}**
   - 深度搜索事件的详细信息：
     * 如果来源是新闻媒体：访问原始新闻和官方资料
     * 至少查找 3-5 个不同来源进行交叉验证
   - **如果是开源项目/工具**：
     * 访问 GitHub 仓库获取 README、文档、代码示例
     * 查看 Star 数、最近提交、社区活跃度
     * 寻找使用教程、最佳实践
   - **如果是Agent开发相关主题，额外搜索：GitHub仓库、技术文档、代码示例、最佳实践**
   - 下载事件相关的高质量图片（产品图、技术图表、**代码截图**、**架构图**等，使用 curl，不要截图）

   - **撰写文章时，必须优化推荐算法指标**：
     * **关键词密度优化（搜一搜流量）**：
       - 确保核心关键词在标题、首段、小标题中自然出现
       - 关键词密度控制在 1%-3%（全文出现 5-8 次）
       - 不要堆砌关键词，要自然融入叙事

     * **内容垂直度优化（建立账号标签）**：
       - 文章聚焦单一AI主题，不要跨领域发散
       - 使用AI领域专业术语（大模型、Transformer、Token、推理等）
       - 保持与公众号定位一致（AI技术分析）

     * **互动引导优化（提升推荐权重）**：
       - 文章结尾设计开放性问题（引导评论）
       - 提供"点赞/在看"的具体理由（如："如果这篇文章帮你了解了XX，点个在看让更多人知道"）
       - 设计分享动机（如："转发给做AI的朋友，这个发现值得关注"）

   - 撰写一篇深度分析的公众号文章（包含 frontmatter）
   - **保存文章为 .md 文件到 {self.working_dir}/articles/**
   - **文件名格式：YYYYMMDD_HHMM_topic_keywords.md**
     - 例如：20251002_1430_openai_gpt5_release.md
     - 例如：20251003_0900_anthropic_claude_code_update.md
     - 确保文件名包含日期、时间和核心主题关键词，方便搜索
   - **立即使用 mcp__wenyan-mcp__publish_article_from_file 发布到公众号草稿箱（不要等待批准，直接执行）**

文章要求：
- 标题聚焦具体事件，吸引眼球（使用步骤7生成的高打开率标题）
- 内容深度解析该事件的技术细节、行业意义、未来影响
- **对于Agent开发类文章，必须包含：实际应用场景、代码示例、最佳实践、避坑指南**
- **对于技术教程类文章，必须包含：步骤分解、关键参数说明、性能优化建议**
- **文章长度 1500-2000 字（最佳区间，兼顾完读率和底部广告曝光）**
- 至少包含 3-7 张配图（绝对路径），**技术类文章优先使用架构图、流程图、代码示例图**
- 使用 Markdown 格式，包含 frontmatter（title, cover）
- **主题只使用agentera系列**（agentera-orange, agentera-blue, agentera-cyan, agentera-rose, agentera-galaxy, agentera-mint）根据文章风格选择合适的配色

**CRITICAL - 发布是必需步骤**:
- 每个 agent 必须完成发布到草稿箱，确认收到 media_id 后任务才算完成
- 不要询问是否发布，直接执行发布操作
- 发布失败则压缩图片后重试

**CRITICAL - 发布后必须发送wenyan-mcp图片消息**:
- 文章发布成功后，立即使用 wenyan-mcp 发送图片消息到朋友圈
- **图片选择**：使用文章中的所有配图（文章里用了几张图就发几张，最多20张）
- **文案要求**：
  * 风格：简短有人感的评论（1-2句话）
  * 内容：自然的感想或评论，加上相关话题标签
  * 话题标签：3-5个相关话题（格式：#AI #ChatGPT #效率工具）
  * 示例："这个AI工具真的很实用，解决了不少实际问题。#AI工具 #ChatGPT #效率神器"
- **执行步骤**：
  1. 提取文章中所有配图的路径（从markdown文件中提取图片路径）
  2. 根据文章主题撰写简短评论文案（1-2句话+话题标签）
  3. 使用 mcp__wenyan-mcp__publish_image_message 发送图片消息（title为标题，content为文案，image_paths为图片路径数组）
  4. 确认发送成功
- **不要询问是否发送，直接执行**

11. **统计成功发布数量并循环补充（CRITICAL - 确保达到目标数量）**：
   - 等待所有 agent 完成后，统计成功发布的文章数量
   - **检查方法**：
     * 使用 Glob 工具检查 `{self.working_dir}/articles/*.md`
     * 统计本次任务新增的文章文件数量（通过文件名中的日期时间判断）
     * 或者统计收到的 media_id 数量

   - **如果成功发布数量 < {self.article_count} 篇**：
     * 计算缺口数量：`缺口 = {self.article_count} - 已成功发布数量`
     * 记录已失败的选题，避免重复尝试
     * ⚠️ **再次确认当前时间**：循环时可能已经过去几十分钟，需要重新计算24小时窗口
     * **立即返回步骤3**，重新搜索新的热门话题（排除已写过和已失败的选题）
     * **搜索时仍然使用 &tbs=qdr:d 参数，并严格验证发布时间**
     * 筛选出缺口数量的新选题
     * 启动新一轮 agent 并行写作和发布
     * 重复此循环，直到成功发布数量达到 {self.article_count} 篇

   - **循环保护**：
     * 最多循环 5 轮
     * 如果 5 轮后仍未达到目标，输出已成功发布的数量和失败原因总结

   - **成功标准**：
     * 只有当成功发布数量 = {self.article_count} 篇时，任务才算完成
     * 输出最终统计：成功 X 篇，失败 Y 篇，循环 Z 轮
     * **对每篇成功发布的文章，输出其发布时间验证记录**

---

📋 **时效性检查总结**（任务结束时必须输出）：
- 当前北京时间: {current_time_str}
- 24小时截止: {cutoff_time_str}
- 成功发布的文章列表：
  * 文章1标题 - 事件发布时间：YYYY-MM-DD HH:MM ✅
  * 文章2标题 - 事件发布时间：YYYY-MM-DD HH:MM ✅
  * ...

请开始执行，确保所有 agent 并行运行以提高效率。

⚠️ **最终提醒**：
- 时效性是第一优先级，宁可数量不足，不用旧新闻
- 必须使用 Google News 的 &tbs=qdr:d 参数过滤
- 每条新闻/推文必须有明确的发布时间验证
- 任务结束时必须输出时效性检查总结和信息来源统计"""

    def generate_prompt(self) -> str:
        """生成当天的 prompt（使用北京时间）"""
        today = get_beijing_time().strftime("%Y年%m月%d日")
        return f"今天是北京时间 {today}。\n\n{self.prompt_template}"

    def run_claude_code(self):
        """执行 Claude Code 命令（headless 模式）"""
        try:
            logger.info("="*60)
            logger.info(f"开始执行 AI 新闻自动化任务 - {get_beijing_time()}")
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
    automation = AINewsAutomation(article_count=article_count, verbose=verbose)
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
        automation = AINewsAutomation(article_count=article_count, verbose=verbose)
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
        description='AI 新闻自动化生成与发布系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 立即生成 1 篇文章
  python daily_ai_news.py --now --count 1

  # 立即生成 1 篇文章（实时显示执行过程）
  python daily_ai_news.py --now --count 1 --verbose

  # 立即生成 3 篇文章
  python daily_ai_news.py --now --count 3

  # 定时每天 08:00 生成 5 篇文章
  python daily_ai_news.py --count 5

  # 定时每天 14:00 生成 2 篇文章（实时输出）
  python daily_ai_news.py --time 14:00 --count 2 -v

  # 定时每天早上8点和晚上8点各生成 10 篇文章
  python daily_ai_news.py --time 08:00 20:00 --count 10

  # 定时多个时间点生成文章（早中晚）
  python daily_ai_news.py --time 08:00 12:00 20:00 --count 5
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
    logger.info("AI 新闻自动化系统")
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
