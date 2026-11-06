#!/bin/bash
SP="/c/Users/hp/AppData/Local/Temp/claude/d--Sakala-POC/5a14e85d-b0dc-4b15-b24d-03ede69632a9/scratchpad"
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
for qs in "$@"; do
  curl -s -X POST http://localhost:8020/api/reset >/dev/null
  out=$("$EDGE" --headless=new --disable-gpu --no-first-run --user-data-dir="$SP/edgeprof2" --virtual-time-budget=90000 --dump-dom "http://localhost:8020/dbg?$qs" 2>/dev/null)
  echo "== $qs"
  echo "$out" | grep -o 'data-err="[^"]*"\|data-ferr="[^"]*"'
  echo "$out" | grep -o "data-res=\"[^\"]*\"" | sed 's/&quot;/"/g'
done
