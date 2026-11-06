"""Focused battery for the real Gemini Live model (online; ~25 turns, one session per profile to keep credit use small):
does the live model choose the right Sakala function, refuse to file junk, and speak results faithfully?
Run from mitra/: python tests/live_battery.py [base]   (default http://localhost:8030)"""
import asyncio
import json
import re
import sys
import time
import urllib.request

import websockets

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8030"
W = B.replace("http", "ws")
ok = fail = 0
FAILS = []


def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


async def session(profile, steps, officer=""):
    global ok, fail
    sid = post("/api/session", {"profile": profile, "officer": officer, "lang": "en"})["session"]
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
        if not any(e["type"] == "ready" for e in ev):
            print("  live not ready:", ev); fail += len(steps); return
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
            except Exception:
                pass
            ok += good; fail += not good
            if not good:
                FAILS.append((profile, text, names, said[:200]))
            print(f"  {'PASS' if good else 'FAIL'} [{profile}] {text[:58]!r} -> {names} ({time.time() - t0:.1f}s) :: {said[:110]!r}")
        t.cancel()


def called(*fns): return lambda n, s, t: any(f in n for f in fns)
def none_filed(n, s, t): return not any(u.get("op") == "routed" for x in t for u in x["ui"]) and "confirm" not in n and len(s) > 3
def spoke(*words): return lambda n, s, t: any(w.lower() in s.lower() for w in words)
def both(*fs): return lambda n, s, t: all(f(n, s, t) for f in fs)


async def main():
    print("[citizen]")
    await session("citizen", [
        ("hello hello, just testing", none_filed),
        ("tell me a joke", none_filed),
        ("there is no drinking water in Gorahalli for a week", called("chat_text")),
        ("yes, please file it", both(called("confirm"), spoke("GR", "G R", "registered", "reference"))),
        ("what is the status of my request?", called("track")),
        ("the street light near the bus stand in Piriyapatna is broken", called("chat_text")),
        ("actually cancel that", lambda n, s, t: "confirm" not in n),
        ("I want to apply for a caste certificate", called("apply_service", "chat_text")),
        ("switch to the officer screen", called("switch_profile", "go_to")),
    ])
    print("[officer]")
    await session("officer", [
        ("read my inbox", called("inbox")),
        ("open the first one", called("open_case", "lookup_case")),
        ("who does this case escalate to?", lambda n, s, t: len(s) > 10),
        ("how many of my cases are in Komalapura?", called("find_cases", "place_info", "ask_data", "inbox")),
        ("I want to file a complaint about my own street", lambda n, s, t: "confirm" not in n and len(s) > 10),
    ], "tah_piriyapatna")
    print("[chief secretary]")
    await session("cs", [
        ("good evening Mitra", lambda n, s, t: len(s) > 5),
        ("give me the position across the state", called("summary", "statewide_stats")),
        ("tell me about grievance 503063", both(called("lookup_case", "open_case", "ask_data"), spoke("Mandya", "Urban"))),
        ("what is the status of SK-RD855S260004811 and who is the officer?", both(called("lookup_case", "open_case"), spoke("Tahsildar"))),
        ("which district has the most open cases?", both(called("ranking", "find_cases", "statewide_stats", "ask_data"), spoke("Shivamogga"))),
        ("how many Revenue cases are open in Bagalkote?", both(called("find_cases", "ask_data"), spoke("77", "seventy"))),
        ("tell me about PDO Attigodu", called("officer_profile")),
        ("what is Bylakuppe?", both(called("place_info"), spoke("Piriyapatna"))),
        ("which district was worst in Sakala 2025?", both(called("sakala_2025", "tracker"), spoke("Bengaluru"))),
        ("nudge the Tahsildar of Piriyapatna and tell him the caste certificate must be cleared today", called("nudge")),
        ("tell me about grievance 999999", lambda n, s, t: bool(re.search(r"could ?n.t|not find|no record|unable|doesn.t", s, re.I))),
    ])
    print("[16 Oct regressions: citizen pension in Live, CS chart switching + navigation]")
    await session("citizen", [
        ("my friend's father's old age pension has been delayed for three months, can you raise a grievance?", lambda n, s, t: "chat_text" in n or (len(s) > 5 and "could not send" not in s.lower())),
        ("his name is Mohan Kumar, he lives in Hunsur taluk", lambda n, s, t: "chat_text" in n and "could not send" not in s.lower()),
        ("the street light near my house isn't working, could you raise a grievance for that?", lambda n, s, t: "could not send" not in s.lower() and len(s) > 5),
    ])
    await session("cs", [
        ("can you show me what's going on right now across all districts?", lambda n, s, t: any(u.get("op") == "viz" for x in t for u in x["ui"])),
        ("could you show this on the Karnataka map?", both(called("show_chart_as"), lambda n, s, t: any(u.get("op") == "morph" for x in t for u in x["ui"]))),
        ("show it as a bar graph", called("show_chart_as")),
        ("okay, can you take me back to the dashboard?", both(called("go_to"), lambda n, s, t: any(u.get("op") == "nav" for x in t for u in x["ui"]))),
    ])
    print(f"\n{ok}/{ok + fail} checks passed")
    for f in FAILS:
        print("  FAIL:", f)


if __name__ == "__main__":
    asyncio.run(main())
