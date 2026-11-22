#!/bin/bash
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DERIVED_HOME="$(cd "$SCRIPT_DIR/../.." && pwd)"
BRIDGE_HOME="${CODEX_CLAUDE_BRIDGE_HOME:-$DERIVED_HOME}"
CONFIG="$BRIDGE_HOME/config.env"
echo "== bridge =="
echo "home: $BRIDGE_HOME"
if [ -f "$CONFIG" ]; then
  # shellcheck disable=SC1090
  source "$CONFIG"
  echo "config: ok (600)"
  echo "claude: ${CLAUDE_PROVIDER:-?} ${CLAUDE_BASE_URL:-?} ${CLAUDE_MODEL:-?} key=${CLAUDE_API_KEY:+set}"
  echo "codex:  ${CODEX_PROVIDER:-?} ${CODEX_BASE_URL:-?} ${CODEX_MODEL:-?} key=${CODEX_API_KEY:+set}"
else
  echo "config: MISSING ($CONFIG)"
fi
echo "== binaries =="
if [ -n "${CLAUDE_BIN:-}" ] && [ -x "$CLAUDE_BIN" ]; then echo "claude: $("$CLAUDE_BIN" --version 2>&1 | head -1) ($CLAUDE_BIN)"; else echo "claude: missing"; fi
if [ -n "${CODEX_BIN:-}" ] && [ -x "$CODEX_BIN" ]; then echo "codex:  $("$CODEX_BIN" --version 2>&1 | head -1) ($CODEX_BIN)"; else echo "codex:  missing"; fi
echo "== mcp =="
[ -f "$BRIDGE_HOME/mcp.json" ] && echo "mcp.json: ok" || echo "mcp.json: missing"
[ -f "$BRIDGE_HOME/app/mcp/server.py" ] && echo "server.py: ok" || echo "server.py: missing"
echo "== smoke (optional) =="
echo "  bash $BRIDGE_HOME/app/scripts/ask-claude.sh \"只回答：OK\""
echo "  bash $BRIDGE_HOME/app/scripts/ask-codex.sh \"只回答：OK\""
