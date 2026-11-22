---
slug: claude-code-mimo-cn
displayName: Claude Code 国内模型桥 · MiMo
version: 1.0.0
summary: 用 MiMo Token Plan 或任意 Anthropic 兼容端点的 Key 驱动本机官方 Claude Code CLI，不需要 Anthropic 账号、不用梯子。支持 MCP 挂浏览器/工具，豆包/WorkBuddy/Hermes/QwenPaw/龙虾(OpenClaw/LobeChat)/Cursor 均可代部署或经 MCP 调用。
license: MIT
name: claude-code-mimo-cn
description: 让智能体在客户本机安装 Claude Code CLI 并接到 MiMo（或任意 Anthropic 兼容端点），免 Anthropic 账号、免翻墙，可挂 MCP 使用浏览器与本地工具。当用户说「用 Claude Code 做」「装 Claude Code」「接国内模型跑 Claude」时使用。
author: 九品锦里e
tags: [claude-code, mimo, 国内模型, 智能体部署, mcp]
---

# Claude Code 国内模型桥（MiMo）

把官方 **Claude Code CLI** 接到客户自己的 **MiMo Token Plan** Key 上，
不需要 Anthropic 账号、不用梯子，`~/.claude` 原有配置一行不动。

**它解决什么**：客户想用 Claude Code 那套「能读整个仓库、能调工具、能挂 MCP 浏览器」的
工作方式，但没有 Anthropic 账号、也没有海外支付手段。Claude Code 只认 Anthropic 格式的
接口，MiMo（及国内若干家）提供了兼容端点，于是本地就能跑。

**它不是**：不是免费使用 Claude 模型。也不是 Claude Desktop——桌面版的 3P Chat 跑在
VM 沙箱里，控制不了宿主机文件与工具；本技能用的是 **Claude Code CLI**，跑在宿主机上。

---

## 一、装之前先确认两件事

1. **宿主能不能动手**（决定「代装」还是「出清单」）

| 宿主 | 能代装吗 | 说明 |
|---|---|---|
| Hermes / WorkBuddy / QwenPaw / 老舟(OpenClaw) | 能 | 有 shell，照第三节跑 |
| 龙虾（LobeChat / OpenClaw 桌面版） | 看版本 | 能挂 MCP 就能用；无 shell 只出清单 |
| 豆包 / Kimi / 网页版助手 | 不能 | 只能给命令清单，客户自己粘贴 |
| Cursor / 任意 MCP 客户端 | 能接 | 挂 `mcp.json` 用 `ask_claude` |

让宿主跑 `node -v`：有版本号＝能代装；答「我无法访问你的电脑」＝只出清单。

2. **客户有 Anthropic 兼容的 Key 吗**：MiMo 的 `tp-...`。注意只有
   **Anthropic 兼容**的端点能接 Claude Code；只给 OpenAI 格式的供应商接不了。

---

## 二、客户机器要求

- macOS / Linux（Windows 走 WSL）
- **Node.js 18+**
- Python 3（解析 JSON 输出）
- 一个 MiMo Key，或任意 Anthropic 兼容端点

**不需要**：Anthropic 账号、海外信用卡、梯子、Claude Desktop 中文补丁。

> 没装过 Claude Code 也没关系，脚本会 npm 装到 `~/.codex-claude-bridge/claude-cli/`。
> 已装过的用 `--claude-bin /path/to/claude` 指过去。

---

## 三、安装（只装 Claude Code 这一侧）

```bash
unzip codex-claude-bridge-portable.zip
cd codex-claude-bridge-portable

MIMO_API_KEY='tp-...' \
bash scripts/install.sh --target generic --no-install-codex --yes
```

安装器做了四件事：

1. npm 安装或定位 Claude Code → `~/.codex-claude-bridge/claude-cli/`
2. 写独立 `CLAUDE_CONFIG_DIR=~/.codex-claude-bridge/claude-config`，**不碰客户 `~/.claude`**
3. 写三个环境变量：`ANTHROPIC_BASE_URL`、`ANTHROPIC_AUTH_TOKEN`（同时写
   `ANTHROPIC_API_KEY`）、`ANTHROPIC_MODEL`，全部落在 `config.env`（600）
4. 生成 `mcp.json` 与 `config.env`

MiMo 预设：

| 项 | 值 |
|---|---|
| Base URL | `https://token-plan-cn.xiaomimimo.com/anthropic` |
| 默认模型 | `mimo-v2.6-flash` |
| Key 环境变量 | `MIMO_API_KEY` |

> MiMo 中国区主机实测直连，`api-key` / `x-api-key` / `Authorization` 三种头都能 200。
> Claude Code 可能打印 `[claude-code:unrecognized_model]`，**只要请求成功就可以忽略**。

**Key 处理铁律**：客户自己粘贴；智能体不复述 Key 到聊天、日志、截图。

### 换成别家（任意 Anthropic 兼容）

```bash
bash scripts/install.sh --target generic --no-install-codex --yes \
  --claude-provider custom \
  --claude-base-url 'https://your-host/anthropic' \
  --claude-model 'your-model' \
  --claude-key 'sk-...'
```

装前先验活：

```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  -X POST "$BASE/v1/messages" \
  -H 'content-type: application/json' -H "x-api-key: $KEY" \
  -d '{"model":"'"$MODEL"'","max_tokens":4,"messages":[{"role":"user","content":"hi"}]}'
```

200 再装。401＝Key，404＝base URL 或模型名。**只给 OpenAI 格式的供应商必须换网关**，
Claude Code 不能直连 OpenAI 端点。

---

## 四、自检（装完必跑）

```bash
bash ~/.codex-claude-bridge/app/scripts/doctor.sh
bash ~/.codex-claude-bridge/app/scripts/ask-claude.sh "只回答：OK"
```

`ask-claude.sh` 默认输出 JSON，取 `result` 字段：

```bash
bash ~/.codex-claude-bridge/app/scripts/ask-claude.sh "只回答：OK" | python3 -c "import sys,json;print(json.load(sys.stdin).get('result'))"
```

五分钟内要回 `OK`。不回先看第七节，别重装。

---

## 五、日常派活

```bash
# 只读（默认 dontAsk，不改文件不跑工具）
~/.codex-claude-bridge/app/scripts/ask-claude.sh "读这个仓库，说明它是干什么的，指出三个风险" "/abs/repo"

# 允许改文件
CLAUDE_PERMISSION_MODE=acceptEdits \
  ~/.codex-claude-bridge/app/scripts/ask-claude.sh "把这些测试补到覆盖率 80%" "/abs/repo"

# 挂 MCP（浏览器 / 数据库 / 内部工具）
CLAUDE_MCP_CONFIG=/path/mcp.json \
  ~/.codex-claude-bridge/app/scripts/ask-claude.sh "打开登录页，走一遍注册流程并截图" "/abs/workspace"
```

适合它的活：长文档/多文件通读、跨文件重构、要调浏览器或外部工具的流程、
需要「看完整上下文再答」的分析。短平快的单文件改写用 Codex 更省。

---

## 六、权限三档

| 档位 | 变量 | 后果 |
|---|---|---|
| 默认 | `CLAUDE_PERMISSION_MODE=dontAsk` | 只读，不改文件、不自动批准工具 |
| 可写 | `CLAUDE_PERMISSION_MODE=acceptEdits` | 自动接受文件编辑 |
| 全放行 | `CLAUDE_PERMISSION_MODE=bypassPermissions` | 不再询问任何权限 |

前两档可直接用。**第三档必须客户明确同意**并写进交付说明；不要替客户开。

注意口径：`acceptEdits` 只放宽「改文件」，不等于「随便跑命令」；需要跑命令时仍会给用户提示
（取决于 Claude Code 版本），别对客户承诺「全自动」。

---

## 七、故障排查

| 症状 | 先查 |
|---|---|
| 401 / invalid_api_key | Key 有没有写进 `config.env`；`ANTHROPIC_AUTH_TOKEN` 与 `ANTHROPIC_API_KEY` 是否都写 |
| 404 / not_found | base URL 少了 `/anthropic` 前缀；或模型名不对 |
| `unrecognized_model` 警告但能出结果 | 正常，模型名不在官方清单里，忽略 |
| 请求挂住不动 | 供应商限流或端点不通；curl 验活一次 |
| 工具调用被拒 / 不执行 | `dontAsk` 下不会自动批准，改用 `acceptEdits` 或明确授权 |
| MCP 工具不出现 | `CLAUDE_MCP_CONFIG` 路径错或 JSON 格式错，`python3 -m json.tool` 校验一次 |
| 乱码 / 中文断行 | 终端 locale，`export LANG=zh_CN.UTF-8` 再跑 |

同一个错第二次修不好就换端点或换模型，别在同一处反复试。

---

## 八、接到各宿主

**Hermes**：拷进 skills 目录常驻；用 shell 调 `ask-claude.sh`。

**WorkBuddy**：`--target workbuddy` 写 `~/.workbuddy/skills/codex-claude-bridge/SKILL.md`，刷新后说「用 Claude Code 做」。

**QwenPaw**：技能格式不同，把本文当手册走 shell。

**龙虾（LobeChat / OpenClaw）**：走 MCP 接入，配置：

```json
{
  "mcpServers": {
    "claude-bridge": {
      "command": "python3",
      "args": ["/Users/you/.codex-claude-bridge/app/mcp/server.py"]
    }
  }
}
```

出现 `ask_claude(prompt, cwd?, permission_mode?, mcp_config?)` 工具即可用。

**Cursor / 其他 MCP 客户端**：同上，路径换成本机实际路径。

---

## 九、和 Claude Desktop 的区别（客户最容易问）

| | Claude Desktop 3P | 本技能的 Claude Code CLI |
|---|---|---|
| 位置 | 跑在 VM 沙箱里 | 跑在宿主机 |
| 能否读写客户文件 | 不能 | 能（在指定目录内） |
| 能否挂 MCP 用浏览器 | 受限 | 能 |
| 能否接 Anthropic 兼容端点 | 部分版本可以 | 能，靠环境变量 |

所以客户问「我装了 Claude 桌面版是不是就够了」——不够，要的是 **Claude Code CLI**。

## 十、边界

- 不是免费使用 Claude：费用由客户自己的供应商按量收取。
- 国内模型对长上下文、图片、thinking、并行工具调用支持不齐，复杂任务先小样本试。
- prompt 与读到的文件内容会发给客户选的供应商；敏感代码先确认能否出网。
- 不承诺官方支持、SLA、合规意见；模型厂条款与数据政策由客户自行评估。
- 默认只读，不要给客户默认开全放行。

## 十一、卸载

```bash
rm -rf ~/.codex-claude-bridge
rm -rf ~/.workbuddy/skills/codex-claude-bridge
rm -rf ~/.claude/skills/codex-claude-bridge
# 若曾写 ~/.codex/AGENTS.md，删除 BEGIN/END codex-claude-bridge 区块
```

## 参考

- `references/providers.md` — 预设、curl 验活、兼容性
- `references/security.md` — 密钥落盘与数据流
- `references/troubleshooting.md` — 细报错对照
- `README.md` — 完整包说明（含 Codex 一侧，本技能用不到可忽略）
