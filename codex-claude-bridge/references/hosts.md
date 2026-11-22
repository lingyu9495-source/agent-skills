# 各宿主怎么接（一个技能包，五种接法）

技能本体只有一份：`SKILL.md` + `scripts/` + `mcp/`。
差别只在「放在哪、用什么方式让智能体触发」。先分清宿主有没有本机执行能力。

## 判据

```bash
node -v        # 有返回值 = 这台机器能跑 CLI
```

- 能返回值：这个智能体可以**代装**，也可以**代跑**。
- 不能返回值 / 回「我无法访问你的电脑」：这个智能体只能**出粘贴清单**。

## 1. Hermes

- 放到 `~/.hermes/profiles/<profile>/skills/codex-claude-bridge/`
- 或直接在对话里让它照本文执行（Hermes 有 terminal 工具）
- 长期用法：装好后把 `ccc` 之类的包装器加入 PATH，让主脑只负责派活和验收

注意：Hermes 起子代理跑长任务时，子代理退出会连带杀子进程。
超过 60 分钟的执行活，走 cron 或 `terminal(background=True)`，别塞在委派里。

## 2. WorkBuddy

```bash
bash scripts/install.sh --target workbuddy --yes
# 写入 ~/.workbuddy/skills/codex-claude-bridge/SKILL.md
```

刷新 / 重启 WorkBuddy 后，直接说「用 Claude Code 做这个」「用 Codex 改这个仓库」。

## 3. QwenPaw

QwenPaw 的技能库格式与 SKILL.md 不完全一致。两种接法：

- 把本目录当**操作手册**：让 QwenPaw 按 SKILL.md 的步骤跑 shell（它宿主机有 shell 时可用）
- 或只接 MCP：把 `mcp.json` 加进 QwenPaw 的 MCP 配置，之后只有两个工具 `ask_claude` / `ask_codex`

## 4. Claude Code / Codex 自己

```bash
bash scripts/install.sh --target claude --yes     # 注册到 ~/.claude/skills/
bash scripts/install.sh --target codex  --yes     # 追加 ~/.codex/AGENTS.md
```

两者可以互相调用：Claude Code 里说「用 Codex 做代码审查」，反之亦然。

## 5. 任意 MCP 客户端（Cursor / Cherry Studio / 自研）

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

## 6. 没有 shell 的宿主（豆包桌面 / Kimi / 网页助手）

这类助手**装不了**，只能当「出题人 + 讲解人」。给它一份粘贴清单，客户自己贴。
清单必须满足三条：**一次一条命令、每条能独立判断成败、失败停不要把后面的一起贴。**

模板：

```
第 1 步（装 Node，只需一次）
  node -v
  成功的样子：v18.x.x 或更高
  失败：去 https://nodejs.org 下 LTS 装完，重开终端再试

第 2 步（装两个 CLI）
  npm install -g @anthropic-ai/claude-code @openai/codex --registry=https://registry.npmmirror.com
  成功的样子：两条 added N packages，没有 ERR!
  失败：把最后 5 行发我

第 3 步（设后端，把 tp-... 换成你自己的 key）
  export ANTHROPIC_BASE_URL=https://token-plan-cn.xiaomimimo.com/anthropic
  export ANTHROPIC_AUTH_TOKEN=tp-...
  export ANTHROPIC_MODEL=mimo-v2.6-flash

第 4 步（验证）
  claude -p "只回答两个字：可以"
  成功的样子：出现「可以」
```

要点：
- **不要让客户在聊天框里贴 key**。让他粘进终端即可；助手不要复述。
- Windows 客户把 `export` 换成 `$env:`，见 `references/windows.md`。
- 客户每步回来只贴「最后几行 + 有没有报错」，不要让他整屏贴。

## 常见判断错误

| 现象 | 真相 |
|---|---|
| 智能体说「我帮你装好了」但没跑过命令 | 没有 shell 的宿主在编答案。要它贴命令输出。 |
| 智能体让你把 key 发给它 | 不该发生。key 只进客户自己的终端。 |
| 装完只说「配置正确」 | 那只证明文件对了。要它跑 `smoke-test.sh`。 |
