#!/usr/bin/env bash
# Install (or with --remove, delete) the crontab lines of this repo:
#   - the publisher, every 15 minutes
#   - Reels Studio: watchdog for the web app + its tunnel (every 15 minutes and at boot), Sheet -> local sync every
#     5 minutes, and a nightly snapshot of every tab (03:15)
# Any older crontab line that mentions reels-shorts is removed first.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$HOME/.local/state/reels-shorts"
mkdir -p "$STATE"
PY="$(command -v python3.11)"
LINES=(
  "*/15 * * * * cd $REPO && $PY ops/scheduler.py --publish >> $STATE/scheduler.log 2>&1  # reels-shorts"
  "*/15 * * * * bash $REPO/ops/studio_service.sh watchdog >> $STATE/studio-watchdog.log 2>&1  # reels-shorts studio"
  "@reboot sleep 60 && bash $REPO/ops/studio_service.sh watchdog >> $STATE/studio-watchdog.log 2>&1  # reels-shorts studio"
  "*/5 * * * * cd $REPO && flock -n $STATE/studio-sync.lock sh -c '$PY -m studio.publish_job --reconcile; $PY -m studio.files sweep; $PY -m studio.sync push' >> $STATE/studio-sync.log 2>&1  # reels-shorts studio"
  "15 3 * * * cd $REPO && flock $STATE/studio-sync.lock sh -c '$PY -m studio.sync push >/dev/null 2>&1; $PY -m studio.sync snapshot' >> $STATE/studio-sync.log 2>&1  # reels-shorts studio"
)
CURRENT="$(crontab -l 2>/dev/null | grep -v 'reels-shorts' || true)"
if [ "${1:-}" = "--remove" ]; then
  printf '%s\n' "$CURRENT" | sed '/^$/d' | crontab -
  echo "removed reels-shorts cron lines"
else
  { printf '%s\n' "$CURRENT"; printf '%s\n' "${LINES[@]}"; } | sed '/^$/d' | crontab -
  printf 'installed: %s\n' "${LINES[@]}"
fi
