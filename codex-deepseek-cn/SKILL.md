---
slug: codex-deepseek-cn
displayName: Codex 国内模型桥 · DeepSeek
version: 1.0.0
summary: 用 DeepSeek 或任意 OpenAI 兼容端点的 Key 驱动本机官方 Codex CLI，不需要 OpenAI 账号。豆包/WorkBuddy/Hermes/QwenPaw/龙虾(OpenClaw/LobeChat)/Cursor 等智能体可代为部署、代为派活。
license: MIT
name: codex-deepseek-cn
description: 让智能体在客户本机安装 Codex CLI 并接到 DeepSeek（或任意 OpenAI 兼容端点），免 OpenAI 账号、免翻墙；支持只读审查与可写改码两档权限。当用户说「用 Codex 做」「装个 Codex」「接 DeepSeek 写代码」时使用。
author: 九品锦里e
tags: [codex, deepseek, 国内模型, 智能体部署, 编程]
---

# Codex 国内模型桥（DeepSeek）

把官方 **Codex CLI** 接到客户自己的 **DeepSeek** Key 上，不需要 OpenAI 账号、不需要梯子，
`~/.codex` 原有配置一行不动。

**它解决什么**：客户机器上没有 Codex，也没有 OpenAI 账号，但想有一个能读仓库、改代码、
跑测试的代码智能体。装完以后任何有 shell 的智能体都能给它派活。

**它不是**：不是免费使用 GPT 模型。费用由 DeepSeek（或客户选的其他供应商）按量收取。
也不是 IDE 插件，它是命令行 agent，靠文件系统工作。

---

## 一、装之前先问清三件事

1. **宿主是谁**（决定「代装」还是「出清单」）

| 宿主 | 能代装吗 | 说明 |
|---|---|---|
| Hermes / WorkBuddy / QwenPaw / 老舟(OpenClaw) | 能 | 有 shell，照第三节直接跑 |
| 龙虾（LobeChat / OpenClaw 桌面版） | 看版本 | 有 MCP 就能用；没有 shell 就只能出清单 |
| 豆包 / Kimi / 网页版助手 | 不能 | 只能输出命令清单，客户自己粘贴执行 |
| Cursor / 任意 MCP 客户端 | 能接 | 挂 `mcp.json`，用 `ask_codex` 工具 |

判断方法：让宿主跑一句 `node -v`。返回版本号＝有执行能力；答「我无法访问你的电脑」＝没能力。

2. **客户有 Key 吗**：DeepSeek 的 `sk-...`。没有 Key 就别装，装了也跑不通。
3. **客户要 Codex 干什么**：只审查（读）还是要改代码（写）？这决定权限档位，见第六节。

---

## 二、客户机器要求

- macOS / Linux（Windows 走 WSL）
- **Node.js 18+**（装了 WorkBuddy 的机器自带一份 Node，安装脚本会自动找）
- Python 3（解析 Codex 的 JSON 输出用）
- 一个 DeepSeek Key，或任意 OpenAI 兼容端点的 Key

**不需要**：OpenAI 账号、梯子、本地模型、显卡。

> 机器上没装过 Codex 也没关系，安装脚本会 npm 装到 `~/.codex-claude-bridge/codex-cli/`，
> 不污染全局。已经装过的它会自动定位，或用 `--codex-bin /path/to/codex` 指过去。

---

## 三、安装（只装 Codex 这一侧）

```bash
unzip codex-claude-bridge-portable.zip
cd codex-claude-bridge-portable

DEEPSEEK_API_KEY='sk-...' \
bash scripts/install.sh --target generic --no-install-claude --yes
```

安装器实际做了四件事：

1. npm 安装或定位 Codex → `~/.codex-claude-bridge/codex-cli/`
2. 写独立 `CODEX_HOME=~/.codex-claude-bridge/codex-home`，**不碰客户的 `~/.codex`**
3. 生成 `config.toml`（`model_provider=bridge`、`model=deepseek-flash`、`wire_api=responses`）
   与 `models.json`（避免 "Model metadata not found" 警告）
4. 写 `config.env`（Key 在里面，权限 600）并生成 `mcp.json`

**Key 处理铁律**：客户自己粘贴进命令或环境变量；智能体**不要**把 Key 复述到聊天、
日志、截图、交付文档里。装完只在 `config.env` 出现一次，`mask()` 打印时也只显示头尾。

### 换成别家（Kimi / GLM / Qwen / 自建网关）

只要对方给 **OpenAI 兼容**端点（`/v1/chat/completions` 或 `/v1/responses`）：

```bash
bash scripts/install.sh --target generic --no-install-claude --yes \
  --codex-provider custom \
  --codex-base-url 'https://your-host/v1' \
  --codex-model 'your-model' \
  --codex-wire-api chat \
  --codex-key 'sk-...'
```

`wire_api` 怎么选：供应商支持 `/v1/responses` 用 `responses`；**只支持
`/v1/chat/completions` 就必须写 `chat`**，否则 404。拿不准时先 curl 一发：

```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  -X POST "$BASE/chat/completions" \
  -H "authorization: Bearer $KEY" -H 'content-type: application/json' \
  -d '{"model":"'"$MODEL"'","messages":[{"role":"user","content":"hi"}],"max_tokens":4}'
```

200 再装。401＝Key 错，404＝路径或模型名错。

---

## 四、自检（装完必跑，不许「应该好了」）

```bash
bash ~/.codex-claude-bridge/app/scripts/doctor.sh
```

看 `codex:` 那一行有没有版本号、`config: ok (600)` 是否成立。然后冒烟：

```bash
bash ~/.codex-claude-bridge/app/scripts/ask-codex.sh "只回答：OK"
```

三分钟内必须回 `OK`。回空、超时、报 401，先查第七节，不要反复重装。

---

## 五、日常派活

```bash
# 只读审查（默认，安全）
~/.codex-claude-bridge/app/scripts/ask-codex.sh "审查这个仓库最近的改动，列出风险点" "/abs/repo"

# 允许改文件 + 跑命令
CODEX_SANDBOX=workspace-write \
  ~/.codex-claude-bridge/app/scripts/ask-codex.sh "修复测试失败" "/abs/repo"
```

- 第二个参数是工作目录，**必须给绝对路径**，Codex 只在这个目录里干活
- 脚本内部用 `codex exec --json`，只取最后一条 `item.completed / agent_message`，
  中间的工具调用日志全部丢掉；拿不到结构化输出时回退最后 4000 字符
- `--skip-git-repo-check` 已开，非 git 目录也能跑

**好用的四类任务**（都是实测场景）：

| 场景 | 提示词骨架 |
|---|---|
| 代码审查 | 「只读。审查 <路径> 的改动，按 严重/中等/建议 三档列问题，每条给文件:行号」 |
| 修测试 | 「跑 <测试命令>，修到全绿，不要改测试断言」 |
| 批量重构 | 「把 <模式 A> 改成 <模式 B>，只改 <范围>，改完给我 diff 概要」 |
| 接手陌生代码 | 「先读 README 与入口文件，画出调用链，再回答 <问题>」 |

---

## 六、权限三档

| 档位 | 命令 | 后果 |
|---|---|---|
| 只读（默认） | `CODEX_SANDBOX=read-only` | 能读能分析，不能写文件、不能跑写命令 |
| 可写 | `CODEX_SANDBOX=workspace-write` | 能改工作目录内文件、跑命令 |
| 全放行 | `CODEX_SANDBOX=danger-full-access` | 能碰工作目录外的任何东西 |

前两档可以直接用。**第三档必须客户明确同意**，并在交付说明里写明风险；不要替客户默认打开。

---

## 七、故障排查

| 症状 | 先查 |
|---|---|
| 401 / unauthorized | Key 是否写进了 `config.env`；供应商是否要求 `Bearer` |
| 404 model / not found | 模型名与供应商实际名称不一致；或 `wire_api` 该用 `chat` |
| Model metadata not found（警告） | 预置 `models.json` 没被读到，确认 `CODEX_HOME` 指向 bridge 目录 |
| 输出为空 | Codex 把错误写到了 stderr；手工跑一次 `codex exec --json ... 2>&1` 看真因 |
| 超时 | 任务太大，拆小；或供应商限流 |
| 工具调用失败 / 不执行 | 该模型不支持 function calling 或细节不兼容，换模型再试 |

规则：**同一个错第二次修不好就换模型或换端点**，别在同一处反复重装。

---

## 八、接到各宿主

**Hermes**：把本目录拷进 skills 目录，SKILL.md 常驻；需要跑时用 shell 调 `ask-codex.sh`。

**WorkBuddy**：`--target workbuddy` 会把说明写到 `~/.workbuddy/skills/`，刷新后直接说「用 Codex 做这个」。

**QwenPaw**：技能格式不同，把本文当手册，用 shell 执行同样的命令。

**龙虾（LobeChat / OpenClaw）**：走 MCP。把下面这段加进客户端的 MCP 配置：

```json
{
  "mcpServers": {
    "codex-bridge": {
      "command": "python3",
      "args": ["/Users/you/.codex-claude-bridge/app/mcp/server.py"]
    }
  }
}
```

客户端里即出现 `ask_codex(prompt, cwd?, sandbox?)` 工具，直接用自然语言派活。

**Cursor / 其他 MCP 客户端**：同上，路径改成客户机器的实际路径。

---

## 九、边界（对客户必须讲）

- 不是「免费使用 GPT」：用的是客户自己的 DeepSeek/其他供应商 Key，按量计费。
- 国内模型对工具调用、长上下文、图片、thinking 的支持**不一定完整**，以实际测试为准。
- prompt 与读到的文件内容会发给客户选择的供应商，敏感仓库先问清能不能出网。
- 只做本地开发辅助，不承诺官方支持、SLA、合规意见。
- 默认只读；不要给客户默认开 `danger-full-access`。

## 十、卸载

```bash
rm -rf ~/.codex-claude-bridge
rm -rf ~/.workbuddy/skills/codex-claude-bridge
# 若曾写 ~/.codex/AGENTS.md，删除其中 BEGIN/END codex-claude-bridge 区块
```

## 参考

- `references/providers.md` — 预设参数与 curl 验活
- `references/security.md` — 密钥落盘位置与数据流
- `references/troubleshooting.md` — 更细的报错对照
- `README.md` — 完整包说明（含 Claude Code 一侧，本技能用不到可忽略）
