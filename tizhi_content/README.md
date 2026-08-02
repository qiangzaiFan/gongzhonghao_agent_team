# 体制内公众号内容工作区

本目录用于参考4位标杆博主的文章，生成具有独立辨识度的体制内公众号原创稿。统一风格已锁定，不再按单一博主切换口吻。“体制内清醒成长”作为新增题材方向使用，不替代原有账号主轴。

## 目录结构

```text
tizhi_content/
├── .claude/agents/                  写作 Agent
├── references/
│   ├── CORPUS_MANIFEST.md             语料路径与数量
│   ├── blogger_01/                  安小渔
│   ├── blogger_02/                  烟火里的小安稳
│   ├── blogger_03/                  田间烟火
│   └── blogger_04/                  老周的建议
├── style_profiles/                  语料报告和已锁定统一风格
├── specs/                           流程、模板和原创边界
├── reviews/auto/                    AIGC 检测报告
├── ai_detector.py                   AIGC 强制检测入口
└── articles/                        原创成稿
```

## 使用方法

1. 语料库位于 `CORPUS_MANIFEST.md` 登记的外部目录，无需在仓库内重复保存823份原文。
2. 创作前读取 `style_profiles/unified_house_style.md`，不单独切换某位博主的口吻。
3. 收到选题后先生成3至5个标题，用户未指定时可由 Agent 代选最适合的一个。
4. 成稿保存到 `articles/`，不覆盖参考原文。
5. 每篇新稿或修改稿必须运行 `ai_detector.py`，通过后才能标记为可发布。
6. 封面图和正文插图统一使用本地 ComfyUI 生成横向风景图，风景地点可来自世界各地，详见 `specs/comfyui_flux2_klein_image_standard.md`。
7. 发布或进入微信公众号草稿箱前，最后排版统一使用 `wenyan-mcp` 的 `lapis` 主题优化；排版走清爽政务蓝 / 商务简约风：白底、深蓝标题、浅灰分割、少装饰、重留白。
8. 体制内公众号名称和文章作者统一为“田间里的烟火”。
9. 语料更新后，可运行 `scripts/analyze_corpus.py` 重新校准数据。

## 排版与发布

`daily_tizhi.py --publish` 和 `publish_existing_article.py` 共用同一套发布默认值：`wenyan-mcp` 的 `lapis` 主题，作者“田间里的烟火”。独立发布现有文章时使用：

```bash
python tizhi_content/publish_existing_article.py tizhi_content/articles/<article>.md
```

发布脚本会先执行本地检查和 AIGC 检测，再由 `wenyan-mcp` 完成最终图文排版并写入微信公众号草稿箱。

## AIGC 检测

```bash
.venv/bin/python tizhi_content/ai_detector.py \
  tizhi_content/articles/<article>.md
```

默认通过线为 `human >= 90%` 且 `ai <= 10%`。详细规则见 `specs/aigc_gate.md`。

## 核心边界

- 只提炼选题角度、标题结构、叙事节奏、论证方式和词汇层级等可迁移规律。
- 标题可使用相同选题或通用表达；强识别度长标题默认重写，除非用户明确指定原题。
- 不复制或近似改写原文句子、段落、独特比喻、案例和观点顺序。
- 新稿必须更换主题论断、素材、案例和结构，能够脱离参考文章独立成立。
- 不写成可以被误认为原博主本人发布的文本。
- 涉及纪检、人事、政策、礼品礼金等敏感主题，发布前必须人工复核。
