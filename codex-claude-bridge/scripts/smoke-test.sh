#!/bin/bash
# 装完必跑的验收：两边各说一句话 + 各真写一个文件。
# 四项全过才算装好；任何一项失败按 references/troubleshooting.md 排查，不要反复重装。
set -uo pipefail

BRIDGE_HOME="${CODEX_CLAUDE_BRIDGE_HOME:-$HOME/.codex-claude-bridge}"
B="$BRIDGE_HOME/app/scripts"
CONFIG="$BRIDGE_HOME/config.env"
PASS=0; FAIL=0; SKIP=0
WS="$(mktemp -d "${TMPDIR:-/tmp}/bridge-smoke.XXXXXX")"
trap 'rm -rf "$WS"' EXIT

say()  { printf '%s\n' "$*"; }
ok()   { say "  PASS  $*"; PASS=$((PASS+1)); }
bad()  { say "  FAIL  $*"; FAIL=$((FAIL+1)); }
skip() { say "  SKIP  $*"; SKIP=$((SKIP+1)); }

[ -f "$CONFIG" ] || { say "没装：缺 $CONFIG，先跑 scripts/install.sh"; exit 1; }
# shellcheck disable=SC1090
. "$CONFIG"

say "== 环境 =="
say "  node $(node -v 2>/dev/null || echo '缺失')  python $(python3 -V 2>&1 | cut -d' ' -f2)"
say "  工作目录 $WS"
say ""

# --- Claude Code -------------------------------------------------------------
if [ -n "${CLAUDE_API_KEY:-}" ] && [ -x "${CLAUDE_BIN:-}" ]; then
  say "== Claude Code（${CLAUDE_MODEL} @ ${CLAUDE_BASE_URL}）=="
  T0=$(date +%s)
  OUT="$(CLAUDE_PERMISSION_MODE=dontAsk timeout 180 bash "$B/ask-claude.sh" "只回答两个字：可以" "$WS" 2>&1)"
  RC=$?; DT=$(( $(date +%s) - T0 ))
  if [ $RC -eq 0 ] && printf '%s' "$OUT" | grep -q '可以'; then
    ok "对话通（${DT}s）"
  else
    bad "对话失败 rc=$RC ${DT}s：$(printf '%s' "$OUT" | tail -c 300)"
  fi
  rm -f "$WS/claude-ok.txt"
  CLAUDE_PERMISSION_MODE=acceptEdits timeout 240 \
    bash "$B/ask-claude.sh" "在当前目录创建 claude-ok.txt，内容只写一行 CLAUDE-OK" "$WS" >/dev/null 2>&1
  if [ -s "$WS/claude-ok.txt" ] && grep -q 'CLAUDE-OK' "$WS/claude-ok.txt"; then
    ok "能写文件（acceptEdits 生效）"
  else
    bad "写文件失败：权限模式或工具调用不通"
  fi
else
  skip "Claude Code 未配置（无 key 或无 binary）"
fi
say ""

# --- Codex -------------------------------------------------------------------
if [ -n "${CODEX_API_KEY:-}" ] && [ -x "${CODEX_BIN:-}" ]; then
  say "== Codex（${CODEX_MODEL} @ ${CODEX_BASE_URL} wire=${CODEX_WIRE_API:-responses}）=="
  T0=$(date +%s)
  OUT="$(CODEX_SANDBOX=read-only timeout 240 bash "$B/ask-codex.sh" "只回答两个字：可以" "$WS" 2>&1)"
  RC=$?; DT=$(( $(date +%s) - T0 ))
  if [ $RC -eq 0 ] && printf '%s' "$OUT" | grep -q '可以'; then
    ok "对话通（${DT}s）"
  else
    bad "对话失败 rc=$RC ${DT}s：$(printf '%s' "$OUT" | tail -c 300)"
  fi
  rm -f "$WS/codex-ok.txt"
  CODEX_SANDBOX=workspace-write timeout 300 \
    bash "$B/ask-codex.sh" "在当前目录创建 codex-ok.txt，内容只写一行 CODEX-OK" "$WS" >/dev/null 2>&1
  if [ -s "$WS/codex-ok.txt" ] && grep -q 'CODEX-OK' "$WS/codex-ok.txt"; then
    ok "能写文件（workspace-write 生效）"
  else
    bad "写文件失败：沙箱等级或工具调用不通"
  fi
else
  skip "Codex 未配置（无 key 或无 binary）"
fi

say ""
say "== 汇总 ==  PASS=$PASS  FAIL=$FAIL  SKIP=$SKIP"
if [ $FAIL -gt 0 ]; then
  say "不合格：先看 references/troubleshooting.md，再动配置。不要重装碰运气。"
  exit 1
fi
[ $PASS -gt 0 ] || { say "没有任何一项跑起来，等于没装。"; exit 1; }
say "验收通过：可以交付。"
exit 0
