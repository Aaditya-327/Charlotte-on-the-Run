#!/usr/bin/env python3
"""
test_feeds.py — Probe all candidate feeds and report which are live + event-quality.

Usage:
    python3 test_feeds.py
"""

import urllib.request, urllib.error, xml.etree.ElementTree as ET
import re, time, sys
from datetime import datetime, timezone, timedelta

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CLT-Events-Bot/1.0)"}
TIMEOUT = 12

CANDIDATES = [
    # (name, url, region, distance)
    ("Queen City Nerve",              "https://qcnerve.com/feed/",                                    "Charlotte",    "0min"),
    ("QNotes Carolinas",              "https://qnotescarolinas.com/feed/",                            "Charlotte",    "0min"),
    ("Charlotte Magazine",            "https://www.charlottemagazine.com/feed/",                      "Charlotte",    "0min"),
    ("Charlotte Ledger",              "https://charlotteledger.substack.com/feed",                    "Charlotte",    "0min"),
    ("CLT52 / Charlotte Five",        "https://www.charlotteobserver.com/charlottefive/?service=rss", "Charlotte",    "0min"),
    ("Unpretentious Palate",          "https://unpretentiouspalate.com/feed/",                        "Charlotte",    "0min"),
    ("Charlotte Is Creative",         "https://charlotteiscreative.com/feed/",                        "Charlotte",    "0min"),
    ("WFAE Arts & Culture",           "https://www.wfae.org/arts-culture/index.rss",                  "Charlotte",    "0min"),
    ("CLTtoday (6AM City)",           "https://clttoday.6amcity.com/index.rss",                       "Charlotte",    "0min"),
    ("QCity Metro",                   "https://qcitymetro.com/feed/",                                 "Charlotte",    "0min"),
    ("Scoop Charlotte",               "https://scoopcharlotte.com/feed/",                             "Charlotte",    "0min"),
    ("Charlotte Pride",               "https://charlottepride.org/feed/",                             "Charlotte",    "0min"),
    ("Pride Magazine Online",         "https://pridemagazineonline.com/feed/",                        "Charlotte",    "0min"),
    ("Charlotte Gaymers Network",     "https://www.charlottegaymersnetwork.com/feed/",                "Charlotte",    "0min"),
    ("Charlotte LGBTQ+ Chamber",      "https://clgbtcc.org/feed/",                                    "Charlotte",    "0min"),
    ("Stonewall Sports Charlotte",    "https://stonewallcharlotte.org/feed/",                         "Charlotte",    "0min"),
    ("PFLAG Charlotte",               "https://pflagcharlotte.org/feed/",                             "Charlotte",    "0min"),
    ("RAIN Charlotte",                "https://www.rain.org/feed/",                                   "Charlotte",    "0min"),
    ("Charlotte Black Pride",         "https://charlotteblackpride.org/feed/",                        "Charlotte",    "0min"),
    ("Beer Me Charlotte",             "https://beermecharlotte.com/feed/",                            "Charlotte",    "0min"),
    ("Work For Your Beer",            "https://www.workforyourbeer.com/feed/",                        "Charlotte",    "0min"),
    ("NC Beer Guys",                  "https://ncbeerguys.com/feed/",                                 "Charlotte",    "0min"),
    ("Charlotte Coffee Culture",      "https://charlottecoffeeculture.com/feed/",                     "Charlotte",    "0min"),
    ("Charlotte Wine + Food",         "https://charlottewineandfood.org/feed/",                       "Charlotte",    "0min"),
    ("QC Foodie",                     "https://qcfoodie.com/feed/",                                   "Charlotte",    "0min"),
    ("NC Brewers Guild",              "https://ncbeer.org/feed/",                                     "Charlotte",    "0min"),
    ("Blumenthal Performing Arts",    "https://www.blumenthalarts.org/blog/rss",                      "Charlotte",    "0min"),
    ("Mint Museum",                   "https://mintmuseum.org/feed/",                                 "Charlotte",    "0min"),
    ("Harvey B. Gantt Center",        "https://ganttcenter.org/feed/",                                "Charlotte",    "0min"),
    ("Arts & Science Council",        "https://artsandscience.org/feed/",                             "Charlotte",    "0min"),
    ("NoDa Neighborhood",             "https://noda.org/feed/",                                       "Charlotte",    "0min"),
    ("Charlotte Symphony",            "https://charlottesymphony.org/feed/",                          "Charlotte",    "0min"),
    ("Bechtler Museum",               "https://bechtler.org/feed/",                                   "Charlotte",    "0min"),
    ("McColl Center",                 "https://mccollcenter.org/feed/",                               "Charlotte",    "0min"),
    ("Charlotte Ballet",              "https://charlotteballet.org/feed/",                            "Charlotte",    "0min"),
    ("SouthPark Magazine",            "https://southparkmagazine.com/feed/",                          "Charlotte",    "0min"),
    ("South End CLT",                 "https://southendclt.org/feed/",                                "Charlotte",    "0min"),
    ("Plaza Midwood Community",       "https://plazamidwood.org/feed/",                               "Charlotte",    "0min"),
    ("Mountain Xpress (Asheville)",   "https://mountainx.com/feed/",                                  "Asheville",    "2h"),
    ("Triad City Beat",               "https://triad-city-beat.com/feed/",                            "Triad",        "1h"),
    ("INDY Week",                     "https://indyweek.com/feed/",                                   "Triangle NC",  "2h30min"),
    ("Greenville Journal",            "https://greenvillejournal.com/feed/",                          "Greenville SC","1h30min"),
    ("Free Times Columbia",           "https://www.postandcourier.com/free-times/search/?f=rss",      "Columbia SC",  "2h"),
    ("Ashvegas",                      "https://ashvegas.com/feed/",                                   "Asheville",    "2h"),
    ("GVLtoday (6AM City)",           "https://gvltoday.6amcity.com/index.rss",                       "Greenville SC","1h30min"),
    ("RALtoday (6AM City)",           "https://raltoday.6amcity.com/index.rss",                       "Triangle NC",  "2h30min"),
    ("Our State Magazine",            "https://www.ourstate.com/feed/",                               "NC",           "varies"),
    ("Walter Magazine",               "https://www.waltermagazine.com/feed/",                         "Triangle NC",  "2h30min"),
    ("Charlotte Business Journal",    "https://www.bizjournals.com/charlotte/rss",                    "Charlotte",    "0min"),
    ("Charlotte Parent",              "https://www.charlotteparent.com/feed/",                        "Charlotte",    "0min"),
]

EVENT_KW = {
    "festival":4,"concert":4,"show":3,"exhibit":3,"exhibition":3,
    "tour":2,"market":3,"fair":3,"workshop":3,"lecture":2,
    "free":2,"ticket":3,"admission":3,"opening":3,"performance":4,
    "race":2,"walk":2,"gala":3,"fundraiser":2,"screening":3,
    "tasting":3,"happy hour":2,"trivia":2,"open mic":3,
    "comedy":3,"dance":3,"class":2,"parade":3,"art walk":4,
    "beer":2,"wine":2,"food truck":3,"pop-up":2,"family":2,
}
NEWS_KW = {
    "police":3,"arrest":3,"shooting":3,"crash":3,"fire":2,
    "obituary":4,"weather":2,"stocks":3,"earnings":3,"legislation":3,
    "lawsuit":3,"traffic":2,"accident":3,"court":2,"crime":3,
}

def score(title, desc):
    text = (title + " " + desc).lower()
    s = sum(w for kw, w in EVENT_KW.items() if kw in text)
    s -= sum(w for kw, w in NEWS_KW.items() if kw in text)
    if re.search(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', text): s += 2
    if re.search(r'\b\d{1,2}:\d{2}\s*(am|pm)\b', text): s += 3
    if re.search(r'\$\d+', text): s += 2
    return s

def clean(s):
    return re.sub(r'<[^>]+>', '', s or '').strip()

def check(name, url):
    try:
        req  = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        raw  = resp.read(400_000)
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:60]}"

    if not any(b in raw for b in [b"<rss", b"<feed", b"<channel", b"<?xml"]):
        return None, "Not XML / no feed"

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        return None, f"ParseError: {str(e)[:50]}"

    NS_ATOM    = "http://www.w3.org/2005/Atom"
    NS_CONTENT = "http://purl.org/rss/1.0/modules/content/"

    def _first(*els):
        for e in els:
            if e is not None: return e
        return None

    items = []
    for tag in ("item", f"{{{NS_ATOM}}}entry"):
        for item in root.iter(tag):
            t = _first(item.find("title"), item.find(f"{{{NS_ATOM}}}title"))
            d = _first(item.find("description"),
                       item.find(f"{{{NS_CONTENT}}}encoded"),
                       item.find(f"{{{NS_ATOM}}}summary"))
            title = clean(t.text if t is not None else "")
            desc  = clean(d.text if d is not None else "")[:300]
            if title:
                items.append({"title": title, "desc": desc, "score": score(title, desc)})

    return items, None

def main():
    now = datetime.now(timezone.utc)
    live, dead = [], []

    print(f"\nTesting {len(CANDIDATES)} feeds...\n")
    print(f"{'#':<3} {'Name':<32} {'Region':<14} {'Status':<6} {'Items':>5} {'Ev%':>5} {'AvgSc':>6}")
    print("─" * 80)

    for i, (name, url, region, dist) in enumerate(CANDIDATES, 1):
        items, err = check(name, url)
        if err or items is None:
            status = "❌"
            print(f"{i:<3} {name:<32} {region:<14} {status} {err}")
            dead.append((name, url, region, dist, err))
            time.sleep(0.3)
            continue

        total    = len(items)
        ev_items = [it for it in items if it["score"] > 0]
        ev_pct   = len(ev_items) / total if total else 0
        avg_sc   = sum(it["score"] for it in items) / total if total else 0
        flag     = "✅" if ev_pct >= 0.30 else ("⚠️ " if ev_pct >= 0.10 else "〰️")

        print(f"{i:<3} {name:<32} {region:<14} {flag} {total:>5} {ev_pct:>4.0%} {avg_sc:>6.1f}")

        if ev_items:
            for t in ev_items[:3]:
                print(f"     • {t['title'][:75]}")

        live.append({
            "name": name, "url": url, "region": region, "distance": dist,
            "total": total, "ev_items": len(ev_items),
            "ev_pct": round(ev_pct, 3), "avg_score": round(avg_sc, 2),
            "samples": [it["title"] for it in ev_items[:5]],
        })
        time.sleep(0.35)

    print(f"\n{'─'*60}")
    print(f"✅ Live: {len(live)}   ❌ Dead: {len(dead)}")

    print("\n── DEAD FEEDS ──────────────────────────────────────────────")
    for name, url, region, dist, err in dead:
        print(f"  {name:<32} {err}")

    print("\n── TOP EVENT FEEDS (ev% ≥ 30%) ─────────────────────────────")
    for f in sorted(live, key=lambda x: -x["ev_pct"]):
        if f["ev_pct"] >= 0.30:
            print(f"  {f['name']:<32} {f['region']:<14} ev={f['ev_pct']:.0%}  avg={f['avg_score']:.1f}")
            for s in f["samples"][:2]:
                print(f"     • {s[:75]}")

if __name__ == "__main__":
    main()
