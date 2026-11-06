"""Kannada navigation on the real live voice: which function is called, with which arguments, and what reaches the screen.
Run from mitra/: PYTHONIOENCODING=utf-8 python tests/kn_nav_probe.py [profile] [phrases...]"""
import asyncio
import json
import sys
import time
import urllib.request

import websockets

B = "http://localhost:8030"
PHRASES = sys.argv[2:] or [
    "citizen view ಗೆ ಕರ್ಕೊಂಡು ಹೋಗಿ",
    "ನಾಗರಿಕರ view ತೋರಿಸಿ",
    "officer profile ಗೆ ಹೋಗಿ",
    "ನನ್ನ inbox ತೋರಿಸಿ",
    "Chief Secretary view ಗೆ ವಾಪಸ್ ಹೋಗಿ",
    "dashboard ಗೆ ವಾಪಸ್ ಕರ್ಕೊಂಡು ಹೋಗಿ",
    "app view ಗೆ ಹೋಗಿ",
]


def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


async def main():
    prof = sys.argv[1] if len(sys.argv) > 1 else "cs"
    sid = post("/api/session", {"profile": prof, "officer": "", "lang": "kn"})["session"]
    for ph in PHRASES:
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
            for _ in range(250):
                await asyncio.sleep(0.1)
                if any(e.get("type") in ("turn_complete", "reconfigure") for e in ev):
                    await asyncio.sleep(0.5)
                    break
            tools = [e for e in ev if e.get("type") == "tool"]
            ops = [(u.get("op"), u.get("profile") or u.get("target") or u.get("view") or "") for x in tools for u in x.get("ui") or [] if u.get("op") in ("profile", "nav", "view", "inbox")]
            said = next((e.get("mitra", "") for e in ev if e.get("type") == "turn_complete"), "")
            s = post("/api/session", {"session": sid, "profile": "", "lang": "kn"}) if False else None
            print(f"{ph!r}\n   tools={[(x['name'], x.get('args')) for x in tools]} ops={ops} reconf={any(e.get('type') == 'reconfigure' for e in ev)} ({time.time() - t0:.1f}s)\n   said={said[:120]!r}")
            t.cancel()


asyncio.run(main())
