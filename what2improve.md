# Charlotte On The Run — What to Improve

> Last audit: April 21, 2026 · 56 events live across 5 regions

---

## 📡 RSS Feeds in Use (20 feeds, 5 regions)

| Feed | Region | Drive | Priority | Event Ratio | Avg Score | Issues |
|------|--------|-------|----------|-------------|-----------|--------|
| Scoop Charlotte | Charlotte | 0 min | 1 | 56% | 2.4 | Home tours, real estate, lifestyle slip through |
| Queen City Nerve | Charlotte | 0 min | 1 | 50% | 2.3 | Cannabis policy, zoning meetings, news items |
| Charlotte Ballet | Charlotte | 0 min | 1 | 40% | 1.2 | Very low volume (4 event items) |
| SouthPark Magazine | Charlotte | 0 min | 1 | 40% | 1.5 | Party pics, renovation stories, brunch roundups |
| Charlotte Pride | Charlotte | 0 min | 1 | 40% | 2.0 | Stale items (2022–2024 articles resurfacing) |
| Arts & Science Council | Charlotte | 0 min | 1 | 50% | 1.5 | **Job postings appearing as events** |
| Charlotte Parent | Charlotte | 0 min | 2 | 80% | 3.4 | Travel articles, parenting advice slip through |
| CLTtoday (6AM City) | Charlotte | 0 min | 2 | 27% | 0.82 | Gift ads, sponsored content |
| QNotes Carolinas | Charlotte | 0 min | 2 | 32% | 0.64 | Political/policy articles dominate |
| Mint Museum | Charlotte | 0 min | 2 | 20% | 0.90 | Very low signal, rarely posts events |
| Unpretentious Palate | Charlotte | 0 min | 2 | 30% | 0.60 | Food profiles, Q&As, not events |
| Charlotte Magazine | Charlotte | 0 min | 3 | **0%** | -0.2 | **Zero event items — consider dropping** |
| Triad City Beat | Triad | 1h | 2 | 42% | 1.42 | **Spam: casino ads, workers comp attorney posts** |
| Greenville Journal (Events) | Greenville SC | 1h 30m | 1 | 53% | 1.73 | Clean feed, good signal |
| Greenville Journal (Arts) | Greenville SC | 1h 30m | 2 | **80%** | **6.07** | ✅ Best feed — highest quality |
| GVLtoday (6AM City) | Greenville SC | 1h 30m | 2 | 36% | 1.09 | Duplicate titles, gift ads |
| Mountain Xpress | Asheville | 2h | 2 | 19% | 0.71 | Low event ratio, opinion/news heavy |
| Walter Magazine | Triangle NC | 2h 30m | 1 | 80% | 3.40 | ✅ High quality — roundup style |
| INDY Week | Triangle NC | 2h 30m | 2 | 30% | 0.10 | Film/doc interviews, policy, not events |
| RALtoday (6AM City) | Triangle NC | 2h 30m | 2 | 36% | 0.91 | Real estate "Mansion Monday", duplicates |

---

## 🔴 Current Issues

### 1. Precision — Irrelevant articles dominate
**53 of 56 items (95%) have "Date TBD"** — only 3 have confirmed dates. Junk getting through:
- Job postings (Arts & Science Council: Director of Marketing, Marketing Coordinator)
- Real estate (Scoop Charlotte home tours, RALtoday Mansion Monday)
- Policy/politics (NC Cannabis Report, Trump admin flag story, affordable housing bond)
- Sponsored content / ads (Tinggly gift box, social casino article)
- Attorney directory spam (Triad City Beat: workers comp attorneys in Illinois/Chicago)
- Restaurant profiles and food Q&As
- Travel articles (Charlotte Parent: Princess Grand Jamaica)

### 2. Date extraction near zero
- Only **3/56 events** have extracted dates (all from Greenville Journal Arts)
- spaCy NER is installed but `date_confidence=0` for all pre-migration DB rows
- Dates in article body text (e.g. "July Fourth", "May 2026 events") are being missed
- Relative-term fallback ("this weekend", "tonight") not triggering on current items

### 3. Stale / duplicate content
- Charlotte Pride feed has 2022–2024 articles still circulating
- GVLtoday and RALtoday have exact duplicate titles within their own feeds
- CLTtoday Tinggly gift box ad appears across **3 different regional feeds**

### 4. Triad City Beat — geographic spam
Articles about Chicago and Illinois workers comp attorneys have nothing to do with Greensboro/Winston-Salem. The feed appears infiltrated by paid content.

### 5. Arts & Science Council — job board, not events
All visible ASC items are job postings. The one real event captured ("Return of Midnight Marathon") was not in this cycle.

### 6. Charlotte Magazine — zero events
event_ratio = 0.0, avg_score = -0.2. Actively dragging precision down. Should be removed or replaced.

### 7. Static site data is frozen
`docs/events_data.js` is a one-time manual export. The "Updated Apr 20" timestamp will grow stale. No auto-refresh is wired up yet.

---

## 🟡 Improvements — Prioritized

### 🔥 High Priority

#### A. GitHub Actions: auto-refresh events_data.js daily
```yaml
# .github/workflows/update_site.yml
on:
  schedule:
    - cron: '0 13 * * *'   # 9 AM ET daily
jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: python fetcher.py
      - run: python export_site_data.py   # writes docs/events_data.js
      - run: git add docs/events_data.js && git commit -m "auto: refresh events" && git push
```

#### B. Raise EVENT_SCORE_MIN: 1 → 3
Current threshold of 1 is far too permissive:
- Score ≥ 3 → genuine events (concerts, festivals, fundraisers)
- Score 1–2 → borderline editorial, profiles, policy
- Score ≤ 0 → clear non-events

Change in `.env`: `EVENT_SCORE_MIN=3`  
Estimated impact: ~60–70% reduction in noise.

#### C. Add a title blocklist in fetcher.py
```python
TITLE_BLOCKLIST = [
    "workers compensation", "mortgage", "non-agency loan",
    "virtual currency", "social casino", "gift ideas", "tinggly",
    "mansion monday", "home tour", "renovation", "real estate",
    "job description", "hiring", "part-time", "executive director",
    "attorney", "lawsuit", "legal", "budget targets",
]
```
Drop items whose lowercased title matches any term before scoring.

#### D. Drop / replace low-signal feeds
| Action | Feed | Reason |
|--------|------|--------|
| ❌ Remove | Charlotte Magazine | 0% event ratio, negative score |
| ❌ Remove | Mint Museum | 20% ratio, extremely low volume |
| ⚠️ Probation | INDY Week | Avg score 0.10 — nearly all noise |
| ⚠️ Probation | Triad City Beat | Spam / paid content infiltration |
| ➕ Add | Blumenthal Performing Arts RSS | Pure event calendar, Charlotte |
| ➕ Add | Creative Loafing Charlotte | High event density |
| ➕ Add | Visit Charlotte events feed | Official tourism calendar |

---

### 🟠 Medium Priority

#### E. Backfill date_confidence for existing DB rows
All 56 current rows have `date_confidence=0` (pre-migration). Run a one-off script:
```python
# backfill_dates.py
from fetcher import get_db
from utils.date_extractor import extract_event_datetime
db = get_db()
rows = db.execute("SELECT sig, title, description FROM events WHERE date_confidence=0").fetchall()
for r in rows:
    d, t, conf = extract_event_datetime(r['title'], r['description'] or '')
    if d or t:
        db.execute("UPDATE events SET event_date=?, event_time=?, date_confidence=? WHERE sig=?",
                   (d, t, conf, r['sig']))
db.commit()
```

#### F. Separate dated vs undated events visually on the site
Add a divider between events with confirmed dates and "Date TBD" items. Makes the page scannable.

#### G. Surface `distance` on event cards
Show drive time (e.g. "1h 30m") as a subtle badge alongside the region chip so users can gauge effort instantly.

#### H. Add category filter chips (arts, food, family, lgbtq…)
The feeds already carry `tags`. Surface them as a third row of filter chips on the static site.

---

### 🔵 Low Priority / Future

#### I. Optional LLM re-ranking
If `GEMINI_API_KEY` is set, classify top 100 items as `event | editorial | spam` via a cheap prompt. Cache result in a new `is_event` column. ~$0.01/day.

#### J. Bot `/flag` owner feedback loop
Owner flags a bad DB entry → that source gets a score penalty. Feeds self-healing blocklist over time.

#### K. Site pagination / virtual scroll
56 events is fine now, but the page will slow down above ~300 cards. Add simple pagination (Next/Prev buttons, 20 per page).

---

## 📊 Summary Scorecard

| Metric | Now | Goal |
|--------|-----|------|
| Events in DB | 56 | 100–200 |
| Events with confirmed date | 3 (5%) | >50% |
| Est. precision (genuine events) | ~35% | >80% |
| Auto data refresh | ❌ Manual | ✅ Daily GHA |
| Spam / off-topic rate | High | Minimal |
| Best performing feed | Greenville Journal Arts (80%, score 6.07) | — |
| Worst performing feed | Charlotte Magazine (0%, score -0.2) | Remove |
