# Charlotte On The Run — What to Improve

> Audit: April 21, 2026 · **19 events in DB (post-cleanup)** · 3 with dates · ~90% genuine events
> *(was: 56 items, ~35% genuine, 81 junk rows deleted)*

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
| Items shown | 56 → **19** | 40–60 (with daily fetch) |
| Items with dates | 3 (5%) → **3 (16%)** | >50% |
| Genuine events | ~35% → **~90%** | >95% |
| Spam / noise | ~68% → **<10%** | <5% |
| Data freshness | Frozen (Apr 20) | Daily auto-update |

The goal is fewer items, all real, all with dates. 20 great events beats 56 random articles every time.

---

## 🖥️ Site-Specific Issues

The static site at `docs/index.html` has these specific problems beyond just data quality:

### What's broken or missing on the site

| Issue | Detail | Fix |
|-------|--------|-----|
| **Dated vs undated mixed** | Events with confirmed dates and "Date TBD" items appear interleaved with no visual separation | Add a divider section header between dated and undated groups |
| **"Date TBD" is dominant** | 16 of 19 cards say "Date TBD" — the date field is the primary info a user wants | Bold/highlight the 3 that have dates; grey out or de-emphasise TBD ones |
| **No drive time on cards** | Cards show region name but not how far ("1h 30m") — user has to know Greenville = 1.5h | Add the `distance` field as a small badge on each card |
| **Source name is eyebrow text** | "Greenville Journal (Arts)" reads as the publisher not the type of event | Consider showing event type/category (arts, music, food) as the eyebrow instead |
| **Description has RSS boilerplate** | Many cards end with "The post X appeared first on GREENVILLE JOURNAL" — ugly | Strip this in `buildCard()` with a regex before rendering |
| **Stats bar is misleading** | "With Dates: 3" next to "Total Events: 19" looks broken, not like a data quality signal | Rename to "Confirmed Date" and add a tooltip explaining the rest are article-based |
| **Free only button is almost always empty** | Currently 0 free events. Button is visible and clickable but produces nothing | Hide or disable it when count is 0 |
| **No link to the Telegram bot** | Site has no mention that there's a real-time Telegram bot version | Add a CTA: "Get live updates → Telegram" |
| **GitHub link in footer is wrong repo** | Footer still points to an old placeholder URL | ✅ Already fixed in latest push |
| **Data never refreshes** | Site data is a static snapshot — users see the same events indefinitely | GitHub Actions workflow (Step 5 above) |

### Quick wins (CSS/JS only, no backend needed)

```js
// 1. Strip RSS boilerplate from descriptions
const clean = (s) => (s || '').replace(/The post .+ appeared first on .+\./, '').trim();

// 2. Separate dated vs undated with a divider
const dated   = filtered.filter(e => e.event_date);
const undated = filtered.filter(e => !e.event_date);
// Render dated first, insert a <hr> label, then undated

// 3. Add distance badge to card HTML
`<span class="badge badge-dist">${ev.distance}</span>`
```

---

## 🔬 Feed Probe Audit — April 21, 2026

Ran `python test_feeds.py` against all 100 candidate URLs.
**Result: 47 live · 53 dead**

Score = event-keyword density across first 10 items (higher = more event content).

---

### ✅ Live Feeds — Ranked by Event Signal

| Score | Items | Region | Feed | URL |
|-------|-------|--------|------|-----|
| 0.51 | 100 | Charlotte | Charlotte on the Cheap | https://www.charlotteonthecheap.com/feed/ |
| 0.51 | 20 | Asheville | Haywood County Press | https://www.hcpress.com/feed |
| 0.49 | 30 | Charlotte | Charlotte Is Creative | https://charlotteiscreative.com/feed/ |
| 0.49 | 10 | Asheville | NC Health News | https://www.northcarolinahealthnews.org/feed/ |
| 0.46 | 100 | Triangle NC | Triangle on the Cheap | https://triangleonthecheap.com/feed/ |
| 0.46 | 50 | Charlotte | QNotes Carolinas | https://qnotescarolinas.com/feed/ |
| 0.38 | 5 | Asheville | Carolina Public Press | https://carolinapublicpress.org/feed/ |
| 0.32 | 10 | Triangle NC | INDY Week | https://indyweek.com/feed/ |
| 0.30 | 10 | Triangle NC | Walter Magazine | https://www.waltermagazine.com/feed/ |
| 0.24 | 10 | Greenville SC | Town Carolina | https://towncarolina.com/feed/ |
| 0.22 | 50 | Charlotte | Scoop Charlotte | https://scoopcharlotte.com/feed/ |
| 0.22 | 10 | Asheville | Asheville Art Museum | https://www.ashevilleart.org/feed/ |
| 0.19 | 12 | Triad | Triad City Beat Culture | https://triad-city-beat.com/category/culture/feed/ |
| 0.19 | 11 | Triad | WStoday (6AM City) | https://wstoday.6amcity.com/index.rss |
| 0.19 | 10 | Triad | Reynolda House | https://reynolda.org/feed/ |
| 0.19 | 10 | Charlotte | Queen City Nerve | https://qcnerve.com/feed/ |
| 0.16 | 10 | Triad | Triad Moms on Main | https://triadmomsonmain.com/feed/ |
| 0.16 | 10 | Charlotte | Charlotte Pride | https://charlottepride.org/feed/ |
| 0.14 | 15 | Greenville SC | Greenville Journal | https://greenvillejournal.com/feed/ |
| 0.14 | 10 | Triangle NC | Raleigh Magazine | https://raleighmag.com/feed/ |
| 0.14 | 10 | Triangle NC | Durham Magazine | https://durhammag.com/feed/ |
| 0.14 | 10 | Charlotte | SouthPark Magazine | https://southparkmagazine.com/feed/ |
| 0.14 | 10 | Asheville | The Laurel of Asheville | https://thelaurelofasheville.com/feed/ |
| 0.11 | 50 | Triad | Greensboro.com Entertainment | https://greensboro.com/search/?f=rss&t=article&c=entertainment&l=50&s=start_time&sd=desc |
| 0.11 | 11 | Greenville SC | GVLtoday (6AM City) | https://gvltoday.6amcity.com/index.rss |
| 0.11 | 11 | Greenville SC | COLAtoday (6AM City) | https://colatoday.6amcity.com/index.rss |
| 0.11 | 11 | Asheville | AVLtoday (6AM City) | https://avltoday.6amcity.com/index.rss |
| 0.11 | 10 | Charlotte | Charlotte Ballet | https://charlotteballet.org/feed/ |
| 0.08 | 11 | Charlotte | CLTtoday (6AM City) | https://clttoday.6amcity.com/index.rss |
| 0.08 | 10 | Charlotte | Unpretentious Palate | https://unpretentiouspalate.com/feed/ |
| 0.08 | 10 | Charlotte | Charlotte Magazine | https://www.charlottemagazine.com/feed/ |
| 0.08 | 10 | Asheville | Mountain Xpress | https://mountainx.com/feed/ |
| 0.08 | 10 | Asheville | Edible Asheville | https://edibleasheville.com/feed/ |
| 0.05 | 11 | Triangle NC | RALtoday (6AM City) | https://raltoday.6amcity.com/index.rss |
| 0.05 | 10 | Asheville | Watauga Democrat | https://www.wataugademocrat.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc |
| 0.05 | 10 | Triangle NC | Chapel Hill Magazine | https://chapelhillmagazine.com/feed/ |
| 0.05 | 10 | Charlotte | PFLAG Charlotte | https://pflagcharlotte.org/feed/ |
| 0.05 | 10 | Charlotte | Mint Museum | https://mintmuseum.org/feed/ |
| 0.03 | 15 | Greenville SC | Upstate Business Journal | https://upstatebusinessjournal.com/feed/ |
| 0.03 | 10 | Charlotte | Arts & Science Council | https://artsandscience.org/feed/ |
| 0.03 | 50 | Charlotte | WBTV News | https://www.wbtv.com/arc/outboundfeeds/rss/?outputType=xml |
| 0.03 | 10 | Triad | The Carolinian (UNCG) | https://carolinianuncg.com/feed/ |
| 0.03 | 20 | Triad | High Point Discovered | https://highpointdiscovered.org/feed/ |
| 0.00 | 10 | Charlotte | Business NC | https://businessnc.com/feed/ |
| 0.00 | 5 | Asheville | Ashvegas | https://ashvegas.com/feed/ |
| 0.00 | 20 | Triad | Triad Foodies | https://triadfoodies.com/feed/ |
| 0.00 | 10 | Charlotte | Charlotte Is Creative *(see above)* | — |

---

### ❌ Dead Feeds — Full Register

| Status | Region | Feed | URL |
|--------|--------|------|-----|
| TIMEOUT | Charlotte | Charlotte Observer Local | https://www.charlotteobserver.com/news/local/?service=rss |
| TIMEOUT | Charlotte | Charlotte Observer Entertainment | https://www.charlotteobserver.com/entertainment/?service=rss |
| TIMEOUT | Triangle NC | News & Observer Entertainment | https://www.newsobserver.com/entertainment/?service=rss |
| TIMEOUT | Greenville SC | The State Entertainment | https://www.thestate.com/entertainment/?service=rss |
| HTTP-404 | Charlotte | Charlotte Ledger (Substack) | https://charlotteledger.substack.com/feed |
| HTTP-404 | Charlotte | QCity Metro | https://qcitymetro.com/feed/ |
| HTTP-404 | Charlotte | WFAE Local News | https://www.wfae.org/local-news/index.rss |
| HTTP-404 | Charlotte | WFAE Arts & Culture | https://www.wfae.org/arts-culture/index.rss |
| HTTP-404 | Charlotte | WSOC-TV Local | https://www.wsoctv.com/arc/outboundfeeds/rss/category/news/local/ |
| HTTP-404 | Charlotte | NoDa Neighborhood | https://noda.org/feed/ |
| HTTP-404 | Charlotte | QC Foodie | https://qcfoodie.com/feed/ |
| HTTP-404 | Charlotte | Blumenthal Arts | https://www.blumenthalarts.org/blog/rss |
| HTTP-404 | Charlotte | McColl Center | https://mccollcenter.org/feed/ |
| HTTP-404 | Charlotte | Charlotte Black Pride | https://charlotteblackpride.org/feed/ |
| HTTP-404 | Charlotte | Charlotte Symphony | https://charlottesymphony.org/feed/ |
| HTTP-404 | Charlotte | Bechtler Museum | https://bechtler.org/feed/ |
| HTTP-404 | Charlotte | Work For Your Beer | https://www.workforyourbeer.com/feed/ |
| HTTP-404 | Charlotte | Restaurant Traffic | http://restauranttraffic.com/feed/ |
| HTTP-404 | Triad | WFDD Public Radio | https://www.wfdd.org/rss.xml |
| HTTP-404 | Triad | SECCA | https://secca.org/feed/ |
| HTTP-404 | Triangle NC | WRAL Out & About | https://www.wral.com/entertainment/out_and_about/rss/58/ |
| HTTP-404 | Triangle NC | Discover Durham | https://www.discoverdurham.com/blog/rss/ |
| HTTP-404 | Triangle NC | Triangle Arts & Ent | https://triangleartsandentertainment.org/feed/ |
| HTTP-404 | Asheville | Explore Asheville Blog | https://www.exploreasheville.com/blog/rss/ |
| HTTP-404 | Asheville | Romantic Asheville Blog | https://www.romanticasheville.com/blog/feed |
| HTTP-404 | Asheville | Asheville Downtown Assoc | https://ashevilledowntown.org/feed/ |
| HTTP-404 | Greenville SC | Edible Upcountry | https://edibleupcountry.com/feed/ |
| HTTP-404 | Greenville SC | Hub City (Spartanburg) | https://www.hubcity.org/feed |
| HTTP-404 | Greenville SC | Visit Greenville SC | https://www.visitgreenvillesc.com/blog/rss/ |
| HTTP-404 | Greenville SC | Experience Columbia SC | https://www.experiencecolumbiasc.com/blog/rss/ |
| HTTP-404 | Greenville SC | Columbia Museum of Art | https://www.columbiamuseum.org/feed |
| HTTP-403 | Charlotte | Biz Journals Charlotte | https://www.bizjournals.com/charlotte/rss |
| HTTP-403 | Asheville | Asheville Citizen-Times Ent | https://rssfeeds.citizen-times.com/asheville/entertainment |
| HTTP-403 | Greenville SC | Greenville Online | https://rssfeeds.greenvilleonline.com/greenville/home |
| HTTP-410 | Charlotte | South End CLT | https://southendclt.org/feed/ |
| HTTP-429 | Triad | Journal Now Local | https://journalnow.com/search/?f=rss&t=article&c=news/local&l=50 |
| HTTP-429 | Triad | Journal Now Entertainment | https://journalnow.com/search/?f=rss&t=article&c=entertainment&l=50 |
| HTTP-429 | Triad | Yes! Weekly | https://yesweekly.com/search/?f=rss&t=article&l=50 |
| HTTP-429 | Greenville SC | Free Times (P&C) | https://www.postandcourier.com/free-times/search/?f=rss |
| HTTP-503 | Triangle NC | Bites of Bull City | https://bitesofbullcity.com/feed/ |
| PARSE_ERR | Charlotte | Gantt Center | https://ganttcenter.org/feed/ |
| PARSE_ERR | Triad | Winston-Salem Monthly | https://www.winstonsalemmonthly.com/feed/ |
| EMPTY | Charlotte | Plaza Midwood | https://plazamidwood.org/feed/ |
| EMPTY | Charlotte | NC Beer Guys | https://ncbeerguys.com/feed/ |
| EMPTY | Charlotte | Charlotte Gaymers Network | https://www.charlottegaymersnetwork.com/feed/ |
| EMPTY | Asheville | Blue Ridge Public Radio | https://www.bpr.org/index.rss |
| EMPTY | Triangle NC | WUNC Public Radio | https://www.wunc.org/index.rss |
| EMPTY | Greenville SC | SC Public Radio | https://www.southcarolinapublicradio.org/index.rss |
| URL-ERR | Charlotte | Beer Me Charlotte | https://beermecharlotte.com/feed/ |
| URL-ERR | Charlotte | Charlotte Coffee Culture | https://charlottecoffeeculture.com/feed/ |
| URL-ERR | Triad | Piedmont Parent | https://www.piedmontparent.com/feed/ |
| URL-ERR | Greenville SC | GoUpstate (Spartanburg) | https://rssfeeds.goupstate.com/spartanburg/home |
| URL-ERR | Triangle NC | Carolina Parent | https://www.carolinaparent.com/feed/ |

---

### 🟢 Recommended New Additions to feeds.py

These are live, event-relevant, and not already in the active feed list:

| Priority | Feed | Region | Reason |
|----------|------|--------|--------|
| **High** | Charlotte on the Cheap | Charlotte | 100 items, highest event score, free/cheap focus |
| **High** | Triangle on the Cheap | Triangle NC | 100 items, same model for Triangle |
| **High** | Charlotte Is Creative | Charlotte | Arts/creative events, decent volume |
| **High** | Triad City Beat Culture | Triad | Category feed — much cleaner than main Triad City Beat |
| **High** | WStoday (6AM City) | Triad | Fills the Triad gap left by removing Triad City Beat |
| Med | Greensboro.com Entertainment | Triad | 50 items entertainment category |
| Med | Raleigh Magazine | Triangle NC | Lifestyle/events mix |
| Med | Durham Magazine | Triangle NC | Cultural events |
| Med | Town Carolina | Greenville SC | SC local events |
| Med | Reynolda House | Triad | Museum/arts events Winston-Salem |
| Med | Asheville Art Museum | Asheville | Pure arts events |
| Low | Haywood County Press | Asheville | Local Waynesville, broader WNC coverage |
| Low | The Laurel of Asheville | Asheville | Arts/culture magazine |
| Low | COLAtoday (6AM City) | Greenville SC | Columbia SC, extends SC coverage |
