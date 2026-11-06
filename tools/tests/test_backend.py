"""Rigorous end-to-end tests against the running server (http://localhost:8020) + direct routing checks.
Run from the app folder:  python ../tools/tests/test_backend.py
Each section resets the demo database first, so tests are independent.
"""
import base64
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))
BASE = "http://localhost:8020"
PASS, FAIL = [], []


def call(path, body=None, files=None, method=None):
    if files:
        bnd = "----sakala"
        name, data = files
        payload = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{bnd}--\r\n".encode()
        req = urllib.request.Request(BASE + path, data=payload, headers={"Content-Type": f"multipart/form-data; boundary={bnd}"})
    else:
        req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else f"  ← {detail}"))


def reset():
    assert call("/api/reset", {})[0] == 200


class Chat:
    def __init__(self, lang="en"):
        self.sid = ""
        self.ev = []
        self.say(action="start")
        self.say(action=f"lang:{lang}")

    def say(self, **kw):
        code, r = call("/api/chat", {"session": self.sid, **kw})
        assert code == 200, (code, r)
        self.sid = r["session"]
        self.ev = r["events"]
        return self

    def text(self):
        return " ".join(re.sub("<[^>]+>", " ", e.get("html", "")) for e in self.ev if e["kind"] == "msg")

    def result(self):
        return next((e for e in self.ev if e["kind"] == "result"), None)

    def buttons(self):
        out = []
        for e in self.ev:
            out += [b["action"] for b in e.get("buttons", []) or []]
            out += [r["action"] for r in ((e.get("list") or {}).get("rows") or [])]
        return out

    def stages(self):
        return {e["i"]: e["state"] for e in self.ev if e["kind"] == "stage"}


# ======================================================================================
def t_routing_matrix():
    print("\n[1] Routing matrix: every service × every pilot taluk × GPs")
    from server import db
    from server.routing import route
    officers = {o["id"]: o for o in db.q("SELECT * FROM officers")}
    services = db.q("SELECT * FROM services")
    bad, n = [], 0
    for s in services:
        for tk in ("Piriyapatna", "Hunsur", "Mysuru"):
            gps = [g["gp"] for g in db.q("SELECT DISTINCT gp FROM gazetteer WHERE taluk=?", (tk,))]
            for gp in gps[:6] + [""]:
                r = route(s["id"], tk, gp)
                n += 1
                if s["role"] == "PDO" and not gp:
                    if not r["need_gp"]:
                        bad.append((s["name"], tk, gp, "should ask for GP"))
                    continue
                o = officers.get(r["officer"])
                if not o:
                    bad.append((s["name"], tk, gp, r["officer"])); continue
                if o["taluk"] and o["taluk"] != tk:
                    bad.append((s["name"], tk, gp, "wrong taluk " + o["id"]))
                if s["role"] == "PDO" and o["role"] == "PDO" and o["gp"] != gp:
                    bad.append((s["name"], tk, gp, "wrong GP " + o["id"]))
                # escalation chain must reach an L3 head with no loops
                seen, cur = set(), o
                while cur and cur["up_id"]:
                    if cur["id"] in seen: bad.append((s["name"], "loop")); break
                    seen.add(cur["id"]); cur = officers.get(cur["up_id"])
                if not cur or cur["level"] != "L3":
                    bad.append((s["name"], tk, gp, "chain does not end at L3"))
    check(f"{n} routing combinations resolve to a real officer in the right taluk / GP with an L3 chain", not bad, bad[:5])
    ev = db.kv_get("routing_eval")
    check(f"real-data agreement ≥ 95% (got {ev['rate']:.1%} on {ev['n']})", ev["rate"] >= 0.95)


def t_understanding():
    print("\n[2] AI understanding on the gateway (Kannada / English / mixed)")
    from server import pipeline, ai, local_ai
    local_ai.load()
    check("gateway LLM is live", ai.status()["llm"], ai.status())
    cases = [  # text, expected intent, expected service substring (or dept for OOS)
        ("ನಮ್ಮ ಗೊರಹಳ್ಳಿ ಗ್ರಾಮದಲ್ಲಿ ಕಳೆದ ಒಂದು ವಾರದಿಂದ ಕುಡಿಯುವ ನೀರು ಬರುತ್ತಿಲ್ಲ", "GRIEVANCE", "Drinking Water"),
        ("ಪೌತಿ ಖಾತಾ ಮಾಡಲು ಮೂರು ತಿಂಗಳಿಂದ ವಿಳಂಬ ಆಗುತ್ತಿದೆ", "GRIEVANCE", "KHATHA|Mutation"),
        ("ನಾನು ವಿಧವೆ, ಐದು ತಿಂಗಳಿಂದ ಸಂಧ್ಯಾ ಸುರಕ್ಷಾ ಪಿಂಚಣಿ ಬಂದಿಲ್ಲ", "GRIEVANCE", "Old-Age|Widow|Sandhya"),
        ("Applied for a new ration card three months ago, still not received.", "GRIEVANCE", "Ration"),
        ("Street light near the bus stand is not working for two weeks.", "GRIEVANCE", "Street Light"),
        ("ನಮ್ಮ ಜಮೀನಿನ ಪಹಣಿಯಲ್ಲಿ ಹೆಸರು ತಪ್ಪಾಗಿದೆ", "GRIEVANCE", "RTC"),
        ("Village road full of potholes, cannot walk", "GRIEVANCE", "Road"),
        ("ಪೋಡಿ ಮಾಡಲು ಅರ್ಜಿ ಸಲ್ಲಿಸಿ ಎರಡು ತಿಂಗಳಾಗಿದೆ", "GRIEVANCE", "podi|Survey|Haddu|11e"),
        ("House not sanctioned under Basava housing scheme though selected in grama sabha", "GRIEVANCE", "Housing"),
        ("drainage blocked and mosquitoes everywhere in our street", "GRIEVANCE", "drain|Sanitation"),
        ("NREGA wages not paid for 2 months", "GRIEVANCE", "MGNREGS"),
        ("Power cut every evening in our village for one week.", "OUT_OF_SCOPE", "Energy"),
        ("Bus does not stop at our village", "OUT_OF_SCOPE", "Transport"),
        ("I want to file an RTI application about the road contract", "WRONG_DOOR", ""),
        ("I need a caste and income certificate for my son's admission", "SERVICE_REQUEST", ""),
        ("hello how are you", "UNCLEAR", ""),
    ]
    ok = 0
    for text, intent, svc in cases:
        _, _, u = pipeline.understand(text)
        good = u["intent"] == intent and (not svc or re.search(svc, (u.get("service") or "") + " " + (u.get("dept") or ""), re.I))
        ok += bool(good)
        if not good:
            print(f"      miss: {text[:50]} → {u['intent']} / {u.get('service') or u.get('dept')} ({u.get('engine')})")
    check(f"understanding correct on {ok}/{len(cases)} (need ≥ 14)", ok >= 14)


def t_chat_flows():
    print("\n[3] WhatsApp flows (all paths)")
    reset()
    c = Chat().say(text="ನಮ್ಮ ಗೊರಹಳ್ಳಿ ಗ್ರಾಮದಲ್ಲಿ ಕಳೆದ ಒಂದು ವಾರದಿಂದ ಕುಡಿಯುವ ನೀರು ಬರುತ್ತಿಲ್ಲ")
    check("water: village found in Kannada text → confirm card", "submit" in c.buttons() and "Chapparadahalli" in c.text(), c.text()[:200])
    c.say(action="submit")
    r = c.result()
    check("water: routed to AE RDWS Piriyapatna (data rule) with 8 stages done", r and r["officer"]["id"] == "rdws_piriyapatna" and all(v == "done" for k, v in c.stages().items() if k >= 4), r)
    c.say(action="submit")
    check("double submit does not create a second case", c.result() is None)
    c.say(action="gp:Komalapura|Piriyapatna")
    check("stale GP button after finishing → polite menu, no error", "already finished" in c.text())
    c2 = Chat().say(text="ನಮ್ಮ ಗೊರಹಳ್ಳಿ ಗ್ರಾಮದಲ್ಲಿ ಕಳೆದ ಒಂದು ವಾರದಿಂದ ಕುಡಿಯುವ ನೀರು ಬರುತ್ತಿಲ್ಲ")
    check("duplicate detection: same service + same GP flagged", "similar open request" in c2.text(), c2.text()[-200:])
    c2.say(action="submit")
    check("duplicate is linked on submit", "linked" in json.dumps(c2.ev))

    c = Chat().say(text="Street light near the bus stand is not working for two weeks.")
    check("street light without village → asks location (not Transport!)", "loc:share" in c.buttons(), c.text()[:200])
    c.say(action="tk:Piriyapatna")
    check("taluk → GP list (≤10 rows)", 0 < len([b for b in c.buttons() if b.startswith("gp:")]) <= 10)
    c.say(text="Xyzqwpura")
    check("unknown village typed → asks again", "could not find" in c.text())
    c.say(text="Kampalapura")
    check("typed village resolves via gazetteer", "Kampalapura" in c.text() and "submit" in c.buttons())
    c.say(action="submit")
    check("street light → PDO of that exact GP", c.result() and c.result()["officer"]["id"] == "pdo_piriyapatna_kampalapura", c.result())

    c = Chat().say(text="ಪೌತಿ ಖಾತಾ ಮಾಡಲು ಮೂರು ತಿಂಗಳಿಂದ ವಿಳಂಬ ಆಗುತ್ತಿದೆ").say(action="loc:share").say(action="submit")
    check("khata + demo GPS → Tahsildar Piriyapatna", c.result() and c.result()["officer"]["id"] == "tah_piriyapatna", c.result())

    c = Chat().say(text="Old age pension not credited for 3 months. Village Halebeedu, Hunsur").say(action="submit")
    check("Hunsur village in English → Tahsildar Hunsur", c.result() and c.result()["officer"]["id"] == "tah_hunsur", c.result())

    c = Chat().say(action="photo")
    check("sample petition photo → phone masked + ration grievance", "[PHONE]" in c.text() and "Ration" in c.text(), c.text()[:200])
    c.say(action="submit")
    check("photo → Food Inspector Piriyapatna (Bylakuppe)", c.result() and c.result()["officer"]["id"] == "fi_piriyapatna", c.result())

    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (900, 300), "white"); d = ImageDraw.Draw(img)
        d.text((30, 40), "To the Tahsildar, Piriyapatna.", fill="black")
        d.text((30, 90), "The street light near Komalapura bus stop is not working for 2 weeks.", fill="black")
        d.text((30, 140), "Please repair it. - Ramesh, Komalapura village. Mobile 9845012345", fill="black")
        buf = io.BytesIO(); img.resize((1800, 600)).save(buf, "PNG")
        c = Chat().say(action="photo", image_b64=base64.b64encode(buf.getvalue()).decode(), media_type="image/png")
        check("real uploaded photo → vision model reads it, phone masked", "Komalapura" in c.text() and "[PHONE]" in c.text(), c.text()[:250])
    except ImportError:
        print("  (PIL missing: real-photo test skipped)")

    wav = Path(__file__).resolve().parent / "asr_test.wav"
    if wav.exists():
        c = Chat().say(action="voice", audio_b64=base64.b64encode(wav.read_bytes()).decode())
        check("real voice note → speech model transcript → street light grievance", "Street Light" in c.text() or "street light" in c.text().lower(), c.text()[:200])
    c = Chat().say(action="voice", audio_b64=base64.b64encode(b"RIFF" + b"\0" * 2000).decode())
    check("empty / broken audio → asks to retry, no crash", "could not hear" in c.text() or "I heard" in c.text())
    c = Chat().say(action="voice")
    check("no microphone → sample voice note path works", "SAMPLE VOICE NOTE" in c.text())

    c = Chat().say(action="apply").say(action="svc:caste_income").say(text="Lakshmi K").say(action="village:Komalapura|Piriyapatna").say(action="doc")
    r = c.result()
    check("Sakala application → Designated Tahsildar, CO AC Hunsur, AA DC, 21-day legal date",
          r and r["officer"]["id"] == "tah_piriyapatna" and "AC Hunsur" in json.dumps(r["chain"]) and "21 days" in c.text(), r)
    c = Chat().say(action="village:Komalapura|Piriyapatna")
    check("village button without an application → menu, no error", "How can I help" in c.text())
    c = Chat().say(text="I need a caste and income certificate for my son")
    check("certificate request → offered as Sakala application", "apply_now:caste_income" in c.buttons(), c.buttons())
    c = Chat().say(text="Power cut every evening in our village")
    check("power cut → out of scope (Energy)", "Energy" in c.text())
    c = Chat().say(text="I want to file an RTI application")
    check("RTI → wrong door", "RTI" in c.text() and c.result() is None)
    c = Chat().say(text="hello how are you")
    check("small talk → menu (not a case)", "How can I help" in c.text())
    c = Chat().say(text="asdf qwer zxcv uiop")
    check("gibberish → scrutiny desk or clarification, never a silent guess", "scrutiny" in c.text().lower() or "How can I help" in c.text())
    c = Chat().say(text="   ")
    check("empty message → no crash", True)
    c = Chat().say(text="ನೀರು " * 900)
    check("very long message (>2000 chars) handled", True)
    c = Chat().say(action="tk:Bengaluru")
    check("invalid taluk action → menu", "How can I help" in c.text() or "did not understand" in c.text())
    c = Chat().say(action="no_such_action")
    check("unknown action → polite reply", "did not understand" in c.text())
    c = Chat("kn").say(action="grievance")
    check("Kannada branch prompts in Kannada", "ಸಮಸ್ಯೆ" in c.text())
    c = Chat().say(text="My application RD855S260004811 for caste certificate is delayed, please help. Komalapura")
    check("GSC number → grievance-to-Sakala bridge shows legal status", "RD855S260004811" in c.text() and "Sakala" in c.text(), c.text()[:300])
    c = Chat().say(action="track")
    check("track with no requests → friendly reply", "no requests" in c.text())
    code, st = call("/api/state?session=" + c.sid)
    check("state endpoint returns cases", code == 200 and len(st["cases"]) > 700)


def t_officer_actions():
    print("\n[4] Officer & Chief Secretary actions + permissions")
    reset()
    c = Chat().say(text="Street light near the bus stand is not working. Kampalapura village").say(action="submit")
    cid, own = c.result()["caseId"], c.result()["officer"]["id"]
    check("wrong officer cannot act (403)", call(f"/api/cases/{cid}/action", {"action": "accept", "officer": "tah_hunsur"})[0] == 403)
    check("CS cannot accept on behalf of officer (403)", call(f"/api/cases/{cid}/action", {"action": "accept"})[0] == 403)
    check("owner accepts", call(f"/api/cases/{cid}/action", {"action": "accept", "officer": own})[0] == 200)
    check("reject without reason → 400", call(f"/api/cases/{cid}/action", {"action": "reject", "officer": own})[0] == 400)
    check("ATR too short → 400", call(f"/api/cases/{cid}/action", {"action": "resolve", "officer": own, "atr": "done"})[0] == 400)
    code, r = call(f"/api/cases/{cid}/action", {"action": "resolve", "officer": own, "atr": "We will look into the matter and forward it to the concerned section."})
    check(f"vague ATR is NOT accepted (score {r.get('score')})", code == 200 and r.get("score", 5) < 4, r)
    code, r = call(f"/api/cases/{cid}/draft_atr", {})
    check("AI drafts an ATR", code == 200 and len(r.get("text", "")) > 30, r)
    code, r = call(f"/api/cases/{cid}/action", {"action": "resolve", "officer": own,
                                                 "atr": "Inspected the pole on 15 Oct with the GP lineman. The faulty LED fitting and fuse were replaced and the street light is working again; the citizen confirmed by phone."})
    check(f"good ATR resolves the case (score {r.get('score')})", code == 200 and r.get("score", 0) >= 4, r)
    check("acting on a resolved case → 409", call(f"/api/cases/{cid}/action", {"action": "accept", "officer": own})[0] == 409)
    _, st = call("/api/state")
    real_open = next(c["id"] for c in st["cases"] if c["real"] and c["status"] == "Pending")
    check("CS nudge on an open real case", call(f"/api/cases/{real_open}/action", {"action": "nudge"})[0] == 200)
    sk = "SK-RD855S260004811"
    check("compensation by non-Competent officer → 403", call(f"/api/cases/{sk}/action", {"action": "comp_order", "officer": "tah_piriyapatna"})[0] == 403)
    code, r = call(f"/api/cases/{sk}/action", {"action": "comp_order", "officer": "ac_hunsur"})
    check("Competent Officer orders ₹100 (5 days × ₹20)", code == 200 and "₹100" in r["toast"][1], r)
    check("compensation on a grievance → 400", call(f"/api/cases/{cid}/action", {"action": "comp_order", "officer": "ac_hunsur"})[0] == 400)
    check("unknown action → 400", call(f"/api/cases/{cid}/action", {"action": "fly", "officer": own})[0] == 400)
    check("unknown case → 404", call("/api/cases/NOPE/action", {"action": "accept", "officer": own})[0] == 404)
    check("unknown officer → 400", call(f"/api/cases/{sk}/action", {"action": "accept", "officer": "ghost"})[0] == 400)


def t_clock():
    print("\n[5] Demo clock: escalation + Sakala legal clock")
    reset()
    from server import db
    code, r1 = call("/api/clock/tick", {"days": 1})
    check("+1 day works", code == 200)
    code, r7 = call("/api/clock/tick", {"days": 7})
    check(f"+7 days escalates the imported backlog (escalated {r7['escalated']})", r7["escalated"] > 100)
    code, st = call("/api/state")
    by = {c["id"]: c for c in st["cases"]}
    bad = [c["id"] for c in st["cases"] if c["status"] in ("Pending",) and c["level"] == "L1" and c["u"]["type"] == "GRIEVANCE"
           and (time.mktime(time.strptime(st["now"][:19], "%Y-%m-%dT%H:%M:%S")) - time.mktime(time.strptime(c["levelSince"][:19], "%Y-%m-%dT%H:%M:%S"))) / 86400 > 7.01]
    check("no L1 grievance left past its deadline after the tick", not bad, bad[:5])
    l3_ok = all(c["level"] in ("L1", "L2", "L3") for c in st["cases"])
    check("levels stay within L1–L3", l3_ok)
    check("Sakala applications never move on the grievance ladder", by["SK-RD855S260004811"]["level"] == "L1")
    ev = db.q("SELECT COUNT(*) n FROM case_events WHERE case_id='SK-FD201S260002219' AND what='Legal deadline missed'")[0]["n"]
    check("ration application not breached at day 20 of 30", ev == 0, ev)
    call("/api/clock/tick", {"days": 15})
    ev = db.q("SELECT COUNT(*) n FROM case_events WHERE case_id='SK-FD201S260002219' AND what='Legal deadline missed'")[0]["n"]
    check("Sakala breach logged once after the 30-day deadline passes", ev == 1, ev)
    call("/api/clock/tick", {"days": 30})
    ev = db.q("SELECT COUNT(*) n FROM case_events WHERE case_id='SK-FD201S260002219' AND what='Legal deadline missed'")[0]["n"]
    check("…and not logged again on later ticks", ev == 1, ev)
    check("tick clamps to 30 days", call("/api/clock/tick", {"days": 999})[0] == 200)


def t_intelligence():
    print("\n[6] Leadership intelligence endpoints")
    reset()
    for p in ("/api/insights/quality", "/api/insights/misrouting", "/api/insights/historical", "/api/insights/hotspots",
              "/api/sakala/tracker", "/api/sakala/early_warning", "/api/e4", "/api/bootstrap"):
        code, r = call(p)
        check(f"GET {p} → 200", code == 200, r)
    code, t = call("/api/sakala/tracker")
    check("tracker totals match the verified report figures (35,168,374 · 4.45% · 7.42%)",
          t["state"]["receipts"] == 35168374 and t["state"]["late_pct"] == 4.45 and t["state"]["rej_pct"] == 7.42, t["state"])
    code, h = call("/api/insights/historical?summary=1")
    check("historical intelligence has an AI summary", bool(h.get("summary")))
    code, h = call("/api/insights/hotspots?fix=1")
    check("hotspots return clusters + AI root-cause fixes", (h["open"] or h["week"]) and h.get("fixes"), h.get("fixes"))
    code, p = call("/api/review_pack?level=cs")
    check("Wednesday pack (CS) has facts + English + Kannada", p["facts"]["open"] > 0 and p.get("html") and p.get("kn"))
    for lv, off in (("dc", "dc_mys"), ("ac", "ac_hunsur"), ("eo", "eo_piriyapatna")):
        code, p = call(f"/api/review_pack?level={lv}&officer_id={off}")
        check(f"Wednesday pack for {lv.upper()} scoped to their team", code == 200 and p["facts"]["scope"] == lv)
    code, a = call("/api/insights/accuracy?run=1&n=20")
    llm = a.get("llm") or {}
    check(f"live accuracy test runs (officer {llm.get('officer_acc')}, dept {llm.get('dept_acc')}, n={llm.get('n')})", llm.get("n", 0) >= 15)


def t_upload_and_ask():
    print("\n[7] Excel / CSV upload + AI mode")
    reset()
    sample = (Path(__file__).resolve().parents[2] / "app" / "web" / "samples" / "sample_complaints.csv").read_bytes()
    code, r = call("/api/upload", files=("complaints.csv", sample))
    check(f"complaints CSV: {r.get('routed')} of {r.get('rows')} routed in one pass", code == 200 and r["rows"] == 8 and r["routed"] >= 5, r)
    outs = {x["text"][:20]: x for x in r.get("results", [])}
    check("CSV: transformer row is out of scope, RTI row is wrong-door", any(x["intent"] == "OUT_OF_SCOPE" for x in r["results"]) and any(x["intent"] == "WRONG_DOOR" for x in r["results"]))
    perf = (Path(__file__).resolve().parents[2] / "combined_dec 1.xlsx").read_bytes()
    code, r = call("/api/upload", files=("combined_dec 1.xlsx", perf))
    check("performance workbook upload → 12 months × 32 rows", code == 200 and r.get("kind") == "performance_report" and r["months"] == 12, r)
    code, r = call("/api/upload", files=("bad.csv", b"name,age\nx,1\n"))
    check("file without a description column → clear 400", code == 400, r)
    for q in ("Which officer has the most overdue cases?", "How many pension complaints are pending in Piriyapatna?",
              "Which district had the highest late-delivery rate in 2025?", "Which channel brings the most complaints?",
              "ಪಿರಿಯಾಪಟ್ಟಣದಲ್ಲಿ ಎಷ್ಟು ಕುಡಿಯುವ ನೀರಿನ ದೂರುಗಳು ಬಾಕಿ ಇವೆ?", "What is the weather tomorrow?"):
        code, r = call("/api/ask", {"q": q})
        check(f"AI mode answers: {q[:45]}", code == 200 and (r.get("html") or r["engine"] == "local"), r)
    code, r = call("/api/ask", {"q": "Which district had the highest late-delivery rate in 2025?"})
    check("AI mode grounded: names Bengaluru Urban 9.18%", "Bengaluru Urban" in (r.get("html") or "") and "9.18" in (r.get("html") or ""), r.get("html"))
    code, r = call("/api/ask", {"q": ""})
    check("empty question → local fallback, no error", code == 200)


if __name__ == "__main__":
    t0 = time.time()
    only = sys.argv[1:]
    for f in (t_routing_matrix, t_understanding, t_chat_flows, t_officer_actions, t_clock, t_intelligence, t_upload_and_ask):
        if not only or f.__name__ in only:
            try:
                f()
            except Exception as e:  # noqa: BLE001
                FAIL.append(f.__name__); print("  CRASH", f.__name__, repr(e))
    reset()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed in {time.time() - t0:.0f}s")
    if FAIL:
        print("FAILED:", *FAIL, sep="\n  ")
