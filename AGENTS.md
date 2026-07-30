<comet-ambient-resume>
<!-- Managed by Comet. Edits inside this block may be replaced by comet init/update. -->
<!-- Contract: comet.resume_probe.v2 -->

## Comet Ambient Resume

在这个仓库中，开始处理需要改动或调查的任务前，如果可能存在活跃 Comet workflow，把当前用户请求传入只读探针：`comet resume-probe . --stdin --json`。

- 如果用户通过宿主明确调用任意 Comet Skill（例如 `@comet`、`/comet`、`@comet-native` 或 `/comet-hotfix`），显式调用优先于本恢复协议；不要运行 resume probe，直接进入被调用的 Skill。
- 只信任返回的 `workflow`、`skill` 和 `entrySource`；它们只由项目配置或无配置兼容回退决定。不得扫描或切换另一套 workflow。
- 如果 probe 返回 `auto_resume`，简短说明选中的 active change，并进入 `nextCommand` 指向的永久入口。不要把状态命令当作恢复入口直接推进。
- 如果 probe 返回 `ask_user`，只问一个简短问题并等待用户回复。
- 如果当前请求未明确调用 Comet Skill，且 probe 返回 `out_of_scope` 或 `none`，不要进入 Comet workflow。
- 如果配置或状态无效且没有 `nextCommand`，停止并报告原因；不要猜测另一个 workflow。
- 不能只因为存在 active change 就把无关任务挂到该 change。Native 的未提交改动由 Native 入口检查，不由探针自动归因。
</comet-ambient-resume>

## 项目 AI 治理

这个仓库是多赛道微信公众号内容生产工作区。把 Comet、OpenSpec 和 Superpowers 当作项目控制层：

- 改项目文件前，先用 `.comet/config.yaml` 和 `comet status` 判断是否已有托管中的 change。
- 需求级变更写入 `docs/openspec/`；设计、计划和执行报告写入 `docs/superpowers/`。
- 优先遵守各赛道本地规则：改某个赛道前先读对应 `README.md`、`CLAUDE.md` 和 `specs/`。
- 除非 OpenSpec proposal 明确写了跨赛道范围，否则变更只限于用户指定赛道。
- 不提交凭证、`.mcp.json`、API key、虚拟环境、日志、生成缓存或临时图片。
- `--publish`、微信公众号草稿箱上传、凭证读取和外部平台写入都必须先经用户确认。

赛道速查：

- `astrology_content/`：星座短文、十二星座日运卡、质量门槛和表现复盘。
- `emotion_women/`：情感女性文章、链接改写、图池、AIGC 检测和草稿箱发布。
- `food_home_cooking/`：家常美食文章、本地配图流水线和原创边界。
- `media_agent/`：AI 科技新闻生成和草稿箱发布。
- `investment_insights/`：财经内容与图表；事实和风险提示需要人工复核。
- `military_frontier/`：军事分析内容；事实、来源和合规需要人工复核。

Comet CLI 要求 Node 22+。如果默认 shell 仍是 Node 16，先运行：

```bash
nvm use --delete-prefix v22.22.2
```
