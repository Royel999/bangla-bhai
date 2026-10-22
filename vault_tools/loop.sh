#!/bin/bash
# Background: every 30 min rebuild + publish vault feed (ciphertext only).
cd "$(dirname "$0")/.."
[ -f "$HOME/.secrets/bangla_bhai.env" ] && set -a && . "$HOME/.secrets/bangla_bhai.env" && set +a
while true; do
  ./venv/bin/python vault_tools/vault_sync.py feed >> /tmp/vault_sync.log 2>&1 || true
  # also honour "want sync" flag set by phone after register
  WANT=$(./venv/bin/python -c "import persist;b=persist.req('GET','vault_want_sync');print(b.decode() if b and b!=b'-' else '')" 2>/dev/null || true)
  if [ -n "$WANT" ]; then
    ./venv/bin/python vault_tools/vault_sync.py feed >> /tmp/vault_sync.log 2>&1 || true
    ./venv/bin/python -c "import persist;persist.req('PUT','vault_want_sync',b'-')" 2>/dev/null || true
  fi
  sleep 1800
done
