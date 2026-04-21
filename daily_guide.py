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
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

API_KEY  = os.getenv("GEMINI_API_KEY")
OUT_FILE = Path(__file__).parent / "docs" / "daily_guide.json"

# ── Baseline Activities ────────────────────────────────────────────────────────
BASELINE_ACTIVITIES = {
    "Monday": [
        {"title": "Morning Run at Freedom Park", "description": "Start the week with a 3-mile loop around Freedom Park. The paved trails are perfect for a brisk morning jog before the crowds arrive.", "period": "morning", "location": "Freedom Park, Myers Park", "cost": "Free", "tags": ["outdoor", "fitness"]},
        {"title": "Coffee at Smelly Cat", "description": "Grab a locally roasted cold brew and a breakfast sandwich. A cozy spot in NoDa to read a book or people-watch.", "period": "morning", "location": "Smelly Cat Coffeehouse, NoDa", "cost": "Under $10", "tags": ["food", "drinks", "queer-friendly"]},
        {"title": "Explore the Mint Museum Uptown", "description": "Browse incredible modern art and craft exhibits. It's a quiet, reflective way to spend a weekday afternoon.", "period": "afternoon", "location": "Mint Museum, Uptown", "cost": "$15", "tags": ["art", "culture", "indoor"]},
        {"title": "Sunset Views at Fahrenheit", "description": "Head up to the rooftop bar at Fahrenheit for a cocktail and the best view of the Charlotte skyline at golden hour. A reliable, stunning spot no matter the day.", "period": "evening", "location": "Fahrenheit, Uptown", "cost": "$18\u2013$25", "tags": ["drinks", "scenic", "outdoor"]},
        {"title": "Evening Walk on the Rail Trail", "description": "Take a sunset stroll along the South End Rail Trail. Great views of the skyline and plenty of spots to stop for a quick bite or drink.", "period": "evening", "location": "Rail Trail, South End", "cost": "Free", "tags": ["outdoor", "fitness", "queer-friendly"]},
        {"title": "Dinner at Optimist Hall", "description": "Grab a casual bite from one of the many food stalls. Harriet's Hamburgers or Dumpling Lady are solid choices for a relaxed Monday night.", "period": "night", "location": "Optimist Hall, Optimist Park", "cost": "$15–$25", "tags": ["food", "casual"]}
    ],
    "Tuesday": [
        {"title": "Yoga at USNWC", "description": "Head out to the Whitewater Center for morning yoga. It's a peaceful way to start the day surrounded by nature.", "period": "morning", "location": "USNWC, West Charlotte", "cost": "Free (parking $6)", "tags": ["fitness", "outdoor", "nature"]},
        {"title": "Lunch at Common Market", "description": "Grab a massive deli sandwich and sit on the eclectic patio. Always a good mix of locals and a very welcoming vibe.", "period": "afternoon", "location": "Common Market, Plaza Midwood", "cost": "$12", "tags": ["food", "queer-friendly", "casual"]},
        {"title": "Sunset Views at Fahrenheit", "description": "Head up to the rooftop bar at Fahrenheit for a cocktail and the best view of the Charlotte skyline at golden hour. A reliable, stunning spot no matter the day.", "period": "evening", "location": "Fahrenheit, Uptown", "cost": "$18\u2013$25", "tags": ["drinks", "scenic", "outdoor"]},
        {"title": "Trivia Night at Legion Brewing", "description": "Join the lively Tuesday trivia crowd. Bring some friends, grab a Juicy Jay IPA, and test your random knowledge.", "period": "evening", "location": "Legion Brewing, Plaza Midwood", "cost": "Free (drinks extra)", "tags": ["drinks", "nightlife", "social"]},
        {"title": "Late Night Slice at Benny Pennello's", "description": "End the night with a massive, foldable slice of pizza. Open late and always hits the spot.", "period": "night", "location": "Benny Pennello's, NoDa", "cost": "$6", "tags": ["food", "late-night"]}
    ],
    "Wednesday": [
        {"title": "Greenway Bike Ride", "description": "Rent a bike and hit the Little Sugar Creek Greenway. A smooth, scenic ride that connects several neighborhoods.", "period": "morning", "location": "Little Sugar Creek Greenway", "cost": "Free", "tags": ["outdoor", "fitness"]},
        {"title": "Lunch at Camp North End", "description": "Grab some food from the food stalls and explore the massive, historic industrial campus. Great spots for photos and walking.", "period": "afternoon", "location": "Camp North End, North End", "cost": "$15", "tags": ["food", "outdoor", "culture"]},
        {"title": "Sunset Views at Fahrenheit", "description": "Head up to the rooftop bar at Fahrenheit for a cocktail and the best view of the Charlotte skyline at golden hour. A reliable, stunning spot no matter the day.", "period": "evening", "location": "Fahrenheit, Uptown", "cost": "$18\u2013$25", "tags": ["drinks", "scenic", "outdoor"]},
        {"title": "Half-Price Wine Night", "description": "Take advantage of Wednesday wine specials. Dilworth Tasting Room has a gorgeous patio and half-price select bottles.", "period": "evening", "location": "Dilworth Tasting Room, Dilworth", "cost": "$20–$40", "tags": ["drinks", "social", "outdoor"]},
        {"title": "Comedy Show at The Comedy Zone", "description": "Catch a midweek stand-up show. It's a fun, low-pressure way to break up the work week with some laughs.", "period": "night", "location": "The Comedy Zone, NC Music Factory", "cost": "$25", "tags": ["nightlife", "culture"]}
    ],
    "Thursday": [
        {"title": "Coffee and Pastries at Amelie's", "description": "Start the day at the iconic French bakery. The salted caramel brownie is legendary, and the eclectic decor is uniquely Charlotte.", "period": "morning", "location": "Amelie's French Bakery, NoDa", "cost": "$8", "tags": ["food", "drinks", "indoor"]},
        {"title": "Bechtler Museum of Modern Art", "description": "Check out the impressive mid-century modern art collection. Don't forget to take a photo with the Firebird sculpture out front.", "period": "afternoon", "location": "Bechtler Museum, Uptown", "cost": "$9", "tags": ["art", "culture", "indoor"]},
        {"title": "Sunset Views at Fahrenheit", "description": "Head up to the rooftop bar at Fahrenheit for a cocktail and the best view of the Charlotte skyline at golden hour. A reliable, stunning spot no matter the day.", "period": "evening", "location": "Fahrenheit, Uptown", "cost": "$18\u2013$25", "tags": ["drinks", "scenic", "outdoor"]},
        {"title": "River Jam at USNWC", "description": "Head to the Whitewater Center for live music by the river. A quintessential Charlotte summer/fall experience.", "period": "evening", "location": "USNWC, West Charlotte", "cost": "Free (parking $6)", "tags": ["music", "outdoor", "social"]},
        {"title": "Cocktails at Idlewild", "description": "There is no menu here—just tell the bartenders what flavors you like and they'll craft something custom. A perfect, intimate Thursday night spot.", "period": "night", "location": "Idlewild, NoDa", "cost": "$16", "tags": ["drinks", "nightlife", "queer-friendly"]}
    ],
    "Friday": [
        {"title": "Breakfast at Famous Toastery", "description": "Start Friday strong with a hearty breakfast. It's a local favorite with great options.", "period": "morning", "location": "Uptown", "cost": "$15", "tags": ["food", "casual"]},
        {"title": "Gallery Crawl in South End", "description": "Explore the local art galleries that often host open houses on Friday afternoons/evenings. A great way to support local artists.", "period": "afternoon", "location": "South End", "cost": "Free", "tags": ["art", "culture", "social"]},
        {"title": "Sunset Views at Fahrenheit", "description": "Head up to the rooftop bar at Fahrenheit for a cocktail and the best view of the Charlotte skyline at golden hour. Especially great on a Friday before a night out.", "period": "evening", "location": "Fahrenheit, Uptown", "cost": "$18\u2013$25", "tags": ["drinks", "scenic", "outdoor"]},
        {"title": "Dinner at Supperland", "description": "Kick off the weekend with a splurge dinner in a restored mid-century church. Incredible Southern steakhouse menu and gorgeous ambiance.", "period": "evening", "location": "Supperland, Plaza Midwood", "cost": "$60+", "tags": ["food", "drinks"]},
        {"title": "Dancing at The Scorpio", "description": "Hit up Charlotte's longest-running LGBTQ+ nightclub. Great music, drag shows, and a fun, welcoming crowd to dance the night away.", "period": "night", "location": "The Scorpio, West Charlotte", "cost": "$10 cover", "tags": ["nightlife", "queer-friendly", "music"]}
    ],
    "Saturday": [
        {"title": "South End Farmers Market", "description": "Stroll through the bustling farmers market at Atherton Mill. Pick up some fresh produce, local crafts, and grab a coffee.", "period": "morning", "location": "Atherton Mill, South End", "cost": "Free", "tags": ["food", "outdoor", "shopping"]},
        {"title": "Brewery Hopping in LoSo", "description": "Spend the afternoon exploring the Lower South End breweries. OMB, Sugar Creek, and Brewers at 4001 Yancey are all within walking distance.", "period": "afternoon", "location": "LoSo", "cost": "$20–$40", "tags": ["drinks", "social", "outdoor"]},
        {"title": "Sunset Views at Fahrenheit", "description": "Head up to the rooftop bar at Fahrenheit for a cocktail and the best view of the Charlotte skyline at golden hour. Saturday evenings here are electric.", "period": "evening", "location": "Fahrenheit, Uptown", "cost": "$18\u2013$25", "tags": ["drinks", "scenic", "outdoor"]},
        {"title": "Dinner in Plaza Midwood", "description": "Grab dinner at Soul Gastrolounge or another trendy spot along Central Ave. Great people-watching and vibrant neighborhood energy.", "period": "evening", "location": "Plaza Midwood", "cost": "$30", "tags": ["food", "social", "queer-friendly"]},
        {"title": "Barcade Night at Super Abari", "description": "Relive your childhood with vintage arcade games and pinball. Grab a drink and challenge your friends to some nostalgic gaming.", "period": "night", "location": "Super Abari Game Bar, Belmont", "cost": "$15", "tags": ["nightlife", "social", "drinks"]}
    ],
    "Sunday": [
        {"title": "Sunday Drag Brunch", "description": "Reserve a spot for a lively drag brunch. Great food, flowing mimosas, and incredible performances to cap off the weekend.", "period": "morning", "location": "Various locations", "cost": "$35", "tags": ["food", "queer-friendly", "entertainment"]},
        {"title": "Relaxing at Romare Bearden Park", "description": "Bring a blanket and lay out in the park with a direct view of the Uptown skyline. A perfect lazy Sunday afternoon activity.", "period": "afternoon", "location": "Romare Bearden Park, Uptown", "cost": "Free", "tags": ["outdoor", "nature", "relaxing"]},
        {"title": "Sunset Views at Fahrenheit", "description": "Head up to the rooftop bar at Fahrenheit for a cocktail and the best view of the Charlotte skyline at golden hour. The perfect Sunday wind-down.", "period": "evening", "location": "Fahrenheit, Uptown", "cost": "$18\u2013$25", "tags": ["drinks", "scenic", "outdoor"]},
        {"title": "Movie Night at Independent Picture House", "description": "Catch an indie film or documentary at Charlotte's dedicated arthouse cinema. A low-key way to end the weekend.", "period": "night", "location": "Independent Picture House, NoDa", "cost": "$12", "tags": ["culture", "indoor", "entertainment"]}
    ]
}

CALLS = [
    {
        "name": "Budget Events",
        "tiers": [
            {"id": "free", "label": "Free", "emoji": "🆓", "max_cost": "Free", "focus": "completely free activities — no entry fees, no mandatory purchases. Include: queer-friendly spaces, parks, neighborhood walks, no-cover bars/cafes, free gallery openings, free outdoor concerts, community meetups."},
            {"id": "under20", "label": "Under $20", "emoji": "💵", "max_cost": "$20", "focus": "activities costing $20 or less per person. Include: cheap eats, local coffee shops, brewery trivia nights, run clubs, dive bars, low-cover events, gallery shows, happy hour deals."}
        ]
    },
    {
        "name": "Premium Events",
        "tiers": [
            {"id": "under50", "label": "Under $50", "emoji": "🍸", "max_cost": "$50", "focus": "activities costing up to $50 per person. Include: mid-range dining, craft cocktail bars, ticketed music shows, drag performances, Camp North End events, US National Whitewater Center."},
            {"id": "splurge", "label": "Splurge", "emoji": "🌟", "max_cost": "no limit", "focus": "premium experiences with no budget limit. Include: high-end dining (reservation required), VIP nightlife, major concert or theater tickets, upscale cocktail lounges, exclusive pop-ups."},
            {"id": "wildcard", "label": "Wildcard", "emoji": "🃏", "max_cost": "varies", "focus": "unique, unusual, or highly dynamic events happening specifically these days. Can be any budget."}
        ]
    }
]

# ── JSON schema embedded in prompt ────────────────────────────────────────────
SYSTEM_INSTRUCTION = """You are a local city guide for Charlotte, NC, with deep knowledge of the queer social scene.

Target audience: 27-year-old gay man, social, adventurous, familiar with Charlotte.

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
  "tier":        "string — the ID of the budget tier this belongs to"
}

Example of the expected output format (shortened):
[{"title":"Morning Run at Freedom Park","description":"Join the free Saturday morning run group...","day":"today","period":"morning","location":"Freedom Park, Myers Park","cost":"Free","tags":["outdoor","fitness","queer-friendly"],"tier":"free"}]"""

def make_prompt(call_def: dict, today_dow: str, today: str, tomorrow_dow: str, tomorrow: str) -> str:
    tiers_info = ""
    for t in call_def["tiers"]:
        tiers_info += f"- Tier ID: '{t['id']}' (Max cost: {t['max_cost']}). Focus on: {t['focus']}\n"

    return f"""Search the web for specific events and activities happening in Charlotte on {today_dow} {today} and {tomorrow_dow} {tomorrow}.

Generate 6–8 activities PER TIER for EACH day (today and tomorrow), covering morning, afternoon, evening, and night time slots.
Provide events for the following tiers:
{tiers_info}

Remember to return a minified JSON array where each object has a 'tier' field matching one of the Tier IDs above."""

# ── JSON extractor ─────────────────────────────────────────────────────────────
def extract_json(text: str) -> list:
    """Extract a JSON array from model output, handling fenced code blocks."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)
    text = text.strip()

    start = text.find("[")
    end   = text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("No JSON array found in response")
    raw = text[start:end+1]
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("Expected JSON array at top level")
    return data

def validate_card(card: dict, allowed_tiers: list) -> dict | None:
    """Normalise and validate a single activity card. Returns None if invalid."""
    required = ("title", "description", "day", "period", "location", "cost", "tier")
    if not all(k in card for k in required):
        return None
    if card.get("day") not in ("today", "tomorrow"):
        return None
    if card.get("period") not in ("morning", "afternoon", "evening", "night"):
        card["period"] = "afternoon"  # safe default
    if card.get("tier") not in allowed_tiers:
        return None
        
    card.setdefault("tags", [])
    card["title"]       = str(card["title"])[:80]
    card["description"] = str(card["description"])[:400]
    card["location"]    = str(card["location"])[:80]
    card["cost"]        = str(card["cost"])[:20]
    return card

# ── Fetch Grouped Tiers ─────────────────────────────────────────────────────────────
def fetch_grouped_tiers(client: genai.Client, call_def: dict, today_dow: str, today: str,
               tomorrow_dow: str, tomorrow: str, retries: int = 3) -> dict:
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
                    temperature=0.2,   # lower = more deterministic JSON
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
            activities = [c for c in (validate_card(c, allowed_tiers) for c in raw_cards) if c]

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
        )
        all_activities.extend(result["activities"])
        all_sources.extend(result["sources"])
        if result["error"]:
            errors.append(f"{call_def['name']}: {result['error']}")

    # Add Baseline
    baseline_today = BASELINE_ACTIVITIES.get(today_dow, [])
    for a in baseline_today:
        a = a.copy()
        a["day"] = "today"
        a["tier"] = "baseline"
        all_activities.append(a)
        
    baseline_tomorrow = BASELINE_ACTIVITIES.get(tomorrow_dow, [])
    for a in baseline_tomorrow:
        a = a.copy()
        a["day"] = "tomorrow"
        a["tier"] = "baseline"
        all_activities.append(a)

    print(f"  Added {len(baseline_today) + len(baseline_tomorrow)} baseline activities.")

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

    print("\nExporting events_data.js…")
    export_events_data()

    if not no_push:
        print("\nPushing to GitHub…")
        git_push(today.isoformat())

    print("\nDone.")

if __name__ == "__main__":
    main()
