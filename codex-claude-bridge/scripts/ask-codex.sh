#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DERIVED_HOME="$(cd "$SCRIPT_DIR/../.." && pwd)"
BRIDGE_HOME="${CODEX_CLAUDE_BRIDGE_HOME:-$DERIVED_HOME}"
CONFIG="$BRIDGE_HOME/config.env"
[ -f "$CONFIG" ] || { echo "Bridge not installed: $CONFIG" >&2; exit 1; }
# shellcheck disable=SC1090
source "$CONFIG"
[ -n "${CODEX_API_KEY:-}" ] || { echo "Codex not configured (no key)" >&2; exit 1; }
[ -n "${CODEX_BIN:-}" ] && [ -x "$CODEX_BIN" ] || { echo "Codex binary missing; rerun install.sh" >&2; exit 1; }
PROMPT="${1:?usage: ask-codex.sh <prompt> [cwd]}"
CWD="${2:-$PWD}"
export CODEX_HOME="$BRIDGE_HOME/codex-home"
TMP=$(mktemp "${TMPDIR:-/tmp}/codex-bridge.XXXXXX")
trap 'rm -f "$TMP"' EXIT
cd "$CWD"
"$CODEX_BIN" exec --json --skip-git-repo-check -s "${CODEX_SANDBOX:-read-only}" -C "$CWD" "$PROMPT" >"$TMP" 2>/dev/null || true
python3 - "$TMP" <<'PY'
import json, sys
last=None
raw=[]
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    raw.append(line)
    try: e=json.loads(line)
    except Exception: continue
    if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message':
        last=e['item'].get('text')
print(last if last is not None else ''.join(raw)[-4000:])
PY
