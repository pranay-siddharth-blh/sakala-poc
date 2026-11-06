#!/usr/bin/env bash
# (Re)start Mitra for development: main instance 8030 (real Gemini Live), test instances 8031 (fake Live on 8099) and
# 8032 (failing fake on 8098). Stop them first from PowerShell (match server.main:app / fake_live.py).
# Usage: bash tests/restart_mitra.sh [main|test|all]   (default all)
cd "$(dirname "$0")/.." || exit 1
LOG="${TMP:-/tmp}"
what="${1:-all}"
if [ "$what" = all ] || [ "$what" = test ]; then
  (PYTHONIOENCODING=utf-8 nohup python tests/fake_live.py 8099 > "$LOG/fake_live.log" 2>&1 &)
  (PYTHONIOENCODING=utf-8 nohup python tests/fake_live.py 8098 --fail > "$LOG/fake_fail.log" 2>&1 &)
  (MITRA_DEBUG=1 MITRA_NO_SYNC=1 MITRA_LIVE_URL=ws://127.0.0.1:8099 PYTHONIOENCODING=utf-8 nohup python -m uvicorn server.main:app --port 8031 > "$LOG/mitra8031.log" 2>&1 &)
  (MITRA_DEBUG=1 MITRA_NO_SYNC=1 MITRA_LIVE_URL=ws://127.0.0.1:8098 PYTHONIOENCODING=utf-8 nohup python -m uvicorn server.main:app --port 8032 > "$LOG/mitra8032.log" 2>&1 &)
fi
if [ "$what" = all ] || [ "$what" = main ]; then
  (PYTHONIOENCODING=utf-8 nohup python -m uvicorn server.main:app --port 8030 > "$LOG/mitra.out.log" 2>&1 &)
fi
sleep 9
for p in 8030 8031 8032; do printf "%s %s\n" "$p" "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:$p/api/health)"; done
