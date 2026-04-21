#!/bin/bash
cd "$(dirname "$0")"

echo "=== Stopping Charlotte On The Run Bot ==="

PIDS=$(pgrep -f "bot.py")

if [ -z "$PIDS" ]; then
  echo "No bot processes found."
  exit 0
fi

echo "Killing PIDs: $PIDS"
echo "$PIDS" | xargs kill

sleep 1

if pgrep -f "bot.py" > /dev/null; then
  echo "Force-killing remaining processes..."
  pgrep -f "bot.py" | xargs kill -9
fi

echo "Bot stopped."
