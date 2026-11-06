"""Regression for 16 Oct: a citizen screen stuck in 'reply to the officer' for a case that is not theirs (left over from the
officer / CS screen of the same Mitra session) answered every new complaint with "I could not send that reply". Also:
navigation must never swallow a citizen's answer. Runs against a Mitra test instance through the cascade with the
function names Live uses (`chat_text`, `go_to`) by calling /api/turn with typed text, and by injecting the stale state.
Usage: python tests/test_citizen_regress.py [base]   (default http://localhost:8031)"""
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8031"
DB = Path(__file__).resolve().parent.parent / "data" / "mitra.db"
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:300])


def post(p, d):
    req = urllib.request.Request(B + p, json.dumps(d).encode(), {"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def poison(sid, case_id):
    c = sqlite3.connect(DB)
    st = json.loads(c.execute("SELECT state FROM sessions WHERE id=?", (sid,)).fetchone()[0] or "{}")
    st.update({"flow": "reply", "reply_case": case_id, "case_id": case_id})
    c.execute("UPDATE sessions SET state=? WHERE id=?", (json.dumps(st), sid)); c.commit(); c.close()


# a case that belongs to somebody else
other = post("/api/session", {"profile": "citizen"})
r = post("/api/turn", {"session": other["session"], "text": "the hand pump in Gorahalli is broken"})
for t in ["yes, file it", "yes"]:
    if "file it" in r["say"].lower() or "shall i" in r["say"].lower():
        r = post("/api/turn", {"session": other["session"], "text": t})
foreign = next((u.get("caseId") for u in r.get("ui", []) if u.get("op") == "routed"), None) or "GR-504211"
print("foreign case:", foreign)

print("[stuck reply flow from another screen]")
s = post("/api/session", {"profile": "citizen"})
sid = s["session"]
poison(sid, foreign)
for text, want in [("my father's old age pension has been delayed for three months", "Old-Age"),
                   ("there is no drinking water in Gorahalli", "Water")]:
    r = post("/api/turn", {"session": sid, "text": text})
    check(f"'{text[:40]}…' is understood as a new request, not a failed reply",
          "could not send" not in r["say"].lower() and (want.lower() in r["say"].lower() or "village" in r["say"].lower() or "file it" in r["say"].lower()), (r["intent"], r["say"][:160]))
    poison(sid, foreign)

print("[a real reply still works]")
s2 = post("/api/session", {"profile": "citizen"})
r = post("/api/turn", {"session": s2["session"], "text": "the street light in Chapparadahalli is not working"})
for _ in range(3):
    if "file it" in r["say"].lower() or "shall i" in r["say"].lower():
        r = post("/api/turn", {"session": s2["session"], "text": "yes"})
mine = next((u.get("caseId") for u in r.get("ui", []) if u.get("op") == "routed"), None)
check("filed", bool(mine), r["say"][:160])
if mine:
    c = sqlite3.connect(DB)
    st = json.loads(c.execute("SELECT state FROM sessions WHERE id=?", (s2["session"],)).fetchone()[0])
    st.update({"flow": "reply", "reply_case": mine}); c.execute("UPDATE sessions SET state=? WHERE id=?", (json.dumps(st), s2["session"])); c.commit(); c.close()
    r = post("/api/turn", {"session": s2["session"], "text": "the pole is next to the temple"})
    check("a reply on their own request reaches the officer", "Sent to" in r["say"], (r["intent"], r["say"][:160]))

print("[navigation never swallows an answer]")
s3 = post("/api/session", {"profile": "citizen"})
post("/api/turn", {"session": s3["session"], "text": "the street light near my house is not working"})
from importlib import import_module  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import asyncio  # noqa: E402
tools = import_module("server.tools"); store = import_module("server.store")


async def nav_checks():
    a = await tools.t_go_to(store.get_session(s3["session"]), {"target": "dashboard", "_text": "Okay, the location was Hunsur."})
    b = await tools.t_go_to(store.get_session(s3["session"]), {"target": "dashboard", "_text": "take me back to the main screen"})
    return a, b


res, res2 = asyncio.run(nav_checks())
check("go_to called on 'the location was Hunsur' files the place instead of navigating", "main screen" not in res.get("say", "").lower() and ("Hunsur" in res.get("say", "") or "Gram Panchayat" in res.get("say", "")), res.get("say", "")[:160])
check("go_to on 'take me back to the main screen' still navigates", "main screen" in res2.get("say", "").lower(), res2.get("say", ""))
print(f"\n{ok} passed, {fail} failed")
