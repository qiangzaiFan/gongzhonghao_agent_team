# AI 科技资讯公众号 · 自动生成系统

基于 Claude Code 的全自动 AI 科技资讯公众号内容生产系统，采用**主编-写手（Manager-Writer）**多智能体协作架构。

- **主编（Agent Manager）**：Claude Code 主进程。接收 Python 脚本注入的动态 Prompt，用 WebSearch 搜索最近 24h 的 AI/科技热点，筛选选题、检查去重，然后分派给写手。
- **写手（Writer Agent）**：定义在 `.claude/agents/ai-news-writer.md`。做深度研究并撰写高信息密度、反 AI 检测的公众号文章，输出为 Markdown 草稿。

两种运行模式：

- **本地草稿模式（默认）**：文章只生成到 `output/` 下的 Markdown，不碰公众号。
- **发布模式（`--publish`）**：成稿后经 `wenyan-mcp` 排版并推送到微信公众号**草稿箱**，人工审核后再群发。凭证与 wenyan-mcp 路径已配置在 `.mcp.json`。

## 目录结构

```
media_agent/
├── .claude/
│   └── agents/
│       └── ai-news-writer.md   # 写手智能体定义
├── .mcp.json                   # MCP 工具 + 公众号凭证（wenyan-mcp / playwright）
├── CLAUDE.md                   # 项目级 Claude 配置
├── daily_ai_news.py            # 调度脚本（核心）
├── output/                     # 生成的 Markdown 草稿
└── README.md
```

## 快速开始

### 前置条件

- [Claude Code CLI](https://docs.claude.com/en/docs/claude-code)（已安装并登录）
- Python 3.9+
- 定时调度需要：`pip install schedule`

### 立即生成（手动触发）

```bash
# 生成 1 篇（详细日志）
python daily_ai_news.py --now --count 1 --verbose

# 生成 3 篇
python daily_ai_news.py --now --count 3
```

生成的草稿在 `output/` 下，文件名形如 `20260702-0830-openai-gpt5-release.md`。

### 定时调度（后台运行）

```bash
# 每天北京时间 08:00 和 20:00 各生成 3 篇
python daily_ai_news.py --time 08:00 20:00 --count 3

# 后台守护进程
nohup python daily_ai_news.py --time 09:00 --count 5 > output.log 2>&1 &
```

## 命令行参数

| 参数 | 说明 |
| --- | --- |
| `--now` | 立即执行一次，不等待定时调度 |
| `--count N` | 每次执行生成 N 篇文章（默认 1） |
| `--time HH:MM [HH:MM ...]` | 设定每日执行的北京时间，可多个 |
| `-v` / `--verbose` | 输出详细日志（stream-json） |

## 工作流程

1. **调度触发** — Python 脚本按 `--now` 或 `--time` 启动。
2. **动态 Prompt 生成** — 注入当前北京时间、24h 新闻窗口、已发文章标题（去重）。
3. **主编执行** — Claude Code 主进程搜热点 → 筛选选题 → 用 `Task` 工具分派写手。
4. **写手撰写** — 深度研究多源信息 → 按风格规范写 Markdown → 保存到 `output/`。
5. **汇总** — 主编报告每篇标题、路径、摘要。

## 开启真实发布（可选）

当前 `output/` 只是本地草稿。要发布到微信公众号草稿箱：

1. 构建 [wenyan-mcp](https://github.com/floodsung/wenyan-mcp)：
   ```bash
   git clone https://github.com/floodsung/wenyan-mcp.git
   cd wenyan-mcp && npm install && npm run build
   ```
2. 编辑 `.mcp.json`，把 `YOUR_WENYAN_MCP_PATH` 换成 `dist/index.js` 的实际路径，填入微信公众号 `WECHAT_APP_ID` / `WECHAT_APP_SECRET`（微信公众平台 → 开发 → 基本配置）。
3. 在 `daily_ai_news.py` 的 `ALLOWED_TOOLS` 中加入 wenyan-mcp 的发布工具，并在 Prompt 第四步要求写手/编辑调用它发布到草稿箱。

微信公众号发布默认进入**草稿箱**，需人工在后台审核后才正式群发，安全可控。

## 设计说明

- **反 AI 检测**：写手规范禁用过渡词堆砌与评价性套话，要求高数据密度、句式长短交错，详见 `.claude/agents/ai-news-writer.md`。
- **去重**：脚本每次运行会扫描 `output/` 已有文章标题注入 Prompt，主编据此避免重复选题。
- **不编造**：Prompt 与写手规范均强制要求事实来自可查证信源，查不到的数据宁可不写。
- **可扩展**：复制 `media_agent/` 目录，替换 `.claude/agents/` 写手风格与 `.mcp.json` 凭证，即可派生其他垂直领域公众号。
