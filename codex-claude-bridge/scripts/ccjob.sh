#!/bin/bash
# ccjob —— Claude Code 工单执行器
# 备份 → 限权执行 → 回读验收（真 diff）→ 需要时一键回滚
# 用法：
#   ccjob --dir /path/to/project --job "只改 config.yaml 的 model 为 xxx，别动其他文件"
#   ccjob --dir /path --job-file task.md --tools "Read,Edit,Bash(ls *),Bash(cat *)"
#   ccjob --rollback <run_id>           # 回滚到该次执行前的状态
#   ccjob --list                        # 看历史工单
set -uo pipefail

CC_ENV="${CC_ENV:-/root/.claude/cc.env}"
RUNS="${CCJOB_RUNS:-/root/.hermes/profiles/chuwu/cache/cc_runs}"

# 只在需要执行时加载凭据；--list / --rollback 不碰网络
need_env() { [ -f "$CC_ENV" ] || { echo "缺 $CC_ENV（跑 ask-claude 安装脚本生成）"; exit 1; }; . "$CC_ENV"; }

JOB=""; JOBFILE=""; WORKDIR=""; TOOLS="${CCJOB_TOOLS:-Read,Edit,Write}"
MAXT="${CCJOB_MAX_TURNS:-20}"; PERM="${CCJOB_PERM:-acceptEdits}"; ROLLBACK_ID=""; LIST=0

usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --job) JOB="$2"; shift 2 ;;
    --job-file) JOBFILE="$2"; shift 2 ;;
    --dir) WORKDIR="$2"; shift 2 ;;
    --tools) TOOLS="$2"; shift 2 ;;
    --max-turns) MAXT="$2"; shift 2 ;;
    --permission-mode) PERM="$2"; shift 2 ;;
    --rollback) ROLLBACK_ID="$2"; shift 2 ;;
    --list) LIST=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数：$1（--help 看用法）"; exit 2 ;;
  esac
done

# ---------- 历史 ----------
if [ "$LIST" = 1 ]; then
  printf '%-20s %-10s %-8s %s\n' RUN_ID 耗时 结果 工单
  for f in "$RUNS"/*/meta.txt; do
    [ -f "$f" ] || continue
    id=$(basename "$(dirname "$f")")
    dur=$(sed -n 's/^duration_ms=//p' "$f"); rc=$(sed -n 's/^rc=//p' "$f")
    job=$(sed -n 's/^job=//p' "$f" | head -c 60)
    printf '%-20s %-10s %-8s %s\n' "$id" "${dur}ms" "$rc" "$job"
  done
  exit 0
fi

# ---------- 回滚 ----------
if [ -n "$ROLLBACK_ID" ]; then
  SRC="$RUNS/$ROLLBACK_ID"
  [ -f "$SRC/backup.tar.gz" ] || { echo "找不到备份：$SRC/backup.tar.gz"; exit 1; }
  TARGET=$(sed -n 's/^workdir=//p' "$SRC/meta.txt")
  [ -n "$TARGET" ] || { echo "meta.txt 里没有 workdir，无法回滚"; exit 1; }
  echo "回滚 $TARGET ← $SRC/backup.tar.gz"
  tar xzf "$SRC/backup.tar.gz" -C "$TARGET" && echo "已回滚。核对：ls -la $TARGET"
  exit 0
fi

# ---------- 参数校验 ----------
[ -n "$JOB" ] || [ -n "$JOBFILE" ] || { echo "必须给 --job 或 --job-file"; exit 2; }
[ -n "$WORKDIR" ] || { echo "必须给 --dir（绝对路径，锁死操作范围）"; exit 2; }
[ -d "$WORKDIR" ] || { echo "目录不存在：$WORKDIR"; exit 2; }
WORKDIR=$(cd "$WORKDIR" && pwd)
if [ -n "$JOBFILE" ]; then
  [ -f "$JOBFILE" ] || { echo "工单文件不存在：$JOBFILE"; exit 2; }
  JOB="$(cat "$JOBFILE")"
fi

need_env
RUN_ID="$(date +%Y%m%d_%H%M%S)_$$"
RUN="$RUNS/$RUN_ID"; mkdir -p "$RUN"

# ---------- 1. 备份 ----------
tar czf "$RUN/backup.tar.gz" -C "$WORKDIR" . 2>/dev/null
BK_SIZE=$(stat -c%s "$RUN/backup.tar.gz" 2>/dev/null || echo 0)
mkdir -p "$RUN/extracted" && tar xzf "$RUN/backup.tar.gz" -C "$RUN/extracted" 2>/dev/null

# ---------- 2. 变更前指纹 ----------
manifest() { ( cd "$WORKDIR" && find . -type f -not -path './.git/*' -not -name '*.tmp' -printf '%P\n' 2>/dev/null | sort | while read -r f; do printf '%s  %s\n' "$(md5sum "$f" 2>/dev/null | cut -d' ' -f1)" "$f"; done ); }
manifest > "$RUN/before.txt"

# ---------- 3. 执行 ----------
echo "== 工单 ==" ; printf '%s\n' "$JOB" | head -20
echo "== 目录 == $WORKDIR"
echo "== 权限 == mode=$PERM tools=$TOOLS max_turns=$MAXT"
echo "== 备份 == $RUN/backup.tar.gz (${BK_SIZE}B)"
echo "== 开始执行 =="

T0=$(date +%s%3N)
OUT="$( cd "$WORKDIR" && timeout "${CCJOB_TIMEOUT:-900}" claude -p "$JOB" \
  --permission-mode "$PERM" \
  --allowedTools "$TOOLS" \
  --add-dir "$WORKDIR" \
  --max-turns "$MAXT" \
  --output-format json 2>&1 )"
RC=$?
T1=$(date +%s%3N); DT=$(( T1 - T0 ))
printf '%s' "$OUT" > "$RUN/raw.out"

# ---------- 4. 回读验收 ----------
manifest > "$RUN/after.txt"
CHANGED=$(diff "$RUN/before.txt" "$RUN/after.txt" | grep -E '^[<>]' | awk '{print $NF}' | sort -u)

echo; echo "== 执行结果 =="
python3 - "$RUN/raw.out" "$RC" "$DT" <<'PY'
import json, sys, re, pathlib
raw = pathlib.Path(sys.argv[1]).read_text(errors='replace')
rc, dt = sys.argv[2], sys.argv[3]
obj = None
dec = json.JSONDecoder()
i = 0
while True:
    i = raw.find('{', i)
    if i < 0: break
    try:
        cand, end = dec.raw_decode(raw, i)
        if isinstance(cand, dict) and ('result' in cand or 'subtype' in cand): obj = cand; i = end; continue
    except Exception: pass
    i += 1
if obj:
    res = (obj.get('result') or '').strip()
    print(f"  rc={rc}  耗时={dt}ms  subtype={obj.get('subtype')}  turns={obj.get('num_turns')}")
    print("  ---- 模型自述 ----")
    print('  ' + '\n  '.join(res.splitlines()[:12]))
else:
    print(f"  rc={rc}  耗时={dt}ms  （没解析到 JSON，原始输出见 raw.out）")
    print('  ' + '\n  '.join(raw.strip().splitlines()[-6:]))
PY

echo; echo "== 真改了哪些文件（不看模型自述，看磁盘）=="
if [ -z "$CHANGED" ]; then
  echo "  ⚠ 一个文件都没变。要么任务不需要改文件，要么它没执行。别当成功。"
else
  printf '%s\n' "$CHANGED" | sed 's/^/  · /'
  echo; echo "== diff =="
  ( cd "$WORKDIR" && for f in $CHANGED; do
      [ -f "./$f" ] && diff -u "$RUN/extracted/$f" "./$f" 2>/dev/null | head -40
    done ) 2>/dev/null || true
fi

printf 'job=%s\nworkdir=%s\nrc=%s\nduration_ms=%s\nchanged=%s\n' \
  "$(printf '%s' "$JOB" | head -c 200)" "$WORKDIR" "$RC" "$DT" "$(echo $CHANGED)" > "$RUN/meta.txt"

echo; echo "== 收尾 =="
echo "  日志 : $RUN"
[ -s "$RUN/backup.tar.gz" ] && echo "  回滚 : ccjob --rollback $RUN_ID"
[ "$RC" -ne 0 ] && echo "  ⚠ 退出码非 0，先看 raw.out 再决定回滚"
exit "$RC"
