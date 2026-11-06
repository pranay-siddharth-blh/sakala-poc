#!/usr/bin/env bash
# Sakala POC on Render. The demo database starts from the pristine snapshot (go-live state) when there is none yet.
set -e
cd "$(dirname "$0")"
if [ ! -f data/sakala.db ]; then cp data/sakala_pristine.db data/sakala.db; fi
exec python -m uvicorn server.api:app --host 0.0.0.0 --port "${PORT:-8020}"
