#!/usr/bin/env bash
# Agent Memory Kit 一键安装（零依赖：只需要 python3 >= 3.8，带 sqlite3 FTS5）
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${AI_MEM_HOME:-$HOME/ai-memory}"
PY="${PYTHON:-python3}"

echo "==> 检查 python3"
command -v "$PY" >/dev/null || { echo "没找到 python3，请先安装"; exit 1; }
"$PY" - <<'PY'
import sqlite3, sys
con = sqlite3.connect(":memory:")
try:
    con.execute("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='trigram')")
    print("   FTS5(trigram) 可用 —— 中文片段检索没问题")
except sqlite3.OperationalError:
    try:
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        print("   FTS5 可用（无 trigram，召回会退化，建议升级 Python/SQLite）")
    except Exception as e:
        print("   ✗ 这个 Python 没编 FTS5：", e)
        sys.exit(1)
PY

echo "==> 安装到 $DEST"
mkdir -p "$DEST/bin" "$DEST/facts" "$DEST/archive"
cp "$HERE/ai_mem.py" "$DEST/bin/ai_mem.py"
chmod +x "$DEST/bin/ai_mem.py"

BIN=/usr/local/bin/ai_mem
if [ -n "${AI_MEM_HOME:-}" ] && [ "$DEST" != "$HOME/ai-memory" ]; then
  # 自定义目录安装（测试/多实例）：不碰全局软链，免得覆盖已有安装
  echo "   自定义目录，跳过全局软链，直接用 $DEST/bin/ai_mem.py"
  BIN="$DEST/bin/ai_mem.py"
elif [ -w /usr/local/bin ]; then
  ln -sf "$DEST/bin/ai_mem.py" "$BIN"; echo "   已链接 $BIN"
else
  echo "   无权限写 /usr/local/bin，改用用户目录："
  mkdir -p "$HOME/.local/bin"
  ln -sf "$DEST/bin/ai_mem.py" "$HOME/.local/bin/ai_mem"
  echo "   已链接 $HOME/.local/bin/ai_mem （确认它在 PATH 里）"
  BIN="$HOME/.local/bin/ai_mem"
fi

if [ ! -f "$DEST/MEMORY.md" ]; then
  cat > "$DEST/MEMORY.md" <<'EOF'
# 核心记忆（热层）

> 人机共写，建议 ≤8KB。只放：身份、铁律、稳定偏好、高频指针。
> 细节走 `ai_mem add`，月度归档走 `ai_mem digest`。

## 用户
- 待填：称呼、角色、沟通偏好

## 铁律
- 涉及金额给算式；拿不到的数据说拿不到，不编
- 对外结论先给结论，再给依据

## 高频指针
- 项目根目录：待填
EOF
  echo "   已生成 $DEST/MEMORY.md（记得改成你自己的）"
fi

echo "==> 自检（写入 → 关键词 → 片段召回）"
export AI_MEM_DIR="$DEST"
"$BIN" add "安装自检暗号：蓝鲸 $(date +%F)" --tags selftest --kind event >/dev/null
echo -n "   search 蓝鲸 : "; "$BIN" search "蓝鲸" -k 1 | head -1
echo -n "   recall 问句 : "; "$BIN" recall "上次装的时候用的什么暗号" -k 1 | head -1
"$BIN" stats

cat <<EOF

✅ 装好了。日常三条：
   export AI_MEM_DIR=$DEST
   ai_mem inject --days 7          # 会话开始：输出记忆块，塞进系统提示
   ai_mem add "结论/决定/偏好" --tags 项目 --kind event

下一步：把 inject 接进你的 Agent（见 docs/03-部署SOP.md）。
EOF
