#!/bin/bash
SP="/c/Users/hp/AppData/Local/Temp/claude/d--Sakala-POC/5a14e85d-b0dc-4b15-b24d-03ede69632a9/scratchpad"
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
URL="file:///C:/Users/hp/AppData/Local/Temp/claude/d--Sakala-POC/5a14e85d-b0dc-4b15-b24d-03ede69632a9/scratchpad/wfdebug/index.html"
for qs in "$@"; do
  out=$("$EDGE" --headless=new --disable-gpu --no-first-run --user-data-dir="$SP/edgeprof" --virtual-time-budget=40000 --dump-dom "$URL?$qs" 2>/dev/null)
  echo "== $qs"
  echo "$out" | grep -o 'data-err="[^"]*"\|data-err2="[^"]*"\|data-ferr="[^"]*"\|data-views="[^"]*"\|data-ans="[^"]*"\|data-drawer="[^"]*"' 
  echo "$out" | grep -o "data-res=\"[^\"]*\"" | sed 's/&quot;/"/g'
done
