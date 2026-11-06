"""The big battery: ~150 utterances a real crowd would say to Mitra, across the three profiles, including junk, "chumma"
grievances, mind changes, wrong-profile commands, unknown ids and places, and data questions. Each has an expected outcome.
Runs through /api/turn (the cascade path: Gemini text brain -> the same tools, routing and pipeline the live session uses).
Run from mitra/: python tests/battery.py [base]   (default http://localhost:8030)"""
import json
import re
import sys
import time
import urllib.request

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8030"
ok = fail = 0
FAILS = []


def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=180).read())


def sess(profile, officer=""):
    return post("/api/session", {"profile": profile, "officer": officer, "lang": "en"})["session"]


def say(sid, text):
    return post("/api/turn", {"session": sid, "text": text, "want_audio": False})


def ops(r):
    return [u.get("op") for u in r.get("ui", [])]


def filed(r):
    return "routed" in ops(r) or bool(re.search(r"\b(Registered|Application accepted)\b", r.get("say", "")))


# expectation helpers -------------------------------------------------------
def no_file(r): return not filed(r) and bool(r.get("say"))
def asks_place(r): return bool(re.search(r"village|taluk|Gram Panchayat|location|which place", r["say"], re.I)) and not filed(r)
def intent(*names): return lambda r: r["intent"] in names
def says(*words): return lambda r: any(w.lower() in r["say"].lower() for w in words)
def has_op(op): return lambda r: op in ops(r)
def both(*fs): return lambda r: all(f(r) for f in fs)
def either(*fs): return lambda r: any(f(r) for f in fs)
def replied(r): return len(r.get("say", "")) > 8


def run(label, profile, steps, officer=""):
    """steps: [(utterance, expectation), ...] in one session."""
    global ok, fail
    sid = sess(profile, officer)
    for text, exp in steps:
        t0 = time.time()
        try:
            r = say(sid, text)
        except Exception as e:
            r = {"intent": "ERROR", "say": str(e), "ui": []}
        good = False
        try:
            good = bool(exp(r))
        except Exception:
            good = False
        if not good and "confirm" in ops(r):          # guardrail 17: the step expects the action done, so confirm the read-back
            r = say(sid, "yes")
            try:
                good = bool(exp(r))
            except Exception:
                good = False
        if good:
            ok += 1
        else:
            fail += 1
            FAILS.append((label, text, r.get("intent"), r.get("say", "")[:160], ops(r)))
        print(f"  {'PASS' if good else 'FAIL'} [{label}] {text[:60]!r} -> {r.get('intent')} ({time.time() - t0:.1f}s) :: {r.get('say', '')[:90]!r}")


# ===================================================================== citizen
JUNK = ["hello", "hello hello, testing one two", "just checking if this works", "nothing", "all good, thanks", "ok", "what's your name",
        "who made you", "tell me a joke", "asdf qwerty", "I love Karnataka", "is it going to rain today", "what is two plus two",
        "my neighbour's dog is very cute", "good morning", "thank you", "bye", "hmm", "are you a robot", "can you sing"]
import sqlite3
from pathlib import Path
_DB = Path(__file__).resolve().parents[2] / "app" / "data" / "sakala.db"


def mitra_cases():
    c = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
    return c.execute("SELECT COUNT(*) FROM cases WHERE src='mitra'").fetchone()[0]


before = mitra_cases()
for j in JUNK:
    run("junk", "citizen", [(j, no_file)])
after = mitra_cases()
if after == before:
    ok += 1; print(f"  PASS [junk] no case of any kind was filed for {len(JUNK)} junk utterances")
else:
    fail += 1; FAILS.append(("junk", "cases filed by junk", after - before, "", [])); print(f"  FAIL [junk] {after - before} cases were filed by junk")

PROBLEMS = [
    ("there is no drinking water in our village for a week", asks_place),
    ("the street light near the temple has not worked for ten days", asks_place),
    ("the road in front of the school is full of potholes", either(asks_place, replied)),
    ("the drain is overflowing onto the road", asks_place),
    ("my ration card has not come even after applying three months ago", either(asks_place, replied)),
    ("my old age pension has not been credited for three months", either(asks_place, replied)),
    ("there is a mistake in my RTC, the survey number is wrong", either(asks_place, replied)),
    ("MGNREGA wages for last month have not been paid", either(asks_place, replied)),
    ("I applied for a house under the housing scheme and nothing happened", either(asks_place, replied)),
    ("garbage has not been collected in our street", either(asks_place, replied)),
    ("there is a power cut every evening for hours", both(no_file, says("ESCOM", "electricity", "power", "Energy"))),
    ("I want to file an RTI application", both(no_file, replied)),
    ("the police are not registering my complaint", both(no_file, replied)),
    ("the KSRTC bus to our village has stopped coming", both(no_file, replied)),
]
for text, exp in PROBLEMS:
    run("problem", "citizen", [(text, exp)])

run("full filing · water in Gorahalli", "citizen", [
    ("there is no drinking water in Gorahalli for a week", either(says("Gorahalli", "Chapparadahalli"), asks_place)),
    ("yes, file it", either(lambda r: filed(r), says("which", "village"))),
])
run("full filing · taluk then GP", "citizen", [
    ("the street light near the bus stand is not working", asks_place),
    ("Piriyapatna", says("Gram Panchayat", "which")),
    ("Attigodu", says("Attigodu")),
    ("yes, file it", lambda r: filed(r) and "Attigodu" in r["say"]),
    ("track my request", either(says("GR-", "request"), intent("track"))),
])
run("mind change before filing", "citizen", [
    ("the road in our village is broken", asks_place),
    ("Hunsur", replied),
    ("no wait, change it", no_file),
])
run("cancel", "citizen", [("the drain near my house is blocked", asks_place), ("cancel, never mind", no_file)])
run("non-existent place", "citizen", [("the street light is not working", asks_place), ("Atlantis", both(no_file, replied))])
run("two problems at once", "citizen", [("no water and the street light is also broken in Attigodu", replied)])
run("place first", "citizen", [("I am from Bylakuppe", replied), ("the drinking water pipe is broken", replied)])
run("phone number is masked", "citizen", [("my number is 9876543210, the road near my house is broken in Attigodu", lambda r: "9876543210" not in r["say"])])
run("vulnerable citizen", "citizen", [("I am a widow and my pension has not come for three months", replied)])
run("long ramble", "citizen", [("so the thing is, every day since about two weeks my mother has to walk two kilometres to get water because the tap "
                                "in our street in Gorahalli stopped working after the pipe broke when they dug the road, and nobody came to fix it even "
                                "though we told the panchayat member twice, please do something", replied)])
run("abuse", "citizen", [("you are useless, nobody does anything", both(no_file, replied))])
run("track with nothing filed", "citizen", [("track my request", replied)])
run("updates with nothing filed", "citizen", [("any update from the officer?", replied)])
run("appeal with nothing rejected", "citizen", [("I want to appeal", both(no_file, replied))])
run("feedback with nothing resolved", "citizen", [("yes it is solved", both(no_file, replied))])
run("service request", "citizen", [("I want to apply for a caste certificate", either(says("apply", "name", "start", "application"), intent("apply_service")))])
run("wrong-profile command", "citizen", [("accept the case", both(no_file, replied))])
run("help", "citizen", [("what can you do?", replied)])
run("kannada switch", "citizen", [("speak in kannada", intent("set_language"))])

# ===================================================================== officer
O = "tah_piriyapatna"
run("officer basics", "officer", [
    ("read my inbox", both(intent("inbox"), has_op("inbox"))),
    ("open the first one", has_op("case")),
    ("read the details", replied),
    ("next case", has_op("case")),
], O)
run("officer without an open case", "officer", [("accept", replied), ("resolve it", replied)], O)
run("reject without reason asks for one", "officer", [("open the first one", has_op("case")), ("reject it", either(says("reason", "why"), replied))], O)
run("open unknown case", "officer", [("open GR-999999", says("could not find", "not find"))], O)
run("officer data questions", "officer", [
    ("which of my cases are overdue?", replied),
    ("how many cases do I have in Bettadapura?", replied),
    ("what is my most urgent case?", replied),
], O)
run("officer wrong-profile", "officer", [("I want to file a complaint about water", replied)], O)
run("officer switch to citizen", "officer", [("switch to citizen mode", intent("switch_profile"))], O)
run("login as another officer", "officer", [("log in as PDO Attigodu", either(intent("login_as"), says("Attigodu")))], O)

# ===================================================================== chief secretary
run("cs position", "cs", [("give me the position", replied), ("what about overdue cases?", replied)])
CSQ = [
    ("tell me about grievance 503063", says("503063", "Urban", "Mandya")),
    ("what is the status of GR-502706?", says("502706")),
    ("who is the officer on SK-RD855S260004811?", says("Tahsildar", "4811")),
    ("where is grievance 503063 located?", says("Mandya")),
    ("tell me about grievance 999999", says("could not find", "not find", "no record", "couldn't")),
    ("how many open cases are there in Mysuru district?", replied),
    ("which district has the most pending cases?", replied),
    ("which officer has the most overdue cases?", replied),
    ("how many grievances came through WhatsApp?", replied),
    ("show me the vulnerable cases", replied),
    ("how many Health department grievances were in the iPGRS sample?", replied),
    ("which district was worst in Sakala 2025?", says("Bengaluru")),
    ("tell me about PDO Attigodu", replied),
    ("what is Bylakuppe?", replied),
    ("compare Hunsur and Piriyapatna", replied),
    ("read the Wednesday pack", replied),
    ("who are the E-4 defaulters?", replied),
    ("nudge the Tahsildar of Piriyapatna, tell him the caste certificate is overdue and he must clear it today", says("Reminder sent", "reminded")),
    ("accept this case", replied),
    ("hello", replied),
]
for text, exp in CSQ:
    run("cs", "cs", [(text, exp)])

print(f"\n{ok}/{ok + fail} checks passed")
if FAILS:
    print("\nFAILURES:")
    for f in FAILS:
        print("  ", f)
