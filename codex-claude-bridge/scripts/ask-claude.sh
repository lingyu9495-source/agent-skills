#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DERIVED_HOME="$(cd "$SCRIPT_DIR/../.." && pwd)"
BRIDGE_HOME="${CODEX_CLAUDE_BRIDGE_HOME:-$DERIVED_HOME}"
CONFIG="$BRIDGE_HOME/config.env"
[ -f "$CONFIG" ] || { echo "Bridge not installed: $CONFIG" >&2; exit 1; }
# shellcheck disable=SC1090
source "$CONFIG"
[ -n "${CLAUDE_API_KEY:-}" ] || { echo "Claude Code not configured (no key)" >&2; exit 1; }
[ -n "${CLAUDE_BIN:-}" ] && [ -x "$CLAUDE_BIN" ] || { echo "Claude Code binary missing; rerun install.sh" >&2; exit 1; }
PROMPT="${1:?usage: ask-claude.sh <prompt> [cwd]}"
CWD="${2:-$PWD}"
mkdir -p "$BRIDGE_HOME/claude-home"
export CLAUDE_CONFIG_DIR="$BRIDGE_HOME/claude-home"
export ANTHROPIC_BASE_URL="$CLAUDE_BASE_URL"
export ANTHROPIC_AUTH_TOKEN="$CLAUDE_API_KEY"
export ANTHROPIC_API_KEY="$CLAUDE_API_KEY"
export ANTHROPIC_MODEL="$CLAUDE_MODEL"
export ANTHROPIC_DEFAULT_SONNET_MODEL="$CLAUDE_MODEL"
export ANTHROPIC_DEFAULT_OPUS_MODEL="$CLAUDE_MODEL"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="$CLAUDE_MODEL"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export DISABLE_TELEMETRY=1
ARGS=(-p "$PROMPT" --output-format "${CLAUDE_OUTPUT_FORMAT:-json}" --permission-mode "${CLAUDE_PERMISSION_MODE:-dontAsk}")
[ -n "${CLAUDE_MCP_CONFIG:-}" ] && ARGS+=(--mcp-config "$CLAUDE_MCP_CONFIG")
cd "$CWD"
if [ "${CLAUDE_OUTPUT_FORMAT:-json}" = "json" ]; then
  OUT=$(mktemp "${TMPDIR:-/tmp}/claude-bridge.XXXXXX")
  ERR=$(mktemp "${TMPDIR:-/tmp}/claude-bridge-err.XXXXXX")
  trap 'rm -f "$OUT" "$ERR"' EXIT
  set +e
  "$CLAUDE_BIN" "${ARGS[@]}" >"$OUT" 2>"$ERR"
  rc=$?
  set -e
  python3 - "$OUT" <<'PY'
import json, sys
s = open(sys.argv[1], encoding="utf-8", errors="replace").read()
i = s.find("{")
if i >= 0:
    candidate = s[i:].strip()
    try:
        json.loads(candidate)
        sys.stdout.write(candidate + "\n")
        raise SystemExit(0)
    except SystemExit:
        raise
    except Exception:
        pass
sys.stdout.write(s)
PY
  [ -s "$ERR" ] && cat "$ERR" >&2
  exit "$rc"
fi
exec "$CLAUDE_BIN" "${ARGS[@]}"
