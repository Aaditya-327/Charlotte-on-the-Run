"""
feeds.py — Validated feed list, sorted by drive time from Charlotte NC.

Dead/removed (last checked 2026-04-21 via test_feeds.py):
  Charlotte on the Cheap   — was ParseError (CDATA) → now FIXED, re-added
  Charlotte Ledger         — HTTP 404 (Substack feed moved)
  CLT52 / Charlotte Five   — Timeout
  QCity Metro              — HTTP 404
  NoDa Neighborhood        — HTTP 404
  South End CLT            — HTTP 410
  Gaston Gazette           — HTTP 403
  Triad City Beat (main)   — Dropped: spam (attorney dirs, casino finance)
  Triad City Beat Arts     — HTTP 404 → switched to Culture category feed
  Triad Foodies            — HTTP 404
  Mountain Xpress Events   — HTTP 403
  AVL Today                — HTTP 404
  Ashvegas                 — ParseError (unclosed CDATA)
  Free Times Columbia      — HTTP 429
  Charlotte Magazine       — Dropped: 0% event ratio, avg score -0.2
  Arts & Science Council   — Dropped: only publishing job postings, not events
  WFAE Local/Arts          — HTTP 404
  WFDD Public Radio        — HTTP 404
  WRAL Out & About         — HTTP 404
  SECCA                    — HTTP 404
  Triangle Arts & Ent      — HTTP 404
  Charlotte Observer/N&O   — Timeout (paywalled McClatchy)
  Blumenthal Arts          — HTTP 404 (blog/rss path moved)
  Gantt Center             — PARSE_ERR (invalid XML)

priority 1 = every 6h  (pure event / high signal)
priority 2 = daily     (culture/events mix, good signal after filtering)
priority 3 = weekly    (background, lower event density)
"""

FEEDS = [
    # ── 0 MIN — Charlotte metro ───────────────────────────────────────────
    ("Charlotte",     "0min",    "Scoop Charlotte",
     "https://scoopcharlotte.com/feed/",
     1, ["events", "culture", "arts"]),

    ("Charlotte",     "0min",    "Queen City Nerve",
     "https://qcnerve.com/feed/",
     1, ["events", "arts", "culture"]),

    ("Charlotte",     "0min",    "Charlotte Ballet",
     "https://charlotteballet.org/feed/",
     1, ["events", "arts", "performance"]),

    ("Charlotte",     "0min",    "SouthPark Magazine",
     "https://southparkmagazine.com/feed/",
     1, ["events", "culture", "arts"]),

    ("Charlotte",     "0min",    "Charlotte Pride",
     "https://charlottepride.org/feed/",
     1, ["events", "community", "lgbtq"]),



    ("Charlotte",     "0min",    "Charlotte Parent",
     "https://www.charlotteparent.com/feed/",
     2, ["events", "family"]),

    ("Charlotte",     "0min",    "CLTtoday (6AM City)",
     "https://clttoday.6amcity.com/index.rss",
     2, ["events", "news", "culture"]),

    ("Charlotte",     "0min",    "QNotes Carolinas",
     "https://qnotescarolinas.com/feed/",
     2, ["events", "lgbtq", "community"]),

    ("Charlotte",     "0min",    "Mint Museum",
     "https://mintmuseum.org/feed/",
     2, ["events", "arts", "culture"]),

    ("Charlotte",     "0min",    "Unpretentious Palate",
     "https://unpretentiouspalate.com/feed/",
     2, ["food", "culture"]),

    ("Charlotte",     "0min",    "Charlotte on the Cheap",
     "https://www.charlotteonthecheap.com/feed/",
     1, ["events", "free", "community"]),

    ("Charlotte",     "0min",    "Charlotte Is Creative",
     "https://charlotteiscreative.com/feed/",
     1, ["events", "arts", "culture"]),

    # ── 1H — Piedmont Triad ───────────────────────────────────────────────
    ("Triad",         "1h",      "Triad City Beat (Culture)",
     "https://triad-city-beat.com/category/culture/feed/",
     1, ["events", "culture", "arts"]),

    ("Triad",         "1h",      "WStoday (6AM City)",
     "https://wstoday.6amcity.com/index.rss",
     2, ["events", "news", "culture"]),

    ("Triad",         "1h",      "Greensboro.com Entertainment",
     "https://greensboro.com/search/?f=rss&t=article&c=entertainment&l=50&s=start_time&sd=desc",
     2, ["events", "entertainment", "culture"]),

    ("Triad",         "1h",      "Reynolda House",
     "https://reynolda.org/feed/",
     2, ["events", "arts", "culture"]),

    ("Greenville SC", "1h30min", "Greenville Journal (Events)",
     "https://greenvillejournal.com/category/events/feed/",
     1, ["events", "arts", "culture"]),

    ("Greenville SC", "1h30min", "Greenville Journal (Arts)",
     "https://greenvillejournal.com/category/arts-culture/feed/",
     2, ["arts", "culture"]),

    ("Greenville SC", "1h30min", "GVLtoday (6AM City)",
     "https://gvltoday.6amcity.com/index.rss",
     2, ["events", "news", "culture"]),

    ("Greenville SC", "1h30min", "Town Carolina",
     "https://towncarolina.com/feed/",
     2, ["events", "culture", "community"]),

    ("Greenville SC", "2h",      "COLAtoday (6AM City)",
     "https://colatoday.6amcity.com/index.rss",
     2, ["events", "news", "culture"]),

    # ── 2H — Asheville / WNC ─────────────────────────────────────────────
    ("Asheville",     "2h",      "Mountain Xpress",
     "https://mountainx.com/feed/",
     2, ["events", "arts", "culture", "food"]),

    # ── 2H 30MIN — Triangle NC ───────────────────────────────────────────
    ("Triangle NC",   "2h30min", "Walter Magazine",
     "https://www.waltermagazine.com/feed/",
     1, ["events", "culture", "arts"]),

    ("Triangle NC",   "2h30min", "Triangle on the Cheap",
     "https://triangleonthecheap.com/feed/",
     1, ["events", "free", "community"]),

    ("Triangle NC",   "2h30min", "Raleigh Magazine",
     "https://raleighmag.com/feed/",
     2, ["events", "culture", "arts"]),

    ("Triangle NC",   "2h30min", "Durham Magazine",
     "https://durhammag.com/feed/",
     2, ["events", "culture", "arts"]),

    ("Triangle NC",   "2h30min", "INDY Week",
     "https://indyweek.com/feed",
     2, ["events", "culture", "arts"]),

    ("Triangle NC",   "2h30min", "RALtoday (6AM City)",
     "https://raltoday.6amcity.com/index.rss",
     2, ["events", "news", "culture"]),
]

DISTANCE_RANK = {"0min": 0, "30min": 1, "1h": 2, "1h30min": 3, "2h": 4, "2h30min": 5}

FEEDS_SORTED      = sorted(FEEDS, key=lambda x: DISTANCE_RANK.get(x[1], 9))
FEEDS_PRIORITY1   = [f for f in FEEDS_SORTED if f[4] == 1]
FEEDS_WITHIN_1H   = [f for f in FEEDS_SORTED if DISTANCE_RANK.get(f[1], 9) <= 2]
FEEDS_WITHIN_1H30 = [f for f in FEEDS_SORTED if DISTANCE_RANK.get(f[1], 9) <= 3]
