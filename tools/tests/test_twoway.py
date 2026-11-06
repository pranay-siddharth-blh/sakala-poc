"""Two-way WhatsApp: officer actions reach the citizen, citizen replies and feedback reach the officer."""
import json
import re
import urllib.request

B = "http://localhost:8020"


def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r).read())


def get(p):
    return json.loads(urllib.request.urlopen(B + p).read())


def msgs(r):
    return [(e["type"], e.get("officer", ""), re.sub("<[^>]+>", " ", e["html"]), [b["action"] for b in e.get("buttons") or []])
            for e in r["events"] if e["kind"] == "msg" and not e["me"]]


ok = 0
def check(name, cond, detail=""):
    global ok
    ok += bool(cond)
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else f"  ← {detail}"))


post("/api/reset", {})
s = post("/api/chat", {"action": "start"})["session"]; post("/api/chat", {"session": s, "action": "lang:en"})
r = post("/api/chat", {"session": s, "text": "road is bad in Hunsur"})
check("'road is bad in Hunsur' → taluk read from text, straight to confirm (no village question)", any("Hunsur taluk" in m[2] for m in msgs(r)) and "submit" in json.dumps(r), msgs(r))
r = post("/api/chat", {"session": s, "action": "submit"})
res = next(e for e in r["events"] if e["kind"] == "result"); cid, own = res["caseId"], res["officer"]["id"]
check("routed to AEE PRED Hunsur", own == "aee_hunsur", own)
post(f"/api/cases/{cid}/action", {"action": "info", "officer": own, "note": "Please share more info on which area in Hunsur and send pics of the condition of the road."})
r = post("/api/chat", {"session": s, "action": "poll"})
m = msgs(r)
check("officer's question arrives in WhatsApp as an officer bubble with Reply button", m and m[0][0] == "officer" and "which area in Hunsur" in m[0][2] and f"reply:{cid}" in m[0][3], m)
check("notify event for the phone ping", any(e["kind"] == "notify" for e in r["events"]))
check("second poll is empty (delivered once)", not post("/api/chat", {"session": s, "action": "poll"})["events"])
r = post("/api/chat", {"session": s, "action": f"reply:{cid}"})
check("reply mode prompt", any("Type your reply" in m[2] for m in msgs(r)))
r = post("/api/chat", {"session": s, "text": "Near the government school on Hanagodu road, 200 metres of potholes. Call 9845012345"})
check("text reply confirmed", any("Sent to" in m[2] for m in msgs(r)))
r = post("/api/chat", {"session": s, "action": f"reply:{cid}"}); r = post("/api/chat", {"session": s, "action": "photo"})
check("photo reply confirmed", any("Sent to" in m[2] for m in msgs(r)))
c = next(x for x in get("/api/state?session=" + s)["cases"] if x["id"] == cid)
check("case back to In progress with both replies in the audit trail (phone masked)",
      c["status"] == "In progress" and sum(h["what"].startswith("Citizen replied") for h in c["history"]) == 2 and "[PHONE]" in json.dumps(c["history"]), c["history"][-2:])
check("officer notified of the reply", any(cid in n["m"] and "replied" in n["m"] for n in get("/api/state")["notifs"]))
r = post("/api/chat", {"session": s, "text": "track"})
check("track shows the case", cid in json.dumps(r))
post(f"/api/cases/{cid}/action", {"action": "accept", "officer": own})
r = post("/api/chat", {"session": s, "action": "poll"})
check("'accepted' message delivered", any(m[0] == "officer" and "accepted" in m[2] for m in msgs(r)), msgs(r))
rr = post(f"/api/cases/{cid}/action", {"action": "resolve", "officer": own, "atr": "Inspected Hanagodu road near the school on 16 Oct. The 200 m stretch was patched with WBM, potholes filled, work completed and verified."})
check("good ATR resolves", rr.get("score", 0) >= 4, rr)
r = post("/api/chat", {"session": s, "action": "poll"})
m = msgs(r)
check("'resolved' message with 👍/👎 buttons", m and f"fb:{cid}:no" in m[0][3], m)
r = post("/api/chat", {"session": s, "action": f"fb:{cid}:no"})
c = next(x for x in get("/api/state?session=" + s)["cases"] if x["id"] == cid)
check("👎 re-opens the case one rung UP the ladder and tells both officers", c["status"] == "Pending" and c["owner"] != own and c["level"] != "L1"
      and any("re-opened" in n["m"] for n in get("/api/state")["notifs"]) and any("rejected the resolution" in n["m"] for n in get("/api/state")["notifs"]), (c["status"], c["owner"], c["level"]))
check("the citizen's chat shows the escalation like a routing", any(e.get("kind") == "result" and e.get("title") == "Escalated to" for e in r["events"]), [e.get("kind") for e in r["events"]])
r = post("/api/chat", {"session": s, "action": f"case:{cid}"})
check("track inside the chat: live card with the ladder and the new holder", "wa-lad" in json.dumps(r) and c["owner"] in json.dumps(get("/api/state?session=" + s)), json.dumps(r)[:200])
own = c["owner"]                                                   # the senior holds it now
rr = post(f"/api/cases/{cid}/action", {"action": "reject", "officer": own, "reason": "Duplicate of an existing request"})
r = post("/api/chat", {"session": s, "action": "poll"})
check("'rejected' message with reason and appeal note", any("could not accept" in m[2] and "appeal" in m[2] for m in msgs(r)), msgs(r))
# Kannada chat gets Kannada officer messages
s2 = post("/api/chat", {"action": "start"})["session"]; post("/api/chat", {"session": s2, "action": "lang:kn"})
r = post("/api/chat", {"session": s2, "text": "ಹುಣಸೂರು ರಸ್ತೆ ಹಾಳಾಗಿದೆ"}); r = post("/api/chat", {"session": s2, "action": "submit"})
res = next((e for e in r["events"] if e["kind"] == "result"), None)
check("Kannada 'ಹುಣಸೂರು' taluk also detected", res and res["officer"]["id"] == "aee_hunsur", res and res["officer"])
if res:
    post(f"/api/cases/{res['caseId']}/action", {"action": "info", "officer": res["officer"]["id"], "note": "ಯಾವ ಗ್ರಾಮ?"})
    r = post("/api/chat", {"session": s2, "action": "poll"})
    check("Kannada officer bubble", any("ಹೆಚ್ಚಿನ ಮಾಹಿತಿ" in m[2] for m in msgs(r)), msgs(r))
# a PDO-level service with only the taluk named still asks for the GP
s3 = post("/api/chat", {"action": "start"})["session"]; post("/api/chat", {"session": s3, "action": "lang:en"})
r = post("/api/chat", {"session": s3, "text": "street light not working in Piriyapatna"})
check("street light + taluk only → asks for the Gram Panchayat list", any("gp:" in a for e in r["events"] for a in [x["action"] for x in ((e.get("list") or {}).get("rows") or [])]), msgs(r))
post("/api/reset", {})
print(f"\n{ok} passed")
