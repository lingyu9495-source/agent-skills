#!/usr/bin/env python3
"""memory_hook —— 把记忆底座接进任何 Agent 的最小钩子。

为什么要它：装了底座但不注入，等于白装。AI 不会主动去翻档案，
必须在**每一轮/每个会话开始时**把相关记忆塞进上下文。

用法：
    python3 memory_hook.py                  # 输出：热层 + 最近 7 天记忆
    python3 memory_hook.py --query "客户名"  # 输出：热层 + 与该查询相关的记忆
    python3 memory_hook.py --days 30 --limit 60

接到 Agent 的三种方式：
1) 会话启动时执行，把 stdout 追加到 system prompt 末尾
2) 每轮用户消息进来时带 --query，做"按需召回"
3) 作为 MCP / 工具暴露给模型，由它自己调

输出带固定标记 【长期记忆·自动召回】，验收时用它 grep 会话文件，
能 grep 到才算真接上（模型编不出这段标记）。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

DIR = Path(os.environ.get("AI_MEM_DIR", Path.home() / "ai-memory"))
AI_MEM = DIR / "bin" / "ai_mem.py"
MARK = "【长期记忆·自动召回】"


def run(*args: str) -> str:
    if not AI_MEM.exists():
        return ""
    try:
        out = subprocess.run(
            [sys.executable, str(AI_MEM), *args],
            capture_output=True, text=True, timeout=20,
            env={**os.environ, "AI_MEM_DIR": str(DIR)},
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


def hot_layer() -> str:
    p = DIR / "MEMORY.md"
    try:
        txt = p.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    # 热层超预算就截断，别把上下文挤爆
    return txt[:8000]


def build(query: str | None, days: int, limit: int) -> str:
    parts: list[str] = []
    hot = hot_layer()
    if hot:
        parts.append("## 热层（身份 / 铁律 / 偏好）\n" + hot)

    if query:
        hits = run("recall", query, "-k", str(min(limit, 20)))
        if not hits:
            hits = run("search", query, "-k", str(min(limit, 20)))
        if hits:
            parts.append("## 与当前任务相关的记忆\n" + hits)
    else:
        recent = run("inject", "--days", str(days), "--limit", str(limit))
        if recent:
            parts.append("## 最近 %d 天\n%s" % (days, recent))

    if not parts:
        return ""
    return f"{MARK}\n" + "\n\n".join(parts) + f"\n（以上来自 {DIR}，如需更正请直接告知）"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default=None, help="按当前任务做相关召回")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--empty-ok", action="store_true", help="没有记忆时也输出空标记")
    a = ap.parse_args()

    block = build(a.query, a.days, a.limit)
    if block:
        print(block)
    elif a.empty_ok:
        print(MARK + "\n（暂无记忆）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
