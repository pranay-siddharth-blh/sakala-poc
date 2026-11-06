"""Cross-profile real-time test for Sakala Mitra.

A citizen files by voice (typed here) -> the officer's screen is told within seconds -> the officer acts
(accept, ask, resolve) -> the citizen's screen hears each one -> the CS nudges -> the officer hears it.
Also: photo intake refusal, apply flow, reply, feedback, appeal, and the WhatsApp POC still passing.
Run with Mitra (8030) and the Sakala POC (8020) up:  PYTHONIOENCODING=utf-8 python tests/test_realtime.py"""
import json
import re
import sys
import threading
import time
import urllib.request

B = "http://localhost:8030"
ok, T = 0, []


def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=240).read())


def get(p):
    return json.loads(urllib.request.urlopen(B + p, timeout=60).read())


def check(n, c, d=""):
    global ok
    ok += bool(c)
    T.append(n)
    print(("  PASS " if c else "  FAIL ") + n + ("" if c else f"  <- {str(d)[:240]}"), flush=True)


def say(sid, text):
    t0 = time.time()
    r = post("/api/turn", {"session": sid, "text": text, "want_audio": False})
    if any(u.get("op") == "confirm" and u.get("question") for u in r.get("ui", [])) and not re.match(r"^\s*(yes|no)\b", text, re.I):
        r = {**post("/api/turn", {"session": sid, "text": "yes", "want_audio": False}), "_readback": r["say"]}    # guardrail 17
    print(f"    > {text!r} -> {r['intent']} ({time.time() - t0:.1f}s) :: {r['say'][:120]!r}", flush=True)
    return r


class Listener(threading.Thread):
    """Collects SSE events for one screen (session)."""

    def __init__(self, sid):
        super().__init__(daemon=True)
        self.sid, self.events, self.stop = sid, [], False

    def run(self):
        resp = urllib.request.urlopen(B + f"/api/events?session={self.sid}", timeout=600)
        for raw in resp:
            if self.stop:
                break
            line = raw.decode("utf-8", "ignore").strip()
            if line.startswith("data:"):
                try:
                    self.events.append((time.time(), json.loads(line[5:])))
                except Exception:
                    pass

    def wait(self, pred, timeout=8.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            for ts, e in list(self.events):
                if ts >= t0 - 1.0 and pred(e):
                    return e, round(time.time() - t0, 2)
            time.sleep(0.1)
        return None, timeout


until = time.time() + 60
while time.time() < until:
    try:
        if get("/api/health").get("sakala"):
            break
    except Exception:
        pass
    time.sleep(1.5)

print("[sessions + live listeners]")
cit = post("/api/session", {"profile": "citizen", "officer": "tah_piriyapatna", "lang": "en"})["session"]
Lc = Listener(cit); Lc.start()
off_sid = None
Lo = None
cs = post("/api/session", {"profile": "cs", "officer": "", "lang": "en"})["session"]
Lcs = Listener(cs); Lcs.start()
time.sleep(1.0)

print("[citizen files by voice]")
r = say(cit, "there is no drinking water in Gorahalli village for one week")
check("understood with place and officer preview", r["intent"] == "chat_text" and "Drinking Water" in r["say"] and "Shall I file it" in r["say"], r["say"])
check("request card + stages ui", any(u["op"] == "request" for u in r["ui"]) and any(u["op"] == "stages" for u in r["ui"]), [u["op"] for u in r["ui"]])
t0 = time.time()
r = say(cit, "yes, file it")
check("filed and routed", r["intent"] == "confirm" and "Registered" in r["say"] and "reference is GR-" in r["say"], r["say"])
cid = next((u["caseId"] for u in r["ui"] if u.get("op") == "routed"), None)
officer = next((u["officer"]["id"] for u in r["ui"] if u.get("op") == "routed"), None)
check("case id + officer known", bool(cid and officer), r["ui"])
e, dt = Lcs.wait(lambda e: e.get("type") == "case" and e.get("id") == cid and e.get("change") == "new")
check(f"CS screen told of the new case live ({dt}s)", e is not None, Lcs.events[-3:])
check("event carries the voice channel", (e or {}).get("src") == "mitra", e)

print("[officer screen]")
off = post("/api/session", {"profile": "officer", "officer": officer, "lang": "en"})["session"]
Lo = Listener(off); Lo.start(); time.sleep(0.8)
r = say(off, "read my inbox")
check("new case is in the officer inbox", r["intent"] == "inbox" and cid in json.dumps(r["ui"]), r["say"])
r = say(off, f"open {cid}")
check("officer opens it", cid in r["say"], r["say"])
r = say(off, "accept")
e, dt = Lc.wait(lambda e: e.get("type") == "case" and e.get("id") == cid and e.get("change") == "accepted" and e.get("mine"))
check(f"citizen screen told of the acceptance live, marked mine ({dt}s)", e is not None, Lc.events[-3:])
u = get(f"/api/updates?session={cit}")
check("citizen hears: accepted", "accepted your request" in u["say"], u["say"])
r = say(off, "ask the citizen which street the problem is on")
e, dt = Lc.wait(lambda e: e.get("type") == "case" and e.get("id") == cid and e.get("change") == "info" and e.get("mine"))
check(f"citizen told of the question live ({dt}s)", e is not None, Lc.events[-3:])
u = get(f"/api/updates?session={cit}")
check("citizen hears the question", "which street" in u["say"].lower() and "Say your reply" in u["say"], u["say"])
r = say(cit, "it is the main road near the temple")
check("citizen reply goes into the file", r["intent"] in ("reply", "chat_text") and "Sent to" in r["say"], r["say"])
e, dt = Lo.wait(lambda e: e.get("type") == "case" and e.get("id") == cid and e.get("change") == "citizen_reply")
check(f"officer screen told of the reply live ({dt}s)", e is not None, Lo.events[-3:])
r = say(off, "resolve: inspected the site on 15 October, the broken pipeline was repaired and water supply was restored to all houses")
check("resolved with AI score", "Resolved" in r["say"] or "scored" in r["say"], r["say"])
e, dt = Lc.wait(lambda e: e.get("type") == "case" and e.get("id") == cid and e.get("change") == "resolved" and e.get("mine"))
check(f"citizen told of the resolution live ({dt}s)", e is not None, Lc.events[-3:])
u = get(f"/api/updates?session={cit}")
check("citizen hears resolved + asked for feedback", "resolved" in u["say"] and "Say yes or no" in u["say"], u["say"])
r = say(cit, "no, it is still not fixed")
check("feedback no re-opens and moves it up the ladder", r["intent"] == "feedback_no" and "re-opened" in r["say"] and "up the ladder" in r["say"], r["say"])
e, dt = Lo.wait(lambda e: e.get("type") == "case" and e.get("id") == cid and e.get("change") == "reopened")
check(f"officer told of the re-open live ({dt}s)", e is not None, Lo.events[-3:])

print("[chief secretary nudges]")
r = say(cs, f"open {cid}")
t_nudge = time.time()
r = say(cs, "nudge this officer")
check("nudge sent", r["intent"] == "nudge" and "Reminder sent" in r["say"], r["say"])
e, dt = Lo.wait(lambda e: e.get("type") == "case" and e.get("id") == cid and e.get("change") == "nudge")
check(f"officer screen told of the nudge live ({dt}s)", e is not None, Lo.events[-3:])
import urllib.request
now_with = json.loads(urllib.request.urlopen(f"http://localhost:8020/api/case/{cid}", timeout=20).read())["owner"]   # the senior since the citizen's "no"
e, t1 = None, time.time()                                     # it arrives with the nudge event: look at everything since the nudge
while e is None and time.time() - t1 < 8:
    e = next((x for ts, x in list(Lo.events) if ts >= t_nudge and x.get("type") == "notif" and x.get("to") == now_with and "Chief Secretary" in x.get("m", "")), None)
    time.sleep(0.1)
check("officer notification arrives live", e is not None, Lo.events[-3:])

print("[other citizen paths]")
r = say(cit, "street light near the bus stand is not working")
check("asks for the place when none is named", "Which village or taluk" in r["say"], r["say"])
r = say(cit, "Piriyapatna")
check("taluk -> asks for the GP with examples", "Gram Panchayat" in r["say"] and "For example" in r["say"], r["say"])
r = say(cit, "Attigodu")
check("GP -> confirm with officer", "Shall I file it" in r["say"] and "PDO" in r["say"], r["say"])
r = say(cit, "change")
check("change clears the draft", r["intent"] == "change", r["say"])
r = say(cit, "I need a caste certificate")
check("service request offered", r["intent"] in ("chat_text", "apply_service") and "application" in r["say"].lower(), r["say"])
r = say(cit, "yes, apply now")
check("asks the applicant's name", "name" in r["say"].lower(), r["say"])
r = say(cit, "Lakshmi K")
check("asks the village", "village" in r["say"].lower(), r["say"])
r = say(cit, "Komalapura")
check("Sakala application registered with a legal deadline", ("Sakala number is SK-" in r["say"] or "application ending in" in r["say"]) and "guaranteed by" in r["say"], r["say"])
r = say(cit, "track my request")
check("track lists both", r["intent"] == "track" and cid in r["say"] and ("SK-" in r["say"] or "ending in" in r["say"]), r["say"])
import base64, io
try:
    from PIL import Image
    img = Image.new("RGB", (500, 300), (110, 150, 190)); buf = io.BytesIO(); img.save(buf, "PNG")
    p = post("/api/photo", {"session": cit, "image_b64": base64.b64encode(buf.getvalue()).decode(), "media_type": "image/png"})
    check("blank photo refused, never guessed", "does not look like a readable" in p["say"], p["say"])
except ImportError:
    print("    (PIL missing, photo test skipped)")
import urllib.request
holder = json.loads(urllib.request.urlopen(f"http://localhost:8020/api/case/{cid}", timeout=20).read())["owner"]   # the senior, after the citizen's "no"
off2 = post("/api/session", {"profile": "officer", "officer": holder, "lang": "en"})["session"]
say(off2, f"open {cid}")
r = say(off2, "reject it as a duplicate of an existing request")
r = say(cit, "any update from the officer?")
check("rejection heard with appeal right", "could not accept" in r["say"] and "appeal" in r["say"].lower(), r["say"])
r = say(cit, "appeal")
check("appeal moves the case up", r["intent"] == "appeal" and "sent to" in r["say"], r["say"])
# guardrail 9: a different citizen session never sees this case
other = post("/api/session", {"profile": "citizen", "officer": "tah_piriyapatna", "lang": "en"})["session"]
r = say(other, "track my request")
check("another citizen screen cannot see the case", cid not in r["say"], r["say"])

for L in (Lc, Lo, Lcs):
    L.stop = True
print(f"\n{ok}/{len(T)} checks passed")
sys.exit(0 if ok == len(T) else 1)
