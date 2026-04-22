#!/usr/bin/env bash
# Charlotte On The Run — daily pipeline
# Double-click to run manually, or triggered at 7:00 AM by launchd.
#
# Step 1: enrich_cotc.py   — fetch COTC RSS → Gemini extraction → events.db
# Step 2: daily_guide.py   — AI guide cards + export events_data.js + git push
#
# Outputs (isolated, then merged by daily_guide.py into a single git push):
#   docs/daily_guide_data.js   ← AI prompt responses
#   docs/events_data.js        ← RSS/Gemini enriched events from DB

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv/bin/python3"

mkdir -p "$DIR/logs"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Charlotte On The Run  ·  $(date '+%a %b %d %H:%M %Z')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "▸ [1/2]  COTC RSS  →  events.db"
echo "─────────────────────────────────────────────────────"
"$VENV" "$DIR/enrich_cotc.py"

echo ""
echo "▸ [2/2]  AI daily guide  →  daily_guide_data.js + events_data.js"
echo "─────────────────────────────────────────────────────"
"$VENV" "$DIR/daily_guide.py"

echo ""
echo "━━━ Done ━━━"
