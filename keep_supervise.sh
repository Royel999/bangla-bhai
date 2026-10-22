#!/bin/bash
# Meta-watch: if bangla_bhai/supervise.sh dies, restart it. Also run box_ai_watchdog.
LOG=/tmp/bb_keep.log
BB="$HOME/bangla_bhai"
# Royal Vault sync loop (ciphertext feed only)
if ! pgrep -f "vault_tools/loop.sh" >/dev/null; then
  nohup "$BB/vault_tools/loop.sh" >/tmp/vault_loop.log 2>&1 &
fi
while true; do
  pgrep -f 'bangla_bhai/supervise.sh' >/dev/null || {
    echo "$(date -Is) restarting supervise" >> "$LOG"
    nohup setsid "$BB/supervise.sh" >/dev/null 2>&1 &
  }
  bash "$HOME/box_ai_watchdog.sh" >/dev/null 2>&1 || true
  [ $(( $(date +%-M) % 5 )) -eq 0 ] && curl -s -m60 -o /dev/null https://bangla-bhai-q0x5.onrender.com/bb/health &
  # phone just registered → publish feed now
  WANT=$("$BB/venv/bin/python" -c "import sys;sys.path.insert(0,'$BB');import persist;b=persist.req('GET','vault_want_sync');print(b.decode() if b and b!=b'-' else '')" 2>/dev/null || true)
  if [ -n "$WANT" ]; then
    "$BB/vault_tools/hook.sh"
    "$BB/venv/bin/python" -c "import sys;sys.path.insert(0,'$BB');import persist;persist.req('PUT','vault_want_sync',b'-')" 2>/dev/null || true
  fi
  sleep 60
done
