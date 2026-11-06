"""Return with a suggestion (22 Oct 2026, Pranay), against the live POC on 8020 and Mitra's test instance on 8031.
An officer returns a case as not their jurisdiction:
  - with an officer, a place, or both  -> straight to that officer (owner, level, Pending, fresh clock, place updated),
    the officer is notified, the citizen is told who has it now, the case file explains the decision;
  - with nothing, or a suggestion that matches no officer, or one that points back to themselves -> the scrutiny desk;
  - a Sakala application never moves this way (its own ladder); only the holder can return.
Then Mitra by voice (cascade on 8031): 'not my jurisdiction, send it to the Tahsildar of Hunsur' -> read-back names the
suggestion -> 'yes' -> transferred; 'return it, not my jurisdiction' -> scrutiny desk; the new holder's Mitra screen gets
'Transferred to you'. Run from app/: PYTHONIOENCODING=utf-8 python ../tools/tests/test_return_suggest.py"""
import json
import re
import sys
import time
import urllib.error
import urllib.request

POC, MITRA = "http://localhost:8020", "http://localhost:8031"
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:400])


def call(base, path, body=None):
    r = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                               headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(r, timeout=120).read())
    except urllib.error.HTTPError as e:
        body = e.read() or b"{}"
        try:
            return {"http": e.code, "detail": json.loads(body).get("detail")}
        except ValueError:
            return {"http": e.code, "detail": body[:200].decode(errors="replace")}


sys.path.insert(0, ".")
from server import db  # noqa: E402


def fresh(owner_like, kind="GRIEVANCE"):
    """An open case on that desk not used by an earlier step."""
    # cases that really sit in Piriyapatna: the real data has a few Tahsildar Piriyapatna cases located elsewhere (e.g. Gadag)
    r = db.q1("SELECT * FROM cases WHERE owner LIKE ? AND status='Pending' AND kind=? AND taluk='Piriyapatna' AND id NOT IN (%s) ORDER BY id DESC LIMIT 1"
              % ",".join("?" * max(1, len(USED))), (owner_like, kind, *(USED or [""])))
    USED.append(r["id"]); return dict(r)


def case(cid):
    return dict(db.q1("SELECT * FROM cases WHERE id=?", (cid,)))


def last_event(cid):
    return dict(db.q1("SELECT * FROM case_events WHERE case_id=? ORDER BY id DESC LIMIT 1", (cid,)))


def notif(oid, cid):
    return db.q1("SELECT * FROM notifications WHERE officer_id=? AND msg LIKE ? ORDER BY id DESC LIMIT 1", (oid, f"%{cid}%"))


USED: list[str] = []
print("[POC: return with a suggestion]")
for label, owner, to, place, want in [
    ("officer named: 'Tahsildar Hunsur'", "tah_piriyapatna", "Tahsildar Hunsur", "", "tah_hunsur"),
    ("place only: 'Hunsur' (same service, routing rule)", "tah_piriyapatna", "", "Hunsur", "tah_hunsur"),
    ("both: 'PDO' + 'Attigodu'", "pdo_piriyapatna_h%", "PDO", "Attigodu", "pdo_piriyapatna_attigodu"),
    ("role only: 'the AC' (the case's own ladder)", "tah_piriyapatna", "the AC", "", "ac_hunsur"),
    ("place in Kannada: 'ಹುಣಸೂರು' for a Tahsildar case", "tah_piriyapatna", "", "ಹುಣಸೂರು", "tah_hunsur"),
]:
    c = fresh(owner)
    t0 = time.time()
    r = call(POC, f"/api/cases/{c['id']}/action", {"action": "return", "officer": c["owner"], "reason": "Location is outside my jurisdiction", "to": to, "place": place})
    after = case(c["id"])
    ev = last_event(c["id"])
    tgt = (r.get("routed_to") or {}).get("id")
    check(f"{label}: {c['id']} -> {tgt} ({time.time() - t0:.1f} s)", tgt == want and after["owner"] == want and after["status"] == "Pending", r)
    check(f"{label}: level / fresh clock (now on the demo clock) / basis / case-file event", after["level"] == (r.get("routed_to") or {}).get("level") and after["level_since"][:16] == ev["t"][:16]
          and "Transferred by" in (after["route_basis"] or "") and ev["what"].startswith("Transferred to") and "suggested" in ev["note"], (after["level"], after["level_since"], ev))
    check(f"{label}: the new holder is notified", bool(notif(want, c["id"])))
    if c["session"]:
        m = db.q1("SELECT * FROM citizen_msgs WHERE case_id=? ORDER BY id DESC LIMIT 1", (c["id"],))
        check(f"{label}: the citizen is told who has it now", m and m["kind"] == "transferred" and m["officer_id"] == want, m and dict(m))
    if place == "Hunsur":
        check(f"{label}: the case's place follows (taluk Hunsur)", after["taluk"] == "Hunsur", after["taluk"])

print("[POC: no usable suggestion -> scrutiny desk]")
for label, to, place in [("nothing given", "", ""), ("a name that matches no officer", "someone in the other office", ""),
                         ("a place that does not exist", "", "xyzzy nowhere"), ("points back to the same officer", "Tahsildar Piriyapatna", "")]:
    c = fresh("tah_piriyapatna")
    r = call(POC, f"/api/cases/{c['id']}/action", {"action": "return", "officer": c["owner"], "reason": "Location is outside my jurisdiction", "to": to, "place": place})
    after = case(c["id"])
    check(f"{label}: {c['id']} -> scrutiny desk", r.get("scrutiny") and after["status"] == "Scrutiny" and not r.get("routed_to"), r)
    if to or place:
        check(f"{label}: the unmatched suggestion is recorded in the case file", (to or place) in last_event(c["id"])["note"], last_event(c["id"]))

print("[POC: guardrails]")
c = fresh("tah_piriyapatna")
r = call(POC, f"/api/cases/{c['id']}/action", {"action": "return", "officer": "tah_hunsur", "to": "Tahsildar Mysuru"})
check("only the officer who holds it can return it (403)", r.get("http") == 403, r)
app = db.q1("SELECT * FROM cases WHERE kind='APPLICATION' AND status IN ('Pending','In progress') LIMIT 1")
if app:
    r = call(POC, f"/api/cases/{app['id']}/action", {"action": "return", "officer": app["owner"], "to": "Tahsildar Hunsur"})
    check("a Sakala application is never transferred by a suggestion (its own ladder) -> scrutiny", not r.get("routed_to") and case(app["id"])["owner"] == app["owner"], r)

print("[Mitra by voice, cascade on 8031]")
c = fresh("tah_piriyapatna")
sid = call(MITRA, "/api/session", {"profile": "officer", "officer": "tah_piriyapatna", "lang": "en"})["session"]
r = call(MITRA, "/api/turn", {"session": sid, "text": f"open {c['id']}", "want_audio": False})
r = call(MITRA, "/api/turn", {"session": sid, "text": "not my jurisdiction, send it to the Tahsildar of Hunsur", "want_audio": False})
check("read-back names the suggestion and waits", re.search(r"Tahsildar (of )?Hunsur", r["say"]) and "Shall I go ahead" in r["say"] and case(c["id"])["owner"] == "tah_piriyapatna", r["say"])
r = call(MITRA, "/api/turn", {"session": sid, "text": "yes", "want_audio": False})
check("'yes' -> transferred to Tahsildar Hunsur, Mitra says who holds it and that they were notified",
      case(c["id"])["owner"] == "tah_hunsur" and "Tahsildar Hunsur" in r["say"] and "notified" in r["say"], r["say"])
check("the case-file event says it came through Mitra by voice, with the sentence", "via Mitra (voice)" in last_event(c["id"])["note"], last_event(c["id"]))
c2 = fresh("tah_piriyapatna")
call(MITRA, "/api/turn", {"session": sid, "text": f"open {c2['id']}", "want_audio": False})
call(MITRA, "/api/turn", {"session": sid, "text": "return it, not my jurisdiction", "want_audio": False})
r = call(MITRA, "/api/turn", {"session": sid, "text": "yes", "want_audio": False})
check("'return it, not my jurisdiction' (nothing suggested) -> scrutiny desk, and Mitra offers to name an officer next time",
      case(c2["id"])["status"] == "Scrutiny" and "scrutiny desk" in r["say"], r["say"])
c3 = fresh("tah_piriyapatna")
call(MITRA, "/api/turn", {"session": sid, "text": f"open {c3['id']}", "want_audio": False})
call(MITRA, "/api/turn", {"session": sid, "text": "this belongs to Hunsur taluk", "want_audio": False})
r = call(MITRA, "/api/turn", {"session": sid, "text": "yes go ahead", "want_audio": False})
check("'this belongs to Hunsur taluk' (a place only) -> the Hunsur officer for that service", case(c3["id"])["owner"] == "tah_hunsur", (case(c3["id"])["owner"], r["say"]))

print("[the new holder's notification card]")
import subprocess  # noqa: E402  (Mitra's own classifier, run in its folder: both projects name their package 'server')
what = last_event(c["id"])["what"]
out = subprocess.run([sys.executable, "-c", f"from server import sync; print(sync.classify({what!r}))"], cwd="../mitra", capture_output=True, text=True).stdout.strip()
check("the event classifies as an assignment for the new holder (their 'Transferred to you' card)", out == "rerouted", (what, out))

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
