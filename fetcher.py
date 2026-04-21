#!/usr/bin/env python3
"""
fetcher.py — RSS fetch, dedup, event scoring, and query helpers.

Dedup: sig = sha256(title.lower() + pub_date[:10])[:16]
New items only inserted if ev_score >= EVENT_SCORE_MIN.
Event dates/times extracted from text and stored for accurate future-only filtering.
"""

import sqlite3, hashlib, json, os, re, time
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, date as date_t, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from utils import scoring, date_extractor

DB_PATH    = os.getenv("DB_PATH",    "events.db")
FEEDS_FILE = os.getenv("FEEDS_FILE", "feeds_live.json")
HEADERS    = {"User-Agent": "Mozilla/5.0 (compatible; CLT-Events-Bot/1.0)"}
EVENT_SCORE_THRESHOLD = int(os.getenv("EVENT_SCORE_MIN", "4"))

# ── Blocklist — hard-reject before scoring ────────────────────────────────────

TITLE_BLOCKLIST = [
    "workers compensation", "attorney", "mortgage", "non-agency loan",
    "virtual currency", "social casino", "gift idea", "tinggly",
    "mansion monday", "home tour", "home renovation",
    "real estate", "homebuyer",
    "job description", "hiring", "part-time", "executive director",
    "director of marketing", "marketing coordinator",
    "federal budget", "cannabis report",
    "proposed budget", "budget targets",
    "travel:", "miles from charlotte",
    "letter:", "opinion:",
]

def is_blocked(title: str) -> bool:
    """Return True if title matches any blocklist pattern."""
    t = title.lower()
    return any(kw in t for kw in TITLE_BLOCKLIST)

# ── Scoring ───────────────────────────────────────────────────────────────────

EVENT_KW = {
    "festival":4, "concert":4, "show":3, "exhibit":3, "exhibition":3,
    "tour":2, "market":3, "fair":3, "workshop":3, "lecture":2,
    "free":2, "ticket":3, "admission":3, "opening":3, "performance":4,
    "race":2, "walk":2, "gala":3, "fundraiser":2, "screening":3,
    "tasting":3, "happy hour":2, "trivia":2, "open mic":3,
    "comedy":3, "dance":3, "class":2, "parade":3, "art walk":4,
    "beer":2, "wine":2, "food truck":3, "pop-up":2,
    "family":2, "kids":2, "free admission":4,
}
NEWS_KW = {
    "police":3, "arrest":3, "shooting":3, "crash":3,
    "obituary":4, "obituaries":4, "weather":2, "forecast":2,
    "stocks":3, "earnings":3, "legislation":3,
    "lawsuit":3, "indictment":3, "traffic":2, "accident":3,
    "court":2, "crime":3, "breaking":2,
}

def score_event(title: str, desc: str) -> int:
    return scoring.compute_event_score(title, desc, EVENT_KW, NEWS_KW)

def extract_price(text: str) -> str | None:
    if not text: return None
    if re.search(r'\bfree\b', text.lower()): return "free"
    m = re.search(r'\$(\d+(?:\.\d{2})?)', text)
    return f"${m.group(1)}" if m else None

# ── Date / time extraction ────────────────────────────────────────────────────

_MONTH_MAP = {
    "january":1,  "february":2,  "march":3,    "april":4,
    "may":5,      "june":6,      "july":7,      "august":8,
    "september":9,"october":10,  "november":11, "december":12,
    "jan":1, "feb":2, "mar":3, "apr":4,
    "jun":6, "jul":7, "aug":8,
    "sep":9, "oct":10, "nov":11, "dec":12,
}
_MONTH_RE = re.compile(
    r'\b(' + '|'.join(_MONTH_MAP) + r')\.?\s+(\d{1,2})(?:st|nd|rd|th)?'
    r'(?:,?\s+(\d{4}))?\b',
    re.IGNORECASE
)
_TIME_RE = re.compile(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', re.IGNORECASE)

def extract_event_datetime(title: str, desc: str) -> tuple[str | None, str | None, int]:
    """Delegate to utils.date_extractor; returns (date, time, confidence)."""
    return date_extractor.extract_event_datetime(title, desc)

# ── Database ──────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            sig               TEXT PRIMARY KEY,
            title             TEXT NOT NULL,
            link              TEXT,
            description       TEXT,
            pub_date          TEXT,
            region            TEXT,
            distance          TEXT,
            source            TEXT,
            tags              TEXT,
            price             TEXT,
            ev_score          INTEGER,
            event_date        TEXT,
            event_time        TEXT,
            date_confidence   INTEGER DEFAULT 0,
            fetched_at        TEXT,
            updated_at        TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_region       ON events (region);
        CREATE INDEX IF NOT EXISTS idx_distance     ON events (distance);
        CREATE INDEX IF NOT EXISTS idx_pub_date     ON events (pub_date);
        CREATE INDEX IF NOT EXISTS idx_event_date   ON events (event_date);

        CREATE TABLE IF NOT EXISTS fetch_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at     TEXT,
            feed_name  TEXT,
            new_items  INTEGER,
            skipped    INTEGER,
            dropped    INTEGER,
            error      TEXT
        );
    """)
    # Migration for older DBs — add missing columns if they don't exist
    for col in ("event_date TEXT", "event_time TEXT", "date_confidence INTEGER DEFAULT 0"):
        try:
            db.execute(f"ALTER TABLE events ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    # Create the confidence index only after the column is guaranteed to exist
    try:
        db.execute("CREATE INDEX IF NOT EXISTS idx_confidence ON events (date_confidence)")
    except sqlite3.OperationalError:
        pass
    db.commit()
    return db


# ── Signature ─────────────────────────────────────────────────────────────────

def make_sig(title: str, pub: str) -> str:
    raw = (title.strip().lower() + (pub or "")[:10]).encode()
    return hashlib.sha256(raw).hexdigest()[:16]

# ── XML parser ────────────────────────────────────────────────────────────────

NS_CONTENT = "http://purl.org/rss/1.0/modules/content/"
NS_ATOM    = "http://www.w3.org/2005/Atom"

def _clean(s: str | None) -> str:
    return re.sub(r'<[^>]+>', '', s or '').strip()

def _parse_date(s: str | None) -> str | None:
    if not s: return None
    try:
        return parsedate_to_datetime(s.strip()).isoformat()
    except Exception:
        return s.strip() or None

def parse_feed(raw: bytes) -> list[dict]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []

    def _first(*els):
        for e in els:
            if e is not None: return e
        return None

    results = []
    for tag in ("item", f"{{{NS_ATOM}}}entry"):
        for item in root.iter(tag):
            t_el = _first(item.find("title"),          item.find(f"{{{NS_ATOM}}}title"))
            d_el = _first(item.find("description"),
                          item.find(f"{{{NS_CONTENT}}}encoded"),
                          item.find(f"{{{NS_ATOM}}}summary"))
            p_el = _first(item.find("pubDate"),        item.find(f"{{{NS_ATOM}}}updated"))
            l_el = _first(item.find("link"),           item.find(f"{{{NS_ATOM}}}link"))

            title = _clean(t_el.text if t_el is not None else "")
            if not title:
                continue
            desc = _clean(d_el.text if d_el is not None else "")[:600]
            pub  = _parse_date(p_el.text if p_el is not None else "")
            link = ((l_el.text or l_el.get("href", "")).strip()
                    if l_el is not None else "")

            results.append({"title": title, "desc": desc, "pub": pub, "link": link})
    return results

# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_raw(url: str, timeout: int = 12) -> bytes:
    req  = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp.read(500_000)

# ── Main loop ─────────────────────────────────────────────────────────────────

def run_fetch(
    priority_filter: int | None = None,
    region_filter:   str | None = None,
    dry_run:         bool       = False,
) -> dict:
    path = Path(FEEDS_FILE)
    if not path.exists():
        raise FileNotFoundError(f"{FEEDS_FILE} missing — run validate_feeds.py first.")
    with open(path) as f:
        feeds = json.load(f)

    if priority_filter:
        feeds = [fd for fd in feeds if fd["priority"] <= priority_filter]
    if region_filter:
        feeds = [fd for fd in feeds if region_filter.lower() in fd["region"].lower()]

    db  = get_db()
    now = datetime.now(timezone.utc).isoformat()
    totals = {"new": 0, "skipped": 0, "dropped": 0, "errors": 0}

    for feed in feeds:
        new_c = skip_c = drop_c = 0

        try:
            raw   = fetch_raw(feed["url"])
            items = parse_feed(raw)
        except Exception as e:
            totals["errors"] += 1
            db.execute("INSERT INTO fetch_log VALUES (NULL,?,?,0,0,0,?)",
                       (now, feed["name"], str(e)))
            print(f"  ✗  {feed['name']}: {e}")
            time.sleep(0.3)
            continue

        for item in items:
            sig   = make_sig(item["title"], item["pub"] or "")
            ev    = score_event(item["title"], item["desc"])
            price = extract_price(item["desc"] + " " + item["title"])

            row = db.execute(
                "SELECT sig, price, event_date FROM events WHERE sig=?", (sig,)
            ).fetchone()

            if row:
                if price and not row["price"]:
                    if not dry_run:
                        db.execute("UPDATE events SET price=?, updated_at=? WHERE sig=?",
                                   (price, now, sig))
                skip_c += 1
                continue

            if is_blocked(item["title"]):
                drop_c += 1
                continue

            if ev < EVENT_SCORE_THRESHOLD:
                drop_c += 1
                continue

            event_date, event_time, date_conf = extract_event_datetime(item["title"], item["desc"])

            if not dry_run:
                db.execute(
                    """INSERT INTO events
                       (sig, title, link, description, pub_date,
                        region, distance, source, tags,
                        price, ev_score, event_date, event_time, date_confidence, fetched_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (sig, item["title"], item["link"], item["desc"],
                     item["pub"], feed["region"], feed["distance"],
                     feed["name"], json.dumps(feed["tags"]),
                     price, ev, event_date, event_time, date_conf, now, now)
                )
            new_c += 1

        totals["new"]     += new_c
        totals["skipped"] += skip_c
        totals["dropped"] += drop_c

        if not dry_run:
            db.execute("INSERT INTO fetch_log VALUES (NULL,?,?,?,?,?,?)",
                       (now, feed["name"], new_c, skip_c, drop_c, None))
        print(f"  {feed['name']:<40} +{new_c:>3} new  {skip_c:>4} skip  {drop_c:>3} drop")
        time.sleep(0.3)

    if not dry_run:
        db.commit()
    db.close()
    print(f"\nDone. new={totals['new']}  skip={totals['skipped']}  "
          f"drop={totals['dropped']}  errors={totals['errors']}")
    return totals

# ── Query ─────────────────────────────────────────────────────────────────────

DIST_RANK = {"0min":0, "30min":1, "1h":2, "1h30min":3, "2h":4, "2h30min":5}

def query_events(
    region:       str | None = None,
    distance_max: str | None = None,
    free_only:    bool       = False,
    tag:          str | None = None,
    date_filter:  str | None = None,   # "today" | "tonight" | "weekend" | YYYY-MM-DD
    keyword:      str | None = None,
    limit:        int        = 10,
    min_score:    int        = 1,
) -> list[dict]:
    """
    Return upcoming events, filtering out anything that started more than 1h ago.
    Events with a known date come first (sorted soonest), then recent undated articles.
    """
    now        = datetime.now(timezone.utc)
    today      = now.date()
    today_str  = today.isoformat()
    ago_1h     = (now - timedelta(hours=1)).strftime("%H:%M")
    pub_cutoff = (now - timedelta(days=30)).isoformat()
    max_rank   = DIST_RANK.get(distance_max, 99) if distance_max else 99

    # Compute weekend date set
    weekday = today.weekday()  # 0=Mon … 6=Sun
    sat = today + timedelta(days=(5 - weekday) % 7)
    sun = sat + timedelta(days=1)
    fri = sat - timedelta(days=1)
    weekend_dates = {fri.isoformat(), sat.isoformat(), sun.isoformat()}

    db = get_db()
    rows = db.execute(
        """SELECT * FROM events
           WHERE ev_score >= ?
             AND pub_date >= ?
             AND (
               (event_date IS NOT NULL AND event_date >= ?)
               OR event_date IS NULL
             )
           ORDER BY
             CASE WHEN event_date IS NOT NULL THEN 0 ELSE 1 END,
             event_date ASC,
             event_time ASC,
             pub_date DESC
           LIMIT 800""",
        (min_score, pub_cutoff, today_str)
    ).fetchall()
    db.close()

    out = []
    for r in rows:
        # ── Distance filter ───────────────────────────────────────────────
        if DIST_RANK.get(r["distance"], 99) > max_rank:
            continue

        # ── Region filter ─────────────────────────────────────────────────
        if region and region.lower() not in r["region"].lower():
            continue

        # ── Tag filter ────────────────────────────────────────────────────
        if tag:
            tags = json.loads(r["tags"] or "[]")
            if tag.lower() not in tags:
                continue

        # ── Free filter ───────────────────────────────────────────────────
        if free_only and r["price"] != "free":
            continue

        # ── Keyword filter ────────────────────────────────────────────────
        if keyword:
            kw = keyword.lower()
            if kw not in (r["title"] or "").lower() and kw not in (r["description"] or "").lower():
                continue

        # ── Drop today's events that started >1h ago ──────────────────────
        if r["event_date"] == today_str and r["event_time"]:
            if r["event_time"] < ago_1h:
                continue

        # ── Date filter ───────────────────────────────────────────────────
        ed = r["event_date"]
        if date_filter == "today":
            if ed and ed != today_str:
                continue
            if not ed:
                continue  # undated articles excluded from /today
        elif date_filter == "tonight":
            if ed != today_str:
                continue
            # Only include if time is unknown (we'll show it) or >= 17:00
            if r["event_time"] and r["event_time"] < "17:00":
                continue
        elif date_filter == "weekend":
            if not ed or ed not in weekend_dates:
                continue
        elif date_filter:  # specific YYYY-MM-DD
            if ed != date_filter:
                continue

        out.append(dict(r))
        if len(out) >= limit:
            break

    return out

def get_stats() -> dict:
    db = get_db()
    total    = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    dated    = db.execute("SELECT COUNT(*) FROM events WHERE event_date IS NOT NULL").fetchone()[0]
    by_region = db.execute(
        "SELECT region, COUNT(*) c FROM events GROUP BY region ORDER BY c DESC"
    ).fetchall()
    last_run = db.execute(
        "SELECT run_at, SUM(new_items) n FROM fetch_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return {
        "total":      total,
        "dated":      dated,
        "by_region":  [(r["region"], r["c"]) for r in by_region],
        "last_fetch": last_run["run_at"][:19] if last_run and last_run["run_at"] else "never",
        "last_new":   last_run["n"] or 0 if last_run else 0,
    }

if __name__ == "__main__":
    run_fetch()
