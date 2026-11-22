---
slug: codex-claude-bridge-cn
displayName: Codex + Claude Code 国内模型桥
version: 1.0.0
summary: 用客户自己的国内模型 Key 驱动本机 Codex CLI 与 Claude Code CLI，不需要 Anthropic/OpenAI 账号。适用于 WorkBuddy、Hermes、QwenPaw、Cursor 及任意支持 MCP 的智能体；智能体可代为部署并委派任务。
license: MIT
name: codex-claude-bridge
description: 让豆包/WorkBuddy/Hermes/QwenPaw 等智能体帮客户在本机部署 Codex CLI 与 Claude Code CLI，并用国内模型 Key（MiMo/DeepSeek 或任意兼容端点）驱动，无需 Anthropic/OpenAI 账号。当用户说「用 Codex 做」「用 Claude Code 做」「接入国内模型」「帮我装 Codex/Claude Code」时使用。
author: 九品锦里e
tags: [codex, claude-code, 国内模型, 智能体部署, mcp]
---

# Codex + Claude Code 国内模型桥

让客户用**自己的国内模型 Key** 驱动官方 **Codex CLI** 和 **Claude Code CLI**，
不需要 Anthropic / OpenAI 账号，也不需要翻墙。

- Codex → 默认 DeepSeek（OpenAI 兼容）
- Claude Code → 默认 MiMo Token Plan（Anthropic 兼容）
- 也支持 Anthropic / OpenAI 官方 Key，或任意兼容端点

本包**不含任何 API Key**：安装时由客户提供，写入本机 600 权限文件，不覆盖客户原有
`~/.codex` / `~/.claude` 配置。

## 一、先判断：当前这个智能体能不能替你动手

这一步决定后面走「代装」还是「出指令清单」。**别让没有执行能力的助手假装在装。**

| 宿主 | 有本地执行能力 | 怎么用 |
|---|---|---|
| Hermes（含各 profile） | 有 shell | 直接照第三节执行脚本；也可把本技能放进 skills 目录长期调用 |
| QwenPaw | 有 shell（Linux/macOS 宿主机） | 技能库格式不同，把本文当操作手册照做，用 shell 调 `ask-*.sh` |
| WorkBuddy | 有 shell + 自带 Node | `--target workbuddy` 会自动注册技能，之后直接说「用 Codex 做」 |
| Claude Code / Codex 自己 | 有 shell | 装完互相调用即可 |
| 豆包、Kimi、网页版助手 | **通常没有本地 shell** | 只能输出「逐条命令清单」交给客户粘贴执行，装完再把结果贴回来 |

判断方法：让智能体跑一句 `uname -a` 或 `node -v`。能返回结果＝有执行能力；说「我无法访问你的电脑」＝只能出清单。

## 二、客户需要准备什么

- macOS 或 Linux（Windows 走 WSL）
- **Node.js 18+**（WorkBuddy 自带的 Node 也能用）
- Python 3
- 一个国内模型 Key：MiMo（`tp-...`）或 DeepSeek（`sk-...`），也可以是任意兼容端点

**不需要**：Anthropic / OpenAI 账号、Claude Desktop 中文补丁、本地网关。

> 客户机器上**没装过** Codex / Claude Code 也可以——安装脚本会自动 npm 安装到
> `~/.codex-claude-bridge/`，不污染全局环境。已经装过的会自动定位，或用
> `--claude-bin` / `--codex-bin` 指过去。

## 三、部署（智能体代执行，或客户粘贴执行）

```bash
unzip codex-claude-bridge-portable.zip
cd codex-claude-bridge-portable

MIMO_API_KEY='tp-...' \
DEEPSEEK_API_KEY='sk-...' \
bash scripts/install.sh --target all --yes
```

`--target all` 会做四件事：

1. 安装或定位 Claude Code 与 Codex 到 `~/.codex-claude-bridge/`
2. 写独立的 `CODEX_HOME` / `CLAUDE_CONFIG_DIR`，**不碰客户原有配置**
3. 按宿主注册技能（WorkBuddy / Claude Code）或追加 `~/.codex/AGENTS.md` 说明
4. 生成 `~/.codex-claude-bridge/mcp.json`

只装一个：

```bash
# 只装 Claude Code + MiMo
MIMO_API_KEY='tp-...' bash scripts/install.sh --target generic --yes

# 只装 Codex + DeepSeek
DEEPSEEK_API_KEY='sk-...' bash scripts/install.sh --target generic --yes
```

**Key 处理铁律**：Key 由客户自己粘贴进命令或写进环境变量，智能体**不要**把它复述到聊天记录、日志或任何交付物里；安装后落在 `config.env`，权限 600。

## 四、自检（装完必须跑，不许「应该好了」）

```bash
bash ~/.codex-claude-bridge/app/scripts/doctor.sh
```

看到 `config: ok (600)`、`claude: …`、`codex: …` 三行都有值，才算装上。
再发一句冒烟测试，两边都要能答：

```bash
bash ~/.codex-claude-bridge/app/scripts/ask-claude.sh "只回答：OK"
bash ~/.codex-claude-bridge/app/scripts/ask-codex.sh "只回答：OK"
```

任何一边超时或报 401，先查 Key 与 base_url（见 `references/troubleshooting.md`），
不要反复重装。

## 五、日常委派

```bash
# Claude Code：长上下文、需要宿主工具/浏览器的任务
~/.codex-claude-bridge/app/scripts/ask-claude.sh "任务描述" "/absolute/workspace"

# Codex：仓库编辑、重构、代码审查
~/.codex-claude-bridge/app/scripts/ask-codex.sh "任务描述" "/absolute/workspace"
```

- `ask-claude.sh` 默认输出 JSON，取 `result` 字段
- `ask-codex.sh` 只输出 Codex 最终 agent message
- 宿主支持 MCP 时优先用 `ask_claude` / `ask_codex` 工具，配置在 `~/.codex-claude-bridge/mcp.json`

## 六、权限：默认只读，要写文件必须显式提

| 层级 | Claude | Codex |
|---|---|---|
| 默认（安全） | `dontAsk`，不改文件、不跑工具 | `read-only` 沙箱 |
| 允许改文件 | `acceptEdits` | `workspace-write` |
| 全放行（慎用） | `bypassPermissions` | `danger-full-access` |

前两级可直接用；**第三级必须拿到客户明确同意**，并在交付说明里写明风险。

```bash
CLAUDE_PERMISSION_MODE=acceptEdits bash ~/.codex-claude-bridge/app/scripts/ask-claude.sh "修复测试" "/repo"
CODEX_SANDBOX=workspace-write      bash ~/.codex-claude-bridge/app/scripts/ask-codex.sh "修复测试" "/repo"
```

## 七、各宿主接入

**WorkBuddy**：`--target workbuddy` 写入 `~/.workbuddy/skills/codex-claude-bridge/SKILL.md`，刷新后直接说「用 Claude Code / Codex 做这个」。

**Claude Code**：写入 `~/.claude/skills/codex-claude-bridge/SKILL.md`，或直接调 `ask-claude.sh`。

**Codex**：在 `~/.codex/AGENTS.md` 追加说明块，Codex 读到全局 AGENTS.md 后按说明调用。

**Hermes / 其他自研 Agent**：把本目录放进 skills 目录，按本文用 shell 调脚本即可。

**任意 MCP 客户端（Cursor、QwenPaw、自研）**：

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

可用工具：`ask_codex(prompt, cwd?, sandbox?)`、`ask_claude(prompt, cwd?, permission_mode?, mcp_config?)`。

## 八、换成别的供应商

```bash
# 任意 Anthropic 兼容端点（Claude Code）
bash scripts/install.sh --claude-provider custom \
  --claude-base-url 'https://your-host/anthropic' \
  --claude-model 'your-model' --claude-key '...' \
  --target generic --yes

# 任意 OpenAI 兼容端点（Codex）
bash scripts/install.sh --codex-provider custom \
  --codex-base-url 'https://your-host/v1' \
  --codex-model 'your-model' --codex-wire-api chat \
  --codex-key '...' --target generic --yes
```

更多见 `references/providers.md`。

## 九、重要边界（对客户必须说清）

- **这不是「免费用 Anthropic/OpenAI 模型」**：用的是客户自备的国内模型服务，费用由客户自己的供应商收取。
- 国内模型对 Claude Code / Codex 的工具调用、长上下文、图片、thinking 支持**不一定完整**，以实际测试为准；不支持时换模型或换端点，不要硬扛。
- Claude Desktop 3P 的 **Chat 跑在 VM 沙箱里，控制不了宿主机**；本技能用的是 **Claude Code CLI**（宿主进程），能读写项目文件、能配 MCP。
- 模型厂条款、地区政策、数据出境与隐私，由客户自行评估；prompt 与文件内容会发给客户选择的供应商。
- 默认只读、不自动批准工具；**不要**默认给 full-access。

## 十、卸载

```bash
rm -rf ~/.codex-claude-bridge
rm -rf ~/.workbuddy/skills/codex-claude-bridge
rm -rf ~/.claude/skills/codex-claude-bridge
# 手动删除 ~/.codex/AGENTS.md 里 BEGIN/END codex-claude-bridge 区块
```

## 参考文件

- `references/providers.md` — 各供应商参数与 model 名
- `references/security.md` — 密钥与数据流
- `references/troubleshooting.md` — 401 / 超时 / 工具调用失败的排查顺序
- `README.md` — 可分发版的完整说明
