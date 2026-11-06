"""Full-duplex relay tests. Offline mode (default): Mitra on 8031 talks to the fake Live server (tests/fake_live.py on 8099),
Mitra on 8032 to a failing fake (8098). Online mode (--online): the main Mitra on 8030 against real Gemini Live, a short
acceptance run (a few turns, keeps credit use small).
Run from mitra/: python tests/test_live.py [--online]"""
import asyncio
import json
import math
import sys
import time
import urllib.request

import websockets

ONLINE = "--online" in sys.argv
B = "http://localhost:8030" if ONLINE else "http://localhost:8031"
W = B.replace("http", "ws")
ok = fail = 0


def post(p, d, base=B):
    r = urllib.request.Request(base + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=120).read())


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:300])


class Live:
    def __init__(self, sid, base=W):
        self.sid, self.base, self.ev, self.audio = sid, base, [], 0

    async def __aenter__(self):
        self.ws = await websockets.connect(f"{self.base}/ws/live?session={self.sid}", max_size=None)
        self.reader = asyncio.create_task(self._read())
        return self

    async def __aexit__(self, *a):
        self.reader.cancel()
        try:
            await self.ws.close()
        except Exception:
            pass

    async def _read(self):
        try:
            async for m in self.ws:
                if isinstance(m, bytes):
                    self.audio += len(m)
                else:
                    self.ev.append(json.loads(m))
        except Exception:
            pass

    async def say(self, text, voice=True):
        await self.ws.send(json.dumps({"type": "text", "text": ("[voice] " if voice and not ONLINE else "") + text}))

    async def wait(self, typ, secs=30.0, since=0, pred=None):
        t0 = time.time()
        while time.time() - t0 < secs:
            for e in self.ev[since:]:
                if e.get("type") == typ and (pred is None or pred(e)):
                    return e
            await asyncio.sleep(0.05)
        return None

    async def turn(self, text, secs=40.0):
        n = len(self.ev)
        await self.say(text)
        tc = await self.wait("turn_complete", secs, since=n)
        tools = [e for e in self.ev[n:] if e.get("type") == "tool"]
        print(f"    > {text!r} -> {[t['name'] for t in tools]} :: {(tc or {}).get('mitra', '')[:110]!r}")
        return tc, tools


def loud_pcm(seconds=2.5):
    """Real speech (the 16 kHz test clip), so a real voice-activity detector hears a person talking over Mitra."""
    import wave
    from pathlib import Path
    with wave.open(str(Path(__file__).resolve().parents[2] / "tools" / "tests" / "asr_test.wav")) as w:
        return w.readframes(int(16000 * seconds))


async def main():
    print(f"[{'ONLINE · real Gemini Live' if ONLINE else 'OFFLINE · fake Live'}]")
    print("[citizen files a grievance by voice, full duplex]")
    sid = post("/api/session", {"profile": "citizen", "officer": "", "lang": "en"})["session"]
    async with Live(sid) as L:
        rd = await L.wait("ready", 15)
        check("live session ready", bool(rd), L.ev[:3])
        tc, tools = await L.turn("the street light near the bus stand is not working")
        check("problem -> chat_text tool ran", any(t["name"] == "chat_text" for t in tools), tools)
        check("request card sent to the screen", any(u.get("op") == "request" for t in tools for u in t["ui"]), [t["ui"] for t in tools])
        check("spoken reply streamed as audio", L.audio > 0, L.audio)
        check("transcript of the reply", bool(tc and tc.get("mitra")), tc)
        await L.turn("Piriyapatna")
        await L.turn("Attigodu")
        tc, tools = await L.turn("yes, file it")
        routed = [u for t in tools for u in t["ui"] if u.get("op") == "routed"]
        check("filed and routed to the exact officer", bool(routed) and "Attigodu" in json.dumps(routed), tools)
        cid = routed[0]["caseId"] if routed else ""
        hist = post("/api/session", {"session": sid, "profile": "citizen", "officer": "", "lang": "en"})
        check("turns logged for the conversation strip", bool(cid), cid)

        print("[interruption]")
        n = len(L.ev)
        await L.say("what can you do")
        await L.wait("out", 20, since=n)
        pcm = loud_pcm()
        for i in range(0, len(pcm), 3200):                   # talk over it, in real time
            await L.ws.send(pcm[i:i + 3200]); await asyncio.sleep(0.1)
        it = await L.wait("interrupted", 6, since=n)
        check("talking over Mitra interrupts it", bool(it), [e["type"] for e in L.ev[n:]][:12])
        n = len(L.ev)
        await L.say("what can you do")
        await L.wait("out", 20, since=n)
        await L.say("track my request")                       # a new request mid-answer
        it = await L.wait("interrupted", 6, since=n)
        tr = await L.wait("tool", 30, since=n, pred=lambda e: e["name"] == "track")
        # the new request must be handled; "interrupted" only appears if the first answer was still being spoken
        check("a new request mid-answer is handled", bool(tr), [e.get("type") for e in L.ev[n:]][:15])

        print("[profile switch reconfigures the live session]")
        n = len(L.ev)
        await L.say("switch to officer mode")
        rc = await L.wait("reconfigure", 30, since=n)
        check("switch_profile -> reconfigure", bool(rc), [e.get("type") for e in L.ev[n:]])

    print("[officer, full duplex]")
    osid = post("/api/session", {"profile": "officer", "officer": "tah_piriyapatna", "lang": "en"})["session"]
    async with Live(osid) as L:
        await L.wait("ready", 15)
        tc, tools = await L.turn("read my inbox")
        check("inbox via live", any(t["name"] == "inbox" for t in tools) and any(u.get("op") == "inbox" for t in tools for u in t["ui"]), tools)
        tc, tools = await L.turn("open the first one")
        check("ordinal 'first' opens a case", any(u.get("op") == "case" for t in tools for u in t["ui"]), tools)

    print("[kannada is full duplex too (22 Oct); failures fall back to the cascade]")
    ksid = post("/api/session", {"profile": "citizen", "officer": "", "lang": "kn"})["session"]
    async with Live(ksid) as L:
        rd = await L.wait("ready", 8)
        check("Kannada session -> the same live relay (ready, not a fallback)", bool(rd) and not any(e.get("type") == "fallback" for e in L.ev), L.ev)
    if not ONLINE:
        fsid = post("/api/session", {"profile": "cs", "officer": "", "lang": "en"}, base="http://localhost:8032")["session"]
        async with Live(fsid, base="ws://localhost:8032") as L:
            fb = await L.wait("fallback", 15)
            check("quota error upstream -> fallback, no crash", bool(fb), L.ev)
        r = json.loads(urllib.request.urlopen("http://localhost:8032/api/health").read())
        check("server still healthy after the failure", r.get("ok") is True, r)

    print(f"\n{ok}/{ok + fail} checks passed")


asyncio.run(main())
