# Current Implementation Problems & Investigation

## Problem: Discrepancy in Event Counts
The dashboard is currently reporting **"24 events · 15 AI"** in the results count, even when "All" filters are selected, despite the total event pool being around 105 (24 RSS + 81 AI).

### 1. Old Logic Persisting (The "15 AI" Clue)
The number **15** is highly significant. In the previous architecture:
- `mixAI` (Today's Free Tier) = 8 cards
- `mixWild` (Today's Wildcard Tier) = 7 cards
- **Total = 15 cards**

The fact that you are seeing exactly **15 AI** and the text **"AI"** (which I changed to "suggestions" in the latest code) suggests that your browser or the served site is still running the **old version of index.html**.

**Potential Causes:**
- **Deployment Lag:** If you are viewing the live GitHub Pages site, it can take 1-3 minutes for the `git push` to trigger the build and update the CDN.
- **Browser Cache:** Your browser may have cached the previous `index.html`.
- **Local Server:** If you are using a local preview (like VS Code Live Server), it may not have refreshed.

### 2. Missing Category Data
The `AI_CARDS` generation in `daily_guide.py` is currently not populating the `category` field in the JSON output (it has `tags` but no `category`).
- **Impact:** The `catOK()` filter in `index.html` defaults to `true` when empty, so it isn't "filtering" them out, but it means the category filter chips on the UI will be empty or non-functional for AI cards.

### 3. All Mode Interleaving Logic
The `All` mode was designed to "interleave" AI cards into the RSS feed. 
- **The Problem:** By default, "All" mode is often more restrictive than "AI Guide" mode because it tries to keep the feed balanced. 
- **The Solution:** I have refactored `index.html` to show **all tiers** in the "All" mode, but if the code isn't refreshing, you won't see the change.

## Action Plan
1. **Hard Refresh:** Press `Cmd + Shift + R` (Mac) or `Ctrl + F5` (Windows) to force the browser to bypass the cache.
2. **Verify Local File:** Open `docs/index.html` and search for the string `suggestions`. If you find `aiCount + " suggestions"`, the file on disk is correct. If you find `aiCount + " AI"`, the file did not save correctly.
3. **Check GitHub Action:** If using GitHub Pages, check the "Actions" tab in your repo to ensure the deployment finished.
