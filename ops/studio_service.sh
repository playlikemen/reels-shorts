#!/usr/bin/env bash
# Reels Studio service: the web app (uvicorn on 127.0.0.1:4820) and, when ~/.cloudflared/reels-studio.yml exists,
# its own Cloudflare tunnel. Other cloudflared processes (other tunnels) are never touched.
#
#   bash ops/studio_service.sh start      # start whatever is not running (prints the first password on first start)
#   bash ops/studio_service.sh stop       # stop the web app and the studio tunnel
#   bash ops/studio_service.sh restart
#   bash ops/studio_service.sh status
#   bash ops/studio_service.sh logs       # last lines of both logs
#   bash ops/studio_service.sh watchdog   # quiet start, for cron
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$HOME/.local/state/reels-shorts"
PY="$(command -v python3.11)"
CLOUDFLARED="${CLOUDFLARED:-$(command -v cloudflared || echo "$HOME/.local/bin/cloudflared")}"
TUNNEL_CFG="$HOME/.cloudflared/reels-studio.yml"
WEB_PID="$STATE/studio.pid"; WEB_LOG="$STATE/studio.log"
TUN_PID="$STATE/studio-tunnel.pid"; TUN_LOG="$STATE/studio-tunnel.log"
PORT="${STUDIO_PORT:-4820}"
mkdir -p "$STATE"

cmd_of() { [ -r "/proc/$1/cmdline" ] && tr '\0' ' ' < "/proc/$1/cmdline"; }
web_pid() {
  local p; p="$(cat "$WEB_PID" 2>/dev/null)"
  [ -n "$p" ] && cmd_of "$p" | grep -q -- "-m studio" && { echo "$p"; return 0; }
  return 1
}
tun_pid() {
  local p; p="$(cat "$TUN_PID" 2>/dev/null)"
  [ -n "$p" ] && cmd_of "$p" | grep -q "reels-studio.yml" && { echo "$p"; return 0; }
  # adopt a studio tunnel started by hand
  p="$(pgrep -f "cloudflared.*reels-studio.yml" | head -1)"
  [ -n "$p" ] && { echo "$p" > "$TUN_PID"; echo "$p"; return 0; }
  return 1
}
healthy() { curl -fsS -m 3 "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1; }

start_web() {
  if p="$(web_pid)"; then [ "${QUIET:-}" ] || echo "web: running (pid $p)"; return 0; fi
  cd "$REPO" || exit 1
  # first start: create the password here so it is printed to this terminal, not into the log
  "$PY" -c "from studio import auth; auth.ensure()" || exit 1
  setsid nohup "$PY" -m studio >> "$WEB_LOG" 2>&1 < /dev/null &
  echo $! > "$WEB_PID"
  for _ in $(seq 1 30); do healthy && break; sleep 0.5; done
  if healthy; then echo "web: started (pid $(cat "$WEB_PID")) on http://127.0.0.1:$PORT"; else echo "web: did not come up; see $WEB_LOG" >&2; return 1; fi
}

start_tunnel() {
  if [ ! -f "$TUNNEL_CFG" ]; then [ "${QUIET:-}" ] || echo "tunnel: no $TUNNEL_CFG, skipped"; return 0; fi
  if p="$(tun_pid)"; then [ "${QUIET:-}" ] || echo "tunnel: running (pid $p)"; return 0; fi
  if [ ! -x "$CLOUDFLARED" ]; then echo "tunnel: cloudflared not found" >&2; return 1; fi
  setsid nohup "$CLOUDFLARED" tunnel --no-autoupdate --config "$TUNNEL_CFG" run >> "$TUN_LOG" 2>&1 < /dev/null &
  echo $! > "$TUN_PID"
  echo "tunnel: started (pid $(cat "$TUN_PID")) for $(grep -m1 hostname "$TUNNEL_CFG" | awk '{print $NF}')"
}

stop_one() {  # name pid-function pid-file
  local p
  if p="$($2)"; then
    kill "$p" 2>/dev/null
    for _ in $(seq 1 20); do kill -0 "$p" 2>/dev/null || break; sleep 0.25; done
    kill -9 "$p" 2>/dev/null
    echo "$1: stopped"
  else
    echo "$1: not running"
  fi
  rm -f "$3"
}

case "${1:-status}" in
  start) start_web; start_tunnel ;;
  stop) stop_one web web_pid "$WEB_PID"; stop_one tunnel tun_pid "$TUN_PID" ;;
  restart) stop_one web web_pid "$WEB_PID"; start_web; start_tunnel ;;
  watchdog)
    QUIET=1
    if web_pid >/dev/null && ! healthy; then echo "$(date -Is) web not answering; restarting"; stop_one web web_pid "$WEB_PID"; fi
    web_pid >/dev/null || { echo "$(date -Is) starting web"; start_web; }
    if [ -f "$TUNNEL_CFG" ] && ! tun_pid >/dev/null; then echo "$(date -Is) starting tunnel"; start_tunnel; fi ;;
  status)
    if p="$(web_pid)"; then echo "web: running (pid $p)$(healthy && echo ', healthy' || echo ', NOT answering')"; else echo "web: stopped"; fi
    if [ -f "$TUNNEL_CFG" ]; then
      if p="$(tun_pid)"; then echo "tunnel: running (pid $p)"; else echo "tunnel: stopped"; fi
    else echo "tunnel: not configured ($TUNNEL_CFG missing)"; fi ;;
  logs) echo "== $WEB_LOG"; tail -n 60 "$WEB_LOG" 2>/dev/null; echo "== $TUN_LOG"; tail -n 30 "$TUN_LOG" 2>/dev/null ;;
  *) echo "usage: $0 start|stop|restart|status|logs|watchdog" >&2; exit 2 ;;
esac
