#!/usr/bin/env python3
"""
test_feeds.py — Probe all 100 candidate feeds and produce a ranked report.

Output columns:
  STATUS  : OK / TIMEOUT / HTTP-NNN / PARSE_ERR / EMPTY
  ITEMS   : number of items in feed
  SCORE   : rough event-keyword density (0-10)
  REGION  : geographic region
  NAME    : feed label
  URL     : the feed URL

Usage:
  python test_feeds.py              # human-readable table
  python test_feeds.py --csv        # machine-readable CSV
  python test_feeds.py --add        # print feeds.py snippets for live high-signal feeds
  python test_feeds.py --workers 30 # tune concurrency (default 20)
"""

import argparse, io, sys
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── All 100 candidate feeds ──────────────────────────────────────────────────

CANDIDATES = [
    # ── Charlotte Core (0 min) ──────────────────────────────────────────────
    ("Charlotte", "0min", "Charlotte Observer Local",         "https://www.charlotteobserver.com/news/local/?service=rss"),
    ("Charlotte", "0min", "Charlotte Observer Entertainment", "https://www.charlotteobserver.com/entertainment/?service=rss"),
    ("Charlotte", "0min", "Queen City Nerve",                 "https://qcnerve.com/feed/"),
    ("Charlotte", "0min", "Charlotte Magazine",               "https://www.charlottemagazine.com/feed/"),
    ("Charlotte", "0min", "Charlotte Ledger (Substack)",      "https://charlotteledger.substack.com/feed"),
    ("Charlotte", "0min", "Unpretentious Palate",             "https://unpretentiouspalate.com/feed/"),
    ("Charlotte", "0min", "Charlotte Is Creative",            "https://charlotteiscreative.com/feed/"),
    ("Charlotte", "0min", "QCity Metro",                      "https://qcitymetro.com/feed/"),
    ("Charlotte", "0min", "WFAE Local News",                  "https://www.wfae.org/local-news/index.rss"),
    ("Charlotte", "0min", "WFAE Arts & Culture",              "https://www.wfae.org/arts-culture/index.rss"),
    ("Charlotte", "0min", "QNotes Carolinas",                 "https://qnotescarolinas.com/feed/"),
    ("Charlotte", "0min", "Charlotte Pride",                  "https://charlottepride.org/feed/"),
    ("Charlotte", "0min", "Scoop Charlotte",                  "https://scoopcharlotte.com/feed/"),
    ("Charlotte", "0min", "CLTtoday (6AM City)",              "https://clttoday.6amcity.com/index.rss"),
    ("Charlotte", "0min", "Charlotte on the Cheap",           "https://www.charlotteonthecheap.com/feed/"),
    ("Charlotte", "0min", "Biz Journals Charlotte",           "https://www.bizjournals.com/charlotte/rss"),
    ("Charlotte", "0min", "Business NC",                      "https://businessnc.com/feed/"),
    ("Charlotte", "0min", "WSOC-TV Local",                    "https://www.wsoctv.com/arc/outboundfeeds/rss/category/news/local/"),
    ("Charlotte", "0min", "WBTV News",                        "https://www.wbtv.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("Charlotte", "0min", "SouthPark Magazine",               "https://southparkmagazine.com/feed/"),
    ("Charlotte", "0min", "Plaza Midwood",                    "https://plazamidwood.org/feed/"),
    ("Charlotte", "0min", "NoDa Neighborhood",                "https://noda.org/feed/"),
    ("Charlotte", "0min", "South End CLT",                    "https://southendclt.org/feed/"),
    ("Charlotte", "0min", "Beer Me Charlotte",                "https://beermecharlotte.com/feed/"),
    ("Charlotte", "0min", "NC Beer Guys",                     "https://ncbeerguys.com/feed/"),
    ("Charlotte", "0min", "QC Foodie",                        "https://qcfoodie.com/feed/"),
    ("Charlotte", "0min", "Blumenthal Arts",                  "https://www.blumenthalarts.org/blog/rss"),
    ("Charlotte", "0min", "Mint Museum",                      "https://mintmuseum.org/feed/"),
    ("Charlotte", "0min", "Gantt Center",                     "https://ganttcenter.org/feed/"),
    ("Charlotte", "0min", "Bechtler Museum",                  "https://bechtler.org/feed/"),
    ("Charlotte", "0min", "Charlotte Symphony",               "https://charlottesymphony.org/feed/"),
    ("Charlotte", "0min", "Charlotte Ballet",                 "https://charlotteballet.org/feed/"),
    ("Charlotte", "0min", "McColl Center",                    "https://mccollcenter.org/feed/"),
    ("Charlotte", "0min", "PFLAG Charlotte",                  "https://pflagcharlotte.org/feed/"),
    ("Charlotte", "0min", "Charlotte Black Pride",            "https://charlotteblackpride.org/feed/"),
    ("Charlotte", "0min", "Arts & Science Council",           "https://artsandscience.org/feed/"),
    ("Charlotte", "0min", "Work For Your Beer",               "https://www.workforyourbeer.com/feed/"),
    ("Charlotte", "0min", "Charlotte Gaymers Network",        "https://www.charlottegaymersnetwork.com/feed/"),
    ("Charlotte", "0min", "Charlotte Coffee Culture",         "https://charlottecoffeeculture.com/feed/"),
    ("Charlotte", "0min", "Restaurant Traffic",               "http://restauranttraffic.com/feed/"),

    # ── Triad (1h - 1h30m) ──────────────────────────────────────────────────
    ("Triad", "1h", "Triad City Beat Culture",    "https://triad-city-beat.com/category/culture/feed/"),
    ("Triad", "1h", "Yes! Weekly",                "https://yesweekly.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc"),
    ("Triad", "1h", "Journal Now Local",          "https://journalnow.com/search/?f=rss&t=article&c=news/local&l=50&s=start_time&sd=desc"),
    ("Triad", "1h", "Journal Now Entertainment",  "https://journalnow.com/search/?f=rss&t=article&c=entertainment&l=50&s=start_time&sd=desc"),
    ("Triad", "1h", "Greensboro.com Ent",         "https://greensboro.com/search/?f=rss&t=article&c=entertainment&l=50&s=start_time&sd=desc"),
    ("Triad", "1h", "WFDD Public Radio",          "https://www.wfdd.org/rss.xml"),
    ("Triad", "1h", "Piedmont Parent",            "https://www.piedmontparent.com/feed/"),
    ("Triad", "1h", "WStoday (6AM City)",         "https://wstoday.6amcity.com/index.rss"),
    ("Triad", "1h", "Triad Foodies",              "https://triadfoodies.com/feed/"),
    ("Triad", "1h", "Winston-Salem Monthly",      "https://www.winstonsalemmonthly.com/feed/"),
    ("Triad", "1h", "SECCA",                      "https://secca.org/feed/"),
    ("Triad", "1h", "Reynolda House",             "https://reynolda.org/feed/"),
    ("Triad", "1h", "Triad Moms on Main",         "https://triadmomsonmain.com/feed/"),
    ("Triad", "1h", "The Carolinian (UNCG)",      "https://carolinianuncg.com/feed/"),
    ("Triad", "1h", "High Point Discovered",      "https://highpointdiscovered.org/feed/"),

    # ── Triangle (2h - 2h30m) ───────────────────────────────────────────────
    ("Triangle NC", "2h30min", "INDY Week",                   "https://indyweek.com/feed/"),
    ("Triangle NC", "2h30min", "RALtoday (6AM City)",         "https://raltoday.6amcity.com/index.rss"),
    ("Triangle NC", "2h30min", "Walter Magazine",             "https://www.waltermagazine.com/feed/"),
    ("Triangle NC", "2h30min", "Raleigh Magazine",            "https://raleighmag.com/feed/"),
    ("Triangle NC", "2h30min", "Triangle on the Cheap",       "https://triangleonthecheap.com/feed/"),
    ("Triangle NC", "2h30min", "Bites of Bull City",          "https://bitesofbullcity.com/feed/"),
    ("Triangle NC", "2h30min", "WRAL Out & About",            "https://www.wral.com/entertainment/out_and_about/rss/58/"),
    ("Triangle NC", "2h30min", "Durham Magazine",             "https://durhammag.com/feed/"),
    ("Triangle NC", "2h30min", "Chapel Hill Magazine",        "https://chapelhillmagazine.com/feed/"),
    ("Triangle NC", "2h30min", "WUNC Public Radio",           "https://www.wunc.org/index.rss"),
    ("Triangle NC", "2h30min", "NC Museum of Art",            "https://ncartmuseum.org/feed/"),
    ("Triangle NC", "2h30min", "Triangle Arts & Ent",         "https://triangleartsandentertainment.org/feed/"),
    ("Triangle NC", "2h30min", "Carolina Parent",             "https://www.carolinaparent.com/feed/"),
    ("Triangle NC", "2h30min", "News & Observer Ent",         "https://www.newsobserver.com/entertainment/?service=rss"),
    ("Triangle NC", "2h30min", "Discover Durham",             "https://www.discoverdurham.com/blog/rss/"),

    # ── Western NC / Asheville (2h) ──────────────────────────────────────────
    ("Asheville", "2h", "Mountain Xpress",              "https://mountainx.com/feed/"),
    ("Asheville", "2h", "Ashvegas",                     "https://ashvegas.com/feed/"),
    ("Asheville", "2h", "AVLtoday (6AM City)",          "https://avltoday.6amcity.com/index.rss"),
    ("Asheville", "2h", "Blue Ridge Public Radio",      "https://www.bpr.org/index.rss"),
    ("Asheville", "2h", "Asheville Citizen-Times Ent",  "https://rssfeeds.citizen-times.com/asheville/entertainment"),
    ("Asheville", "2h", "Edible Asheville",             "https://edibleasheville.com/feed/"),
    ("Asheville", "2h", "Explore Asheville Blog",       "https://www.exploreasheville.com/blog/rss/"),
    ("Asheville", "2h", "Haywood County Press",         "https://www.hcpress.com/feed"),
    ("Asheville", "2h", "Watauga Democrat",             "https://www.wataugademocrat.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc"),
    ("Asheville", "2h", "Asheville Art Museum",         "https://www.ashevilleart.org/feed/"),
    ("Asheville", "2h", "Romantic Asheville Blog",      "https://www.romanticasheville.com/blog/feed"),
    ("Asheville", "2h", "The Laurel of Asheville",      "https://thelaurelofasheville.com/feed/"),
    ("Asheville", "2h", "NC Health News",               "https://www.northcarolinahealthnews.org/feed/"),
    ("Asheville", "2h", "Asheville Downtown Assoc",     "https://ashevilledowntown.org/feed/"),
    ("Asheville", "2h", "Carolina Public Press",        "https://carolinapublicpress.org/feed/"),

    # ── SC Upstate & Midlands (1h30m - 2h) ──────────────────────────────────
    ("Greenville SC", "1h30min", "Greenville Journal",        "https://greenvillejournal.com/feed/"),
    ("Greenville SC", "1h30min", "GVLtoday (6AM City)",       "https://gvltoday.6amcity.com/index.rss"),
    ("Greenville SC", "1h30min", "Upstate Business Journal",  "https://upstatebusinessjournal.com/feed/"),
    ("Greenville SC", "1h30min", "Free Times (P&C)",          "https://www.postandcourier.com/free-times/search/?f=rss"),
    ("Greenville SC", "2h",      "COLAtoday (6AM City)",      "https://colatoday.6amcity.com/index.rss"),
    ("Greenville SC", "1h30min", "Edible Upcountry",          "https://edibleupcountry.com/feed/"),
    ("Greenville SC", "1h30min", "GoUpstate (Spartanburg)",   "https://rssfeeds.goupstate.com/spartanburg/home"),
    ("Greenville SC", "2h",      "The State Entertainment",   "https://www.thestate.com/entertainment/?service=rss"),
    ("Greenville SC", "1h30min", "Greenville Online",         "https://rssfeeds.greenvilleonline.com/greenville/home"),
    ("Greenville SC", "2h",      "SC Public Radio",           "https://www.southcarolinapublicradio.org/index.rss"),
    ("Greenville SC", "2h",      "Columbia Museum of Art",    "https://www.columbiamuseum.org/feed"),
    ("Greenville SC", "1h30min", "Town Carolina",             "https://towncarolina.com/feed/"),
    ("Greenville SC", "2h",      "Experience Columbia SC",    "https://www.experiencecolumbiasc.com/blog/rss/"),
    ("Greenville SC", "1h30min", "Visit Greenville SC",       "https://www.visitgreenvillesc.com/blog/rss/"),
    ("Greenville SC", "1h30min", "Hub City (Spartanburg)",    "https://www.hubcity.org/feed"),
]

# ── Event keyword set ────────────────────────────────────────────────────────

EVENT_KW = [
    "festival", "concert", "show", "exhibit", "exhibition", "tour",
    "market", "fair", "workshop", "lecture", "free", "ticket",
    "admission", "opening", "performance", "race", "walk", "gala",
    "fundraiser", "screening", "tasting", "happy hour", "trivia",
    "open mic", "comedy", "dance", "class", "parade", "art walk",
    "beer", "wine", "food truck", "pop-up", "family", "kids",
    "live music", "gallery",
]

TIMEOUT = 10
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CLT-FeedTester/1.0)"}


def score_text(text: str) -> float:
    if not text:
        return 0.0
    t = text.lower()
    hits = sum(1 for kw in EVENT_KW if kw in t)
    return round(hits / len(EVENT_KW) * 10, 2)


def probe(candidate: tuple) -> dict:
    region, distance, name, url = candidate
    result = {
        "region": region, "distance": distance, "name": name, "url": url,
        "status": "UNKNOWN", "items": 0, "ev_score": 0.0,
        "sample": [], "error": "",
    }
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            result["status"] = f"OK-{resp.status}"
    except urllib.error.HTTPError as e:
        result["status"] = f"HTTP-{e.code}"
        result["error"] = str(e)
        return result
    except urllib.error.URLError as e:
        reason = str(e.reason)
        result["status"] = "TIMEOUT" if "timed out" in reason.lower() else "URL-ERR"
        result["error"] = reason[:80]
        return result
    except Exception as e:
        result["status"] = "ERR"
        result["error"] = str(e)[:80]
        return result

    # Parse
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        result["status"] = "PARSE_ERR"
        result["error"] = str(e)[:80]
        return result

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item") or root.findall(".//atom:entry", ns)
    result["items"] = len(items)
    if not items:
        result["status"] = "EMPTY"
        return result

    scores = []
    for item in items[:10]:
        title = (item.findtext("title") or
                 item.findtext("atom:title", namespaces=ns) or "")
        desc  = (item.findtext("description") or
                 item.findtext("atom:summary", namespaces=ns) or
                 item.findtext("atom:content", namespaces=ns) or "")
        scores.append(score_text(title + " " + desc))
        if len(result["sample"]) < 3 and title.strip():
            result["sample"].append(title.strip()[:72])

    result["ev_score"] = round(sum(scores) / len(scores), 2) if scores else 0.0
    return result


def main():
    parser = argparse.ArgumentParser(description="Probe 100 candidate feeds")
    parser.add_argument("--csv",     action="store_true", help="CSV output")
    parser.add_argument("--add",     action="store_true", help="Print feeds.py snippets for live high-signal feeds")
    parser.add_argument("--workers", type=int, default=20)
    args = parser.parse_args()

    print(f"Probing {len(CANDIDATES)} feeds ({args.workers} threads)…", file=sys.stderr)

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(probe, c): c for c in CANDIDATES}
        done = 0
        for f in as_completed(futures):
            done += 1
            r = f.result()
            results.append(r)
            bar = "✅" if r["status"].startswith("OK") else "❌"
            print(f"  {bar} [{done:3}/{len(CANDIDATES)}] {r['status']:<12} {r['name']}", file=sys.stderr)

    results.sort(key=lambda r: (0 if r["status"].startswith("OK") else 1, -r["ev_score"]))

    # ── CSV ──────────────────────────────────────────────────────────────────
    if args.csv:
        import csv
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["status","items","ev_score","region","distance","name","url","error","sample"])
        for r in results:
            w.writerow([r["status"], r["items"], r["ev_score"],
                        r["region"], r["distance"], r["name"], r["url"],
                        r["error"], " | ".join(r["sample"])])
        print(out.getvalue())
        return

    # ── Human table ──────────────────────────────────────────────────────────
    live = [r for r in results if r["status"].startswith("OK")]
    dead = [r for r in results if not r["status"].startswith("OK")]

    hdr = f"{'ST':<12} {'ITEMS':>5} {'SCORE':>5}  {'REGION':<16} {'NAME':<35} URL"
    sep = "─" * 130

    print(f"\n{sep}")
    print(f"{'LIVE FEEDS':^130}")
    print(sep)
    print(hdr)
    print(sep)
    for r in live:
        print(f"{'✅ '+r['status']:<12} {r['items']:>5} {r['ev_score']:>5.2f}  "
              f"{r['region']:<16} {r['name']:<35} {r['url']}")
        for s in r["sample"]:
            print(f"   {'':49}· {s}")

    print(f"\n{sep}")
    print(f"{'DEAD / BROKEN':^130}")
    print(sep)
    for r in dead:
        print(f"{'❌ '+r['status']:<12} {'':>5} {'':>5}  "
              f"{r['region']:<16} {r['name']:<35} {r['url']}")
        if r["error"]:
            print(f"   {'':49}! {r['error']}")

    print(f"\n{sep}")
    print(f"Total: {len(results)}  |  Live: {len(live)}  |  Dead: {len(dead)}")
    high = [r for r in live if r["ev_score"] >= 1.5]
    print(f"High event-signal (score ≥ 1.5): {len(high)}")
    print(f"\nTop 10 by event score:")
    for r in sorted(live, key=lambda x: -x["ev_score"])[:10]:
        print(f"  {r['ev_score']:>5.2f}  {r['region']:<16} {r['name']}")

    # ── --add ────────────────────────────────────────────────────────────────
    if args.add:
        print("\n\n# ── Paste into feeds.py (high-signal live feeds) ───────────\n")
        for r in sorted(high, key=lambda x: (-x["ev_score"], x["distance"])):
            print(f'    ("{r["region"]}", "{r["distance"]}", "{r["name"]}",')
            print(f'     "{r["url"]}",')
            print(f'     2, ["events", "culture"]),\n')


if __name__ == "__main__":
    main()
