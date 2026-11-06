"""The 8-stage Sakala AI pipeline, shared by every channel (WhatsApp, call centre, camps, CSC counters, app).

1 Entry · 2 Privacy shield · 3 AI understanding · 4 Completion agent · 5 Validate & confirm
6 Exact-officer routing · 7 Deadlines & reminders · 8 Leadership view
"""
import json
import re
from datetime import timedelta

from . import ai, db, local_ai
from .privacy import mask
from .routing import route, resolve_place
from .sla import now, officer, chain, next_id, insert_case, event, notify, sla_info
from .config import SLA_DAYS

STAGES = [("Entry", "WhatsApp · one number for every citizen"),
          ("Privacy shield", "Phone, Aadhaar, ration-card numbers masked"),
          ("AI understanding", "Department → Line dept → Service → Grievance"),
          ("Completion agent", "Asks only for what is missing"),
          ("Validate & confirm", "Location, duplicates, citizen confirms"),
          ("Exact-officer routing", "Village / GP → named field officer"),
          ("Deadlines & reminders", "Clock starts · escalation chain armed"),
          ("Leadership view", "Live on the officer & Chief Secretary screens")]
DEPT_SHORT = {"REV": "Revenue", "RDPR": "RDPR", "FOOD": "Food & Civil Supplies"}
LOW_CONF_DEFAULT = 0.55


def low_conf():
    """Auto-route threshold: tuned from the last accuracy run on real data (analytics.llm_eval), else 0.55."""
    return float(db.kv_get("low_conf", LOW_CONF_DEFAULT))


def understand(text, hint=""):
    """Stages 2–3. Returns (masked, n_masked, u). hint = retrieved evidence (a written letter's matching iPGRS record)."""
    masked, n = mask(text)
    u = None
    rules = []
    if ai.status()["llm"]:
        try:
            u = ai.understand(masked, hint=hint) if hint else ai.understand(masked)
            # guardrail: the keyword wrong-door / out-of-scope checks are high precision; keep them authoritative
            lu = local_ai.understand(masked)
            # high-precision keyword checks stay authoritative: RTI, other departments, new-service applications
            if lu["intent"] in ("WRONG_DOOR", "OUT_OF_SCOPE", "SERVICE_REQUEST") and u["intent"] != lu["intent"]:
                rules.append(f"rule override: model said {u['intent']}, keyword rule says {lu['intent']}")
                lu.update(engine="llm+rules", summary=u.get("summary", ""))
                u = lu
            # second opinion the other way: the model is unsure ("we haven't had water for a week") but the offline model, trained on
            # the real iPGRS records, is confident about a real grievance -> take it (junk stays unclear: the offline model is not sure of it)
            if u["intent"] == "UNCLEAR" and lu["intent"] == "GRIEVANCE" and lu.get("conf", 0) >= max(0.6, low_conf()):
                rules.append(f"second opinion: model unsure, offline model confident ({lu['conf']:.2f}) on {lu.get('service')}")
                lu.update(engine="llm+rules", summary=u.get("summary") or lu.get("summary", ""))
                u = lu
            # low confidence never routes silently: a person at the scrutiny desk sees the top-3 options
            # second opinion: if the offline model finds nothing similar in the real data and disagrees, do not trust a high self-score
            _kw = {w for w in re.findall(r"[a-z]{4,}", (u.get("service") or "").lower())} - {"provision", "issue", "maintenance", "services", "service", "other", "scheme", "schemes", "related", "under"}
            _said = set(re.findall(r"[a-z]{4,}", masked.lower()))
            if u["intent"] == "GRIEVANCE" and lu["intent"] == "UNCLEAR" and u["service"] not in local_ai.alternatives(masked, 3) and not (_kw & _said):
                rules.append("second opinion: offline model found nothing similar and disagrees; confidence capped")
                u["conf"] = min(u["conf"], low_conf() - 0.05)
            if u["intent"] == "GRIEVANCE" and u.get("conf", 1) < low_conf():
                rules.append(f"confidence {u['conf']:.2f} below the tuned threshold {low_conf():.2f}: human decides")
                alts = [u["service"]] + [a for a in local_ai.alternatives(masked, 3) if a != u["service"]]
                u = {"intent": "UNCLEAR", "engine": u["engine"], "conf": u["conf"], "summary": u.get("summary", ""),
                     "alternatives": alts[:3], "similar": u.get("similar", []),
                     "reason": f"Confidence only {round(u['conf'] * 100)}%. Possible services: " + " / ".join(alts[:3])}
        except Exception as e:  # noqa: BLE001 - any model failure falls back to the local engine
            u = None
            db.run("INSERT INTO ai_log(t,task,engine,ms,ok,detail) VALUES (datetime('now'),'understand','fallback',0,0,?)", (str(e)[:200],))
    if u is None:
        u = local_ai.understand(masked)
        db.run("INSERT INTO ai_log(t,task,engine,ms,ok,detail) VALUES (datetime('now'),'understand','local',0,1,?)", (u.get("intent", ""),))
    u["rules"] = rules
    u["threshold"] = low_conf()
    return masked, n, u


def engine_label(u):
    return {"llm": "Sakala AI", "llm+rules": "Sakala AI · rule check", "local": "Sakala AI (offline model)"}.get(u.get("engine"), u.get("engine", ""))


def process(text, src="upload", session=None):
    """Whole pipeline in one shot (assisted channels, Excel upload): returns where the request went."""
    masked, n, u = understand(text)
    out = {"masked_items": n, "intent": u["intent"], "engine": engine_label(u)}
    if u["intent"] != "GRIEVANCE":
        if u["intent"] == "UNCLEAR":
            out["case_id"] = scrutiny_case(text, masked, u, src, session)
            out["officer"] = "Scrutiny desk"
        out["note"] = u.get("reason") or u.get("dept") or u.get("sakala_key", "")
        return out
    place = locate(text, u)
    out.update(service=u["service"], dept=u["dept_code"], conf=u["conf"])
    if not place:
        out["case_id"] = scrutiny_case(text, masked, {**u, "reason": "Location missing: village / GP needed"}, src, session)
        out["officer"] = "Scrutiny desk (location missing)"
        return out
    dup = find_duplicate(u, place["gp"])
    res = create_grievance(text, masked, u, src, place["taluk"], place["gp"], place["village"], session=session, dup=dup["id"] if dup else None, how="text", place=place)
    if "scrutiny" in res:
        out.update(case_id=res["scrutiny"], officer="Scrutiny desk (guardrail)")
        return out
    out.update(case_id=res["id"], officer=res["officer"]["short"], gp=place["gp"], taluk=place["taluk"], linked_to=dup["id"] if dup else None)
    return out


def locate(text, u):
    """Stage 4 helper: find village → GP → taluk from what the citizen wrote (or what Claude extracted)."""
    cands = local_ai.place_candidates(text)
    place = resolve_place(*cands) if cands else None
    if not place and u.get("village"):
        # the model's village is only trusted if it is really written in the message (no invented places)
        import difflib, re as _re
        v = _re.sub(r"[^a-z]", "", u["village"].lower())
        if v and any(difflib.SequenceMatcher(None, v, _re.sub(r"[^a-z]", "", c.lower())).ratio() >= 0.8 for c in cands):
            place = resolve_place(u["village"], taluk_hint=u.get("taluk_text", ""))
    return place


def find_duplicate(u, gp):
    if not gp or not u.get("service_id"):
        return None
    return db.q1("SELECT id FROM cases WHERE service_id=? AND gp=? AND status IN ('Pending','In progress','Info requested') "
                 "ORDER BY created DESC LIMIT 1", (u["service_id"], gp))


def in_masters(u):
    """Guardrail 1: the AI may only use categories that exist in the official master."""
    svc = db.q1("SELECT id, name FROM services WHERE id=?", (u.get("service_id"),))
    if not svc or svc["name"] != u.get("service"):
        return False, "service not in the official master"
    grs = [g["name"] for g in db.q("SELECT name FROM grievance_types WHERE service_id=?", (svc["id"],))]
    if u.get("grievance") not in grs:
        u["grievance"] = grs[0] if grs else "General"          # snap to the master's own grievance names
    return True, ""


def audit_record(u, place=None, route_res=None, how=""):
    """Guardrail 3: every routing decision keeps its reason and evidence."""
    return {"at": now().isoformat(timespec="seconds"), "engine": u.get("engine"), "model": ai.status()["model"] if u.get("engine", "").startswith("llm") else "offline",
            "confidence": u.get("conf"), "threshold": u.get("threshold"), "intent": u.get("intent"),
            "decision": {"service_id": u.get("service_id"), "service": u.get("service"), "grievance": u.get("grievance"), "reason": u.get("why", "")},
            "alternatives": u.get("alternatives") or (local_ai.alternatives(u.get("summary") or "", 3) if False else []),
            "similar_real_cases": [{"gid": s["gid"], "service_id": s["service_id"], "score": s["score"]} for s in (u.get("similar") or [])[:5]],
            "rules": u.get("rules", []), "place": {**(place or {}), "how": how} if place else None,
            "route": {k: route_res.get(k) for k in ("officer", "role", "share", "support", "fallback", "basis")} if route_res else None}


def create_grievance(text, masked, u, src, taluk, gp, village, session=None, dup=None, how="", place=None):
    """Stages 6–8: route to the exact officer, start the clock, publish to dashboards."""
    ok, why_not = in_masters(u)
    if not ok:
        return {"scrutiny": scrutiny_case(text, masked, {**u, "reason": "Guardrail: " + why_not}, src, session)}
    r = route(u["service_id"], taluk, gp)
    oid = r["officer"] or f"eo_{taluk.lower()}"
    o = officer(oid)
    if not o:
        return {"scrutiny": scrutiny_case(text, masked, {**u, "reason": "Guardrail: officer not in the official master"}, src, session)}
    audit = audit_record(u, place or {"village": village, "gp": gp, "taluk": taluk}, r, how)
    cid = "GR-" + str(next_id(""))
    t = now()
    insert_case(id=cid, kind="GRIEVANCE", text=text, masked=masked, summary=u.get("summary", ""), src=src, lang=u.get("lang", ""),
                district=o.get("district") or "Mysuru", taluk=taluk, gp=gp, village=village, dept_code=u["dept_code"], line=u["line"], service=u["service"],
                service_id=u["service_id"], grievance=u["grievance"], conf=u["conf"], why=u["why"], engine=u["engine"],
                vulnerable=int(bool(u.get("vulnerable"))), vuln_reason=u.get("vuln_reason", ""), owner=oid, level=o["level"],
                level_since=t.isoformat(), created=t.isoformat(), status="Pending", real=0, synthetic=0, route_basis=r["basis"],
                sakala=None, session=session, linked_to=dup, audit=json.dumps(audit, default=str))
    event(cid, "Sakala AI", f"Routed to {o['short']}", "#26732f",
          f"{u['service']} · via {src} · {engine_label(u)} · confidence {round(u['conf'] * 100)}%")
    if dup:
        event(cid, "Sakala AI", f"Linked to similar open request {dup}", "#3b7dd8", "Same service, same Gram Panchayat")
    notify(oid, f"New grievance {cid} ({u['service']}) from {src}")
    ch = chain(oid)
    return {"id": cid, "officer": {"id": oid, "name": o["name"], "short": o["short"], "level": o["level"]},
            "chain": [{"lv": x["level"], "short": x["short"]} for x in ch], "basis": r["basis"], "fallback": r["fallback"],
            "days": SLA_DAYS.get(o["level"], 7), "next": ch[1]["short"] if len(ch) > 1 else "senior officers"}


def scrutiny_case(text, masked, u, src, session=None, taluk=""):
    """The scrutiny desk is the Taluk Panchayat EO of the taluk when it is known; the pilot desk (EO Piriyapatna) otherwise."""
    from .ingest import slug
    desk = officer(f"eo_{slug(taluk)}") if taluk else None
    if not desk:
        desk = officer("eo_piriyapatna")
    cid = "GR-" + str(next_id(""))
    t = now()
    insert_case(id=cid, kind="GRIEVANCE", text=text, masked=masked, summary=u.get("summary", ""), src=src, lang=u.get("lang", ""),
                district=desk.get("district") or "Mysuru", taluk=desk.get("taluk") or "Piriyapatna",
                gp="", village="", dept_code="", line="", service="", service_id=None, grievance="", conf=u.get("conf", 0),
                why=u.get("reason", ""), engine=u["engine"], vulnerable=0, owner=desk["id"], level=desk["level"], level_since=t.isoformat(),
                created=t.isoformat(), status="Scrutiny", real=0, synthetic=0, route_basis="Low confidence → human scrutiny desk",
                sakala=None, session=session, audit=json.dumps(audit_record(u), default=str))
    event(cid, "Sakala AI", "Sent to scrutiny desk", "#c98a00", (u.get("reason") or "Low confidence") + " · never a silent guess")
    notify(desk["id"], f"{cid} needs a human decision at the scrutiny desk")
    return cid
