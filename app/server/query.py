"""Deterministic answers over the whole Sakala data, for "ask me anything" by voice (Sakala Mitra) and the AI mode.

Sources: the live caseload (`cases` + `case_events`, statewide pilot departments), the 9,999 real iPGRS records of the
sample week (`ipgrs_records`, all 38 departments), the officer master, the gazetteer and the Sakala 2025 reports.
The model only chooses which function to call and with which filters; every number below comes from SQL."""
from __future__ import annotations

import difflib
import json
import re
from collections import Counter
from datetime import datetime, timedelta

from . import analytics, db
from .sla import chain, now, sla_info

OPEN = ("Pending", "In progress", "Info requested")
DEPT = {"REV": "Revenue", "RDPR": "Rural Development & Panchayat Raj", "FOOD": "Food & Civil Supplies"}
SRC = {"camp": "Praja Seva camp", "csc": "Citizen Service Centre", "web": "iPGRS website", "app": "Mobile App", "call": "1902 call centre",
       "rdpr": "RDPR call centre", "whatsapp": "WhatsApp", "mitra": "Sakala Mitra (voice)"}
STATUS_WORDS = {"open": OPEN, "pending": OPEN, "unresolved": OPEN, "outstanding": OPEN, "active": OPEN, "ongoing": OPEN, "live": OPEN,
                "in process": OPEN, "inprocess": OPEN, "not closed": OPEN, "not resolved": OPEN, "unattended": OPEN, "awaiting action": OPEN, "in progress": ("In progress",), "info requested": ("Info requested",),
                "resolved": ("Resolved",), "closed": ("Resolved", "Rejected"), "rejected": ("Rejected",), "scrutiny": ("Scrutiny",),
                "returned": ("Scrutiny",)}
_W = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}


def _low(v) -> str:
    return str(v or "").strip().lower()


def norm_id(x) -> tuple[str, str]:
    """'GR-504227', 'gr 504 227', 'five zero four two two seven', '503063', 'SK-RD855S260004811' -> (case_id, gid)."""
    s = _low(x)
    s = " ".join(_W.get(w, w) for w in re.split(r"[\s,]+", s))
    s = re.sub(r"[^a-z0-9]", "", s).upper()
    if s.startswith("SK"):
        return ("SK-" + s[2:] if not s.startswith("SK-") else s), ""
    digits = re.sub(r"\D", "", s)
    if s.startswith("GR") or digits:
        return "GR-" + digits, digits
    return s, ""


def _officers() -> dict:
    return {o["id"]: o for o in db.q("SELECT * FROM officers")}


def _off_label(o) -> str:
    return (o or {}).get("short") or (o or {}).get("name") or "the scrutiny desk"


def find_officer(text: str) -> dict | None:
    t = _low(text)
    if not t:
        return None
    offs = list(_officers().values())
    for o in offs:
        if t == o["id"].lower():
            return o
    t2 = re.sub(r"\b(the|officer|of|sir|madam|mr|mrs|ms)\b", " ", t)
    words = [w for w in re.split(r"[^a-z0-9]+", t2) if w]
    best, score = None, 0.0
    for o in offs:
        hay = f"{o['short']} {o['name']} {o.get('data_name') or ''} {o['role']} {o['taluk'] or ''} {o['gp'] or ''} {o.get('district') or ''}".lower()
        hit = sum(1 for w in words if w in hay)
        s = hit / max(1, len(words)) + difflib.SequenceMatcher(None, " ".join(words), o["short"].lower()).ratio() * 0.5
        if s > score:
            best, score = o, s
    return best if score >= 0.8 else None


def _case_row(c, offs) -> dict:
    si = sla_info(c)
    o = offs.get(c["owner"])
    open_ = c["status"] in OPEN
    left = si["left"]
    return {"id": c["id"], "kind": c["kind"].lower(), "service": c["service"], "department": DEPT.get(c["dept_code"], c["dept_code"]),
            "district": c["district"], "taluk": c["taluk"], "gp": c["gp"], "village": c["village"], "status": c["status"],
            "officer": _off_label(o), "level": c["level"], "source": SRC.get(c["src"], c["src"]),
            "days_left": left if open_ else None,
            "time": (f"{-left} day{'s' if left != -1 else ''} overdue" if left < 0 else "due today" if left == 0 else f"{left} day{'s' if left != 1 else ''} left") if open_ else c["status"].lower(),
            "vulnerable": bool(c["vulnerable"]), "created": (c["created"] or "")[:10]}


# ------------------------------------------------------------------ one case / one G.Id
def case_info(args: dict) -> dict:
    cid, gid = norm_id(args.get("case_id") or args.get("id") or args.get("gid") or "")
    offs = _officers()
    c = db.q1("SELECT * FROM cases WHERE id=?", (cid,))
    rec = db.q1("SELECT * FROM ipgrs_records WHERE gid=?", (gid,)) if gid else None
    if not c and not rec:
        near = [r["id"] for r in db.q("SELECT id FROM cases WHERE id LIKE ? LIMIT 3", (cid[:-1] + "%",))] if len(cid) > 5 else []
        return {"found": False, "asked": cid, "similar_ids": near}
    out = {"found": True, "id": cid}
    if c:
        r = _case_row(c, offs)
        o = offs.get(c["owner"])
        ch = [x for x in chain(c["owner"])] if c["owner"] else []
        r.update({"grievance": c["grievance"], "complaint": (c["masked"] or "")[:400], "officer_full": (o or {}).get("name"),
                  "escalation_chain": [f"{x['level']} {x['short']}" for x in ch], "vulnerable_reason": c["vuln_reason"],
                  "linked_to": c["linked_to"], "atr": c["atr"], "atr_score": c["atr_score"], "real_record": bool(c["real"]),
                  "synthetic": bool(c["synthetic"]), "ai_confidence": c["conf"], "routing_basis": c["route_basis"]})
        if c["sakala"]:
            sk = json.loads(c["sakala"])
            r["sakala"] = {"due_days": sk.get("dueDays"), "designated": sk.get("DO"), "competent": sk.get("CO"), "appellate": sk.get("AA")}
        r["history"] = [{"when": e["t"][:16], "who": e["who"], "what": e["what"], "note": (e["note"] or "")[:160]}
                        for e in db.q("SELECT * FROM case_events WHERE case_id=? ORDER BY t, id", (c["id"],))][-8:]
        out["live_case"] = r
    if rec:
        out["ipgrs_record"] = {"gid": rec["gid"], "complaint": (rec["text_masked"] or "")[:400], "department": rec["dept"], "line_department": rec["line"],
                               "service": rec["service"], "grievance": rec["grievance"], "service_type": rec["service_type"],
                               "district": rec["district"], "taluk": rec["taluk"], "gp": rec["gp"], "village": rec["village"],
                               "created": rec["created"], "status_in_ipgrs": rec["status"], "level_in_ipgrs": rec["role"],
                               "pending_with_or_closed_by": rec["officer"], "source": rec["source"]}
        if not c:
            out["note"] = "This G.Id is in the iPGRS sample but not in the pilot's live caseload (department outside the pilot, or not mappable to an officer)."
    return out


# ------------------------------------------------------------------ the live caseload
PLACE_ALIAS = {"mysore": "mysuru", "shimoga": "shivamogga", "belgaum": "belagavi", "bangalore": "bengaluru", "bagalkot": "bagalkote",
               "gulbarga": "kalaburagi", "bellary": "ballari", "bijapur": "vijayapura", "tumkur": "tumakuru", "chikmagalur": "chikkamagaluru",
               "mangalore": "dakshina kannada", "karwar": "uttara kannada", "periyapatna": "piriyapatna", "hunsuru": "hunsur",
               "chamarajanagara": "chamarajanagar", "hassana": "hassan"}


def _match(v, want) -> bool:
    w = _low(want)
    w = " ".join(PLACE_ALIAS.get(x, x) for x in w.replace(" district", "").replace(" taluk", "").split())   # Mysore -> Mysuru ...
    v = _low(v)
    if not w or not v:
        return False
    if w == v or re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", v):   # whole words: "Alur" is not inside "Bengaluru"
        return True
    return len(w) >= 5 and difflib.SequenceMatcher(None, v, w).ratio() >= 0.85


def _dept_code(v) -> str:
    t = _low(v)
    if not t:
        return ""
    if t.upper() in DEPT:
        return t.upper()
    if "food" in t or "civil" in t or "ration" in t:
        return "FOOD"
    if "rural" in t or "panchayat" in t or "rdpr" in t:
        return "RDPR"
    if "revenue" in t or "survey" in t or "land" in t:
        return "REV"
    return t.upper()


def find_cases(args: dict) -> dict:
    offs = _officers()
    owners = (args or {}).pop("_owners", None)   # an officer's view: only cases on their ladder
    rows = db.q("SELECT * FROM cases")
    if owners is not None:
        rows = [r for r in rows if r["owner"] in owners]
    applied = {}

    def keep(name, fn):
        nonlocal rows
        rows = [r for r in rows if fn(r)]
        applied[name] = True

    a = {k: v for k, v in (args or {}).items() if v not in (None, "", [], "any", "all")}
    if a.get("district"): keep("district", lambda r: _match(r["district"], a["district"]))
    if a.get("taluk"): keep("taluk", lambda r: _match(r["taluk"], a["taluk"]))
    if a.get("gp"): keep("gp", lambda r: _match(r["gp"], a["gp"]) or _match(r["village"], a["gp"]))
    if a.get("department"):
        from . import query_board as _qb
        dd = _qb.resolve_dept(a["department"])
        if dd and not dd["code"] and owners is None:          # outside the pilot: the real iPGRS sample week answers it
            ia = {k: v for k, v in a.items() if k in ("district", "taluk", "gp", "service", "level", "group_by", "limit", "text")}
            st0 = _low(a.get("status"))
            if st0 in ("open", "pending", "in progress", "overdue"):
                ia["status"] = "open"
            elif st0 in ("resolved", "closed", "scrutiny"):
                ia["status"] = st0
            ia["department"] = dd["name"]
            out = ipgrs_records(ia)
            out["delegated"] = "ipgrs_records"
            out["department_short"] = dd["short"]
            return out
        code = dd["code"] if dd else _dept_code(a["department"])
        keep("department", lambda r: r["dept_code"] == code)
    if a.get("service"):
        keep("service", lambda r: _low(a["service"]) in f"{_low(r['service'])} {_low(r['grievance'])}" or _match(r["service"], a["service"]))
    if a.get("text"): keep("text", lambda r: _low(a["text"]) in _low(r["masked"]))
    st = _low(a.get("status"))
    if st and st != "overdue":
        allowed = STATUS_WORDS.get(st) or tuple(s for s in ("Pending", "In progress", "Info requested", "Resolved", "Rejected", "Scrutiny") if _low(s) == st)
        if allowed:                                      # an unknown status word is ignored, never a false zero
            keep("status", lambda r: r["status"] in allowed)
    if a.get("overdue") in (True, "true", "yes", 1) or st == "overdue":
        keep("overdue", lambda r: r["status"] in OPEN and sla_info(r)["left"] < 0)
    if a.get("days_left") is not None and str(a.get("days_left")).lstrip("-").isdigit():
        n = int(a["days_left"])
        keep("days_left", lambda r: r["status"] in OPEN and sla_info(r)["left"] == n)
    if a.get("due_within_days") is not None:
        n = int(a["due_within_days"])
        keep("due", lambda r: r["status"] in OPEN and 0 <= sla_info(r)["left"] <= n)
    if a.get("vulnerable") in (True, "true", "yes", 1): keep("vulnerable", lambda r: bool(r["vulnerable"]))
    if a.get("level"): keep("level", lambda r: r["level"] == str(a["level"]).upper())
    if a.get("officer"):
        o = find_officer(a["officer"])
        oid = o["id"] if o else "__none__"
        keep("officer", lambda r: r["owner"] == oid)
        applied["officer_matched"] = _off_label(o) if o else None
    if a.get("source"):
        s = _low(a["source"])
        keep("source", lambda r: s in _low(r["src"]) or s in _low(SRC.get(r["src"], "")))
    if a.get("kind"):
        k = "APPLICATION" if "appl" in _low(a["kind"]) or "sakala" in _low(a["kind"]) else "GRIEVANCE"
        keep("kind", lambda r: r["kind"] == k)
    if a.get("escalated") in (True, "true", "yes", 1):
        from . import query_board as _qb
        esc = _qb.escalated_ids()
        keep("escalated", lambda r: r["id"] in esc)
    elif a.get("escalated") in (False, "false", "no", 0, "0"):
        from . import query_board as _qb
        esc = _qb.escalated_ids()
        keep("escalated", lambda r: r["id"] not in esc)
    if a.get("created_from"): keep("created_from", lambda r: (r["created"] or "")[:10] >= str(a["created_from"])[:10])
    if a.get("created_to"): keep("created_to", lambda r: (r["created"] or "")[:10] <= str(a["created_to"])[:10])
    if a.get("since_go_live") in (True, "true", "yes", 1):
        keep("new", lambda r: not r["real"] and not r["synthetic"])

    total = len(rows)
    out = {"total": total, "open": sum(1 for r in rows if r["status"] in OPEN),
           "overdue": sum(1 for r in rows if r["status"] in OPEN and sla_info(r)["left"] < 0),
           "resolved": sum(1 for r in rows if r["status"] == "Resolved"), "filters": a, "officer_matched": applied.get("officer_matched")}
    g = _low(a.get("group_by")).replace(" ", "_").replace("-", "_")
    g = {"deadline": "days_left", "days": "days_left", "time_left": "days_left", "days_remaining": "days_left", "escalation": "escalated"}.get(g, g)
    if g == "days_left":                                  # the 7-day clock: overdue, due today, 1..7 days left, beyond
        from . import query_board as _qb
        open_rows = [r for r in rows if r["status"] in OPEN]
        cnt = Counter(_qb.bucket(sla_info(r)["left"]) for r in open_rows)
        out["group_by"] = "days_left"
        out["groups"] = [{"name": b, "count": cnt.get(b, 0)} for b in _qb.BUCKETS]
        out["distinct"] = sum(1 for b in _qb.BUCKETS if cnt.get(b))
        out["of_open"] = len(open_rows)
        return out
    if g == "escalated":
        from . import query_board as _qb
        esc = _qb.escalated_ids()
        open_rows = [r for r in rows if r["status"] in OPEN]
        out["group_by"] = "escalated"
        out["groups"] = [{"name": "Escalated", "count": sum(1 for r in open_rows if r["id"] in esc)},
                         {"name": "Not escalated", "count": sum(1 for r in open_rows if r["id"] not in esc)}]
        out["distinct"] = 2
        out["of_open"] = len(open_rows)
        return out
    key = {"district": lambda r: r["district"], "kind": lambda r: "Sakala application" if r["kind"] == "APPLICATION" else "Grievance",
           "vulnerable": lambda r: "Vulnerable citizen" if r["vulnerable"] else "Others", "taluk": lambda r: r["taluk"], "gp": lambda r: r["gp"] or "(taluk level)",
           "department": lambda r: DEPT.get(r["dept_code"], r["dept_code"]), "dept": lambda r: DEPT.get(r["dept_code"], r["dept_code"]),
           "service": lambda r: r["service"], "officer": lambda r: _off_label(offs.get(r["owner"])), "status": lambda r: r["status"],
           "source": lambda r: SRC.get(r["src"], r["src"]), "channel": lambda r: SRC.get(r["src"], r["src"]), "level": lambda r: r["level"],
           "day": lambda r: (r["created"] or "")[:10], "month": lambda r: (r["created"] or "")[:7]}.get(g)
    if key:
        if g in ("department", "dept", "service"):        # a case at the scrutiny desk has no department yet: not a department of its own
            rows = [r for r in rows if (r["dept_code"] if g != "service" else r["service"])]
        cnt = Counter(key(r) or "-" for r in rows)
        top = cnt.most_common(int(a.get("limit") or 12))
        out["group_by"] = g
        out["groups"] = [{"name": k, "count": v} for k, v in (sorted(cnt.items()) if g in ("day", "month") else top)]
        if g not in ("district", "day", "month"):        # each group's footprint across the districts (for the map)
            names = {x["name"] for x in out["groups"]}
            geo: dict = {}
            for r in rows:
                k = key(r) or "-"
                if k in names and r["district"]:
                    geo.setdefault(k, {}); geo[k][r["district"]] = geo[k].get(r["district"], 0) + 1
            out["geo"] = geo
        out["distinct"] = len(cnt)
        return out
    sort = _low(a.get("sort")) or "urgent"
    if sort == "newest":
        rows.sort(key=lambda r: r["created"] or "", reverse=True)
    elif sort == "oldest":
        rows.sort(key=lambda r: r["created"] or "")
    else:
        rows.sort(key=lambda r: (r["status"] not in OPEN, sla_info(r)["left"]))
    out["cases"] = [_case_row(r, offs) for r in rows[:int(a.get("limit") or 10)]]
    return out


# ------------------------------------------------------------------ the 9,999 real iPGRS records (all departments)
def ipgrs_records(args: dict) -> dict:
    a = {k: v for k, v in (args or {}).items() if v not in (None, "", [], "any", "all")}
    where, p = ["1=1"], []
    if a.get("department"):
        from . import query_board as _qb
        dd = _qb.resolve_dept(a["department"])
        if dd:
            a["department"] = dd["name"]
            where.append("dept = ?"); p.append(dd["name"])
            a["_dept_done"] = True
    for f, col in (("district", "district"), ("taluk", "taluk"), ("gp", "gp"), ("department", "dept"), ("line_department", "line"),
                   ("source", "source"), ("officer", "officer")):
        if f == "department" and a.get("_dept_done"):
            continue
        if a.get(f):
            v = _low(a[f])
            if f in ("district", "taluk"):
                v = " ".join(PLACE_ALIAS.get(x, x) for x in v.replace(" district", "").replace(" taluk", "").split())
            where.append(f"lower({col}) LIKE ?"); p.append(f"%{v}%")
    if a.get("service"):
        where.append("(lower(service) LIKE ? OR lower(grievance) LIKE ?)"); p += [f"%{_low(a['service'])}%"] * 2
    if a.get("text"):
        where.append("lower(text_masked) LIKE ?"); p.append(f"%{_low(a['text'])}%")
    if a.get("status"):
        s = _low(a["status"])
        openish = ("open", "pending", "active", "unresolved", "outstanding", "ongoing", "live", "in process", "inprocess", "in progress", "not closed", "not resolved")
        s = "inprocess" if s in openish else {"closed": "closed", "disposed": "closed", "resolved": "resolved", "scrutiny": "scrutiny", "registered": "scrutiny"}.get(s, s)
        if s in ("inprocess", "closed", "resolved", "scrutiny"):     # an unknown status word is ignored, never a false zero
            where.append("lower(replace(status,' ','')) LIKE ?"); p.append(f"%{'registered' if s == 'scrutiny' else s}%")
    if a.get("service_type"):
        where.append("lower(service_type) = ?"); p.append("sakala" if "non" not in _low(a["service_type"]) else "non sakala")
    if a.get("level"):
        where.append("upper(role) = ?"); p.append(str(a["level"]).upper().replace("L1", "LMF"))
    if a.get("created_from"):
        where.append("created >= ?"); p.append(str(a["created_from"])[:10])
    if a.get("created_to"):
        where.append("created < ?"); p.append((datetime.fromisoformat(str(a["created_to"])[:10]) + timedelta(days=1)).date().isoformat())
    w = " AND ".join(where)
    total = db.q1(f"SELECT COUNT(*) n FROM ipgrs_records WHERE {w}", p)["n"]
    a.pop("_dept_done", None)
    out = {"total": total, "of": 9999, "filters": a, "period": "3-9 Oct 2026 (iPGRS sample week)",
           "open": db.q1(f"SELECT COUNT(*) n FROM ipgrs_records WHERE {w} AND status='InProcess'", p)["n"]}
    g = _low(a.get("group_by"))
    col = {"department": "dept", "dept": "dept", "line_department": "line", "service": "service", "grievance": "grievance", "district": "district",
           "taluk": "taluk", "gp": "gp", "status": "status", "source": "source", "channel": "source", "service_type": "service_type",
           "level": "role", "officer": "officer", "day": "substr(created,1,10)"}.get(g)
    if col:
        rows = db.q(f"SELECT {col} k, COUNT(*) n FROM ipgrs_records WHERE {w} GROUP BY {col} ORDER BY " + ("k" if g == "day" else "n DESC") +
                    f" LIMIT {int(a.get('limit') or 12)}", p)
        out["group_by"] = g
        out["groups"] = [{"name": r["k"] or "-", "count": r["n"]} for r in rows]
        out["distinct"] = db.q1(f"SELECT COUNT(DISTINCT {col}) n FROM ipgrs_records WHERE {w}", p)["n"]
        if g not in ("district", "day") and rows:            # each group's footprint across the districts (for the map)
            ks = [r["k"] for r in rows]
            gr = db.q(f"SELECT {col} k, district d, COUNT(*) n FROM ipgrs_records WHERE {w} AND {col} IN ({','.join('?' * len(ks))}) GROUP BY {col}, district", p + ks)
            geo: dict = {}
            for x in gr:
                if x["d"]:
                    geo.setdefault(x["k"] or "-", {})[x["d"].title()] = x["n"]
            out["geo"] = geo
        return out
    recs = db.q(f"SELECT * FROM ipgrs_records WHERE {w} ORDER BY created DESC LIMIT {int(a.get('limit') or 8)}", p)
    out["records"] = [{"gid": r["gid"], "department": r["dept"], "service": r["service"], "district": r["district"], "taluk": r["taluk"],
                       "gp": r["gp"], "status": r["status"], "pending_with": r["officer"], "source": r["source"], "created": (r["created"] or "")[:16],
                       "complaint": (r["text_masked"] or "")[:160]} for r in recs]
    return out


# ------------------------------------------------------------------ officers and places
def officer_profile(args: dict) -> dict:
    o = find_officer(args.get("officer") or args.get("name") or "")
    if not o:
        return {"found": False, "asked": args.get("officer") or args.get("name")}
    rows = db.q("SELECT * FROM cases WHERE owner=?", (o["id"],))
    open_ = [r for r in rows if r["status"] in OPEN]
    od = [r for r in open_ if sla_info(r)["left"] < 0]
    up = [f"{x['level']} {x['short']}" for x in chain(o["id"])][1:]
    oldest = min(open_, key=lambda r: sla_info(r)["left"], default=None)
    return {"found": True, "officer": o["short"], "full_title": o["name"], "id": o["id"], "level": o["level"], "role": o["role"],
            "department": DEPT.get(o["dept_code"], o["dept_code"]), "district": o.get("district"), "taluk": o["taluk"], "gp": o["gp"],
            "reports_to": up, "open": len(open_), "overdue": len(od), "resolved": sum(1 for r in rows if r["status"] == "Resolved"),
            "rejected": sum(1 for r in rows if r["status"] == "Rejected"), "vulnerable_open": sum(1 for r in open_ if r["vulnerable"]),
            "most_urgent": _case_row(oldest, {o["id"]: o}) if oldest else None, "seen_in_ipgrs_sample": bool(o["seen_in_data"]),
            "ipgrs_records_with_them": db.q1("SELECT COUNT(*) n FROM ipgrs_records WHERE officer=?", (o.get("data_name") or "",))["n"] if o.get("data_name") else 0}


def place_info(args: dict) -> dict:
    name = _low(args.get("place") or args.get("name") or "")
    if not name:
        return {"found": False}
    gaz = db.q("SELECT * FROM gazetteer")
    best, kind, score = None, "", 0.0
    for r in gaz:
        for k in ("village", "gp", "taluk", "district"):
            v = _low(r[k])
            s = 1.0 if v == name else difflib.SequenceMatcher(None, v, name).ratio()
            if s > score or (s == score and k in ("taluk", "district") and kind in ("village", "gp")):
                best, kind, score = r, k, s
    if not best or score < 0.84:
        return {"found": False, "asked": name}
    field = {"village": "village", "gp": "gp", "taluk": "taluk", "district": "district"}[kind]
    rows = db.q(f"SELECT * FROM cases WHERE lower({field})=?", (_low(best[kind]),))
    open_ = [r for r in rows if r["status"] in OPEN]
    offs = db.q("SELECT short, level, role FROM officers WHERE " + ("gp=? AND taluk=?" if kind in ("village", "gp") else "taluk=? AND (gp IS NULL OR gp='')" if kind == "taluk" else "district=? AND level!='L1'"),
                (best["gp"], best["taluk"]) if kind in ("village", "gp") else (best["taluk"],) if kind == "taluk" else (best["district"],))
    return {"found": True, "is_a": kind, "name": best[kind], "village": best["village"] if kind == "village" else None,
            "gp": best["gp"] if kind in ("village", "gp") else None, "taluk": best["taluk"] if kind != "district" else None, "district": best["district"],
            "officers_here": [f"{o['level']} {o['short']}" for o in offs][:12], "live_cases": len(rows), "open": len(open_),
            "overdue": sum(1 for r in open_ if sla_info(r)["left"] < 0), "top_services": Counter(r["service"] for r in rows).most_common(5),
            "ipgrs_records": db.q1(f"SELECT COUNT(*) n FROM ipgrs_records WHERE lower({field})=?", (_low(best[kind]),))["n"]}


def statewide_stats(args: dict) -> dict:
    rows = db.q("SELECT * FROM cases")
    open_ = [r for r in rows if r["status"] in OPEN]
    today = now().date().isoformat()
    esc = db.q1("SELECT COUNT(DISTINCT case_id) n FROM case_events WHERE what LIKE 'Auto-escalated%'")["n"]
    return {"as_of": now().isoformat(timespec="minutes"), "live_cases": len(rows), "open": len(open_),
            "overdue": sum(1 for r in open_ if sla_info(r)["left"] < 0), "vulnerable_open": sum(1 for r in open_ if r["vulnerable"]),
            "auto_escalated": esc, "resolved": sum(1 for r in rows if r["status"] == "Resolved"), "rejected": sum(1 for r in rows if r["status"] == "Rejected"),
            "at_scrutiny_desk": sum(1 for r in rows if r["status"] == "Scrutiny"),
            "by_status": Counter(r["status"] for r in rows).most_common(), "open_by_level": Counter(r["level"] for r in open_).most_common(),
            "open_by_department": [(DEPT.get(k, k), v) for k, v in Counter(r["dept_code"] for r in open_).most_common()],
            "by_channel": [(SRC.get(k, k), v) for k, v in Counter(r["src"] for r in rows).most_common()],
            "filed_since_go_live": sum(1 for r in rows if not r["real"] and not r["synthetic"]),
            "filed_today": sum(1 for r in rows if (r["created"] or "")[:10] == today and not r["real"]),
            "districts": len({r["district"] for r in rows}), "taluks": len({r["taluk"] for r in rows}),
            "ipgrs_sample_records": 9999, "officers": db.q1("SELECT COUNT(*) n FROM officers")["n"],
            "due_today": sum(1 for r in open_ if sla_info(r)["left"] == 0)}


def sakala_2025(args: dict) -> dict:
    t = analytics.sakala_tracker()
    d = _low(args.get("district"))
    out = {"state": t["state"], "source": "Sakala 2025 district performance reports (Jan-Dec 2025)"}
    if d:
        out["district"] = [x for x in t["districts"] if _match(x["district"], d)]
    else:
        out["worst_by_late_delivery"] = t["districts"][:5]
        out["best_by_late_delivery"] = t["districts"][-5:]
    if args.get("monthly") or not d:
        out["monthly_state"] = [{"month": m["month"], "overdue": int(m["overdue"]), "late_pct": m["late_pct"], "rejected_pct": m["rej_pct"]} for m in t["monthly"]]
    return out


TOOLS = {"case_info": case_info, "find_cases": find_cases, "ipgrs_records": ipgrs_records, "officer_profile": officer_profile,
         "place_info": place_info, "statewide_stats": statewide_stats, "sakala_2025": sakala_2025}


def _lazy(name):
    def run_(args):
        from . import compare as _c
        return getattr(_c, name)(args)
    return run_


TOOLS["compare"] = _lazy("compare")


def _board(args):
    from . import query_board as _qb
    return _qb.dashboard(args)


TOOLS["dashboard"] = _board
TOOLS["ranking"] = _lazy("ranking")


def ladder_owners(viewer: str) -> set:
    """Officers whose cases `viewer` may read: themselves and everyone who reports to them, directly or further down."""
    up = {r["id"]: r["up_id"] for r in db.q("SELECT id, up_id FROM officers")}
    out = set()
    for oid in up:
        o, n = oid, 0
        while o and n < 8:
            if o == viewer:
                out.add(oid)
                break
            o, n = up.get(o), n + 1
    return out


def _scoped(tool: str, args: dict, viewer: str) -> dict:
    """Sakala Mitra guardrail 12: an officer reads only the cases on their own ladder (aggregate counts stay open)."""
    me = db.q1("SELECT id, short, district FROM officers WHERE id=?", (viewer,))
    if not me:
        return {"error": "unknown viewer"}
    owners = ladder_owners(viewer)
    if tool == "case_info":
        cid, gid = norm_id(args.get("case_id") or args.get("id") or args.get("gid") or "")
        c = db.q1("SELECT id, owner FROM cases WHERE id=?", (cid,))
        if c and c["owner"] not in owners:
            h = db.q1("SELECT short FROM officers WHERE id=?", (c["owner"],))
            return {"found": False, "restricted": True, "asked": cid, "holder": (h or {}).get("short", "")}
        if not c and gid:
            rec = db.q1("SELECT district FROM ipgrs_records WHERE gid=?", (gid,))
            if rec and me["district"] and _low(rec["district"]) != _low(me["district"]):
                return {"found": False, "restricted": True, "asked": gid, "holder": ""}
        return case_info(args)
    if tool == "find_cases":
        out = find_cases({**args, "_owners": owners})
        out["scope"] = "your desk and your team"
        return out
    if tool == "ipgrs_records":
        out = ipgrs_records({**args, "district": me["district"]} if me["district"] else args)
        out["scope"] = f"{me['district']} district"
        return out
    return TOOLS[tool](args)


def run(tool: str, args: dict) -> dict:
    fn = TOOLS.get(tool)
    if not fn:
        return {"error": f"unknown tool {tool}"}
    from . import query_board as _qb
    args = _qb.normalise_args(dict(args or {}))          # Kannada arguments from the live voice -> English
    viewer = args.pop("viewer", None)
    if viewer:
        return _scoped(tool, args, viewer)
    return fn(args)
