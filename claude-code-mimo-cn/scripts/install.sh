#!/bin/bash
set -euo pipefail

# Codex + Claude Code portable bridge installer.
# Bring your own domestic model key; no Anthropic/OpenAI account required.

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRIDGE_HOME="${CODEX_CLAUDE_BRIDGE_HOME:-$HOME/.codex-claude-bridge}"
TARGET="${BRIDGE_TARGET:-generic}"
SKILLS_ROOT="${SKILLS_ROOT:-$HOME}"
ASSUME_YES=0
INSTALL_CLAUDE=1
INSTALL_CODEX=1

CLAUDE_PROVIDER="${CLAUDE_PROVIDER:-mimo}"
CODEX_PROVIDER="${CODEX_PROVIDER:-deepseek}"
CLAUDE_BASE_URL="${CLAUDE_BASE_URL:-}"
CLAUDE_MODEL="${CLAUDE_MODEL:-}"
CLAUDE_API_KEY="${CLAUDE_API_KEY:-${ANTHROPIC_API_KEY:-${MIMO_API_KEY:-}}}"
CODEX_BASE_URL="${CODEX_BASE_URL:-}"
CODEX_MODEL="${CODEX_MODEL:-}"
CODEX_API_KEY="${CODEX_API_KEY:-${OPENAI_API_KEY:-${DEEPSEEK_API_KEY:-}}}"
CODEX_WIRE_API="${CODEX_WIRE_API:-responses}"
CLAUDE_BIN="${CLAUDE_BIN:-}"
CODEX_BIN="${CODEX_BIN:-}"
NODE_BIN="${NODE_BIN:-}"
NPM_BIN="${NPM_BIN:-}"

usage() {
  cat <<'USAGE'
Usage: bash scripts/install.sh [options]

Options:
  --home DIR                 bridge home (default: ~/.codex-claude-bridge)
  --target LIST              workbuddy,claude,codex,generic,all,none
                             default: generic
  --skills-root DIR          root for agent skill dirs (default: $HOME)
  --claude-provider NAME     mimo | anthropic | custom (default: mimo)
  --claude-base-url URL      Anthropic-compatible endpoint
  --claude-model NAME        model id sent to the endpoint
  --claude-key KEY           provider key (or MIMO_API_KEY / ANTHROPIC_API_KEY)
  --codex-provider NAME      deepseek | openai | custom (default: deepseek)
  --codex-base-url URL       OpenAI-compatible endpoint
  --codex-model NAME         model id (default: deepseek-flash)
  --codex-key KEY            provider key (or DEEPSEEK_API_KEY / OPENAI_API_KEY)
  --codex-wire-api API       responses | chat (default: responses)
  --claude-bin PATH          existing Claude Code binary (skip npm install)
  --codex-bin PATH           existing Codex binary (skip npm install)
  --no-install-claude        do not npm-install Claude Code
  --no-install-codex         do not npm-install Codex
  --yes                      non-interactive; missing keys are skipped
  -h, --help                 show this help

Provider presets:
  Claude Code / MiMo: https://token-plan-cn.xiaomimimo.com/anthropic
                      model mimo-v2.6-flash, auth token in ANTHROPIC_AUTH_TOKEN
  Codex / DeepSeek:   https://api.deepseek.com
                      model deepseek-flash, wire_api=responses

The installer never writes into your existing ~/.codex or ~/.claude config;
it uses a private CODEX_HOME and CLAUDE_CONFIG_DIR under the bridge home.
USAGE
}

die() { echo "ERROR: $*" >&2; exit 1; }
q() { printf '%q' "$1"; }
toml_quote() { local v="$1"; v=${v//\\/\\\\}; v=${v//\"/\\\"}; printf '"%s"' "$v"; }
have() { command -v "$1" >/dev/null 2>&1; }
mask() { if [ -n "${1:-}" ]; then printf '%s…%s' "${1:0:4}" "${1: -4}"; else printf '(not set)'; fi; }

while [ $# -gt 0 ]; do
  case "$1" in
    --home) BRIDGE_HOME="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --skills-root) SKILLS_ROOT="$2"; shift 2 ;;
    --claude-provider) CLAUDE_PROVIDER="$2"; shift 2 ;;
    --claude-base-url) CLAUDE_BASE_URL="$2"; shift 2 ;;
    --claude-model) CLAUDE_MODEL="$2"; shift 2 ;;
    --claude-key) CLAUDE_API_KEY="$2"; shift 2 ;;
    --codex-provider) CODEX_PROVIDER="$2"; shift 2 ;;
    --codex-base-url) CODEX_BASE_URL="$2"; shift 2 ;;
    --codex-model) CODEX_MODEL="$2"; shift 2 ;;
    --codex-key) CODEX_API_KEY="$2"; shift 2 ;;
    --codex-wire-api) CODEX_WIRE_API="$2"; shift 2 ;;
    --claude-bin) CLAUDE_BIN="$2"; shift 2 ;;
    --codex-bin) CODEX_BIN="$2"; shift 2 ;;
    --no-install-claude) INSTALL_CLAUDE=0; shift ;;
    --no-install-codex) INSTALL_CODEX=0; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1 (use --help)" ;;
  esac
done

# --- provider presets -------------------------------------------------------
case "$CLAUDE_PROVIDER" in
  mimo)
    CLAUDE_BASE_URL="${CLAUDE_BASE_URL:-https://token-plan-cn.xiaomimimo.com/anthropic}"
    CLAUDE_MODEL="${CLAUDE_MODEL:-mimo-v2.6-flash}"
    ;;
  anthropic)
    CLAUDE_BASE_URL="${CLAUDE_BASE_URL:-https://api.anthropic.com}"
    CLAUDE_MODEL="${CLAUDE_MODEL:-claude-sonnet-4-5}"
    ;;
  custom)
    [ -n "$CLAUDE_BASE_URL" ] || die "--claude-base-url is required for custom provider"
    [ -n "$CLAUDE_MODEL" ] || die "--claude-model is required for custom provider"
    ;;
  *) die "unknown --claude-provider: $CLAUDE_PROVIDER" ;;
esac

case "$CODEX_PROVIDER" in
  deepseek)
    CODEX_BASE_URL="${CODEX_BASE_URL:-https://api.deepseek.com}"
    CODEX_MODEL="${CODEX_MODEL:-deepseek-flash}"
    ;;
  openai)
    CODEX_BASE_URL="${CODEX_BASE_URL:-https://api.openai.com/v1}"
    CODEX_MODEL="${CODEX_MODEL:-gpt-5.1-codex}"
    ;;
  custom)
    [ -n "$CODEX_BASE_URL" ] || die "--codex-base-url is required for custom provider"
    [ -n "$CODEX_MODEL" ] || die "--codex-model is required for custom provider"
    ;;
  *) die "unknown --codex-provider: $CODEX_PROVIDER" ;;
esac

# --- keys (prompt only when interactive) -----------------------------------
if [ -z "$CLAUDE_API_KEY" ] && [ "$ASSUME_YES" -eq 0 ] && [ -t 0 ]; then
  read -rsp "Claude Code provider API key (empty to skip Claude): " CLAUDE_API_KEY || true
  echo
fi
if [ -z "$CODEX_API_KEY" ] && [ "$ASSUME_YES" -eq 0 ] && [ -t 0 ]; then
  read -rsp "Codex provider API key (empty to skip Codex): " CODEX_API_KEY || true
  echo
fi
if [ -z "$CLAUDE_API_KEY" ]; then
  echo "WARN: no Claude Code provider key; Claude wrapper will be skipped." >&2
fi
if [ -z "$CODEX_API_KEY" ]; then
  echo "WARN: no Codex provider key; Codex wrapper will be skipped." >&2
fi
[ -n "$CLAUDE_API_KEY" ] || [ -n "$CODEX_API_KEY" ] || die "at least one provider key is required"

# --- node / python ----------------------------------------------------------
if [ -z "$NODE_BIN" ]; then
  if have node; then
    NODE_BIN="$(command -v node)"
  elif [ -f "$HOME/.workbuddy/binaries/node/versions/current" ]; then
    NODE_BIN="$HOME/.workbuddy/binaries/node/versions/$(cat "$HOME/.workbuddy/binaries/node/versions/current")/bin/node"
  fi
fi
[ -n "$NODE_BIN" ] && [ -x "$NODE_BIN" ] || die "Node.js 18+ not found; install Node or set NODE_BIN"
if [ -z "$NPM_BIN" ]; then
  if have npm; then
    NPM_BIN="$(command -v npm)"
  elif [ -x "$(dirname "$NODE_BIN")/npm" ]; then
    NPM_BIN="$(dirname "$NODE_BIN")/npm"
  fi
fi
if [ "$INSTALL_CLAUDE" -eq 1 ] || [ "$INSTALL_CODEX" -eq 1 ]; then
  [ -n "$NPM_BIN" ] && [ -x "$NPM_BIN" ] || die "npm not found; install npm or pass --claude-bin/--codex-bin"
  export PATH="$(dirname "$NODE_BIN"):$PATH"
fi

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
if [ -z "$PYTHON_BIN" ]; then
  echo "WARN: python3 not found; MCP server will be skipped, CLI wrappers still work." >&2
fi

mkdir -p "$BRIDGE_HOME"
chmod 700 "$BRIDGE_HOME"

# --- Claude Code ------------------------------------------------------------
if [ -n "$CLAUDE_API_KEY" ]; then
  if [ -n "$CLAUDE_BIN" ]; then
    [ -x "$CLAUDE_BIN" ] || die "Claude binary is not executable: $CLAUDE_BIN"
  elif [ -x "$BRIDGE_HOME/claude-cli/node_modules/@anthropic-ai/claude-code/bin/claude.exe" ]; then
    CLAUDE_BIN="$BRIDGE_HOME/claude-cli/node_modules/@anthropic-ai/claude-code/bin/claude.exe"
  elif [ -x "$BRIDGE_HOME/claude-cli/node_modules/@anthropic-ai/claude-code/bin/claude" ]; then
    CLAUDE_BIN="$BRIDGE_HOME/claude-cli/node_modules/@anthropic-ai/claude-code/bin/claude"
  elif [ "$INSTALL_CLAUDE" -eq 1 ]; then
    echo "Installing Claude Code into $BRIDGE_HOME/claude-cli ..."
    "$NPM_BIN" install --prefix "$BRIDGE_HOME/claude-cli" --no-fund --no-audit @anthropic-ai/claude-code
    for candidate in \
      "$BRIDGE_HOME/claude-cli/node_modules/@anthropic-ai/claude-code/bin/claude.exe" \
      "$BRIDGE_HOME/claude-cli/node_modules/@anthropic-ai/claude-code/bin/claude" \
      "$BRIDGE_HOME/claude-cli/node_modules/.bin/claude"; do
      [ -x "$candidate" ] && CLAUDE_BIN="$candidate" && break
    done
  fi
  [ -n "$CLAUDE_BIN" ] && [ -x "$CLAUDE_BIN" ] || { echo "WARN: Claude Code not installed; skip Claude." >&2; CLAUDE_API_KEY=""; }
fi

# --- Codex ------------------------------------------------------------------
codex_wrapper() {
  local js="$1"
  mkdir -p "$BRIDGE_HOME/bin"
  printf '#!/bin/bash\nexec %q %q "$@"\n' "$NODE_BIN" "$js" > "$BRIDGE_HOME/bin/codex"
  chmod +x "$BRIDGE_HOME/bin/codex"
  CODEX_BIN="$BRIDGE_HOME/bin/codex"
}

if [ -n "$CODEX_API_KEY" ]; then
  if [ -n "$CODEX_BIN" ]; then
    [ -x "$CODEX_BIN" ] || die "Codex binary is not executable: $CODEX_BIN"
  elif have codex; then
    CODEX_BIN="$(command -v codex)"
  elif [ -x "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex" ]; then
    CODEX_BIN="/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
  elif [ -f "$BRIDGE_HOME/codex-cli/node_modules/@openai/codex/bin/codex.js" ]; then
    codex_wrapper "$BRIDGE_HOME/codex-cli/node_modules/@openai/codex/bin/codex.js"
  elif [ "$INSTALL_CODEX" -eq 1 ]; then
    echo "Installing Codex CLI into $BRIDGE_HOME/codex-cli ..."
    "$NPM_BIN" install --prefix "$BRIDGE_HOME/codex-cli" --no-fund --no-audit @openai/codex
    if [ -f "$BRIDGE_HOME/codex-cli/node_modules/@openai/codex/bin/codex.js" ]; then
      codex_wrapper "$BRIDGE_HOME/codex-cli/node_modules/@openai/codex/bin/codex.js"
    elif [ -x "$BRIDGE_HOME/codex-cli/node_modules/.bin/codex" ]; then
      CODEX_BIN="$BRIDGE_HOME/codex-cli/node_modules/.bin/codex"
    fi
  fi
  [ -n "$CODEX_BIN" ] && [ -x "$CODEX_BIN" ] || { echo "WARN: Codex not installed; skip Codex." >&2; CODEX_API_KEY=""; }
fi

# --- copy app ---------------------------------------------------------------
APP="$BRIDGE_HOME/app"
if [ "$PKG_DIR" != "$APP" ]; then
  mkdir -p "$APP"
  cp -R "$PKG_DIR/scripts" "$PKG_DIR/mcp" "$PKG_DIR/templates" "$APP/"
  for f in SKILL.md AGENTS.md README.md VERSION.txt LICENSE.md NOTICE.md; do
    [ -f "$PKG_DIR/$f" ] && cp "$PKG_DIR/$f" "$APP/"
  done
fi
chmod +x "$APP/scripts/"*.sh 2>/dev/null || true

# --- config.env -------------------------------------------------------------
CONFIG="$BRIDGE_HOME/config.env"
{
  echo "# generated by codex-claude-bridge $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "export CLAUDE_PROVIDER=$(q "$CLAUDE_PROVIDER")"
  echo "export CLAUDE_BASE_URL=$(q "$CLAUDE_BASE_URL")"
  echo "export CLAUDE_MODEL=$(q "$CLAUDE_MODEL")"
  echo "export CLAUDE_API_KEY=$(q "$CLAUDE_API_KEY")"
  echo "export CLAUDE_BIN=$(q "$CLAUDE_BIN")"
  echo "export CODEX_PROVIDER=$(q "$CODEX_PROVIDER")"
  echo "export CODEX_BASE_URL=$(q "$CODEX_BASE_URL")"
  echo "export CODEX_MODEL=$(q "$CODEX_MODEL")"
  echo "export CODEX_API_KEY=$(q "$CODEX_API_KEY")"
  echo "export CODEX_BIN=$(q "$CODEX_BIN")"
  echo "export CODEX_WIRE_API=$(q "$CODEX_WIRE_API")"
} > "$CONFIG"
chmod 600 "$CONFIG"
mkdir -p "$BRIDGE_HOME/claude-home" "$BRIDGE_HOME/codex-home"

# --- Codex home -------------------------------------------------------------
CATALOG=""
if [ -n "$CODEX_API_KEY" ]; then
  if [ "$CODEX_PROVIDER" = "deepseek" ] && [ -f "$APP/templates/deepseek-models.json" ]; then
    cp "$APP/templates/deepseek-models.json" "$BRIDGE_HOME/codex-home/models.json"
    CATALOG="$BRIDGE_HOME/codex-home/models.json"
  fi
  CT="$BRIDGE_HOME/codex-home/config.toml"
  {
    echo "model_provider = \"bridge\""
    echo "model = $(toml_quote "$CODEX_MODEL")"
    echo "forced_login_method = \"api\""
    echo "suppress_unstable_features_warning = true"
    if [ -n "$CATALOG" ]; then
      echo "model_catalog_json = $(toml_quote "$CATALOG")"
    fi
    echo
    echo "[model_providers.bridge]"
    echo "name = $(toml_quote "$CODEX_PROVIDER")"
    echo "base_url = $(toml_quote "$CODEX_BASE_URL")"
    echo "wire_api = \"$CODEX_WIRE_API\""
    echo "requires_openai_auth = true"
  } > "$CT"
  json_escape() { local v="$1"; v=${v//\\/\\\\}; v=${v//\"/\\\"}; printf '%s' "$v"; }
  printf '{"auth_mode":"apikey","OPENAI_API_KEY":"%s"}\n' "$(json_escape "$CODEX_API_KEY")" > "$BRIDGE_HOME/codex-home/auth.json"
  chmod 600 "$BRIDGE_HOME/codex-home/auth.json"
fi

# --- MCP config -------------------------------------------------------------
if [ -n "$PYTHON_BIN" ]; then
  printf '{\n  "mcpServers": {\n    "codex-claude-bridge": {\n      "command": "%s",\n      "args": ["%s"]\n    }\n  }\n}\n' \
    "$PYTHON_BIN" "$APP/mcp/server.py" > "$BRIDGE_HOME/mcp.json"
else
  echo "WARN: skip mcp.json (no python3); MCP clients cannot attach until python3 is installed." >&2
fi

# --- agent registration -----------------------------------------------------
render_skill() {
  local out="$1"
  mkdir -p "$(dirname "$out")"
  sed "s|__BRIDGE_HOME__|$BRIDGE_HOME|g" "$APP/templates/SKILL.md" > "$out"
}

register_workbuddy() {
  render_skill "$SKILLS_ROOT/.workbuddy/skills/codex-claude-bridge/SKILL.md"
  echo "WorkBuddy skill: $SKILLS_ROOT/.workbuddy/skills/codex-claude-bridge/SKILL.md"
}
register_claude() {
  render_skill "$SKILLS_ROOT/.claude/skills/codex-claude-bridge/SKILL.md"
  echo "Claude Code skill: $SKILLS_ROOT/.claude/skills/codex-claude-bridge/SKILL.md"
}
register_codex() {
  local agents="$SKILLS_ROOT/.codex/AGENTS.md"
  mkdir -p "$(dirname "$agents")"
  if ! grep -q 'BEGIN codex-claude-bridge' "$agents" 2>/dev/null; then
    {
      echo
      echo "<!-- BEGIN codex-claude-bridge -->"
      sed "s|__BRIDGE_HOME__|$BRIDGE_HOME|g" "$APP/templates/AGENTS-block.md"
      echo "<!-- END codex-claude-bridge -->"
      echo
    } >> "$agents"
  fi
  echo "Codex AGENTS.md: $agents"
}

TARGETS="$(echo "$TARGET" | tr ',' ' ')"
[ "$TARGET" = "all" ] && TARGETS="workbuddy claude codex generic"
for t in $TARGETS; do
  case "$t" in
    workbuddy) register_workbuddy ;;
    claude) register_claude ;;
    codex) register_codex ;;
    generic) echo "MCP config: $BRIDGE_HOME/mcp.json" ;;
    none|"") : ;;
    *) die "unknown --target: $t" ;;
  esac
done

echo
echo "Bridge installed: $BRIDGE_HOME"
echo "  Claude Code: $(mask "$CLAUDE_API_KEY")  ${CLAUDE_MODEL:-<skipped>}  $CLAUDE_BASE_URL"
echo "  Codex:       $(mask "$CODEX_API_KEY")  ${CODEX_MODEL:-<skipped>}  $CODEX_BASE_URL"
echo "  Config:      $CONFIG (600)"
echo "  MCP:         $BRIDGE_HOME/mcp.json"
echo
echo "Next:"
echo "  bash $APP/scripts/doctor.sh"
echo "  bash $APP/scripts/ask-claude.sh \"只回答：OK\""
echo "  bash $APP/scripts/ask-codex.sh \"只回答：OK\""
