# 情感女性公众号 Agent

自动生成情感、女性成长类公众号文章的 Agent 系统。

## 定位

- **目标读者**：22-35岁都市女性
- **内容方向**：两性情感、女性成长、情绪疗愈
- **风格**：真实故事 + 犀利观点 + 温暖底色（像闺蜜深夜聊天）

## 使用方法

### 立即生成文章

```bash
# 生成 1 篇文章
python daily_emotion_women.py --now --count 1

# 生成 3 篇文章（实时输出）
python daily_emotion_women.py --now --count 3 -v
```

### 定时生成

```bash
# 每天早上9点生成 3 篇
python daily_emotion_women.py --time 09:00 --count 3

# 每天早晚各生成 2 篇
python daily_emotion_women.py --time 09:00 21:00 --count 2
```

### 在 Claude Code 中直接使用

进入 `emotion_women/` 目录后，Claude Code 会自动加载 CLAUDE.md 配置，你可以直接对话：

```
写一篇关于"分手后为什么总是女生在反思"的文章
```

Claude 会调用 `emotion-writer` agent 完成研究、撰写和发布。

## 配置

1. 编辑 `.mcp.json`，填入你的公众号 wenyan-mcp 路径和凭证
2. 确保已安装 `schedule` 库（定时模式需要）：`pip install schedule`

## 目录结构

```
emotion_women/
├── .claude/agents/
│   └── emotion-writer.md    # 写作 agent 定义
├── .mcp.json                # MCP 工具配置
├── CLAUDE.md                # 主编指令
├── daily_emotion_women.py   # 自动化脚本
├── README.md                # 本文件
├── articles/                # 生成的文章
├── images/                  # 文章配图
└── logs/                    # 运行日志
```
