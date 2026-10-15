#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve so.com /link?m= redirect -> fetch real page -> print title + dates + keyword contexts.

Usage:
    python fetch_article.py "<so.com link or direct URL>" "关键词1,关键词2"

Why: so.com search result links are JS redirects (window.location.replace). This script
resolves them, fetches the real article with encoding fallback (utf-8 -> gbk -> gb18030,
many Chinese gov/media sites like cnr.cn are GBK), and prints the title, date-like
snippets, and ±120-char context around each keyword so you can verify wording without
dumping the whole page into context.

Verified 2026-08: 央广网 cnr.cn (GBK), 中国驻外使馆官网 tj.china-embassy.gov.cn (UTF-8),
腾讯新闻 news.qq.com, 新华网. so.com redirects are UNRELIABLE — may point at a different
article than the snippet promised; always check the printed TITLE.
"""
import sys, re, html, subprocess

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

def curl(url):
    cmd = ["curl", "-sL", "-m", "25", url, "-H", f"User-Agent: {UA}", "-H", "Accept-Language: zh-CN,zh;q=0.9"]
    try:
        raw = subprocess.run(cmd, capture_output=True, timeout=40).stdout
        for enc in ("utf-8", "gbk", "gb18030"):
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, UnicodeError):
                continue
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def resolve(link):
    if not link.startswith("http"):
        return None
    t = curl(link)
    m = re.search(r'window\.location\.replace\("([^"]+)"\)', t)
    return m.group(1) if m else None

def clean(s):
    s = re.sub(r'<script.*?</script>', ' ', s, flags=re.S)
    s = re.sub(r'<style.*?</style>', ' ', s, flags=re.S)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html.unescape(s)
    return re.sub(r'\s+', ' ', s).strip()

def main():
    link = sys.argv[1]
    kws = sys.argv[2].split(",") if len(sys.argv) > 2 else []
    real = resolve(link)
    print("REAL_URL:", real if real else "(direct)")
    t = curl(real if real else link)
    if not t:
        print("FETCH_FAILED")
        return
    m = re.search(r'<title[^>]*>(.*?)</title>', t, re.S)
    print("TITLE:", clean(m.group(1)) if m else "?")
    body = clean(t)
    for dm in re.finditer(r'(20\d\d[-年/]\d{1,2}[-月/]\d{1,2}日?)', body[:3000]):
        print("DATE_HIT:", dm.group(1))
    text = body[:12000]
    for kw in kws:
        idx, cnt = 0, 0
        while cnt < 3:
            i = text.find(kw, idx)
            if i < 0:
                break
            print(f"[{kw}] ...{text[max(0,i-120):i+180]}...")
            idx = i + len(kw)
            cnt += 1
    print("BODYLEN:", len(body))

if __name__ == "__main__":
    main()
