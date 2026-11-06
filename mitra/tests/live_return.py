"""Return with a suggestion on the REAL live voice (main instance 8030), English and Kannada (22 Oct 2026, Pranay).
Officer Tahsildar Piriyapatna opens a case, says it is not theirs and who / where it belongs, confirms; the case must end
with that officer. With nothing suggested it must go to the scrutiny desk. Run from mitra/: python tests/live_return.py"""
import asyncio
import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

import websockets

B, W = "http://localhost:8030", "ws://localhost:8030"
DB = Path(__file__).resolve().parents[2] / "app" / "data" / "sakala.db"
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:400])


def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


def q1(sql, *a):
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    r = c.execute(sql, a).fetchone(); c.close()
    return dict(r) if r else None


USED = []


def fresh():
    r = q1("SELECT id FROM cases WHERE owner='tah_piriyapatna' AND status='Pending' AND kind='GRIEVANCE' AND id NOT IN (%s) ORDER BY id DESC LIMIT 1"
           % ",".join("?" * max(1, len(USED))), *(USED or [""]))
    USED.append(r["id"]); return r["id"]


async def run(lang, steps, cid, want):
    sid = post("/api/session", {"profile": "officer", "officer": "tah_piriyapatna", "lang": lang})["session"]
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
            if any(e.get("type") == "ready" for e in ev):
                break
            await asyncio.sleep(0.1)
        said = []
        for text in [f"open {cid}"] + steps:
            n = len(ev); t0 = time.time()
            await ws.send(json.dumps({"type": "text", "text": text}))
            for _ in range(300):
                await asyncio.sleep(0.1)
                if any(e.get("type") == "turn_complete" for e in ev[n:]):
                    await asyncio.sleep(0.4)
                    break
            tools = [(e["name"], {k: v for k, v in (e.get("args") or {}).items()}) for e in ev[n:] if e.get("type") == "tool"]
            tc = next((e for e in ev[n:] if e.get("type") == "turn_complete"), {})
            said.append((text, [x[0] for x in tools], tc.get("mitra", "")[:160], round(time.time() - t0, 1)))
        t.cancel()
    owner = q1("SELECT owner, status FROM cases WHERE id=?", cid)
    for s in said:
        print("     ", s)
    return owner


async def main():
    print("[English: officer named]")
    cid = fresh()
    o = await run("en", ["This is not my jurisdiction. Please send it to the Tahsildar of Hunsur.", "yes, go ahead"], cid, "tah_hunsur")
    check(f"{cid} -> Tahsildar Hunsur", o["owner"] == "tah_hunsur" and o["status"] == "Pending", o)
    print("[English: place only]")
    cid = fresh()
    o = await run("en", ["Not mine, this belongs to Hunsur taluk.", "yes"], cid, "tah_hunsur")
    check(f"{cid} -> the Hunsur officer for that service", o["owner"] == "tah_hunsur", o)
    print("[English: nothing suggested]")
    cid = fresh()
    o = await run("en", ["Return this one, it's not my jurisdiction.", "yes"], cid, "")
    check(f"{cid} -> scrutiny desk", o["status"] == "Scrutiny", o)
    print("[Kannada: place said in Kannada]")
    cid = fresh()
    o = await run("kn", ["ಇದು ನನ್ನ ವ್ಯಾಪ್ತಿಗೆ ಬರಲ್ಲ, ಹುಣಸೂರು ತಹಶೀಲ್ದಾರ್ ಗೆ ಕಳಿಸಿ", "ಹೌದು, ಕಳಿಸಿ"], cid, "tah_hunsur")
    check(f"{cid} -> Tahsildar Hunsur (Kannada)", o["owner"] == "tah_hunsur", o)
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
