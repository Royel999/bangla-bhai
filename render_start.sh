#!/bin/bash
# Render entrypoint: materialise secrets, restore data, run app + backup loop.
set -u
mkdir -p ~/.secrets && chmod 700 ~/.secrets
if [ -n "${BB_SECRETS_B64:-}" ]; then echo "$BB_SECRETS_B64" | base64 -d | tar -xz -C ~/.secrets && chmod 600 ~/.secrets/*; fi
unset BB_SECRETS_B64
cd ~/bangla_bhai
mkdir -p media_store sandbox
python persist.py restore || { echo "restore failed - refusing to start with empty DB"; sleep 60; exit 1; }
python persist.py loop &
LOOP=$!
uvicorn app:app --host 0.0.0.0 --port "${PORT:-10000}" --proxy-headers --forwarded-allow-ips='*' &
APP=$!
trap 'kill -TERM $APP; wait $APP; kill $LOOP; python persist.py push; exit 0' TERM INT
wait $APP
python persist.py push
