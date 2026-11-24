#!/usr/bin/env python3
"""ai_mem — 零依赖共享记忆底座（L1 档）
只依赖 Python3 标准库 + sqlite3(FTS5)。一个目录，多个智能体共用。

目录（默认 ~/.ai-memory，可用 AI_MEM_DIR 覆盖）：
  MEMORY.md        热层：身份、铁律、偏好、团队共识（人机共写，建议 ≤8KB）
  facts/*.jsonl    温层：结构化事实（时间/内容/标签/来源）
  archive/*.md     冷层：按月归档摘要
  index.db         FTS5 全文索引

命令：
  add "内容" [--tags a,b] [--source x|--as 智能体名] [--kind fact|pref|event|knowledge]
  search "关键词" [-k 8] [--source x] [--kind k]
  recall "整句话" [--source x] [--kind k]
  recent [-n 10] [--source x]
  inject [--days 7]        输出可直接塞进提示的记忆块（按来源分组，含团队知识点）
  digest [--month 2026-11] 生成月度归档摘要
  sources                  谁在用这个底座、各记了多少、最后一次是什么时候
  stats
"""
import argparse, json, os, sqlite3, sys, datetime, re, hashlib

DIR = os.environ.get("AI_MEM_DIR", os.path.expanduser("~/.ai-memory"))
DB = os.path.join(DIR, "index.db")
AGENT = os.environ.get("AI_MEM_AGENT", "cli")


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


def _filters(args, alias=""):
    """把 --source / --kind 拼成 WHERE 片段（同时用于过滤和分组）。"""
    pre = alias + "." if alias else ""
    sql, vals = [], []
    src = getattr(args, "source", "") or ""
    kind = getattr(args, "kind", "") or ""
    if src:
        sql.append(f"{pre}source = ?")
        vals.append(src)
    if kind:
        sql.append(f"{pre}kind = ?")
        vals.append(kind)
    return (" AND " + " AND ".join(sql)) if sql else "", vals


def add(args):
    con = ensure()
    body = args.text.strip()
    if not body:
        sys.exit("empty text")
    rid = hashlib.sha1((body + str(now())).encode()).hexdigest()[:16]
    ts = now().isoformat(timespec="seconds")
    tags = ",".join(t.strip() for t in args.tags.split(",")) if args.tags else ""
    source = (getattr(args, "as_agent", "") or args.source or AGENT or "cli").strip()
    con.execute("INSERT INTO mem(rid,ts,kind,tags,source,body) VALUES (?,?,?,?,?,?)",
                (rid, ts, args.kind, tags, source, body))
    con.commit()
    # 温层落盘（与索引同源，便于迁移与人审）
    fp = os.path.join(DIR, "facts", now().strftime("%Y-%m") + ".jsonl")
    with open(fp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"rid": rid, "ts": ts, "kind": args.kind, "tags": tags,
                            "source": source, "body": body}, ensure_ascii=False) + "\n")
    print(f"ok {rid}")


def search(args):
    con = ensure()
    q = args.query.strip()
    terms = [t for t in re.split(r"[\s,，]+", q) if t]
    expr = " OR ".join('"' + t.replace('"', '""') + '"' for t in terms) or '""'
    where, vals = _filters(args)
    try:
        rows = con.execute(
            f"SELECT ts,kind,tags,source,body FROM mem WHERE mem MATCH ?{where} ORDER BY rank LIMIT ?",
            (expr, *vals, args.k)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    if not rows:
        rows = con.execute(
            f"SELECT ts,kind,tags,source,body FROM mem WHERE body LIKE ?{where} ORDER BY ts DESC LIMIT ?",
            (f"%{q}%", *vals, args.k)).fetchall()
    if not rows:
        print("(no hit)")
        return
    for ts, kind, tags, source, body in rows:
        print(f"[{ts[:16]}] ({kind}{'/'+tags if tags else ''} @{source}) {body[:300]}")


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
    where, vals = _filters(args)
    clause = " OR ".join(["body LIKE ?"] * len(grams))
    rows = con.execute(
        f"SELECT ts,kind,tags,source,body FROM mem WHERE ({clause}){where} ORDER BY ts DESC LIMIT 500",
        (*[f"%{g}%" for g in grams], *vals)).fetchall()
    scored = []
    for ts, kind, tags, source, body in rows:
        s = sum(1 for g in grams if g in body)
        s += sum(0.5 for g in grams if len(g) >= 3 and g in body)
        if s >= 1:
            scored.append((s, ts, kind, tags, source, body))
    scored.sort(key=lambda r: (-r[0], r[1]))
    if not scored:
        print("(no hit)")
        return
    for s, ts, kind, tags, source, body in scored[:args.k]:
        print(f"[{ts[:16]}] ({kind}{'/'+tags if tags else ''} @{source}) {body[:300]}")


def recent(args):
    con = ensure()
    where, vals = _filters(args)
    for ts, kind, source, body in con.execute(
            f"SELECT ts,kind,source,body FROM mem WHERE 1=1{where} ORDER BY ts DESC LIMIT ?",
            (*vals, args.n)):
        print(f"[{ts[:16]}] ({kind} @{source}) {body[:200]}")


def inject(args):
    """输出记忆块，供提示注入。热层优先，其后是近 N 天事实，按来源分组。"""
    mem_md = os.path.join(DIR, "MEMORY.md")
    print("## 长期记忆（自动注入）\n")
    if os.path.exists(mem_md):
        txt = open(mem_md, encoding="utf-8").read().strip()
        if txt:
            print("### 一、核心记忆\n")
            print(txt[:6000])
            print()
    con = ensure()
    since = (now() - datetime.timedelta(days=args.days)).isoformat(timespec="seconds")

    # 知识点单独一段：跨智能体沉淀的结论与方法，优先级高于流水事实
    kn = con.execute(
        "SELECT ts,tags,source,body FROM mem WHERE ts >= ? AND kind='knowledge' ORDER BY ts DESC LIMIT ?",
        (since, args.limit)).fetchall()
    if kn:
        print(f"### 二、团队知识点（{len(kn)} 条）\n")
        for ts, tags, source, body in kn:
            print(f"- {ts[:10]} [{tags or '未分类'} @{source}] {body[:220]}")
        print()

    rows = con.execute(
        "SELECT ts,kind,tags,source,body FROM mem WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
        (since, args.limit)).fetchall()
    rows = [r for r in rows if r[1] != "knowledge"]
    if rows:
        by_src = {}
        for r in rows:
            by_src.setdefault(r[3] or "cli", []).append(r)
        print(f"### 三、最近 {args.days} 天事实（{len(rows)} 条 / {len(by_src)} 个智能体）\n")
        for src, items in sorted(by_src.items(), key=lambda kv: -len(kv[1])):
            print(f"**@{src}**（{len(items)} 条）")
            for ts, kind, tags, s, body in items[:12]:
                print(f"- {ts[:10]} [{kind}{'/'+tags if tags else ''}] {body[:200]}")
            print()
    else:
        print("### 三、最近事实\n（空）")


def digest(args):
    month = args.month or now().strftime("%Y-%m")
    con = ensure()
    rows = con.execute(
        "SELECT ts,kind,tags,source,body FROM mem WHERE ts LIKE ? ORDER BY ts", (month + "%",)).fetchall()
    out = [f"# {month} 记忆归档\n", f"条目数：{len(rows)}\n"]
    srcs = {}
    for _, _, _, s, _ in rows:
        srcs[s] = srcs.get(s, 0) + 1
    if srcs:
        out.append("来源分布：" + "，".join(f"{k} {v}" for k, v in sorted(srcs.items(), key=lambda kv: -kv[1])) + "\n")
    by_kind = {}
    for ts, kind, tags, source, body in rows:
        by_kind.setdefault(kind, []).append(f"- {ts[5:16]} [@{source}] {body[:160]}")
    for k, items in by_kind.items():
        out.append(f"\n## {k}（{len(items)}）\n")
        out.extend(items[:200])
        out.append("")
    fp = os.path.join(DIR, "archive", month + ".md")
    open(fp, "w", encoding="utf-8").write("\n".join(out))
    print(f"written {fp} rows={len(rows)}")


def sources(args):
    """团队视图：谁在用这个底座、各记了多少、最后一次记了什么。"""
    con = ensure()
    rows = con.execute(
        "SELECT source,count(*),max(ts) FROM mem GROUP BY source ORDER BY count(*) DESC").fetchall()
    if not rows:
        print("(空底座：还没有任何智能体写入)")
        return
    total = sum(r[1] for r in rows)
    print(f"底座：{DIR}\n共 {len(rows)} 个智能体 / {total} 条记忆\n")
    print(f"{'智能体':<14}{'条数':>6}  最后写入")
    for src, n, last in rows:
        tail = con.execute(
            "SELECT body FROM mem WHERE source=? ORDER BY ts DESC LIMIT 1", (src,)).fetchone()
        print(f"{src:<14}{n:>6}  {last[:16]}  {(tail[0][:36] if tail else '')}")
    kn = con.execute("SELECT count(*) FROM mem WHERE kind='knowledge'").fetchone()[0]
    print(f"\n其中知识点（kind=knowledge）：{kn} 条")


def stats(args):
    con = ensure()
    n = con.execute("SELECT count(*) FROM mem").fetchone()[0]
    first = con.execute("SELECT min(ts) FROM mem").fetchone()[0] or "-"
    last = con.execute("SELECT max(ts) FROM mem").fetchone()[0] or "-"
    agents = con.execute("SELECT count(DISTINCT source) FROM mem").fetchone()[0]
    size = sum(os.path.getsize(os.path.join(r, f))
               for r, _, fs in os.walk(DIR) for f in fs if os.path.exists(os.path.join(r, f)))
    print(f"dir={DIR}\nentries={n}\nagents={agents}\nfirst={first}\nlast={last}\nsize={size/1024:.1f}KB")


def main():
    p = argparse.ArgumentParser(prog="ai_mem")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add"); a.add_argument("text"); a.add_argument("--tags", default="")
    a.add_argument("--source", default=""); a.add_argument("--as", dest="as_agent", default="")
    a.add_argument("--kind", default="fact"); a.set_defaults(f=add)

    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("-k", type=int, default=8)
    s.add_argument("--source", default=""); s.add_argument("--kind", default=""); s.set_defaults(f=search)

    r = sub.add_parser("recent"); r.add_argument("-n", type=int, default=10)
    r.add_argument("--source", default=""); r.set_defaults(f=recent)

    rc = sub.add_parser("recall"); rc.add_argument("query"); rc.add_argument("-k", type=int, default=5)
    rc.add_argument("--source", default=""); rc.add_argument("--kind", default=""); rc.set_defaults(f=recall)

    i = sub.add_parser("inject"); i.add_argument("--days", type=int, default=7)
    i.add_argument("--limit", type=int, default=40); i.set_defaults(f=inject)

    d = sub.add_parser("digest"); d.add_argument("--month"); d.set_defaults(f=digest)

    so = sub.add_parser("sources"); so.set_defaults(f=sources)
    tm = sub.add_parser("team"); tm.set_defaults(f=sources)

    st = sub.add_parser("stats"); st.set_defaults(f=stats)

    args = p.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
