## 1. 工具基线

- [ ] 1.1 为 Codex 项目作用域安装 Comet Classic。
- [ ] 1.2 验证 `.comet/config.yaml` 能把默认工作流解析为 Classic。
- [ ] 1.3 验证 `.codex/` 下已经存在 Codex hook 和 rule 文件。

## 2. OpenSpec 治理基线

- [ ] 2.1 在 `docs/openspec/config.yaml` 中补充项目上下文和 artifact 规则。
- [ ] 2.2 创建 `establish-project-governance` OpenSpec change。
- [ ] 2.3 增加带可验证场景的 `ai-project-governance` delta spec。
- [ ] 2.4 为该 change 补齐 proposal、design 和 tasks artifact。

## 3. Agent 入口指引

- [ ] 3.1 在根级 `AGENTS.md` 中增加 AI 协作指引。
- [ ] 3.2 在根级 `CLAUDE.md` 中同步相同协作指引。
- [ ] 3.3 更新 `目录说明.md`，说明 `.agents/`、`.codex/`、`.comet/` 和 `docs/` 的新用途。
- [ ] 3.4 保留已有 Comet 托管的 ambient resume 区块。

## 4. 验证

- [ ] 4.1 运行 `comet status --json .`，确认 active Classic change 可见。
- [ ] 4.2 运行 `comet classic openspec -- status --change establish-project-governance --json`，确认必需 artifact 都已完成。
- [ ] 4.3 运行 `comet classic openspec -- validate establish-project-governance`。
