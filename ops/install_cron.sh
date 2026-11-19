#!/usr/bin/env bash
# Install (or with --remove, delete) the one crontab line that runs the publisher every 15 minutes.
# Any older crontab line that mentions reels-shorts is removed first.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$HOME/.local/state/reels-shorts"
mkdir -p "$STATE"
PY="$(command -v python3.11)"
LINE="*/15 * * * * cd $REPO && $PY ops/scheduler.py --publish >> $STATE/scheduler.log 2>&1  # reels-shorts"
CURRENT="$(crontab -l 2>/dev/null | grep -v 'reels-shorts' || true)"
if [ "${1:-}" = "--remove" ]; then
  printf '%s\n' "$CURRENT" | sed '/^$/d' | crontab -
  echo "removed reels-shorts cron line"
else
  { printf '%s\n' "$CURRENT"; echo "$LINE"; } | sed '/^$/d' | crontab -
  echo "installed: $LINE"
fi
