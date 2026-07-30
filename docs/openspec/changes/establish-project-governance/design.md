## Context

见 `proposal.md`。当前仓库已经有清晰的赛道目录和局部规则，但缺少根级、可恢复、可验证的 AI 协作状态层。Comet 初始化后，Classic 布局固定为 `docs/openspec/` 和 `docs/superpowers/`。

## Goals / Non-Goals

**Goals:**

- 让后续 AI 工作先确认当前 Comet change，再决定是否创建新 change 或恢复旧 change。
- 让需求行为进入 OpenSpec，执行方法进入 Superpowers，阶段状态进入 Comet。
- 保留各赛道已有规则的优先级，避免根级治理覆盖业务目录细则。
- 为内容生产、公众号草稿箱发布、图片资产、AIGC 检测和月度复盘提供统一风险口径。

**Non-Goals:**

- 不重写现有内容生成脚本。
- 不改变任何公众号发布凭证或发布目标。
- 不迁移历史文章、图片、日志或质检报告。
- 不把所有赛道合并成统一框架。

## Decisions

### 1. 使用 Comet Classic 作为默认工作流

选择 Classic，因为这个项目涉及内容原创边界、发布风险、人工复核和多目录协作，比单纯代码实现更需要显式阶段约束。Native 可留作未来选项，但当前只启用 Classic，降低状态分叉风险。

### 2. OpenSpec 根目录使用 `docs/openspec/`

使用 Comet 默认 docs 布局，避免在根目录散落 `openspec/` 产物。所有 change、archive 和主 specs 都通过 `comet classic openspec -- ...` 访问，不直接依赖物理路径猜测。

### 3. Superpowers 记录“怎么做”

OpenSpec 只定义 WHAT。涉及实现计划、调试、测试、代码审查、分支收尾和复盘证据时，写入 `docs/superpowers/`。这让需求和方法分层，后续恢复时能快速判断：要做什么、做到哪一步、证据在哪里。

### 4. 根级治理只管边界，不替代赛道规则

根级 `AGENTS.md` 和 `CLAUDE.md` 只提供入口规则、目录边界和风险提示。具体写作风格、标题限制、配图规则、质检命令仍以对应目录的 README、CLAUDE.md、specs/ 为准。

### 5. 发布与高风险内容保留人工确认

`--publish`、草稿箱上传、凭证读取、财经事实、军事事实和素材版权都不是纯本地变更。即使 Comet 阶段允许继续，也必须在执行外部写入或高风险发布前让用户确认。

## Risks / Trade-offs

- Comet CLI 要求 Node 22+，当前默认 shell 可能仍是 Node 16。缓解：运行 Comet 命令前使用 `nvm use --delete-prefix v22.22.2` 或安装全局 Node 22 环境。
- 初始化会增加 `.agents/skills/` 等大量工具文件。缓解：这些文件是项目级 AI 工作流的一部分，后续可用 `comet update` 统一升级。
- 根级规则可能与赛道规则重复。缓解：根级只定义协作协议，具体内容质量仍以赛道目录规则为准。
- 月度复盘数据可能来自截图，结构化程度不稳定。缓解：允许先收截图，再整理为表格/JSONL，逐步提高数据质量。

## Migration Plan

1. 保留现有业务目录与脚本不变。
2. 使用 Comet 初始化项目级 Classic 工作流。
3. 将本治理 change 作为第一条 OpenSpec 记录。
4. 后续新增需求通过 `/comet`、`/comet-tweak` 或 `/comet-hotfix` 创建可恢复 change。
5. 验证通过并经用户确认后再归档到主 specs。
