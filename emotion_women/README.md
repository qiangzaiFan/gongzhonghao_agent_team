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

默认只生成本地 Markdown 草稿，不会碰微信公众号。

默认使用 Claude Code 调度，原有功能不变。也可以切到 OpenAI API：

```bash
export OPENAI_API_KEY="你的 OpenAI API Key"

# 使用 OpenAI API 生成 1 篇本地草稿
python daily_emotion_women.py --now --count 1 --provider openai

# 指定模型
python daily_emotion_women.py --now --count 1 --provider openai --openai-model gpt-5.5
```

OpenAI 路径会复用同一套文章格式、固定图池、图片预检和质量门槛；带 `--publish` 时同样发布到公众号草稿箱。

### 发布到公众号草稿箱

发布前先从模板生成 `emotion_women/.mcp.json`，填好 `wenyan-mcp` 路径和情感女性公众号的 `WECHAT_APP_ID` / `WECHAT_APP_SECRET`。

```bash
cp .mcp.example.json .mcp.json
```

```bash
# 生成 1 篇，并推送到微信公众号草稿箱
python daily_emotion_women.py --now --count 1 --publish -v
```

发布只进入微信公众号**草稿箱**，不会直接群发。成功后去微信公众平台后台：内容与互动 → 草稿箱，人工预览、检查排版和封面后再发布。

如果提示 `IP 白名单限制`，把日志里的 IP 加到微信公众平台：设置与开发 → 基本配置 → IP 白名单，然后重试发布已有文章：

```bash
python publish_existing_article.py articles/20260703_2200_roommate-marriage.md -v
```

### 发布到小红书（图文笔记）

小红书没有官方发文 API，也**没有草稿箱**，这里通过本地运行的
[`xiaohongshu-mcp`](https://github.com/xpzouying/xiaohongshu-mcp)（浏览器自动化）发布。
详细步骤见 `使用说明.md` 的「发布到小红书」一节，概览：

1. 用 Docker 启动 xiaohongshu-mcp（服务在 `http://localhost:18060/mcp`）：

   ```bash
   cd /Users/xiao/codeworkspace/自媒体/xiaohongshu-mcp
   docker compose up -d
   ```

2. 首次需**手机扫码登录**（cookie 存到 `./data` 复用，只做一次）。

3. 公众号长文不能直接发小红书（硬约束：**标题≤20字、正文≤1000字**）。
   先把文章改写成「小红书笔记」，存到 `articles/xhs/<slug>.xhs.md`，再发布
   （**默认以「仅自己可见」发布**，验证无误后再改公开）：

   ```bash
   # 验证：仅自己可见，发布前会打印内容并要人工确认
   python publish_to_xiaohongshu.py articles/xhs/20260705_1502_solo-recovery.xhs.md -v

   # 正式公开
   python publish_to_xiaohongshu.py articles/xhs/20260705_1502_solo-recovery.xhs.md --visibility 公开可见
   ```

### 发布到今日头条（图文长文）

头条走开源的 [Wechatsync](https://github.com/wechatsync/Wechatsync)（Chrome 扩展 + CLI），
**支持长文，公众号原文可直接同步、无需改写**，且**默认进草稿箱**。详见 `使用说明.md`「发布到今日头条」。

一次性准备：Chrome 加载扩展（`../wechatsync-ext/ext/`）、登录 mp.toutiao.com、扩展设置里开启 CLI 桥接。之后：

```bash
# 预览
wechatsync sync articles/20260705_1502_solo-recovery.md -p toutiao --dry-run
# 同步到头条草稿箱（可多平台：-p toutiao,zhihu,baijiahao）
wechatsync sync articles/20260705_1502_solo-recovery.md -p toutiao
```

> 小红书也可以走 Wechatsync（`-p xiaohongshu`），进的是小红书「长文」草稿，不截断。
> 这与 `publish_to_xiaohongshu.py` 发的「图文短笔记」是两种形态，按需选用。

### 生成时自动同步到多平台草稿（一步到位）

`daily_emotion_women.py` 支持 `--sync`：文章成稿后自动用 wechatsync 把**本轮新文章**同步到各平台草稿箱。
前提同上（扩展已连接、平台已登录、`WECHATSYNC_TOKEN` 或 `.wechatsync_token` 已配）。

```bash
# 生成 1 篇 → 公众号草稿 + 头条/小红书草稿（--sync 默认 toutiao,xiaohongshu）
python daily_emotion_women.py --now --count 1 --publish --sync

# 只同步、指定平台（头条+知乎+掘金），不发公众号
python daily_emotion_women.py --now --count 2 --sync toutiao,zhihu,juejin

# 定时：每天 21:00 生成 1 篇，公众号草稿 + 多平台草稿
python daily_emotion_women.py --time 21:00 --count 1 --publish --sync
```

### 定时生成

```bash
# 每天早上9点生成 3 篇
python daily_emotion_women.py --time 09:00 --count 3

# 每天早晚各生成 2 篇
python daily_emotion_women.py --time 09:00 21:00 --count 2

# 每天 21:00 生成 1 篇，并推送到草稿箱
python daily_emotion_women.py --time 21:00 --count 1 --publish
```

### 在 Claude Code 中直接使用

进入 `emotion_women/` 目录后，Claude Code 会自动加载 CLAUDE.md 配置，你可以直接对话：

```
写一篇关于"分手后为什么总是女生在反思"的文章
```

Claude 会调用 `emotion-writer` agent 完成研究、撰写和发布。

## 配置

1. 编辑 `.mcp.json`，填入你的公众号 wenyan-mcp 路径和凭证
2. 如使用 OpenAI API，设置 `OPENAI_API_KEY`；可选 `OPENAI_MODEL` / `OPENAI_BASE_URL` / `OPENAI_ENABLE_WEB_SEARCH=0`
3. 确保已安装 `schedule` 库（定时模式需要）：`pip install schedule`
4. 只有带 `--publish` 时才会加载 `.mcp.json` 并推送草稿箱

## 目录结构

```
emotion_women/
├── .claude/agents/
│   └── emotion-writer.md    # 写作 agent 定义
├── .mcp.json                # MCP 工具配置
├── CLAUDE.md                # 主编指令
├── daily_emotion_women.py   # 自动化脚本
├── publish_existing_article.py # 重试发布已有文章到草稿箱
├── README.md                # 本文件
├── articles/                # 生成的文章
├── images/                  # 文章配图
└── logs/                    # 运行日志
```
