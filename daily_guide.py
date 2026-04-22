#!/usr/bin/env python3
"""
daily_guide.py — Fetch AI-generated daily activity cards for Charlotte using
Gemini 2.5 Flash with Google Search grounding.

Restructured to make only 2 API calls to save Search Grounding costs:
Call A: Budget (Free, Under $20)
Call B: Premium (Under $50, Splurge, Wildcard)
Baseline: Evergreen events (Zero API cost)
"""

import json, os, re, subprocess, sys, time
from json_repair import repair_json
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

API_KEY  = os.getenv("GEMINI_API_KEY")
OUT_FILE = Path(__file__).parent / "docs" / "daily_guide.json"

# ── Load Staples ──────────────────────────────────────────────────────────────
def load_staples(today_date, tomorrow_date) -> list:
    staples_file = Path(__file__).parent / "baseline_staples.json"
    with open(staples_file) as f:
        pool = json.load(f)  # pre-sorted by rank descending, score > 0

    n = 10  # staples per day
    offset = (today_date.timetuple().tm_yday * n) % max(len(pool), 1)

    staples = []
    for day_label, day_offset in [("today", offset), ("tomorrow", offset + n)]:
        for i in range(n):
            card = pool[(day_offset + i) % len(pool)].copy()
            card["day"]  = day_label
            card["tier"] = "baseline"
            card.setdefault("category", [])
            staples.append(card)

    return staples
CALLS = [
    {
        "name": "Budget Events",
        "tiers": [
            {"id": "free", "label": "Free", "emoji": "🆓", "max_cost": "Free", "focus": "specific free events happening on these exact dates — free gallery openings, free outdoor concerts, pop-up community events, street festivals, free entry shows, community meetups. Do NOT include generic parks, standard coffee shops, or bars with no special event."},
            {"id": "under20", "label": "Under $20", "emoji": "💵", "max_cost": "$20", "focus": "specific dated events under $20 — trivia nights on these exact dates, run club events, gallery opening nights, low-cover music shows, ticketed workshops. Do NOT include standard venue or restaurant recommendations with no specific event happening."}
        ]
    },
    {
        "name": "Premium Events",
        "tiers": [
            {"id": "under50", "label": "Under $50", "emoji": "🍸", "max_cost": "$50", "focus": "specific ticketed events under $50 on these exact dates — drag shows, live music, comedy nights, Camp North End programming, ticketed USNWC events. Only include a bar or restaurant if there is a specific event happening there on these dates."},
            {"id": "splurge", "label": "Splurge", "emoji": "🌟", "max_cost": "no limit", "focus": "specific premium events on these exact dates — major concerts, theater performances, VIP events, exclusive pop-ups, special dining experiences. Must be a specific event, not a general venue recommendation."},
            {"id": "wildcard", "label": "Wildcard", "emoji": "🃏", "max_cost": "varies", "focus": "genuinely WEIRD, unexpected, or absurd events that would make someone say 'wait, what?' — things that combine two things that don't belong together, or are just strange by nature. Examples of what BELONGS here: wrestling at a brewery, axe throwing tournament, adult spelling bee, drag bingo, competitive eating contest, paranormal walking tour, silent disco, escape room event, cult film midnight screening, adults-only museum night with cocktails, weird themed 5K (zombie run, color run), burlesque show, comedy roast, psychic fair, taxidermy workshop, gothic market. Examples of what does NOT belong here: regular concerts, gallery openings, food truck rallies, farmers markets, pub trivia, outdoor movies (unless truly bizarre), charity galas, community workshops. Must pass the 'wait, that's a thing?' test. Can be any budget."}
        ]
    }
]

# ── JSON schema embedded in prompt ────────────────────────────────────────────
SYSTEM_INSTRUCTION = """You are a local city guide for Charlotte, NC, with deep knowledge of the queer social scene.

Target audience: 27-year-old gay man, social, adventurous, familiar with Charlotte.

CRITICAL — DYNAMIC EVENTS ONLY: Every card you generate MUST be tied to a specific event happening on the exact dates given. Do NOT recommend a venue simply because it exists and is always open.

DO NOT GENERATE cards for:
- Standard visits to bars, breweries, or coffee shops with no special event (e.g. "grab a beer at Birdsong", "coffee at Smelly Cat")
- Generic parks, trails, or greenways with no scheduled activity
- Regular restaurant dining with no event or special occasion
- Shopping at retail stores or markets that are open every day
- Anything that would be identical advice any day of the week

DO GENERATE cards for:
- Concerts, live music sets, DJ nights on these specific dates
- Drag shows, drag brunches, drag performances at specific venues
- Trivia nights, pub quizzes, game nights happening on these exact days
- Sports events: Charlotte FC match, Charlotte Knights game, wrestling event at a brewery (e.g. Lenny Boy Brewery WWE-style wrestling), 5K races, tournament nights
- Gallery opening receptions, art show openings, film premieres
- Pop-up markets, food pop-ups, chef collaborations, tap takeovers
- Comedy shows, improv nights, open mic events with a specific lineup
- Festival days, street fairs, outdoor concerts, block parties
- Themed or ticketed nights at venues (e.g. "Science on the Rocks" at Discovery Place, "River Jam" at USNWC)
- Charity or community events, runs, fundraisers with a specific date
- Special screenings, midnight movies, film festival screenings
- One-time or limited pop-ups, brand activations, exclusive tastings

IMPORTANT: Respond ONLY with a valid JSON array. Return minified JSON (no indentation, no line breaks). No explanation, no markdown, no prose — just the raw JSON array.
Each element must match this exact schema:
{
  "title":       "string — short activity name (≤60 chars)",
  "description": "string — 2-3 sentences with specific details (venue, what to expect, why it's worth it)",
  "day":         "today | tomorrow",
  "period":      "morning | afternoon | evening | night",
  "location":    "string — venue name + neighborhood (e.g. 'Optimist Hall, NoDa')",
  "cost":        "string — e.g. 'Free', '$12', '$8–$15'",
  "tags":        ["array of 2-4 strings from: outdoor, food, drinks, music, art, queer-friendly, nightlife, fitness, culture, shopping, sports, nature"],
  "category":    ["array of 1-2 strings from: music, food, drinks, arts, outdoors, nightlife, comedy, sports, theater, fitness, market, drag, film, weird, family — use 'weird' only if the event is genuinely unusual or absurd"],
  "tier":        "string — the ID of the budget tier this belongs to",
  "rank":        "integer 1–5 — how worth attending is this event? 5=unmissable/rare, 4=highly recommended, 3=solid, 2=niche, 1=filler"
}

Example of the expected output format (shortened):
[{"title":"WWE-Style Wrestling at Lenny Boy Brewery","description":"Catch live professional wrestling bouts in the taproom...","day":"today","period":"night","location":"Lenny Boy Brewing Co, LoSo","cost":"$15","tags":["sports","nightlife","drinks"],"tier":"free","rank":5}]"""

def make_prompt(call_def: dict, today_dow: str, today: str, tomorrow_dow: str, tomorrow: str) -> str:
    tiers_info = ""
    for t in call_def["tiers"]:
        tiers_info += f"- Tier ID: '{t['id']}' (Max cost: {t['max_cost']}). Focus on: {t['focus']}\n"

    return f"""Search the web for SPECIFIC EVENTS happening in Charlotte on {today_dow} {today} and {tomorrow_dow} {tomorrow}.

You are looking for date-specific happenings only — concerts, shows, sports, pop-ups, drag nights, gallery openings, themed events, festivals, trivia nights, run clubs, comedy shows, film screenings, tap takeovers, wrestling nights, and community events tied to these exact dates.

DO NOT generate generic venue recommendations (e.g. "grab drinks at X bar", "visit Y park", "eat at Z restaurant") unless a specific event is occurring there on these dates. Charlotte's evergreen venues are already covered separately — your job is to surface what's uniquely happening right now.

Generate 6–8 EVENTS PER TIER for EACH day (today and tomorrow), covering morning, afternoon, evening, and night time slots.
Provide events for the following tiers:
{tiers_info}

Remember to return a minified JSON array where each object has a 'tier' field matching one of the Tier IDs above."""

# ── JSON extractor ─────────────────────────────────────────────────────────────
def extract_json(text: str) -> list:
    """Extract a JSON array from model output, repairing malformed LLM output."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)
    text = text.strip()

    start = text.find("[")
    if start == -1:
        raise ValueError("No JSON array found in response")
    raw = text[start:]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("    ⚠ Malformed JSON — attempting repair…", flush=True)
        data = json.loads(repair_json(raw))

    if not isinstance(data, list):
        raise ValueError("Expected JSON array at top level")
    return data

def validate_card(card: dict, allowed_tiers: list, today_iso: str, tomorrow_iso: str) -> dict | None:
    """Normalise and validate a single activity card. Returns None if invalid."""
    # Translate ISO date → day label when model ignores schema
    if "day" not in card and "date" in card:
        d = str(card["date"])[:10]
        if d == today_iso:
            card["day"] = "today"
        elif d == tomorrow_iso:
            card["day"] = "tomorrow"

    required = ("title", "description", "day", "location", "cost", "tier")
    if not all(k in card for k in required):
        return None
    if card.get("day") not in ("today", "tomorrow"):
        return None
    if card.get("period") not in ("morning", "afternoon", "evening", "night"):
        card["period"] = "afternoon"
    if card.get("tier") not in allowed_tiers:
        return None

    card.setdefault("tags", [])
    card.setdefault("category", [])
    card["title"]       = str(card["title"])[:80]
    card["description"] = str(card.get("description") or "")[:400]
    card["location"]    = str(card["location"])[:80]
    card["cost"]        = str(card["cost"])[:20]
    return card

# ── Fetch Grouped Tiers ─────────────────────────────────────────────────────────────
def fetch_grouped_tiers(client: genai.Client, call_def: dict, today_dow: str, today: str,
               tomorrow_dow: str, tomorrow: str, today_iso: str, tomorrow_iso: str,
               retries: int = 3) -> dict:
    call_name = call_def["name"]
    prompt  = make_prompt(call_def, today_dow, today, tomorrow_dow, tomorrow)
    allowed_tiers = [t["id"] for t in call_def["tiers"]]

    print(f"  Fetching {call_name}…", flush=True)

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.2,
                ),
            )
            text = response.text or ""

            # Extract grounding sources
            sources = []
            try:
                for chunk in response.candidates[0].grounding_metadata.grounding_chunks:
                    if hasattr(chunk, "web") and chunk.web:
                        sources.append({"title": chunk.web.title, "url": chunk.web.uri})
            except Exception:
                pass

            # Parse JSON
            raw_cards = extract_json(text)
            activities = [c for c in (validate_card(c, allowed_tiers, today_iso, tomorrow_iso) for c in raw_cards) if c]

            print(f"    ✓ {len(activities)} total cards | {len(sources)} sources")
            return {
                "activities": activities,
                "sources":    sources,
                "error":      None,
            }

        except Exception as e:
            msg = str(e)
            if attempt < retries - 1:
                wait = 60
                if "429" in msg:
                    m = re.search(r"retryDelay.*?(\d+)s", msg)
                    if m: wait = int(m.group(1)) + 5
                print(f"    Error/Rate limited — waiting {wait}s (retry {attempt+2}/{retries}). Error: {msg[:60]}")
                time.sleep(wait)
                continue
            
            print(f"    ERROR [{call_name}]: {msg[:160]}", file=sys.stderr)
            return {
                "activities": [],
                "sources":    [],
                "error":      msg[:300],
            }


# ── Export events_data.js ─────────────────────────────────────────────────────
def export_events_data():
    import sqlite3
    db_path = os.getenv("DB_PATH", "events.db")
    if not Path(db_path).exists():
        return
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    today  = date.today().isoformat()
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
    print(f"  events_data.js: {len(events)} events")


# ── Git push ──────────────────────────────────────────────────────────────────
def git_push(today_iso: str):
    repo = Path(__file__).parent
    try:
        subprocess.run(
            ["git", "add", "docs/daily_guide.json",
             "docs/daily_guide_data.js", "docs/events_data.js"],
            cwd=repo, check=True, capture_output=True,
        )
        changed = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=repo, capture_output=True
        ).returncode != 0
        if changed:
            subprocess.run(
                ["git", "commit", "-m", f"auto: daily guide (JSON cards) + events {today_iso}"],
                cwd=repo, check=True, capture_output=True,
            )
            subprocess.run(["git", "push"], cwd=repo, check=True, capture_output=True)
            print("  Git: pushed.")
        else:
            print("  Git: nothing changed.")
    except subprocess.CalledProcessError as e:
        print(f"  Git error: {e.stderr.decode()}", file=sys.stderr)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    no_push = "--no-push" in sys.argv

    today      = date.today()
    tomorrow   = today + timedelta(days=1)
    dow        = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    today_s    = today.strftime("%B %d, %Y")
    tomorrow_s = tomorrow.strftime("%B %d, %Y")
    today_dow    = dow[today.weekday()]
    tomorrow_dow = dow[tomorrow.weekday()]

    print("Charlotte On The Run — Daily Guide (JSON cards)")
    print(f"Today: {today_dow} {today_s}  |  Tomorrow: {tomorrow_dow} {tomorrow_s}\n")

    if not API_KEY:
        print("ERROR: GEMINI_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    client  = genai.Client(api_key=API_KEY)
    
    all_activities = []
    all_sources = []
    errors = []

    # Fetch dynamic tiers
    for call_def in CALLS:
        result = fetch_grouped_tiers(
            client, call_def,
            today_dow, today_s,
            tomorrow_dow, tomorrow_s,
            today.isoformat(), tomorrow.isoformat(),
        )
        all_activities.extend(result["activities"])
        all_sources.extend(result["sources"])
        if result["error"]:
            errors.append(f"{call_def['name']}: {result['error']}")

    # Add Staples
    staples = load_staples(today, tomorrow)
    all_activities.extend(staples)
    print(f"  Added {len(staples)} staple activities.")

    # Deduplicate by (title, location) pair
    deduped_activities = []
    seen = set()
    for act in all_activities:
        key = (act["title"].lower().strip(), act["location"].lower().strip())
        if key not in seen:
            seen.add(key)
            deduped_activities.append(act)
    
    dup_count = len(all_activities) - len(deduped_activities)
    if dup_count > 0:
        print(f"  Removed {dup_count} duplicate activities.")

    # Organize into tier outputs
    tier_defs = [
        {"id": "baseline", "label": "Staples", "emoji": "📍"}
    ]
    for c in CALLS:
        tier_defs.extend(c["tiers"])
        
    results = []
    for tdef in tier_defs:
        t_acts = [a for a in deduped_activities if a["tier"] == tdef["id"]]
        if not t_acts and tdef["id"] != "baseline":
            continue # skip empty tiers unless baseline
        results.append({
            "id": tdef["id"],
            "label": tdef["label"],
            "emoji": tdef.get("emoji", "📍"),
            "activities": t_acts,
            "sources": all_sources, # pass all sources for now
            "error": " | ".join(errors) if errors else None
        })

    output = {
        "generated_at": today.isoformat(),
        "today":        today_s,
        "today_dow":    today_dow,
        "tomorrow":     tomorrow_s,
        "tomorrow_dow": tomorrow_dow,
        "tiers":        results,
    }

    # Save JSON
    OUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → {OUT_FILE}")

    # Save JS module
    js_file = OUT_FILE.parent / "daily_guide_data.js"
    with open(js_file, "w") as f:
        f.write("const DAILY_GUIDE_DATA = ")
        json.dump(output, f, ensure_ascii=False)
        f.write(";\n")
    print(f"Saved → {js_file}")

    # Print summary
    total = sum(len(r["activities"]) for r in results)
    print(f"\nTotal activity cards: {total}")
    for r in results:
        today_n    = sum(1 for c in r["activities"] if c["day"] == "today")
        tomorrow_n = sum(1 for c in r["activities"] if c["day"] == "tomorrow")
        print(f"  {r['emoji']} {r['label']:12} {len(r['activities'])} cards "
              f"(today={today_n}, tomorrow={tomorrow_n})"
              + (f" ⚠ {r['error'][:60]}" if r.get("error") else ""))

    print("\nEnriching Charlotte on the Cheap…")
    try:
        import enrich_cotc
        enrich_cotc.main()
    except Exception as e:
        print(f"  enrich_cotc error: {e}", file=sys.stderr)

    print("\nExporting events_data.js…")
    export_events_data()

    if not no_push:
        print("\nPushing to GitHub…")
        git_push(today.isoformat())

    print("\nDone.")

if __name__ == "__main__":
    main()
