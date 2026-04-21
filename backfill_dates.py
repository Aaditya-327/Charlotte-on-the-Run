#!/usr/bin/env python3
"""
backfill_dates.py — One-off script to re-extract dates for existing DB rows.
Run after adding the spaCy NER date extractor to populate date_confidence.
"""
from fetcher import get_db, is_blocked
from utils.date_extractor import extract_event_datetime

db = get_db()
rows = db.execute(
    "SELECT sig, title, description, ev_score FROM events"
).fetchall()

updated = 0
deleted = 0
for r in rows:
    # Remove blocked items that slipped in before the blocklist existed
    if is_blocked(r["title"]) or r["ev_score"] < 4:
        db.execute("DELETE FROM events WHERE sig=?", (r["sig"],))
        deleted += 1
        continue

    d, t, conf = extract_event_datetime(r["title"], r["description"] or "")
    if d or t or conf:
        db.execute(
            "UPDATE events SET event_date=?, event_time=?, date_confidence=? WHERE sig=?",
            (d, t, conf, r["sig"])
        )
        updated += 1

db.commit()
remaining = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
db.close()
print(f"Done. updated={updated}  deleted={deleted}  remaining={remaining}")
