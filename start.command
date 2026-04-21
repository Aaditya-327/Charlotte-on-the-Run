#!/bin/bash
cd "$(dirname "$0")"

echo "=== Charlotte On The Run Bot ==="

if pgrep -f "bot.py" > /dev/null; then
  echo "Bot is already running (PID: $(pgrep -f 'bot.py' | head -1)). Stop it first."
  exit 1
fi

if [ ! -f "feeds_live.json" ]; then
  echo "Generating feeds_live.json..."
  .venv/bin/python3 validate_feeds.py --write-only
fi

echo "Starting bot..."
.venv/bin/python3 bot.py
