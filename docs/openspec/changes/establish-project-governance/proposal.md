## Why

当前仓库已经从多个独立公众号脚本发展为多赛道内容生产工作区。AI 协作如果只依赖聊天记录，容易忘记赛道边界、发布风险、质检口径和正在进行的变更阶段。

现在引入 Comet + OpenSpec + Superpowers，是为了把需求、设计、执行计划、验证证据和恢复状态落到文件系统里，让后续 AI 可以按项目规则继续工作，而不是靠上下文记忆猜测。

## What Changes

- 初始化项目级 Comet Classic 工作流，默认使用 OpenSpec + Superpowers 五阶段：open、design、build、verify、archive。
- 建立项目治理能力，要求后续行为变更通过 OpenSpec change 记录目标、范围、非目标和验收场景。
- 把当前多赛道公众号项目的模块边界、质量检查、发布风险和人工复核要求写入 OpenSpec 上下文。
- 为 AI 协作增加根级入口说明，要求优先读取 Comet 状态、OpenSpec 规格和各赛道本地 README/CLAUDE/specs。
- 不改变现有文章生成脚本、公众号发布脚本、图片流水线或历史草稿内容。

## Capabilities

### New Capabilities

- `ai-project-governance`: 管理 AI 在当前多赛道公众号项目中的需求记录、阶段推进、模块边界、质量验证和发布前人工确认。

### Modified Capabilities

- 无。

## Impact

- 新增项目级配置和工作流文件：`.comet/`、`.codex/`、`.agents/skills/`、`docs/openspec/`、根级 `AGENTS.md`、`CLAUDE.md` 和 `目录说明.md`。
- OpenSpec 主工作区位于 `docs/openspec/`；Superpowers 设计、计划和报告位于 `docs/superpowers/`。
- 现有业务目录保持原状：`astrology_content/`、`emotion_women/`、`food_home_cooking/`、`investment_insights/`、`media_agent/`、`military_frontier/`。
- 后续涉及公众号发布、财经/军事事实、AIGC 检测、图片版权或凭证配置的操作仍需要人工确认。
