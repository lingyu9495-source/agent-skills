#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
revkit —— 合规逆向取数工具链（CDP 驱动，零第三方依赖：websockets + stdlib）

用途：当数据不在 HTML 里、而在"带签名参数的内部接口"后面时，
      用浏览器真实执行 + CDP 内核级观测，把请求样本、签名明文、算法还原出来。

子命令：
  launch                     起一个带 CDP 调试端口的 Chromium（返回 ws 地址）
  capture <url>              抓页面上所有 XHR/fetch 请求（含参数/头部/响应体）→ JSON
  breakread <url>            源码关键词定位 + 断点 + 命中后读调用帧局部变量（拿明文/盐）
  hooks <url>               注入 hook.js，回显被 hook 的加密/网络调用与控制台日志
  solve                     给定样本，暴力匹配签名算法（md5/sha/hmac × 拼接顺序 × 盐）
  replay                    复现一条抓到的请求（可自动刷新时间戳）

合规红线（必须遵守）：只用于你本人有权访问的数据（自有后台、公开页面、公开行情）；
  不绕付费墙、不碰个人敏感数据、不用于攻击。默认遵守目标站 robots/ToS。
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

CHROME = os.environ.get("REVKIT_CHROME", "<HERMES_HOME>")
DEFAULT_PORT = int(os.environ.get("REVKIT_PORT", "9333"))
DEFAULT_PROFILE = os.environ.get("REVKIT_PROFILE", "<HERMES_HOME>")


# ----------------------------------------------------------------------------
# 极简 CDP 客户端
# ----------------------------------------------------------------------------
class CDP:
    def __init__(self, ws_url, timeout=30):
        from websockets.sync.client import connect
        self.ws = connect(ws_url, max_size=256 * 1024 * 1024, open_timeout=timeout,
                          close_timeout=5, additional_headers={"Origin": "http://127.0.0.1"})
        self._id = 0
        self._events = []
        self._cv = threading.Condition()
        self._dead = False
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            for raw in self.ws:
                d = json.loads(raw)
                with self._cv:
                    self._events.append(d)
                    self._cv.notify_all()
        except Exception:
            with self._cv:
                self._dead = True
                self._cv.notify_all()

    def send(self, method, **params):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        return mid

    def wait_id(self, mid, timeout=30):
        end = time.time() + timeout
        with self._cv:
            while time.time() < end:
                for e in list(self._events):
                    if e.get("id") == mid:
                        self._events.remove(e)
                        if "error" in e:
                            raise RuntimeError(f"{e.get('error')}")
                        return e.get("result", {})
                self._cv.wait(0.1)
        raise TimeoutError(f"CDP id={mid} timeout")

    def call(self, method, timeout=30, **params):
        return self.wait_id(self.send(method, **params), timeout)

    def drain(self):
        with self._cv:
            ev = self._events
            self._events = []
            return ev

    def wait_event(self, method, timeout=30, pred=None):
        end = time.time() + timeout
        while time.time() < end:
            for e in self.drain():
                if e.get("method") == method and (pred is None or pred(e.get("params", {}))):
                    return e.get("params", {})
            time.sleep(0.05)
        return None

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def http_json(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def launch(port=DEFAULT_PORT, headed=False, profile=None):
    profile = profile or f"{DEFAULT_PROFILE}-{port}"
    # 已有实例直接复用（避免同 profile 锁冲突把新进程憋死）
    try:
        v = http_json(f"http://127.0.0.1:{port}/json/version", timeout=2)
        return v.get("webSocketDebuggerUrl")
    except Exception:
        pass
    os.makedirs(profile, exist_ok=True)
    flags = [
        CHROME, f"--remote-debugging-port={port}", "--remote-allow-origins=*",
        "--no-sandbox", "--disable-dev-shm-usage", "--no-first-run",
        "--no-default-browser-check", "--disable-background-networking",
        "--disable-sync", "--disable-features=Translate",
        "--enable-unsafe-swiftshader", f"--user-data-dir={profile}",
        "--window-size=1440,900",
    ]
    if not headed:
        flags += ["--headless=new", "--ozone-platform=headless"]
    flags.append("about:blank")
    subprocess.Popen(flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            v = http_json(f"http://127.0.0.1:{port}/json/version")
            return v.get("webSocketDebuggerUrl")
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("Chromium 启动超时（检查 REVKIT_CHROME 与 GUI 依赖库）")


def ensure_page_ws(a):
    """返回一个 page 级 CDP ws；没有就起一个浏览器再取。"""
    if getattr(a, "ws", None):
        return a.ws
    launch(a.port, headed=a.headed, profile=a.profile)
    return page_target(a.port)["webSocketDebuggerUrl"]


def page_target(port=DEFAULT_PORT):
    for _ in range(40):
        try:
            for t in http_json(f"http://127.0.0.1:{port}/json/list"):
                if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                    return t
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError("没有可用的 page target")


# ----------------------------------------------------------------------------
# capture：抓 XHR/fetch
# ----------------------------------------------------------------------------
INTERESTING = ("XHR", "Fetch")


def cmd_capture(a):
    ws = ensure_page_ws(a)
    c = CDP(ws)
    c.call("Page.enable")
    c.call("Runtime.enable")
    c.call("Network.enable")
    c.call("Page.navigate", url=a.url)
    time.sleep(a.wait)
    if a.eval:
        try:
            c.call("Runtime.evaluate", expression=a.eval, awaitPromise=True, timeout=25)
        except Exception as e:
            print(f"[warn] eval 失败: {e}", file=sys.stderr)
        time.sleep(a.wait)
    if a.click:
        c.call("Runtime.evaluate", expression=(
            "(()=>{const el=document.querySelector(%s);if(el)el.click();return !!el;})()" % json.dumps(a.click)))
        time.sleep(a.wait)

    reqs, order = {}, []
    for e in c.drain():
        m, p = e.get("method"), e.get("params", {})
        if m == "Network.requestWillBeSent":
            rid = p.get("requestId")
            reqs[rid] = {
                "kind": p.get("type"), "method": p["request"].get("method"),
                "url": p["request"].get("url"), "headers": p["request"].get("headers", {}),
                "postData": p["request"].get("postData"),
                "initiator": (p.get("initiator") or {}).get("stack", {}).get("callFrames", [])[:3],
            }
            order.append(rid)
        elif m == "Network.responseReceived":
            rid = p.get("requestId")
            if rid in reqs:
                reqs[rid]["status"] = p["response"].get("status")
                reqs[rid]["mimeType"] = p["response"].get("mimeType")

    out = []
    for rid in order:
        r = reqs.get(rid)
        if not r or r.get("kind") not in INTERESTING:
            continue
        if a.contains and a.contains not in (r.get("url") or ""):
            continue
        if a.with_body and r.get("kind") in INTERESTING:
            try:
                b = c.call("Network.getResponseBody", requestId=rid, timeout=10)
                r["body"] = (b.get("body") or "")[:4000]
            except Exception:
                pass
        out.append(r)

    print(f"# 抓到 {len(out)} 条 XHR/fetch 请求")
    for r in out:
        print(f"\n[{r.get('method')}] {r.get('url')}")
        if r.get("postData"):
            print(f"  body: {r['postData'][:300]}")
        if r.get("body"):
            print(f"  resp: {r['body'][:200]}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\n# 已保存 {a.out}")
    c.close()


# ----------------------------------------------------------------------------
# breakread：源码定位 + 断点 + 读调用帧
# ----------------------------------------------------------------------------
def cmd_breakread(a):
    ws = ensure_page_ws(a)
    c = CDP(ws, timeout=60)
    c.call("Page.enable")
    c.call("Runtime.enable")
    c.call("Debugger.enable")
    c.call("Page.navigate", url=a.url)
    time.sleep(a.wait)

    # 1) 收集已解析脚本
    scripts = {}
    for e in c.drain():
        if e.get("method") == "Debugger.scriptParsed":
            p = e["params"]
            scripts[p["scriptId"]] = p.get("url", "")
    if not scripts:
        for _ in range(int(a.wait / 0.2) + 20):
            got = False
            for e in c.drain():
                if e.get("method") == "Debugger.scriptParsed":
                    p = e["params"]
                    scripts[p["scriptId"]] = p.get("url", "")
                    got = True
            if got:
                break
            time.sleep(0.2)

    # 2) 找含关键词的脚本
    hits = []
    for sid, url in scripts.items():
        if a.script and a.script not in url:
            continue
        try:
            src = c.call("Debugger.getScriptSource", scriptId=sid, timeout=15).get("scriptSource", "")
        except Exception:
            continue
        if a.match and a.match in src:
            hits.append((sid, url, src))
    if not hits:
        print(f"[!] 没在已加载脚本里找到关键词 {a.match!r}（可加大 --wait，或换关键词）")
        for sid, url in list(scripts.items())[:20]:
            if url:
                print(f"    script: {url}")
        c.close()
        return

    sid, url, src = hits[0]
    print(f"[+] 命中脚本: {url or sid}  (scriptId={sid})")
    lines = src.split("\n")
    ln = next((i for i, L in enumerate(lines) if a.match in L), 0)
    col = lines[ln].find(a.match)
    for i in range(max(0, ln - 2), min(len(lines), ln + 3)):
        print(f"  {i + 1:>5}| {lines[i][:160]}")

    # 3) 按 URL 正则设断点（跨重建稳定）
    pat = re.escape(url) if url else r".*"
    bp = c.call("Debugger.setBreakpointByUrl", urlRegex=pat, lineNumber=ln,
                columnNumber=max(col, 0), timeout=15)
    print(f"[+] 断点已设: line {ln + 1} col {max(col, 0)}  -> {len(bp.get('locations', []))} 处命中位置")
    c.drain()

    # 4) 触发（页面会在断点处暂停，因此不等 evaluate 返回，直接发）
    trig = a.eval or "location.reload()"
    print(f"[+] 触发: {trig}", flush=True)
    c.send("Runtime.evaluate", expression=trig, awaitPromise=False)

    # 5) 等暂停，读调用帧
    paused = c.wait_event("Debugger.paused", timeout=a.timeout)
    if not paused:
        print("[!] 断点未命中（脚本可能没被触发，或代码走了另一条路径）")
        c.close()
        return
    print(f"[+] 断点命中，调用栈 {len(paused.get('callFrames', []))} 层：\n")
    exprs = [x for x in (a.expr or "").split(",") if x] or ["JSON.stringify(this)"]
    for i, fr in enumerate(paused.get("callFrames", [])[:a.depth]):
        name = fr.get("functionName") or "(anonymous)"
        loc = fr.get("location", {})
        print(f"  #{i} {name}  @line {loc.get('lineNumber', 0) + 1}")
        for ex in exprs:
            try:
                r = c.call("Debugger.evaluateOnCallFrame", callFrameId=fr["callFrameId"],
                           expression=ex, returnByValue=True, timeout=8)
                v = r.get("result", {}).get("value")
                if v is not None:
                    print(f"      {ex} = {str(v)[:400]}")
            except Exception as e:
                print(f"      {ex} -> {e}")
        # 打印作用域里的局部变量名（便于发现该读什么）
        try:
            scopes = [s for s in fr.get("scopeChain", []) if s.get("type") in ("local", "closure")]
            if scopes:
                names = c.call("Runtime.getProperties", objectId=scopes[0]["object"]["objectId"],
                               timeout=8).get("result", [])
                keys = [n["name"] for n in names if n.get("enumerable")]
                if keys:
                    print(f"      locals: {keys}")
        except Exception:
            pass
    c.call("Debugger.resume")
    c.close()


# ----------------------------------------------------------------------------
# hooks：注入 hook.js
# ----------------------------------------------------------------------------
def cmd_hooks(a):
    ws = ensure_page_ws(a)
    hook_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hook.js")
    hook_src = open(hook_path, encoding="utf-8").read()
    c = CDP(ws)
    c.call("Page.enable")
    c.call("Runtime.enable")
    c.call("Page.addScriptToEvaluateOnNewDocument", source=hook_src)
    c.call("Page.navigate", url=a.url)
    time.sleep(a.wait)
    if a.eval:
        try:
            c.call("Runtime.evaluate", expression=a.eval, awaitPromise=True, timeout=25)
        except Exception as e:
            print(f"[warn] eval: {e}", file=sys.stderr)
        time.sleep(a.wait)
    logs = []
    for e in c.drain():
        if e.get("method") == "Runtime.consoleAPICalled":
            p = e["params"]
            txt = " ".join(str(x.get("value", x.get("description", ""))) for x in p.get("args", []))
            logs.append(txt)
    print(f"# hook 命中 {len(logs)} 条")
    for t in logs[:a.limit]:
        print(" ", t[:500])
    c.close()


# ----------------------------------------------------------------------------
# solve：常见签名算法暴力匹配
# ----------------------------------------------------------------------------
def _h(name, data: bytes, key: bytes = None):
    if name == "md5":
        return hashlib.md5(data).hexdigest()
    if name == "sha1":
        return hashlib.sha1(data).hexdigest()
    if name == "sha256":
        return hashlib.sha256(data).hexdigest()
    if name.startswith("hmac"):
        alg = name.split("-")[1]
        return hmac.new(key or b"", data, getattr(hashlib, alg)).hexdigest()
    raise ValueError(name)


def _variants(params, secret):
    """生成常见"明文串"构造方式"""
    items_sorted = sorted((k, v) for k, v in params.items() if k != "sign")
    items_orig = [(k, v) for k, v in params.items() if k != "sign"]
    secs = [secret, ""] if secret is not None else [""]
    out = []
    for items in (items_sorted, items_orig):
        kvs = [f"{k}={v}" for k, v in items]
        for s in secs:
            base = [
                "&".join(kvs) + (f"&key={s}" if s else ""),
                "&".join(kvs) + (f"&secret={s}" if s else ""),
                "&".join(kvs) + s,
                s + "&".join(kvs),
                "".join(kvs) + s,
                "|".join(kvs) + s,
                json.dumps(dict(items), separators=(",", ":")) + s,
                json.dumps(dict(items), sort_keys=True, separators=(",", ":")) + s,
            ]
            out.extend(base)
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def cmd_solve(a):
    params = dict(urllib.parse.parse_qsl(a.params))
    target = (a.sign or "").strip()
    salts = [s for s in (a.salts or "").split(",") if s != ""] or [None]
    algs = a.algs.split(",") if a.algs else ["md5", "sha1", "sha256", "hmac-md5", "hmac-sha1", "hmac-sha256"]
    tried = 0
    for salt in salts:
        salt_b = salt.encode() if salt is not None else None
        for raw in _variants(params, salt):
            for alg in algs:
                try:
                    h = _h(alg, raw.encode("utf-8"), salt_b)
                except Exception:
                    continue
                tried += 1
                for cand, tag in ((h, "hex"), (h.upper(), "HEX"),
                                  (base64.b64encode(bytes.fromhex(h)).decode(), "b64")):
                    if cand == target:
                        print("### 命中 ###")
                        print(f"算法 : {alg}")
                        print(f"输出 : {tag}")
                        print(f"盐   : {salt!r}")
                        print("明文 : " + raw)
                        print(f"结果 : {cand}")
                        return
    print(f"[x] 未命中（试了 {tried} 种组合）。下一手：")
    print("    · 换 --salts 候选（盐常藏在 JS 的字符串数组里，用 breakread 抓明文最稳）")
    print("    · 用 breakread 在签名函数处断点，直接读明文/中间值")
    print("    · 可能含时间戳/nonce/固定前缀，或输出被截取(前 N 位/大写)")


# ----------------------------------------------------------------------------
# replay：复现请求
# ----------------------------------------------------------------------------
def cmd_replay(a):
    rec = json.load(open(a.file, encoding="utf-8")) if a.file else json.loads(a.json)
    if isinstance(rec, list):
        rec = next((r for r in rec if a.contains is None or a.contains in r["url"]), rec[0])
    url = rec["url"]
    if a.refresh_ts:
        url = re.sub(r"([?&](?:ts|_t|timestamp|time)=\d+)", lambda m: re.sub(r"\d+", str(int(time.time() * 1000)), m.group(1)), url)
    headers = {k: v for k, v in (rec.get("headers") or {}).items()
               if k.lower() not in ("content-length", "host", "cookie", ":authority")}
    data = rec.get("postData")
    if data is not None:
        data = data.encode()
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method=rec.get("method", "GET"))
    try:
        with urllib.request.urlopen(req, timeout=a.timeout) as r:
            body = r.read().decode("utf-8", "replace")
            print(f"HTTP {r.status}\n{body[:1500]}")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}\n{e.read().decode('utf-8', 'replace')[:800]}")


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="revkit 逆向取数工具链")
    ap.add_argument("--ws", help="已有 CDP ws 地址（不给则自动 launch）")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--profile", default=None, help="浏览器 profile 目录（默认按端口隔离）")
    ap.add_argument("--headed", action="store_true", help="显示浏览器窗口")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("launch"); p.set_defaults(fn=lambda a: print(launch(a.port, a.headed, a.profile)))

    p = sub.add_parser("capture")
    p.add_argument("url"); p.add_argument("--wait", type=float, default=3.0)
    p.add_argument("--eval", default=None, help="加载后执行的 JS（触发请求）")
    p.add_argument("--click", default=None, help="加载后点击的 CSS 选择器")
    p.add_argument("--contains", default=None, help="只留 URL 含此串的请求")
    p.add_argument("--with-body", action="store_true"); p.add_argument("--out")
    p.set_defaults(fn=cmd_capture)

    p = sub.add_parser("breakread")
    p.add_argument("url"); p.add_argument("--match", required=True, help="脚本源码里的关键词，如 md5( 或 sign")
    p.add_argument("--script", default=None, help="限定 URL 含此串的脚本")
    p.add_argument("--expr", default=None, help="命中后在每层调用帧求值的表达式，逗号分隔")
    p.add_argument("--depth", type=int, default=6); p.add_argument("--wait", type=float, default=4.0)
    p.add_argument("--timeout", type=float, default=25.0)
    p.add_argument("--eval", default=None, help="触发表达式（默认 location.reload()）")
    p.set_defaults(fn=cmd_breakread)

    p = sub.add_parser("hooks")
    p.add_argument("url"); p.add_argument("--wait", type=float, default=4.0)
    p.add_argument("--eval", default=None); p.add_argument("--limit", type=int, default=60)
    p.set_defaults(fn=cmd_hooks)

    p = sub.add_parser("solve")
    p.add_argument("--params", required=True, help="原始参数串 a=1&b=2（不含 sign）")
    p.add_argument("--sign", required=True, help="目标签名值")
    p.add_argument("--salts", default="", help="候选盐，逗号分隔")
    p.add_argument("--algs", default="")
    p.set_defaults(fn=cmd_solve)

    p = sub.add_parser("replay")
    p.add_argument("--file"); p.add_argument("--json"); p.add_argument("--contains", default=None)
    p.add_argument("--refresh-ts", action="store_true"); p.add_argument("--timeout", type=float, default=20)
    p.set_defaults(fn=cmd_replay)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
