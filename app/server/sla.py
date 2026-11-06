"""Stages 7–8 · Deadlines, reminders, automatic escalation and the Sakala legal clock (demo clock driven)."""
import json
from datetime import datetime, timedelta

from . import db
from .config import SLA_DAYS, DEMO_START, COMP_PER_DAY, COMP_CAP

OPEN = ("Pending", "In progress", "Info requested")


def now() -> datetime:
    return datetime.fromisoformat(db.kv_get("now", DEMO_START.isoformat()))


def officer(oid):
    return db.q1("SELECT * FROM officers WHERE id=?", (oid,))


def chain(oid):
    out = []
    while oid:
        o = officer(oid)
        if not o:
            break
        out.append(o)
        oid = o["up_id"]
    return out


def next_id(prefix):
    n = db.kv_get("seq", 504200) + 1
    db.kv_set("seq", n)
    return f"{prefix}{n}"


def event(case_id, who, what, color, note="", t=None):
    db.run("INSERT INTO case_events(case_id,t,who,what,color,note) VALUES (?,?,?,?,?,?)",
           (case_id, (t or now()).isoformat(), who, what, color, note))


def message_citizen(case_id, officer_id, kind, text=""):
    """Queue a WhatsApp message to the citizen who filed the case (delivered on their next poll)."""
    c = db.q1("SELECT session FROM cases WHERE id=?", (case_id,))
    if c and c["session"]:
        db.run("INSERT INTO citizen_msgs(case_id,session,t,officer_id,kind,text) VALUES (?,?,?,?,?,?)",
               (case_id, c["session"], now().isoformat(), officer_id or "", kind, text))


def notify(officer_id, msg):
    db.run("INSERT INTO notifications(officer_id,t,msg) VALUES (?,?,?)", (officer_id, now().isoformat(), msg))


def ladder_up(c):
    """The next rung above the case's holder: the senior on the grievance ladder, or the next Sakala authority
    (Designated -> Competent -> Appellate) for an application. The two ladders never mix."""
    if c.get("sakala"):
        sk = json.loads(c["sakala"])
        order = [sk.get("DO"), sk.get("CO"), sk.get("AA")]
        if c["owner"] in order:
            i = order.index(c["owner"])
            return officer(order[i + 1]) if i + 1 < len(order) and order[i + 1] else None
    cur = officer(c["owner"])
    return officer(cur["up_id"]) if cur and cur["up_id"] else None


def feedback_pending(c) -> bool:
    """The officer filed a resolution and the citizen has not yet said whether it is really solved."""
    if c["status"] != "Resolved":
        return False
    last = db.q1("SELECT what FROM case_events WHERE case_id=? AND (what LIKE 'Resolved with ATR%' OR what LIKE 'Citizen confirmed%') "
                 "ORDER BY id DESC LIMIT 1", (c["id"],))
    return bool(last) and last["what"].startswith("Resolved")


def citizen_verdict(c, accepted: bool, who: str, channel: str) -> dict:
    """Stage 8, the citizen's verdict on the officer's resolution. Accepted: the case is closed and the confirmation sits
    on the officer's report. Rejected: the case is RE-OPENED and moves ONE RUNG UP the escalation ladder (L1 -> L2 -> L3);
    the senior's clock starts now, both officers and the Chief Secretary are told. Shared by WhatsApp and Sakala Mitra."""
    cid = c["id"]
    cur = officer(c["owner"]) or {"id": c["owner"], "name": "the officer", "short": "the officer", "level": c["level"], "up_id": None}
    if accepted:
        event(cid, who, "Citizen confirmed: problem solved 👍", "#1f9d57", f"Resolution accepted on {channel}")
        db.run("UPDATE cases SET status='Resolved' WHERE id=?", (cid,))
        notify(cur["id"], f"{cid} closed: the citizen confirmed the problem is solved")
        return {"accepted": True, "status": "Resolved", "officer": cur["short"], "officer_id": cur["id"], "level": cur["level"]}
    up = ladder_up(c)
    t = now().isoformat()
    if up:
        days = SLA_DAYS.get(up["level"], 7)
        db.run("UPDATE cases SET owner=?, level=?, level_since=?, status='Pending' WHERE id=?", (up["id"], up["level"], t, cid))
        event(cid, who, f"Re-opened by the citizen · escalated to {up['short']}", "#c8372d",
              f"Resolution by {cur['short']} rejected on {channel} · {cur['level']} → {up['level']} · clock restarted: {days} days")
        notify(up["id"], f"{cid} escalated to you from {cur['short']}: the citizen rejected the resolution")
        notify(cur["id"], f"{cid} re-opened by the citizen after your ATR · moved up to {up['short']}")
        return {"accepted": False, "status": "Pending", "escalated": True, "from": cur["short"], "from_level": cur["level"],
                "officer": up["short"], "officer_id": up["id"], "officer_name": up["name"], "level": up["level"], "days": days,
                "chain": [{"lv": x["level"], "short": x["short"], "id": x["id"]} for x in chain(up["id"])]}
    days = SLA_DAYS.get(cur["level"], 7)
    db.run("UPDATE cases SET status='Pending', level_since=? WHERE id=?", (t, cid))
    event(cid, who, "Re-opened by the citizen · top of the ladder", "#c8372d",
          f"Resolution by {cur['short']} rejected on {channel} · no senior to escalate to · clock restarted: {days} days · flagged for the Chief Secretary")
    notify(cur["id"], f"{cid} re-opened by the citizen after your ATR · top of the ladder, the Chief Secretary is informed")
    return {"accepted": False, "status": "Pending", "escalated": False, "from": cur["short"], "from_level": cur["level"],
            "officer": cur["short"], "officer_id": cur["id"], "officer_name": cur.get("name") or cur["short"], "level": cur["level"], "days": days,
            "chain": [{"lv": x["level"], "short": x["short"], "id": x["id"]} for x in chain(cur["id"])]}


def days_between(a: datetime, b: datetime) -> int:
    return (b - a).days


def sla_info(c):
    """Days used / allowed / left for a case row (dict from the cases table)."""
    sk = json.loads(c["sakala"]) if c.get("sakala") else None
    if sk:
        used = days_between(datetime.fromisoformat(sk["complete"]), now())
        return {"used": used, "total": sk["dueDays"], "left": sk["dueDays"] - used, "legal": True}
    total = SLA_DAYS.get(c["level"], 7)
    used = days_between(datetime.fromisoformat(c["level_since"]), now())
    return {"used": used, "total": total, "left": total - used, "legal": False}


def compensation(c):
    s = sla_info(c)
    return min(COMP_CAP, COMP_PER_DAY * -s["left"]) if s["legal"] and s["left"] < 0 else 0


def insert_case(**f):
    # guardrail 14: a grievance never carries a Sakala legal clock; an application always does
    if f.get("kind") == "APPLICATION" and not f.get("sakala"):
        raise ValueError("an application needs its Sakala clock")
    if f.get("kind") == "GRIEVANCE" and f.get("sakala"):
        raise ValueError("a grievance must not carry a Sakala clock")
    cols = ["id", "kind", "text", "masked", "summary", "src", "lang", "district", "taluk", "gp", "village", "dept_code", "line",
            "service", "service_id", "grievance", "conf", "why", "engine", "vulnerable", "vuln_reason", "owner", "level",
            "level_since", "created", "status", "real", "synthetic", "route_basis", "sakala", "atr", "atr_score", "atr_reason",
            "session", "linked_to", "audit"]
    db.run(f"INSERT INTO cases({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [f.get(k) for k in cols])


def create_application(key, applicant, gp, taluk, src, complete_at=None, text=None, case_id=None, session=None, doc_note=""):
    """Register a Sakala service application: Designated → Competent → Appellate officers and the legal deadline."""
    from .routing import officer_for_role
    from .ingest import slug
    s = db.q1("SELECT * FROM sakala_services WHERE key=?", (key,))
    do = officer_for_role(s["do_role"], taluk, gp)
    drow = db.q1("SELECT district FROM officers WHERE taluk=? AND district IS NOT NULL AND district!='' LIMIT 1", (taluk,))
    district = (drow or {}).get("district") or "Mysuru"
    if district == "Mysuru":
        co = {"AC": "ac_hunsur" if taluk in ("Piriyapatna", "Hunsur") else "ac_mysuru", "DD_FOOD": "dd_food"}[s["co"]]
        aa = "dc_mys"
    else:
        co = {"AC": f"ac_{slug(district)}", "DD_FOOD": f"dd_food_{slug(district)}"}[s["co"]]
        aa = f"dc_{slug(district)}"
    complete_at = complete_at or now()
    cid = case_id or ("SK-" + ("FD201" if s["dept_code"] == "FOOD" else "RD855") + "S26" + str(next_id("")).zfill(6))
    o = officer(do)
    sk = {"key": key, "service": s["name"], "dueDays": s["days"], "DO": do, "CO": co, "AA": aa,
          "complete": complete_at.isoformat(), "applicant": applicant, "illustrative": True}
    insert_case(id=cid, kind="APPLICATION", text=text or f"Application: {s['name']} for {applicant}", masked=text or f"Application: {s['name']} for {applicant}",
                summary=f"{s['name']} application", src=src, lang="en", district=district, taluk=taluk, gp=gp, village=gp,
                dept_code=s["dept_code"], line="Sakala service", service=s["name"], grievance="New application", conf=1.0,
                why="Citizen applied for a Sakala-notified service.", engine="Sakala", vulnerable=0, owner=do, level=o["level"],
                level_since=complete_at.isoformat(), created=complete_at.isoformat(), status="Pending", real=0,
                synthetic=1 if case_id else 0, route_basis=f"Designated Officer for {s['name']} in {taluk}",
                sakala=json.dumps(sk), session=session)
    event(cid, "Sakala AI", f"Application registered · Designated Officer {o['short']}", "#26732f",
          "Complete on submission · legal clock started" + (f" · {doc_note}" if doc_note else ""), t=complete_at)
    notify(do, f"New Sakala application {cid} ({s['name']})")
    return cid


def tick(days: int):
    """Move the demo clock and apply escalation + Sakala breach rules. Returns counts."""
    t = now() + timedelta(days=days)
    db.kv_set("now", t.isoformat())
    escalated = 0
    for c in db.q(f"SELECT * FROM cases WHERE status IN ({','.join('?' * len(OPEN))}) AND kind='GRIEVANCE'", OPEN):
        guard = 0
        while guard < 3:
            guard += 1
            o = officer(c["owner"])
            if not o or not o["up_id"] or sla_info(c)["left"] >= 0:
                break
            up = officer(o["up_id"])
            since = datetime.fromisoformat(c["level_since"]) + timedelta(days=SLA_DAYS.get(c["level"], 7))
            c.update(owner=up["id"], level=up["level"], level_since=since.isoformat())
            db.run("UPDATE cases SET owner=?, level=?, level_since=? WHERE id=?", (up["id"], up["level"], since.isoformat(), c["id"]))
            event(c["id"], "System", f"Auto-escalated to {up['short']}", "#c8372d",
                  f"{o['short']} did not act within {SLA_DAYS.get(o['level'], 7)} days (assumed timeline). Notice sent to both officers.", t=since)
            notify(up["id"], f"{c['id']} escalated to you from {o['short']}")
            message_citizen(c["id"], up["id"], "escalated", f"{o['short']} did not act within {SLA_DAYS.get(o['level'], 7)} days")
            notify(o["id"], f"{c['id']} escalated to {up['short']} (no action in time)")
            escalated += 1
    # pre-deadline reminders: due tomorrow / due today (stage 7)
    for c in db.q(f"SELECT * FROM cases WHERE status IN ({','.join('?' * len(OPEN))})", OPEN):
        left = sla_info(c)["left"]
        if left in (0, 1):
            notify(c["owner"], f"{c['id']} is due {'today' if left == 0 else 'tomorrow'}" + (" (Sakala legal deadline)" if c["kind"] == "APPLICATION" else " · will escalate if not acted on"))
    breached = 0
    for c in db.q("SELECT * FROM cases WHERE kind='APPLICATION' AND status NOT IN ('Resolved','Rejected')"):
        sk = json.loads(c["sakala"])
        if sla_info(c)["left"] < 0 and not sk.get("breached"):
            sk["breached"] = True
            db.run("UPDATE cases SET sakala=? WHERE id=?", (json.dumps(sk), c["id"]))
            due = datetime.fromisoformat(sk["complete"]) + timedelta(days=sk["dueDays"])
            event(c["id"], "Sakala clock", "Legal deadline missed", "#c8372d",
                  f"Alert to Competent Officer ({officer(sk['CO'])['short']}). Citizen informed of first-appeal right (30 days).", t=due)
            notify(sk["CO"], f"Sakala deadline missed on {c['id']}: compensation due")
            breached += 1
    return {"now": t.isoformat(), "escalated": escalated, "breached": breached}
