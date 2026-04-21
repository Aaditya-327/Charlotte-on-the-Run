#!/bin/bash
# run.sh — One-shot setup and launch script
# Run this once on your machine to get everything going.

set -e
cd "$(dirname "$0")"

echo "=== Installing dependencies ==="
pip install -r requirements.txt

echo ""
echo "=== Validating RSS feeds ==="
echo "This checks which feeds are live and scores their event quality."
python3 validate_feeds.py

echo ""
echo "=== Starting bot ==="
echo "Send /help to @CLT_events_bot on Telegram to verify it's running."
echo "Send /refresh to do the first fetch."
echo ""
python3 bot.py
