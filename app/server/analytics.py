"""Leadership intelligence: use cases 3, 8, 10, 14, 17, 18, 19, 21, 22, 23 (+ E-4 notices for UC 12).

Everything here is computed from the database (real iPGRS records, live pilot cases, real Sakala 2025 reports);
the model only writes the plain-language summary on top of computed facts.
"""
import io
import json
import re
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np
import pandas as pd

from . import ai, db, local_ai
from .config import PROJECT, DATA

LLM_EVAL = DATA / "llm_eval.json"
from .sla import now, sla_info, officer

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
PERF_COLS = ["sl", "district", "pop", "receipts", "disposals", "rejected", "rej_pct", "delayed", "late_pct", "intime", "intime_pct",
             "overdue", "overdue_per_lakh", "e2_w", "c2_w", "rec_per_lakh", "a2_w", "f2_w", "total_w", "rank"]
GSC_RX = re.compile(r"\b[A-Z]{2}\d{3}[A-Z]\d{9,10}\b")


# ======================= UC 21/23: Sakala monthly performance reports (Excel) =======================
def parse_perf_report(src):
    """Parse a Sakala district performance workbook (one sheet per month). Returns a DataFrame."""
    xl = pd.ExcelFile(src)
    out = []
    for sh in xl.sheet_names:
        raw = pd.read_excel(xl, sheet_name=sh, header=None, dtype=str)
        hdr = raw.index[raw.iloc[:, 0].astype(str).str.strip().str.upper().str.startswith("SL")]
        if not len(hdr):
            continue
        body = raw.iloc[hdr[0] + 1:].copy()
        body = body[body.iloc[:, 0].notna()]
        body = body.iloc[:, :len(PERF_COLS)]
        body.columns = PERF_COLS[:body.shape[1]]
        n = sh.strip().lower()
        m = next((i + 1 for i, mm in enumerate(MONTHS) if n.startswith(mm)), None)
        if not m:
            continue
        body["month"] = m
        for c in PERF_COLS[2:]:
            if c in body:
                body[c] = pd.to_numeric(body[c], errors="coerce")
        body["district"] = body["district"].astype(str).str.strip()
        out.append(body[body["receipts"].notna()])
    if not out:
        raise ValueError("No monthly sheets with an 'SL' header row were found.")
    return pd.concat(out, ignore_index=True)


def load_perf(df, source):
    db.run("CREATE TABLE IF NOT EXISTS sakala_perf (district TEXT, month INTEGER, receipts REAL, disposals REAL, rejected REAL, delayed REAL, "
           "intime REAL, overdue REAL, pop REAL, total_w REAL, rank REAL, source TEXT, PRIMARY KEY (district, month))")
    num = lambda v: None if pd.isna(v) else float(v)  # noqa: E731
    rows = [(r["district"], int(r["month"]), num(r["receipts"]), num(r["disposals"]), num(r["rejected"]), num(r["delayed"]), num(r["intime"]),
             num(r["overdue"]), num(r["pop"]), num(r["total_w"]), num(r["rank"]), source) for _, r in df.iterrows()]
    db.many("INSERT OR REPLACE INTO sakala_perf VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def ingest_perf():
    return load_perf(parse_perf_report(PROJECT / "combined_dec 1.xlsx"), "combined_dec 1.xlsx (Sakala 2025, all departments)")


def perf_frame():
    df = pd.DataFrame(db.q("SELECT * FROM sakala_perf"))
    return df[~df.district.str.contains("BBMP", case=False)]


def sakala_tracker():
    df = perf_frame()
    by_m = df.groupby("month").agg(receipts=("receipts", "sum"), disposals=("disposals", "sum"), rejected=("rejected", "sum"),
                                   delayed=("delayed", "sum"), overdue=("overdue", "sum")).reset_index()
    by_m["late_pct"] = (by_m.delayed / by_m.disposals * 100).round(2)
    by_m["rej_pct"] = (by_m.rejected / by_m.disposals * 100).round(2)
    g = df.groupby("district").agg(receipts=("receipts", "sum"), disposals=("disposals", "sum"), rejected=("rejected", "sum"),
                                   delayed=("delayed", "sum")).reset_index()
    g["late_pct"] = (g.delayed / g.disposals * 100).round(2)
    g["rej_pct"] = (g.rejected / g.disposals * 100).round(2)
    dec = df[df.month == df.month.max()].set_index("district")
    g["overdue_last"] = g.district.map(dec.overdue)
    g["rank_last"] = g.district.map(dec["rank"])
    tot = by_m.sum(numeric_only=True)
    return {"state": {"receipts": int(tot.receipts), "late_pct": round(tot.delayed / tot.disposals * 100, 2),
                      "rej_pct": round(tot.rejected / tot.disposals * 100, 2),
                      "overdue_first": int(by_m.iloc[0].overdue), "overdue_last": int(by_m.iloc[-1].overdue),
                      "months": int(by_m.month.nunique()), "districts": int(g.district.nunique())},
            "monthly": by_m.to_dict("records"),
            "districts": g.sort_values("late_pct", ascending=False).to_dict("records"),
            "source": db.q1("SELECT source FROM sakala_perf LIMIT 1")["source"]}


def early_warning():
    """UC 22: districts whose rejection / late / overdue trend is rising, and a fairer composite score."""
    df = perf_frame()
    last = df.month.max()
    out = []
    for d, g in df.groupby("district"):
        g = g.sort_values("month")
        g = g.assign(late=g.delayed / g.disposals * 100, rej=g.rejected / g.disposals * 100)
        recent, prior = g[g.month > last - 3], g[(g.month <= last - 3) & (g.month > last - 6)]
        if recent.empty or prior.empty:
            continue
        slope = lambda s: float(np.polyfit(range(len(s)), s.values, 1)[0]) if len(s) > 2 else 0.0  # noqa: E731
        f = {"district": d, "late_now": round(recent.late.mean(), 2), "late_before": round(prior.late.mean(), 2),
             "rej_now": round(recent.rej.mean(), 2), "rej_before": round(prior.rej.mean(), 2),
             "overdue_now": int(recent.iloc[-1].overdue), "overdue_before": int(prior.iloc[-1].overdue),
             "rej_trend": round(slope(g.rej.tail(6)), 3), "late_trend": round(slope(g.late.tail(6)), 3),
             "official_rank": int(g.iloc[-1]["rank"]) if pd.notna(g.iloc[-1]["rank"]) else None,
             "official_score": round(float(g.iloc[-1].total_w), 1) if pd.notna(g.iloc[-1].total_w) else None}
        flags = []
        if f["rej_now"] - f["rej_before"] > 0.8:
            flags.append(f"rejections up {f['rej_before']}% → {f['rej_now']}%")
        if f["late_now"] - f["late_before"] > 0.8:
            flags.append(f"late delivery up {f['late_before']}% → {f['late_now']}%")
        if f["overdue_before"] and f["overdue_now"] > f["overdue_before"] * 1.25 and f["overdue_now"] > 150:
            flags.append(f"overdue up {f['overdue_before']:,} → {f['overdue_now']:,}")
        f["flags"] = flags
        out.append(f)
    s = pd.DataFrame(out)
    # fairer score: equal weight to timeliness, rejection, backlog per lakh and trend (z-scores, higher = better)
    z = lambda x: (x - x.mean()) / (x.std() or 1)  # noqa: E731
    pop = df[df.month == last].set_index("district")["pop"]
    s["overdue_pl"] = s.apply(lambda r: r.overdue_now / pop.get(r.district, np.nan) * 1e5, axis=1)
    s["fair_score"] = (50 + 10 * (-z(s.late_now) - z(s.rej_now) - z(s.overdue_pl.fillna(s.overdue_pl.mean())) - z(s.rej_trend + s.late_trend)) / 2).round(1)
    s["fair_rank"] = s.fair_score.rank(ascending=False).astype(int)
    off = s.official_score.dropna()
    return {"districts": s.sort_values("fair_rank").replace({np.nan: None}).to_dict("records"),
            "flagged": [r for r in s.sort_values("rej_now", ascending=False).to_dict("records") if r["flags"]],
            "official_spread": [round(float(off.min()), 1), round(float(off.max()), 1)] if len(off) else None,
            "fair_spread": [float(s.fair_score.min()), float(s.fair_score.max())]}


# ======================= UC 3 / 8: data quality + misrouting on the 9,999 real records =======================
_CACHE = {}


def data_quality():
    if "dq" in _CACHE:
        return _CACHE["dq"]
    recs = db.q("SELECT gid, text_masked, dept_code, service, taluk, gp, status, source, officer, role FROM ipgrs_records")
    raw = pd.read_excel(PROJECT / "Sample grievance cases.xlsx", sheet_name=0, dtype=str, usecols=["G.Id", "Grievance Description"]).fillna("")
    phone = raw["Grievance Description"].str.contains(r"(?<!\d)[6-9]\d{9}(?!\d)", regex=True).sum()
    aadhaar = raw["Grievance Description"].str.contains(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)", regex=True).sum()
    gsc = raw["Grievance Description"].str.contains(GSC_RX.pattern, regex=True).sum()
    texts = Counter(r["text_masked"].strip().lower() for r in recs if len(r["text_masked"].strip()) > 15)
    dup = sum(n for n in texts.values() if n > 1)
    general = sum(1 for r in recs if r["service"] in ("General", "General Schemes"))
    out = {"total": len(recs),
           "checks": [
               {"k": "Phone numbers written inside the complaint text", "n": int(phone), "fix": "Masked automatically before any AI step"},
               {"k": "Aadhaar-like 12-digit numbers in the text", "n": int(aadhaar), "fix": "Masked automatically"},
               {"k": "Sakala GSC application numbers quoted", "n": int(gsc), "fix": "Linked to the Sakala application (grievance → Sakala bridge)"},
               {"k": "Missing Gram Panchayat / village", "n": sum(1 for r in recs if not r["gp"]), "fix": "Completion agent asks the citizen"},
               {"k": "Missing taluk", "n": sum(1 for r in recs if not r["taluk"]), "fix": "Completion agent asks the citizen"},
               {"k": "Very short description (< 20 characters)", "n": sum(1 for r in recs if len(r["text_masked"].strip()) < 20), "fix": "Agent asks one follow-up question"},
               {"k": "Exact duplicate complaints (same text)", "n": dup, "fix": "Linked to the first open request"},
               {"k": "Filed under a vague 'General' service", "n": general, "fix": "AI re-classifies to a specific service"},
               {"k": "Waiting in 'Registered & Sent for Scrutiny'", "n": sum(1 for r in recs if r["status"].startswith("Registered")), "fix": "AI routes in seconds; only low-confidence cases go to a person"},
           ]}
    _CACHE["dq"] = out
    return out


def misrouting(limit=40):
    """Real records whose filed service strongly disagrees with the model trained on all records (UC 8)."""
    if "mis" in _CACHE:
        return _CACHE["mis"]
    recs = db.q("SELECT gid, text_masked, service, service_id, dept_code, officer, taluk, district, source FROM ipgrs_records "
                "WHERE service_id IS NOT NULL AND length(text_masked) > 25")
    vs, ms = local_ai._M["vs"], local_ai._M["ms"]
    P = ms.predict_proba(vs.transform([r["text_masked"] for r in recs]))
    names = {s["id"]: s["name"] for s in db.q("SELECT id, name FROM services")}
    flags = []
    for r, p in zip(recs, P):
        i = int(np.argmax(p))
        sid, prob = int(ms.classes_[i]), float(p[i])
        filed_prob = float(p[list(ms.classes_).index(r["service_id"])]) if r["service_id"] in ms.classes_ else 0.0
        if sid != r["service_id"] and prob >= 0.8 and filed_prob < 0.05:
            flags.append({"gid": r["gid"], "text": r["text_masked"][:180], "filed": r["service"], "suggested": names.get(sid, ""),
                          "confidence": round(prob, 2), "officer": r["officer"], "district": r["district"], "source": r["source"]})
    kridl = db.q1("SELECT COUNT(*) n FROM ipgrs_records WHERE line LIKE 'Karnataka Rural Infrastructure%' AND service='General'")["n"]
    out = {"n_checked": len(recs), "n_flagged": len(flags), "kridl_general": kridl,
           "by_source": Counter(f["source"] for f in flags).most_common(), "examples": sorted(flags, key=lambda f: -f["confidence"])[:limit]}
    _CACHE["mis"] = out
    return out


# ======================= UC 10: accuracy proof =======================
def accuracy(run_llm=False, n=40):
    out = {"routing": db.kv_get("routing_eval"), "local_model": db.kv_get("model_eval"), "llm": saved_llm_eval()}
    if run_llm and ai.status()["llm"]:
        out["llm"] = llm_eval(n)
    return out


def llm_eval(n=40):
    """End-to-end on real Mysuru pilot records: model reads the masked text → service → router → officer, vs. what iPGRS did."""
    from .routing import route
    rows = db.q("""SELECT r.gid, r.text_masked, r.service_id, r.dept_code, r.taluk, r.gp, c.owner FROM ipgrs_records r
                   JOIN cases c ON c.id = 'GR-' || r.gid WHERE c.real=1 AND r.service_id IS NOT NULL AND length(r.text_masked) > 25
                   ORDER BY r.gid LIMIT ?""", (n,))

    def one(r):
        try:
            u = ai.understand(r["text_masked"])
        except Exception as e:  # noqa: BLE001
            return {"gid": r["gid"], "error": str(e)[:80]}
        res = {"gid": r["gid"], "dept_ok": u.get("dept_code") == r["dept_code"], "svc_ok": u.get("service_id") == r["service_id"], "conf": u.get("conf", 0)}
        if u.get("service_id"):
            rt = route(u["service_id"], r["taluk"], r["gp"])
            res["officer_ok"] = bool(rt and rt.get("officer") == r["owner"])
        else:
            res["officer_ok"] = False
        return res
    t0 = datetime.now()
    res = ai.parallel(one, rows, workers=8)
    ok = [r for r in res if "error" not in r]
    # guardrail 2: tune the auto-route threshold from measured accuracy. Lowest threshold whose auto-routed cases are
    # >= 90% correct on the exact service while still auto-routing at least 70% of real complaints (floor 0.4, cap 0.75).
    thr = 0.55
    for t in [x / 100 for x in range(40, 80, 5)]:
        above = [r for r in ok if r["conf"] >= t]
        if above and len(above) / max(1, len(ok)) >= 0.7 and np.mean([r["svc_ok"] for r in above]) >= 0.9:
            thr = t
            break
    db.kv_set("low_conf", thr)
    out = {"n": len(ok), "errors": len(res) - len(ok), "threshold": thr, "auto_routed_share": round(sum(r["conf"] >= thr for r in ok) / max(1, len(ok)), 3),
           "dept_acc": round(np.mean([r["dept_ok"] for r in ok]), 3) if ok else None,
           "service_acc": round(np.mean([r["svc_ok"] for r in ok]), 3) if ok else None,
           "officer_acc": round(np.mean([r["officer_ok"] for r in ok]), 3) if ok else None,
           "seconds": (datetime.now() - t0).seconds, "model": ai.status()["model"], "at": datetime.now().isoformat(timespec="minutes")}
    LLM_EVAL.write_text(json.dumps(out), encoding="utf-8")      # kept outside the DB so a demo reset keeps it
    return out


def saved_llm_eval():
    return json.loads(LLM_EVAL.read_text(encoding="utf-8")) if LLM_EVAL.exists() else None


# ======================= UC 14: grievance → Sakala bridge =======================
def gsc_bridge(text):
    m = GSC_RX.search(text or "")
    if not m:
        return None
    no = m.group(0)
    c = db.q1("SELECT * FROM cases WHERE id=? OR id=?", (no, "SK-" + no))
    payment = any(w in (text or "").lower() for w in ("not received", "amount", "credited", "ಬಂದಿಲ್ಲ", "ಹಣ", "money"))
    res = {"gsc": no, "found": bool(c), "payment_issue": payment}
    if c:
        s = sla_info(c)
        sk = json.loads(c["sakala"]) if c["sakala"] else {}
        res.update(case_id=c["id"], service=c["service"], officer=officer(c["owner"])["short"], left=s["left"], status=c["status"],
                   rights=(f"Sakala rights apply: the legal deadline is {'passed by ' + str(-s['left']) + ' days' if s['left'] < 0 else str(s['left']) + ' days away'}; "
                           f"first appeal to {officer(sk['CO'])['short']} within 30 days, compensation ₹20/day up to ₹500." if sk else ""))
    res["advice"] = ("This is about a payment after the service was delivered (for example a pension amount), so Sakala delay rights do not apply; "
                     "it is handled as a grievance." if payment else
                     "This complaint quotes a Sakala application, so the application's legal deadline and appeal rights apply.")
    return res


# ======================= UC 17: Praja Seva historical intelligence =======================
def historical(district="Mysuru"):
    recs = pd.DataFrame(db.q("SELECT * FROM ipgrs_records"))
    pil = recs[recs.dept_code != ""]
    camp = recs[recs.source == "Praja Seva Abhiyana"]
    recs["day"] = recs.created.str[:10]
    by_day = recs.groupby(["day", "source"]).size().unstack(fill_value=0)
    mys = pil[pil.district == district]
    top_taluk = {t: Counter(g.service).most_common(3) for t, g in mys.groupby("taluk") if len(g) >= 10}
    vul_rx = r"ವಿಧವೆ|widow|ಪಿಂಚಣಿ|pension|ವೃದ್ಧ|old age|ಅಂಗವಿಕಲ|disabled|ಮಾಸಾಶನ"
    vul = pil[pil.text_masked.str.contains(vul_rx, case=False, regex=True) & (pil.status == "InProcess")]
    rep = Counter(re.sub(r"\W+", " ", t.lower()).strip()[:60] for t in pil.text_masked if len(t) > 30)
    out = {"total": len(recs), "pilot": len(pil), "camp_share": round(len(camp) / len(recs) * 100, 1),
           "by_day": {d: {s: int(v) for s, v in row.items() if v} for d, row in by_day.iterrows()},
           "biggest_day": by_day.sum(axis=1).idxmax(), "biggest_day_n": int(by_day.sum(axis=1).max()),
           "sources": Counter(recs.source).most_common(),
           "scrutiny_stuck": {s: int(n) for s, n in Counter(recs[recs.status.str.startswith("Registered")].source).most_common()},
           "scrutiny_rate_app": round((recs[recs.source == "Mobile App"].status.str.startswith("Registered")).mean() * 100, 1),
           "top_issues_by_taluk": top_taluk, "vulnerable_waiting": int(len(vul)),
           "repeat_complaints": sum(1 for n in rep.values() if n > 1),
           "top_services_state": Counter(pil.service).most_common(8)}
    return out


# ======================= UC 19: hotspots =======================
def hotspots(min_n=3):
    open_ = db.q("SELECT service, gp, taluk, COUNT(*) n, SUM(vulnerable) v, GROUP_CONCAT(id) ids FROM cases "
                 "WHERE status NOT IN ('Resolved','Rejected') AND gp<>'' AND service<>'' GROUP BY service, gp, taluk HAVING n>=? ORDER BY n DESC LIMIT 12", (min_n,))
    hist = db.q("SELECT service, gp, taluk, COUNT(*) n FROM ipgrs_records WHERE district='Mysuru' AND gp<>'' AND service_id IS NOT NULL "
                "GROUP BY service, gp, taluk HAVING n>=? ORDER BY n DESC LIMIT 12", (min_n,))
    return {"open": open_, "week": hist}


def hotspot_fixes(spots):
    if not spots:
        return []
    facts = [{"place": f"{s['gp']} GP, {s['taluk']}", "service": s["service"], "complaints": s["n"]} for s in spots[:6]]
    schema = {"type": "object", "additionalProperties": False, "required": ["items"], "properties": {"items": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["place", "root_cause", "fix"],
        "properties": {"place": {"type": "string"}, "root_cause": {"type": "string"}, "fix": {"type": "string"}}}}}}
    j = ai.chat("hotspots", [{"role": "system", "content": "For each cluster of repeated citizen complaints in rural Karnataka, infer the most likely root "
                                                          "cause and one practical fix an officer can order this week. Be specific, one sentence each, no invented numbers."},
                             {"role": "user", "content": json.dumps(facts)}], schema=schema, max_tokens=800)
    return j["items"]


# ======================= UC 12/18: Wednesday Review Pack + E-4 notices =======================
def review_facts(level="cs", officer_id=""):
    cases = db.q("SELECT * FROM cases")
    openc = [c for c in cases if c["status"] not in ("Resolved", "Rejected")]
    if level != "cs" and officer_id:
        team = {officer_id} | {o["id"] for o in db.q("SELECT id FROM officers WHERE up_id=?", (officer_id,))}
        team |= {o["id"] for o in db.q("SELECT id FROM officers WHERE up_id IN (%s)" % ",".join("?" * len(team)), tuple(team))}
        openc = [c for c in openc if c["owner"] in team]
    over = [c for c in openc if sla_info(c)["left"] < 0]
    by_off = Counter(c["owner"] for c in over)
    issues = Counter(c["service"] or "Scrutiny desk" for c in openc).most_common(6)
    esc = db.q("SELECT COUNT(DISTINCT case_id) n FROM case_events WHERE what LIKE 'Auto-escalated%'")["n"] if False else \
        db.q1("SELECT COUNT(DISTINCT case_id) n FROM case_events WHERE what LIKE 'Auto-escalated%'")["n"]
    sk_late = [c for c in openc if c["kind"] == "APPLICATION" and sla_info(c)["left"] < 0]
    perf = None
    try:
        t = sakala_tracker()
        mys = next((d for d in t["districts"] if d["district"].lower().startswith("mysuru")), None)
        perf = {"mysuru_late_pct": mys["late_pct"] if mys else None, "mysuru_rej_pct": mys["rej_pct"] if mys else None,
                "state_late_pct": t["state"]["late_pct"]}
    except Exception:  # noqa: BLE001
        pass
    return {"as_of": now().strftime("%d %b %Y"), "scope": level, "open": len(openc), "overdue": len(over),
            "vulnerable_waiting": sum(1 for c in openc if c["vulnerable"]), "auto_escalated": esc,
            "top_issues": issues, "most_overdue_officers": [(officer(k)["short"], n) for k, n in by_off.most_common(5)],
            "sakala_deadlines_missed": [(c["id"], c["service"]) for c in sk_late],
            "stuck_examples": [(c["id"], c["service"], officer(c["owner"])["short"], -sla_info(c)["left"]) for c in sorted(over, key=lambda c: sla_info(c)["left"])[:4]],
            "sakala_2025": perf}


def review_pack(level="cs", officer_id=""):
    f = review_facts(level, officer_id)
    html = kn = None
    if ai.status()["llm"]:
        try:
            html = ai.brief("pack_en", "Write the Wednesday Review Pack for the Karnataka Chief Secretary's grievance review: 1) position, "
                                       "2) top issues, 3) where it is stuck (name officers and case ids), 4) three decisions needed this week. Crisp, factual.", f)
            kn = ai.brief("pack_kn", "Write the same Wednesday Review Pack in simple, formal Kannada (ಕನ್ನಡ), 4 short sections.", f)
        except Exception:  # noqa: BLE001
            html = kn = None
    return {"facts": f, "html": html, "kn": kn}


def e4_defaulters(threshold=7):
    """Sakala Rules: more than 7 defaults by an officer → Form E-4 show-cause. Counts overdue items per officer."""
    over = Counter(c["owner"] for c in db.q("SELECT * FROM cases WHERE status NOT IN ('Resolved','Rejected')") if sla_info(c)["left"] < 0)
    return [{"officer": officer(k)["name"], "id": k, "defaults": n} for k, n in over.most_common() if n > threshold]


# ======================= UC 23: Excel / CSV upload =======================
def upload(file_bytes, filename):
    """Accepts (a) a Sakala monthly performance workbook, or (b) a sheet of complaints with a description column.
    (b) runs every row through the same 8-stage pipeline and routes it to an officer."""
    from . import pipeline
    bio = io.BytesIO(file_bytes)
    if filename.lower().endswith((".xlsx", ".xls")):
        try:
            perf = parse_perf_report(bio)
            n = load_perf(perf, filename)
            return {"kind": "performance_report", "rows": n, "months": int(perf.month.nunique()), "districts": int(perf.district.nunique())}
        except ValueError:
            bio.seek(0)
        df = pd.read_excel(bio, dtype=str).fillna("")
    else:
        df = pd.read_csv(bio, dtype=str).fillna("")
    cols = {c.lower().strip(): c for c in df.columns}
    tcol = next((cols[c] for c in cols if any(k in c for k in ("description", "complaint", "grievance", "text", "ದೂರು"))), None)
    if not tcol:
        raise ValueError("No complaint description column found (expected a column named Description / Complaint / Grievance).")
    vcol = next((cols[c] for c in cols if any(k in c for k in ("village", "gp", "panchayat"))), None)
    tkcol = next((cols[c] for c in cols if "taluk" in c), None)
    results = []
    for _, r in df.head(50).iterrows():
        text = str(r[tcol]).strip()
        if not text:
            continue
        hint = " ".join(str(r[c]) for c in (vcol, tkcol) if c)
        res = pipeline.process(text + (f" ({hint})" if hint else ""), src="upload")
        results.append({"text": text[:120], **res})
    ok = sum(1 for r in results if r.get("case_id"))
    return {"kind": "complaints", "rows": len(results), "routed": ok, "results": results}
