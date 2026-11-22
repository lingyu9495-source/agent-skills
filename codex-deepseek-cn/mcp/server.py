#!/usr/bin/env python3
"""Minimal MCP stdio server for the Codex + Claude Code bridge.

Tools:
  ask_codex  -> run the Codex CLI with a prompt
  ask_claude -> run the Claude Code CLI with a prompt

The server is intentionally dependency-free (Python stdlib only) and talks
newline-delimited JSON-RPC 2.0 on stdin/stdout. Logs go to stderr.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SERVER_NAME = "codex-claude-bridge"
SERVER_VERSION = "1.0.0"
DEFAULT_PROTOCOL = "2024-11-05"
TIMEOUT_SECONDS = int(os.environ.get("CODEX_CLAUDE_BRIDGE_TIMEOUT", "900"))


def bridge_home() -> Path:
    # Installed layout: <bridge>/app/mcp/server.py -> <bridge>
    # Source layout: allow CODEX_CLAUDE_BRIDGE_HOME override.
    env_home = os.environ.get("CODEX_CLAUDE_BRIDGE_HOME")
    if env_home:
        return Path(env_home)
    return Path(__file__).resolve().parent.parent.parent


def scripts_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "scripts"


def log(message: str) -> None:
    print(f"[{SERVER_NAME}] {message}", file=sys.stderr, flush=True)


def send(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def error(request_id, code: int, message: str) -> None:
    send({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


TOOLS = [
    {
        "name": "ask_codex",
        "description": (
            "Delegate a coding/repository task to the local Codex CLI. "
            "Codex runs with its own isolated config and a domestic/OpenAI-compatible "
            "model. Default sandbox is read-only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Task or question for Codex."},
                "cwd": {"type": "string", "description": "Absolute working directory (optional)."},
                "sandbox": {
                    "type": "string",
                    "enum": ["read-only", "workspace-write", "danger-full-access"],
                    "description": "Codex sandbox mode (optional; default read-only).",
                },
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ask_claude",
        "description": (
            "Delegate a task to the local Claude Code CLI. Claude Code runs on the "
            "host (not Claude Desktop's 3P sandbox) and can use MCP tools. Default "
            "permission mode is dontAsk; grant more only with user consent."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Task or question for Claude Code."},
                "cwd": {"type": "string", "description": "Absolute working directory (optional)."},
                "permission_mode": {
                    "type": "string",
                    "enum": ["default", "dontAsk", "acceptEdits", "bypassPermissions", "plan"],
                    "description": "Claude Code permission mode (optional; default dontAsk).",
                },
                "mcp_config": {
                    "type": "string",
                    "description": "Optional path to an MCP JSON config for Claude Code.",
                },
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
    },
]


def run_tool(name: str, arguments: dict) -> tuple[str, bool]:
    prompt = arguments.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return "prompt is required", True
    cwd = arguments.get("cwd") or os.getcwd()
    if not isinstance(cwd, str) or not Path(cwd).is_dir():
        return f"cwd is not a directory: {cwd}", True

    env = os.environ.copy()
    env["CODEX_CLAUDE_BRIDGE_HOME"] = str(bridge_home())
    env.setdefault("PYTHONUNBUFFERED", "1")

    if name == "ask_codex":
        script = scripts_dir() / "ask-codex.sh"
        env["CODEX_SANDBOX"] = str(arguments.get("sandbox") or "read-only")
    elif name == "ask_claude":
        script = scripts_dir() / "ask-claude.sh"
        env["CLAUDE_PERMISSION_MODE"] = str(arguments.get("permission_mode") or "dontAsk")
        mcp_config = arguments.get("mcp_config")
        if isinstance(mcp_config, str) and mcp_config:
            env["CLAUDE_MCP_CONFIG"] = mcp_config
    else:
        return f"unknown tool: {name}", True

    if not script.is_file():
        return f"bridge script missing: {script}", True

    try:
        proc = subprocess.run(
            [str(script), prompt, cwd],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env=env,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return f"{name} timed out after {TIMEOUT_SECONDS}s", True
    except Exception as exc:  # pragma: no cover - defensive
        return f"{name} failed: {exc}", True

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if name == "ask_claude":
        try:
            payload = json.loads(stdout)
            if isinstance(payload, dict):
                result = payload.get("result")
                if isinstance(result, str):
                    stdout = result
                if payload.get("is_error"):
                    return (stdout or stderr or "Claude Code error"), True
        except Exception:
            pass
    if proc.returncode != 0:
        return (stdout or stderr or f"{name} exited {proc.returncode}"), True
    return (stdout or stderr or f"{name} returned no output"), False


def handle(request: dict):
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}

    if method == "initialize":
        send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": params.get("protocolVersion") or DEFAULT_PROTOCOL,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "instructions": (
                        "Use ask_codex for repository/coding tasks and ask_claude for "
                        "long-context or host-level tool tasks. Defaults are read-only/dontAsk."
                    ),
                },
            }
        )
    elif method in ("notifications/initialized", "notifications/cancelled"):
        return
    elif method == "ping":
        send({"jsonrpc": "2.0", "id": request_id, "result": {}})
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            error(request_id, -32602, "arguments must be an object")
            return
        text, is_error = run_tool(str(name), arguments)
        send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": text}], "isError": bool(is_error)},
            }
        )
    elif method == "resources/list":
        send({"jsonrpc": "2.0", "id": request_id, "result": {"resources": []}})
    elif method == "prompts/list":
        send({"jsonrpc": "2.0", "id": request_id, "result": {"prompts": []}})
    else:
        error(request_id, -32601, f"method not found: {method}")


def main() -> int:
    log(f"started; bridge={bridge_home()} scripts={scripts_dir()}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except Exception as exc:
            error(None, -32700, f"parse error: {exc}")
            continue
        if not isinstance(request, dict):
            error(None, -32600, "invalid request")
            continue
        try:
            handle(request)
        except Exception as exc:  # pragma: no cover - defensive
            error(request.get("id"), -32603, f"internal error: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
