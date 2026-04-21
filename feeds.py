"""
feeds.py — Validated feed list, sorted by drive time from Charlotte NC.

Dead/removed (tested 2026-04-21):
  Charlotte on the Cheap  — ParseError (unclosed CDATA)
  Queen City Nerve Events — HTTP 404 (category feed gone; switched to main feed)
  CLT52 / Charlotte Five  — Timeout
  QCity Metro             — HTTP 404
  NoDa Neighborhood       — HTTP 404
  South End CLT           — HTTP 410
  Gaston Gazette          — HTTP 403
  Triad City Beat Arts    — HTTP 404 (category feed; switched to main feed)
  Triad Foodies           — HTTP 404
  Mountain Xpress Events  — HTTP 403
  AVL Today               — HTTP 404
  Ashvegas                — ParseError (unclosed CDATA)
  Free Times Columbia     — HTTP 429
  Charlotte Magazine      — Dropped: 0% event ratio, avg score -0.2
  Triad City Beat         — Dropped: spam (attorney directories, casino finance)
  Arts & Science Council  — Dropped: only publishing job postings, not events

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



    # ── 1H 30MIN — Greenville SC ─────────────────────────────────────────
    ("Greenville SC", "1h30min", "Greenville Journal (Events)",
     "https://greenvillejournal.com/category/events/feed/",
     1, ["events", "arts", "culture"]),

    ("Greenville SC", "1h30min", "Greenville Journal (Arts)",
     "https://greenvillejournal.com/category/arts-culture/feed/",
     2, ["arts", "culture"]),

    ("Greenville SC", "1h30min", "GVLtoday (6AM City)",
     "https://gvltoday.6amcity.com/index.rss",
     2, ["events", "news", "culture"]),

    # ── 2H — Asheville / WNC ─────────────────────────────────────────────
    ("Asheville",     "2h",      "Mountain Xpress",
     "https://mountainx.com/feed/",
     2, ["events", "arts", "culture", "food"]),

    # ── 2H 30MIN — Triangle NC ───────────────────────────────────────────
    ("Triangle NC",   "2h30min", "Walter Magazine",
     "https://www.waltermagazine.com/feed/",
     1, ["events", "culture", "arts"]),

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
