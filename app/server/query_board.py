"""The Chief Secretary's questions, answered from SQL (22 Oct 2026).

- every department in the iPGRS Excel, by any of its names (RDPR, education, power, police, municipal, ...);
- the live caseload sliced by level (L1 / L2 / L3), escalated or not, overdue, days left (1-7 day buckets), owner, service;
- `dashboard(entity)`: the whole picture of a department, district, taluk, level, officer or the state, in one call:
  KPIs + by level + days-left buckets + by place + by service + the officers holding the most + oldest overdue cases.
  A pilot department (Revenue, RDPR, Food) or no department = the live caseload with clocks; any other department = the
  9,999 real iPGRS records of the sample week (status, level, place, pending officer; no clocks, said so).
- arguments given in Kannada by the live voice are normalised (ಹುಣಸೂರು -> Hunsur, ಬಾಕಿ -> open, ಕಂದಾಯ -> Revenue).
The model only chooses the function and the filters; every number here is counted from the database."""
from __future__ import annotations

import difflib
import re
from collections import Counter

from . import db
from .sla import now, sla_info

OPEN = ("Pending", "In progress", "Info requested")
PILOT = {"REV": "Revenue", "RDPR": "Rural Development & Panchayat Raj", "FOOD": "Food & Civil Supplies"}

# ------------------------------------------------------------------ departments (all 38 in the Excel)
DEPT_ALIAS = [
    (r"\brdpr\b|rural|panchayat|gram panchayat|zilla|taluk panchayat|ಗ್ರಾಮೀಣ|ಪಂಚಾಯ", "Rural Development and Panchayath Raj Department", "RDPR"),
    (r"\brevenue\b|tahsildar|land records|survey|khata|ಕಂದಾಯ", "Revenue Department", "REV"),
    (r"\bfood\b|civil supplies|ration|ಆಹಾರ|ಪಡಿತರ", "Food and Civil Supplies Department", "FOOD"),
    (r"urban|municipal|\bcity\b|corporation|\bbbmp\b|\bulb\b|town panchayat|ನಗರ", "Urban Development Department", ""),
    (r"\bhousing\b|ವಸತಿ", "Housing Department", ""),
    (r"women|child|\bwcd\b|disab|senior citizen|anganwadi|ಮಹಿಳ", "Department of Women & Child Development", ""),
    (r"energy|power|electric|\bescom\b|bescom|cesc|hescom|gescom|mescom|ವಿದ್ಯುತ್|ಇಂಧನ", "Energy Department", ""),
    (r"transport|\bksrtc\b|\bbus\b|\brto\b|ಸಾರಿಗೆ", "Transport Department", ""),
    (r"public works|\bpwd\b|ಲೋಕೋಪಯೋಗಿ", "Public Works Department", ""),
    (r"\bhome\b|police|ಗೃಹ|ಪೊಲೀಸ್", "Home Department", ""),
    (r"water resources|major irrigation|ಜಲಸಂಪನ್ಮೂಲ", "Water Resources Department", ""),
    (r"minor irrigation|ಸಣ್ಣ ನೀರಾವರಿ", "Minor Irrigation Department", ""),
    (r"medical education", "Medical Education Department", ""),
    (r"health|hospital|family welfare|ಆರೋಗ್ಯ", "Health and Family Welfare Department", ""),
    (r"forest|ecology|environment|ಅರಣ್ಯ", "Forest,Ecology and Environment Department", ""),
    (r"skill|livelihood|entrepreneur", "Skill Development, Entrepreneurship and Livelihood Department", ""),
    (r"social welfare|ಸಮಾಜ ಕಲ್ಯಾಣ", "Department of Social Welfare", ""),
    (r"higher education|college|university", "Higher Education Department", ""),
    (r"school|education|ಶಿಕ್ಷಣ", "Department of School Education and Literacy", ""),
    (r"backward|ಹಿಂದುಳಿದ", "Backward Classes Welfare Department", ""),
    (r"agricultur|farmer|ಕೃಷಿ", "Agriculture Department", ""),
    (r"labour|labor|ಕಾರ್ಮಿಕ", "Labour Department", ""),
    (r"cooperat|ಸಹಕಾರ", "Department of Cooperation", ""),
    (r"e-?gov|\bdpar\b.*e-?gov", "DPAR(E-Gov)", ""),
    (r"personnel|administrative services|\bdpar\b", "Department of Personnel and Administrative Services (DPAR)", ""),
    (r"minorit", "Minorites Welfare Department", ""),
    (r"animal|fisher|veterinar|ಪಶು", "Animal Husbandary and Fisheries Department", ""),
    (r"horticultur|sericultur|ತೋಟಗಾರಿಕೆ", "Horticulture and Sericulture Department", ""),
    (r"commerce|industr|ಕೈಗಾರಿಕ", "Commerce and Industries Department", ""),
    (r"tribe|tribal|\bst welfare", "Scheduled Tribes Welfare Department", ""),
    (r"finance|treasury|ಹಣಕಾಸು", "Finance Department", ""),
    (r"\blaw\b|legal", "Law Department", ""),
    (r"youth|sport", "Youth Empowerment and Sports Department", ""),
    (r"kannada and culture|culture", "Kannada and Culture Department", ""),
    (r"touris", "Tourism Department", ""),
    (r"information and pr|\bi&pr\b|public relations", "Information and PR Department", ""),
    (r"infrastructure|ports|inland water", "Department of Infrastructure Development, Ports and Inland Water Transport", ""),
    (r"electronics|\bit\b|biotech|science and technology", "Department of Electronics Information Technology Biotechnology and Science and Technology", ""),
]
_DEPTS: list[str] = []


def dept_names() -> list[str]:
    global _DEPTS
    if not _DEPTS:
        _DEPTS = [r["dept"] for r in db.q("SELECT dept, COUNT(*) n FROM ipgrs_records GROUP BY dept ORDER BY n DESC")]
    return _DEPTS


def resolve_dept(name) -> dict | None:
    """Any way of naming a department -> {name (as in iPGRS), short, code (pilot code or '')}."""
    t = str(name or "").strip().lower()
    if not t:
        return None
    if t.upper() in PILOT:
        t = {"REV": "revenue", "RDPR": "rdpr", "FOOD": "food"}[t.upper()]
    for rx, full, code in DEPT_ALIAS:
        if re.search(rx, t, re.I):
            real = next((d for d in dept_names() if d.lower().startswith(full.lower()[:24])), full)
            return {"name": real, "short": short_dept(real), "code": code}
    best = difflib.get_close_matches(t, [d.lower() for d in dept_names()], n=1, cutoff=0.55)
    if best:
        real = next(d for d in dept_names() if d.lower() == best[0])
        return {"name": real, "short": short_dept(real), "code": ""}
    return None


def short_dept(full: str) -> str:
    f = full or ""
    for a, b in (("Rural Development and Panchayath Raj Department", "RDPR"), ("Revenue Department", "Revenue"), ("Food and Civil Supplies Department", "Food & Civil Supplies"),
                 ("Department of Women & Child Development", "Women & Child Development"), ("Department of School Education and Literacy", "School Education"),
                 ("Department of Electronics", "Electronics & IT"), ("Department of Infrastructure", "Infrastructure & Ports"),
                 ("Department of Personnel and Administrative Services", "DPAR"), ("Forest,Ecology and Environment Department", "Forest & Environment")):
        if f.startswith(a):
            return b
    return re.sub(r"^Department of |\s*Department$", "", f).strip()


# ------------------------------------------------------------------ Kannada arguments from the live voice
KN_STATUS = [(r"ಬಾಕಿ|ಉಳಿದ|ತೆರೆದ|ಪೆಂಡಿಂಗ್", "open"), (r"ವಿಳಂಬ|ಗಡುವು ಮೀರ|ತಡ|ಓವರ್", "overdue"), (r"ಪರಿಹರ|ಮುಕ್ತಾಯ|ಇತ್ಯರ್ಥ", "resolved"),
             (r"ತಿರಸ್ಕೃತ|ತಿರಸ್ಕರ", "rejected"), (r"ಪರಿಶೀಲನ", "scrutiny")]


def normalise_args(args: dict) -> dict:
    """Arguments in Kannada script (the live voice sometimes passes the words as heard) -> the English the engine knows."""
    out = dict(args or {})
    kn = lambda v: isinstance(v, str) and re.search(r"[ಀ-೿]", v)
    if not any(kn(v) for v in out.values()):
        return out
    from . import chat, local_ai
    for k, v in list(out.items()):
        if not kn(v):
            continue
        if k == "status":
            out[k] = next((e for rx, e in KN_STATUS if re.search(rx, v)), v)
        elif k == "department":
            d = resolve_dept(v)
            out[k] = d["name"] if d else v
        elif k == "level":
            m = re.search(r"[1-3೧-೩]", v)
            out[k] = ("L" + m.group(0).translate(str.maketrans("೧೨೩", "123"))) if m else v
        elif k in ("taluk", "district", "gp", "place", "village", "entities"):
            tk = chat.taluk_in_text(v)
            if tk and k in ("taluk", "place"):
                out[k] = tk
                continue
            if k == "taluk" and len(v.split()) > 2:            # a whole Kannada sentence: a district in it, or nothing
                dists = {r["district"] for r in db.q("SELECT DISTINCT district FROM gazetteer") if r["district"]}
                hit = ""
                for w in v.split():
                    w2 = re.sub(r"(ಜಿಲ್ಲೆಯಲ್ಲಿ|ಜಿಲ್ಲೆ|ದಲ್ಲಿ|ನಲ್ಲಿ|ಯಲ್ಲಿ|ಲ್ಲಿ)$", "", w)
                    lat = local_ai.kn_to_latin(w2).lower()
                    mm = difflib.get_close_matches(lat, [d.lower() for d in dists], n=1, cutoff=0.8)
                    if mm:
                        hit = next(d for d in dists if d.lower() == mm[0]); break
                out.pop(k, None)
                if hit:
                    out["district"] = hit
                continue
            lat = local_ai.kn_to_latin(v)
            col = {"district": "district", "taluk": "taluk", "gp": "gp", "village": "village"}.get(k, "taluk")
            names = {r[col] for r in db.q(f"SELECT DISTINCT {col} FROM gazetteer") if r[col]}   # a district is matched among districts only
            lat = re.sub(r"(jilleyalli|jille|dalli|nalli|yalli|lli)$", "", lat.lower().strip())
            KN_EXTRA = {"maisooru": "Mysuru", "maisuru": "Mysuru", "bemgalooru": "Bengaluru", "bengalooru": "Bengaluru", "bemgaluru": "Bengaluru"}
            if col == "district" and lat in KN_EXTRA:
                out[k] = KN_EXTRA[lat]                         # the same word English uses (Bengaluru = Urban + Rural, as for "Bangalore")
                continue
            m = difflib.get_close_matches(lat, [n.lower() for n in names], n=1, cutoff=0.6 if col == "district" else 0.7)
            if m:
                out[k] = next(n for n in names if n.lower() == m[0])
            else:
                out.pop(k, None)                               # not resolvable: no filter rather than a wrong one
        else:
            out[k] = local_ai.kn_to_latin(v)
    return out


# ------------------------------------------------------------------ live caseload slices
BUCKETS = ["Overdue", "Due today", "1 day left", "2 days left", "3 days left", "4 days left", "5 days left", "6 days left", "7 days left", "8+ days left"]


def bucket(left: int) -> str:
    if left < 0:
        return "Overdue"
    if left == 0:
        return "Due today"
    if left <= 7:
        return f"{left} day{'s' if left > 1 else ''} left"
    return "8+ days left"


def escalated_ids() -> set:
    return {e["case_id"] for e in db.q("SELECT DISTINCT case_id FROM case_events WHERE what LIKE 'Auto-escalated%' OR what LIKE 'Re-opened by the citizen%' OR what LIKE 'Appealed%'")}


def _officers() -> dict:
    return {o["id"]: o for o in db.q("SELECT * FROM officers")}


def _label(o) -> str:
    return (o or {}).get("short") or (o or {}).get("name") or "Scrutiny desk"


def live_board(rows: list, scope: dict) -> dict:
    offs = _officers()
    esc = escalated_ids()
    open_ = [r for r in rows if r["status"] in OPEN]
    left = {r["id"]: sla_info(r)["left"] for r in open_}
    today = now().date()
    kp = {"total": len(rows), "open": len(open_), "overdue": sum(1 for r in open_ if left[r["id"]] < 0),
          "due_today": sum(1 for r in open_ if left[r["id"]] == 0), "due_3": sum(1 for r in open_ if 0 <= left[r["id"]] <= 3),
          "escalated": sum(1 for r in rows if r["id"] in esc), "escalated_open": sum(1 for r in open_ if r["id"] in esc),
          "l1": sum(1 for r in open_ if r["level"] == "L1"), "l2": sum(1 for r in open_ if r["level"] == "L2"), "l3": sum(1 for r in open_ if r["level"] == "L3"),
          "resolved": sum(1 for r in rows if r["status"] == "Resolved"), "rejected": sum(1 for r in rows if r["status"] == "Rejected"),
          "scrutiny": sum(1 for r in rows if r["status"] == "Scrutiny"), "vulnerable_open": sum(1 for r in open_ if r["vulnerable"]),
          "applications_open": sum(1 for r in open_ if r["kind"] == "APPLICATION"), "new_since_go_live": sum(1 for r in rows if not r["real"] and not r["synthetic"])}
    kp["not_escalated_open"] = kp["open"] - kp["escalated_open"]
    bk = Counter(bucket(left[r["id"]]) for r in open_)
    by = "gp" if scope.get("taluk") else "taluk" if scope.get("district") or scope.get("officer") else "district"
    if by == "district" and len({r["district"] for r in rows}) <= 1:
        by = "taluk"
    place = Counter((r[by] or "(taluk level)") for r in open_)
    od_place = Counter((r[by] or "(taluk level)") for r in open_ if left[r["id"]] < 0)
    offc = Counter(r["owner"] for r in open_)
    offod = Counter(r["owner"] for r in open_ if left[r["id"]] < 0)
    geo = Counter(r["district"] for r in open_ if r["district"])
    oldest = sorted((r for r in open_ if left[r["id"]] < 0), key=lambda r: left[r["id"]])[:5]
    return {"source": "live", "period": f"live caseload as of {now().strftime('%d %b %Y %H:%M')}",
            "kpis": kp,
            "by_level": [{"name": l, "count": kp[l.lower()]} for l in ("L1", "L2", "L3")],
            "days_left": [{"name": b, "count": bk.get(b, 0)} for b in BUCKETS],
            "place_by": by,
            "places": [{"name": k, "count": v, "overdue": od_place.get(k, 0), "district": next((r["district"] for r in open_ if (r[by] or "(taluk level)") == k), "")}
                       for k, v in place.most_common(12)],
            "services": [{"name": k, "count": v} for k, v in Counter(r["service"] for r in open_).most_common(8)],
            "departments": [{"name": PILOT.get(k, k), "count": v} for k, v in Counter(r["dept_code"] for r in open_).most_common()],
            "officers": [{"name": _label(offs.get(k)), "id": k, "level": (offs.get(k) or {}).get("level"), "open": v, "overdue": offod.get(k, 0)} for k, v in offc.most_common(8)],
            "status": [{"name": k, "count": v} for k, v in Counter(r["status"] for r in rows).most_common()],
            "escalation": [{"name": "Escalated", "count": kp["escalated_open"]}, {"name": "Not escalated", "count": kp["not_escalated_open"]}],
            "geo": dict(geo),
            "oldest_overdue": [{"id": r["id"], "service": r["service"], "taluk": r["taluk"], "gp": r["gp"], "officer": _label(offs.get(r["owner"])),
                                "level": r["level"], "days_overdue": -left[r["id"]]} for r in oldest],
            "as_of": today.isoformat()}


def ipgrs_board(where: str, p: list) -> dict:
    q1 = lambda sql, *a: db.q1(sql, tuple(p) + a)["n"]
    grp = lambda col, extra="", lim=12: [{"name": r["k"] or "-", "count": r["n"]} for r in
                                         db.q(f"SELECT {col} k, COUNT(*) n FROM ipgrs_records WHERE {where}{extra} GROUP BY {col} ORDER BY n DESC LIMIT {lim}", tuple(p))]
    open_w = " AND status='InProcess'"
    total = q1(f"SELECT COUNT(*) n FROM ipgrs_records WHERE {where}")
    kp = {"total": total, "open": q1(f"SELECT COUNT(*) n FROM ipgrs_records WHERE {where}{open_w}"),
          "closed": q1(f"SELECT COUNT(*) n FROM ipgrs_records WHERE {where} AND status='Closed by Officer'"),
          "scrutiny": q1(f"SELECT COUNT(*) n FROM ipgrs_records WHERE {where} AND status LIKE 'Registered%'"),
          "feedback": q1(f"SELECT COUNT(*) n FROM ipgrs_records WHERE {where} AND status LIKE 'Resolved%'"),
          "l1": q1(f"SELECT COUNT(*) n FROM ipgrs_records WHERE {where}{open_w} AND role='LMF'"),
          "l2": q1(f"SELECT COUNT(*) n FROM ipgrs_records WHERE {where}{open_w} AND role='L2'"),
          "l3": q1(f"SELECT COUNT(*) n FROM ipgrs_records WHERE {where}{open_w} AND role='L3'"),
          "sakala_tagged": q1(f"SELECT COUNT(*) n FROM ipgrs_records WHERE {where} AND lower(service_type)='sakala'"),
          "districts": q1(f"SELECT COUNT(DISTINCT district) n FROM ipgrs_records WHERE {where}")}
    dists = q1(f"SELECT COUNT(DISTINCT district) n FROM ipgrs_records WHERE {where}")
    by = "taluk" if dists <= 1 else "district"
    places = grp(by, open_w)
    geo = {r["name"].title(): r["count"] for r in grp("district", open_w, 40)}
    return {"source": "ipgrs", "period": "iPGRS sample week, 3-9 Oct 2026 (real records; no live clock)",
            "kpis": kp, "by_level": [{"name": "L1", "count": kp["l1"]}, {"name": "L2", "count": kp["l2"]}, {"name": "L3", "count": kp["l3"]}],
            "status": [{"name": {"InProcess": "In process", "Closed by Officer": "Closed by officer", "Registered & Sent for Scrutiny": "At scrutiny",
                                 "Resolved (Feedback Taken)": "Resolved with feedback"}.get(x["name"], x["name"]), "count": x["count"]} for x in grp("status")],
            "place_by": by, "places": [{**x, "name": x["name"].title(), "district": x["name"].title() if by == "district" else ""} for x in places],
            "services": grp("service", open_w, 8), "officers": [{"name": x["name"], "open": x["count"]} for x in grp("officer", open_w, 8)],
            "channels": grp("source"), "geo": geo}


def dashboard(args: dict) -> dict:
    """The whole picture of one thing: a department, district, taluk, Gram Panchayat, level, officer, service, or the state."""
    from .query import _match, PLACE_ALIAS, find_officer       # the same matching rules as every other answer
    a = {k: v for k, v in normalise_args(args or {}).items() if v not in (None, "", [], "any", "all", "overall", "statewide")}
    d = resolve_dept(a.get("department")) if a.get("department") else None
    scope = {k: a[k] for k in ("district", "taluk", "gp", "level", "officer", "service") if a.get(k)}
    if d:
        scope["department"] = d["short"]
    title = " · ".join(x for x in (scope.get("department"), scope.get("district"), scope.get("taluk"), scope.get("gp"),
                                     scope.get("level") and f"at {str(scope['level']).upper()}", scope.get("officer"), scope.get("service")) if x) or "Karnataka"
    if d and not d["code"]:                                   # a department outside the pilot: the real iPGRS sample week
        where, p = ["dept = ?"], [d["name"]]
        for f in ("district", "taluk", "gp"):
            if a.get(f):
                v = " ".join(PLACE_ALIAS.get(x, x) for x in str(a[f]).lower().replace(" district", "").replace(" taluk", "").split())
                where.append(f"lower({f}) LIKE ?"); p.append(f"%{v}%")
        if a.get("level"):
            where.append("role = ?"); p.append(str(a["level"]).upper().replace("L1", "LMF"))
        if a.get("service"):
            where.append("(lower(service) LIKE ? OR lower(grievance) LIKE ?)"); p += [f"%{str(a['service']).lower()}%"] * 2
        out = ipgrs_board(" AND ".join(where), p)
        out.update({"title": title, "scope": scope, "department": d})
        return out
    rows = db.q("SELECT * FROM cases")
    if d:
        rows = [r for r in rows if r["dept_code"] == d["code"]]
    for f in ("district", "taluk"):
        if a.get(f):
            rows = [r for r in rows if _match(r[f], a[f])]
    if a.get("gp"):
        rows = [r for r in rows if _match(r["gp"], a["gp"]) or _match(r["village"], a["gp"])]
    if a.get("level"):
        rows = [r for r in rows if r["level"] == str(a["level"]).upper() or r["status"] not in OPEN and False]
    if a.get("service"):
        s = str(a["service"]).lower()
        rows = [r for r in rows if s in f"{(r['service'] or '').lower()} {(r['grievance'] or '').lower()}"]
    if a.get("officer"):
        o = find_officer(a["officer"])
        rows = [r for r in rows if o and r["owner"] == o["id"]]
        if o:
            scope["officer"] = o["short"]
            title = title.replace(a["officer"], o["short"])
    out = live_board(rows, scope)
    out.update({"title": title, "scope": scope, "department": d})
    return out


def days_left_ok(r, n: int) -> bool:
    return r["status"] in OPEN and sla_info(r)["left"] == n
