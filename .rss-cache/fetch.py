#!/usr/bin/env python3
"""Parallel-fetch all feeds from memory/feeds.yml using urllib."""
import os
import sys
import urllib.request
import urllib.error
import re
import yaml
import concurrent.futures
import socket

socket.setdefaulttimeout(20)

ROOT = "/home/runner/work/aeon/aeon"
RAW = os.path.join(ROOT, ".rss-cache", "raw")
os.makedirs(RAW, exist_ok=True)

with open(os.path.join(ROOT, "memory", "feeds.yml")) as f:
    feeds = yaml.safe_load(f)["feeds"]

def safe(name):
    return re.sub(r"[^A-Za-z0-9]", "_", name)

def fetch(feed):
    name, url = feed["name"], feed["url"]
    safe_name = safe(name)
    out = os.path.join(RAW, f"{safe_name}.xml")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; Aeon-RSS/1.0)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
            with open(out, "wb") as f:
                f.write(data)
            return (name, len(data), None)
    except Exception as e:
        return (name, 0, str(e))

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    results = list(ex.map(fetch, feeds))

ok = sum(1 for _, n, e in results if n > 100 and e is None)
fail = [(n, e) for n, sz, e in results if e is not None]
small = [(n, sz) for n, sz, e in results if e is None and sz <= 100]

print(f"OK: {ok}/{len(feeds)}")
if fail:
    print("FAILED:")
    for n, e in fail:
        print(f"  {n}: {e}")
if small:
    print("EMPTY:")
    for n, sz in small:
        print(f"  {n}: {sz} bytes")
