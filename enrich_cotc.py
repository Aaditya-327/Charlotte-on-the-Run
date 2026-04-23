#!/usr/bin/env python3
"""
enrich_cotc.py — Fetch Charlotte on the Cheap RSS, batch-send valid items to
Gemini to extract structured event data, and upsert into events.db.

First run: processes items published in the last 3 days.
Subsequent runs: processes only items newer than the last run (delta).

State is tracked in cotc_state.json.
"""

import json, os, re, sys, hashlib, sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from email.utils import parsedate_to_datetime

import feedparser
from dotenv import load_dotenv
from google import genai
from google.genai import types
from json_repair import repair_json

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

FEED_URL   = "https://www.charlotteonthecheap.com/feed/"
STATE_FILE = Path(__file__).parent / "cotc_state.json"
DB_PATH    = os.getenv("DB_PATH", "events.db")
API_KEY    = os.getenv("GEMINI_API_KEY")
BATCH_SIZE = 30   # items per Gemini call

# ── Junk filter — skip before sending to Gemini ───────────────────────────────
JUNK_PATTERNS = [
    r'\bvpn\b', r'\bamazon deal', r'\bdiscount\b.*\b(online|shop|store)\b',
    r'travel deal', r'tax season', r'save up to \d+%',
    r'\bhottest\b.*\bdeal', r'buy one get one', r'credit card',
    r'mortgage', r'real estate', r'job\b', r'hiring',
    r'wear a .* jersey', r'promo code', r'coupon',
]
JUNK_RE = re.compile('|'.join(JUNK_PATTERNS), re.IGNORECASE)

def is_junk(title: str, desc: str) -> bool:
    return bool(JUNK_RE.search(title + ' ' + desc))

# ── State ─────────────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))

# ── DB ────────────────────────────────────────────────────────────────────────
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
            venue             TEXT,
            category          TEXT,
            fetched_at        TEXT,
            updated_at        TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_pub_date   ON events (pub_date);
        CREATE INDEX IF NOT EXISTS idx_event_date ON events (event_date);
    """)
    db.commit()
    return db

def ensure_columns(db: sqlite3.Connection):
    for col, typ in [("venue", "TEXT"), ("category", "TEXT")]:
        try:
            db.execute(f"ALTER TABLE events ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass
    db.commit()

def make_sig(title: str, pub: str) -> str:
    raw = (title.strip().lower() + (pub or "")[:10]).encode()
    return hashlib.sha256(raw).hexdigest()[:16]

def upsert_events(db: sqlite3.Connection, events: list[dict], now: str):
    inserted = 0
    for ev in events:
        sig = make_sig(ev["title"], ev.get("pub", ""))
        existing = db.execute("SELECT sig FROM events WHERE sig=?", (sig,)).fetchone()
        if existing:
            # Update date/time if we got better data
            db.execute("""
                UPDATE events SET
                    event_date=COALESCE(?,event_date),
                    event_time=COALESCE(?,event_time),
                    date_confidence=MAX(date_confidence,?),
                    updated_at=?
                WHERE sig=?
            """, (ev.get("event_date"), ev.get("event_time"), 90, now, sig))
        else:
            db.execute("""
                INSERT INTO events
                  (sig,title,link,description,pub_date,region,distance,source,
                   tags,price,ev_score,event_date,event_time,date_confidence,
                   venue,category,fetched_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                sig,
                ev["title"][:200],
                ev.get("link",""),
                ev.get("description","")[:600],
                ev.get("pub",""),
                "Charlotte", "0min", "Charlotte on the Cheap",
                json.dumps(["Charlotte"]),
                ev.get("cost_raw"),
                ev.get("ev_score", 5),
                ev.get("event_date"),
                ev.get("event_time"),
                90,
                ev.get("venue"),
                json.dumps(ev.get("category") or []),
                now, now,
            ))
            inserted += 1
    db.commit()
    return inserted

# ── Gemini extraction ─────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an event data extractor for Charlotte, NC.

Given a list of article items from Charlotte on the Cheap, extract structured event data.

For each item that is a real local event or activity (something with a specific date, time, or recurring schedule that a person can physically attend), return a JSON object.

For non-events (online deals, sponsored content, national offers, gift guides, general advice articles), return null for that index.

Return a JSON array with exactly one entry per input item (null for non-events).

Each event object must have:
{
  "idx": <integer, original index>,
  "title": "clean event title (no dates in title)",
  "event_date": "YYYY-MM-DD or null if no specific date",
  "event_time": "HH:MM (24h) or null",
  "end_date": "YYYY-MM-DD or null (for multi-day events)",
  "venue": "venue name or null",
  "neighborhood": "neighborhood or area name or null",
  "cost": "Free / $X / $X–$Y / Varies or null",
  "description": "1–2 sentence summary of the event",
  "category": ["1-2 strings from: music, food, drinks, arts, outdoors, nightlife, comedy, sports, theater, fitness, market, drag, film, weird, family"],
  "is_recurring": true or false
}"""

def build_batch_prompt(items: list[dict], ref_date: str) -> str:
    lines = [f"Today's date is {ref_date}. Extract event data from these {len(items)} items:\n"]
    for i, item in enumerate(items):
        lines.append(f"[{i}] Title: {item['title']}")
        if item['desc']:
            lines.append(f"    Summary: {item['desc'][:300]}")
        lines.append("")
    return "\n".join(lines)

def call_gemini(client, items: list[dict], ref_date: str) -> list[dict | None]:
    prompt = build_batch_prompt(items, ref_date)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,
        ),
    )
    text = response.text or ""
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE).strip()

    start = text.find("[")
    if start == -1:
        raise ValueError("No JSON array in response")
    raw = text[start:]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("    ⚠ Repairing malformed JSON…")
        data = json.loads(repair_json(raw))

    if not isinstance(data, list) or len(data) != len(items):
        print(f"    ⚠ Expected {len(items)} items, got {len(data) if isinstance(data,list) else '?'}")

    return data

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not API_KEY:
        print("ERROR: GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    state    = load_state()
    now_utc  = datetime.now(timezone.utc)
    now_iso  = now_utc.isoformat()
    ref_date = now_utc.strftime("%Y-%m-%d")

    # Determine cutoff: first run = 3 days back, subsequent = last run time
    if "last_run" in state:
        cutoff = datetime.fromisoformat(state["last_run"])
        print(f"Delta run — fetching items since {cutoff.strftime('%Y-%m-%d %H:%M')} UTC")
    else:
        cutoff = now_utc - timedelta(days=3)
        print(f"First run — fetching items from last 3 days (since {cutoff.strftime('%Y-%m-%d')})")

    # ── Fetch feed ────────────────────────────────────────────────────────────
    print(f"Fetching {FEED_URL}…")
    feed = feedparser.parse(FEED_URL)
    print(f"  {len(feed.entries)} total entries in feed")

    # ── Filter to delta window ────────────────────────────────────────────────
    raw_items = []
    for e in feed.entries:
        try:
            pub = parsedate_to_datetime(e.get("published", ""))
        except Exception:
            continue
        if pub <= cutoff:
            continue
        desc = re.sub(r"<[^>]+>", "", e.get("summary", "") or "")[:500]
        raw_items.append({
            "title": e.get("title", "").strip(),
            "link":  e.get("link", ""),
            "pub":   pub.isoformat(),
            "desc":  desc,
        })

    print(f"  {len(raw_items)} new items since cutoff")

    if not raw_items:
        print("Nothing new. Done.")
        save_state({"last_run": now_iso, **{k:v for k,v in state.items() if k != "last_run"}})
        return

    # ── Pre-filter junk ───────────────────────────────────────────────────────
    valid = [it for it in raw_items if not is_junk(it["title"], it["desc"])]
    dropped = len(raw_items) - len(valid)
    print(f"  {dropped} junk items dropped, {len(valid)} sent to Gemini")

    # ── Batch Gemini calls ────────────────────────────────────────────────────
    client = genai.Client(api_key=API_KEY)
    extracted: list[dict] = []
    null_count = 0

    for batch_start in range(0, len(valid), BATCH_SIZE):
        batch = valid[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(valid) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} items)…", end=" ", flush=True)

        try:
            results = call_gemini(client, batch, ref_date)
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        for i, result in enumerate(results):
            if result is None:
                null_count += 1
                continue
            if not isinstance(result, dict):
                continue
            # Merge with original item metadata
            orig = batch[i] if i < len(batch) else {}
            ev = {
                "title":       result.get("title") or orig.get("title", ""),
                "link":        orig.get("link", ""),
                "pub":         orig.get("pub", ""),
                "description": result.get("description", ""),
                "event_date":  result.get("event_date"),
                "event_time":  result.get("event_time"),
                "venue":       result.get("venue"),
                "neighborhood":result.get("neighborhood"),
                "cost_raw":    result.get("cost"),
                "category":    result.get("category") or [],
                "ev_score":    6,
            }
            extracted.append(ev)

        print(f"✓ {sum(1 for r in results if r is not None)} events found")

    print(f"\n  Total: {len(extracted)} events extracted, {null_count} non-events filtered")

    # ── Write to DB ───────────────────────────────────────────────────────────
    db = get_db()
    ensure_columns(db)
    inserted = upsert_events(db, extracted, now_iso)
    db.close()
    print(f"  DB: {inserted} new rows inserted")

    # ── Save state ────────────────────────────────────────────────────────────
    save_state({"last_run": now_iso, "total_processed": state.get("total_processed", 0) + len(raw_items)})
    print("\nDone.")

if __name__ == "__main__":
    main()
