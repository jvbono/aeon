#!/usr/bin/env python3
"""Parse RSS/Atom feeds, extract last 48h entries."""
import os
import re
import json
import glob
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

FEED_NAMES = {
    "cbc_politics": "CBC Politics",
    "canadaland": "Canadaland",
    "globe_opinion": "Globe and Mail Opinion",
    "the_tyee": "The Tyee",
    "walrus_politics": "The Walrus Politics",
    "ipolitics": "iPolitics",
    "breach_media": "Breach Media",
    "pluralistic": "Pluralistic",
    "disconnect": "Disconnect",
    "michael_geist": "Michael Geist",
    "policy_options": "Policy Options",
    "priv_canada": "Privacy Commissioner of Canada",
    "the_markup": "The Markup",
    "eff": "EFF",
    "betakit": "BetaKit",
    "citation_needed": "Citation Needed",
    "jwz": "JWZ",
    "schneier": "Schneier on Security",
    "joan_westenberg": "Joan Westenberg",
    "ed_zitron": "Ed Zitron",
    "convivial": "The Convivial Society",
    "contraptions": "Contraptions",
    "fourzerofour": "404 Media",
    "platformer": "Platformer",
    "garbage_day": "Garbage Day",
    "tech_policy_press": "Tech Policy Press",
    "techdirt": "Techdirt",
    "robin_sloan": "Robin Sloan",
    "ted_gioia": "Ted Gioia",
    "dada_drummer": "Dada Drummer",
    "aquarium_drunkard": "Aquarium Drunkard",
    "interdependence": "Interdependence",
    "metalabel": "Metalabel",
    "new_models": "New Models",
    "kneeling_bus": "Kneeling Bus",
    "real_life": "Real Life",
    "nplusone": "n+1",
    "unpopular_front": "Unpopular Front",
    "yancey_strickler": "Yancey Strickler",
}

NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(hours=48)

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            s2 = s.replace("Z", "+0000")
            dt = datetime.strptime(s2, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return None


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"&quot;", '"', s)
    s = re.sub(r"&#39;", "'", s)
    s = re.sub(r"&lt;", "<", s)
    s = re.sub(r"&gt;", ">", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_feed(path, key):
    try:
        with open(path, "rb") as f:
            data = f.read()
        if len(data) < 100:
            return []
        root = ET.fromstring(data)
    except Exception as e:
        return []

    items = []
    # RSS 2.0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        date_str = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
        desc = item.findtext("description") or ""
        content = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
        dt = parse_date(date_str)
        if not dt or dt < CUTOFF:
            continue
        items.append({
            "title": strip_html(title),
            "link": link,
            "date": dt.isoformat(),
            "summary": strip_html(content or desc)[:600],
            "feed": FEED_NAMES.get(key, key),
        })
    # Atom
    for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
        title = (entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
        link_el = entry.find("{http://www.w3.org/2005/Atom}link")
        link = link_el.get("href") if link_el is not None else ""
        date_str = entry.findtext("{http://www.w3.org/2005/Atom}published") or entry.findtext("{http://www.w3.org/2005/Atom}updated") or ""
        summary = entry.findtext("{http://www.w3.org/2005/Atom}summary") or ""
        content = entry.findtext("{http://www.w3.org/2005/Atom}content") or ""
        dt = parse_date(date_str)
        if not dt or dt < CUTOFF:
            continue
        items.append({
            "title": strip_html(title),
            "link": link,
            "date": dt.isoformat(),
            "summary": strip_html(content or summary)[:600],
            "feed": FEED_NAMES.get(key, key),
        })
    return items


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    all_items = []
    feed_counts = {}
    for path in sorted(glob.glob(os.path.join(base, "*.xml"))):
        key = os.path.basename(path).replace(".xml", "")
        if key == "test":
            continue
        items = parse_feed(path, key)
        feed_counts[FEED_NAMES.get(key, key)] = len(items)
        all_items.extend(items)
    all_items.sort(key=lambda x: x["date"], reverse=True)
    with open(os.path.join(base, "items.json"), "w") as f:
        json.dump({"items": all_items, "counts": feed_counts, "cutoff": CUTOFF.isoformat(), "now": NOW.isoformat()}, f, indent=2)
    print(f"Total items: {len(all_items)}")
    print(f"Feeds with items: {sum(1 for v in feed_counts.values() if v > 0)}")
    print(f"Feeds with zero items: {sum(1 for v in feed_counts.values() if v == 0)}")
    for fname, count in sorted(feed_counts.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"  {fname}: {count}")


if __name__ == "__main__":
    main()
