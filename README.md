# 公众号多智能体系统 / WeChat Official Account Multi-Agent System

[中文](#中文) | [English](#english)

---

## 中文

### 项目简介

这是一个基于 Claude AI 的全自动微信公众号内容生产系统，采用**主编-编辑（Manager-Editor）多智能体协作架构**。

每个公众号都拥有独立的 Agent Manager（主编智能体，即 Claude Code 主进程）和多个 Sub Agent Editor（编辑智能体）。主编负责搜索热点、筛选选题，然后将任务分派给编辑智能体完成撰写和发布。8 个公众号并行运行，各自独立，互不干扰。

### 多智能体架构

```
┌─────────────────────────────────────────────────────────────┐
│                Python 调度层 (daily_*.py x 8)                │
│           每个公众号一个独立脚本，定时/手动触发                  │
└──┬──────────┬──────────┬──────────┬──────────┬──────────┬───┘
   │          │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼          ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│AI科技│ │论文  │ │投资  │ │数码  │ │游民  │ │时尚  │  ... x8
│公众号│ │公众号│ │公众号│ │公众号│ │公众号│ │公众号│
└──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘
   │        │        │        │        │        │
   ▼        ▼        ▼        ▼        ▼        ▼
   每个公众号内部结构相同（以 AI 科技公众号为例）：
```

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  🤖 Agent Manager — Claude Code 主进程（主编）               │
│                                                             │
│  1. 搜索热点: WebSearch / Playwright 抓取 24h 内资讯          │
│  2. 筛选选题: 过滤低质量话题，检查已发文章去重                  │
│  3. 分派任务: 将选题交给 Sub Agent Editor 执行                │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                                                       │  │
│  │  ✍️  Sub Agent Editor（编辑智能体）                     │  │
│  │      定义在 .claude/agents/*.md                        │  │
│  │                                                       │  │
│  │  • 深度研究: WebFetch 提取多源内容                      │  │
│  │  • 图片采集: curl 下载 + Read 验证                      │  │
│  │  • 撰写文章: 按领域专属风格写 Markdown                  │  │
│  │  • (可选) Reviewer Agent 多轮质量迭代                   │  │
│  │  • 发布: wenyan-mcp → 公众号草稿箱                      │  │
│  │                                                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
                ┌───────────────────┐
                │  微信公众号草稿箱   │
                │  人工审核后发布     │
                └───────────────────┘
```

### 智能体协作模式

每个公众号内部采用 Manager-Editor 两层协作：

```
daily_*.py (Python 调度)
    │
    └── Agent Manager (Claude Code 主进程)    ← 搜索热点、筛选选题、分派任务
            │
            ├── Sub Agent: Writer (写手)      ← 研究 + 撰写文章
            │       │
            │       └── Sub Agent: Reviewer   ← 质量审核、反 AI 检测（部分领域）
            │
            └── Sub Agent: Editor (编辑)      ← 图片筛选、排版、发布到公众号
```

- **Agent Manager（主编）**: Claude Code 主进程。接收 Python 脚本的动态 Prompt 后，用 WebSearch/Playwright 搜索当日热点，筛选有价值的选题，检查已有文章避免重复，然后调用 Sub Agent 执行具体写作和发布。
- **Writer Agent（写手）**: 定义在 `.claude/agents/*.md` 中的专业写作智能体。每个公众号有独立的写作风格、术语库和反 AI 检测规则。
- **Reviewer Agent（审核）**: 部分公众号（如 `intelligent_unit`）配备独立审核智能体，与写手进行 2-3 轮迭代优化。
- **Editor Agent（编辑）**: 负责图片筛选、排版和通过 `wenyan-mcp` 发布到微信公众号草稿箱。

> 关键设计: 8 个公众号各自拥有独立的 Agent Manager 和 Sub Agent，互不干扰，可并行运行。每个公众号的智能体配置（`.claude/agents/`）和 MCP 凭证（`.mcp.json`）完全独立。

### 垂直领域

| 目录 | 领域 | 公众号定位 | 核心脚本 |
|------|------|-----------|---------|
| `media_agent/` | AI 科技资讯 | AI 前沿动态、模型发布、行业趋势 | `daily_ai_news.py` |
| `intelligent_unit/` | arXiv 论文解读 | LLM、Agent、强化学习论文深度分析 | `daily_arxiv_papers.py` |
| `investment_insights/` | 投资洞察 | 美股财报、市场分析、经济指标 | `daily_investment_news.py` |
| `digital_tech/` | 数码科技 | 数码产品评测、新品发布 | `daily_digital_tech_news.py` |
| `digital_nomad/` | 数字游民 | 签证政策、远程办公、目的地推荐 | `daily_nomad_news.py` |
| `fuson/` | 时尚针织 | 设计师系列、秀场分析、面料工艺 | `daily_fashion.py` |
| `aml_compliance/` | 反洗钱合规 | OFAC/FATF 监管动态（中英双语） | `daily_aml_news.py` |
| `military_frontier/` | 军事前沿 | 武器系统、国防科技、战略分析 | `daily_military_frontier.py` |

### 技术栈

- **调度层**: Python + `schedule` 库
- **AI 引擎**: Claude Code（通过 `subprocess` 无头调用）
- **MCP 工具**:
  - `wenyan-mcp` — 微信公众号文章发布
  - `playwright-mcp` — 浏览器自动化（Google News 抓取）
  - `arxiv-mcp` — arXiv 论文检索
- **智能体配置**: `.claude/agents/*.md`（每个领域有专属写作智能体）
- **发布凭证**: `.mcp.json`（每个领域独立的公众号 AppID/Secret）

### 快速开始

#### 前置条件

1. 安装 [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)
2. 安装 Python 3.x 及依赖：
   ```bash
   pip install schedule
   ```
3. 安装并配置 MCP 服务（见下方 MCP 配置指南）

#### MCP 配置指南

系统依赖 3 个 MCP 服务，需要在每个公众号目录的 `.mcp.json` 中配置。

**1. wenyan-mcp（微信公众号发布 — 必需）**

用于将文章发布到微信公众号草稿箱。

```bash
# 克隆并构建 wenyan-mcp
git clone https://github.com/floodsung/wenyan-mcp.git
cd wenyan-mcp
npm install && npm run build
```

在 `.mcp.json` 中将 `YOUR_WENYAN_MCP_PATH` 替换为你的实际安装路径：
```json
"wenyan-mcp": {
  "command": "node",
  "args": ["/your/path/to/wenyan-mcp/dist/index.js"],
  "env": {
    "WECHAT_APP_ID": "YOUR_APP_ID",
    "WECHAT_APP_SECRET": "YOUR_APP_SECRET"
  }
}
```

微信凭证获取：登录[微信公众平台](https://mp.weixin.qq.com) → 开发 → 基本配置 → 获取 AppID 和 AppSecret。

**2. Playwright MCP（浏览器自动化 — 必需）**

用于 Google News 搜索和网页抓取，无需额外安装，通过 npx 自动下载。

```json
"playwright": {
  "command": "npx",
  "args": ["@playwright/mcp@latest", "--isolated", "--headless"]
}
```

**3. arxiv-mcp-server（arXiv 论文检索 — 可选）**

仅 `intelligent_unit` 等需要论文检索的领域使用。

```bash
# 通过 pip 安装
pip install arxiv-mcp-server
```

```json
"arxiv": {
  "command": "arxiv-mcp-server",
  "args": [],
  "env": {}
}
```

#### 配置步骤

1. 按上述说明安装所需的 MCP 服务
2. 编辑每个公众号目录下的 `.mcp.json`：
   - 将 `YOUR_WENYAN_MCP_PATH` 替换为 wenyan-mcp 的实际路径
   - 将 `YOUR_APP_ID` / `YOUR_APP_SECRET` 替换为对应公众号的凭证
3. 每个公众号使用不同的 AppID/Secret，对应不同的微信公众号账号

#### 运行方式

**立即生成文章（手动触发）：**

```bash
# 生成 1 篇 AI 资讯文章
python media_agent/daily_ai_news.py --now --count 1 --verbose

# 生成 3 篇投资分析文章
python investment_insights/daily_investment_news.py --now --count 3 -v

# 生成 arXiv 论文解读
python intelligent_unit/daily_arxiv_papers.py --now --count 2 -v
```

**定时调度（后台运行）：**

```bash
# 每天北京时间 08:00 和 20:00 各生成 3 篇
python media_agent/daily_ai_news.py --time 08:00 20:00 --count 3

# 后台守护进程运行
nohup python digital_nomad/daily_nomad_news.py --time 09:00 --count 5 > output.log 2>&1 &
```

#### 命令行参数

| 参数 | 说明 |
|------|------|
| `--now` | 立即执行，不等待定时调度 |
| `--count N` | 每次执行生成 N 篇文章 |
| `--time HH:MM [HH:MM ...]` | 设定每日执行的北京时间 |
| `-v` / `--verbose` | 输出详细日志 |

### 工作流程

1. **调度触发** — Python 脚本按设定时间启动
2. **动态 Prompt 生成** — 注入当前时间、24 小时新闻窗口、去重规则
3. **Claude Code 执行** — 搜索资讯 → 提取内容 → 下载图片 → 撰写文章
4. **质量控制** — 部分领域有 Manager Agent 协调 Writer + Reviewer 多轮迭代
5. **发布到草稿箱** — 通过 `wenyan-mcp` 发布，人工审核后正式发布

### 目录结构

```
.
├── CLAUDE.md                    # 全局 Claude 配置
├── README.md
├── media_agent/                 # AI 科技资讯
│   ├── .claude/agents/          # 智能体定义
│   ├── .mcp.json                # MCP 工具 + 公众号凭证
│   ├── daily_ai_news.py         # 调度脚本
│   └── daily_ai_tech_pic.py     # 图文消息发布
├── intelligent_unit/            # arXiv 论文
├── investment_insights/         # 投资洞察
├── digital_tech/                # 数码科技
├── digital_nomad/               # 数字游民
├── fuson/                       # 时尚针织
├── aml_compliance/              # 反洗钱合规
└── military_frontier/           # 军事前沿
```

### 智能体设计

每个领域包含专属智能体（`.claude/agents/*.md`），定义了：

- **写作风格** — 信息密度、句式结构、专业术语
- **反 AI 检测规则** — 禁用过渡词、评价性语言，要求高数据密度
- **图片规范** — 3-8 张原始图片，必须通过 Read 工具验证
- **发布格式** — Markdown frontmatter 仅含 `title` + `cover`
- **合规要求** — 投资领域禁止推荐买卖，合规领域要求中英双语

---

## English

### Overview

A fully automated WeChat Official Account (公众号) content production system powered by Claude AI, built on a **Manager-Editor multi-agent architecture**.

Each of the 8 WeChat accounts has its own independent Agent Manager (Claude Code main process) that discovers trending topics, and its own Sub Agent Editors that handle writing and publishing. All 8 accounts run in parallel, fully independent of each other.

### Multi-Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                Python Scheduling Layer (daily_*.py x 8)      │
│          One independent script per account, cron/manual     │
└──┬──────────┬──────────┬──────────┬──────────┬──────────┬───┘
   │          │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼          ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│AI    │ │arXiv │ │Invest│ │ Tech │ │Nomad │ │Fash- │  ... x8
│News  │ │Papers│ │ment  │ │  Rev │ │      │ │ ion  │
└──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘
   │        │        │        │        │        │
   ▼        ▼        ▼        ▼        ▼        ▼
   Each account has the same internal structure (example below):
```

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  🤖 Agent Manager — Claude Code Main Process (Chief Editor) │
│                                                             │
│  1. Search: WebSearch / Playwright for trending topics (24h)│
│  2. Filter: Remove low-quality topics, deduplicate          │
│  3. Dispatch: Assign topics to Sub Agent Editors            │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                                                       │  │
│  │  ✍️  Sub Agent Editor                                  │  │
│  │      Defined in .claude/agents/*.md                    │  │
│  │                                                       │  │
│  │  • Deep Research: WebFetch multi-source content        │  │
│  │  • Image Sourcing: curl download + Read verify         │  │
│  │  • Write Article: Domain-specific style (Markdown)     │  │
│  │  • (Optional) Reviewer Agent for quality iteration     │  │
│  │  • Publish: wenyan-mcp → WeChat draft box              │  │
│  │                                                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
                ┌───────────────────┐
                │  WeChat Draft Box  │
                │  Manual review     │
                └───────────────────┘
```

### Agent Collaboration Model

Each WeChat account uses a Manager-Editor two-tier collaboration:

```
daily_*.py (Python scheduler)
    │
    └── Agent Manager (Claude Code main process)  ← Topic discovery, filtering, dispatch
            │
            ├── Sub Agent: Writer                 ← Research + write article
            │       │
            │       └── Sub Agent: Reviewer       ← Quality review, anti-AI checks (some)
            │
            └── Sub Agent: Editor                 ← Image curation, formatting, publish
```

- **Agent Manager (Chief Editor)**: The Claude Code main process for each account. Receives dynamic prompts from Python, searches trending topics via WebSearch/Playwright, filters and deduplicates, then dispatches to Sub Agents.
- **Writer Agent**: Specialized writing agents defined in `.claude/agents/*.md`. Each account has its own writing style, terminology, and anti-AI detection rules.
- **Reviewer Agent**: Some accounts (e.g., `intelligent_unit`) have a dedicated reviewer that iterates 2-3 rounds with the writer.
- **Editor Agent**: Handles image curation, layout, and publishing to WeChat via `wenyan-mcp`.

> Key design: All 8 accounts have their own independent Agent Manager and Sub Agents. They run in parallel without interference. Each account's agent config (`.claude/agents/`) and MCP credentials (`.mcp.json`) are fully separate.

### Verticals

| Directory | Domain | Focus | Core Script |
|-----------|--------|-------|-------------|
| `media_agent/` | AI & Tech News | Model releases, industry trends | `daily_ai_news.py` |
| `intelligent_unit/` | arXiv Papers | LLM, Agent, RL paper analysis | `daily_arxiv_papers.py` |
| `investment_insights/` | Investment | US stock earnings, market analysis | `daily_investment_news.py` |
| `digital_tech/` | Digital Products | Product reviews, gadget launches | `daily_digital_tech_news.py` |
| `digital_nomad/` | Digital Nomad | Visa policies, remote work, destinations | `daily_nomad_news.py` |
| `fuson/` | Fashion & Knitwear | Designer collections, runway analysis | `daily_fashion.py` |
| `aml_compliance/` | AML Compliance | OFAC/FATF regulatory updates (bilingual) | `daily_aml_news.py` |
| `military_frontier/` | Military & Defense | Weapon systems, defense tech | `daily_military_frontier.py` |

### Tech Stack

- **Orchestration**: Python + `schedule` library
- **AI Engine**: Claude Code (headless invocation via `subprocess`)
- **MCP Tools**:
  - `wenyan-mcp` — WeChat article publishing
  - `playwright-mcp` — Browser automation (Google News scraping)
  - `arxiv-mcp` — arXiv paper retrieval
- **Agent Config**: `.claude/agents/*.md` (specialized writing agents per vertical)
- **Credentials**: `.mcp.json` (per-vertical WeChat AppID/Secret)

### Quick Start

#### Prerequisites

1. Install [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)
2. Install Python 3.x and dependencies:
   ```bash
   pip install schedule
   ```
3. Install and configure MCP servers (see MCP Setup Guide below)

#### MCP Setup Guide

The system relies on 3 MCP servers, configured in each account's `.mcp.json`.

**1. wenyan-mcp (WeChat Publishing — Required)**

Publishes articles to the WeChat Official Account draft box.

```bash
# Clone and build wenyan-mcp
git clone https://github.com/floodsung/wenyan-mcp.git
cd wenyan-mcp
npm install && npm run build
```

In `.mcp.json`, replace `YOUR_WENYAN_MCP_PATH` with your actual install path:
```json
"wenyan-mcp": {
  "command": "node",
  "args": ["/your/path/to/wenyan-mcp/dist/index.js"],
  "env": {
    "WECHAT_APP_ID": "YOUR_APP_ID",
    "WECHAT_APP_SECRET": "YOUR_APP_SECRET"
  }
}
```

To get WeChat credentials: Log in to the [WeChat Official Account Platform](https://mp.weixin.qq.com) → Development → Basic Configuration → get AppID and AppSecret.

**2. Playwright MCP (Browser Automation — Required)**

Used for Google News search and web scraping. No manual install needed — runs via npx.

```json
"playwright": {
  "command": "npx",
  "args": ["@playwright/mcp@latest", "--isolated", "--headless"]
}
```

**3. arxiv-mcp-server (arXiv Paper Retrieval — Optional)**

Only needed for verticals that search academic papers (e.g., `intelligent_unit`).

```bash
# Install via pip
pip install arxiv-mcp-server
```

```json
"arxiv": {
  "command": "arxiv-mcp-server",
  "args": [],
  "env": {}
}
```

#### Configuration Steps

1. Install the required MCP servers as described above
2. Edit `.mcp.json` in each account directory:
   - Replace `YOUR_WENYAN_MCP_PATH` with the actual path to wenyan-mcp
   - Replace `YOUR_APP_ID` / `YOUR_APP_SECRET` with the WeChat credentials for that account
3. Each account uses different AppID/Secret, corresponding to a separate WeChat Official Account

#### Usage

**Generate articles immediately (manual trigger):**

```bash
# Generate 1 AI news article
python media_agent/daily_ai_news.py --now --count 1 --verbose

# Generate 3 investment analysis articles
python investment_insights/daily_investment_news.py --now --count 3 -v

# Generate arXiv paper analysis
python intelligent_unit/daily_arxiv_papers.py --now --count 2 -v
```

**Scheduled execution (background daemon):**

```bash
# Generate 3 articles daily at 08:00 and 20:00 Beijing time
python media_agent/daily_ai_news.py --time 08:00 20:00 --count 3

# Run as background daemon
nohup python digital_nomad/daily_nomad_news.py --time 09:00 --count 5 > output.log 2>&1 &
```

#### CLI Arguments

| Argument | Description |
|----------|-------------|
| `--now` | Execute immediately, skip scheduled wait |
| `--count N` | Generate N articles per execution |
| `--time HH:MM [HH:MM ...]` | Set daily execution times (Beijing time) |
| `-v` / `--verbose` | Enable verbose logging |

### Workflow

1. **Schedule Trigger** — Python script starts at configured time
2. **Dynamic Prompt Generation** — Injects current time, 24-hour news window, dedup rules
3. **Claude Code Execution** — Search news → Extract content → Download images → Write article
4. **Quality Control** — Some verticals use Manager Agents to coordinate Writer + Reviewer iterations
5. **Publish to Draft Box** — Published via `wenyan-mcp`, manually reviewed before going live

### Project Structure

```
.
├── CLAUDE.md                    # Global Claude configuration
├── README.md
├── media_agent/                 # AI & Tech News
│   ├── .claude/agents/          # Agent definitions
│   ├── .mcp.json                # MCP tools + WeChat credentials
│   ├── daily_ai_news.py         # Orchestration script
│   └── daily_ai_tech_pic.py     # Image message publishing
├── intelligent_unit/            # arXiv Papers
├── investment_insights/         # Investment Insights
├── digital_tech/                # Digital Products
├── digital_nomad/               # Digital Nomad
├── fuson/                       # Fashion & Knitwear
├── aml_compliance/              # AML Compliance
└── military_frontier/           # Military & Defense
```

### Agent Design

Each vertical contains specialized agents (`.claude/agents/*.md`) that define:

- **Writing Style** — Information density, sentence structure, domain terminology
- **Anti-AI Detection Rules** — No transition words, no evaluative language, high data density
- **Image Standards** — 3-8 original images, verified via Read tool
- **Publishing Format** — Markdown frontmatter with `title` + `cover` only
- **Compliance** — Investment vertical prohibits buy/sell recommendations; AML vertical requires bilingual output
