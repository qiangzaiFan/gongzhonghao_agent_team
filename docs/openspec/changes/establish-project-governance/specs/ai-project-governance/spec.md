## Purpose

本能力定义 AI 在当前多赛道公众号项目中如何通过文件系统管理需求、阶段、设计、验证和发布风险，避免跨赛道误改、遗漏质检或凭聊天上下文恢复任务。

## ADDED Requirements

### Requirement: Comet Workflow Ownership

项目中的需求型变更 MUST 由 Comet Classic change 记录当前阶段和恢复状态。

#### Scenario: Start managed project work

- **WHEN** 用户要求新增功能、调整业务行为、改内容流水线或整理跨目录规则
- **THEN** AI MUST 使用项目配置的 Comet 入口创建或恢复一个 OpenSpec change
- **AND** 当前 change MUST 具有 `.comet.yaml` 状态文件
- **AND** 当前 change MUST 可通过 `comet status` 或 `comet state check` 检查

#### Scenario: Resume after interruption

- **WHEN** 工作在中途被打断或上下文被压缩
- **THEN** AI MUST 先读取 `.comet/config.yaml` 和 `.comet/current-change.json`
- **AND** AI MUST 使用 Comet resume/status/state 命令确认当前 change 与阶段
- **AND** AI MUST NOT 只依据聊天历史继续改文件

### Requirement: OpenSpec Requirements Source

影响项目行为、模块边界、发布流程或质量门槛的变更 MUST 以 OpenSpec artifact 作为需求事实源。

#### Scenario: Document a behavior change

- **WHEN** 变更会影响文章生成、链接改写、质检、图片生成、复盘、发布或凭证处理
- **THEN** OpenSpec change MUST 包含 proposal、delta spec、design 和 tasks
- **AND** delta spec MUST 使用 Requirement 和 Scenario 描述可验证行为
- **AND** tasks MUST 使用 `- [ ]` 复选框格式

#### Scenario: Keep local lane rules authoritative

- **WHEN** 变更只影响一个赛道目录
- **THEN** AI MUST 读取该目录的 README、CLAUDE.md 和 specs/
- **AND** OpenSpec artifact MUST 说明涉及目录
- **AND** AI MUST NOT 修改其他赛道目录，除非 proposal 明确列入范围

### Requirement: Superpowers Execution Discipline

实现阶段 MUST 使用 Superpowers 风格的设计、计划、验证和复盘文档来记录“怎么做”。

#### Scenario: Prepare implementation

- **WHEN** OpenSpec open 阶段完成并进入 design/build
- **THEN** AI MUST 在 `docs/superpowers/` 下记录设计、计划或报告
- **AND** 计划 MUST 拆成可验证的小任务
- **AND** 每个任务 MUST 绑定代码、文档或人工验收结果

#### Scenario: Verify before completion

- **WHEN** AI 准备声称某项变更完成
- **THEN** AI MUST 运行与影响范围匹配的验证命令
- **AND** AI MUST 在回复或报告中记录验证证据
- **AND** 如果无法运行验证，AI MUST 明确说明原因和剩余风险

### Requirement: Content Safety And Publishing Guard

内容生产和发布相关操作 MUST 保留质检、原创边界和人工确认。

#### Scenario: Generate or rewrite content

- **WHEN** AI 生成或改写公众号文章
- **THEN** AI MUST 遵守对应赛道的风格、原创边界和质量门槛
- **AND** AI SHOULD 运行对应目录的 quality_gate、preflight、ai_detector 或 performance_tracker
- **AND** AI MUST NOT 把外部原文逐段搬运或把他人图片二改当作自有素材

#### Scenario: Trigger publish-capable workflow

- **WHEN** 命令、脚本或任务可能触发 `--publish`、草稿箱上传、凭证读取或外部平台写入
- **THEN** AI MUST 明确说明目标账号、动作类型和是否只是草稿箱
- **AND** AI MUST 等待用户确认后再执行发布相关命令
- **AND** AI MUST NOT 提交真实凭证、token、`.mcp.json` 或本地密钥文件

### Requirement: Monthly Performance Review Records

公众号月度复盘 MUST 使用结构化文件记录关键数据和结论，方便后续选题、标题和发布时间优化。

#### Scenario: Review astrology account performance

- **WHEN** 用户提供星座公众号月度阅读、互动或涨粉数据
- **THEN** AI SHOULD 整理为结构化复盘记录
- **AND** 记录 SHOULD 覆盖文章标题、主题、星座、发布时间、阅读、分享、点赞/在看、新增关注和备注
- **AND** 结论 SHOULD 输出下月选题方向、标题规律和需要避免的低效模式
