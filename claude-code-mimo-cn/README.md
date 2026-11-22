# Codex + Claude Code 国内模型桥（可分发版）

让客户用**自己的国内模型 Key** 驱动官方 **Codex CLI** 和 **Claude Code CLI**，
不需要 Anthropic / OpenAI 账号。

- Codex → 默认 DeepSeek（OpenAI 兼容）
- Claude Code → 默认 MiMo Token Plan（Anthropic 兼容）
- 也支持 Anthropic / OpenAI 官方 Key，或任意兼容端点

包里**不含任何 API Key**。安装时由客户提供，写入本机 600 权限文件。

## 客户需要什么

- macOS 或 Linux（Windows 建议 WSL）
- Node.js 18+（WorkBuddy 自带 Node 也可）
- Python 3
- 一个国内模型 Key（MiMo 或 DeepSeek），或官方 Key

不需要：

- Anthropic / OpenAI 账号
- Claude Desktop 中文补丁
- 本地网关

## 一键安装

```bash
unzip codex-claude-bridge-portable.zip
cd codex-claude-bridge-portable

MIMO_API_KEY='tp-...' \
DEEPSEEK_API_KEY='sk-...' \
bash scripts/install.sh --target all --yes
```

`--target all` 会：

- 安装/定位 Claude Code 和 Codex 到 `~/.codex-claude-bridge/`
- 写独立的 `CODEX_HOME` / `CLAUDE_CONFIG_DIR`，不碰客户原有配置
- 注册 WorkBuddy / Claude Code 的 skill
- 在 `~/.codex/AGENTS.md` 追加说明
- 生成 `~/.codex-claude-bridge/mcp.json`

只想装一个：

```bash
# 只装 Claude Code + MiMo
MIMO_API_KEY='tp-...' bash scripts/install.sh --target generic --yes

# 只装 Codex + DeepSeek
DEEPSEEK_API_KEY='sk-...' bash scripts/install.sh --target generic --yes
```

## 检查

```bash
bash ~/.codex-claude-bridge/app/scripts/doctor.sh
```

## 使用

```bash
bash ~/.codex-claude-bridge/app/scripts/ask-claude.sh "分析这个仓库" "/path/to/repo"
bash ~/.codex-claude-bridge/app/scripts/ask-codex.sh "修复测试失败" "/path/to/repo"
```

默认：

- Claude：`CLAUDE_PERMISSION_MODE=dontAsk`
- Codex：`CODEX_SANDBOX=read-only`

需要写文件/跑命令时显式提升：

```bash
CLAUDE_PERMISSION_MODE=acceptEdits bash .../ask-claude.sh "..." "/repo"
CODEX_SANDBOX=workspace-write bash .../ask-codex.sh "..." "/repo"
```

## 智能体接入

### WorkBuddy

`--target workbuddy` 会写：

```text
~/.workbuddy/skills/codex-claude-bridge/SKILL.md
```

重启/刷新 WorkBuddy 后，直接说“用 Claude Code / Codex 做这个”。

### Claude Code

写到：

```text
~/.claude/skills/codex-claude-bridge/SKILL.md
```

或者直接调用 `ask-claude.sh`。

### Codex

在 `~/.codex/AGENTS.md` 追加一段说明，Codex 读全局 AGENTS.md 后即可按说明调用。

### 其他智能体（Cursor / 自研 Agent / MCP 客户端）

把以下 MCP server 加进客户端：

```json
{
  "mcpServers": {
    "codex-claude-bridge": {
      "command": "python3",
      "args": ["/Users/you/.codex-claude-bridge/app/mcp/server.py"]
    }
  }
}
```

可用工具：

- `ask_codex(prompt, cwd?, sandbox?)`
- `ask_claude(prompt, cwd?, permission_mode?, mcp_config?)`

## 自定义供应商

```bash
# 任意 Anthropic 兼容端点（Claude Code）
bash scripts/install.sh \
  --claude-provider custom \
  --claude-base-url 'https://your-host/anthropic' \
  --claude-model 'your-model' \
  --claude-key '...' \
  --target generic --yes

# 任意 OpenAI 兼容端点（Codex）
bash scripts/install.sh \
  --codex-provider custom \
  --codex-base-url 'https://your-host/v1' \
  --codex-model 'your-model' \
  --codex-wire-api chat \
  --codex-key '...' \
  --target generic --yes
```

更多见 [references/providers.md](references/providers.md)。

## 重要限制

- **不是免费使用 Anthropic/OpenAI 模型**；费用由客户自己的供应商收取。
- 国内模型对 Claude Code/Codex 的工具调用、长上下文、图片、thinking 支持
  不一定完整；以实际测试为准。
- 仅供本地开发/实验；不承诺官方支持、SLA、合规。
- 客户需自行评估厂商条款、地区政策、数据出境/隐私。
- 默认只读/不自动批准工具；不要默认给 full-access。

## 安全

- 密钥在 `~/.codex-claude-bridge/config.env` 和 `codex-home/auth.json`，600。
- 不写入客户原有 `~/.codex` / `~/.claude` 配置。
- 不上传密钥到任何第三方；但 prompt/文件内容会发给客户选择的模型供应商。
- 详见 [references/security.md](references/security.md)。

## 卸载

```bash
rm -rf ~/.codex-claude-bridge
rm -rf ~/.workbuddy/skills/codex-claude-bridge
rm -rf ~/.claude/skills/codex-claude-bridge
# 手动删除 ~/.codex/AGENTS.md 里 BEGIN/END codex-claude-bridge 区块
```

## 许可

MIT。见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。
