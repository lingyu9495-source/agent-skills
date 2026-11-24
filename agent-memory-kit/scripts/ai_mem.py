#!/usr/bin/env python3
"""ai_mem — 零依赖长期记忆底座（L1 档）
只依赖 Python3 标准库 + sqlite3(FTS5)。适合装在客户机 / 无运维环境。

目录（默认 ~/.ai-memory，可用 AI_MEM_DIR 覆盖）：
  MEMORY.md        热层：身份、铁律、偏好（人机共写，建议 ≤8KB）
  facts/*.jsonl    温层：结构化事实（时间/内容/标签/来源）
  archive/*.md     冷层：按月归档摘要
  index.db         FTS5 全文索引

命令：
  add "内容" [--tags a,b] [--source x] [--kind fact|pref|event]
  search "关键词" [-k 8]
  recent [-n 10]
  inject [--days 7]        输出可直接塞进提示的记忆块
  digest [--month 2026-11] 生成月度归档摘要
  stats
"""
import argparse, json, os, sqlite3, sys, datetime, re, hashlib

DIR = os.environ.get("AI_MEM_DIR", os.path.expanduser("~/.ai-memory"))
DB = os.path.join(DIR, "index.db")


def now():
    return datetime.datetime.now()


def ensure():
    for d in ("facts", "archive"):
        os.makedirs(os.path.join(DIR, d), exist_ok=True)
    con = sqlite3.connect(DB)
    try:
        con.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS mem USING fts5(
            rid UNINDEXED, ts UNINDEXED, kind UNINDEXED, tags UNINDEXED,
            source UNINDEXED, body, tokenize='trigram')""")
    except sqlite3.OperationalError:
        con.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS mem USING fts5(
            rid UNINDEXED, ts UNINDEXED, kind UNINDEXED, tags UNINDEXED,
            source UNINDEXED, body, tokenize='unicode61')""")
    con.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
    con.commit()
    return con


def add(args):
    con = ensure()
    body = args.text.strip()
    if not body:
        sys.exit("empty text")
    rid = hashlib.sha1((body + str(now())).encode()).hexdigest()[:16]
    ts = now().isoformat(timespec="seconds")
    tags = ",".join(args.tags.split(",")) if args.tags else ""
    con.execute("INSERT INTO mem(rid,ts,kind,tags,source,body) VALUES (?,?,?,?,?,?)",
                (rid, ts, args.kind, tags, args.source or "cli", body))
    con.commit()
    # 温层落盘（与索引同源，便于迁移与人审）
    fp = os.path.join(DIR, "facts", now().strftime("%Y-%m") + ".jsonl")
    with open(fp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"rid": rid, "ts": ts, "kind": args.kind, "tags": tags,
                            "source": args.source or "cli", "body": body}, ensure_ascii=False) + "\n")
    print(f"ok {rid}")


def search(args):
    con = ensure()
    q = args.query.strip()
    # FTS5 语法保护：按词加引号 OR 连接
    terms = [t for t in re.split(r"[\s,，]+", q) if t]
    expr = " OR ".join('"' + t.replace('"', '""') + '"' for t in terms) or '""'
    try:
        rows = con.execute(
            "SELECT ts,kind,tags,body FROM mem WHERE mem MATCH ? ORDER BY rank LIMIT ?",
            (expr, args.k)).fetchall()
    except sqlite3.OperationalError:
        rows = con.execute(
            "SELECT ts,kind,tags,body FROM mem WHERE body LIKE ? ORDER BY ts DESC LIMIT ?",
            (f"%{q}%", args.k)).fetchall()
    if not rows:
        rows = con.execute(
            "SELECT ts,kind,tags,body FROM mem WHERE body LIKE ? ORDER BY ts DESC LIMIT ?",
            (f"%{q}%", args.k)).fetchall()
    if not rows:
        print("(no hit)")
        return
    for ts, kind, tags, body in rows:
        print(f"[{ts[:16]}] ({kind}{'/'+tags if tags else ''}) {body[:300]}")


def _ngrams(q: str) -> list:
    """把一句自然语言切成 2–3 字 CJK 片段 + 英文/数字词，用于模糊召回。"""
    grams, seen, out = [], set(), []
    for run in re.findall(r"[\u4e00-\u9fff]+", q):
        L = len(run)
        for n in (2, 3):
            for i in range(0, max(0, L - n + 1)):
                grams.append(run[i:i + n])
    grams.extend(re.findall(r"[A-Za-z0-9]{2,}", q))
    for g in grams:
        if g not in seen:
            seen.add(g)
            out.append(g)
    return out[:14]


def recall(args):
    """整句召回：按 2–3 字片段命中数打分，适合"这句问话里有没有旧事"这种场景。"""
    con = ensure()
    q = args.query.strip()
    grams = _ngrams(q)
    if not grams:
        return search(args)
    where = " OR ".join(["body LIKE ?"] * len(grams))
    rows = con.execute(
        f"SELECT ts,kind,tags,body FROM mem WHERE {where} ORDER BY ts DESC LIMIT 500",
        tuple(f"%{g}%" for g in grams)).fetchall()
    scored = []
    for ts, kind, tags, body in rows:
        s = sum(1 for g in grams if g in body)
        s += sum(0.5 for g in grams if len(g) >= 3 and g in body)
        if s >= 1:
            scored.append((s, ts, kind, tags, body))
    scored.sort(key=lambda r: (-r[0], r[1]))
    if not scored:
        print("(no hit)")
        return
    for s, ts, kind, tags, body in scored[:args.k]:
        print(f"[{ts[:16]}] ({kind}{'/'+tags if tags else ''}) {body[:300]}")


def recent(args):
    con = ensure()
    for ts, kind, body in con.execute(
            "SELECT ts,kind,body FROM mem ORDER BY ts DESC LIMIT ?", (args.n,)):
        print(f"[{ts[:16]}] ({kind}) {body[:200]}")


def inject(args):
    """输出记忆块，供提示注入。热层优先，其后是近 N 天事实。"""
    mem_md = os.path.join(DIR, "MEMORY.md")
    print("## 长期记忆（自动注入）\n")
    if os.path.exists(mem_md):
        txt = open(mem_md, encoding="utf-8").read().strip()
        if txt:
            print("### 一、核心记忆\n")
            print(txt[:6000])
            print()
    since = (now() - datetime.timedelta(days=args.days)).isoformat(timespec="seconds")
    con = ensure()
    rows = con.execute(
        "SELECT ts,kind,tags,body FROM mem WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
        (since, args.limit)).fetchall()
    if rows:
        print(f"### 二、最近 {args.days} 天事实（{len(rows)} 条）\n")
        for ts, kind, tags, body in rows:
            print(f"- {ts[:10]} [{kind}{'/'+tags if tags else ''}] {body[:200]}")
    else:
        print("### 二、最近事实\n（空）")


def digest(args):
    month = args.month or now().strftime("%Y-%m")
    con = ensure()
    rows = con.execute(
        "SELECT ts,kind,tags,body FROM mem WHERE ts LIKE ? ORDER BY ts", (month + "%",)).fetchall()
    out = [f"# {month} 记忆归档\n", f"条目数：{len(rows)}\n"]
    by_kind = {}
    for ts, kind, tags, body in rows:
        by_kind.setdefault(kind, []).append(f"- {ts[5:16]} {body[:160]}")
    for k, items in by_kind.items():
        out.append(f"\n## {k}（{len(items)}）\n")
        out.extend(items[:200])
        out.append("")
    fp = os.path.join(DIR, "archive", month + ".md")
    open(fp, "w", encoding="utf-8").write("\n".join(out))
    print(f"written {fp} rows={len(rows)}")


def stats(args):
    con = ensure()
    n = con.execute("SELECT count(*) FROM mem").fetchone()[0]
    first = con.execute("SELECT min(ts) FROM mem").fetchone()[0] or "-"
    last = con.execute("SELECT max(ts) FROM mem").fetchone()[0] or "-"
    size = sum(os.path.getsize(os.path.join(r, f))
               for r, _, fs in os.walk(DIR) for f in fs if os.path.exists(os.path.join(r, f)))
    print(f"dir={DIR}\nentries={n}\nfirst={first}\nlast={last}\nsize={size/1024:.1f}KB")


def main():
    p = argparse.ArgumentParser(prog="ai_mem")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add"); a.add_argument("text"); a.add_argument("--tags", default="")
    a.add_argument("--source", default=""); a.add_argument("--kind", default="fact"); a.set_defaults(f=add)

    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("-k", type=int, default=8)
    s.set_defaults(f=search)

    r = sub.add_parser("recent"); r.add_argument("-n", type=int, default=10); r.set_defaults(f=recent)

    rc = sub.add_parser("recall"); rc.add_argument("query"); rc.add_argument("-k", type=int, default=5)
    rc.set_defaults(f=recall)

    i = sub.add_parser("inject"); i.add_argument("--days", type=int, default=7)
    i.add_argument("--limit", type=int, default=40); i.set_defaults(f=inject)

    d = sub.add_parser("digest"); d.add_argument("--month"); d.set_defaults(f=digest)

    st = sub.add_parser("stats"); st.set_defaults(f=stats)

    args = p.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
