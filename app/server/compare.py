"""Side-by-side comparisons for Sakala Mitra's stage visuals: "compare Piriyapatna, Hunsur and Mysuru", "Revenue vs RDPR
vs Food on open, overdue and resolved", "which districts have the most pending". Entities are matched against the live
caseload's districts, taluks, Gram Panchayats, departments, officers, services and channels (the kind is detected from
the names when not given). Every number is SQL over the live caseload (or the iPGRS sample when dataset=ipgrs)."""
from __future__ import annotations

import difflib
import re

from . import db
from .query import DEPT, OPEN, SRC, _dept_code, _low, find_officer
from .sla import sla_info

# how people say Karnataka's places and the departments (spoken names -> canonical in the data)
ALIASES = {
    "mysuru": ["mysore"], "bengaluru urban": ["bangalore urban", "bengaluru", "bangalore", "bengaluru city"], "bengaluru rural": ["bangalore rural"],
    "belagavi": ["belgaum"], "kalaburagi": ["gulbarga"], "vijayapura": ["bijapur"], "shivamogga": ["shimoga"], "tumakuru": ["tumkur"],
    "chikkamagaluru": ["chikmagalur", "chikamagalur"], "ballari": ["bellary"], "chamarajanagar": ["chamrajnagar", "chamarajanagara"],
    "dakshina kannada": ["mangaluru", "mangalore", "south kannada"], "uttara kannada": ["karwar", "north kannada"], "hubballi": ["hubli"],
    "dharwad": ["dharwar"], "bagalkote": ["bagalkot"], "davanagere": ["davangere"], "chitradurga": ["chitradurg"], "hassan": ["hasan"],
    "kolar": ["kolara"], "raichur": ["raichuru"], "koppal": ["koppala"], "haveri": [], "gadag": [], "bidar": [], "yadgir": ["yadgiri"],
    "mandya": [], "kodagu": ["coorg", "madikeri"], "udupi": [], "ramanagara": ["ramanagar"], "chikkaballapur": ["chikballapur"],
    "vijayanagara": ["vijayanagar", "hosapete"], "piriyapatna": ["periyapatna", "piriyapattana"], "hunsur": ["hunsuru", "hunsoor"],
    "revenue": ["revenue department", "revenue dept"], "rural development & panchayat raj": ["rdpr", "rural development", "panchayat raj", "panchayath raj", "rdpr department"],
    "food & civil supplies": ["food", "civil supplies", "food and civil supplies", "food department"],
}
METRICS = ("open", "overdue", "resolved", "rejected", "vulnerable", "escalated", "scrutiny", "total", "due_soon")
KIND_FIELD = {"district": "district", "taluk": "taluk", "gp": "gp", "department": "dept_code", "officer": "owner", "service": "service", "source": "src"}


def aliases_for(name: str) -> list[str]:
    n = _low(name)
    out = list(ALIASES.get(n, []))
    for k, v in ALIASES.items():
        if n in v and k not in out:
            out.append(k)
    first = re.split(r"[\s&/,-]+", n)[0]
    if len(first) >= 4 and first != n:
        out.append(first)
    return out


def _catalog():
    rows = db.q("SELECT DISTINCT district, taluk, gp, dept_code, owner, service, src FROM cases")
    cat = {k: {} for k in KIND_FIELD}
    for r in rows:
        for kind, f in KIND_FIELD.items():
            v = r[f]
            if v:
                cat[kind][v] = v
    offs = {o["id"]: o for o in db.q("SELECT id, short, name FROM officers")}
    cat["officer"] = {oid: (offs.get(oid) or {}).get("short", oid) for oid in cat["officer"]}
    cat["department"] = {c: DEPT.get(c, c) for c in cat["department"]}
    cat["source"] = {c: SRC.get(c, c) for c in cat["source"]}
    return cat


def _resolve(name: str, kind: str, cat: dict) -> tuple[str | None, str, float]:
    """(key in the data, display label, score) for one spoken entity within one kind."""
    n = _low(name)
    if not n:
        return None, "", 0.0
    if kind == "department":
        code = _dept_code(n)
        if code in cat["department"]:
            return code, cat["department"][code], 1.0
        return None, "", 0.0
    if kind == "officer":
        o = find_officer(name)
        return (o["id"], o["short"], 0.95) if o and o["id"] in cat["officer"] else (None, "", 0.0)
    best, label, score = None, "", 0.0
    for key, disp in cat[kind].items():
        cands = [_low(disp)] + aliases_for(disp)
        for c in cands:
            s = 1.0 if c == n else (0.92 if (len(n) >= 5 and (n in c or c in n)) else difflib.SequenceMatcher(None, c, n).ratio())
            if s > score:
                best, label, score = key, disp, s
    return (best, label, score) if score >= 0.84 else (None, "", score)


def detect(entities: list[str], by: str = "", cat: dict | None = None) -> tuple[str, list[dict]]:
    """The kind that matches most of the names (a stated `by` wins), with each name resolved."""
    cat = cat or _catalog()
    kinds = [by] if by in KIND_FIELD else ["district", "taluk", "department", "gp", "officer", "service", "source"]
    best_kind, best = "", None
    for k in kinds:
        res = [dict(zip(("key", "label", "score"), _resolve(e, k, cat)), asked=e) for e in entities]
        hits = sum(1 for r in res if r["key"])
        tot = sum(r["score"] for r in res)
        if best is None or (hits, tot) > (best[0], best[1]):
            best_kind, best = k, (hits, tot, res)
    return best_kind, best[2] if best else []


def _metrics(rows: list[dict]) -> dict:
    open_ = [r for r in rows if r["status"] in OPEN]
    lefts = [sla_info(r)["left"] for r in open_]
    esc = {e["case_id"] for e in db.q("SELECT DISTINCT case_id FROM case_events WHERE what LIKE 'Auto-escalated%'")} if rows else set()
    return {"open": len(open_), "overdue": sum(1 for x in lefts if x < 0), "due_soon": sum(1 for x in lefts if 0 <= x <= 2),
            "resolved": sum(1 for r in rows if r["status"] == "Resolved"), "rejected": sum(1 for r in rows if r["status"] == "Rejected"),
            "vulnerable": sum(1 for r in open_ if r["vulnerable"]), "escalated": sum(1 for r in rows if r["id"] in esc),
            "scrutiny": sum(1 for r in rows if r["status"] == "Scrutiny"), "total": len(rows)}


def compare(args: dict) -> dict:
    ents = args.get("entities") or args.get("names") or []
    if isinstance(ents, str):
        ents = [x.strip() for x in re.split(r",|\band\b|\bvs\.?\b|\bversus\b|;", ents) if x.strip()]
    ents = [e for e in ents if e][:8]
    metrics = args.get("metrics") or args.get("metric") or ["open"]
    if isinstance(metrics, str):
        metrics = [m.strip() for m in re.split(r",|\band\b|/", metrics) if m.strip()]
    metrics = [{"pending": "open", "late": "overdue", "delayed": "overdue", "solved": "resolved", "closed": "resolved", "all": "total", "cases": "total",
                "priority": "vulnerable", "auto-escalated": "escalated"}.get(_low(m), _low(m)) for m in metrics]
    metrics = [m for m in metrics if m in METRICS] or ["open"]
    dataset = _low(args.get("dataset"))
    cat = _catalog()
    by, res = detect(ents, _low(args.get("by")), cat)
    if not ents or not any(r["key"] for r in res):
        return {"found": False, "asked": ents, "by": by}
    field = KIND_FIELD[by]
    rows = db.q("SELECT * FROM cases")
    out_ents = []
    for r in res:
        if not r["key"]:
            continue
        sub = [c for c in rows if c[field] == r["key"]]
        vals = _metrics(sub)
        if dataset == "ipgrs":
            col = {"district": "district", "taluk": "taluk", "gp": "gp", "department": "dept", "service": "service", "source": "source"}.get(by)
            if col:
                vals["ipgrs_records"] = db.q1(f"SELECT COUNT(*) n FROM ipgrs_records WHERE lower({col}) LIKE ?", (f"%{_low(r['label'])[:10]}%",))["n"]
        out_ents.append({"name": r["label"], "asked": r["asked"], "aliases": aliases_for(r["label"]) + ([_low(r["asked"])] if _low(r["asked"]) != _low(r["label"]) else []),
                         "values": {m: vals[m] for m in metrics}, "all": vals, "district": _district_of(by, r["key"], sub),
                         "geo": {m: _geo(sub, m) for m in metrics} if by != "district" else {}})
    unmatched = [r["asked"] for r in res if not r["key"]]
    return {"found": True, "by": by, "metrics": metrics, "entities": out_ents, "unmatched": unmatched}


def _district_of(by: str, key: str, rows: list[dict]) -> str:
    """The district a compared thing sits in (for the map card): a district is itself; taluks / GPs / officers come from
    their cases or the gazetteer; departments, services and channels span the state (empty)."""
    if by == "district":
        return key
    if by in ("taluk", "gp", "officer"):
        if rows:
            return max(set(r["district"] for r in rows if r["district"]), key=lambda d: sum(1 for r in rows if r["district"] == d), default="")
        col = {"taluk": "taluk", "gp": "gp"}.get(by)
        if col:
            g = db.q1(f"SELECT district FROM gazetteer WHERE lower({col})=? LIMIT 1", (_low(key),))
            return g["district"] if g else ""
    return ""


def _geo(rows: list[dict], metric: str, esc: set | None = None) -> dict:
    """How many of `rows` meet `metric`, district by district (the map card's footprint)."""
    if metric in ("open", "overdue", "due_soon", "vulnerable"):
        rows = [r for r in rows if r["status"] in OPEN]
    if metric in ("overdue", "due_soon"):
        lefts = {r["id"]: sla_info(r)["left"] for r in rows}
        rows = [r for r in rows if (lefts[r["id"]] < 0 if metric == "overdue" else 0 <= lefts[r["id"]] <= 2)]
    elif metric == "vulnerable":
        rows = [r for r in rows if r["vulnerable"]]
    elif metric in ("resolved", "rejected", "scrutiny"):
        rows = [r for r in rows if r["status"] == metric.capitalize()]
    elif metric == "escalated":
        esc = esc if esc is not None else {e["case_id"] for e in db.q("SELECT DISTINCT case_id FROM case_events WHERE what LIKE 'Auto-escalated%'")}
        rows = [r for r in rows if r["id"] in esc]
    out: dict[str, int] = {}
    for r in rows:
        if r["district"]:
            out[r["district"]] = out.get(r["district"], 0) + 1
    return out


def ranking(args: dict) -> dict:
    """Top N of a kind by a metric (districts by overdue, officers by open...), for the bar race."""
    by = _low(args.get("by")) or "district"
    if by not in KIND_FIELD:
        by = "district"
    metric = _low(args.get("metric") or "open")
    metric = {"pending": "open", "late": "overdue"}.get(metric, metric)
    if metric not in METRICS:
        metric = "open"
    n = int(args.get("limit") or 8)
    cat = _catalog()
    rows = db.q("SELECT * FROM cases")
    field = KIND_FIELD[by]
    groups: dict[str, list] = {}
    for r in rows:
        k = r[field]
        if k:
            groups.setdefault(k, []).append(r)
    scored = [(cat[by].get(k, k), _metrics(v)[metric], k) for k, v in groups.items()]
    scored.sort(key=lambda x: -x[1])
    return {"by": by, "metric": metric, "total": sum(x[1] for x in scored), "distinct": len(scored),
            "entities": [{"name": lab, "aliases": aliases_for(lab), "values": {metric: val}, "district": _district_of(by, key, groups[key]),
                          "geo": {metric: _geo(groups[key], metric)} if by != "district" else {}} for lab, val, key in scored[:n]]}
