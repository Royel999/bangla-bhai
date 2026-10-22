#!/bin/bash
# Meta-watch: if bangla_bhai/supervise.sh dies, restart it. Also run box_ai_watchdog.
LOG=/tmp/bb_keep.log
while true; do
  pgrep -f 'bangla_bhai/supervise.sh' >/dev/null || {
    echo "$(date -Is) restarting supervise" >> "$LOG"
    nohup setsid "$HOME/bangla_bhai/supervise.sh" >/dev/null 2>&1 &
  }
  # also poke classic watchdog for openwebui/n8n
  bash "$HOME/box_ai_watchdog.sh" >/dev/null 2>&1 || true
  # interim Render keep-awake pinger (until CF cron / GH Actions are enabled)
  [ $(( $(date +%-M) % 5 )) -eq 0 ] && curl -s -m60 -o /dev/null https://bangla-bhai-q0x5.onrender.com/bb/health &
  sleep 60
done
