---
name: codex-claude-bridge
description: 用国内或自备模型驱动本机 Codex CLI 与 Claude Code CLI，不需要 Anthropic/OpenAI 账号。适用于 WorkBuddy、Claude Code 或任意支持 MCP 的智能体；当用户要求“用 Codex 做”“用 Claude Code 做”“接入国内模型”时使用。
version: "1.0.0"
user-invocable: true
---

# Codex + Claude Code 国内模型桥

这个 skill 让智能体把任务交给两个本机子代理：

- **Codex CLI**：默认 DeepSeek（OpenAI 兼容）
- **Claude Code CLI**：默认 MiMo Token Plan（Anthropic 兼容）

两个 CLI 都使用**独立配置目录**，不登录 Anthropic/OpenAI，也不覆盖用户原有
`~/.codex` / `~/.claude` 配置。客户只需要自己的国内模型 Key。

## 先检查

```bash
__BRIDGE_HOME__/app/scripts/doctor.sh
```

如果提示 bridge 缺失，说明还没安装。请让用户重新运行安装包里的
`scripts/install.sh`，不要在对话里猜测或写入 Key。

## 委派任务

```bash
# Claude Code：长上下文、需要宿主工具/浏览器的任务
__BRIDGE_HOME__/app/scripts/ask-claude.sh "任务描述" "/absolute/workspace"

# Codex：仓库编辑、重构、代码审查
__BRIDGE_HOME__/app/scripts/ask-codex.sh "任务描述" "/absolute/workspace"
```

- `ask-claude.sh` 默认输出 JSON，读取 `result` 字段。
- `ask-codex.sh` 只输出 Codex 最终 agent message。
- 如果当前智能体支持 MCP，优先调用 `ask_claude` / `ask_codex` 工具；
  MCP 配置在 `__BRIDGE_HOME__/mcp.json`。

## 权限

默认安全：

- Claude：`CLAUDE_PERMISSION_MODE=dontAsk`，不会自动改文件/跑工具
- Codex：`CODEX_SANDBOX=read-only`

需要实际编辑时，先向用户说明，再显式提升：

```bash
CLAUDE_PERMISSION_MODE=acceptEdits __BRIDGE_HOME__/app/scripts/ask-claude.sh "修复测试" "/repo"
CODEX_SANDBOX=workspace-write __BRIDGE_HOME__/app/scripts/ask-codex.sh "修复测试" "/repo"
```

`bypassPermissions` / `danger-full-access` 风险极高，必须获得用户明确同意。

## 重要边界

- 这不是“免费用 Anthropic/OpenAI 模型”；用的是客户自备的国内模型服务。
- Claude Desktop 3P 的 **Chat** 在 VM 沙箱里，不能控制宿主机；本 skill 用的是
  **Claude Code CLI**，运行在宿主机，可配合 MCP 使用浏览器/工具。
- 需要浏览器 MCP 时，给 Claude Code 传 `CLAUDE_MCP_CONFIG=/path/mcp.json`。
- 模型/工具兼容性、费用、条款风险由客户自行评估；默认只读最安全。
