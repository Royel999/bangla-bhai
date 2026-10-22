#!/bin/bash
# Call after any change to ~/.secrets or Bangla Bhai service info.
# Publishes a hybrid-encrypted feed for Royal Vault (no plaintext leaves the box).
set -e
cd "$(dirname "$0")/.."
export PATH="$PWD/venv/bin:$PATH"
# load edge secret for persist
[ -f "$HOME/.secrets/bangla_bhai.env" ] && set -a && . "$HOME/.secrets/bangla_bhai.env" && set +a
python vault_tools/vault_sync.py feed >> /tmp/vault_sync.log 2>&1 || true
python vault_tools/vault_sync.py notebook >> /tmp/vault_sync.log 2>&1 || true
