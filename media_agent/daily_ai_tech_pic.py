#!/usr/bin/env python3
"""
AI 技术图片消息自动化发布脚本
从最新文章中提取高质量图片，发布到微信公众号朋友圈
支持定时执行或立即执行
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
        logging.FileHandler(LOG_DIR / f'ai_tech_pic_{get_beijing_time().strftime("%Y%m")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class AITechPicAutomation:
    """AI 技术图片消息自动化处理类"""

    def __init__(self, working_dir: str = None, pic_count: int = 3, verbose: bool = False):
        self.working_dir = working_dir or str(Path(__file__).parent)
        self.pic_count = pic_count
        self.verbose = verbose
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """加载 prompt 模板"""
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
- ⚠️ 宁可图片消息数量不足 {self.pic_count} 条，也绝不使用旧新闻

请执行以下任务：

## 📋 任务概览

从最新 AI 新闻中发现热门话题，为每个话题创作图片消息并发布到微信公众号。

## 🔍 Step 1: 使用 WebFetch 搜索 Google News 发现热门 AI 话题

**⚠️ 搜索时必须使用时间过滤参数**：
- 完整URL格式：`https://www.google.com/search?q=[关键词]&tbm=nws&tbs=qdr:d`
- `&tbs=qdr:d` 参数表示过滤最近24小时的新闻

**并行搜索多个关键词**（建议至少6个）：
- "AI" 或 "artificial intelligence"
- "OpenAI" 或 "ChatGPT" 或 "GPT"
- "Anthropic" 或 "Claude"
- "AI agent" 或 "autonomous agent"
- "LangChain" 或 "CrewAI" 或 "agent framework"
- "machine learning" 或 "deep learning"
- 其他相关热词

**对每个关键词**：
1. 使用 WebFetch 访问 Google News（带 &tbs=qdr:d 参数），prompt 设置为："提取所有新闻标题、来源、发布时间和链接"
2. 提取新闻标题、来源、**精确发布时间**、链接
3. **立即验证发布时间**：只保留 {cutoff_time_str} 之后的新闻

## 🌐 Step 2: 访问权威科技媒体网站

**并行访问以下主流科技媒体**（选择2-3个）：
- TechCrunch AI: https://techcrunch.com/category/artificial-intelligence/
- The Verge AI: https://www.theverge.com/ai-artificial-intelligence
- VentureBeat AI: https://venturebeat.com/category/ai/
- MIT Technology Review AI: https://www.technologyreview.com/topic/artificial-intelligence/

**对每个网站**：
1. 使用 WebFetch 访问，prompt 设置为："提取首页最新文章的标题、发布时间和链接"
2. 提取首页最新文章的标题、**精确发布时间**、链接
3. **立即验证时间**：只保留 {cutoff_time_str} 之后的文章

## 🎯 Step 3: 筛选出最多 {self.pic_count} 个最适合做图片消息的话题

**评估标准（优先级排序）**：

1. **视觉潜力**（权重 40%，核心指标）：
   - 话题是否有丰富的配图（产品截图、架构图、数据图表）
   - 新闻原文是否包含高质量图片
   - 是否有视觉冲击力（产品发布、技术演示、对比图）

2. **话题热度**（权重 30%）：
   - 在多个渠道都有报道（Google News + 科技媒体）
   - 当前热门的 AI 话题（ChatGPT、Claude、Agent、开源工具）
   - 有讨论价值的争议性话题

3. **分享价值**（权重 30%）：
   - 读者会主动分享到朋友圈的内容
   - 有实用价值（工具推荐、效率提升、技术教程）
   - 引发共鸣（成功故事、技术突破、行业洞察）

**筛选规则**：
- ‼️ **第一优先级：时效性** - 所有选中事件发布时间必须晚于 {cutoff_time_str}
- 优先选择"高视觉潜力 + 高话题热度"的新闻
- 主题不重复（避免连续发布相似内容）
- **最终确认：输出选中话题的标题、发布时间、新闻链接、预估图片数量**

## 🚀 Step 4: 为每个选中的话题并行启动 ai-tech-editor agent

为每个话题并行启动一个 ai-tech-editor agent（共实际话题数量个并行任务）

**传递给每个 agent 的详细信息**：
```
任务：为以下 AI 新闻话题创作图片消息并发布

话题标题：[新闻标题]
发布时间：[精确发布时间，如：2025-11-04 14:30]
新闻链接：[原文URL]
话题主题：[核心关键词]

请按照以下步骤执行：

1. **访问新闻原文，获取图片资源**：
   - 使用 WebFetch 访问新闻链接，提取图片 URL
   - 优先寻找：产品截图、技术演示图、架构图、数据可视化
   - 找到至少 3-5 个高质量图片 URL

2. **下载原始图片**（使用 curl，不要截图）：
   ```bash
   curl -o "/home/floodsung/media_agents/media_agent/images/descriptive-name.png" "图片URL"
   ```
   - 使用描述性文件名
   - 保存到 /home/floodsung/media_agents/media_agent/images/ 目录
   - 下载至少 3 张图片

3. **验证每张图片**（CRITICAL）：
   - 使用 Read 工具查看每张下载的图片
   - 确认图片清晰、相关、有视觉冲击力
   - 丢弃：模糊、广告、页面截图、纯文字图
   - 最终筛选出 3-8 张最优质的图片

4. **压缩大图片**（如果需要）：
   ```bash
   sips -Z 1200 original.png --out compressed.png
   ```

5. **撰写简短口语化文案**（1-2句话）：
   - 风格：像朋友圈评论，自然真实
   - 类型：推荐型、感叹型、疑问型、期待型（选一种）
   - 示例：
     * "这个 AI 工具真的很实用，解决了不少实际问题。"
     * "没想到这个功能这么强大。"
     * "你们试过这个工具吗？"
     * "期待这个项目的后续发展。"
   - ❌ 避免：书面语、营销腔、夸张表述

6. **生成 3-5 个话题标签**：
   - 核心主题标签（1-2个）：#AI #ChatGPT #Claude #机器学习 #大模型
   - 细分领域标签（1-2个）：#Prompt工程 #RAG #LangChain #Agent框架
   - 情感/行动标签（1个）：#效率神器 #推荐 #技术洞察 #值得一试
   - 格式：标签之间用空格分隔

7. **使用 mcp__wenyan-mcp__publish_image_message 发布**：
   - title: 从新闻标题提取或自拟（10-20字）
   - content: [文案（1-2句话）] + \\n\\n + [话题标签，空格分隔]
   - image_paths: [筛选后的 3-8 张图片绝对路径数组]
   - need_open_comment: true
   - only_fans_can_comment: false

8. **确认发布成功，输出报告**：
   - media_id
   - 图片数量和来源
   - 使用的文案和标签
   - 图片筛选理由

**CRITICAL - 直接执行，不要询问**：
- 完成所有步骤后，直接调用发布工具
- 不需要等待用户确认
- 发布失败则输出错误信息并尝试压缩图片重试
```

## 📊 Step 5: 统计发布结果

等待所有 agents 完成后，统计并输出：

**统计信息**：
```
📊 图片消息发布统计
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ 当前时间：{current_time_str}
📅 24小时窗口：{cutoff_time_str} 至今

✅ 成功发布：X / {self.pic_count} 条
📸 总图片数：X 张
🏷️ 使用标签：[标签汇总]

详细列表：
1. [话题标题] - 发布时间：YYYY-MM-DD HH:MM ✅
   - 图片：X 张
   - 文案：[实际文案]
   - 标签：[实际标签]
   - media_id: xxx

2. [话题标题] - 发布时间：YYYY-MM-DD HH:MM ✅
   - 图片：X 张
   - 文案：[实际文案]
   - 标签：[实际标签]
   - media_id: xxx

...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 🎯 成功标准

任务完成需要满足：
- ✅ 成功发布图片消息（目标 {self.pic_count} 条，实际尽可能多）
- ✅ 所有话题的发布时间晚于 {cutoff_time_str}
- ✅ 每条消息包含 3-8 张验证过的高质量图片
- ✅ 每条消息有简短自然的文案（1-2句话）
- ✅ 每条消息有 3-5 个相关话题标签
- ✅ 所有消息都获得 media_id 确认

## ⚠️ 重要提醒

1. **时效性是第一优先级**：
   - 宁可数量不足，不用旧新闻
   - 必须使用 &tbs=qdr:d 参数过滤
   - 每条新闻必须有明确的发布时间验证

2. **图片下载和验证是必须的**：
   - 使用 curl 下载原始图片（不要截图）
   - 每张图片都要用 Read 工具查看验证
   - 质量优先于数量

3. **文案保持简短自然**：
   - 1-2 句话，像朋友圈评论
   - 口语化，避免书面语和营销腔

4. **标签要精准热门**：
   - 3-5 个标签，与话题高度相关
   - 优先使用热门标签（#AI #ChatGPT）

5. **并行执行提高效率**：
   - 多个 agents 同时运行
   - 节省时间，快速发布

6. **错误处理**：
   - 如果某个话题找不到高质量图片，跳过
   - 如果发布失败，记录原因
   - 不强求完成所有任务，质量优先

---

请开始执行，确保所有 agents 并行运行以提高效率。

⚠️ **最终提醒**：
- 时效性是第一优先级，宁可数量不足，不用旧新闻
- 图片必须从新闻原文下载，不要使用截图
- 每张图片必须用 Read 工具验证
- 任务结束时必须输出时效性检查总结"""

    def generate_prompt(self) -> str:
        """生成当天的 prompt（使用北京时间）"""
        today = get_beijing_time().strftime("%Y年%m月%d日")
        return f"今天是北京时间 {today}。\n\n{self.prompt_template}"

    def run_claude_code(self):
        """执行 Claude Code 命令（headless 模式）"""
        try:
            logger.info("="*60)
            logger.info(f"开始执行 AI 技术图片消息自动化任务 - {get_beijing_time()}")
            logger.info(f"图片消息数量: {self.pic_count} 条")
            logger.info("="*60)

            prompt = self.generate_prompt()

            logger.info(f"工作目录: {self.working_dir}")
            logger.info(f"使用 headless 模式{' [实时输出]' if self.verbose else ''}")

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
                '--permission-mode', 'bypassPermissions',  # 绕过所有权限检查
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
                    timeout=3600  # 1小时超时（包括搜索、下载图片等）
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


def run_now(pic_count: int, verbose: bool = False):
    """立即执行任务"""
    logger.info("🚀 立即执行模式")
    automation = AITechPicAutomation(pic_count=pic_count, verbose=verbose)
    success = automation.run_claude_code()
    return 0 if success else 1


def beijing_to_utc(beijing_time_str: str) -> str:
    """将北京时间 HH:MM 转换为 UTC 时间 HH:MM"""
    hour, minute = map(int, beijing_time_str.split(':'))
    # 北京时间是 UTC+8，所以减去8小时
    utc_hour = (hour - 8) % 24
    return f"{utc_hour:02d}:{minute:02d}"


def run_scheduled(pic_count: int, schedule_times: list = None, verbose: bool = False):
    """定时执行任务（支持多个时间点）- 使用北京时间"""
    import schedule
    import time
    from datetime import datetime, timedelta

    if schedule_times is None:
        schedule_times = ["12:00"]  # 默认中午发布

    logger.info("⏰ 定时执行模式（北京时间）")
    logger.info(f"调度时间: 每天 {', '.join(schedule_times)} 北京时间")
    logger.info(f"图片消息数量: {pic_count} 条")
    logger.info(f"实时输出: {'开启' if verbose else '关闭'}")

    beijing_now = get_beijing_time()
    logger.info(f"当前北京时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"系统UTC时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def job():
        logger.info(f"🚀 定时任务触发 - 北京时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
        automation = AITechPicAutomation(pic_count=pic_count, verbose=verbose)
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
        description='AI 技术图片消息自动化发布系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 立即发布 1 条图片消息
  python daily_ai_tech_pic.py --now --count 1

  # 立即发布 1 条图片消息（实时显示执行过程）
  python daily_ai_tech_pic.py --now --count 1 --verbose

  # 立即发布 3 条图片消息
  python daily_ai_tech_pic.py --now --count 3

  # 定时每天 12:00 发布 3 条图片消息
  python daily_ai_tech_pic.py --count 3

  # 定时每天 18:00 发布 5 条图片消息（实时输出）
  python daily_ai_tech_pic.py --time 18:00 --count 5 -v

  # 定时每天中午和晚上各发布 3 条图片消息
  python daily_ai_tech_pic.py --time 12:00 20:00 --count 3

  # 定时多个时间点发布图片消息（早中晚）
  python daily_ai_tech_pic.py --time 09:00 14:00 21:00 --count 2
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
        help='发布图片消息数量（默认: 3）'
    )

    parser.add_argument(
        '--time',
        type=str,
        nargs='+',
        default=['12:00'],
        help='定时执行时间，格式 HH:MM，支持多个时间点用空格分隔（默认: 12:00）'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='实时显示 Claude 执行过程（实时输出模式）'
    )

    args = parser.parse_args()

    # 显示配置
    logger.info("="*60)
    logger.info("AI 技术图片消息自动化系统")
    logger.info("="*60)
    logger.info(f"图片消息数量: {args.count} 条")
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
