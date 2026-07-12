# 情感女性公众号 Agent

自动生成情感、女性成长类公众号文章的 Agent 系统。

## 定位

- **目标读者**：25-45岁女性，覆盖恋爱、婚姻、育儿、职场与家庭照护压力
- **内容方向**：两性情感、女性成长、情绪疗愈
- **风格**：真实故事 + 犀利观点 + 温暖底色（像有阅历的女性朋友认真聊天）
- **篇幅**：正文目标约 800 个中文字符，发布质检范围 720-900
- **表达约束**：故事占正文至少 75%，有冲突、对话和变化；不虚构真人来源，不在正文插免责声明
- **封面去重**：同批封面不重复，并优先选择最近 12 篇里使用次数最少的封面

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

### 从爆款链接生成原创转化稿

看到一篇同领域爆款后，可以把链接交给脚本：它会抓取正文，分析标题钩子、读者痛点、结构和互动点，再按 `emotion-writer` 风格重新立项写一篇本账号文章。默认只生成本地草稿。

硬约束：必须确认拿到了来源正文，才会进入改写。脚本会检查正文中文长度、过滤明显页面噪声，打印正文预览，并把来源抽取快照保存到 `sources/`。如果抓不到正文，直接停止；不要只凭标题或链接脑补。

默认会跑两轮：第一轮分析爆款并原创转化，第二轮做“人工主编润色”，重点补生活细节、删模板化表达、调整段落节奏、降低搬运感和机器稿味。这个步骤不是绕过检测，而是提升原创质量和账号辨识度。确实想跳过时可加 `--no-editor-polish`。

```bash
export OPENAI_API_KEY="你的 OpenAI API Key"

python rewrite_from_link.py "https://example.com/hot-article"
```

如果公众号链接无法直接抓取，先把原文复制到本地 txt/md，再用：

```bash
python rewrite_from_link.py --source-file /path/to/source.txt
```

生成并直接发布到公众号草稿箱：

```bash
python rewrite_from_link.py "https://example.com/hot-article" --publish
```

这个流程只把来源文章当作选题研究样本，要求更换标题、开头、故事、结构、小标题和表达，并会输出来源相似度指纹。不要做逐段改写或搬运；平台风险的核心处理方式是提高原创度、事实准确性和真人编辑质量，而不是研究绕过检测。

### 从链接直接改写标题和正文

如果不想使用情感 agent 的爆款分析和重构模板，只想拿一篇文章的标题和正文做“直接原创改写”，使用独立脚本：

```bash
python rewrite_direct_from_link.py "https://example.com/source-article"
```

这条链路仍然会先确认拿到来源正文、保存来源快照、计算来源相似度，但不会调用 `emotion-writer` 风格摘要，也不会输出爆款分析。它只要求重写标题、开头、小标题、段落表达和正文内容。生成文件名会带 `direct-` 前缀，避免和情感模板改写稿混在一起。

微信链接会优先使用移动端页面抓取，并抽取正文容器 `js_content`，自动清理阅读器、预约直播、按钮文案等广告/页面噪声。

链接抓不到时也可以传原文文件：

```bash
python rewrite_direct_from_link.py --source-file /path/to/source.txt
```

需要直接发布到公众号草稿箱：

```bash
python rewrite_direct_from_link.py "https://example.com/source-article" --publish
```

### 配图图池

文章第一张图会作为公众号封面，从 `image_pool.txt` 的 `COVER_*` 本地精选封面池读取。脚本会按标题关键词自动匹配封面主题，例如婚姻/家庭、分手/前任、职场、亲密关系、女性成长、朋友关系。

```text
## COVER_BREAKUP
../images/cover/cover_breakup_anxious_900x600.jpg

## COVER_MARRIAGE
../images/cover/cover_marriage_mature_home_900x600.jpg
```

封面图后面的第一张正文图片，优先从 `drama_image_pool.txt` 读取，适合放年轻、现代、彩色的爱情/生活剧关系图、男女主合照或生活化关系截图。为了保证公众号正文清晰度，这个图池只放本地高清缓存图；批量生成/发布时会避开最近 12 篇用过的剧照，并尽量保证同一批文章不用同一来源场景。不要再放年代感强的黑白老片剧照。

```text
../images/drama/your-drama-still-1_900x600.jpg
../images/drama/your-drama-still-2_900x600.jpg
```

其余正文氛围图从 `image_pool.txt` 的 BODY 段读取。发布前会真实探测远程图片，404 或非图片资源会被拦下。

本地图统一为 `900x600`。发布前的质量门槛会检查本地正文图尺寸，并对封面图做亮度、清晰度、色彩吸引力检测，对封面后的影视剧图做清晰度检测，避免公众号里出现随机、偏暗、偏糊或尺寸不一致的图片。

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

### 把已有文章制作成公众号贴图版

贴图版会写入 `articles/image_posts/`，不会覆盖或修改原文章。转换最新 3 篇并推送到公众号草稿箱：

```bash
python article_to_images.py --latest 3 --publish -v
```

也可以只转换指定文章，不发布：

```bash
python article_to_images.py articles/20260712_0913-ex-still-used-membership.md
```

在项目对话中可使用固定口令：

- `贴图最新文章`：转换最新 1 篇，只保存到本地。
- `贴图最新 3 篇文章`：转换最新 3 篇，只保存到本地。
- `贴图最新文章，发到草稿箱`：转换最新 1 篇并发布。
- `贴图最新 3 篇文章，发到草稿箱`：转换最新 3 篇并逐篇发布。

只有口令明确包含“发到草稿箱”时才会发布；否则不调用公众号接口。

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
├── rewrite_from_link.py     # 爆款链接原创转化脚本
├── rewrite_direct_from_link.py # 链接文章标题/正文直接改写脚本
├── publish_existing_article.py # 重试发布已有文章到草稿箱
├── drama_image_pool.txt     # 封面后第一张正文图：影视/生活剧男女主合照等
├── image_pool.txt           # 封面图池 + 正文氛围图池
├── README.md                # 本文件
├── articles/                # 生成的文章
├── images/                  # 文章配图
└── logs/                    # 运行日志
```
