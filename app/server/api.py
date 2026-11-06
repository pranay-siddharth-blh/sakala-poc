"""HTTP API + static web app.  Run:  python -m uvicorn server.api:app --port 8020   (from the app folder)"""
import re
import json
import shutil
import time
from datetime import datetime

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai, analytics, chat, db, docread, local_ai, sla
from .config import WEB, DB_PATH, SLA_DAYS
from .sla import now, officer, event, notify, sla_info, compensation, message_citizen

app = FastAPI(title="Sakala AI POC")


class Protection:
    """Guardrail 19 (same pattern as the sister POCs): per-client rolling-minute rate limits, a request-size cap
    and security headers. Plain ASGI so nothing is buffered."""
    LIMITS = (("/api/transcribe", 240), ("/api/chat", 120), ("/api/ask", 60), ("/api/cases", 120), ("/api/upload", 20), ("/api/clock", 60))
    MAX_BYTES = 8_000_000
    HEADERS = [(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"), (b"referrer-policy", b"no-referrer"),
               (b"permissions-policy", b"camera=(), microphone=(self), geolocation=()")]

    def __init__(self, app):
        import collections
        self.app, self.hits = app, collections.defaultdict(collections.deque)

    def over(self, key, limit):
        import time as _t
        q, t = self.hits[key], _t.monotonic()
        while q and t - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(t)
        return False

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        hdr = dict(scope.get("headers") or [])
        ln = hdr.get(b"content-length", b"")
        status, msg = None, ""
        if ln.isdigit() and int(ln) > self.MAX_BYTES:
            status, msg = 413, "That file is too large (8 MB limit)."
        else:
            for prefix, limit in self.LIMITS:
                if path.startswith(prefix):
                    client = (scope.get("client") or ("?", 0))[0]
                    if self.over(f"{client}:{prefix}", limit):
                        status, msg = 429, "Too many requests in a short time. Please wait a moment and try again."
                    break
        if status:
            body = json.dumps({"detail": msg}).encode()
            await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), (b"retry-after", b"60"), *self.HEADERS]})
            return await send({"type": "http.response.body", "body": body})

        async def send2(m):
            if m["type"] == "http.response.start":
                m = dict(m); m["headers"] = list(m.get("headers") or []) + self.HEADERS
            await send(m)
        return await self.app(scope, receive, send2)


app.add_middleware(Protection)
from fastapi.middleware.gzip import GZipMiddleware   # noqa: E402  (the statewide caseload makes /api/state several MB)
app.add_middleware(GZipMiddleware, minimum_size=2000)
PRISTINE = DB_PATH.with_name("sakala_pristine.db")


@app.on_event("startup")
def startup():
    db.conn()
    if not PRISTINE.exists():
        db.run("PRAGMA wal_checkpoint(TRUNCATE)")
        shutil.copyfile(DB_PATH, PRISTINE)
    if not local_ai.load():
        local_ai.train(evaluate=False)


# ---------------- serialisation in the exact shape the web UI uses ----------------
def case_json(c, events, session=None, light=False):
    sk = json.loads(c["sakala"]) if c["sakala"] else None
    if light:            # list views: no raw text, no audit, only the latest event
        ev = events.get(c["id"], [])
        return {"id": c["id"], "masked": (c["masked"] or "")[:240], "summary": c["summary"], "src": c["src"], "district": c["district"],
                "taluk": c["taluk"], "gp": c["gp"] or "", "village": c["village"] or "", "owner": c["owner"], "level": c["level"],
                "levelSince": c["level_since"], "created": c["created"], "status": c["status"], "vulnerable": bool(c["vulnerable"]),
                "real": bool(c["real"]), "synthetic": bool(c["synthetic"]), "engine": c["engine"], "atr": c["atr"], "atrScore": c["atr_score"],
                "linkedTo": c["linked_to"], "mine": bool(session and c["session"] == session),
                "u": {"d": c["dept_code"], "line": c["line"], "svc": c["service"], "gr": c["grievance"], "conf": c["conf"], "why": c["why"],
                      "type": c["kind"], "vulnerable": bool(c["vulnerable"]), "vulnReason": c["vuln_reason"]},
                "sakala": sk, "last": ev[-1] if ev else None, "escalated": any(e["what"].startswith("Auto-escalated") for e in ev), "nEvents": len(ev)}
    return {"id": c["id"], "text": c["text"], "masked": c["masked"], "summary": c["summary"], "src": c["src"], "district": c["district"],
            "taluk": c["taluk"], "gp": c["gp"] or "", "village": c["village"] or "", "owner": c["owner"], "level": c["level"],
            "levelSince": c["level_since"], "created": c["created"], "status": c["status"], "vulnerable": bool(c["vulnerable"]),
            "real": bool(c["real"]), "synthetic": bool(c["synthetic"]), "engine": c["engine"], "routeBasis": c["route_basis"],
            "atr": c["atr"], "atrScore": c["atr_score"], "atrReason": c["atr_reason"], "linkedTo": c["linked_to"],
            "mine": bool(session and c["session"] == session), "audit": json.loads(c["audit"]) if c.get("audit") else None,
            "u": {"d": c["dept_code"], "line": c["line"], "svc": c["service"], "gr": c["grievance"], "conf": c["conf"], "why": c["why"],
                  "type": c["kind"], "vulnerable": bool(c["vulnerable"]), "vulnReason": c["vuln_reason"]},
            "sakala": sk, "history": events.get(c["id"], []), "doc": json.loads(c["doc"]) if ("doc" in c.keys() and c["doc"]) else None}


def all_cases(session=None, scope="all", owner="", district="", light=False, ids=None):
    where, args = [], []
    if scope == "citizen":                     # guardrail 9: a citizen's screen only ever receives the cases filed from its own chat
        where.append("session=?"); args.append(session or "-")
    if owner:
        where.append("owner=?"); args.append(owner)
    if district:
        where.append("lower(district)=?"); args.append(district.lower())
    if ids:
        where.append(f"id IN ({','.join('?' * len(ids))})"); args.extend(ids)
    sql = "SELECT * FROM cases" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY created"
    rows = db.q(sql, args)
    ev = {}
    if rows and (where and len(rows) < 2000):
        cid = [r["id"] for r in rows]
        for chunk in range(0, len(cid), 800):
            part = cid[chunk:chunk + 800]
            for e in db.q(f"SELECT * FROM case_events WHERE case_id IN ({','.join('?' * len(part))}) ORDER BY t, id", part):
                ev.setdefault(e["case_id"], []).append({"t": e["t"], "who": e["who"], "what": e["what"], "c": e["color"], "note": e["note"]})
    else:
        for e in db.q("SELECT * FROM case_events ORDER BY t, id"):
            ev.setdefault(e["case_id"], []).append({"t": e["t"], "who": e["who"], "what": e["what"], "c": e["color"], "note": e["note"]})
    return [case_json(c, ev, session, light) for c in rows]


@app.get("/api/bootstrap")
def bootstrap():
    offs = {o["id"]: {"n": o["name"], "short": o["short"], "d": o["dept_code"], "lv": o["level"], "up": o["up_id"], "role": o["role"],
                      "taluk": o["taluk"], "gp": o["gp"], "seen": bool(o["seen_in_data"]), "dataName": o["data_name"], "nReal": o["n_real"]}
            for o in db.q("SELECT * FROM officers ORDER BY level DESC, dept_code, taluk, gp")}
    geo = {}
    for r in db.q("SELECT district, taluk, gp, SUM(n_real) n FROM gazetteer GROUP BY district, taluk, gp ORDER BY n DESC"):
        geo.setdefault(r["district"] or "Mysuru", {}).setdefault(r["taluk"], []).append(r["gp"])
    names = {"REV": "Revenue Department", "RDPR": "Rural Development & Panchayat Raj", "FOOD": "Food & Civil Supplies"}
    depts = {d["code"]: {"name": names[d["code"]], "kn": d["name_kn"], "c": d["color"]} for d in db.q("SELECT * FROM departments WHERE pilot=1")}
    return {"officers": offs, "geo": geo, "depts": depts, "now": now().isoformat(), "sla": SLA_DAYS, "ai": ai.status(),
            "evals": {"routing": db.kv_get("routing_eval"), "routing_pilot": db.kv_get("routing_eval_pilot"), "model": db.kv_get("model_eval"), "llm": analytics.saved_llm_eval()},
            "masters": {"services": db.q1("SELECT COUNT(*) n FROM services")["n"], "grievanceTypes": db.q1("SELECT COUNT(*) n FROM grievance_types")["n"],
                        "officers": len(offs), "villages": db.q1("SELECT COUNT(*) n FROM gazetteer")["n"], "records": db.q1("SELECT COUNT(*) n FROM ipgrs_records")["n"],
                        "gps": sum(len(t) for d in geo.values() for t in d.values()), "districts": len(geo), "taluks": sum(len(d) for d in geo.values())},
            "samples": chat.SAMPLES}


@app.get("/api/state")
def state(session: str = "", scope: str = "all", owner: str = "", district: str = "", light: bool = False, id: str = ""):
    notifs = [] if scope == "citizen" else [{"to": n["officer_id"], "t": n["t"], "m": n["msg"]} for n in db.q("SELECT * FROM notifications ORDER BY id DESC LIMIT 400")]
    ids = [x for x in id.split(",") if x] if id else None
    return {"now": now().isoformat(), "cases": all_cases(session, scope, owner, district, light, ids), "notifs": notifs, "ai": ai.status()}


@app.get("/api/case/{cid}")
def one_case(cid: str, session: str = ""):
    rows = all_cases(session, "all", ids=[cid])
    if not rows:
        raise HTTPException(404, "case not found")
    return rows[0]


@app.get("/api/ai_log")
def ai_log(limit: int = 200):
    """Guardrail 12: every AI call is logged; this is the weekly-review view (failures first)."""
    rows = db.q("SELECT * FROM ai_log ORDER BY ok, id DESC LIMIT ?", (max(10, min(limit, 1000)),))
    tot = db.q1("SELECT COUNT(*) n, SUM(ok=0) fails FROM ai_log")
    return {"total": tot["n"], "failures": tot["fails"] or 0, "rows": rows}


class Tick(BaseModel):
    days: int


@app.post("/api/clock/tick")
def tick(t: Tick):
    return sla.tick(max(1, min(30, t.days)))


@app.post("/api/reset")
def reset():
    import sqlite3
    src = sqlite3.connect(PRISTINE)
    with db._lock:
        src.backup(db.conn())          # restores in place: works even while other readers hold the file
        db.conn().executescript(db.SCHEMA)   # tables added after the snapshot was taken
        db.migrate()
    src.close()
    analytics._CACHE.clear()
    return {"ok": True, "now": now().isoformat()}


class ChatReq(BaseModel):
    session: str = ""
    action: str = ""
    text: str = ""
    image_b64: str = ""
    media_type: str = "image/png"
    voice_text: str = ""
    audio_b64: str = ""


@app.post("/api/chat")
def chat_ep(r: ChatReq):
    if len(r.text) > 2000:
        r.text = r.text[:2000]
    return chat.handle(r.session, r.model_dump())


class Action(BaseModel):
    action: str
    officer: str = ""
    note: str = ""
    reason: str = ""
    atr: str = ""
    to: str = ""
    place: str = ""      # return: where the case really belongs (taluk / GP / village), optional
    via: str = ""        # a channel that acted for the officer (Sakala Mitra voice): recorded in the case file
    heard: str = ""      # the sentence that was heard (masked again here)


OPEN = ("Pending", "In progress", "Info requested")


@app.get("/api/cases/{cid}/transfer_preview")
def transfer_preview(cid: str, officer: str = "", to: str = "", place: str = ""):
    """Who a return with this suggestion would go to (nothing is changed): for the read-back and the drawer hint."""
    from . import transfer
    c = db.q1("SELECT * FROM cases WHERE id=?", (cid,))
    if not c:
        raise HTTPException(404, "case not found")
    if c["kind"] == "APPLICATION" or not (to or place):
        return {"officer": None, "scrutiny": True, "how": "a Sakala application follows its own ladder" if c["kind"] == "APPLICATION" else ""}
    s = transfer.resolve(dict(c), to, place, officer)
    o = s["officer"]
    return {"officer": {"id": o["id"], "short": o["short"], "name": o["name"], "level": o["level"]} if o else None,
            "scrutiny": not o, "how": s["how"], "asked": s["asked"]}


@app.post("/api/cases/{cid}/action")
def case_action(cid: str, a: Action):
    _ev = globals()["event"]
    _said = _pl.mask(a.heard)[0][:200] if a.heard else ""
    _via = (f" · via {a.via}" + (f": “{_said}”" if _said else "")) if a.via else ""

    def event(case_id, who_, what, color, note="", t=None):      # every event of a voice action names the channel and the words
        _ev(case_id, who_, what, color, (note or "") + _via, t)

    c = db.q1("SELECT * FROM cases WHERE id=?", (cid,))
    if not c:
        raise HTTPException(404, "case not found")
    me = officer(a.officer) if a.officer else None
    if a.officer and not me:
        raise HTTPException(400, "unknown officer")
    who = me["short"] if me else "Chief Secretary’s office"
    sk = json.loads(c["sakala"]) if c["sakala"] else None
    officer_actions = ("accept", "info", "return", "reject", "resolve")
    if a.action in officer_actions:
        if c["status"] not in OPEN:
            raise HTTPException(409, f"case is {c['status']}")
        if not me or me["id"] != c["owner"]:
            raise HTTPException(403, "only the officer who holds the case can act on it")
    if a.action in ("comp_order", "comp_hrms"):
        if not sk:
            raise HTTPException(400, "compensation applies only to Sakala applications")
        if not me or me["id"] != sk["CO"]:
            raise HTTPException(403, "only the Competent Officer can order compensation")
        if compensation(c) <= 0:
            raise HTTPException(409, "no delay: nothing to compensate")
    out = {"ok": True}

    def status(s):
        db.run("UPDATE cases SET status=? WHERE id=?", (s, cid))

    if a.action == "accept":
        event(cid, who, "Accepted", "#3b7dd8", "Officer started work"); status("In progress")
        message_citizen(cid, me["id"], "accepted")
        out["toast"] = ["Accepted", cid]
    elif a.action == "info":
        event(cid, who, "Asked citizen for information", "#3b7dd8", a.note or "Question sent on WhatsApp"); status("Info requested")
        message_citizen(cid, me["id"], "info", a.note or "Please share more details about your request.")
        out["toast"] = ["Sent", "Question sent to the citizen on WhatsApp"]
    elif a.action == "return":
        from . import transfer
        why = a.reason or "Wrong jurisdiction"
        sug = transfer.resolve(dict(c), a.to, a.place, me["id"]) if (a.to or a.place) and c["kind"] != "APPLICATION" else \
            {"officer": None, "place": None, "how": "a Sakala application follows its own ladder" if (a.to or a.place) else "", "asked": " · ".join(x for x in (a.to, a.place) if x)}
        target = sug["officer"]
        if target:
            # the suggestion names a real officer: the case goes straight to them, with a fresh clock, and they are told
            pl = sug.get("place") or {}
            new_taluk = pl.get("taluk") or target.get("taluk") or c["taluk"]
            new_gp = pl.get("gp") if pl.get("gp") else (c["gp"] if new_taluk == c["taluk"] else "")
            new_dist = pl.get("district") or target.get("district") or c["district"]
            audit = json.loads(c["audit"]) if c.get("audit") else {}
            audit["human_decision"] = {"by": who, "to": target["id"], "note": f"Returned as not my jurisdiction; suggested {sug['asked']}",
                                       "how": sug["how"], "at": now().isoformat(timespec="seconds")}
            db.run("UPDATE cases SET owner=?, level=?, level_since=?, status='Pending', route_basis=?, audit=?, taluk=?, gp=?, district=?, "
                   "village=CASE WHEN ?<>'' THEN ? ELSE village END WHERE id=?",
                   (target["id"], target["level"], now().isoformat(), f"Transferred by {who} (not their jurisdiction) to {target['short']}: {sug['how']}",
                    json.dumps(audit), new_taluk, new_gp or "", new_dist, pl.get("village") or "", pl.get("village") or "", cid))
            event(cid, who, f"Transferred to {target['short']}", "#0e9f6e",
                  f"Returned as not my jurisdiction ({why}); suggested: {sug['asked']} → {target['short']} ({sug['how']}). Clock restarted. Logged as a routing correction for the learning loop.")
            notify(target["id"], f"{cid} transferred to you by {who}: not their jurisdiction")
            message_citizen(cid, target["id"], "transferred", who)
            out.update(routed_to={"id": target["id"], "short": target["short"], "name": target["name"], "level": target["level"]},
                       how=sug["how"], scrutiny=False)
            out["toast"] = ["Transferred", f"{cid} → {target['short']} · notified"]
        else:
            note = why + (f" · suggested: {sug['asked']} (no matching officer" + (f": {sug['how']}" if sug.get("how") else "") + ")" if sug.get("asked") else "")
            event(cid, who, "Returned: not my jurisdiction", "#c98a00", note + ". Logged as a routing correction for the learning loop."); status("Scrutiny")
            message_citizen(cid, me["id"], "returned")
            out.update(scrutiny=True, suggestion_unmatched=sug.get("asked") or "", why_unmatched=sug.get("how") or "")
            out["toast"] = ["Returned", "Sent to the scrutiny desk for re-routing" + (" · the suggestion matched no officer" if sug.get("asked") else "")]
    elif a.action == "reject":
        if not a.reason:
            raise HTTPException(400, "a reason is mandatory")
        event(cid, who, "Rejected with reason", "#c8372d", a.reason + (f" · {a.note}" if a.note else "")); status("Rejected")
        message_citizen(cid, me["id"], "rejected", a.reason + (f" {a.note}" if a.note else ""))
        out["toast"] = ["Rejected", "Citizen told the reason and their right to appeal"]
    elif a.action == "resolve":
        if len((a.atr or "").strip()) < 15:
            raise HTTPException(400, "write the Action Taken Report (at least one sentence)")
        engine = "local check"
        try:
            if ai.status()["llm"]:
                score, reason = ai.check_atr(c["masked"], a.atr)
                engine = "Sakala AI"
            else:
                score, reason = ai.check_atr_local(a.atr)
        except Exception:  # noqa: BLE001
            score, reason = ai.check_atr_local(a.atr)
        out.update(score=score, reason=reason, engine=engine)
        if score >= 4:
            db.run("UPDATE cases SET atr=?, atr_score=?, atr_reason=? WHERE id=?", (a.atr, score, reason, cid))
            event(cid, who, "Resolved with ATR", "#1f9d57", f"AI resolution check {score}/5 ({engine})"); status("Resolved")
            message_citizen(cid, me["id"], "resolved", a.atr)
            out["toast"] = ["Resolved", f"{cid} closed · citizen asked to confirm on WhatsApp"]
        else:
            event(cid, "Sakala AI", "ATR flagged: not resolved", "#c98a00", f"AI resolution check {score}/5 · {reason}")
    elif a.action == "reroute":
        if c["status"] != "Scrutiny":
            raise HTTPException(409, "only scrutiny-desk cases can be re-routed")
        if c["kind"] == "APPLICATION":
            raise HTTPException(409, "Sakala applications follow the Designated → Competent → Appellate ladder, not the grievance desk")
        if me and me["level"] == "L1":
            raise HTTPException(403, "the scrutiny desk is the taluk / district level (L2, L3) or the Chief Secretary's office")
        target = officer(a.to)
        if not target:
            raise HTTPException(400, "choose the officer to send it to")
        audit = json.loads(c["audit"]) if c.get("audit") else {}
        audit["human_decision"] = {"by": who, "to": target["id"], "note": a.note, "at": now().isoformat(timespec="seconds")}
        db.run("UPDATE cases SET owner=?, level=?, level_since=?, status='Pending', route_basis=?, audit=? WHERE id=?",
               (target["id"], target["level"], now().isoformat(), f"Scrutiny desk decision by {who}" + (f": {a.note}" if a.note else ""), json.dumps(audit), cid))
        event(cid, who, f"Scrutiny desk: routed to {target['short']}", "#0e9f6e", a.note or "Human decision recorded as a routing correction")
        notify(target["id"], f"{cid} assigned to you by the scrutiny desk")
        message_citizen(cid, target["id"], "routed", "")
        out["toast"] = ["Re-routed", f"{cid} → {target['short']}"]
    elif a.action == "nudge":
        if c["status"] not in OPEN + ("Scrutiny",):
            raise HTTPException(409, f"case is {c['status']}")
        msg = (a.note or "").strip()[:200]     # the Chief Secretary's own words, when given (Sakala Mitra passes them)
        event(cid, "Chief Secretary’s office", "Reminder from Chief Secretary’s office", "#da6823", msg or "Officer and their senior notified")
        notify(c["owner"], f"Chief Secretary’s office asked for action on {cid}" + (f": {msg}" if msg else ""))
        out["toast"] = ["Nudge sent", f"{officer(c['owner'])['short']} has been reminded"]
    elif a.action == "comp_order":
        amt = compensation(c)
        event(cid, who, f"Compensation ₹{amt} ordered", "#da6823", "Paid to the citizen (Sakala Act s.9: ₹20/day, max ₹500)")
        message_citizen(cid, me["id"], "compensation", str(amt))
        out["toast"] = ["Compensation", f"₹{amt} ordered"]
    elif a.action == "comp_hrms":
        amt = compensation(c)
        event(cid, who, f"HRMS debit note ₹{amt} approved", "#6d4bc4", "Posted to HRMS (mock) after the officer's reply · s.11(4)")
        out["toast"] = ["HRMS (mock)", f"Debit note ₹{amt} posted for {officer(sk['DO'])['short']}"]
    else:
        raise HTTPException(400, "unknown action")
    return out


@app.post("/api/cases/{cid}/draft_atr")
def draft_atr(cid: str):
    c = db.q1("SELECT * FROM cases WHERE id=?", (cid,))
    if not c:
        raise HTTPException(404)
    if not ai.status()["llm"]:
        return {"text": "Inspected the site on [DATE] with [DETAIL]. The issue has been [DETAIL] and the citizen informed.", "engine": "template"}
    try:
        return {"text": ai.draft_atr({"officer": officer(c["owner"])["name"], "service": c["service"], "masked": c["masked"]}), "engine": "Sakala AI"}
    except Exception as e:  # noqa: BLE001
        return {"text": "Inspected the site on [DATE] with [DETAIL]. The issue has been [DETAIL] and the citizen informed.", "engine": "template", "error": str(e)[:120]}


# ---------------- AI mode (UC 20) ----------------
def run_tool(name, args):
    args = args or {}
    f = lambda v: str(v or "").lower()  # noqa: E731
    if name == "record":
        rid = str(args.get("id") or args.get("gid") or args.get("case_id") or "").strip().upper().replace(" ", "")
        gid = rid[3:] if rid.startswith("GR-") else rid
        rec = db.q1("SELECT * FROM ipgrs_records WHERE gid=?", (gid,))
        case = db.q1("SELECT c.*, o.short officer_short, o.name officer_name FROM cases c LEFT JOIN officers o ON o.id=c.owner WHERE c.id=? OR c.id=?", (rid, "GR-" + gid))
        if not rec and not case:
            return {"found": False, "id": rid}
        out = {"found": True, "id": rid}
        if rec:
            out["record"] = {"gid": rec["gid"], "complaint_masked": rec["text_masked"], "department": rec["dept"], "line_department": rec["line"],
                             "service": rec["service"], "grievance": rec["grievance"], "service_type": rec["service_type"], "district": rec["district"],
                             "taluk": rec["taluk"], "gp": rec["gp"], "village": rec["village"], "created": rec["created"], "status_in_ipgrs": rec["status"],
                             "officer_role": rec["role"], "pending_with": rec["officer"], "source": rec["source"]}
        if case:
            out["live_case"] = {"id": case["id"], "status": case["status"], "owner": case["officer_name"], "level": case["level"], "days_left": sla_info(case)["left"],
                                "service": case["service"], "taluk": case["taluk"], "gp": case["gp"], "district": case["district"], "atr": case["atr"],
                                "history": [{"t": e["t"], "who": e["who"], "what": e["what"], "note": e["note"]} for e in db.q("SELECT * FROM case_events WHERE case_id=? ORDER BY t, id", (case["id"],))][-8:]}
        return out
    if name == "query_cases":
        rows = db.q("SELECT c.*, o.short officer FROM cases c LEFT JOIN officers o ON o.id=c.owner")
        if args.get("dept_code"): rows = [r for r in rows if r["dept_code"] == str(args["dept_code"]).upper()]
        if args.get("district"): rows = [r for r in rows if f(r["district"]).startswith(f(args["district"])[:6])]
        if args.get("taluk"): rows = [r for r in rows if f(r["taluk"]) == f(args["taluk"])]
        if args.get("status"): rows = [r for r in rows if f(r["status"]) == f(args["status"])]
        if args.get("service_contains"): rows = [r for r in rows if f(args["service_contains"]) in f(r["service"]) + " " + f(r["grievance"])]
        if args.get("officer_contains"): rows = [r for r in rows if f(args["officer_contains"]) in f(r["officer"])]
        if args.get("overdue_only"): rows = [r for r in rows if r["status"] in OPEN and sla_info(r)["left"] < 0]
        if args.get("list"):
            rows.sort(key=lambda r: (r["status"] not in OPEN, sla_info(r)["left"]))
            return {"total": len(rows), "open": sum(1 for r in rows if r["status"] in OPEN),
                    "cases": [{"id": r["id"], "service": r["service"], "department": r["dept_code"], "officer": r["officer"], "status": r["status"],
                               "district": r["district"], "taluk": r["taluk"], "gp": r["gp"], "days_left": sla_info(r)["left"], "complaint": (r["masked"] or "")[:140]}
                              for r in rows[:25]]}
        g = args.get("group_by", "none")
        key = {"officer": "officer", "service": "service", "taluk": "taluk", "district": "district", "level": "level", "status": "status", "source": "src", "dept": "dept_code"}.get(g)
        if key:
            names = {"REV": "Revenue", "RDPR": "RDPR", "FOOD": "Food & Civil Supplies", "camp": "Praja Seva camp", "csc": "Citizen Service Centre",
                     "web": "iPGRS website", "app": "Mobile App", "call": "1902 call centre", "rdpr": "RDPR call centre", "whatsapp": "WhatsApp",
                     "mitra": "Mitra (voice)"}
            agg = {}
            for r in rows:
                k = names.get(r[key], r[key]) or "Scrutiny desk"
                agg[k] = agg.get(k, 0) + 1
            return {"total": len(rows), "groups": sorted(agg.items(), key=lambda x: -x[1])[:15]}
        return {"total": len(rows), "open": sum(1 for r in rows if r["status"] in OPEN),
                "sample": [{"id": r["id"], "service": r["service"], "officer": r["officer"], "status": r["status"], "taluk": r["taluk"], "gp": r["gp"],
                            "days_left": sla_info(r)["left"]} for r in rows[:10]]}
    if name == "real_records":
        col = {"dept": "dept", "service": "service", "district": "district", "taluk": "taluk", "source": "source", "status": "status", "role": "role"}.get(args.get("group_by"), "dept")
        where, a = ["1=1"], []
        if args.get("district"): where.append("lower(district) LIKE ?"); a.append(str(args["district"]).lower()[:6] + "%")
        if args.get("taluk"): where.append("lower(taluk)=?"); a.append(str(args["taluk"]).lower())
        if args.get("dept_code"): where.append("dept_code=?"); a.append(str(args["dept_code"]).upper())
        if args.get("status"): where.append("lower(status) LIKE ?"); a.append("%" + str(args["status"]).lower()[:8] + "%")
        if args.get("service_contains"): where.append("(lower(service) LIKE ? OR lower(grievance) LIKE ?)"); a += ["%" + str(args["service_contains"]).lower() + "%"] * 2
        total = db.q1(f"SELECT COUNT(*) n FROM ipgrs_records WHERE {' AND '.join(where)}", a)["n"]
        if args.get("list"):
            recs = db.q(f"SELECT gid, text_masked, dept, service, grievance, district, taluk, gp, status, officer, source, created FROM ipgrs_records "
                        f"WHERE {' AND '.join(where)} ORDER BY created DESC LIMIT 25", a)
            return {"total": total, "records": [{"gid": r["gid"], "complaint": (r["text_masked"] or "")[:140], "department": r["dept"], "service": r["service"],
                                                 "grievance": r["grievance"], "district": r["district"], "taluk": r["taluk"], "gp": r["gp"],
                                                 "status": r["status"], "pending_with": r["officer"], "source": r["source"], "created": r["created"]} for r in recs]}
        rows = db.q(f"SELECT {col} k, COUNT(*) n FROM ipgrs_records WHERE {' AND '.join(where)} GROUP BY {col} ORDER BY n DESC LIMIT 15", a)
        return {"groups": [(r["k"], r["n"]) for r in rows], "total": total}
    if name == "sakala_2025":
        t = analytics.sakala_tracker()
        monthly = [{"month": m["month"], "overdue": int(m["overdue"]), "late_pct": m["late_pct"], "rej_pct": m["rej_pct"]} for m in t["monthly"]]
        if args.get("district"):
            d = [x for x in t["districts"] if x["district"].lower().startswith(str(args["district"]).lower()[:5])]
            return {"state": t["state"], "district": d, "monthly_state": monthly}
        return {"state": t["state"], "worst_late": t["districts"][:8], "best_late": t["districts"][-5:], "monthly": monthly}
    if name == "insights":
        k = args.get("kind", "hotspots")
        if k == "hotspots": return analytics.hotspots()
        if k == "scrutiny": return {s: n for s, n in analytics.historical()["scrutiny_stuck"].items()}
        if k == "vulnerable": return {"open_vulnerable": db.q1("SELECT COUNT(*) n FROM cases WHERE vulnerable=1 AND status IN ('Pending','In progress','Info requested')")["n"]}
        if k == "escalations": return {"auto_escalated_cases": db.q1("SELECT COUNT(DISTINCT case_id) n FROM case_events WHERE what LIKE 'Auto-escalated%'")["n"]}
    return {"error": "unknown tool"}


class Ask(BaseModel):
    q: str


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def build_chart(question, results):
    """Chart spec built ONLY from tool results (never from the model's text)."""
    q = question.lower()
    trend = any(w in q for w in ("trend", "month", "over time", "ತಿಂಗಳ"))
    short = lambda x: (str(x)[:26] + "…") if len(str(x)) > 27 else str(x)  # noqa: E731
    for r in results:
        res, tool = r.get("result") or {}, r.get("tool")
        if tool == "sakala_2025" and isinstance(res, dict):
            res = dict(res)
            res["monthly"] = res.get("monthly") or res.get("monthly_state")
            if trend and res.get("monthly"):
                rej = "reject" in q
                late = "late" in q
                key, lab, unit = ("rej_pct", "Rejected", "%") if rej else ("late_pct", "Delivered late", "%") if late else ("overdue", "Overdue applications", "")
                return {"type": "line", "labels": [MONTHS[m["month"] - 1] for m in res["monthly"]], "values": [m[key] for m in res["monthly"]],
                        "series_label": lab, "unit": unit, "title": f"{lab} · month by month, 2025", "source": "Sakala district performance reports, Jan–Dec 2025"}
            rows = res.get("worst_late") or res.get("district")
            if rows and len(rows) >= 2:
                return {"type": "bar", "labels": [d["district"] for d in rows], "values": [d["late_pct"] for d in rows], "series_label": "Delivered late",
                        "unit": "%", "title": "Late delivery by district, 2025", "source": "Sakala district performance reports, 2025"}
        groups = res.get("groups") if isinstance(res, dict) else None
        if groups and len(groups) >= 2:
            groups = [g for g in groups if g[0] not in (None, "", "—")][:12]
            what = (r.get("args") or {}).get("group_by", "")
            src = "9,999 real iPGRS grievances, 3–9 Oct 2026" if tool == "real_records" else "Live pilot cases · Mysuru district"
            return {"type": "bar", "labels": [short(g[0]) for g in groups], "full": [str(g[0]) for g in groups], "values": [g[1] for g in groups],
                    "series_label": "Cases", "unit": "", "title": f"Cases by {({'dept': 'department', 'source': 'channel', 'src': 'channel', 'level': 'escalation level'}).get(what, what or 'group')}", "source": src}
        if tool == "insights" and isinstance(res, dict) and (res.get("open") or res.get("week")):
            rows = (res.get("open") or res.get("week"))[:10]
            return {"type": "bar", "labels": [short(f"{x['gp']} · {x['service']}") for x in rows], "full": [f"{x['gp']} GP, {x['taluk']} · {x['service']}" for x in rows],
                    "values": [x["n"] for x in rows], "series_label": "Repeated complaints", "unit": "", "title": "Hotspots · same service, same GP", "source": "Live pilot cases"}
        if tool == "insights" and isinstance(res, dict) and res and all(isinstance(v, int) for v in res.values()) and len(res) >= 2:
            return {"type": "bar", "labels": [short(k) for k in res], "full": list(res), "values": list(res.values()), "series_label": "Waiting in scrutiny",
                    "unit": "", "title": "Complaints stuck in manual scrutiny, by channel", "source": "9,999 real iPGRS grievances"}
    return None


_BY_RX = re.compile(r"\bby (department|dept|district|taluk|officer|service|status|channel|source|level)\b|\b(per|across) (department|district|taluk|officer)s?\b", re.I)


def ensure_groups(question, results):
    """A 'by X' question always gets a deterministic grouping (so the chart never depends on how the model phrased its plan)."""
    if any(isinstance(r.get("result"), dict) and r["result"].get("groups") for r in results):
        return results
    m = _BY_RX.search(question or "")
    if not m:
        return results
    key = (m.group(1) or m.group(3) or "").lower()
    key = {"dept": "dept", "department": "dept", "channel": "source"}.get(key, key)
    q = (question or "").lower()
    dist = next((d for d in ("bagalkote", "ballari", "belagavi", "bengaluru rural", "bengaluru south", "bengaluru urban", "bidar", "chamarajanagara",
                             "chikkaballapura", "chikkamagaluru", "chitradurga", "dakshina kannada", "davangere", "dharwad", "gadag", "hassan", "haveri",
                             "kalaburagi", "kodagu", "kolar", "koppal", "mandya", "mysuru", "raichur", "shivamogga", "tumakuru", "udupi", "uttara kannada",
                             "vijayanagar", "vijayapura", "yadgir") if d[:6] in q), "")
    historical = any(w in q for w in ("grievances came", "records", "historical", "9,999", "9999", "sample", "all departments", "ipgrs"))
    if historical or key in ("source", "status") and "pending" not in q:
        args = {"group_by": key if key in ("dept", "service", "district", "taluk", "source", "status") else "dept"}
        if dist:
            args["district"] = dist
        results.append({"tool": "real_records", "args": args, "result": run_tool("real_records", args), "added": "deterministic grouping"})
    else:
        args = {"group_by": key if key in ("officer", "service", "taluk", "district", "dept", "level", "status", "source") else "dept"}
        if dist:
            args["district"] = dist
        if "pending" in q or "open" in q:
            args["status"] = "Pending"
        results.append({"tool": "query_cases", "args": args, "result": run_tool("query_cases", args), "added": "deterministic grouping"})
    return results


@app.post("/api/ask")
def ask(a: Ask):
    if not ai.status()["llm"] or not a.q.strip():
        return {"engine": "local"}
    try:
        r = ai.ask(a.q[:500], run_tool)
        results = ensure_groups(a.q, r.get("results", []))
        return {"engine": "ai", "html": r["html"], "tools": r["tools"], "chart": build_chart(a.q, results)}
    except Exception as e:  # noqa: BLE001
        return {"engine": "local", "error": str(e)[:160]}


# ---------------- leadership intelligence ----------------
@app.get("/api/insights/quality")
def quality():
    return analytics.data_quality()


@app.get("/api/insights/misrouting")
def misrouting():
    return analytics.misrouting()


@app.get("/api/insights/historical")
def historical(summary: bool = False):
    h = analytics.historical()
    if summary and ai.status()["llm"]:
        try:
            h["summary"] = ai.brief("historical", "Summarise these Praja Seva / iPGRS patterns for the Chief Secretary in 4 bullet points: "
                                                  "channels, where complaints get stuck, top issues, vulnerable citizens.", h)
        except Exception:  # noqa: BLE001
            pass
    return h


@app.get("/api/insights/hotspots")
def hotspots(fix: bool = False):
    h = analytics.hotspots()
    if fix and ai.status()["llm"]:
        try:
            h["fixes"] = analytics.hotspot_fixes(h["open"] or h["week"])
        except Exception:  # noqa: BLE001
            h["fixes"] = []
    return h


@app.get("/api/insights/accuracy")
def accuracy(run: bool = False, n: int = 40):
    return analytics.accuracy(run_llm=run, n=max(10, min(n, 120)))


@app.get("/api/sakala/tracker")
def tracker():
    return analytics.sakala_tracker()


@app.get("/api/sakala/early_warning")
def early_warning():
    return analytics.early_warning()


@app.get("/api/review_pack")
def review_pack(level: str = "cs", officer_id: str = ""):
    return analytics.review_pack(level, officer_id)


@app.get("/api/e4")
def e4():
    return analytics.e4_defaulters()


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 5_000_000:
        raise HTTPException(413, "file too large (5 MB max)")
    try:
        return analytics.upload(data, file.filename or "upload.xlsx")
    except ValueError as e:
        raise HTTPException(400, str(e))


class Audio(BaseModel):
    audio_b64: str
    lang: str = "en"


@app.post("/api/transcribe")
def transcribe(a: Audio):
    """Speech to text for the AI-mode microphone (same model as WhatsApp voice notes)."""
    import base64
    try:
        return {"text": ai.transcribe(base64.b64decode(a.audio_b64), "kn" if a.lang == "kn" else "en")}
    except Exception as e:  # noqa: BLE001
        return {"text": "", "error": str(e)[:120]}


@app.get("/api/health")
def health():
    return {"ok": True, "time": datetime.now().isoformat(), "ai": ai.status(), "local_model": local_ai.ready()}


# ---------------- Sakala Mitra intake: the voice agent as its own input channel ----------------
# Additive. The WhatsApp engine (chat.py) is untouched; this is a second door into the same pipeline
# (privacy shield, AI understanding, completion, validation, exact-officer routing, clock, dashboards).
from . import pipeline as _pl                                   # noqa: E402
from .routing import gp_list as _gp_list, resolve_place as _resolve_place, route as _route   # noqa: E402


class Intake(BaseModel):
    session: str
    step: str = "understand"          # understand | place | create | apply | reply | feedback | appeal | messages | mine
    text: str = ""
    image_b64: str = ""
    media_type: str = "image/png"
    channel: str = "mitra"
    lang: str = "en"
    u: dict | None = None
    taluk: str = ""
    gp: str = ""
    village: str = ""
    how: str = ""
    case_id: str = ""
    defer_scrutiny: bool = False      # Mitra: report UNCLEAR without filing; it asks the citizen first
    answer: str = ""
    key: str = ""
    name: str = ""
    file_b64: str = ""                # the document door: a PDF / PNG / JPG of a written complaint
    filename: str = ""
    doc: dict | None = None           # the reviewed form (complainant details, not-provided fields, evidence) stored with the case


_MUNICIPAL_RX = re.compile(r"\b(municipal|municipality|city corporation|town panchayat|nagara ?sabhe|purasabhe|cmc|tmc|bbmp|ward no)\b|ನಗರಸಭೆ|ಪುರಸಭೆ|ಮಹಾನಗರ ಪಾಲಿಕೆ|ಪಟ್ಟಣ ಪಂಚಾಯಿತಿ", re.I)


def _doc_rules(u: dict, f: dict, rec: dict | None) -> dict:
    """Deterministic guardrails on a read letter: the iPGRS record it quotes is official evidence of its department (a record outside
    the three pilot departments means the letter is outside the pilot, whatever the words suggest), and a letter addressed to a
    municipal body is an urban matter, not a Gram Panchayat one. Both go to the scrutiny desk with the letter, never to a wrong officer."""
    u = dict(u)
    pilot = {"REV", "RDPR", "FOOD"}
    if rec:
        u["record"] = rec["gid"]
        if (rec.get("dept_code") or "") not in pilot and rec.get("dept"):
            if u.get("intent") in ("GRIEVANCE", "UNCLEAR"):
                u.update(intent="OUT_OF_SCOPE", dept=rec["dept"], line=rec.get("line") or "", conf=0.98, engine="llm+rules",
                         reason=f"The letter quotes iPGRS grievance {rec['gid']}, filed under the {rec['dept']} ({rec.get('service') or rec.get('grievance')}), outside the three pilot departments.")
                u["why"] = u["reason"]
            return u
    to = " ".join(str(f.get(k) or "") for k in ("addressed_to", "complainant_address", "address"))
    if u.get("intent") == "GRIEVANCE" and _MUNICIPAL_RX.search(to) and not re.search(r"gram|grama|panchayat|ಗ್ರಾಮ", to, re.I):
        u.update(intent="OUT_OF_SCOPE", dept="Urban Development Department", line="", conf=0.9, engine="llm+rules",
                 reason=f"Addressed to {f.get('addressed_to') or 'a municipal body'}: an urban local body matter, outside the three pilot departments.")
        u["why"] = u["reason"]
    return u


def _place_block(u, place=None, taluk=""):
    """What the completion agent still needs, plus the officer preview once the place is known."""
    out = {}
    if place:
        out["place"] = place
        dup = _pl.find_duplicate(u, place.get("gp") or "")
        out["duplicate"] = dup["id"] if dup else None
        rt = _route(u["service_id"], place["taluk"], place.get("gp") or "")
        if rt and rt.get("officer"):
            o = officer(rt["officer"])
            if o:
                ch = sla.chain(rt["officer"])
                out["preview"] = {"officer": {"id": o["id"], "name": o["name"], "short": o["short"], "level": o["level"]},
                                  "chain": [{"lv": x["level"], "short": x["short"]} for x in ch], "basis": rt["basis"],
                                  "days": SLA_DAYS.get(o["level"], 7), "fallback": rt["fallback"]}
        return out
    if taluk:
        rt = _route(u["service_id"], taluk, "")
        if rt and not rt["need_gp"]:
            return _place_block(u, {"village": "", "gp": "", "taluk": taluk, "how": "taluk named in the request"})
        out.update(need="gp", taluk=taluk, gp_options=_gp_list(taluk)[:12])
        return out
    out.update(need="place", taluks=sorted(chat.gp_taluks()))
    return out


@app.post("/api/intake")
def intake(r: Intake):
    s = r.step
    if s == "understand":
        text = r.text.strip()
        if r.image_b64:
            try:
                text = ai.read_petition(r.image_b64, r.media_type or "image/png") if ai.status()["llm"] else ""
            except Exception:  # noqa: BLE001
                text = ""
            if not text:
                return {"step": s, "ok": False, "reason": "unreadable_image"}
        if not text:
            return {"step": s, "ok": False, "reason": "empty"}
        masked, n, u = _pl.understand(text)
        out = {"step": s, "ok": True, "text": text, "masked": masked, "masked_items": n, "engine": _pl.engine_label(u),
               "u": {k: v for k, v in u.items() if k != "similar"}}
        try:
            b = analytics.gsc_bridge(text)
            if b and b.get("gsc"):
                if b.get("found"):
                    c = db.q1("SELECT session FROM cases WHERE id=? OR id=?", (b["gsc"], "SK-" + b["gsc"]))
                    if not c or c["session"] != r.session:          # guardrail 9
                        b = {k: b[k] for k in ("gsc", "payment_issue", "advice")} | {"found": False}
                out["gsc"] = b
        except Exception:  # noqa: BLE001
            pass
        if u["intent"] == "GRIEVANCE":
            tk = chat.taluk_in_text(text, u.get("taluk_text", ""))
            place = _pl.locate(text, u)
            if place and tk and place["taluk"] != tk:      # a taluk named outright beats a same-named village elsewhere
                place = None
            if place:
                out.update(_place_block(u, {**place, "how": "village named in the request"}))
            else:
                out.update(_place_block(u, taluk=tk))
        elif u["intent"] == "SERVICE_REQUEST":
            svc = db.q1("SELECT * FROM sakala_services WHERE key=?", (u.get("sakala_key"),))
            if svc:
                out["service"] = {"key": svc["key"], "name": svc["name"], "days": svc["days"], "checklist": json.loads(svc["checklist"] or "[]")}
        elif u["intent"] == "UNCLEAR":
            if r.defer_scrutiny:
                out["scrutiny_pending"] = True
            else:
                out["case_id"] = _pl.scrutiny_case(text, masked, u, r.channel, r.session)
        return out
    if s == "document":                    # the document door: a written complaint read into the form, then the same pipeline
        if not r.file_b64:
            raise HTTPException(400, "file_b64 needed")
        import base64 as _b64
        try:
            data = _b64.b64decode(r.file_b64)
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "bad file")
        if len(data) > 30 * 1024 * 1024:
            return {"step": s, "ok": False, "reason": "too_big"}
        rd = docread.read(data, r.media_type or "application/pdf", r.filename)
        if not rd.get("ok"):
            return {"step": s, "ok": False, "reason": rd.get("reason", "unreadable"), "detail": rd.get("detail", ""), "transcript": rd.get("transcript", "")}
        f = rd["fields"]
        text = (f.get("description") or rd["transcript"]).strip()
        rec = rd.get("record")                                       # the letter's own iPGRS number found in the real records: retrieved evidence
        masked, n, u = _pl.understand(rd["english"] if rd["english"] and rd["english"] != text else text, hint=rd.get("hint") or "")
        if rd["english"] and rd["english"] != text:
            masked, n = _pl.mask(text)[0], _pl.mask(text)[1]          # the case keeps the citizen's own words (masked)
        u = _doc_rules(u, f, rec)
        out = {"step": s, "ok": True, "text": text, "english": rd["english"], "masked": masked, "masked_items": n, "engine": _pl.engine_label(u),
               "u": {k: v for k, v in u.items() if k != "similar"}, "reader": rd["engine"], "pages": rd["pages"], "thumbs": rd["thumbs"],
               "fields": f, "confidence": rd["confidence"], "flags": rd["flags"], "evidence": rd["evidence"], "several": rd["several"],
               "transcript": (rd.get("transcript") or "")[:6000], "rotation": rd.get("rotation", 0), "language": rd.get("language", ""),
               "record": rec, "ms_look": rd.get("ms_look"),
               "missing": docread.missing(f), "filename": r.filename, "ms": rd["ms"],
               "form": {"steps": [{"id": st["id"], "title": st["title"], "fields": [{"key": x["key"], "label": x["label"], "required": x.get("required", False)} for x in st["fields"]]} for st in docread.FORM["steps"]]}}
        if u["intent"] == "GRIEVANCE":
            if rd.get("place"):
                out.update(_place_block(u, rd["place"]))
            else:
                out.update(_place_block(u, taluk=rd.get("taluk") or ""))
        else:
            out["taluk"] = (rd.get("place") or {}).get("taluk") or rd.get("taluk") or ""     # picks the scrutiny desk of that taluk
        return out
    if s == "scrutiny":                    # the citizen agreed: send an unclear request to the human scrutiny desk
        from .privacy import mask as _mask
        text = (r.text or "").strip()
        if not text:
            raise HTTPException(400, "text needed")
        u = dict(r.u or {}); u.setdefault("intent", "UNCLEAR")
        tk = chat.taluk_in_text(r.taluk) if r.taluk else ""        # the taluk on the letter (any wording, Kannada too) picks the desk
        cid = _pl.scrutiny_case(text, _mask(text)[0], u, r.channel, r.session, taluk=tk or "")
        if r.doc:                                              # the document door: the letter and its form stay with the case
            d = dict(r.doc)
            d["not_provided"] = [k for k in ("name", "phone", "complainant_address", "pincode", "since", "letter_date") if not str(d.get(k) or "").strip()]
            db.run("UPDATE cases SET doc=? WHERE id=?", (json.dumps(d, ensure_ascii=False), cid))
            event(cid, "Sakala AI", f"Written complaint read from {d.get('filename') or 'a document'}", "#6d4ce6",
                  f"{d.get('pages', 1)} page(s) · {d.get('reader') or 'document reader'} · complainant {d.get('name') or 'not given'}"
                  + (f" · {d['phone'][:2]}XXXXXX{d['phone'][-2:]}" if d.get("phone") else " · no phone given")
                  + (f" · iPGRS record {d['record']} quoted in the letter" if d.get("record") else "")
                  + (f" · not in the letter: {', '.join(d['not_provided'])}" if d["not_provided"] else ""))
        return {"ok": True, "case_id": cid}
    if s == "place":                       # the citizen named a village / GP / taluk (or picked one)
        u = r.u or {}
        if r.gp and r.taluk:
            return {"step": s, "ok": True, **_place_block(u, {"village": r.village or r.gp, "gp": r.gp, "taluk": r.taluk, "how": r.how or "picked from the list"})}
        place, named_tk = chat.place_reply(r.text, r.taluk)   # the same completion step WhatsApp uses
        if place:
            return {"step": s, "ok": True, **_place_block(u, {**place, "how": "village named by the citizen"})}
        tk = named_tk or r.taluk
        if tk:
            return {"step": s, "ok": True, **_place_block(u, taluk=tk)}
        return {"step": s, "ok": False, "reason": "unknown_place", **_place_block(u)}
    if s == "create":
        u = r.u or {}
        masked = _pl.mask(r.text)[0]
        dup = _pl.find_duplicate(u, r.gp)
        place = {"village": r.village, "gp": r.gp, "taluk": r.taluk}
        res = _pl.create_grievance(r.text, masked, u, r.channel, r.taluk, r.gp, r.village, session=r.session,
                                   dup=dup["id"] if dup else None, how=r.how or "voice", place=place)
        if r.doc and res.get("id"):                            # the document door: the reviewed form stays with the case
            d = dict(r.doc)
            d["not_provided"] = [k for k in ("name", "phone", "complainant_address", "pincode", "since", "letter_date") if not str(d.get(k) or "").strip()]
            db.run("UPDATE cases SET doc=? WHERE id=?", (json.dumps(d, ensure_ascii=False), res["id"]))
            event(res["id"], "Sakala AI", f"Written complaint read from {d.get('filename') or 'a document'}", "#6d4ce6",
                  f"{d.get('pages', 1)} page(s) · {d.get('reader') or 'document reader'} · complainant {d.get('name') or 'not given'}"
                  + (f" · {d['phone'][:2]}XXXXXX{d['phone'][-2:]}" if d.get("phone") else " · no phone given")
                  + (f" · iPGRS record {d['record']} quoted in the letter" if d.get("record") else "")
                  + (f" · not in the letter: {', '.join(d['not_provided'])}" if d["not_provided"] else ""))
        return {"step": s, "ok": True, **res, "duplicate": dup["id"] if dup else None}
    if s == "apply":
        svc = db.q1("SELECT * FROM sakala_services WHERE key=?", (r.key,))
        if not svc:
            return {"step": s, "ok": False, "reason": "unknown_service"}
        cid = sla.create_application(r.key, r.name or "Applicant", r.gp, r.taluk, r.channel, session=r.session,
                                     doc_note="filed by voice through Mitra")
        c = db.q1("SELECT * FROM cases WHERE id=?", (cid,))
        sk = json.loads(c["sakala"])
        do = officer(sk["DO"]) or {}
        return {"step": s, "ok": True, "id": cid, "service": svc["name"], "days": svc["days"], "due": sk["complete"],
                "officer": {"id": do.get("id"), "name": do.get("name"), "short": do.get("short"), "level": do.get("level")},
                "chain": [{"lv": "Designated", "short": do.get("short")}, {"lv": "Competent", "short": (officer(sk["CO"]) or {}).get("short")},
                          {"lv": "Appellate", "short": (officer(sk["AA"]) or {}).get("short")}]}
    c = db.q1("SELECT * FROM cases WHERE id=? AND session=?", (r.case_id, r.session)) if r.case_id else None
    if s == "reply":
        if not c:
            return {"step": s, "ok": False, "reason": "not_yours"}
        masked = _pl.mask(r.text)[0]
        event(c["id"], "Citizen (Mitra)", "Citizen replied", "#128c4b", masked)
        if c["status"] == "Info requested":
            db.run("UPDATE cases SET status='In progress' WHERE id=?", (c["id"],))
        notify(c["owner"], f"Citizen replied on {c['id']}: {masked[:80]}")
        return {"step": s, "ok": True, "officer": officer(c["owner"])["short"]}
    if s == "feedback":
        if not c:
            return {"step": s, "ok": False, "reason": "not_yours"}
        if not sla.feedback_pending(c):
            return {"step": s, "ok": False, "reason": "nothing_to_answer", "status": c["status"]}
        return {"step": s, "ok": True, **sla.citizen_verdict(c, r.answer == "yes", "Citizen (Mitra)", "Mitra (voice)")}
    if s == "appeal":
        c = db.q1("SELECT * FROM cases WHERE session=? AND status='Rejected' ORDER BY created DESC LIMIT 1", (r.session,))
        if not c:
            return {"step": s, "ok": False, "reason": "nothing_to_appeal"}
        cur = officer(c["owner"])
        up = officer(json.loads(c["sakala"])["CO"]) if c["kind"] == "APPLICATION" else officer(cur["up_id"]) if cur and cur["up_id"] else None
        if not up:
            return {"step": s, "ok": False, "reason": "top_level", "id": c["id"]}
        db.run("UPDATE cases SET owner=?, level=?, level_since=?, status='Pending' WHERE id=?", (up["id"], up["level"], now().isoformat(), c["id"]))
        event(c["id"], "Citizen (Mitra)", f"Appealed to {up['short']}", "#6d4ce6", "Citizen used the appeal right after a rejection")
        notify(up["id"], f"Appeal on {c['id']} from the citizen (rejected by {cur['short'] if cur else '-'})")
        return {"step": s, "ok": True, "id": c["id"], "to": up["short"]}
    if s == "messages":                    # officer -> citizen messages not yet heard by this session
        rows = db.q("SELECT * FROM citizen_msgs WHERE session=? AND delivered=0 ORDER BY id", (r.session,))
        out = []
        for m in rows:
            off = officer(m["officer_id"]) or {"short": "Sakala desk", "name": "Sakala desk", "id": ""}
            case = db.q1("SELECT * FROM cases WHERE id=?", (m["case_id"],)) or {}
            upo = officer((officer(case.get("owner")) or {}).get("up_id") or "") if case else None
            if case.get("kind") == "APPLICATION" and case.get("sakala"):
                upo = officer(json.loads(case["sakala"]).get("CO", "")) or upo
            out.append({"id": m["id"], "kind": m["kind"], "case_id": m["case_id"], "t": m["t"], "text": m["text"] or "",
                        "officer": off["short"], "officerFull": off["name"], "up": (upo or {}).get("short", "the senior officer"),
                        "service": case.get("service") or ""})
            db.run("UPDATE citizen_msgs SET delivered=1 WHERE id=?", (m["id"],))
        return {"step": s, "ok": True, "messages": out}
    if s == "mine":
        rows = all_cases(r.session, "citizen")
        out = []
        for c in rows:
            row = db.q1("SELECT * FROM cases WHERE id=?", (c["id"],))
            info = sla_info(row)
            out.append({"id": c["id"], "service": c["u"]["svc"] or "Scrutiny desk", "status": c["status"], "owner": c["owner"],
                        "ownerShort": (officer(c["owner"]) or {}).get("short", ""), "level": c["level"], "left": info["left"],
                        "total": info["total"], "legal": info["legal"], "created": c["created"], "gp": c["gp"], "taluk": c["taluk"],
                        "kind": c["u"]["type"], "last": (c["history"] or [{}])[-1].get("what", ""),
                        "atr": row["atr"] or "", "feedback_pending": sla.feedback_pending(row),
                        "chain": [{"lv": x["level"], "short": x["short"]} for x in sla.chain(c["owner"])]})
        return {"step": s, "ok": True, "cases": list(reversed(out))}
    raise HTTPException(400, "unknown step")


class QueryReq(BaseModel):
    tool: str
    args: dict = {}


@app.post("/api/query")
def query_api(req: QueryReq):
    """Deterministic data answers (case / G.Id lookup, filtered caseload, iPGRS records, officers, places, statewide, Sakala 2025)
    for Sakala Mitra's voice questions. Read-only."""
    from . import query
    return query.run(req.tool, req.args)


@app.get("/api/changes")
def changes(after_event: int = 0, after_notif: int = 0, limit: int = 200):
    """Cheap change feed for live screens: new case events and notifications since the given ids."""
    ev = db.q("SELECT e.id, e.case_id, e.t, e.who, e.what, e.note, c.status, c.owner, c.level, c.service, c.taluk, c.gp, c.src, c.session "
              "FROM case_events e JOIN cases c ON c.id=e.case_id WHERE e.id>? ORDER BY e.id LIMIT ?", (after_event, limit))
    nf = db.q("SELECT id, officer_id, t, msg FROM notifications WHERE id>? ORDER BY id LIMIT ?", (after_notif, limit))
    last_e = db.q1("SELECT MAX(id) m FROM case_events")["m"] or 0
    last_n = db.q1("SELECT MAX(id) m FROM notifications")["m"] or 0
    return {"now": now().isoformat(), "events": ev, "notifs": nf, "last_event": last_e, "last_notif": last_n}


@app.get("/docupload.js")
def docupload_js():
    return FileResponse(WEB / "docupload.js", media_type="application/javascript", headers={"Cache-Control": "no-store"})


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/dbg")
def dbg():
    p = WEB / "dbg.html"            # headless test page (only exists on the developer machine)
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")
app.mount("/samples", StaticFiles(directory=WEB / "samples"), name="samples")
