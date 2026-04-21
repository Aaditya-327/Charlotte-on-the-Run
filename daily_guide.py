#!/usr/bin/env python3
"""
daily_guide.py — Fetch AI-generated daily activity cards for Charlotte using
Gemini 2.5 Flash with Google Search grounding.

Gemini is asked to return a JSON array of activity objects — no markdown blobs.
Each activity:
  {
    "title":       "Short activity name",
    "description": "2-3 sentence description with specifics",
    "day":         "today" | "tomorrow",
    "period":      "morning" | "afternoon" | "evening" | "night",
    "location":    "Venue name, Neighborhood",
    "cost":        "Free" | "$X" | "$X–$Y",
    "tags":        ["outdoor", "food", "queer-friendly", ...]
  }

Schedule: launchd at 7 AM ET (com.charlotteontherun.guide.plist)
Usage:    python daily_guide.py [--no-push]
"""

import json, os, re, subprocess, sys, time
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from fetcher import run_fetch

load_dotenv()

API_KEY  = os.getenv("GEMINI_API_KEY")
OUT_FILE = Path(__file__).parent / "docs" / "daily_guide.json"

TIERS = [
    {"id": "free",     "label": "Free",       "emoji": "🆓", "max_cost": "Free"},
    {"id": "under20",  "label": "Under $20",  "emoji": "💵", "max_cost": "$20"},
    {"id": "under50",  "label": "Under $50",  "emoji": "🍸", "max_cost": "$50"},
    {"id": "splurge",  "label": "Splurge",    "emoji": "🌟", "max_cost": "no limit"},
    {"id": "wildcard", "label": "Wild Card",  "emoji": "🎪", "max_cost": "any"},
]

# ── Predefined categories (used in schema + frontend filter) ──────────────────
VALID_CATS = {
    "music", "food", "drinks", "arts", "outdoors", "nightlife",
    "comedy", "sports", "theater", "fitness", "market", "drag",
    "film", "weird", "family",
}

# ── JSON schema embedded in prompt ────────────────────────────────────────────
SCHEMA = """{
  "title":       "string — short activity name (≤60 chars)",
  "description": "string — 2-3 sentences with specific details (venue, what to expect, why it's worth it)",
  "day":         "today | tomorrow",
  "period":      "morning | afternoon | evening | night",
  "location":    "string — venue name + neighborhood (e.g. 'Optimist Hall, NoDa')",
  "cost":        "string — e.g. 'Free', '$12', '$8–$15'",
  "category":    ["1-3 strings chosen ONLY from: music, food, drinks, arts, outdoors, nightlife, comedy, sports, theater, fitness, market, drag, film, weird, family"],
  "tags":        ["2-4 specific detail tags like 'dog-friendly', 'rooftop', 'BYOB', 'all-ages', 'queer-friendly'"]
}"""

def make_prompt(tier: dict, today_dow: str, today: str,
                tomorrow_dow: str, tomorrow: str) -> str:
    tier_id   = tier["id"]
    max_cost  = tier["max_cost"]
    tier_name = tier["label"]

    if tier_id == "free":
        focus = (
            "completely free activities — no entry fees, no mandatory purchases. "
            "Include: queer-friendly spaces, parks, neighborhood walks, no-cover bars/cafes, "
            "free gallery openings, free outdoor concerts, community meetups."
        )
    elif tier_id == "under20":
        focus = (
            "activities costing $20 or less per person. "
            "Include: cheap eats, local coffee shops, brewery trivia nights, run clubs, "
            "dive bars, low-cover events, gallery shows, happy hour deals."
        )
    elif tier_id == "under50":
        focus = (
            "activities costing up to $50 per person. "
            "Include: mid-range dining, craft cocktail bars, ticketed music shows, "
            "drag performances, Camp North End events, US National Whitewater Center."
        )
    elif tier_id == "splurge":
        focus = (
            "premium experiences with no budget limit. "
            "Include: high-end dining (reservation required), VIP nightlife, "
            "major concert or theater tickets, upscale cocktail lounges, exclusive pop-ups."
        )
    else:  # wildcard
        focus = (
            "bizarre, unexpected, and one-of-a-kind events — the weirder the better. "
            "Search specifically for: pro wrestling (WWE, AEW, indie wrestling), "
            "demolition derbies, monster truck shows, roller derby bouts, "
            "competitive eating contests, arm wrestling competitions, "
            "burlesque shows, drag racing, oddities markets, fringe theater, "
            "murder mystery dinners, paranormal tours, taxidermy workshops, "
            "ax throwing leagues, goat yoga, adult game shows, hypnotist shows, "
            "professional wrestling, midget wrestling, comedy roasts, "
            "anything campy, kitschy, cult-classic, or genuinely surprising. "
            "DO NOT include normal bars, restaurants, standard live music, or typical city-guide content. "
            "Every single card must be something a person would say 'wait, that's actually happening?' about."
        )

    if tier_id == "wildcard":
        audience = "anyone who wants something genuinely memorable, weird, or surprising — not a typical night out"
        schema_note = (
            'For "category", use "weird" for all wildcard cards, plus any other applicable categories. '
            "Tags should be specific descriptors like 'campy', 'novelty', 'one-night-only', 'audience-participation'."
        )
    else:
        audience = "27-year-old gay man, social, adventurous, familiar with Charlotte"
        schema_note = (
            'For "category", pick 1-3 from ONLY: music, food, drinks, arts, outdoors, nightlife, '
            "comedy, sports, theater, fitness, market, drag, film, weird, family. "
            "Tags should be specific details like 'dog-friendly', 'rooftop', 'BYOB', 'queer-friendly', 'all-ages'."
        )

    return f"""You are a local city guide for Charlotte, NC, with deep knowledge of local events across all categories.

Search the web for specific events and activities happening in Charlotte (and within 30 miles) on {today_dow} {today} and {tomorrow_dow} {tomorrow}.

Generate 5–7 activities for EACH day (today and tomorrow), covering morning, afternoon, evening, and night time slots.
Focus on: {focus}

Target audience: {audience}.

IMPORTANT: Respond ONLY with a valid JSON array. No explanation, no markdown, no prose — just the raw JSON array.
Each element must match this exact schema:
{SCHEMA}
{schema_note}

Example of the expected output format (shortened):
[
  {{"title": "Morning Run at Freedom Park", "description": "Join the free Saturday morning run group...", "day": "today", "period": "morning", "location": "Freedom Park, Myers Park", "cost": "Free", "tags": ["outdoor", "fitness", "queer-friendly"]}},
  {{"title": "Brunch at The Fig Tree", "description": "...", "day": "today", "period": "morning", "location": "The Fig Tree, Elizabeth", "cost": "$18–$25", "tags": ["food"]}}
]

Now generate the full array for {today_dow} {today} and {tomorrow_dow} {tomorrow} (tier: {tier_name}, max cost per activity: {max_cost}):"""


# ── JSON extractor ─────────────────────────────────────────────────────────────
def extract_json(text: str) -> list:
    """Extract a JSON array from model output, handling fenced code blocks."""
    # Strip ```json ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)
    text = text.strip()

    # Find first [ ... ] block
    start = text.find("[")
    end   = text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("No JSON array found in response")
    raw = text[start:end+1]
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("Expected JSON array at top level")
    return data


def validate_card(card: dict, tier_id: str) -> dict | None:
    """Normalise and validate a single activity card. Returns None if invalid."""
    required = ("title", "description", "day", "period", "location", "cost")
    if not all(k in card for k in required):
        return None
    if card.get("day") not in ("today", "tomorrow"):
        return None
    if card.get("period") not in ("morning", "afternoon", "evening", "night"):
        card["period"] = "afternoon"
    card.setdefault("tags", [])
    card["tier"] = tier_id
    card["title"]       = str(card["title"])[:80]
    card["description"] = str(card["description"])[:400]
    card["location"]    = str(card["location"])[:80]
    card["cost"]        = str(card["cost"])[:20]
    # Normalize category to fixed vocabulary
    raw = card.get("category", [])
    if isinstance(raw, str):
        raw = [raw]
    card["category"] = [c.lower() for c in raw if c.lower() in VALID_CATS][:3]
    # Wildcard tier always gets "weird" category
    if tier_id == "wildcard" and "weird" not in card["category"]:
        card["category"].insert(0, "weird")
    return card


# ── Fetch one tier ─────────────────────────────────────────────────────────────
def fetch_tier(client: genai.Client, tier: dict, today_dow: str, today: str,
               tomorrow_dow: str, tomorrow: str, retries: int = 3) -> dict:
    tier_id = tier["id"]
    prompt  = make_prompt(tier, today_dow, today, tomorrow_dow, tomorrow)
    print(f"  Fetching {tier_id}…", flush=True)

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.4,   # lower = more deterministic JSON
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
            activities = [c for c in (validate_card(c, tier_id) for c in raw_cards) if c]

            # Token usage
            um = response.usage_metadata
            in_tok  = getattr(um, "prompt_token_count",     0) or 0
            out_tok = getattr(um, "candidates_token_count", 0) or 0

            today_n    = sum(1 for c in activities if c["day"] == "today")
            tomorrow_n = sum(1 for c in activities if c["day"] == "tomorrow")
            print(f"    ✓ {len(activities)} cards "
                  f"(today={today_n}, tomorrow={tomorrow_n}) | "
                  f"{len(sources)} sources | "
                  f"{in_tok:,}in {out_tok:,}out tokens")
            return {
                "id":         tier_id,
                "label":      tier["label"],
                "emoji":      tier["emoji"],
                "activities": activities,
                "sources":    sources,
                "usage":      {"input_tokens": in_tok, "output_tokens": out_tok},
                "error":      None,
            }

        except Exception as e:
            msg = str(e)
            if "429" in msg and attempt < retries - 1:
                m = re.search(r"retryDelay.*?(\d+)s", msg)
                wait = int(m.group(1)) + 5 if m else 60
                print(f"    Rate limited — waiting {wait}s (retry {attempt+2}/{retries})…")
                time.sleep(wait)
                continue
            print(f"    ERROR [{tier_id}]: {msg[:160]}", file=sys.stderr)
            return {
                "id":         tier_id,
                "label":      tier["label"],
                "emoji":      tier["emoji"],
                "activities": [],
                "sources":    [],
                "usage":      {"input_tokens": 0, "output_tokens": 0},
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

    # ── Step 1: refresh RSS feeds before generating guide or exporting ────────
    print("Fetching RSS feeds…")
    try:
        stats = run_fetch(priority_filter=2)
        print(f"  Feeds: +{stats['new']} new  |  {stats['skipped']} skipped  "
              f"|  {stats['dropped']} dropped  |  {stats['errors']} errors\n")
    except Exception as e:
        print(f"  Feed fetch error (continuing): {e}\n", file=sys.stderr)

    if not API_KEY:
        print("ERROR: GEMINI_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    client  = genai.Client(api_key=API_KEY)
    results = []

    for tier in TIERS:
        result = fetch_tier(
            client, tier,
            today_dow, today_s,
            tomorrow_dow, tomorrow_s,
        )
        results.append(result)

    # ── Cost calculation (Gemini 2.5 Flash + Search grounding) ──────────────────
    # Prices: $0.075/1M input · $0.30/1M output · $0.035/search call
    PRICE_IN  = 0.075 / 1_000_000
    PRICE_OUT = 0.30  / 1_000_000
    PRICE_SEARCH = 0.035          # per grounding call (one per tier)

    total_in  = sum(r["usage"]["input_tokens"]  for r in results)
    total_out = sum(r["usage"]["output_tokens"] for r in results)
    search_calls = len([r for r in results if not r["error"]])
    approx_usd = (total_in * PRICE_IN) + (total_out * PRICE_OUT) + (search_calls * PRICE_SEARCH)

    run_cost = {
        "input_tokens":  total_in,
        "output_tokens": total_out,
        "search_calls":  search_calls,
        "approx_usd":    round(approx_usd, 4),
    }
    print(f"\nCost: {total_in:,} in + {total_out:,} out tokens | "
          f"{search_calls} search calls | ~${approx_usd:.4f}")

    output = {
        "generated_at": today.isoformat(),
        "today":        today_s,
        "today_dow":    today_dow,
        "tomorrow":     tomorrow_s,
        "tomorrow_dow": tomorrow_dow,
        "tiers":        results,
        "run_cost":     run_cost,
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
              + (f" ⚠ {r['error'][:60]}" if r["error"] else ""))

    print("\nExporting events_data.js…")
    export_events_data()

    if not no_push:
        print("\nPushing to GitHub…")
        git_push(today.isoformat())

    print("\nDone.")


if __name__ == "__main__":
    main()
