#!/usr/bin/env python3
"""
validate_feeds.py — Run locally to test every feed and score event quality.

Usage:
    python3 validate_feeds.py
    python3 validate_feeds.py --write-only   # only save feeds_live.json, no verbose

Output:
    feeds_live.json  — feeds that returned valid XML
    feeds_dead.json  — feeds that failed
    Prints a ranked table showing event signal quality for each live feed.
"""

import urllib.request, urllib.error, xml.etree.ElementTree as ET
import json, re, hashlib, time, sys
from feeds import FEEDS_SORTED

HEADERS  = {"User-Agent": "Mozilla/5.0 (compatible; CLT-Events-Bot/1.0)"}
TIMEOUT  = 12
VERBOSE  = "--write-only" not in sys.argv

# ── Event scorer ─────────────────────────────────────────────────────────────

EVENT_KW = {
    "festival":4, "concert":4, "show":3, "exhibit":3, "exhibition":3,
    "tour":2, "market":3, "fair":3, "workshop":3, "lecture":2,
    "free":2, "ticket":3, "admission":3, "opening":3, "performance":4,
    "competition":2, "race":2, "walk":2, "gala":3, "fundraiser":2,
    "screening":3, "tasting":3, "happy hour":2, "trivia":2, "open mic":3,
    "comedy":3, "dance":3, "class":2, "seminar":2, "parade":3,
    "art walk":4, "beer":2, "wine":2, "food truck":3, "pop-up":2,
    "sale":1, "family":2, "kids":2, "free admission":4, "no charge":3,
}

NEWS_KW = {
    "police":3, "arrest":3, "shooting":3, "crash":3, "fire":2,
    "obituary":4, "obituaries":4, "weather":2, "forecast":2,
    "stocks":3, "earnings":3, "budget":2, "tax":1, "legislation":3,
    "lawsuit":3, "indictment":3, "election":2, "vote":2, "traffic":2,
    "accident":3, "court":2, "crime":3, "breaking":2,
}

def score_item(title, desc):
    text = (title + " " + desc).lower()
    score = 0
    for kw, w in EVENT_KW.items():
        if kw in text: score += w
    for kw, w in NEWS_KW.items():
        if kw in text: score -= w
    # date/time patterns add weight
    if re.search(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', text): score += 2
    if re.search(r'\b\d{1,2}:\d{2}\s*(am|pm)\b', text): score += 3
    if re.search(r'\$\d+', text): score += 2
    return score

def clean(s):
    return re.sub(r'<[^>]+>', '', s or '').strip()

# ── Feed checker ─────────────────────────────────────────────────────────────

def check_feed(url):
    try:
        req  = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        raw  = resp.read(300_000)
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:60]}"

    if not any(b in raw for b in [b"<rss", b"<feed", b"<channel", b"<?xml"]):
        return None, "Not XML"

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        return None, f"ParseError: {e}"

    def _first(*els):
        for e in els:
            if e is not None:
                return e
        return None

    items = []
    for tag in ("item", "{http://www.w3.org/2005/Atom}entry"):
        for item in root.iter(tag):
            t_el = _first(item.find("title"),
                          item.find("{http://www.w3.org/2005/Atom}title"))
            d_el = _first(item.find("description"),
                          item.find("{http://purl.org/rss/1.0/modules/content/}encoded"),
                          item.find("{http://www.w3.org/2005/Atom}summary"))
            p_el = _first(item.find("pubDate"),
                          item.find("{http://www.w3.org/2005/Atom}updated"))
            l_el = _first(item.find("link"),
                          item.find("{http://www.w3.org/2005/Atom}link"))

            title = clean(t_el.text if t_el is not None else "")
            if not title:
                continue
            desc  = clean(d_el.text if d_el is not None else "")[:400]
            pub   = (p_el.text or "").strip() if p_el is not None else ""
            link  = (
                (l_el.text or l_el.get("href", "")).strip()
                if l_el is not None else ""
            )

            sig   = hashlib.sha256((title.lower() + pub[:10]).encode()).hexdigest()[:16]
            items.append({
                "title": title, "desc": desc, "pub": pub,
                "link": link, "sig": sig,
                "ev_score": score_item(title, desc),
            })

    return items, None

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    live, dead = [], []
    scores     = {}          # feed_name → avg event score
    seen_sigs  = set()       # global dedup across all feeds

    if VERBOSE:
        print(f"\nChecking {len(FEEDS_SORTED)} feeds...\n")
        print(f"{'#':<3} {'Region':<16} {'Drive':<9} {'Name':<36} {'HTTP':<5} {'Items':>5} {'Event%':>7} {'AvgSc':>6} {'NewSigs':>8}")
        print("─" * 100)

    for i, (region, dist, name, url, priority, tags) in enumerate(FEEDS_SORTED, 1):
        items, err = check_feed(url)
        if err or items is None:
            if VERBOSE:
                print(f"{i:<3} {region:<16} {dist:<9} {name:<36} ❌ {err}")
            dead.append({"region": region, "distance": dist, "name": name,
                         "url": url, "error": err, "priority": priority, "tags": tags})
            time.sleep(0.3)
            continue

        total   = len(items)
        ev_items= [it for it in items if it["ev_score"] > 0]
        ev_ratio= len(ev_items) / total if total else 0
        avg_sc  = sum(it["ev_score"] for it in items) / total if total else 0

        # Count new (not-yet-seen) signatures
        new_count = sum(1 for it in items if it["sig"] not in seen_sigs)
        for it in items:
            seen_sigs.add(it["sig"])

        scores[name] = avg_sc

        entry = {
            "region": region, "distance": dist, "name": name,
            "url": url, "priority": priority, "tags": tags,
            "total_items": total,
            "event_items": len(ev_items),
            "event_ratio": round(ev_ratio, 3),
            "avg_event_score": round(avg_sc, 2),
            "new_sigs": new_count,
            "sample_titles": [it["title"] for it in ev_items[:5]],
        }
        live.append(entry)

        if VERBOSE:
            bar  = "█" * int(ev_ratio * 8)
            flag = "✅" if ev_ratio >= 0.35 else ("⚠️ " if ev_ratio >= 0.10 else "❌")
            print(f"{i:<3} {region:<16} {dist:<9} {name:<36} {flag} {total:>5} {ev_ratio:>6.0%} {avg_sc:>6.1f} {new_count:>8}  {bar}")

        time.sleep(0.35)

    # ── Summary ──────────────────────────────────────────────────────────

    if VERBOSE:
        print(f"\n{'─'*60}")
        print(f"✅ Live: {len(live)}   ❌ Dead: {len(dead)}   "
              f"🔑 Unique sigs across all feeds: {len(seen_sigs)}")

        low_signal = [e for e in live if e["event_ratio"] < 0.10]
        if low_signal:
            print(f"\n⚠️  LOW SIGNAL (event_ratio < 10%) — consider dropping:")
            for e in low_signal:
                print(f"   {e['name']:<36} ratio={e['event_ratio']:.0%}  avg_score={e['avg_event_score']}")

        print("\n── Sample titles from top event feeds ──────────────────────────")
        for e in sorted(live, key=lambda x: -x["avg_event_score"])[:6]:
            print(f"\n▶ {e['name']} ({e['distance']}) — {e['event_items']}/{e['total_items']} events, avg_score={e['avg_event_score']}")
            for t in e["sample_titles"][:3]:
                print(f"   • {t[:80]}")

    with open("feeds_live.json", "w") as f:
        json.dump(live, f, indent=2)
    with open("feeds_dead.json", "w") as f:
        json.dump(dead, f, indent=2)

    if VERBOSE:
        print(f"\nSaved feeds_live.json ({len(live)}) and feeds_dead.json ({len(dead)})")
        print("Commit feeds_live.json to your repo.")

if __name__ == "__main__":
    main()
