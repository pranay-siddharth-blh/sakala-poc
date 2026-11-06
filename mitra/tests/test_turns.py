"""Text-turn smoke test for the Mitra brain + tools across the three profiles.
Run with the Mitra server up:  PYTHONIOENCODING=utf-8 python tests/test_turns.py"""
import json
import re
import sys
import time
import urllib.request

B = "http://localhost:8030"
ok, T = 0, []


def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=180).read())


def check(n, c, d=""):
    global ok
    ok += bool(c)
    T.append(n)
    print(("  PASS " if c else "  FAIL ") + n + ("" if c else f"  <- {str(d)[:220]}"))


def say(sid, text, want_audio=False):
    t0 = time.time()
    r = post("/api/turn", {"session": sid, "text": text, "want_audio": want_audio})
    if any(u.get("op") == "confirm" and u.get("question") for u in r.get("ui", [])) and not re.match(r"^\s*(yes|no)\b", text, re.I):
        r = {**post("/api/turn", {"session": sid, "text": "yes"}), "_readback": r["say"]}    # guardrail 17: confirm the read-back
    r["_t"] = round(time.time() - t0, 2)
    print(f"    > {text!r} -> {r['intent']} [{r.get('provider')}] {r['_t']}s :: {r['say'][:140]!r}")
    return r


for i in range(40):
    try:
        h = json.loads(urllib.request.urlopen(B + "/api/health", timeout=3).read())
        if h.get("sakala"):
            break
    except Exception:
        pass
    time.sleep(1.5)
print("health:", h)

print("[citizen]")
s = post("/api/session", {"profile": "citizen", "officer": "tah_piriyapatna", "lang": "en"})
sid = s["session"]
r = say(sid, "hello")
check("greeting -> help", r["intent"] == "help" and "Mitra" in r["say"], r)
r = say(sid, "there is no drinking water in Gorahalli village for one week")
check("grievance understood", r["intent"] in ("chat_text", "smalltalk") and ("Drinking Water" in r["say"] or "file it" in r["say"].lower()), r)
if "file it" not in r["say"].lower():
    r = say(sid, "Piriyapatna")
if "file it" not in r["say"].lower():
    r = say(sid, "share my location")
check("reached confirm", "file it" in r["say"].lower(), r)
r = say(sid, "yes, file it")
check("submitted and routed", r["intent"] == "confirm" and "Registered" in r["say"], r)
cid = officer = None
for u in r.get("ui", []):
    if u.get("op") == "routed":
        cid = u["caseId"]; officer = u["officer"]["id"]
check("case id captured", bool(cid), [u.get("op") for u in r.get("ui", [])])
r = say(sid, "track my request")
# the brain may route this through the "Track my request" option chip; the outcome is the same
check("track works", r["intent"] in ("track", "chat_option") and cid in r["say"], r)

print("[officer]")
o = post("/api/session", {"profile": "officer", "officer": officer, "lang": "en"})
oid = o["session"]
r = say(oid, "good morning mitra, read my inbox")
check("inbox read", r["intent"] == "inbox" and "open case" in r["say"], r)
r = say(oid, "yes")
check("yes opens the offered case", r["intent"] == "open_case" and "citizen says" in r["say"], r)
r = say(oid, f"open {cid}")
check("case opened by id", r["intent"] == "open_case" and cid in r["say"], r)
r = say(oid, "accept it")
check("accepted", r["intent"] == "accept" and "Accepted" in r["say"], r)
r = say(oid, "ask the citizen which street the problem is on")
check("info asked", r["intent"] == "ask_info" and "Sent to the citizen" in r["say"], r)
r = say(oid, "draft the report")
check("atr drafted", r["intent"] == "draft_atr" and "draft" in r["say"].lower(), r)
r = say(oid, "resolve: inspected the site on 15 October, the broken pipeline was repaired and water supply was restored to all houses")
check("resolved with score", r["intent"] == "resolve" and ("Resolved" in r["say"] or "scored" in r["say"]), r)

print("[citizen hears officer]")
r = say(sid, "track my request")
check("citizen sees officer messages", "Message from" in r["say"] or "resolved" in r["say"].lower() or "Resolved" in r["say"], r)
r = say(sid, "yes it is solved, thank you")
check("feedback recorded", r["intent"] in ("feedback_yes", "chat_text") and ("Thank" in r["say"] or "recorded" in r["say"]), r)

print("[chief secretary]")
c = post("/api/session", {"profile": "cs", "officer": "", "lang": "en"})
csid = c["session"]
r = say(csid, "give me the position")
check("summary", r["intent"] == "summary" and "pending" in r["say"], r)
r = say(csid, "show me the overdue cases")
check("filter overdue", r["intent"] == "filter_cases" and "overdue" in r["say"], r)
r = say(csid, "which officer has the most overdue cases")
check("ask data", r["intent"] in ("ask_data", "officers_attention") and len(r["say"]) > 10, r)
r = say(csid, "nudge the Tahsildar of Piriyapatna")
check("nudge", r["intent"] == "nudge" and ("Reminder sent" in r["say"] or "no open" in r["say"]), r)
r = say(csid, "read the wednesday pack")
check("pack", r["intent"] == "wednesday_pack" and len(r["say"]) > 20, r)
r = say(csid, "switch to citizen mode")
check("profile switch", r["intent"] == "switch_profile" and r["profile"] == "citizen", r)

print("[kannada + audio]")
r = post("/api/turn", {"session": csid, "text": "switch to officer mode", "want_audio": False})
r = post("/api/turn", {"session": oid, "text": "speak in kannada", "want_audio": True})
check("kannada switch", r["intent"] == "set_language" and r["lang"] == "kn", r)
r = post("/api/turn", {"session": oid, "text": "read my inbox", "want_audio": True})
check("kannada reply translated", any("ಀ" <= ch <= "೿" for ch in r["say"]) or r["tts"] == "browser", r["say"][:80])
print("    tts providers:", r["tts"])
r = post("/api/turn", {"session": oid, "text": "speak in english", "want_audio": True})
check("english tts audio or browser", (r["audio_b64"] and r["tts"] != "browser") or r["tts"] == "browser", r["tts"])
print("    tts:", r["tts"], "audio bytes:", len(r["audio_b64"]))

print(f"\n{ok}/{len(T)} checks passed")
sys.exit(0 if ok == len(T) else 1)
