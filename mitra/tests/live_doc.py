"""The document door on the REAL Gemini Live model (main instance 8030): a real handwritten letter uploaded on a citizen session,
then the rest by voice over Live: 'submit' files it (or sends it to the scrutiny desk with the letter), 'the phone number is …'
edits the form. Run from mitra/: PYTHONIOENCODING=utf-8 python tests/live_doc.py [base]"""
import asyncio
import base64
import json
import sys
import time
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_battery as LB  # noqa: E402

if len(sys.argv) > 1:
    LB.B = sys.argv[1]; LB.W = LB.B.replace("http", "ws")
LETTERS = Path(__file__).resolve().parents[2] / "tools" / "tests" / "letters"
POC = "http://localhost:8020"
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    ok += bool(cond); fail += not cond
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else f"  <- {str(detail)[:300]}"))


async def live_steps(sid, steps):
    """Send typed turns into the real Live session and judge each (same shape as live_battery)."""
    ev = []
    async with websockets.connect(f"{LB.W}/ws/live?session={sid}", max_size=None) as ws:
        async def rd():
            try:
                async for m in ws:
                    if isinstance(m, str):
                        ev.append(json.loads(m))
            except Exception:  # noqa: BLE001
                pass
        t = asyncio.create_task(rd())
        for _ in range(100):
            if any(e["type"] in ("ready", "fallback") for e in ev):
                break
            await asyncio.sleep(0.1)
        if not any(e["type"] == "ready" for e in ev):
            check("live ready", False, ev[:2]); t.cancel(); return []
        out = []
        for text, exp in steps:
            n = len(ev); t0 = time.time()
            await ws.send(json.dumps({"type": "text", "text": text}))
            tc = None
            for _ in range(600):
                await asyncio.sleep(0.1)
                tc = next((e for e in ev[n:] if e["type"] == "turn_complete"), None)
                if tc:
                    break
            tools = [e for e in ev[n:] if e["type"] == "tool"]
            names = [x["name"] for x in tools]
            said = (tc or {}).get("mitra", "")
            good = False
            try:
                good = bool(exp(names, said, tools))
            except Exception:  # noqa: BLE001
                pass
            check(f"live {text!r} -> {names} ({time.time() - t0:.1f}s) :: {said[:100]!r}", good)
            out.append((names, said, tools))
        t.cancel()
        return out


def upload(sid, name):
    f = LETTERS / name
    t0 = time.time()
    r = LB.post("/api/document", {"session": sid, "file_b64": base64.b64encode(f.read_bytes()).decode(), "media_type": "image/jpeg", "filename": name})
    return r, time.time() - t0


def routed(n, s, t):
    return any(u.get("op") == "routed" for x in t for u in x["ui"])


def ui_of(r, op):
    return [u for u in (r.get("ui") or []) if u.get("op") == op]


async def main():
    print("[letter 1: Kodigenahalli water, filed by voice]")
    sid = LB.post("/api/session", {"profile": "citizen", "lang": "en"})["session"]
    r, dt = upload(sid, "l1_kodigenahalli_water.jpeg")
    say = r.get("say") or ""
    card = next((u for u in ui_of(r, "request")), {})
    doc = (card.get("draft") or {}).get("doc") or {}
    print(f"  upload {dt:.1f} s :: {say[:160]!r}")
    check("read into the form: name, date, the iPGRS record, the place, the PDO", "read the letter" in say.lower() and "narasimhaiah" in say.lower() and "502806" in say
          and (doc.get("record") or {}).get("gid") == "502806" and "Kodigenahalli" in json.dumps(card.get("draft", {}).get("place")) and "Kodigenahalli" in json.dumps(card.get("draft", {}).get("preview")), {"say": say, "rec": doc.get("record"), "place": (card.get("draft") or {}).get("place")})
    check("upload within 20 s", dt < 20, f"{dt:.1f} s")
    res = await live_steps(sid, [
        ("I want to upload another letter", lambda n, s, t: "upload_document" in n and not routed(n, s, t)),
        ("the phone number is 9980012345", lambda n, s, t: ("chat_text" in n or "citizen_text" in n or n) and "phone" in s.lower()),
        ("submit", lambda n, s, t: routed(n, s, t) and "registered" in s.lower()),
    ])
    if res and res[-1][2]:
        cid = next((u.get("caseId") for x in res[-1][2] for u in x["ui"] if u.get("op") == "routed"), None)
        import urllib.request
        if cid:
            cj = json.loads(urllib.request.urlopen(f"{POC}/api/case/{cid}", timeout=30).read())
            check("the case on the POC: src=document, phone from the voice edit, the record, the Kodigenahalli PDO",
                  cj.get("src") == "document" and (cj.get("doc") or {}).get("phone") == "9980012345" and (cj.get("doc") or {}).get("record") == "502806" and "kodigenahalli" in (cj.get("owner") or "").lower(),
                  {"src": cj.get("src"), "doc_phone": (cj.get("doc") or {}).get("phone"), "rec": (cj.get("doc") or {}).get("record"), "owner": cj.get("owner")})
    print("[letter 2: Chintamani scholarship, outside the pilot: scrutiny desk by voice]")
    sid = LB.post("/api/session", {"profile": "citizen", "lang": "en"})["session"]
    r, dt = upload(sid, "l2_chintamani_ssp.jpeg")
    say = r.get("say") or ""
    print(f"  upload {dt:.1f} s :: {say[:200]!r}")
    check("read, outside the pilot, the record quoted, submit offered", "keerthana" in say.lower() and "scrutiny" in say.lower() and "502854" in say, say)
    res = await live_steps(sid, [
        # judged on the action itself: Gemini Live occasionally stays silent after a function result (the known 4 s nudge case)
        ("yes submit it", lambda n, s, t: "confirm" in n and ("scrutiny" in s.lower() or "scrutiny" in json.dumps([x["ui"] for x in t]).lower())),
    ])
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
