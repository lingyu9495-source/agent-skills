---
slug: codex-claude-bridge-cn
displayName: Codex + Claude Code 国内模型桥（多宿主版）
version: 2.0.0
summary: 一个技能包，让能跑 shell 的智能体（Hermes / WorkBuddy / QwenPaw / Claude Code / Codex）替客户在本机装好并驱动官方 Codex CLI 与 Claude Code CLI，后端接客户自己的国内模型 Key（MiMo / DeepSeek / 任意兼容端点），不需要 Anthropic 或 OpenAI 账号。装完有机器验收，四项真跑全过才算交付。
license: MIT
name: codex-claude-bridge
description: 让豆包/WorkBuddy/Hermes/QwenPaw/Cursor 等智能体帮客户在本机部署官方 Codex CLI 与 Claude Code CLI，并用国内模型 Key（MiMo/DeepSeek 或任意兼容端点）驱动，不需要 Anthropic/OpenAI 账号。当用户说「用 Codex 做」「用 Claude Code 做」「接入国内模型」「帮我装 Codex / Claude Code」「不用账号用 Claude Code」时使用。
author: 九品锦里e
tags: [codex, claude-code, 国内模型, 智能体部署, mcp, 客户交付]
---

# Codex + Claude Code 国内模型桥

一句话：**把官方 Codex CLI 和 Claude Code CLI 装上，后端换成客户自己的国内模型 Key。**
两个客户端都是官方 npm 包，不魔改、不破解；换的只是 `base_url` + `key` + 模型名。

- Codex → 默认 DeepSeek（OpenAI 兼容，`wire_api = responses`）
- Claude Code → 默认 MiMo Token Plan（Anthropic 兼容）
- 也支持 Anthropic / OpenAI 官方 Key，或任何兼容端点
- 本包不含任何 API Key，安装时由客户提供，落到 600 权限文件
- 独立 `CODEX_HOME` / `CLAUDE_CONFIG_DIR`，**不覆盖**客户原有 `~/.codex` / `~/.claude`

## 零、先说清一件事（对客户必须讲）

**这不是「免费使用 Anthropic / OpenAI 模型」。** 两个 CLI 本体免费开源，模型算力要钱，
钱交给客户自己选的国内供应商（DeepSeek / 小米 MiMo / 智谱 / Kimi 都行）。
省掉的是**账号门槛**（不用注册 Anthropic、不用国际信用卡、不用翻墙），不是算力成本。
把这句话讲在前面，客户才不会后面觉得被忽悠。

## 一、三步走：探 → 装 → 验

不要跳步。**跳过探测直接装，是这套东西最常见的翻车方式。**

### 第 1 步 · 探（10 秒）

```bash
bash scripts/host-check.sh
```

它会告诉你三件事：这台机器有没有 node / npm / python3、npm 源通不通、
本机是否已经装过 claude / codex。结尾直接给结论：走「代装」还是走「粘贴清单」。

判据很简单：**能不能跑 shell**。

| 宿主 | 能跑 shell | 走哪条路 |
|---|---|---|
| Hermes（任意 profile） | ✅ | AI 自己跑 install.sh，跑完自己验收 |
| WorkBuddy | ✅ 且自带 Node | 同上，`--target workbuddy` 会自动注册技能 |
| QwenPaw | ✅（Linux/macOS 宿主） | 同上，技能库格式不同，照 README 手动放 |
| Claude Code / Codex 自己 | ✅ | 互相调用，装完即用 |
| Cursor / Cherry Studio / 任意 MCP 客户端 | ✅（有终端） | 装完接 `mcp.json`，调 `ask_claude` / `ask_codex` |
| 豆包桌面 / Kimi / 网页版助手 | ❌ 通常没有本机 shell | **只能出「粘贴清单」**，客户自己粘 |

> 实测口径：让智能体跑一句 `node -v`。返回版本号 = 有执行能力；
> 回「我无法访问你的电脑」= 只能出清单。**别让没有执行能力的助手假装在装。**

### 第 2 步 · 装

```bash
MIMO_API_KEY='tp-...' DEEPSEEK_API_KEY='sk-...' \
  bash scripts/install.sh --target all --yes
```

`--target all` 做四件事：装/定位两个 CLI 到 `~/.codex-claude-bridge/`、写独立配置目录、
按宿主注册技能、生成 `mcp.json`。只装其中一个就用 `--target generic` 且只给一个 key。

已经装过官方 CLI 的机器不用重装，指过去即可：

```bash
bash scripts/install.sh --target all --yes \
  --claude-bin /usr/bin/claude --codex-bin /usr/bin/codex \
  --no-install-claude --no-install-codex
```

**Key 铁律**：key 由客户自己贴进命令或环境变量。智能体**不得**把 key 复述到聊天记录、
日志、截图、交付文档里；装完只报「key=set」，不报内容。

### 第 3 步 · 验（必须是真跑，不许「应该好了」）

```bash
bash ~/.codex-claude-bridge/app/scripts/smoke-test.sh
```

四项全 PASS 才算装好：

```
== Claude Code ==  PASS 对话通 / PASS 能写文件
== Codex       ==  PASS 对话通 / PASS 能写文件
== 汇总 == PASS=4 FAIL=0
```

只有 `doctor.sh` 显示配置齐全**不算**通过——那只证明文件写对了，不证明模型能用。
**能对话 + 真写出文件**，才证明端点、鉴权、工具调用三样都通。

## 二、日常怎么派活

```bash
# Claude Code：长上下文、要读多文件、要配合宿主工具的活
~/.codex-claude-bridge/app/scripts/ask-claude.sh "任务描述" "/绝对/工作目录"

# Codex：仓库级编辑、重构、代码审查
~/.codex-claude-bridge/app/scripts/ask-codex.sh "任务描述" "/绝对/工作目录"
```

- `ask-claude.sh` 默认输出 JSON，读 `result` 字段
- `ask-codex.sh` 只输出 Codex 最后的 agent message，适合直接贴给人看
- 宿主支持 MCP 时优先用工具 `ask_claude` / `ask_codex`，配置在 `~/.codex-claude-bridge/mcp.json`

派活写法（这是效果好坏的分水岭）：

```
✗ 「帮我看看这个项目」
✓ 「只改 src/config.ts 里的 apiBase，改成 https://x.example.com，
   别动其他文件，别加注释，改完把 diff 读回来给我看」
```

写清 **改哪里 / 改成什么 / 不许做什么 / 完成后怎么自证**。
模型不是 Claude 本人时更吃这一套——指令越像工单，越不容易跑偏。

## 三、权限：默认只读，写文件要显式提

| 层级 | Claude Code | Codex |
|---|---|---|
| 默认（安全） | `dontAsk`，不改文件、不跑工具 | `read-only` 沙箱 |
| 允许改文件 | `acceptEdits` | `workspace-write` |
| 全放行（慎用） | `bypassPermissions` | `danger-full-access` |

```bash
CLAUDE_PERMISSION_MODE=acceptEdits bash .../ask-claude.sh "修复测试失败" "/repo"
CODEX_SANDBOX=workspace-write      bash .../ask-codex.sh "修复测试失败" "/repo"
```

第三级必须拿到客户明确同意，并在交付说明里写明风险。默认不要给。

## 四、实测记录（本包已跑通，不是只写在文档里）

2026-11-23，Ubuntu 24.04 / Node 22.22.1，走完整 install → smoke-test 流程：

| 项 | 配置 | 结果 |
|---|---|---|
| Claude Code 2.1.330 | `mimo-v2.6-flash` @ `token-plan-cn.xiaomimimo.com/anthropic` | 对话 1–3s，写文件 PASS |
| Codex CLI 0.171.0 | `deepseek-flash` @ `api.deepseek.com`，`wire_api=responses` | 对话 11s，写文件 PASS |
| 汇总 | 4 项 | 4 PASS / 0 FAIL |

细节与复现命令见 `references/verified-matrix.md`。

## 五、换供应商

```bash
# 任意 Anthropic 兼容端点（Claude Code）
bash scripts/install.sh --claude-provider custom \
  --claude-base-url 'https://your-host/anthropic' \
  --claude-model 'your-model' --claude-key '...' --target generic --yes

# 任意 OpenAI 兼容端点（Codex）
bash scripts/install.sh --codex-provider custom \
  --codex-base-url 'https://your-host/v1' \
  --codex-model 'your-model' --codex-wire-api chat \
  --codex-key '...' --target generic --yes
```

已知可用组合与踩坑见 `references/providers.md`。

## 六、边界（交付时逐条讲给客户）

- **不是免费模型**，费用由客户供应商收取；prompt 与文件内容会发给该供应商。
- 国内模型对工具调用 / 长上下文 / 图片 / thinking 的支持**不一定完整**；
  不支持就换模型或换端点，不要硬扛、不要改客户端源码。
- Claude Desktop 3P 的 **Chat** 跑在 VM 沙箱里，控不了宿主机；
  本包用的是 **Claude Code CLI**（宿主进程），能读写项目文件、能挂 MCP。
- Windows 原生路径见 `references/windows.md`（PowerShell 步骤），
  不必强求客户装 WSL。
- 模型厂条款、地区政策、数据出境与隐私，由客户自行评估。
- 默认只读；不要默认给 full-access。

## 七、卸载

```bash
rm -rf ~/.codex-claude-bridge
rm -rf ~/.workbuddy/skills/codex-claude-bridge
rm -rf ~/.claude/skills/codex-claude-bridge
# 手动删除 ~/.codex/AGENTS.md 里 BEGIN/END codex-claude-bridge 区块
```

## 参考文件

- `references/hosts.md` — 各宿主接入细节 + 零终端宿主的粘贴清单模板
- `references/windows.md` — Windows PowerShell 手工路径（不装 WSL）
- `references/providers.md` — 供应商参数、模型名、可用性
- `references/troubleshooting.md` — 401 / 超时 / 工具调用失败的排查顺序
- `references/security.md` — 密钥存放与数据流
- `references/verified-matrix.md` — 实测矩阵与复现命令
