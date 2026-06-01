#!/usr/bin/env python3
"""Parse RSS/Atom XML files in .rss-cache/raw/ and emit recent entries as JSON."""
import os
import re
import json
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
import yaml
import html

ROOT = "/home/runner/work/aeon/aeon"
RAW = os.path.join(ROOT, ".rss-cache", "raw")

# Cutoff: 48h to be a bit generous given variable cron timing
NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(hours=48)

# Map safe_name -> feed name from feeds.yml
with open(os.path.join(ROOT, "memory", "feeds.yml")) as f:
    feeds = yaml.safe_load(f)["feeds"]
name_map = {re.sub(r"[^A-Za-z0-9]", "_", f["name"]): f["name"] for f in feeds}

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        # ISO 8601
        if re.match(r"\d{4}-\d{2}-\d{2}T", s):
            s2 = s.replace("Z", "+00:00")
            return datetime.fromisoformat(s2)
        # RFC 822
        return parsedate_to_datetime(s)
    except Exception:
        return None

def clean(txt):
    if not txt:
        return ""
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = html.unescape(txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def parse_feed(path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
        if len(raw) < 200 or not (b"<rss" in raw or b"<feed" in raw or b"<rdf:" in raw.lower() or b"<Rss" in raw):
            return None, []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            # Try to strip BOM/whitespace
            raw = raw.lstrip()
            root = ET.fromstring(raw)
    except Exception as e:
        return None, [f"parse_error: {e}"]

    items = []
    tag = root.tag.lower()
    # RSS 2.0
    if tag.endswith("rss") or tag.endswith("rdf"):
        channel = root.find("channel") or root
        for item in channel.findall("item") or root.findall(".//{http://purl.org/rss/1.0/}item"):
            title = clean((item.findtext("title") or "").strip())
            link = (item.findtext("link") or "").strip()
            desc = item.findtext("description") or item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
            pub = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
            dt = parse_date(pub)
            items.append({"title": title, "link": link, "desc": clean(desc)[:600], "date": dt})
    # Atom
    elif tag.endswith("feed"):
        for entry in root.findall("atom:entry", NS) or root.findall("entry"):
            title = clean((entry.findtext("atom:title", default="", namespaces=NS) or entry.findtext("title") or ""))
            link = ""
            for ln in entry.findall("atom:link", NS) or entry.findall("link"):
                if ln.get("rel") in (None, "alternate"):
                    link = ln.get("href", "")
                    break
            summary = entry.findtext("atom:summary", default="", namespaces=NS) or entry.findtext("summary") or ""
            content = entry.findtext("atom:content", default="", namespaces=NS) or entry.findtext("content") or ""
            desc = summary or content
            pub = entry.findtext("atom:published", default="", namespaces=NS) or entry.findtext("atom:updated", default="", namespaces=NS) or entry.findtext("published") or entry.findtext("updated") or ""
            dt = parse_date(pub)
            items.append({"title": title, "link": link, "desc": clean(desc)[:600], "date": dt})
    else:
        return None, [f"unknown_root: {tag}"]
    return items, []

results = {}
errors = []
total_in_window = 0
total_all = 0
for fname in sorted(os.listdir(RAW)):
    if not fname.endswith(".xml"):
        continue
    safe_name = fname[:-4]
    feed_name = name_map.get(safe_name, safe_name)
    path = os.path.join(RAW, fname)
    items, errs = parse_feed(path)
    if items is None:
        errors.append((feed_name, errs[0] if errs else "no_items"))
        continue
    recent = []
    for it in items:
        total_all += 1
        if it["date"] is None:
            continue
        # Some feeds have naive datetimes
        d = it["date"]
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        if d >= CUTOFF:
            total_in_window += 1
            recent.append({
                "title": it["title"],
                "link": it["link"],
                "desc": it["desc"],
                "date": d.isoformat(),
            })
    if recent:
        results[feed_name] = sorted(recent, key=lambda x: x["date"], reverse=True)

out = {
    "now": NOW.isoformat(),
    "cutoff": CUTOFF.isoformat(),
    "feed_count": len([x for x in os.listdir(RAW) if x.endswith('.xml')]),
    "feeds_with_recent": len(results),
    "total_entries": total_all,
    "total_recent": total_in_window,
    "errors": errors,
    "feeds": results,
}
out_path = os.path.join(ROOT, ".rss-cache", "parsed.json")
with open(out_path, "w") as f:
    json.dump(out, f, indent=2, default=str)
# Also write a short summary for the agent
summary = {
    "feed_count": out["feed_count"],
    "feeds_with_recent": out["feeds_with_recent"],
    "total_recent": out["total_recent"],
    "errors": errors,
    "feed_names_with_recent": list(results.keys()),
}
print(json.dumps(summary, indent=2, default=str))
