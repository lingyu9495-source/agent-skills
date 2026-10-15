#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""so.com (360) search helper: extract result titles + descriptions.

Usage:
    python so_search.py "关键词 关键词 2026" output.txt

Prints first 3000 chars of results to stdout, writes full results (max 10)
to output.txt. Result links are so.com /link?m=... redirects — fetch the
target separately if you need the full page.
"""
import sys, re, html, urllib.parse, subprocess

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

def fetch(url):
    try:
        out = subprocess.run(
            ["curl", "-sL", "-m", "25", url,
             "-H", f"User-Agent: {UA}",
             "-H", "Accept-Language: zh-CN,zh;q=0.9"],
            capture_output=True, text=True, timeout=40).stdout
    except Exception as e:
        return ""
    return out

def clean(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html.unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def search(query):
    url = "https://www.so.com/s?q=" + urllib.parse.quote(query)
    t = fetch(url)
    results = []
    for m in re.finditer(
        r'<h3[^>]*class="[^"]*res-title[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>\s*</h3>(.*?)(?=<h3|$)',
        t, flags=re.S):
        href, title, rest = m.group(1), clean(m.group(2)), m.group(3)
        ab = re.search(r'class="[^"]*res-desc[^"]*"[^>]*>(.*?)</p>', rest, flags=re.S)
        if not ab:
            ab = re.search(r'class="[^"]*res-desc[^"]*"[^>]*>(.*?)</div>', rest, flags=re.S)
        abstract = clean(ab.group(1)) if ab else ""
        if title:
            results.append((title, abstract, href))
    return results

if __name__ == "__main__":
    query = sys.argv[1]
    outfile = sys.argv[2] if len(sys.argv) > 2 else "search_result.txt"
    results = search(query)
    lines = []
    for i, (title, abstract, href) in enumerate(results[:10], 1):
        lines.append(f"[{i}] {title}\n    {abstract}\n    src: {href}")
    body = "\n".join(lines)
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(body)
    print(body[:3000] if body else "NO RESULTS")
