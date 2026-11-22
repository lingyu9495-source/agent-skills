# 安全与合规

## 密钥

- 只写入 `~/.codex-claude-bridge/config.env` 和
  `~/.codex-claude-bridge/codex-home/auth.json`，权限 600。
- 安装包和 zip 内**不含任何 Key**。
- 不要把 `config.env`、`auth.json` 提交到 Git 或发给别人。
- 建议给供应商 Key 设置预算/限额，泄露后立即轮换。

## 数据流

```text
智能体 -> ask-claude / ask-codex -> 官方 CLI -> 客户选择的模型供应商
```

- prompt、文件内容、工具结果会发给客户选择的供应商。
- 客户版不使用本地网关；CLI 直接 HTTPS 访问供应商。
- Claude Code 的 `CLAUDE_CONFIG_DIR` 和 Codex 的 `CODEX_HOME` 都隔离在桥目录，
  不覆盖客户原有账号/配置。

## 工具权限

- 默认 Claude `dontAsk`、Codex `read-only`。
- 提升到 `acceptEdits` / `workspace-write` 后，子代理可改文件/跑命令。
- `bypassPermissions` / `danger-full-access` 风险极高，必须由用户明确同意。
- 浏览器/MCP 工具可能访问登录态和敏感数据；只装可信 MCP server。

## 供应链

- Claude Code 来自 npm `@anthropic-ai/claude-code`；Codex 来自 npm
  `@openai/codex` 或客户已安装的 ChatGPT.app。
- 建议固定版本、审查更新、保留回滚。
- 本包不修改 Claude.app/Codex.app；不包含中文补丁。

## 条款

- 用官方客户端接第三方模型可能触及厂商条款/地区政策；客户自行评估。
- 本包不提供任何官方支持、SLA 或合规保证。
- 不是“免费使用官方模型”；费用与责任由客户和供应商承担。
