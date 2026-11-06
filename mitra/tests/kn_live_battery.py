"""Kannada in FULL DUPLEX on the real live model (22 Oct 2026). A Kannada session (lang kn) opens the same /ws/live relay as
English: casual Bengaluru Kannada in, functions called with English arguments (or Kannada normalised by the server), the answer
spoken in Kannada (Kannada script in the transcript), first audio timed. Citizen: complaint -> filed; knowledge. CS: counts,
a dashboard board, levels, then switching back to English. Run from mitra/: PYTHONIOENCODING=utf-8 python tests/kn_live_battery.py"""
import asyncio
import json
import sys
import time
import urllib.request

import websockets

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8030"
W = B.replace("http", "ws")
KN = lambda s: sum(1 for ch in s or "" if "ಀ" <= ch <= "೿")
ok = fail = 0
FAILS = []


def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


async def session(profile, steps):
    global ok, fail
    sid = post("/api/session", {"profile": profile, "officer": "", "lang": "kn"})["session"]
    ev = []
    async with websockets.connect(f"{W}/ws/live?session={sid}", max_size=None) as ws:
        async def rd():
            try:
                async for m in ws:
                    ev.append(json.loads(m) if isinstance(m, str) else {"type": "audio", "t": time.time()})
            except Exception:
                pass
        t = asyncio.create_task(rd())
        for _ in range(100):
            if any(e.get("type") in ("ready", "fallback") for e in ev):
                break
            await asyncio.sleep(0.1)
        if not any(e.get("type") == "ready" for e in ev):
            print("  live not ready:", ev[:2]); fail += len(steps); return
        for text, exp in steps:
            n = len(ev); t0 = time.time()
            await ws.send(json.dumps({"type": "text", "text": text}))
            tc = None
            for _ in range(600):
                await asyncio.sleep(0.1)
                tc = next((e for e in ev[n:] if e.get("type") == "turn_complete"), None)
                if tc or any(e.get("type") == "reconfigure" for e in ev[n:]):
                    break
            tools = [e for e in ev[n:] if e.get("type") == "tool"]
            names = [x["name"] for x in tools]
            said = (tc or {}).get("mitra", "") or " ".join(e.get("text", "") for e in ev[n:] if e.get("type") == "out")
            first = next((e["t"] for e in ev[n:] if e.get("type") == "audio"), None)
            good = False
            try:
                good = bool(exp(names, said, tools, ev[n:]))
            except Exception as e:  # noqa: BLE001
                said += f" [check error {e}]"
            ok += good; fail += not good
            if not good:
                FAILS.append((profile, text, names, said[:200]))
            fa = f"{first - t0:.1f}s" if first else "-"
            print(f"  {'PASS' if good else 'FAIL'} [{profile}/kn] {text[:48]!r} -> {names} (first audio {fa}, turn {time.time() - t0:.1f}s, kn chars {KN(said)}) :: {said[:120]!r}")
        t.cancel()


def kn_spoken(n, s, t, e): return KN(s) >= 8
def called(*fns): return lambda n, s, t, e: any(f in n for f in fns) and KN(s) >= 8
def ui_op(op): return lambda n, s, t, e: any(u.get("op") == op for x in t for u in x.get("ui") or [])
def both(*fs): return lambda n, s, t, e: all(f(n, s, t, e) for f in fs)
def say_has(*w): return lambda n, s, t, e: any(x in " ".join(y.get("say", "") for y in t) for x in w)


async def main():
    print("[citizen, Kannada full duplex]")
    await session("citizen", [
        ("ನಮಸ್ಕಾರ, ನಮ್ಮ ಊರು ಗೊರಹಳ್ಳಿಯಲ್ಲಿ ಒಂದು ವಾರದಿಂದ ಕುಡಿಯುವ ನೀರು ಬರ್ತಿಲ್ಲ", both(called("chat_text"), ui_op("request"))),
        ("ಹೌದು, file ಮಾಡಿ", both(called("confirm"), ui_op("routed"))),
        ("ಸಕಾಲ ಅಂದ್ರೆ ಏನು?", called("ask_knowledge")),
    ])
    print("[chief secretary, Kannada full duplex]")
    await session("cs", [
        ("ಹುಣಸೂರು ತಾಲ್ಲೂಕಿನಲ್ಲಿ ಎಷ್ಟು cases pending ಇದೆ?", both(called("find_cases", "dashboard", "place_info"), say_has("10"))),
        ("RDPR ಹೇಗೆ perform ಮಾಡ್ತಿದೆ?", both(called("dashboard"), ui_op("viz"))),
        ("L1 officers ಹತ್ರ ಎಷ್ಟು cases ಇವೆ?", both(called("find_cases", "dashboard"), ui_op("viz"))),
        ("switch to English please", lambda n, s, t, e: "set_language" in n),
    ])
    print(f"\n{ok}/{ok + fail} checks passed")
    for f in FAILS:
        print("  FAIL:", f)


asyncio.run(main())
