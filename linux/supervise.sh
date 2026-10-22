#!/bin/bash
# Persistent supervisor: bangla_bhai (:8090) + ngrok static free domain
set -u
DOMAIN_HOST="pueblo-onshore-undesired.ngrok-free.dev"
NGROK="$HOME/bin/ngrok"
APPDIR="$HOME/bangla_bhai"
LOG=/tmp/bb_supervise.log
HEALTH_URL="http://127.0.0.1:8090/bb/health"
NGROK_API="http://127.0.0.1:4040/api/tunnels"

log(){ echo "$(date '+%Y-%m-%d %H:%M:%S %Z') $*" >> "$LOG"; }

start_app(){
  if curl -fsS -m5 "$HEALTH_URL" >/dev/null 2>&1; then return 0; fi
  log "starting bangla_bhai uvicorn :8090"
  pkill -f 'uvicorn app:app --host 127.0.0.1 --port 8090' 2>/dev/null || true
  sleep 0.5
  (cd "$APPDIR" && nohup setsid ./venv/bin/uvicorn app:app --host 127.0.0.1 --port 8090 --proxy-headers >> /tmp/banglabhai.log 2>&1 9>&- &)
  for i in $(seq 1 15); do
    curl -fsS -m3 "$HEALTH_URL" >/dev/null 2>&1 && { log "app healthy"; return 0; }
    sleep 1
  done
  log "WARN app not healthy yet"
}

ngrok_ok(){
  curl -fsS -m3 "$NGROK_API" 2>/dev/null | grep -q "$DOMAIN_HOST"
}

start_ngrok(){
  if ngrok_ok; then return 0; fi
  log "starting ngrok (config-pinned $DOMAIN_HOST)"
  pkill -f 'ngrok start webui' 2>/dev/null || true
  pkill -x ngrok 2>/dev/null || true
  sleep 1
  # url is pinned in ~/.config/ngrok/ngrok.yml — do not pass --url (invalid with `start`)
  nohup setsid "$NGROK" start webui --log /tmp/ngrok.log >> /tmp/ngrok_supervise.log 2>&1 9>&- &
  for i in $(seq 1 20); do
    if ngrok_ok; then log "ngrok up: https://$DOMAIN_HOST"; return 0; fi
    sleep 1
  done
  log "WARN ngrok not advertising expected domain yet"
  # dump last errors
  tail -5 /tmp/ngrok_supervise.log >> "$LOG" 2>/dev/null || true
}

CF="$HOME/.local/bin/cloudflared"
cf_ok(){ pgrep -f 'cloudflared .*tunnel .*run banglabhai' >/dev/null; }
start_cf(){
  if cf_ok; then return 0; fi
  log "starting cloudflared tunnel banglabhai -> https://banglabhai.dpdns.org"
  nohup setsid "$CF" --no-autoupdate tunnel --config "$HOME/.cloudflared/config.yml" run banglabhai >> /tmp/cloudflared.log 2>&1 9>&- &
  sleep 3
}

PUB_URL="https://$DOMAIN_HOST/"
FAILS=0
public_check(){
  local out code
  out=$(curl -s -m10 -H 'ngrok-skip-browser-warning: 1' -w '\n%{http_code}' "$PUB_URL" 2>/dev/null)
  code=$(printf '%s' "$out" | tail -1)
  if [[ "$code" =~ ^[23] ]] && ! printf '%s' "$out" | grep -q 'ERR_NGROK'; then FAILS=0; return 0; fi
  FAILS=$((FAILS+1)); log "public check failed ($FAILS) code=$code"
  if [ "$FAILS" -ge 2 ]; then log "killing stuck ngrok"; pkill -x ngrok 2>/dev/null; FAILS=0; sleep 2; start_ngrok; fi
}

LOCK=/tmp/bb_supervise_v2.lock
exec 9>"$LOCK"
if command -v flock >/dev/null 2>&1; then
  if ! flock -n 9; then echo "supervise already running"; exit 0; fi
else
  # fallback pidfile
  if [ -f /tmp/bb_supervise.pid ] && kill -0 "$(cat /tmp/bb_supervise.pid)" 2>/dev/null; then
    echo "supervise already running"; exit 0
  fi
  echo $$ > /tmp/bb_supervise.pid
fi

log "supervise started pid=$$"
start_app
start_ngrok
# start_cf  (disabled: TCP 7844 blocked; Worker proxy used)
while true; do
  start_app
  start_ngrok
  # start_cf
  public_check
  sleep 30
done
