# Codex + Claude Code 国内模型桥（可分发版 v2.0）

让客户用**自己的国内模型 Key** 驱动官方 **Codex CLI** 和 **Claude Code CLI**，
不需要 Anthropic / OpenAI 账号，不需要国际信用卡，不需要翻墙。

- Codex → 默认 DeepSeek（OpenAI 兼容）
- Claude Code → 默认 MiMo Token Plan（Anthropic 兼容）
- 也支持 Anthropic / OpenAI 官方 Key，或任意兼容端点

包里**不含任何 API Key**。安装时由客户提供，写入本机 600 权限文件。

## 一句话说清它是什么

两个 CLI 都是官方 npm 包，本身免费。换的只是「后端」——
把 `base_url` 指向国内厂商的兼容端点，用客户自己的 key 付费。
所以：**省的是账号门槛，不是算力钱。**

## 客户需要什么

- macOS / Linux（Windows 原生步骤见 `references/windows.md`，不必装 WSL）
- Node.js 18+
- Python 3
- 一个国内模型 Key（MiMo `tp-...` 或 DeepSeek `sk-...`）

不需要：Anthropic / OpenAI 账号、Claude Desktop 中文补丁、本地网关。

## 三步：探 → 装 → 验

```bash
# 1. 探（先看这台机器能不能装）
bash scripts/host-check.sh

# 2. 装
MIMO_API_KEY='tp-...' DEEPSEEK_API_KEY='sk-...' \
  bash scripts/install.sh --target all --yes

# 3. 验（四项真跑，全过才算装好）
bash ~/.codex-claude-bridge/app/scripts/smoke-test.sh
```

`--target all` 会：

- 安装/定位 Claude Code 和 Codex 到 `~/.codex-claude-bridge/`
- 写独立的 `CODEX_HOME` / `CLAUDE_CONFIG_DIR`，不碰客户原有配置
- 注册 WorkBuddy / Claude Code 的 skill
- 在 `~/.codex/AGENTS.md` 追加说明
- 生成 `~/.codex-claude-bridge/mcp.json`

只装一个：

```bash
MIMO_API_KEY='tp-...' bash scripts/install.sh --target generic --yes      # 只装 Claude Code
DEEPSEEK_API_KEY='sk-...' bash scripts/install.sh --target generic --yes  # 只装 Codex
```

## 使用

```bash
bash ~/.codex-claude-bridge/app/scripts/ask-claude.sh "分析这个仓库" "/path/to/repo"
bash ~/.codex-claude-bridge/app/scripts/ask-codex.sh "修复测试失败" "/path/to/repo"
```

默认只读：

- Claude：`CLAUDE_PERMISSION_MODE=dontAsk`
- Codex：`CODEX_SANDBOX=read-only`

要写文件时显式提：

```bash
CLAUDE_PERMISSION_MODE=acceptEdits bash .../ask-claude.sh "..." "/repo"
CODEX_SANDBOX=workspace-write      bash .../ask-codex.sh "..." "/repo"
```

`bypassPermissions` / `danger-full-access` 风险极高，必须客户明确同意。

## 工单执行器：备份 + 真 diff + 可回滚

`claude -p` 没有内建 checkpoint/rewind，也不校验 YAML/JSON 语法。
回滚与验收要靠 `scripts/ccjob.sh`：

```bash
cp scripts/ccjob.sh /usr/local/bin/ccjob && chmod +x /usr/local/bin/ccjob

ccjob --dir /repo --job "只改 config.yaml 的 model 为 xxx，别动其他文件"
ccjob --list                    # 历史工单
ccjob --rollback <run_id>       # 回到那一单执行前
```

每单一律：tar 备份 → md5 指纹 → 锁目录限权执行 → 重算指纹 → 打印真实 diff → 留痕。
**验收看磁盘，不看模型自述；一个文件都没变就等于没执行。**

## 智能体接入

| 宿主 | 接法 |
|---|---|
| **Hermes** | 放进 `~/.hermes/profiles/<profile>/skills/`，或照 SKILL.md 直接跑 shell |
| **WorkBuddy** | `--target workbuddy` 写入 `~/.workbuddy/skills/codex-claude-bridge/SKILL.md` |
| **QwenPaw** | 当操作手册用，或只接 MCP（`ask_claude` / `ask_codex`） |
| **Claude Code** | `--target claude` 写入 `~/.claude/skills/` |
| **Codex** | `--target codex` 追加 `~/.codex/AGENTS.md` |
| **Cursor / Cherry Studio / 自研** | 接 `mcp.json` |
| **豆包桌面 / Kimi / 网页助手** | 没有本机 shell，只能输出「粘贴清单」让客户自己执行 |

粘贴清单模板与判断方法见 `references/hosts.md`。

MCP 配置：

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

工具：`ask_codex(prompt, cwd?, sandbox?)`、`ask_claude(prompt, cwd?, permission_mode?, mcp_config?)`。

## 自定义供应商

```bash
# 任意 Anthropic 兼容端点（Claude Code）
bash scripts/install.sh \
  --claude-provider custom \
  --claude-base-url 'https://your-host/anthropic' \
  --claude-model 'your-model' \
  --claude-key '...' --target generic --yes

# 任意 OpenAI 兼容端点（Codex）
bash scripts/install.sh \
  --codex-provider custom \
  --codex-base-url 'https://your-host/v1' \
  --codex-model 'your-model' \
  --codex-wire-api chat \
  --codex-key '...' --target generic --yes
```

更多见 `references/providers.md`。

## 实机验证

2026-11-23 在 Ubuntu 24.04 / Node 22.22.1 跑通全链路：

| 组件 | 版本 | 后端 | 结果 |
|---|---|---|---|
| Claude Code | 2.1.330 | MiMo `mimo-v2.6-flash` | 对话 + 写文件 PASS |
| Codex CLI | 0.171.0 | DeepSeek `deepseek-flash`（responses） | 对话 + 写文件 PASS |

`smoke-test.sh` 汇总 4 PASS / 0 FAIL。未验证项在 `references/verified-matrix.md` 里逐条标了。

## 重要限制

- **不是免费使用 Anthropic/OpenAI 模型**；费用由客户自己的供应商收取。
- 国内模型对 Claude Code / Codex 的工具调用、长上下文、图片、thinking 支持
  不一定完整；以实际测试为准。
- Claude Desktop 3P 的 Chat 在 VM 沙箱里，控不了宿主机；本包用的是 CLI。
- 仅供本地开发/实验；不承诺官方支持、SLA、合规。
- 客户需自行评估厂商条款、地区政策、数据出境/隐私。
- 默认只读，不要默认给 full-access。

## 安全

- 密钥在 `~/.codex-claude-bridge/config.env` 和 `codex-home/auth.json`，600。
- 不写入客户原有 `~/.codex` / `~/.claude` 配置。
- 不上传密钥到任何第三方；但 prompt / 文件内容会发给客户选择的模型供应商。
- 详见 `references/security.md`。

## 卸载

```bash
rm -rf ~/.codex-claude-bridge
rm -rf ~/.workbuddy/skills/codex-claude-bridge
rm -rf ~/.claude/skills/codex-claude-bridge
# 手动删除 ~/.codex/AGENTS.md 里 BEGIN/END codex-claude-bridge 区块
```

## 许可

MIT。见 `LICENSE` 和 `NOTICE`。
