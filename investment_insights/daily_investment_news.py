#!/usr/bin/env python3
"""
投资资讯自动化生成与发布脚本
支持定时执行或立即执行，可自定义文章数量
主题：股票市场、投资策略、财经分析、财富管理
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
        logging.FileHandler(LOG_DIR / f'investment_news_{get_beijing_time().strftime("%Y%m")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class InvestmentNewsAutomation:
    """投资资讯自动化处理类"""

    def __init__(self, working_dir: str = None, article_count: int = 5, verbose: bool = False):
        self.working_dir = working_dir or str(Path(__file__).parent)
        self.article_count = article_count
        self.verbose = verbose
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """加载 prompt 模板"""
        return f"""请执行以下任务：

1. **首先使用 Bash 执行 `TZ='Asia/Shanghai' date` 命令获取北京时间**
   - 记录当前日期和时间（北京时间）
   - 用于确定"过去24小时"的准确时间范围
   - 注意美股、港股、A股的交易时间和时区

2. **检查已存在的文章，避免重复选题**
   - 使用 Glob 工具检查 `{self.working_dir}/articles/*.md`
   - 从文件名中识别已覆盖的主题
   - 记录所有已存在的选题关键词
   - **在后续选题时必须避开这些已写过的主题**

3. **使用 WebFetch 搜索 Google News 发现热门投资话题（必须附带时间过滤）**
   - ⚠️ **搜索时必须使用时间过滤参数**：在URL中添加 `&tbs=qdr:d` 参数（过去24小时）
   - 完整URL格式：`https://www.google.com/search?q=[关键词]&tbm=nws&tbs=qdr:d`
   - 并行搜索多个关键词组合（建议至少10个不同关键词）：
     * **财报季重点（高优先级）**：
       - "earnings report 2025", "Q4 2024 earnings", "Q1 2025 earnings"
       - "Apple earnings", "Microsoft earnings", "Nvidia earnings", "Tesla earnings"
       - "Amazon earnings", "Google earnings", "Meta earnings"
       - "阿里巴巴财报", "腾讯财报", "拼多多财报", "美团财报"
       - "earnings beat", "earnings miss", "revenue guidance"
       - "quarterly results", "fiscal year earnings"
     * 美股市场："US stock market", "S&P 500", "Nasdaq", "Dow Jones"
     * 科技股："tech stocks", "FAANG", "AI chips", "cloud computing"
     * 中概股："Chinese stocks", "BABA", "BIDU", "ADR", "China tech"
     * 经济数据："Federal Reserve", "interest rates", "inflation", "CPI", "GDP"
     * 行业趋势："AI stocks", "EV sector", "semiconductor", "biotech"
     * 市场事件："IPO", "M&A", "stock split", "dividend"

   - 对每个关键词：
     * 使用 WebFetch 访问：https://www.google.com/search?q=[关键词]&tbm=nws&tbs=qdr:d
       - `tbm=nws` 表示新闻搜索
       - `tbs=qdr:d` 表示只显示过去24小时的新闻（自动过滤旧新闻）
     * prompt 设置为："提取所有新闻标题、来源、发布时间和链接"
     * 提取新闻标题、来源、发布时间、关键数据
     * 记录所有找到的重要资讯
     * 优先选择有具体数据和分析价值的内容

   - 从所有搜索结果中识别出现频率最高的市场热点
   - 优先选择多个来源都在报道的重大市场事件

4. **补充使用 WebSearch 深挖细节**
   - 针对在 Google News 中发现的热门话题
   - 使用 WebSearch 查找更多技术细节和官方信息
   - **确认新闻发布时间确实在过去24小时内**

5. **访问权威财经媒体和公司官网获取财报原文及深度分析**
   - **优先访问公司投资者关系页面（高优先级）**：
     * 使用 WebSearch 搜索 "[公司名] investor relations earnings"
     * 访问公司官网 IR 页面获取最新财报 PDF、earnings call transcript
     * 例如：Apple IR, Microsoft IR, Tesla IR, Nvidia IR, Amazon IR
     * 中概股：阿里巴巴 IR, 腾讯 IR, 拼多多 IR, 美团 IR
     * 提取关键财务数据：营收、净利润、毛利率、EPS、guidance

   - **访问权威财经媒体获取分析**：
     * Bloomberg: 市场分析、财报解读、投资策略
     * Wall Street Journal: 深度调查、行业趋势
     * Financial Times: 全球市场、经济政策
     * Reuters: 实时财报新闻、数据分析
     * CNBC: 市场动态、财报直播、专家观点
     * Seeking Alpha: 投资策略、个股财报分析
     * Yahoo Finance: 市场数据、财报追踪、估值指标
     * 中文财经媒体：财新、第一财经、华尔街见闻、雪球

   - **对找到的财报和分析**：
     * 提取核心财务指标：营收、利润、增长率、margins
     * 记录分析师观点、市场预期 vs 实际表现
     * 重点关注：财报超预期/不及预期、guidance变化、关键业务指标
     * 对比同行业竞品的财报表现

   - 交叉验证：
     * 找出在多个权威媒体都有报道的热点话题（优先级最高）
     * 记录独家深度分析（投资价值高）
     * 整合市场数据和专业观点

6. **严格验证新闻时间，只保留过去24小时内的资讯**：
   - 对每条搜索结果，仔细检查其发布时间
   - 计算发布时间与当前时间（步骤1获取的时间）的时间差
   - **如果新闻发布时间早于24小时前，立即丢弃**
   - **如果找不到明确发布时间，也必须丢弃**
   - **特别注意：美股盘后、亚洲盘前的新闻时效性**
   - 宁可文章数量不足 {self.article_count} 篇，也绝不使用旧新闻

7. **适度去重检查 - 避免完全重复的文章**
   - 对于每个候选主题，执行以下去重验证：
     * 提取主题核心关键词（公司名、财报季度、产品名等）
     * 使用 Glob 工具检查已有文章文件名：
       - 检查 `{self.working_dir}/articles/*.md` 的文件名
       - 从文件名中识别已覆盖的主题关键词
     * 只排除**明确重复**的主题（相同公司+相同季度+相同事件）
     * 不需要使用 Grep 搜索文件内容

   - **去重判断标准（放宽标准，减少过度去重）**：
     * ✅ 允许：同一公司的不同季度财报（例如：已写过 Q2 财报，现在发布 Q3 财报）
     * ✅ 允许：同一板块的不同公司（例如：已写过英伟达，现在要写 AMD）
     * ✅ 允许：同一公司的不同角度分析（例如：已写过财报数据，现在写业务展望）
     * ✅ 允许：同一主题的新进展（例如：已写过某公司新闻，现在有新的重要更新）
     * ❌ 仅禁止：完全相同的主题（相同公司+相同季度+相同事件类型）

8. 从去重后的候选主题中筛选出**实际可写的主题**（数量 ≤ {self.article_count}）：
   - ⚠️ **不强求写满 {self.article_count} 篇**
   - ⚠️ **宁缺毋滥：如果去重后只剩2个主题，就只写2篇**
   - 每个资讯应该是独立、明确的投资主题（如：英伟达Q3财报超预期，股价大涨15%）

   - **评估标准（按优先级排序，权重总计100%）**：
     * 📊 **市场影响力**（权重 25%，最高优先级）：
       - 影响大盘走势的重大事件（美联储决议、重要财报等）
       - **知名公司财报发布**（Apple、Tesla、Nvidia、阿里等）
       - 财报超预期/不及预期对股价的显著影响
     * 📈 **数据完整性**（权重 20%）：
       - 有详实的财务数据（营收、利润、EPS、guidance）
       - 财报原文数据、同比/环比增长率
       - 估值分析、关键业务指标（如云计算收入、用户数等）
     * 💰 **分析价值**（权重 20%）：
       - 有明确的投资逻辑和市场分析
       - 多角度观点（看多因素 + 风险因素）
       - **财报解读深度**（不仅是数据，还有业务趋势分析）
     * 🔥 **市场热度**（权重 15%）：
       - 多家权威媒体报道的热点话题
       - 财报季高关注度公司
     * 👥 **用户共鸣度**（权重 15%）：
       - 话题是否触及投资者关注点（收益机会、风险、配置）
       - 是否有争议性/对比性（容易引发讨论）
       - **财报分析是否通俗易懂**（专业但不晦涩）
     * 📖 **完读率潜力**（权重 5%）：
       - 故事性：财报背后的业务故事、管理层展望
       - 实用性：读者能获得市场洞察和数据理解
       - 视觉潜力：财报图表、数据可视化

   - **筛选规则**：
     * 必须排除步骤2中已识别的选题，确保选题不重复
     * **优先选择知名公司财报**（Apple、Microsoft、Nvidia、Tesla、Amazon、Google、Meta、阿里、腾讯、拼多多、美团等）
     * 优先选择"财报超预期/不及预期 + 股价大幅波动"的话题
     * "独家财报深度解读 + 高数据价值"的话题优先入选
     * 避免"纯数据播报但缺乏分析"的话题（完读率低）
     * 再次人工确认：所有选中内容的发布日期必须在当前日期或前一天
     * 如果24小时内的资讯不足 {self.article_count} 个，只生成实际找到的数量
     * **财报季期间（1月、4月、7月、10月）优先选择财报主题**

9. **为每个选中的资讯生成"高打开率标题"**（在交给 agent 之前）：

   - **标题公式（选择最适合该资讯的一种）**：
     * **财报数据型（财报主题优先使用）**："[公司]Q[季度]财报：营收[增长率]，[关键指标]如何？"
       - 适用场景：财报发布、业绩数据
       - 例："英伟达Q3财报：营收同比增206%，数据中心业务表现如何？"
       - 例："特斯拉Q4交付量超预期，毛利率变化透露什么信号？"
       - 例："阿里巴巴财报解读：云计算首次盈利，电商业务何去何从？"

     * **财报对比型（财报季高频使用）**："[公司A] vs [公司B]：财报数据谁更强？"
       - 适用场景：竞品财报对比
       - 例："苹果vs微软：Q3财报对比，谁的增长更稳健？"
       - 例："阿里vs拼多多：电商财报对决，谁的盈利能力更强？"

     * **悬念型**："[公司]财报发布后股价大跌，市场担忧什么？"
       - 适用场景：财报不及预期、政策变化
       - 例："特斯拉财报后股价跌15%，自动驾驶进展不及预期？"
       - 例："美联储暂停加息，市场为何未能反弹？"

     * **对比型**："[概念A] vs [概念B]：市场观点如何？"
       - 适用场景：竞品分析、板块轮动
       - 例："茅台 vs 五粮液：谁的估值更合理？"
       - 例："成长股vs价值股：数据显示市场偏好哪类？"

     * **数据解读型**："[公司]关键数据变化：[指标]同比[变化]意味着什么？"
       - 适用场景：财报深度分析
       - 例："微软云计算收入占比达45%，业务结构转型进展如何？"
       - 例："特斯拉毛利率降至18%，成本控制面临挑战？"

     * **市场观察型**："[板块/行业]观察：数据显示[趋势]"
       - 适用场景：行业趋势、资金流向
       - 例："AI芯片板块观察：机构资金流向分析"
       - 例："港股科技股走势：市场情绪如何变化？"

   - **标题优化原则**：
     * **财报类标题必须包含**：公司名、季度、核心数据（营收/利润/增长率）
     * 包含具体数字但避免夸张："同比增206%"、"营收达180亿美元"（客观数据）
     * 触及投资者关注点：财报数据、业务表现、估值分析、市场观点
     * 使用疑问句引导思考："表现如何？"、"意味着什么？"、"市场观点如何？"（避免断言）
     * 长度控制在 18-28 字（财报标题可适当放宽到28字）
     * 包含核心关键词（SEO优化）：公司名、"财报"、"Q3"、"营收"、"数据"
     * **保持客观中性**（不用"暴涨"、"狂买"等煽动性词汇，用"增长"、"上涨"）

   - **标题质量检查清单**：
     * [ ] 是否有具体数字或数据
     * [ ] 是否触及投资者痛点或利益点
     * [ ] 是否制造悬念、冲突或好奇心
     * [ ] 长度是否在 18-25 字之间
     * [ ] 是否包含 1-2 个核心关键词
     * [ ] 是否避免了过度夸张

10. **总结去重结果并决定文章数量**：
   - 明确说明：找到 X 个候选主题，经过去重后剩余 Y 个可写主题
   - 如果 Y < {self.article_count}，说明："本次只写 Y 篇文章（去重后的实际数量）"
   - 如果 Y = 0，说明："没有找到新主题，本次不生成文章"并结束任务

11. 为每个通过去重的主题并行启动 investor-editor agent（共 Y 个并行任务）

12. 每个 agent 需要针对该具体资讯完成以下步骤（必须全部完成）：
   - **深度搜索资讯的详细信息**（至少3-5个权威来源）：
     * **优先访问公司投资者关系页面**（获取财报原文PDF、earnings call transcript）
     * 访问财经媒体获取分析报告（Bloomberg、WSJ、Reuters、CNBC、Seeking Alpha）
     * 提取关键财务数据：营收、净利润、EPS、毛利率、现金流、guidance
     * 记录分析师观点、市场预期 vs 实际表现
     * 对比历史数据（YoY、QoQ增长率）
     * **对于财报主题，必须包含**：
       - 核心财务指标（营收、利润、EPS等）
       - 关键业务指标（用户数、云收入、交付量等）
       - 管理层guidance和展望
       - 同行业竞品对比数据
   - 下载相关的高质量图片（财报图表、业务数据图、股价走势图等，使用 curl，不要截图，3-5张）

   - **撰写文章时，必须优化推荐算法指标**：
     * **关键词密度优化（搜一搜流量）**：
       - 确保核心关键词在标题、首段、小标题中自然出现
       - 关键词密度控制在 1%-3%（全文出现 5-8 次）
       - 不要堆砌关键词，要自然融入叙事

     * **内容垂直度优化（建立账号标签）**：
       - 文章聚焦单一投资主题，不要跨领域发散
       - 使用投资领域专业术语（市盈率、ROE、估值、K线等）
       - 保持与公众号定位一致（投资分析）

     * **互动引导优化（提升推荐权重）**：
       - 文章结尾设计开放性问题（引导评论）
       - 提供"点赞/在看"的具体理由（如："如果这篇分析对你有帮助，点个在看让更多投资者看到"）
       - 设计分享动机（如："转发给投资的朋友，这个机会值得关注"）

   - 撰写一篇专业深度的投资分析文章（包含 frontmatter）
   - **保存文章为 .md 文件到 {self.working_dir}/articles/**
   - **文件名格式：YYYYMMDD_HHMM_topic_keywords.md**
     - 例如：20251005_1530_nvidia_earnings_analysis.md
     - 例如：20251005_0900_fed_rate_decision.md
     - 确保文件名包含日期、时间和核心主题关键词，方便搜索
   - **立即使用 mcp__wenyan-mcp__publish_article_from_file 发布到公众号草稿箱（不要等待批准，直接执行）**

文章要求：
- 标题聚焦具体投资主题，专业吸引（如：「英伟达Q3营收暴涨206%，AI芯片龙头估值几何？」）
- 内容专业、有深度，包含详实的市场数据和客观分析
- **文章长度严格控制在 1200-1500 字**（合规考量，避免过度冗长）
- 至少包含 3-5 张配图（市场图表、数据对比、公司信息等，绝对路径）
- 使用 Markdown 格式，包含 frontmatter（title, cover）
- **主题只使用agentera系列**（agentera, agentera-orange, agentera-blue, agentera-cyan, agentera-rose, agentera-galaxy, agentera-mint）根据文章风格选择合适的配色
- **必须包含投资风险提示及免责声明**

**合规要求（CRITICAL - 必须遵守）**：
- ❌ **禁止提供具体操作建议**：不得出现"建议买入"、"推荐持有"、"现在抄底"等明确投资指令
- ❌ **禁止预测具体涨跌幅**：不得出现"预计上涨30%"、"目标价XX元"等具体预测
- ❌ **禁止承诺收益**：不得出现"稳赚"、"必涨"、"保证收益"等保证性表述
- ✅ **采用客观分析语气**：使用"市场观点认为"、"数据显示"、"分析师指出"等客观表述
- ✅ **提供多角度观点**：同时呈现看多和看空的观点，保持中立
- ✅ **强调风险**：在文章结尾必须包含风险提示和免责声明

**CRITICAL - 发布是必需步骤**:
- 每个 agent 必须完成发布到草稿箱，确认收到 media_id 后任务才算完成
- 不要询问是否发布，直接执行发布操作
- 发布失败则压缩图片后重试

**CRITICAL - 发布后必须发送wenyan-mcp图片消息**:
- 文章发布成功后，立即使用 wenyan-mcp 发送图片消息到朋友圈
- **图片选择**：使用文章中的所有配图（文章里用了几张图就发几张，最多20张）
- **文案要求**：
  * 风格：简短有人感的评论（1-2句话）
  * 内容：自然的投资观察或数据评论，加上相关话题标签
  * 话题标签：3-5个相关话题（格式：#投资分析 #财报解读 #股市）
  * 示例："英伟达Q3财报数据挺亮眼的，AI芯片业务增长迅速。#英伟达财报 #AI芯片 #投资分析"
- **执行步骤**：
  1. 提取文章中所有配图的路径（从markdown文件中提取图片路径）
  2. 根据文章主题撰写简短评论文案（1-2句话+话题标签）
  3. 使用 mcp__wenyan-mcp__publish_image_message 发送图片消息（title为标题，content为文案，image_paths为图片路径数组）
  4. 确认发送成功
- **不要询问是否发送，直接执行**

13. **统计成功发布数量并循环补充（CRITICAL - 确保达到目标数量）**：
   - 等待所有 agent 完成后，统计成功发布的文章数量
   - **检查方法**：
     * 使用 Glob 工具检查 `{self.working_dir}/articles/*.md`
     * 统计本次任务新增的文章文件数量（通过文件名中的日期时间判断）
     * 或者统计收到的 media_id 数量

   - **最低要求：至少发布 {self.article_count // 2} 篇文章（目标数量的一半）**

   - **如果成功发布数量 < {self.article_count // 2} 篇**：
     * 计算缺口数量：`缺口 = {self.article_count // 2} - 已成功发布数量`
     * 记录已失败的选题，避免重复尝试
     * **立即返回步骤3**，重新搜索新的热门资讯（排除已写过和已失败的选题）
     * 筛选出缺口数量的新选题
     * 启动新一轮 agent 并行写作和发布
     * 重复此循环，直到成功发布数量达到至少 {self.article_count // 2} 篇

   - **如果成功发布数量 >= {self.article_count // 2} 篇但 < {self.article_count} 篇**：
     * 任务视为基本成功，可以选择继续补充或结束
     * 建议：尝试补充 1-2 轮，如果仍不够则接受当前结果

   - **循环保护**：
     * 最多循环 5 轮
     * 如果 5 轮后仍未达到最低要求（一半数量），输出已成功发布的数量和失败原因总结

   - **成功标准**：
     * 完美成功：成功发布数量 = {self.article_count} 篇
     * 基本成功：成功发布数量 >= {self.article_count // 2} 篇
     * 输出最终统计：成功 X 篇（目标 {self.article_count} 篇，最低 {self.article_count // 2} 篇），失败 Y 篇，循环 Z 轮

请开始执行，确保所有 agent 并行运行以提高效率。记住：必须达到 {self.article_count} 篇成功发布才能结束！"""

    def generate_prompt(self) -> str:
        """生成当天的 prompt（使用北京时间）"""
        today = get_beijing_time().strftime("%Y年%m月%d日")
        return f"今天是北京时间 {today}。\n\n{self.prompt_template}"

    def run_claude_code(self):
        """执行 Claude Code 命令（headless 模式）"""
        try:
            logger.info("="*60)
            logger.info(f"开始执行投资资讯自动化任务 - {get_beijing_time()}")
            logger.info(f"文章数量: {self.article_count} 篇")
            logger.info("="*60)

            prompt = self.generate_prompt()

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
    automation = InvestmentNewsAutomation(article_count=article_count, verbose=verbose)
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
        schedule_times = ["08:00"]

    logger.info("⏰ 定时执行模式（北京时间）")
    logger.info(f"调度时间: 每天 {', '.join(schedule_times)} 北京时间")
    logger.info(f"文章数量: {article_count} 篇")
    logger.info(f"实时输出: {'开启' if verbose else '关闭'}")

    beijing_now = get_beijing_time()
    utc_now = datetime.utcnow()
    logger.info(f"当前北京时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"当前UTC时间: {utc_now.strftime('%Y-%m-%d %H:%M:%S')}")

    def job():
        logger.info(f"🚀 定时任务触发 - 北京时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
        automation = InvestmentNewsAutomation(article_count=article_count, verbose=verbose)
        automation.run_claude_code()

    # 系统在 UTC 时区，需要将北京时间转换为 UTC 时间
    for beijing_time_str in schedule_times:
        utc_time_str = beijing_to_utc(beijing_time_str)
        schedule.every().day.at(utc_time_str).do(job)
        logger.info(f"✅ 已设置定时任务: 每天 {beijing_time_str} 北京时间 (UTC {utc_time_str})")

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
        description='投资资讯自动化生成与发布系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 立即生成 1 篇文章
  python daily_investment_news.py --now --count 1

  # 立即生成 1 篇文章（实时显示执行过程）
  python daily_investment_news.py --now --count 1 --verbose

  # 立即生成 3 篇文章
  python daily_investment_news.py --now --count 3

  # 定时每天 08:00 生成 5 篇文章
  python daily_investment_news.py --count 5

  # 定时每天 14:00 生成 2 篇文章（实时输出）
  python daily_investment_news.py --time 14:00 --count 2 -v

  # 定时每天早上8点和晚上8点各生成 10 篇文章
  python daily_investment_news.py --time 08:00 20:00 --count 10

  # 定时多个时间点生成文章（早中晚）
  python daily_investment_news.py --time 08:00 12:00 20:00 --count 5
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
    logger.info("投资资讯自动化系统")
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
