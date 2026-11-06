#!/usr/bin/env bash
# Sakala Mitra on Render. SAKALA_URL points at the POC service; GEMINI_API_KEY comes from Render's environment.
set -e
cd "$(dirname "$0")"
mkdir -p data
exec python -m uvicorn server.main:app --host 0.0.0.0 --port "${PORT:-8030}"
