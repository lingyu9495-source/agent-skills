# 供应商配置

## 预设

| CLI | 预设 | Base URL | 默认模型 | Key 环境变量 |
|---|---|---|---|---|
| Claude Code | `mimo` | `https://token-plan-cn.xiaomimimo.com/anthropic` | `mimo-v2.6-flash` | `MIMO_API_KEY` |
| Claude Code | `anthropic` | `https://api.anthropic.com` | `claude-sonnet-4-5` | `ANTHROPIC_API_KEY` |
| Codex | `deepseek` | `https://api.deepseek.com` | `deepseek-flash` | `DEEPSEEK_API_KEY` |
| Codex | `openai` | `https://api.openai.com/v1` | `gpt-5.1-codex` | `OPENAI_API_KEY` |

也可以 `--claude-provider custom` / `--codex-provider custom` 接任意兼容端点。

## Claude Code（Anthropic 兼容）

Claude Code 通过环境变量工作：

```bash
ANTHROPIC_BASE_URL=...
ANTHROPIC_AUTH_TOKEN=...   # 同时写 ANTHROPIC_API_KEY
ANTHROPIC_MODEL=...
```

- MiMo Token Plan 中国区主机已实测直连；`api-key` / `x-api-key` /
  `Authorization: Bearer` 三种头都可 200。
- Claude Code 可能打印 `[claude-code:unrecognized_model]`，只要请求成功即可忽略。
- 若供应商只支持 OpenAI 格式，Claude Code 不能直连；需要 Anthropic 兼容网关
  或换用支持 Anthropic 的供应商。

## Codex（OpenAI 兼容）

Codex 使用独立 `CODEX_HOME`：

```toml
model_provider = "bridge"
model = "deepseek-flash"
forced_login_method = "api"

[model_providers.bridge]
name = "deepseek"
base_url = "https://api.deepseek.com"
wire_api = "responses"
requires_openai_auth = true
```

- `auth.json`：`{"auth_mode":"apikey","OPENAI_API_KEY":"..."}`
- DeepSeek 预设会附带 `models.json` 目录，避免 “Model metadata not found” 警告。
- 只支持 chat/completions 的供应商：加 `--codex-wire-api chat`。
- 模型名必须与供应商实际名称一致。

## 其他国内模型

Kimi、GLM、Qwen、MiniMax 等只要提供 **Anthropic 兼容**或
**OpenAI 兼容**端点，就可以用 `custom` 预设接入。安装前先用 `curl` 验证：

```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  -X POST "$BASE/v1/messages" \
  -H "content-type: application/json" \
  -H "x-api-key: $KEY" \
  -d '{"model":"'$MODEL'","max_tokens":4,"messages":[{"role":"user","content":"hi"}]}'
```

返回 200 再安装；返回 401/404 时先核对 base URL、模型名、鉴权头。

## 兼容性提醒

- 工具调用（tool use）是最容易不兼容的部分；先用简单任务测试。
- 长上下文、图片、thinking、并行工具调用可能降级。
- 费用、限流、数据政策由供应商决定，与本安装包无关。
