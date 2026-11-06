"""The question bank on the real Gemini Live model: a sample of paraphrases per group (default 2), each in its own short
session; the same checks as run_bank.py, applied to what Mitra SAID (spoken numbers converted to digits) and to the UI the
functions sent. Run from mitra/: python tests/live_bank.py [base] [--per 2] [--profile cs]"""
import argparse
import asyncio
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import question_bank as QB  # noqa: E402
from server import guard  # noqa: E402
import websockets  # noqa: E402
import urllib.request  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("base", nargs="?", default="http://localhost:8030")
ap.add_argument("--per", type=int, default=2)
ap.add_argument("--profile", default="")
ap.add_argument("--only", default="")
A = ap.parse_args()
W = A.base.replace("http", "ws")


def post(p, d):
    r = urllib.request.Request(A.base + p, json.dumps(d).encode(), {"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


SKIP = {"cs-views", "off-switch", "cit-chitchat", "cs-injection"}          # covered by their own live tests (screens change / reconnect)


async def ask(item):
    sid = post("/api/session", {"profile": item["profile"], "officer": item["officer"], "lang": "en"})["session"]
    ev = []
    async with websockets.connect(f"{W}/ws/live?session={sid}", max_size=None) as ws:
        async def rd():
            try:
                async for m in ws:
                    if isinstance(m, str):
                        ev.append(json.loads(m))
            except Exception:
                pass
        t = asyncio.create_task(rd())
        for _ in range(100):
            if any(e["type"] in ("ready", "fallback") for e in ev):
                break
            await asyncio.sleep(0.1)
        q = item["q"].replace("{CASE}", QB.case_id()).replace("{FOREIGN}", QB.foreign())
        n = len(ev); t0 = time.time()
        await ws.send(json.dumps({"type": "text", "text": q}))
        tc = None
        for _ in range(450):
            await asyncio.sleep(0.1)
            tc = next((e for e in ev[n:] if e["type"] == "turn_complete"), None)
            if tc:
                break
        tools = [e for e in ev[n:] if e["type"] == "tool"]
        said = (tc or {}).get("mitra", "")
        if any(u.get("op") == "confirm" for x in tools for u in x["ui"]):
            await ws.send(json.dumps({"type": "text", "text": "no"}))
            await asyncio.sleep(3)
        t.cancel()
    digits = " ".join(str(int(x)) if float(x).is_integer() else str(x) for x in guard.spoken_numbers(said))
    r = {"say": said + " " + digits, "ui": [u for x in tools for u in x["ui"]], "intent": tools[-1]["name"] if tools else ""}
    probs = []
    for chk in item["checks"]:
        try:
            ok, why = chk(r, {})
        except Exception as e:  # noqa: BLE001
            ok, why = False, str(e)
        if not ok:
            probs.append(why)
    return {"id": item["id"], "group": item["group"], "q": q, "ok": not probs, "problems": probs, "fns": [x["name"] for x in tools],
            "said": said[:220], "secs": round(time.time() - t0, 1)}


async def main():
    per = defaultdict(int)
    items = []
    only = {int(x) for x in A.only.split(",") if x.strip()}
    for it in QB.BANK:
        if only:
            if it["id"] in only:
                items.append(it)
            continue
        if it["group"] in SKIP or (A.profile and it["profile"] != A.profile):
            continue
        if per[it["group"]] < A.per:
            per[it["group"]] += 1; items.append(it)
    print(f"{len(items)} questions on real Gemini Live ({A.base})", flush=True)
    res = []
    for it in items:
        r = await ask(it)
        res.append(r)
        print(f"  {'PASS' if r['ok'] else 'FAIL'} #{r['id']:>3} [{r['group']}] {r['q'][:56]!r} -> {r['fns']} ({r['secs']}s)"
              + ("" if r["ok"] else f" :: {r['problems'][0][:120]} :: {r['said'][:100]!r}"), flush=True)
    ok = sum(r["ok"] for r in res)
    (HERE / "live_bank_report.json").write_text(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M"), "passed": ok, "total": len(res), "results": res}, indent=1), encoding="utf-8")
    print(f"\n{ok}/{len(res)} passed")


asyncio.run(main())
