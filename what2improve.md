# Charlotte On The Run — What to Improve

> Audit: April 21, 2026 · 56 items in DB · 3 with real dates · ~35% actual events

---

## Honest Assessment

The site is not good right now. Out of 56 items showing:

- **3 are dated real events** (all from one feed: Greenville Journal Arts)
- **~20 are genuine event-adjacent articles** (concert recaps, festival announcements without dates)
- **~33 are pure noise**: job postings, real estate tours, attorney directories, cannabis policy, gift ads, travel pieces, home renovations, film interviews, political news

A user landing on this page would see a feed that reads like a random local news aggregator, not an events guide. The core promise — *upcoming events in Charlotte and surrounding areas* — is not being delivered.

---

## Root Causes (in order of impact)

### 1. EVENT_SCORE_MIN is too low (set to 1)
The threshold of 1 allows almost anything through. A score of 1 can be earned by a single weak keyword match. In practice, it lets through:
- "Workers Compensation Attorneys in Chicago" (Triad City Beat) → score: 2 (matched "class", "walk")
- "Proposed 2027 federal budget targets LGBTQ+ health" → score: 1 (matched "free")
- "Charlotte homebuyers are picky" → score: 1 (matched "fair")
- "Princess Grand Jamaica travel article" → score: 3 (matched "family", "kids", "free")

**Fix: raise to 4 or 5.** Re-audit after each bump.

### 2. No content blocklist
Entire categories of content are structurally ineligible to be events but score high enough to pass:
- Job postings ("Director of Marketing", "Marketing Coordinator (Part-time)")
- Real estate ("Home Tour", "Mansion Monday", "homebuyers")
- Sponsored ads ("Tinggly Experience box")
- Casino/financial spam ("Virtual Currency", "Non-Agency Loans", "Workers Comp Attorneys")
- Political/policy ("federal budget targets", "Cannabis Report", "Trump admin")
- Travel articles ("Princess Grand Jamaica")
- Film/book interviews ("Gina Gershon", "Alan Berliner")

**Fix: add a hard title-level blocklist before scoring.**

### 3. Three feeds are broken/polluted and should be cut immediately

| Feed | Problem | Action |
|------|---------|--------|
| **Triad City Beat** | Actively publishing Chicago/Illinois attorney directories, casino finance articles — nothing to do with Greensboro | ❌ Remove |
| **Charlotte Magazine** | 0% event ratio, avg score -0.2 | ❌ Remove |
| **Arts & Science Council** | Only publishing job board listings | ❌ Remove or manually filter |

### 4. Date extraction is not working
Only 3 of 56 items have an extracted date. Articles like:
- "Charlotte's Stars and Stripes to take over Truist Field for **July Fourth**" → no date extracted
- "Artisphere announces music lineup for **2026 festival**" → no date extracted
- "Indie Craft Parade... **Sept. 11-13**" → no date extracted

The spaCy NER + regex pipeline was added to the code but existing DB rows predate it (all have `date_confidence=0`). New fetches will get dates, but the current 56 items won't.

**Fix: run backfill script against existing rows.**

### 5. Static site data doesn't update
`docs/events_data.js` is a one-time snapshot from April 20. The bot runs and fetches daily but the website never sees new data. Users will see the same 56 stale items forever unless someone manually re-exports and pushes.

**Fix: GitHub Actions workflow that runs fetcher + export + commit on a schedule.**

---

## Fix List — Ordered by Bang-for-Buck

### Do these now (no new dependencies)

**Step 1 — Raise score threshold**
```bash
# In .env
EVENT_SCORE_MIN=4
```
Re-run `python fetcher.py` and spot-check what's left. If it's still noisy, push to 5.

**Step 2 — Add blocklist to fetcher.py**
```python
TITLE_BLOCKLIST = [
    "workers compensation", "attorney", "mortgage", "non-agency loan",
    "virtual currency", "social casino", "gift idea", "tinggly",
    "mansion monday", "home tour", "home renovation",
    "real estate", "homebuyer",
    "job description", "hiring", "part-time", "executive director",
    "director of marketing", "marketing coordinator",
    "federal budget", "cannabis report", "lgbtq+ health",
    "trump admin", "proposed budget",
    "travel:", "miles from charlotte",
    "letter:", "opinion:",
]

def is_blocked(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in TITLE_BLOCKLIST)
```
Call `is_blocked(item["title"])` before `score_event()` — if blocked, drop immediately.

**Step 3 — Remove dead feeds from feeds.py**
Remove: Charlotte Magazine, Triad City Beat, Arts & Science Council.
Then re-run `python validate_feeds.py` to regenerate `feeds_live.json`.

**Step 4 — Backfill dates on existing rows**
```python
# Run once: python backfill_dates.py
from fetcher import get_db
from utils.date_extractor import extract_event_datetime
db = get_db()
rows = db.execute(
    "SELECT sig, title, description FROM events WHERE date_confidence=0"
).fetchall()
for r in rows:
    d, t, conf = extract_event_datetime(r['title'], r['description'] or '')
    if d or conf:
        db.execute(
            "UPDATE events SET event_date=?, event_time=?, date_confidence=? WHERE sig=?",
            (d, t, conf, r['sig'])
        )
db.commit()
print("Done")
```

### Do these next (automation)

**Step 5 — GitHub Actions daily refresh**
```yaml
# .github/workflows/refresh_site.yml
name: Refresh site data
on:
  schedule:
    - cron: '0 13 * * *'   # 9 AM ET daily
  workflow_dispatch:

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install python-telegram-bot python-dotenv spacy python-dateutil
      - run: python -m spacy download en_core_web_sm
      - run: python fetcher.py
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          DB_PATH: events.db
          FEEDS_FILE: feeds_live.json
          EVENT_SCORE_MIN: 4
      - run: python export_site_data.py
      - run: |
          git config user.email "bot@github.com"
          git config user.name "Charlotte Bot"
          git add docs/events_data.js
          git diff --cached --quiet || git commit -m "auto: refresh events $(date +%Y-%m-%d)"
          git push
```

**Step 6 — Replace dropped feeds with better sources**

| Add | URL | Why |
|-----|-----|-----|
| Blumenthal Performing Arts | blumenthalarts.org/feed/ | Pure event calendar, Charlotte |
| Visit Charlotte | Eventbrite Charlotte or ilovecharlottenc.com | Official tourism events |
| NC Museum of Art | ncartmuseum.org/feed/ | High quality, dated events |
| Creative Loafing Charlotte | clclt.com/rss | High event density alt |

---

## Expected State After Fixes

| Metric | Now | After fixes |
|--------|-----|-------------|
| Items shown | 56 | ~20–30 (higher quality) |
| Items with dates | 3 (5%) | ~15–20 (50–70%) |
| Genuine events | ~18 (~32%) | ~18–25 (~80–90%) |
| Spam / noise | ~38 (~68%) | <5 |
| Data freshness | Frozen (Apr 20) | Daily auto-update |

The goal is fewer items, all real, all with dates. 20 great events beats 56 random articles every time.
