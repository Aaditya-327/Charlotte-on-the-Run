#!/usr/bin/env python3
"""
daily_guide.py — Fetch AI-generated daily event guides for Charlotte using
Gemini 2.0 Flash with Google Search grounding.

Runs the 4 budget-tier prompts, saves results to docs/daily_guide.json,
and pushes updated docs/events_data.js + daily_guide.json to git.

Schedule: run via launchd at 7 AM ET daily (see com.charlotteontherun.guide.plist)
Usage:    python daily_guide.py [--no-push]
"""

import json, os, re, subprocess, sys, time
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

API_KEY  = os.getenv("GEMINI_API_KEY")
OUT_FILE = Path(__file__).parent / "docs" / "daily_guide.json"

TIERS = [
    {
        "id":    "free",
        "label": "Free",
        "emoji": "🆓",
    },
    {
        "id":    "under20",
        "label": "Under $20",
        "emoji": "💵",
    },
    {
        "id":    "under50",
        "label": "Under $50",
        "emoji": "🍸",
    },
    {
        "id":    "splurge",
        "label": "Splurge",
        "emoji": "🌟",
    },
]

def make_prompt(tier_id: str, today: str, tomorrow: str, today_dow: str, tomorrow_dow: str) -> str:
    if tier_id == "free":
        return (
            f"Act as a specialized local city guide for Charlotte, NC. "
            f"Generate a highly detailed and comprehensive itinerary of completely free things to do "
            f"for a 27-year-old gay man in Charlotte today ({today_dow}, {today}) and tomorrow ({tomorrow_dow}, {tomorrow}). "
            f"Search the live web for specific free events happening on these exact dates. "
            f"Include free queer-friendly spaces, parks, neighborhood walks, no-cover venues, and community meetups. "
            f"Break down the recommendations by morning, afternoon, and evening for both days. "
            f"Provide a very long response. Do not include any activities that require an entry fee or a mandatory purchase."
        )
    elif tier_id == "under20":
        return (
            f"Act as a specialized local city guide for Charlotte, NC. "
            f"Generate a highly detailed and comprehensive itinerary of activities costing $20 or less "
            f"for a 27-year-old gay man in Charlotte today ({today_dow}, {today}) and tomorrow ({tomorrow_dow}, {tomorrow}). "
            f"Search the live web for specific events happening on these exact dates. "
            f"Focus on cheap eats, local coffee shops, brewery run clubs or trivia nights, dive bars, and low-cover events or gallery shows. "
            f"Break down the recommendations by morning, afternoon, and evening for both days, providing estimated costs for each item. "
            f"Provide a very long response."
        )
    elif tier_id == "under50":
        return (
            f"Act as a specialized local city guide for Charlotte, NC. "
            f"Generate a highly detailed and comprehensive itinerary of activities costing up to $50 "
            f"for a 27-year-old gay man in Charlotte today ({today_dow}, {today}) and tomorrow ({tomorrow_dow}, {tomorrow}). "
            f"Search the live web for specific events happening on these exact dates. "
            f"Include mid-range dining, craft cocktail bars, ticketed local music shows, drag performances, "
            f"and activities at venues like the US National Whitewater Center or Camp North End. "
            f"Break down the recommendations by morning, afternoon, and evening for both days, providing estimated costs for each item. "
            f"Provide a very long response."
        )
    else:  # splurge
        return (
            f"Act as a specialized local city guide for Charlotte, NC. "
            f"Generate a highly detailed and comprehensive itinerary of premium activities with no strict budget limit "
            f"for a 27-year-old gay man in Charlotte today ({today_dow}, {today}) and tomorrow ({tomorrow_dow}, {tomorrow}). "
            f"Search the live web for specific premium events happening on these exact dates. "
            f"Include high-end dining reservations, VIP nightlife experiences, major concert or theater tickets, "
            f"upscale cocktail lounges, and exclusive events. "
            f"Break down the recommendations by morning, afternoon, and evening for both days. "
            f"Provide a very long response."
        )


def fetch_tier(client: genai.Client, tier_id: str, today: str, tomorrow: str,
               today_dow: str, tomorrow_dow: str, retries: int = 3) -> dict:
    prompt = make_prompt(tier_id, today, tomorrow, today_dow, tomorrow_dow)
    print(f"  Fetching {tier_id}…", flush=True)
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.7,
                ),
            )
            text = response.text or ""
            sources = []
            try:
                for chunk in response.candidates[0].grounding_metadata.grounding_chunks:
                    if hasattr(chunk, "web") and chunk.web:
                        sources.append({"title": chunk.web.title, "url": chunk.web.uri})
            except Exception:
                pass
            return {"id": tier_id, "content": text, "sources": sources, "error": None}
        except Exception as e:
            msg = str(e)
            if "429" in msg and attempt < retries - 1:
                # Extract retryDelay seconds from error message
                m = re.search(r"retryDelay.*?(\d+)s", msg)
                wait = int(m.group(1)) + 5 if m else 60
                print(f"    Rate limited — waiting {wait}s before retry {attempt+2}/{retries}…")
                time.sleep(wait)
                continue
            print(f"    ERROR: {msg[:120]}", file=sys.stderr)
            return {"id": tier_id, "content": "", "sources": [], "error": msg[:200]}


def export_events_data():
    """Re-export docs/events_data.js from the SQLite DB."""
    import sqlite3
    from datetime import date, timedelta
    db_path = os.getenv("DB_PATH", "events.db")
    if not Path(db_path).exists():
        return
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    today = date.today().isoformat()
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    rows = db.execute("""
        SELECT title, link, description, pub_date, region, distance,
               source, price, ev_score, event_date, event_time, date_confidence
        FROM events
        WHERE ev_score >= 4
          AND pub_date >= ?
          AND (event_date IS NULL OR event_date >= ?)
        ORDER BY
          CASE WHEN event_date IS NOT NULL THEN 0 ELSE 1 END,
          event_date ASC,
          ev_score DESC
        LIMIT 300
    """, (cutoff, today)).fetchall()
    events = [dict(r) for r in rows]
    db.close()
    out = Path(__file__).parent / "docs" / "events_data.js"
    with open(out, "w") as f:
        f.write("const EVENTS_DATA = ")
        json.dump(events, f, default=str, indent=2)
        f.write(";\n")
    print(f"  events_data.js: {len(events)} events exported")


def git_push():
    repo = Path(__file__).parent
    try:
        subprocess.run(["git", "add", "docs/daily_guide.json", "docs/events_data.js"],
                       cwd=repo, check=True, capture_output=True)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=repo, capture_output=True
        )
        if result.returncode != 0:
            subprocess.run(
                ["git", "commit", "-m", f"auto: daily guide + events {date.today()}"],
                cwd=repo, check=True, capture_output=True,
            )
            subprocess.run(["git", "push"], cwd=repo, check=True, capture_output=True)
            print("  Git: pushed.")
        else:
            print("  Git: nothing changed, skipping push.")
    except subprocess.CalledProcessError as e:
        print(f"  Git error: {e.stderr.decode()}", file=sys.stderr)


def main():
    no_push = "--no-push" in sys.argv

    today    = date.today()
    tomorrow = today + timedelta(days=1)
    dow      = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    today_s    = today.strftime("%B %d, %Y")
    tomorrow_s = tomorrow.strftime("%B %d, %Y")
    today_dow    = dow[today.weekday()]
    tomorrow_dow = dow[tomorrow.weekday()]

    print(f"Charlotte On The Run — Daily Guide")
    print(f"Today: {today_dow}, {today_s}  |  Tomorrow: {tomorrow_dow}, {tomorrow_s}")
    print()

    if not API_KEY:
        print("ERROR: GEMINI_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=API_KEY)
    results = []

    for tier in TIERS:
        result = fetch_tier(client, tier["id"], today_s, tomorrow_s, today_dow, tomorrow_dow)
        result["label"] = tier["label"]
        result["emoji"] = tier["emoji"]
        results.append(result)
        preview = result["content"][:120].replace("\n", " ")
        print(f"    ✓ {len(result['content'])} chars | {len(result['sources'])} sources | {preview}…")

    output = {
        "generated_at": today.isoformat(),
        "today":        today_s,
        "today_dow":    today_dow,
        "tomorrow":     tomorrow_s,
        "tomorrow_dow": tomorrow_dow,
        "tiers":        results,
    }

    OUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → {OUT_FILE}")

    print("\nExporting events_data.js…")
    export_events_data()

    if not no_push:
        print("\nPushing to GitHub…")
        git_push()

    print("\nDone.")


if __name__ == "__main__":
    main()
