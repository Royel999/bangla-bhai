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
  sleep 60
done
