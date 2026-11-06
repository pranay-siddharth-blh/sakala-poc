"""Notifications end to end (needs the POC on 8020 and Mitra on 8030).

A citizen files by voice-text -> the routed officer's screen gets a "Just in" card + shelf entry (also when the
officer screen is opened only afterwards) -> the officer's actions reach the citizen as cards -> the Chief
Secretary's nudge reaches the officer with her own words -> re-open reaches the officer -> nothing leaks to another
citizen -> live cards arrive over SSE to the right screen only -> seen-cursors stop repeats.
Run from mitra/: python tests/test_notify.py"""
import json
import re
import threading
import time
import urllib.request

B = "http://localhost:8030"
ok = fail = 0


def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=180).read())


def get(p):
    return json.loads(urllib.request.urlopen(B + p, timeout=60).read())


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:300])


def say(sid, text):
    r = post("/api/turn", {"session": sid, "text": text, "want_audio": False})
    if any(u.get("op") == "confirm" and u.get("question") for u in r.get("ui", [])) and not re.match(r"^\s*(yes|no)\b", text, re.I):
        r = {**post("/api/turn", {"session": sid, "text": "yes", "want_audio": False}), "_readback": r["say"]}    # guardrail 17
    print(f"    > {text!r} -> {r['intent']} :: {r['say'][:110]!r}")
    return r


def session(profile, officer=""):
    return post("/api/session", {"profile": profile, "officer": officer, "lang": "en"})["session"]


def pend(sid, change=None, cid=None):
    r = get(f"/api/notifs?session={sid}")
    cards = [c for c in r["pending"] if (change is None or c["change"] == change) and (cid is None or c["case_id"] == cid)]
    return r, cards


def wait_card(sid, change, cid, secs=6.0):
    t0 = time.time()
    while time.time() - t0 < secs:
        r, cards = pend(sid, change, cid)
        if cards:
            return r, cards
        time.sleep(0.5)
    return r, []


class Listener(threading.Thread):
    """Reads one screen's SSE stream and keeps the notification cards it receives."""
    def __init__(self, sid):
        super().__init__(daemon=True); self.sid, self.cards = sid, []

    def run(self):
        try:
            with urllib.request.urlopen(f"{B}/api/events?session={self.sid}", timeout=120) as r:
                for line in r:
                    line = line.decode("utf-8", "replace").strip()
                    if line.startswith("data: "):
                        e = json.loads(line[6:])
                        if e.get("type") == "notify":
                            self.cards.append(e["card"])
        except Exception:
            pass

    def wait(self, change, cid, secs=6.0):
        t0 = time.time()
        while time.time() - t0 < secs:
            for c in self.cards:
                if c["change"] == change and c["case_id"] == cid:
                    return c
            time.sleep(0.2)
        return None


print("[citizen files]")
cit = session("citizen")
say(cit, "street light near the bus stand is not working")
say(cit, "Piriyapatna")
say(cit, "Attigodu")
r = say(cit, "yes, file it")
routed = next((u for u in r.get("ui", []) if u.get("op") == "routed"), None)
cid = routed and routed.get("caseId")
check("case filed and routed", bool(cid), r.get("ui"))
time.sleep(1.6)
_, mine = pend(cit, "new", cid)
check("citizen gets a 'Filed' card", bool(mine) and mine[0]["title"].startswith("Filed"), mine)
owner = mine[0]["owner"] if mine else ""
check("Filed card offers 'View as the officer'", bool(mine) and any(a.get("as_officer") == owner for a in mine[0]["actions"]), mine)

print("[the officer opens their screen afterwards]")
off = session("officer", owner)
r, cards = pend(off, "new", cid)
check("officer gets a 'Just in' card for it", bool(cards) and cards[0]["title"].startswith("Just in"), r["pending"])
check("Just-in shelf lists it at the top", bool(r["just_in"]) and r["just_in"][0]["case_id"] == cid, r["just_in"])
check("shelf time is real time ('just now' / minutes)", bool(r["just_in"]) and ("just now" in r["just_in"][0]["ago"] or "min" in r["just_in"][0]["ago"]), r["just_in"])
post("/api/notifs/seen", {"session": off})
_, again = pend(off, "new", cid)
check("seen cursor: it does not pop twice", not again, again)
r2 = get(f"/api/notifs?session={off}")
check("shelf stays after it was seen (it is about recency, not unread)", any(j["case_id"] == cid for j in r2["just_in"]), r2["just_in"])

print("[live cards over SSE]")
lc, lo = Listener(cit), Listener(off)
lc.start(); lo.start(); time.sleep(0.8)
say(off, f"open {cid}")
say(off, "accept")
c = lc.wait("accepted", cid)
check("citizen screen gets 'accepted' live", bool(c), lc.cards)
c2 = lo.wait("accepted", cid)
check("officer screen gets 'sent to the citizen' live", bool(c2) and c2["tone"] == "sent", lo.cards)
say(off, "ask the citizen which street the problem is on")
c = lc.wait("info", cid)
check("citizen gets the officer's question live", bool(c) and "street" in (c["body"] or "").lower(), c)
check("question card offers Reply", bool(c) and any(a.get("say") == "reply" for a in c["actions"]), c)

print("[chief secretary nudges with her own words]")
cs = session("cs")
lcs = Listener(cs); lcs.start(); time.sleep(0.6)
say(cs, f"open {cid}")
say(cs, "remind this officer, tell him only one day is left and he needs to get on top of this")
c = lo.wait("nudge", cid, 8)
check("officer gets the reminder live", bool(c), lo.cards)
check("reminder carries her message", bool(c) and "top of" in (c["body"] or "").lower(), c)
check("officer's spoken line carries it too", bool(c) and "top of" in (c.get("speak") or "").lower(), c)
d = lcs.wait("nudge", cid, 4)
check("CS sees 'Reminder delivered'", bool(d) and d["title"] == "Reminder delivered", lcs.cards)

print("[resolve -> citizen, re-open -> officer]")
say(off, "resolve: replaced the street light bulb near the bus stand and checked it works at night")
c = lc.wait("resolved", cid, 8)
check("citizen gets 'Resolved' with Solved / Not solved", bool(c) and len(c["actions"]) == 2, c)
say(cit, "no it is not solved")
t0, c = time.time(), None
while time.time() - t0 < 8 and not c:          # the resolver is told (a notification), the senior gets the case event
    c = next((x for x in lo.cards if x["case_id"] == cid and x["title"].startswith("Re-opened")), None); time.sleep(0.2)
check("the officer whose resolution was rejected gets 'Re-opened' live", bool(c) and c["tone"] == "bad", lo.cards)

print("[isolation]")
other = session("citizen")
r = get(f"/api/notifs?session={other}")
check("another citizen sees none of this case", not any(x["case_id"] == cid for x in r["pending"] + r["history"]), r["pending"][:3])
other_off = session("officer", "tah_hunsur")
r = get(f"/api/notifs?session={other_off}")
check("an unrelated officer sees none of it", not any(x["case_id"] == cid for x in r["pending"] + r["history"]), r["pending"][:3])
check("citizen got no officer-only cards", not any(x["change"] in ("nudge", "reopened") for x in lc.cards), [x["change"] for x in lc.cards])

print(f"\n{ok}/{ok + fail} checks passed")
