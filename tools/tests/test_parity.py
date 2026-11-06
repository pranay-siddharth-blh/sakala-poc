"""WhatsApp and Sakala Mitra run the same routing pipeline (19 Oct 2026).
1. The same complaints through WhatsApp (/api/chat) and through Mitra's door (/api/intake) reach the same service and officer.
2. A bare taluk typed at WhatsApp's "where is it?" is a place (GP list, or confirm for a taluk-level officer), never a new case.
3. Junk on WhatsApp is not filed: it is offered to the scrutiny desk and filed only on a yes.
4. The resolution loop on WhatsApp: "yes" closes the case, "no" re-opens it one rung up the ladder; a second tap changes nothing.
Run from app/ with the POC on 8020:  PYTHONIOENCODING=utf-8 python ../tools/tests/test_parity.py"""
import json
import urllib.request

B = "http://localhost:8020"
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:300])


def post(p, b):
    return json.loads(urllib.request.urlopen(urllib.request.Request(B + p, json.dumps(b).encode(), {"Content-Type": "application/json"}), timeout=120).read())


def get(p):
    return json.loads(urllib.request.urlopen(B + p, timeout=120).read())


def chat(s, **kw):
    return post("/api/chat", {"session": s, **kw})


def text_of(r):
    return " ".join((e.get("html") or "") for e in r["events"] if e.get("kind") == "msg")


def actions(r):
    return [b["action"] for e in r["events"] if e.get("kind") == "msg" for b in (e.get("buttons") or [])]


def wa_session():
    s = post("/api/chat", {"action": "start"})["session"]
    chat(s, action="lang:en")
    return s


def wa_file(text):
    """File through WhatsApp, answering the completion step the simplest way; returns (case id, officer id)."""
    s = wa_session()
    r = chat(s, text=text)
    for _ in range(3):
        if "submit" in actions(r):
            r = chat(s, action="submit")
            break
        gp = next((a for a in actions(r) + [row["action"] for e in r["events"] for row in ((e.get("list") or {}).get("rows") or [])] if a.startswith("gp:")), None)
        r = chat(s, action=gp) if gp else chat(s, text="Attigodu")
    res = next((e for e in r["events"] if e.get("kind") == "result"), None)
    return s, (res or {}).get("caseId"), ((res or {}).get("officer") or {}).get("id")


def mitra_route(text):
    """Mitra's door: understand + place, the officer preview it would file with."""
    sess = "parity-" + text[:12].replace(" ", "")
    r = post("/api/intake", {"session": sess, "step": "understand", "text": text})
    if "preview" not in r and r.get("need") == "gp":
        r = post("/api/intake", {"session": sess, "step": "place", "text": "Attigodu", "u": r["u"], "taluk": r.get("taluk", "")})
    elif "preview" not in r:
        r = post("/api/intake", {"session": sess, "step": "place", "text": "Attigodu", "u": r["u"]})
    return r["u"].get("service_id"), ((r.get("preview") or {}).get("officer") or {}).get("id")


print("[1. same complaint, same officer on both channels]")
for t in ("The street light near the bus stand in Attigodu is not working",
          "There is no drinking water in Attigodu for three days",
          "The road in Hunsur is full of potholes"):
    s, cid, wa_off = wa_file(t)
    svc, mi_off = mitra_route(t)
    c = get(f"/api/case/{cid}") if cid else {}
    check(f"'{t[:40]}…' WhatsApp → {wa_off} · Mitra → {mi_off}", cid and wa_off and wa_off == mi_off, (cid, wa_off, mi_off))

print("[2. a bare taluk at the location question is a place]")
s = wa_session()
r = chat(s, text="the street light is not working")
check("asks where", "Where is this problem" in text_of(r), text_of(r)[:160])
r = chat(s, text="Hunsur")
rows = [row["action"] for e in r["events"] for row in ((e.get("list") or {}).get("rows") or [])]
check("'Hunsur' → the Gram Panchayats of Hunsur (not a new complaint)", any(a.startswith("gp:") and a.endswith("|Hunsur") for a in rows)
      and not any(e.get("kind") == "stage" and e.get("i") == 0 for e in r["events"]), (rows[:3], text_of(r)[:120]))
s = wa_session()
chat(s, text="the road to our village is broken and full of potholes")
r = chat(s, text="Hunsur")
check("road (taluk-level officer) + 'Hunsur' → straight to confirm", "submit" in actions(r), (actions(r), text_of(r)[:160]))
s = wa_session()
chat(s, text="the street light is not working")
r = chat(s, text="xyzzy")
check("an unknown short answer asks again, nothing filed", "could not find" in text_of(r) and not any(e.get("kind") == "result" for e in r["events"]), text_of(r)[:160])

print("[3. junk on WhatsApp is not filed]")
s = wa_session()
before = len(get(f"/api/state?session={s}&scope=citizen")["cases"])
r = chat(s, text="asdf qwerty blah")
after = len(get(f"/api/state?session={s}&scope=citizen")["cases"])
check("unclear text: asks before the scrutiny desk, nothing filed", "scrutiny:yes" in actions(r) and after == before, (actions(r), before, after))
r = chat(s, action="scrutiny:yes")
mine = get(f"/api/state?session={s}&scope=citizen")["cases"]
check("on a yes it goes to the scrutiny desk", len(mine) == before + 1 and mine[-1]["status"] == "Scrutiny", [(c["id"], c["status"]) for c in mine])

print("[4. resolution loop on WhatsApp]")
s, cid, own = wa_file("The street light near the bus stand in Attigodu is not working")
atr = "Inspected on 19 October; the street light near the bus stand was repaired with a new fixture and checked at night."
post(f"/api/cases/{cid}/action", {"action": "resolve", "officer": own, "atr": atr})
chat(s, action="poll")
r = chat(s, action=f"fb:{cid}:yes")
c = get(f"/api/case/{cid}")
check("yes → closed, confirmation on the file, owner unchanged", c["status"] == "Resolved" and c["owner"] == own and "closed" in text_of(r), (c["status"], text_of(r)[:120]))
r = chat(s, action=f"fb:{cid}:no")
c = get(f"/api/case/{cid}")
check("a late 'no' after a 'yes' changes nothing", c["status"] == "Resolved" and "not waiting" in text_of(r), (c["status"], text_of(r)[:120]))
s, cid, own = wa_file("There is no drinking water in Attigodu for three days")
post(f"/api/cases/{cid}/action", {"action": "resolve", "officer": own, "atr": atr.replace("street light", "pipeline")})
r = chat(s, action="track")
check("Track in the chat asks for the verdict on the resolved request", f"fb:{cid}:no" in actions(r) and "wa-lad" in json.dumps(r), actions(r))
r = chat(s, action=f"fb:{cid}:no")
c = get(f"/api/case/{cid}")
check("no → re-opened, one rung up (L1 → L2), clock restarted", c["status"] == "Pending" and c["owner"] != own and c["level"] == "L2", (c["status"], c["owner"], c["level"]))
r2 = chat(s, action=f"fb:{cid}:no")
c2 = get(f"/api/case/{cid}")
check("a second 'no' does not climb again", c2["owner"] == c["owner"] and c2["level"] == "L2", (c2["owner"], c2["level"]))

print(f"\n{ok} passed, {fail} failed")
