"""Language switching by voice on the real live model, both ways (22 Oct 2026, Pranay): an English session asked for Kannada
(or simply spoken to in Kannada) must become a Kannada session, and a Kannada session asked for English (in either language)
must become English. Prints the function called, whether the relay reconfigured, and the session language afterwards.
Run from mitra/: PYTHONIOENCODING=utf-8 python tests/lang_switch_probe.py [profile]"""
import asyncio
import json
import sys
import time
import urllib.request

import websockets

B = "http://localhost:8030"
KN = lambda s: sum(1 for ch in s or "" if "ಀ" <= ch <= "೿")
CASES = [
    ("en", "ನಮ್ಮ ಊರಲ್ಲಿ ಎರಡು ದಿನದಿಂದ ನೀರು ಬರ್ತಿಲ್ಲ", "kn"),
    ("kn", "I want to file a complaint, switch to English", "en"),
] if "--mix" in sys.argv else [
    ("en", "ಕನ್ನಡಕ್ಕೆ ಬದಲಾಯಿಸಿ", "kn"),
    ("en", "Kannada please", "kn"),
] if "--kn2" in sys.argv else [
    ("en", "can you please shift to Kannada", "kn"),
    ("en", "switch to Kannada", "kn"),
    ("en", "ಕನ್ನಡದಲ್ಲಿ ಮಾತಾಡಿ", "kn"),
    ("en", "ನಮ್ಮ ಊರಲ್ಲಿ ಎರಡು ದಿನದಿಂದ ನೀರು ಬರ್ತಿಲ್ಲ", "kn"),
    ("kn", "switch to English", "en"),
    ("kn", "English ನಲ್ಲಿ ಮಾತಾಡಿ", "en"),
    ("kn", "ಇಂಗ್ಲಿಷ್ ಗೆ ಬದಲಾಯಿಸಿ", "en"),
    ("kn", "can we continue in English please", "en"),
]


def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


def get(p):
    return json.loads(urllib.request.urlopen(B + p, timeout=60).read())


async def one(prof, lang, ph, want):
    sid = post("/api/session", {"profile": prof, "officer": "", "lang": lang})["session"]
    ev = []
    async with websockets.connect(f"ws://localhost:8030/ws/live?session={sid}", max_size=None) as ws:
        async def rd():
            try:
                async for m in ws:
                    if isinstance(m, str):
                        ev.append(json.loads(m))
            except Exception:
                pass
        t = asyncio.create_task(rd())
        for _ in range(100):
            if any(e.get("type") in ("ready", "fallback") for e in ev):
                break
            await asyncio.sleep(0.1)
        t0 = time.time()
        await ws.send(json.dumps({"type": "text", "text": ph}))
        for _ in range(300):
            await asyncio.sleep(0.1)
            if any(e.get("type") in ("turn_complete", "reconfigure") for e in ev):
                await asyncio.sleep(0.3)
                break
        tools = [(e["name"], e.get("args")) for e in ev if e.get("type") == "tool"]
        reconf = any(e.get("type") == "reconfigure" for e in ev)
        ann = next((e.get("say", "") for e in ev if e.get("type") == "reconfigure"), "")
        said = next((e.get("mitra", "") for e in ev if e.get("type") == "turn_complete"), "") or " ".join(e.get("text", "") for e in ev if e.get("type") == "out")
        t.cancel()
    after = post("/api/session", {"session": sid, "profile": prof, "officer": "", "lang": ""}).get("lang") if False else get(f"/api/boot?session={sid}").get("lang") if False else None
    # the session's language is read back through a fresh /api/session call that does not change it
    after = store_lang(sid)
    good = after == want
    print(f"{'PASS' if good else 'FAIL'} [{lang}] {ph!r} -> tools={[n for n, _ in tools]} reconf={reconf} lang_after={after} ({time.time() - t0:.1f}s) announce={ann[:160]!r}")
    return good


def store_lang(sid):
    import sqlite3
    from pathlib import Path
    db = Path(__file__).resolve().parents[1] / "data" / "mitra.db"
    c = sqlite3.connect(db)
    r = c.execute("select lang from sessions where id=?", (sid,)).fetchone()
    c.close()
    return r[0] if r else None


async def main():
    prof = sys.argv[1] if len(sys.argv) > 1 else "citizen"
    n = 0
    for lang, ph, want in CASES:
        n += await one(prof, lang, ph, want)
    print(f"\n{n}/{len(CASES)} switched as asked")


asyncio.run(main())
