"""Builds the POC database from the real iPGRS sample (python -m server.ingest).

Everything routing depends on is LEARNED from the 9,999 real grievances, not typed by hand:
  * category master   Department › Line department › Service › Grievance (as used in iPGRS)
  * role rules        which kind of officer actually handles each service (e.g. Khata → Tahsildar)
  * gazetteer         village → Gram Panchayat → taluk → district, for every place in the data (31 districts, 235 taluks)
  * officer master    one named field officer per role per taluk (and one PDO per Gram Panchayat) for the whole state,
                      plus their supervisors (L2/L3) per district; the real iPGRS designation is kept as data_name
  * live caseload     every real grievance of the three pilot departments, statewide, with its real officer
The Mysuru officer ids used in the demo (tah_piriyapatna, pdo_piriyapatna_attigodu, ac_hunsur, dc_mys, …) are unchanged.
"""
import difflib
import json
import re
from collections import Counter, defaultdict
from datetime import timedelta

import pandas as pd

from . import db
from .config import SOURCE_XLSX, PILOT_TALUKS, PILOT_DISTRICT, DEMO_START
from .privacy import mask

DEPT_CODE = {"Revenue Department": "REV", "Rural Development and Panchayath Raj Department": "RDPR",
             "Food and Civil Supplies Department": "FOOD"}
DEPT_STYLE = {"REV": ("ಕಂದಾಯ ಇಲಾಖೆ", "#26732f"), "RDPR": ("ಗ್ರಾಮೀಣಾಭಿವೃದ್ಧಿ ಮತ್ತು ಪಂಚಾಯತ್ ರಾಜ್ ಇಲಾಖೆ", "#3b7dd8"),
              "FOOD": ("ಆಹಾರ ಮತ್ತು ನಾಗರಿಕ ಸರಬರಾಜು ಇಲಾಖೆ", "#da6823")}
DEPT_HEAD_ROLE = {"REV": "TAHSILDAR", "RDPR": "EO_TP", "FOOD": "FI"}      # fallback when a line department has no pilot officer
MODELLED_ROLES = {"PDO", "TAHSILDAR", "ADLR", "FI", "AE_RDWS", "AEE_PRED", "EO_TP", "SUBREG"}
SUBDIVISION = {"Piriyapatna": "Hunsur", "Hunsur": "Hunsur", "Mysuru": "Mysuru"}     # Mysuru district's two AC sub-divisions (known)
L1_ROLES = [  # (role, id prefix, dept, long name, short name, who it reports to: "ac" | "ddlr" | "dc" | "ddf" | "eo")
    ("TAHSILDAR", "tah", "REV", "Tahsildar Grade-1, {t}", "Tahsildar {t}", "ac"),
    ("ADLR", "adlr", "REV", "ADLR (Taluk Survey), {t}", "ADLR {t}", "ddlr"),
    ("SUBREG", "subreg", "REV", "Sub-Registrar, {t}", "Sub-Registrar {t}", "dc"),
    ("FI", "fi", "FOOD", "Food Inspector, {t}", "Food Inspector {t}", "ddf"),
    ("AEE_PRED", "aee", "RDPR", "Assistant Executive Engineer (PRED), {t}", "AEE PRED {t}", "eo"),
    ("AE_RDWS", "rdws", "RDPR", "AE/JE (Rural Drinking Water), {t}", "AE RDWS {t}", "eo"),
]


def split_bi(s):
    """'English/ಕನ್ನಡ' → ('English', 'ಕನ್ನಡ')."""
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    m = re.match(r"^(.*?[A-Za-z0-9)\].]) ?/ ?([^A-Za-z].*)$", s)
    return (m.group(1).strip(), m.group(2).strip()) if m else (s, "")


def officer_role(s):
    t = re.sub(r"\s+", " ", str(s or "")).lower()
    if "panchayat development officer" in t: return "PDO"
    if "chief executive officer" in t: return "ZP_CEO"
    if "deputy commissioner" in t: return "DC"
    if "assistant comissioner" in t or "assistant commissioner" in t: return "AC"
    if "ddlr" in t: return "DDLR"
    if "adlr" in t or "surveyor" in t: return "ADLR"
    if "tahsildar" in t or "tahasildar" in t or "case worker" in t: return "TAHSILDAR"
    if "food inspector" in t: return "FI"
    if "deputy director/jd" in t: return "DD_FOOD"
    if "rdws" in t or "assistance engineer/junior engineer" in t: return "AE_RDWS"
    if "pred" in t: return "AEE_PRED"
    if "executive officer" in t: return "EO_TP"
    if "sub-registrar" in t or "sub registrar" in t: return "SUBREG"
    return "OTHER"


def title(s):
    return " ".join(w.capitalize() if not w[:2].isupper() or len(w) > 3 else w for w in str(s).lower().split()) if s else ""


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


def norm_taluk(t):
    t = str(t or "").strip()
    t = {"SARAGURU": "Saraguru"}.get(t, t)
    return title(t) if t.isupper() else t          # MUDALGI → Mudalgi; Piriyapatna stays


def clean_name(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def load_frame():
    df = pd.read_excel(SOURCE_XLSX, sheet_name=0, dtype=str).fillna("")
    df["dept_en"] = df["Department"].map(lambda s: split_bi(s)[0])
    df["dept_code"] = df["dept_en"].map(DEPT_CODE).fillna("")
    df["line_en"] = df["Line Department"].map(lambda s: split_bi(s)[0])
    df["svc_en"] = df["Service Name"].map(lambda s: split_bi(s)[0])
    df["gr_en"] = df["Grievance Name"].map(lambda s: split_bi(s)[0])
    df["officer"] = df["Pending with / Closed By"].map(clean_name)
    df["role"] = df["officer"].map(officer_role)
    gpv = df["GP/Village/Hobli"].str.split(" / ", n=1)
    df["gp"] = gpv.map(lambda p: title(p[0]) if p and p[0] else "")
    df["village"] = gpv.map(lambda p: title(p[1]) if len(p) > 1 else (title(p[0]) if p and p[0] else ""))
    df["Taluk"] = df["Taluk"].map(norm_taluk)
    df["District"] = df["District"].str.strip().str.title().str.replace(" And ", " and ")
    return df


def build():
    db.reset()
    pristine = db.DB_PATH.with_name("sakala_pristine.db")
    if pristine.exists():
        pristine.unlink()
    df = load_frame()
    pilot = df[df.dept_code != ""]

    # ---------- departments (all 38, pilot flag) ----------
    depts = []
    for d in sorted(df.dept_en.unique()):
        code = DEPT_CODE.get(d, slug(d)[:24].upper())
        kn = split_bi(df[df.dept_en == d]["Department"].iloc[0])[1]
        style = DEPT_STYLE.get(code, (kn, "#8a9a93"))
        depts.append((code, d, style[0] if code in DEPT_STYLE else kn, style[1], int(code in DEPT_STYLE)))
    db.many("INSERT INTO departments VALUES (?,?,?,?,?)", depts)

    # ---------- line departments / services / grievance types (pilot departments) ----------
    line_id, svc_id = {}, {}
    for (code, line), g in pilot.groupby(["dept_code", "line_en"]):
        line_id[(code, line)] = len(line_id) + 1
        db.run("INSERT INTO line_departments VALUES (?,?,?,?,?)",
               (line_id[(code, line)], code, line, split_bi(g["Line Department"].iloc[0])[1], len(g)))
    lmf = pilot[pilot["Officer Role"] == "LMF"]
    for (code, line, svc), g in pilot.groupby(["dept_code", "line_en", "svc_en"]):
        sid = len(svc_id) + 1
        svc_id[(code, line, svc)] = sid
        roles = Counter(lmf[(lmf.dept_code == code) & (lmf.line_en == line) & (lmf.svc_en == svc)]["role"])
        if sum(roles.values()) < 3:     # thin evidence → learn from the whole line department
            roles = Counter(lmf[(lmf.dept_code == code) & (lmf.line_en == line)]["role"])
        modelled = [(r, n) for r, n in roles.most_common() if r in MODELLED_ROLES]
        role, n = modelled[0] if modelled else (DEPT_HEAD_ROLE[code], 0)
        share = n / max(1, sum(roles.values()))
        db.run("INSERT INTO services VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (sid, line_id[(code, line)], code, svc.split(":")[0].strip() if len(svc) > 60 else svc, svc, split_bi(g["Service Name"].iloc[0])[1],
                int((g["Service Type"] == "Sakala").mean() > 0.5), len(g), role, round(share, 3), int(sum(roles.values()))))
        for gr, k in Counter(g["gr_en"]).most_common():
            if gr:
                db.run("INSERT INTO grievance_types(service_id,name,n_real) VALUES (?,?,?)", (sid, gr, k))

    # ---------- gazetteer: village → GP → taluk → district, for every place in the data ----------
    geo = df[df.gp != ""]
    gaz = Counter(zip(geo.village, geo.gp, geo.Taluk, geo.District))
    db.many("INSERT INTO gazetteer VALUES (?,?,?,?,?)", [(v, g, t, d, n) for (v, g, t, d), n in gaz.items()])
    gps = defaultdict(set)
    for (_, g, t, d) in gaz:
        gps[(d, t)].add(g)

    # ---------- officer master: every taluk in the data, every GP, per-district supervisors ----------
    seen = Counter(df["officer"])
    by_role = defaultdict(Counter)            # (district, taluk, role) -> officer strings seen in that taluk for that role
    for r in df[["District", "Taluk", "role", "officer"]].itertuples(index=False):
        by_role[(r.District, r.Taluk, r.role)][r.officer] += 1
    by_dist_role = defaultdict(Counter)       # (district, role) -> officer strings (supervisors)
    for r in df[["District", "role", "officer"]].itertuples(index=False):
        by_dist_role[(r.District, r.role)][r.officer] += 1
    by_pdo = defaultdict(Counter)             # (district, taluk, gp) -> PDO strings
    for r in df[df.role == "PDO"][["District", "Taluk", "gp", "officer"]].itertuples(index=False):
        if r.gp:
            by_pdo[(r.District, r.Taluk, r.gp)][r.officer] += 1
    pdo_place = {s: s.split(" - ")[-1].strip() for s in seen if "Panchayat Development Officer" in s}

    offs, name_map, name_votes = [], {}, {}

    def add(oid, name, short, dept, level, role, taluk, gp, up, district, strings=None):
        strings = strings or Counter()
        dn, n = (strings.most_common(1)[0] if strings else ("", 0))
        offs.append((oid, name, short, dept, level, role, taluk, gp, up, dn, int(bool(dn)), int(sum(strings.values())), district))
        for s, k in strings.items():           # an iPGRS spelling belongs to the officer in whose taluk it occurs most
            if k > name_votes.get(s, 0):
                name_votes[s], name_map[s] = k, oid

    districts = sorted(df.District.unique())
    taluks_of = defaultdict(set)
    for r in df[["District", "Taluk"]].drop_duplicates().itertuples(index=False):
        if r.Taluk:
            taluks_of[r.District].add(r.Taluk)
    for district in districts:
        mys = district == PILOT_DISTRICT
        ds = slug(district)
        dc = "dc_mys" if mys else f"dc_{ds}"
        ceo = "ceo_zp" if mys else f"ceo_zp_{ds}"
        ddlr = "ddlr_mys" if mys else f"ddlr_{ds}"
        ddf = "dd_food" if mys else f"dd_food_{ds}"
        add(dc, f"Deputy Commissioner, {district}", f"DC {district}", "REV", "L3", "DC", "", "", None, district, by_dist_role[(district, "DC")])
        add(ceo, f"Chief Executive Officer, Zilla Panchayat {district}", f"ZP CEO {district}", "RDPR", "L3", "ZP_CEO", "", "", None, district, by_dist_role[(district, "ZP_CEO")])
        add(ddlr, f"Deputy Director of Land Records, {district}", f"DDLR {district}", "REV", "L2", "DDLR", "", "", dc, district, by_dist_role[(district, "DDLR")])
        add(ddf, f"Deputy Director, Food & Civil Supplies, {district}", f"DD Food {district}", "FOOD", "L2", "DD_FOOD", "", "", dc, district, by_dist_role[(district, "DD_FOOD")])
        if mys:
            acs = by_dist_role[(district, "AC")]
            add("ac_hunsur", "Assistant Commissioner, Hunsur Sub-division", "AC Hunsur", "REV", "L2", "AC", "", "", dc, district,
                Counter({s: n for s, n in acs.items() if "hunsur" in s.lower()}))
            add("ac_mysuru", "Assistant Commissioner, Mysuru Sub-division", "AC Mysuru", "REV", "L2", "AC", "", "", dc, district,
                Counter({s: n for s, n in acs.items() if "mysuru" in s.lower()}))
        else:
            add(f"ac_{ds}", f"Assistant Commissioner, {district}", f"AC {district}", "REV", "L2", "AC", "", "", dc, district, by_dist_role[(district, "AC")])
        for t in sorted(taluks_of[district]):
            ts = slug(t)
            ac = (f"ac_{slug(SUBDIVISION.get(t, 'Mysuru'))}" if mys else f"ac_{ds}")
            eo = f"eo_{ts}"
            add(eo, f"Executive Officer, Taluk Panchayat {t}", f"EO TP {t}", "RDPR", "L2", "EO_TP", t, "", ceo, district, by_role[(district, t, "EO_TP")])
            ups = {"ac": ac, "ddlr": ddlr, "dc": dc, "ddf": ddf, "eo": eo}
            for role, pre, dept, long, short, up in L1_ROLES:
                add(f"{pre}_{ts}", long.format(t=t), short.format(t=t), dept, "L1", role, t, "", ups[up], district, by_role[(district, t, role)])
            cands = {s: g for s, g in pdo_place.items() if f"- {t.upper()} -" in s.upper()}
            for gp in sorted(gps.get((district, t), [])):
                strings = Counter(by_pdo.get((district, t, gp), {}))
                if not strings and cands:
                    best = difflib.get_close_matches(gp.upper(), [g.upper() for g in cands.values()], n=1, cutoff=0.72)
                    s = next((s for s, g in cands.items() if best and g.upper() == best[0]), "")
                    if s:
                        strings = Counter({s: seen[s]})
                add(f"pdo_{ts}_{slug(gp)}", f"PDO, {gp} Gram Panchayat", f"PDO {gp}", "RDPR", "L1", "PDO", t, gp, eo, district, strings)
    db.many("INSERT INTO officers(id,name,short,dept_code,level,role,taluk,gp,up_id,data_name,seen_in_data,n_real,district) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", offs)

    # ---------- all 9,999 records (masked) ----------
    recs = []
    for r in df.itertuples(index=False):
        sid = svc_id.get((r.dept_code, r.line_en, r.svc_en))
        recs.append((r[0], mask(r[1])[0], r.dept_en, r.dept_code, r.line_en, r.svc_en, r.gr_en, r[8], r.District, r.Taluk,
                     r.gp, r.village, r[12], r[13], r[14], r.officer, r.role, r[16], sid))
    db.many("INSERT INTO ipgrs_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", recs)

    # ---------- Sakala services handled in the pilot (timelines illustrative until confirmed) ----------
    sk = [("caste_income", "Caste & Income Certificate", "ಜಾತಿ ಮತ್ತು ಆದಾಯ ಪ್ರಮಾಣ ಪತ್ರ", "REV", 21, "TAHSILDAR", "AC", "DC",
           ["Applicant's name", "Village", "Photo of ration card / Aadhaar"]),
          ("pension", "Old-age pension (Sandhya Suraksha)", "ಸಂಧ್ಯಾ ಸುರಕ್ಷಾ ಪಿಂಚಣಿ", "REV", 45, "TAHSILDAR", "AC", "DC",
           ["Applicant's name", "Village", "Photo of age proof / Aadhaar"]),
          ("ration_new", "New Ration Card", "ಹೊಸ ಪಡಿತರ ಚೀಟಿ", "FOOD", 30, "FI", "DD_FOOD", "DC",
           ["Head of family's name", "Village", "Photo of Aadhaar of the head of family"])]
    db.many("INSERT INTO sakala_services VALUES (?,?,?,?,?,?,?,?,?)", [(*s[:8], json.dumps(s[8])) for s in sk])

    db.kv_set("now", DEMO_START.isoformat())
    db.kv_set("seq", 504200)
    from . import local_ai
    print("training local models on the real records…", local_ai.train(evaluate=True))
    seed_cases(df, name_map, svc_id)
    db.kv_set("routing_eval", routing_eval())
    db.kv_set("routing_eval_pilot", routing_eval(PILOT_DISTRICT))
    from . import analytics
    print("Sakala 2025 performance rows loaded:", analytics.ingest_perf())
    print(f"departments={len(depts)} lines={len(line_id)} services={len(svc_id)} officers={len(offs)} "
          f"gazetteer={len(gaz)} records={len(recs)} cases={db.q1('SELECT COUNT(*) n FROM cases')['n']}")


CASE_COLS = ["id", "kind", "text", "masked", "summary", "src", "lang", "district", "taluk", "gp", "village", "dept_code", "line",
             "service", "service_id", "grievance", "conf", "why", "engine", "vulnerable", "vuln_reason", "owner", "level",
             "level_since", "created", "status", "real", "synthetic", "route_basis", "sakala", "atr", "atr_score", "atr_reason",
             "session", "linked_to", "audit"]


def seed_cases(df, name_map, svc_id):
    """Live caseload = every REAL pilot-department grievance in the sample week, statewide, with its real officer."""
    pil = df[df.dept_code != ""]
    officers = {o["id"]: o for o in db.q("SELECT * FROM officers")}
    events, rows = [], []
    skipped = Counter()
    for r in pil.itertuples(index=False):
        owner = name_map.get(r.officer)
        if not owner or owner not in officers:
            skipped[r.role] += 1
            continue                              # handled by an office outside the officer master (e.g. the KRIDL state desk)
        created = pd.Timestamp(r[12]).to_pydatetime()
        st = {"InProcess": "Pending", "Registered & Sent for Scrutiny": "Scrutiny"}.get(r[13], "Resolved")
        masked = mask(r[1])[0]
        rows.append({"id": f"GR-{r[0]}", "kind": "GRIEVANCE", "text": r[1], "masked": masked, "summary": "", "src": src_key(r[16]),
                     "lang": "kn" if re.search("[ಀ-೿]", r[1]) else "en", "district": r.District, "taluk": r.Taluk, "gp": r.gp,
                     "village": r.village, "dept_code": r.dept_code, "line": r.line_en, "service": r.svc_en,
                     "service_id": svc_id.get((r.dept_code, r.line_en, r.svc_en)), "grievance": r.gr_en, "conf": 1.0,
                     "why": "Category as recorded in iPGRS (real record).", "engine": "iPGRS", "vulnerable": 0, "vuln_reason": "",
                     "owner": owner, "level": officers[owner]["level"], "level_since": max(created, DEMO_START).isoformat(),
                     "created": created.isoformat(), "status": st, "real": 1, "synthetic": 0,
                     "route_basis": "iPGRS assignment (real) · escalation clock starts at pilot go-live"})
        events.append((f"GR-{r[0]}", created.isoformat(), "iPGRS", f"Assigned to {officers[owner]['short']}", "#26732f",
                       f"Real record · {r[16]} · {r.svc_en}"))
        if st == "Resolved":
            events.append((f"GR-{r[0]}", (created + timedelta(days=1)).isoformat(), officers[owner]["short"], "Closed by officer (iPGRS)", "#1f9d57", "Status in the sample week"))
    db.many(f"INSERT INTO cases({','.join(CASE_COLS)}) VALUES ({','.join('?' * len(CASE_COLS))})",
            [[row.get(k) for k in CASE_COLS] for row in rows])
    db.many("INSERT INTO case_events(case_id,t,who,what,color,note) VALUES (?,?,?,?,?,?)", events)
    print(f"real cases loaded: {len(rows)} · not mappable to a field officer: {dict(skipped)}")
    seed_synthetic()


def routing_eval(district=None):
    """Officer-level agreement: give the router the real service + location, does it pick the officer iPGRS used?"""
    from .routing import route
    ok = n = 0
    misses = Counter()
    where = "AND district=?" if district else ""
    args = (district,) if district else ()
    for c in db.q(f"SELECT service_id, taluk, gp, owner FROM cases WHERE real=1 AND service_id IS NOT NULL {where} "
                  "AND id IN (SELECT case_id FROM case_events WHERE who='iPGRS')", args):
        r = route(c["service_id"], c["taluk"], c["gp"])
        if not r or not r.get("officer"):
            continue
        n += 1
        if r["officer"] == c["owner"]:
            ok += 1
        else:
            misses[(r["officer"], c["owner"])] += 1
    return {"n": n, "agree": ok, "rate": round(ok / max(1, n), 3), "top_misses": [f"{a}->{b}:{k}" for (a, b), k in misses.most_common(6)],
            "scope": district or "Karnataka"}


def src_key(s):
    return {"Praja Seva Abhiyana": "camp", "Citizen Service Centre": "csc", "iPGRS website": "web", "Mobile App": "app",
            "iPGRS-Call Center": "call", "RDPR-Call Center": "rdpr", "Department Officers": "dept", "ZP-CEO": "zp"}.get(s, "web")


DEMO_GRIEVANCES = [  # SYNTHETIC grievances filed through Sakala AI before go-live day, so reminders / escalation show immediately
    ("Pension not received for 4 months, I am 74 years old", "Hunsur", "Halebeedu", 6, "call"),
    ("ನಮ್ಮ ಗ್ರಾಮದ ಚರಂಡಿ ಸ್ವಚ್ಛಗೊಳಿಸಿಲ್ಲ, ಸೊಳ್ಳೆ ಕಾಟ ಹೆಚ್ಚಾಗಿದೆ", "Piriyapatna", "Attigodu", 12, "camp"),
    ("Street light pole fallen near the temple, whole street dark", "Piriyapatna", "Chapparadahalli", 8, "whatsapp"),
    ("Borewell pipeline broken, no drinking water for 3 days", "Piriyapatna", "Komalapura", 5, "rdpr"),
    ("Ration shop dealer is not giving the full rice quantity", "Piriyapatna", "Attigodu", 7, "csc"),
    ("House not sanctioned under Basava Vasathi though selected in Grama Sabha", "Piriyapatna", "Komalapura", 3, "camp"),
    ("Village internal road full of potholes, children and elders are falling", "Piriyapatna", "Bhuvanahalli", 10, "camp"),
    ("ಪೋಡಿ ಮಾಡಲು ಅರ್ಜಿ ಸಲ್ಲಿಸಿ ಎರಡು ತಿಂಗಳಾಗಿದೆ, ಸರ್ವೆ ಆಗಿಲ್ಲ", "Piriyapatna", "Haraduru", 6, "csc"),
    ("Fair price shop closed most days of the week, ration not given", "Mysuru", "Jayapura", 8, "web"),
    ("ನಮ್ಮ ಜಮೀನಿನ ಪಹಣಿಯಲ್ಲಿ ಹೆಸರು ತಪ್ಪಾಗಿದೆ, ತಿದ್ದುಪಡಿ ಮಾಡಿ", "Hunsur", "Govindanahalli", 4, "app"),
]


def seed_synthetic():
    """SYNTHETIC demo data (flagged in the UI): Sakala applications + grievances with ages, then the escalation rules."""
    from .sla import create_application, tick
    from . import local_ai, pipeline
    local_ai.load() or local_ai.train(evaluate=False)
    for text, tk, gp, age, src in DEMO_GRIEVANCES:
        masked, _ = mask(text)
        u = local_ai.understand(masked)
        if u["intent"] != "GRIEVANCE":
            print("skipped demo grievance:", text, u["intent"])
            continue
        res = pipeline.create_grievance(text, masked, u, src, tk, gp, gp)
        t = (DEMO_START - timedelta(days=age)).isoformat()
        db.run("UPDATE cases SET created=?, level_since=?, synthetic=1 WHERE id=?", (t, t, res["id"]))
        db.run("UPDATE case_events SET t=? WHERE case_id=?", (t, res["id"]))
    create_application("caste_income", "Lakshmi K", "Komalapura", "Piriyapatna", "csc", DEMO_START - timedelta(days=26),
                       "I need a caste and income certificate for my daughter's scholarship.", case_id="SK-RD855S260004811")
    create_application("ration_new", "Manjunatha S", "Halebeedu", "Hunsur", "web", DEMO_START - timedelta(days=12),
                       "Applied for new ration card, documents complete.", case_id="SK-FD201S260002219")
    tick(0)
    db.run("DELETE FROM notifications")


if __name__ == "__main__":
    build()
