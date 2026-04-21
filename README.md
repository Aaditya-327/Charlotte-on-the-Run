# Charlotte On The Run 🏃‍♂️

> A precision-focused, AI-augmented local event discovery portal for Charlotte, NC and surrounding regions — built for people who actually want to *do things*.

**Live site →** [aaditya-327.github.io/Charlotte-on-the-Run](https://aaditya-327.github.io/Charlotte-on-the-Run)

---

## What Is This?

Charlotte On The Run is a personal event dashboard that aggregates **real local event signals** from 23 curated RSS feeds across 5 regions, then layers on **Gemini AI-generated activity guides** (with live Google Search grounding) — all rendered as a fast, zero-dependency static site hosted on GitHub Pages.

The goal is simple: open the site on any given day and immediately know what's worth doing in Charlotte and up to 2.5 hours away — without wading through job boards, real estate listings, or recycled press releases.

---

## Goals

| Goal | Status |
|------|--------|
| Aggregate high-signal local events from RSS (not just news) | ✅ |
| Filter out junk: jobs, attorney spam, real estate, finance | ✅ |
| Extract specific event dates with confidence scoring | ✅ |
| Serve a clean, fast static site with zero dependencies | ✅ |
| Add AI-generated daily activity guides by budget tier | ✅ |
| Automate daily refresh via GitHub Actions + local launchd | ✅ |
| Cover Charlotte, Triad, Greenville SC, Asheville, Triangle NC | ✅ |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Data Pipeline                         │
│                                                             │
│   feeds.py          23 curated RSS feeds                    │
│       │                 (5 regions, 3 priority tiers)       │
│       ▼                                                     │
│   fetcher.py        Fetch → Score → Filter → Store          │
│       │              • TITLE_BLOCKLIST (pre-filter junk)    │
│       │              • EVENT_SCORE_MIN = 4                  │
│       │              • Date extraction (regex + NLP)        │
│       │              • SQLite (events.db)                   │
│       ▼                                                     │
│   export_site_data  → docs/events_data.js                   │
│                                                             │
│   daily_guide.py    Gemini 2.5 Flash + Google Search        │
│       │              • 4 budget tiers (Free/$20/$50/Splurge)│
│       │              • Structured JSON cards per activity   │
│       │              → docs/daily_guide_data.js             │
│       ▼                                                     │
│   GitHub Actions / launchd → git push → GitHub Pages        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     Static Frontend                          │
│   docs/index.html   Pure HTML + Vanilla JS + CSS            │
│                      • Filter by Region, Time, Free          │
│                      • Search across all events             │
│                      • ✦ AI Guide mode (4 budget tiers)     │
│                      • AI cards mixed into RSS grid          │
└─────────────────────────────────────────────────────────────┘
```

---

## Current State (as of April 21, 2026)

| Metric | Value |
|--------|-------|
| Live RSS feeds | **23** |
| Events in DB | **60** |
| Events with confirmed dates | **26** |
| Regions covered | **5** |
| AI activity cards (today + tomorrow) | **47** |
| AI tiers | Free · Under $20 · Under $50 · Splurge |
| Dead feeds (probed & catalogued) | **58** |

---

## Project Structure

```
Charlotte On The Run/
│
├── feeds.py                 Feed registry — 25 live feeds with region/distance/priority
├── fetcher.py               Core engine: fetch → score → blocklist → date-extract → store
├── daily_guide.py           Gemini AI daily guide — structured JSON card output
├── validate_feeds.py        Probe all feeds, emit feeds_live.json / feeds_dead.json
├── test_feeds.py            Concurrent probe of 100 candidate feeds with event scoring
├── backfill_dates.py        One-off: purge junk events, re-extract dates from DB
│
├── utils/
│   ├── scoring.py           Event keyword scoring (37 signals, weighted)
│   └── date_extractor.py    Regex + NLP date extraction with confidence levels
│
├── docs/                    GitHub Pages static site root
│   ├── index.html           Single-page app (filters, search, AI guide, event grid)
│   ├── events_data.js       Exported events array (auto-generated)
│   ├── daily_guide.json     Raw AI guide output (JSON)
│   └── daily_guide_data.js  AI guide as JS module (auto-generated)
│
├── feeds_live.json          Validated live feed list
├── feeds_dead.json          Dead feeds from latest probe
├── events.db                SQLite event store
│
├── bot.py                   Telegram bot for push notifications
├── daily_fetch.yml          GitHub Actions workflow (daily 9 AM ET)
├── com.charlotteontherun.guide.plist  macOS launchd job (7 AM ET)
│
├── run.sh / start.command / stop.command   Local dev helpers
├── what2improve.md          Living audit doc: feed scores, UX issues, roadmap
└── .env                     API keys (not committed)
```

---

## Key Design Decisions

### 1. Score-then-filter, not keyword-search
Every RSS item is scored against 37 event-intent keywords (`festival`, `tickets`, `admission`, `rsvp`, etc.) weighted by title vs. body position. Items below `EVENT_SCORE_MIN = 4` are dropped before hitting the database. This keeps the DB clean rather than filtering at render time.

### 2. Hard blocklist before scoring
A `TITLE_BLOCKLIST` in `fetcher.py` catches non-event content patterns (job postings, attorney directories, real estate listings, sponsored finance content) *before* the scoring loop runs — a cheap, fast pre-filter that prevents score gaming.

### 3. Gemini returns structured JSON, not prose
`daily_guide.py` instructs Gemini to return a raw JSON array of activity objects (title, description, location, cost, period, tags) — not markdown. This means cards are parsed directly with `json.loads()`, no text splitting, no heuristic day-detection. Each card is a discrete unit the frontend renders immediately.

### 4. Static site, no server
`docs/events_data.js` and `docs/daily_guide_data.js` are committed JS modules — the site has no API, no server, no build step. GitHub Pages serves them as-is. Filters and search run entirely in the browser. Load time < 100ms.

### 5. Two-layer automation
- **GitHub Actions** (`daily_fetch.yml`): runs `fetcher.py` + `daily_guide.py` + git push daily at 9 AM ET on the server.
- **launchd** (`com.charlotteontherun.guide.plist`): same pipeline at 7 AM ET locally, ensuring the site updates even if Actions is down.

---

## Feed Coverage

Feeds are validated weekly via `test_feeds.py`, which probes all 100 candidate URLs concurrently and scores each by event-keyword density.

### Active Feeds by Region

| Region | Drive Time | Key Sources |
|--------|-----------|-------------|
| **Charlotte** | 0 min | Charlotte on the Cheap, Charlotte Is Creative, Queen City Nerve, Scoop Charlotte, QNotes Carolinas, Charlotte Pride, SouthPark Magazine, CLTtoday |
| **Triad** | ~1 hr | Triad City Beat (Culture), WStoday, Greensboro.com Entertainment |
| **Greenville SC** | ~1h 30m | Greenville Journal (Events + Arts), GVLtoday, Town Carolina, COLAtoday |
| **Asheville** | ~2 hr | Mountain Xpress |
| **Triangle NC** | ~2h 30m | Walter Magazine, Triangle on the Cheap, Raleigh Magazine, Durham Magazine, INDY Week, RALtoday |

### Dropped Feeds (58 total)
Full register in `what2improve.md` and `feeds.py` header. Notable removals: Charlotte Observer / N&O (McClatchy paywall timeout), Blumenthal Arts (404), WFAE (404), Gantt Center (XML parse error), all Journal Now / Yes! Weekly / Free Times properties (HTTP 429 rate-limiting), Charlotte Ballet / Mint Museum / Reynolda House (single-venue org feeds), Charlotte Parent (niche demographic, low event signal), Unpretentious Palate (food blog).

---

## AI Daily Guide

`daily_guide.py` runs four Gemini 2.5 Flash queries (with Google Search grounding) every morning, one per budget tier:

| Tier | Emoji | Focus |
|------|-------|-------|
| Free | 🆓 | No-cost events, queer-friendly spaces, parks, no-cover venues |
| Under $20 | 💵 | Cheap eats, trivia nights, brewery run clubs, gallery shows |
| Under $50 | 🍸 | Craft cocktail bars, ticketed music, drag shows, Camp North End |
| Splurge | 🌟 | High-end dining, VIP nightlife, theater, upscale lounges |

Each tier yields ~10–13 structured activity cards covering **today** and **tomorrow**, each with:
- `title`, `description`, `location` (venue + neighborhood)
- `cost`, `period` (morning/afternoon/evening/night), `tags`

In the site, clicking **✦ AI Guide** switches to AI-only mode with a tier selector. In the default mixed view, AI cards from the Free tier are interleaved into the RSS grid every 4 cards.

---

## Setup

### Prerequisites
- Python 3.11+
- `pip install -r requirements.txt` (or install individually: `feedparser`, `python-dotenv`, `requests`, `google-genai`)
- SQLite (built into Python)

### `.env` file
```env
TELEGRAM_TOKEN=...
TELEGRAM_OWNER_ID=...
DB_PATH=events.db
FEEDS_FILE=feeds_live.json
EVENT_SCORE_MIN=4
GEMINI_API_KEY=...
```

### Run manually
```bash
# Activate venv
source .venv/bin/activate

# Validate all feeds and regenerate feeds_live.json
python validate_feeds.py

# Fetch new events from all live feeds
python fetcher.py

# Generate today's AI activity guide (requires paid Gemini API)
python daily_guide.py --no-push

# Probe all 100 candidate feeds for signal quality
python test_feeds.py
```

### Local site preview
Open `docs/index.html` directly in a browser — no server needed.

### Automation (macOS)

Install the launchd job to run at 7 AM daily:
```bash
cp com.charlotteontherun.guide.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.charlotteontherun.guide.plist
```

Logs: `logs/daily_guide.log` / `logs/daily_guide_err.log`

---

## Scoring System

Event scoring is in `utils/scoring.py`. Every RSS item title + description is scanned against a weighted keyword list:

**Tier 1 keywords** (weight 3): `festival`, `concert`, `tickets`, `admission`, `rsvp`, `register`, `screening`, `exhibit opens`

**Tier 2 keywords** (weight 2): `event`, `show`, `performance`, `opening`, `reception`, `fundraiser`, `workshop`, `tour`

**Tier 3 keywords** (weight 1): `music`, `art`, `food`, `beer`, `pride`, `drag`, `run`, `market`, `free`

Minimum score to enter DB: **4 points**. Title matches count 2× body matches.

---

## Roadmap

- [ ] **Telegram push notifications** — daily digest to bot at 8 AM
- [ ] **Category tags** — Music / Food / Art / Sports filter chips on the site
- [ ] **Asheville expansion** — add Mountain Xpress Events category feed + AVLtoday once feed stabilizes
- [ ] **Deeper SC coverage** — COLAtoday (Columbia) already in feeds, explore Visit Greenville SC direct scrape
- [ ] **LLM re-ranking** — optional Gemini pass to classify "event" vs "event-adjacent news" on borderline items
- [ ] **Event deduplication** — fuzzy-match titles across sources to collapse cross-posted items
- [ ] **Map view** — plot confirmed-date events on a Leaflet map by venue geocode

---

## Contributing

This is a personal tool, but PRs for new high-signal RSS feeds are welcome. Run `test_feeds.py` to score any feed before proposing it, and add it to `feeds.py` with the correct `region`, `distance`, and `priority`.

---

*Built in Charlotte. Updated daily.*
