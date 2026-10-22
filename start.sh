#!/bin/bash
cd ~/bangla_bhai && exec ./venv/bin/uvicorn app:app --host 127.0.0.1 --port 8090 --proxy-headers
