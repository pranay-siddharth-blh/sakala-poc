"""Return with a suggestion (22 Oct 2026, Pranay). An officer returning a case as "not my jurisdiction" may say who should
have it (an officer: "PDO Attigodu", "Tahsildar Hunsur", "the AEE") and/or where it really is (a taluk, Gram Panchayat or
village: "Hunsur", "Attigodu GP"). If either resolves to a real officer in the master, the case goes straight to them, the
clock restarts for them and they are notified; only when nothing usable is given does it go to the scrutiny desk.

Everything is deterministic and read from the officer master and the gazetteer; nothing is invented. The grievance ladder and
the Sakala ladder never mix: a Sakala application is never transferred this way."""
from __future__ import annotations

import difflib
import re

from . import db
from .routing import ROLE_LABEL, officer_for_role, resolve_place, route

# spoken / typed role words -> officer master roles (longest first so "ae rdws" wins over "ae")
ROLE_WORDS = [
    (r"\b(zp ceo|zilla panchayat ceo|ceo zp|ceo,? zilla panchayat|ceo)\b", "ZP_CEO"),
    (r"\b(deputy commissioner|dc)\b", "DC"),
    (r"\b(assistant commissioner|ac)\b", "AC"),
    (r"\b(ddlr|deputy director of land records)\b", "DDLR"),
    (r"\b(dd food|deputy director,? food|deputy director of food)\b", "DD_FOOD"),
    (r"\b(food inspector|fi)\b", "FI"),
    (r"\b(adlr|taluk survey|survey officer|surveyor)\b", "ADLR"),
    (r"\b(sub[- ]?registrar)\b", "SUBREG"),
    (r"\b(ae rdws|rdws|ae/je|je|drinking water engineer|ae)\b", "AE_RDWS"),
    (r"\b(aee pred|aee|pred|roads engineer|assistant executive engineer)\b", "AEE_PRED"),
    (r"\b(eo tp|eo|executive officer|taluk panchayat)\b", "EO_TP"),
    (r"\b(pdo|panchayat development officer|gram panchayat officer)\b", "PDO"),
    (r"\b(tahsildar|tahasildar|thasildar|tehsildar)\b|ತಹಶೀಲ್ದಾರ್|ತಹಸೀಲ್ದಾರ್", "TAHSILDAR"),
    (r"ಪಿಡಿಒ|ಪಿ ಡಿ ಓ|ಪಂಚಾಯಿತಿ ಅಭಿವೃದ್ಧಿ ಅಧಿಕಾರಿ", "PDO"),
    (r"ಆಹಾರ ನಿರೀಕ್ಷಕ", "FI"),
    (r"ಜಿಲ್ಲಾಧಿಕಾರಿ", "DC"),
]
DISTRICT_ROLES = {"DC", "AC", "DDLR", "DD_FOOD", "ZP_CEO"}
LABEL = {**ROLE_LABEL, "AC": "Assistant Commissioner", "DC": "Deputy Commissioner", "ZP_CEO": "Zilla Panchayat CEO",
         "DDLR": "DDLR (survey)", "DD_FOOD": "Deputy Director, Food"}
_FILLER = re.compile(r"\b(the|of|to|it|send|sent|give|pass|transfer|forward|should|go|goes|be|with|please|for|in|at|office|officer|"
                     r"concerned|correct|right|taluk|district|gram|panchayat|gp|village|grama|hobli|sir|madam|suggest|suggested|"
                     r"i|think|this|that|is|belongs|matter|case|grievance|complaint|not|my|jurisdiction|a|an|and|or|under)\b")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).strip()


def _taluks() -> dict[str, dict]:
    return {r["taluk"].lower(): {"taluk": r["taluk"], "district": r["district"]}
            for r in db.q("SELECT DISTINCT taluk, district FROM officers WHERE taluk<>''")}


def _districts() -> dict[str, str]:
    return {r["district"].lower(): r["district"] for r in db.q("SELECT DISTINCT district FROM officers WHERE district<>''")}


def find_place(text: str, hint_district: str = "") -> dict | None:
    """A taluk, district, Gram Panchayat or village named in free text -> {taluk, district, gp, village, level}."""
    t = _clean(text)
    tks, dts = _taluks(), _districts()
    if re.search("[ಀ-೿]", text or ""):              # Kannada script: the shared taluk finder (transliteration)
        try:
            from .chat import taluk_in_text
            tk = taluk_in_text(text)
            if tk and tk.lower() in tks:
                return {**tks[tk.lower()], "gp": "", "village": "", "level": "taluk"}
        except Exception:  # noqa: BLE001
            pass
    if not t:
        return None
    words = t.split()
    grams = [" ".join(words[i:i + n]) for n in (3, 2, 1) for i in range(len(words) - n + 1)]
    for g in grams:                                              # a taluk named outright beats a look-alike village
        if g in tks:
            return {**tks[g], "gp": "", "village": "", "level": "taluk"}
    try:
        from .chat import taluk_in_text                          # Kannada script / spacing variants
        tk = taluk_in_text(text)
        if tk and tk.lower() in tks:
            return {**tks[tk.lower()], "gp": "", "village": "", "level": "taluk"}
    except Exception:  # noqa: BLE001
        pass
    for g in grams:
        if len(g) >= 5:
            m = difflib.get_close_matches(g, list(tks), n=1, cutoff=0.88)
            if m:
                return {**tks[m[0]], "gp": "", "village": "", "level": "taluk"}
    cand = [g for g in grams if len(g) >= 4 and not _FILLER.fullmatch(g)]
    hit = resolve_place(*cand, district_hint=hint_district) if cand else None
    if hit:
        return {"taluk": hit["taluk"], "district": hit.get("district") or "", "gp": hit["gp"], "village": hit["village"], "level": "gp"}
    for g in grams:
        if g in dts:
            return {"taluk": "", "district": dts[g], "gp": "", "village": "", "level": "district"}
    return None


def _role_in(text: str) -> str:
    low = (text or "").lower()
    for rx, role in ROLE_WORDS:
        if re.search(rx, low):
            return role
    return ""


def _officer_at(role: str, place: dict | None, case: dict) -> dict | None:
    """The officer with this role at that place (or at the case's own place when no place is given)."""
    p = place or {"taluk": case.get("taluk") or "", "district": case.get("district") or "", "gp": case.get("gp") or ""}
    if role in DISTRICT_ROLES:
        if p.get("taluk"):                                       # the senior of that taluk's own ladder (AC sub-division, DC, ZP CEO)
            seen, q = set(), [r["id"] for r in db.q("SELECT id FROM officers WHERE taluk=? AND level='L1'", (p["taluk"],))]
            while q:
                oid = q.pop(0)
                if oid in seen:
                    continue
                seen.add(oid)
                o = db.q1("SELECT * FROM officers WHERE id=?", (oid,))
                if not o:
                    continue
                if o["role"] == role:
                    return dict(o)
                if o["up_id"]:
                    q.append(o["up_id"])
        d = p.get("district") or (db.q1("SELECT district FROM officers WHERE taluk=? LIMIT 1", (p.get("taluk") or "",)) or {}).get("district", "")
        if not d:
            return None
        r = db.q1("SELECT * FROM officers WHERE role=? AND district=? ORDER BY id LIMIT 1", (role, d))
        return dict(r) if r else None
    if not p.get("taluk"):
        return None
    oid = officer_for_role(role, p["taluk"], p.get("gp") or "")
    r = db.q1("SELECT * FROM officers WHERE id=? AND role=?", (oid, role)) or \
        db.q1("SELECT * FROM officers WHERE role=? AND taluk=? ORDER BY id LIMIT 1", (role, p["taluk"]))
    if role == "PDO" and not p.get("gp"):
        return None                                              # each GP has its own PDO: a PDO needs the GP
    return dict(r) if r else None


def _officer_by_name(text: str, place: dict | None) -> dict | None:
    """'PDO Attigodu', 'Tahsildar Grade-1, Hunsur', an officer id: fuzzy over the master's short names."""
    raw = (text or "").strip()
    if not raw:
        return None
    r = db.q1("SELECT * FROM officers WHERE id=?", (raw,))
    if r:
        return dict(r)
    t = _clean(raw)
    rows = db.q("SELECT * FROM officers" + (" WHERE district=?" if place and place.get("district") else ""),
                ((place["district"],) if place and place.get("district") else ()))
    best, score = None, 0.0
    for o in rows:
        for cand in (_clean(o["short"]), _clean(o["name"])):
            s = 1.0 if t == cand else difflib.SequenceMatcher(None, t, cand).ratio()
            if s > score:
                best, score = o, s
    return dict(best) if best and score >= 0.86 else None


def resolve(case: dict, to: str = "", place: str = "", me_id: str = "") -> dict:
    """-> {"officer": row | None, "place": {...} | None, "how": text, "asked": text}. `officer` None = scrutiny desk."""
    to, place = (to or "").strip(), (place or "").strip()
    asked = " · ".join(x for x in (to, place) if x)
    out = {"officer": None, "place": None, "how": "", "asked": asked}
    if not asked:
        return out
    hint_d = case.get("district") or ""
    pl = find_place(place, hint_d) if place else None
    if not pl and to:
        pl = find_place(_FILLER.sub(" ", _clean(re.sub("|".join(rx for rx, _ in ROLE_WORDS), " ", to.lower()))), hint_d)
    role = _role_in(to) or _role_in(place)
    target, how = None, ""
    if to:
        target = _officer_by_name(to, pl)
        how = "the officer named" if target else ""
    if not target and role:
        target = _officer_at(role, pl, case)
        if not target and role == "PDO" and pl and pl.get("taluk") and not pl.get("gp"):
            target = _officer_at("EO_TP", pl, case)            # no GP named: the Taluk Panchayat EO of that taluk takes it
            how = "the Taluk Panchayat EO (no Gram Panchayat named)" if target else ""
        else:
            how = how or (f"the {LABEL.get(role, role)} " + ("of the place given" if pl else "of the case's own place"))
    if not target and pl and pl.get("taluk"):
        # only a place: the same rule that routes every new grievance (service -> role -> officer at that place)
        if case.get("service_id"):
            r = route(case["service_id"], pl["taluk"], pl.get("gp") or "")
            oid = (r or {}).get("officer") or ((r or {}).get("need_gp") and f"eo_{re.sub(r'[^a-z0-9]+', '_', pl['taluk'].lower()).strip('_')}")
            row = db.q1("SELECT * FROM officers WHERE id=?", (oid,)) if oid else None
            if row:
                target, how = dict(row), ("the routing rule for this service at the place given" +
                                          (" (no Gram Panchayat named, so the Taluk Panchayat EO)" if (r or {}).get("need_gp") else ""))
        if not target and me_id:
            me = db.q1("SELECT role FROM officers WHERE id=?", (me_id,))
            if me:
                target = _officer_at(me["role"], pl, case)
                how = "the same office at the place given" if target else ""
    if target and target["id"] == me_id:
        target, how = None, "the suggestion pointed back to the returning officer"
    out.update(officer=target, place=pl, how=how)
    return out
