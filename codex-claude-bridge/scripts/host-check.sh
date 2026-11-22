#!/bin/bash
# 先探清这台机器 / 这个宿主能走哪条路：代装、给粘贴清单、还是走 MCP。
# 只读探测，不改任何东西。
set -uo pipefail

OS="$(uname -s 2>/dev/null || echo unknown)"
NODE="$(command -v node 2>/dev/null || true)"
NPM="$(command -v npm 2>/dev/null || true)"
PY="$(command -v python3 2>/dev/null || true)"
CLAUDE="$(command -v claude 2>/dev/null || true)"
CODEX="$(command -v codex 2>/dev/null || true)"
NET="down"

if [ -n "$NPM" ]; then
  if timeout 15 curl -s -o /dev/null -w '' --max-time 12 https://registry.npmmirror.com/ 2>/dev/null; then NET="ok"; fi
fi

NODE_V="$([ -n "$NODE" ] && "$NODE" -v 2>/dev/null || echo '-')"
say() { printf '%s\n' "$*"; }

say "== 这台机器 =="
say "  系统      : $OS"
say "  node      : ${NODE:-未装} $NODE_V"
say "  npm       : ${NPM:-未装}"
say "  python3   : ${PY:-未装}"
say "  claude    : ${CLAUDE:-未装}"
say "  codex     : ${CODEX:-未装}"
say "  npm 源    : $NET"
say ""

MODE="paste"
if [ -n "$NODE" ] && [ -n "$NPM" ] && [ -n "$PY" ] && [ "$NET" = "ok" ]; then
  MODE="auto"
elif [ -n "$NODE" ] && [ -n "$NPM" ] && [ -n "$PY" ]; then
  MODE="auto-slow"   # 能装，但 npm 源慢，建议先换 npmmirror
fi

say "== 结论 =="
case "$MODE" in
  auto)
    say "  走「代装」：AI 可以自己跑 install.sh，装完跑 smoke-test.sh 验收。"
    ;;
  auto-slow)
    say "  走「代装（先换源）」：npm 源访问不顺，先执行："
    say "    npm config set registry https://registry.npmmirror.com"
    ;;
  *)
    say "  走「粘贴清单」：这台机器缺 node/npm/python3，AI 代装会失败。"
    say "  先把缺的东西补上（装 Node.js 18+ 与 Python 3），再回来跑本脚本。"
    ;;
esac
say ""
say "宿主侧提醒（详细见 references/hosts.md）："
say "  · 能跑 shell 的智能体（Hermes / QwenPaw / WorkBuddy / Claude Code / Codex）→ 代装"
say "  · 网页版助手（豆包 / Kimi / 网页 ChatGPT）→ 只能给命令清单让客户粘贴"
say "  · 支持 MCP 的客户端 → 装完接 mcp.json，用 ask_claude / ask_codex 工具"
exit 0
