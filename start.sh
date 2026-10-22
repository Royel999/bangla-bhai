#!/bin/bash
# Linux/Mac start
cd "$(dirname "$0")" && exec ./venv/bin/uvicorn app:app --host 127.0.0.1 --port 8090 --proxy-headers
