# 情感女性公众号 Agent

自动生成情感、女性成长类公众号文章的 Agent 系统。

## 定位

- **目标读者**：25-45岁女性，覆盖恋爱、婚姻、育儿、职场与家庭照护压力
- **内容方向**：两性情感、女性成长、情绪疗愈 + 爬山/骑行/游泳/跑步/做饭/逛街等第一人称生活日记
- **风格**：关系文是具体事件 + 犀利观点 + 温暖底色；生活文是真人口吻的现场记录 + 少量感受
- **篇幅**：正文目标约 800 个中文字符，发布质检范围 720-900
- **内容比例**：每批 3 篇至少 1 篇生活日记；滚动 10 篇保持 4-5 篇，不连续 3 篇全是关系故事
- **表达约束**：关系文故事占至少 75%；生活日记用“我”记录量化细节、感官细节、小失误与行程推进，不硬编关系冲突
- **模板内去重**：保留 2 个小标题、1 处加粗和 3 张图，但轮换开头、重点句/图片位置、冲突结果和结尾；与近期文章同骨架会被质检拦截
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
python daily_emotion_women.py --now --count 1 --provider openai --openai-model gpt-5.6-luna
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

### 从链接保留原标题，只改写正文

如果不想使用情感 agent 的爆款分析和重构模板，只想保留来源标题并原创改写正文，使用独立脚本：

```bash
python rewrite_direct_from_link.py "https://example.com/source-article"
```

这条链路仍然会先确认拿到来源正文、保存来源快照、计算来源相似度，但不会调用 `emotion-writer` 风格摘要，也不会输出爆款分析。来源标题由程序强制原样保留，模型只能重写开头、小标题、段落结构和正文表达。生成文件名会带 `direct-` 前缀，避免和情感模板改写稿混在一起。

在 Codex 中可以直接说：

```text
改写链接：https://example.com/source-article
标题保持原样，只改写正文。只生成本地草稿，不发布。
```

微信链接会优先使用移动端页面抓取，并抽取正文容器 `js_content`，自动清理阅读器、预约直播、按钮文案等广告/页面噪声。

链接抓不到时也可以传原文文件：

```bash
python rewrite_direct_from_link.py --source-file /path/to/source.txt
```

需要直接发布到公众号草稿箱：

```bash
python rewrite_direct_from_link.py "https://example.com/source-article" --publish
```

### 标题硬规则

普通文章标题必须在 20 字以内，并同时融合至少 3 种标题方法：数字法、对比法、热词法、疑问法、对话法、好奇法、俗语法、电影台词法。补救稿、重发稿和新生成稿都走同一套 `quality_gate.py` 发布前质检；只命中 1-2 种方法会直接停止发布。禁止继续使用 `她不再...`、`她没有再...`、`她把...`、`这次，她...` 这类旧标题外壳。

### 配图图池

以后每篇文章固定使用 3 张图片：1 张封面和 2 张正文图。

文章第一张图会作为公众号封面，从 `image_pool.txt` 的 `COVER_*` 本地精选封面池读取。新文章封面优先使用 `images/persona/scenes/` 里的同一人设图池；`images/cover/` 里的旧封面只作为历史重发或临时兜底。默认封面固定使用同一位 28 岁成年女性形象，通过晨间咖啡、通勤、咖啡馆、居家阅读和城市夜晚等生活场景保持账号视觉识别；保留真实皮肤纹理和生活化表情，通过露肩、锁骨、修身剪裁和自然姿态增强吸引力，但不使用未成年感、裸露、透明衣物、内衣特写或低俗挑逗姿势。脚本仍会按标题关键词自动匹配封面主题。

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

第三张正文氛围图从 `image_pool.txt` 的 BODY 段读取。发布前会真实探测远程图片，404 或非图片资源会被拦下。

本地图不再强制为 `900x600`。发布前只检查最低分辨率：短边至少 600 像素、总像素不少于 540000；封面推荐 3:2 横图，正文允许横图或竖图。质量门槛仍会检查亮度、清晰度和色彩，避免使用偏暗或偏糊的图片。

### 本地图像生成环境

当前地区直接访问 OpenAI 图片端点会返回 `unsupported_country_region_territory`。项目使用 Codex 已配置的 `apexapi` OpenAI 兼容端点运行官方 `imagegen` 技能自带 CLI，不在仓库保存 API Key。

一次性安装独立依赖：

```bash
cd /Users/xiao/codeworkspace/自媒体/autoAirtic
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-imagegen.txt
```

验证图像生成环境：

```bash
OPENAI_API_KEY="$(node -p 'require(process.env.HOME + "/.codex/auth.json").OPENAI_API_KEY')" \
OPENAI_BASE_URL="https://apexapi.roixw.com/v1" \
.venv/bin/python "$HOME/.codex/skills/.system/imagegen/scripts/image_gen.py" generate \
  --model gpt-image-2 \
  --prompt "A tasteful editorial portrait of an adult woman" \
  --size 1536x1024 --quality low \
  --out output/imagegen/test-cover.png
```

`.venv/`、`output/` 和真实凭证都已被 Git 忽略。生成公众号封面时推荐使用 `1536x1024` 横图；如果构图安全，可直接加入 `images/persona/scenes/` 和 `image_pool.txt`，不需要额外保存 `900x600` 副本。

### 同一人物视觉 Agent

项目提供 persona-visual-director 子 agent，用同一张母图生成不同造型、表情、姿势和背景。

在 Codex 中使用时，直接复制
[Codex 生成人设图指令](./Codex生成人设图指令.md)
中的单图或文章三图模板。

人物配置：

~~~text
images/persona/persona_profile.yaml
~~~

唯一身份母图：

~~~text
images/persona/master/persona_master_glam_v3.png
~~~

在 Claude Code 中可以直接说：

~~~text
生成人设图：她穿灰色风衣，雨夜站在便利店门口，
一手拿透明雨伞，一手看手机，疲惫但平静，中景。
~~~

或者按文章生成三个分镜：

~~~text
为最新文章生成人设配图
~~~

工作流程：

~~~text
固定母图
→ 生成2张低质量候选
→ 对照母图检查身份和AI瑕疵
→ 生成1张中/高质量定稿
→ 转成一张高质量JPG并保留原分辨率
→ 人工确认
→ 按需加入图池
~~~

候选图保存在 output/persona_jobs，不提交 Git。人工确认后的正式图片写入 images/persona/scenes，生成记录写入 images/persona/metadata。

正式资产整理命令：

~~~bash
cd emotion_women
../.venv/bin/python persona_asset_tool.py finalize \
  output/persona_jobs/JOB/finals/SCENE.png \
  --slug 20260720-topic-scene-cover \
  --prompt-file output/persona_jobs/JOB/prompts/SCENE.txt
~~~

该 agent 复用上文的 imagegen CLI 和 API 配置，不保存 API Key。它不会自动入图池、修改文章或发布公众号。

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

贴图版会自动重写一个 20 字以内的新标题，使用粉彩渐变、大号钩子和同一位轻熟成年女性的 2-3 张生活照拼贴；每张正文卡也保留照片区，不再生成大面积纯文字卡。输出写入 `articles/image_posts/`，不会覆盖或修改原文章。转换最新 3 篇并推送到公众号草稿箱：

```bash
python article_to_images.py --latest 3 --publish -v
```

也可以只转换指定文章，不发布：

```bash
python article_to_images.py articles/20260712_0913-ex-still-used-membership.md
```

确实需要沿用原标题时，显式添加 `--keep-title`。

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
├── rewrite_direct_from_link.py # 保留链接原标题、只改写正文
├── publish_existing_article.py # 重试发布已有文章到草稿箱
├── drama_image_pool.txt     # 封面后第一张正文图：影视/生活剧男女主合照等
├── image_pool.txt           # 封面图池 + 正文氛围图池
├── README.md                # 本文件
├── articles/                # 生成的文章
├── images/                  # 文章配图
└── logs/                    # 运行日志
```
