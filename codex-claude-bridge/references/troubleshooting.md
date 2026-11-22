# 排错

## Claude Code 401/403

- 检查 `config.env` 的 `CLAUDE_BASE_URL` / `CLAUDE_API_KEY`
- 用 `curl` 直接测 `/v1/messages` 是否 200
- MiMo 用 CN Token Plan 主机，`tp-` Key 不要配到 SGP/AMS 主机
- 确认 key 没有多余空格/引号

## Claude Code `unrecognized_model`

Claude Code 不认识自定义模型名时会打印该警告，但请求仍可能成功。只要输出里
有 `result` 即可忽略；要消除警告可让供应商提供 Claude 角色名，或用兼容网关。

## Codex `Model metadata not found`

DeepSeek 预设会复制 `models.json`；自定义供应商没有 catalog 时会出现此警告，
通常仍可运行，但工具/上下文元数据可能退化。可提供自己的 catalog 或用
`deepseek` 预设。

## Codex 401/404

- `base_url` 是否包含 `/v1`（不同供应商不一样）
- `wire_api` 是否匹配：Responses 用 `responses`，Chat Completions 用 `chat`
- `auth.json` 是否存在、600、`OPENAI_API_KEY` 正确
- 模型名是否真实存在

## Node/npm 找不到

- 安装 Node 18+；或设置 `NODE_BIN=/path/to/node`
- WorkBuddy 客户可用自带 Node：
  `~/.workbuddy/binaries/node/versions/<version>/bin`
- `npm install` 失败时检查网络/代理；也可用 `--claude-bin` / `--codex-bin`
  指向已安装的二进制

## MCP 客户端看不到工具

- 确认 `mcp.json` 的 `args` 指向真实 `server.py`
- 用 `python3 server.py` 手动发 `initialize`/`tools/list` 测试
- server 的日志只写 stderr；stdout 必须是 JSON-RPC
- 客户端需要支持 stdio MCP

## 超时

- 默认 900s；设置 `CODEX_CLAUDE_BRIDGE_TIMEOUT` 调整
- 大仓库/长任务建议拆分，避免一次塞太多上下文

## Windows

原生 Windows 未测试；建议 WSL。macOS/Linux 是主要支持平台。
