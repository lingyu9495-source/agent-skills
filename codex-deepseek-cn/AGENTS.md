## Codex + Claude Code 国内模型桥

如果用户要求用本机 Codex 或 Claude Code 处理任务，可使用已安装的桥：

- 检查：`~/.codex-claude-bridge/app/scripts/doctor.sh`
- Claude Code：`~/.codex-claude-bridge/app/scripts/ask-claude.sh "<task>" "<abs cwd>"`
- Codex：`~/.codex-claude-bridge/app/scripts/ask-codex.sh "<task>" "<abs cwd>"`
- 支持 MCP 时，添加 `~/.codex-claude-bridge/mcp.json`，调用 `ask_claude` / `ask_codex`。

默认 Claude `dontAsk`、Codex `read-only`。需要写文件/执行命令时，先告知用户，
再显式设置 `CLAUDE_PERMISSION_MODE=acceptEdits` 或
`CODEX_SANDBOX=workspace-write`。不要默认使用 bypass/full-access。

这套桥使用客户自备的国内模型 Key，不需要 Anthropic/OpenAI 账号；不是免费使用
官方模型。Claude Desktop 3P Chat 不能控制宿主机，本桥使用宿主机的 Claude Code CLI。
