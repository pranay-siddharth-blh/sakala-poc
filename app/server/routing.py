"""Stage 6 · Exact-officer routing.

Service → officer ROLE comes from the learned rules (which role actually handled that service in the real data).
ROLE + taluk (+ Gram Panchayat for PDOs) → one named officer from the officer master.
"""
import difflib
import re

from . import db
from .ingest import slug

ROLE_PREFIX = {"TAHSILDAR": "tah", "ADLR": "adlr", "FI": "fi", "AEE_PRED": "aee", "AE_RDWS": "rdws", "EO_TP": "eo", "SUBREG": "subreg"}
ROLE_LABEL = {"PDO": "Panchayat Development Officer", "TAHSILDAR": "Tahsildar", "ADLR": "ADLR (survey)", "FI": "Food Inspector",
              "AEE_PRED": "AEE, PRED (roads & works)", "AE_RDWS": "AE/JE, Rural Drinking Water", "EO_TP": "Executive Officer, Taluk Panchayat",
              "SUBREG": "Sub-Registrar"}


def officer_for_role(role, taluk, gp=""):
    ts = slug(taluk)
    if role == "PDO":
        if gp and db.q1("SELECT id FROM officers WHERE id=?", (f"pdo_{ts}_{slug(gp)}",)):
            return f"pdo_{ts}_{slug(gp)}"
        return f"eo_{ts}"
    return f"{ROLE_PREFIX.get(role, 'tah')}_{ts}"


def route(service_id, taluk, gp=""):
    """Return {officer, role, need_gp, fallback, basis, share}."""
    s = db.q1("SELECT * FROM services WHERE id=?", (service_id,))
    if not s:
        return None
    role = s["role"]
    res = {"role": role, "role_label": ROLE_LABEL.get(role, role), "share": s["role_share"], "support": s["role_support"],
           "need_gp": False, "fallback": False}
    weak = s["role_share"] < 0.3
    evidence = (f"In the real iPGRS data '{s['name']}' grievances went to a state-level desk, not a field officer; "
                f"the pilot sends them to the {ROLE_LABEL.get(role, role)} so a named officer owns them." if weak else
                f"In the real iPGRS data, {round(s['role_share'] * 100)}% of '{s['name']}' grievances "
                f"({s['role_support']} cases) were handled by the {ROLE_LABEL.get(role, role)}.")
    if role == "PDO" and not gp:
        res.update(need_gp=True, officer=None, basis="Needs the Gram Panchayat: each GP has its own PDO. " + evidence)
        return res
    oid = officer_for_role(role, taluk, gp)
    res["officer"] = oid
    res["fallback"] = (role == "PDO" and oid.startswith("eo_")) or weak
    where = f"{gp} GP, {taluk} taluk" if gp else f"{taluk} taluk"
    res["basis"] = (f"{ROLE_LABEL.get(role, role)} for {where}. " + evidence +
                    (" No PDO for this GP in the pilot master, so the Taluk Panchayat EO receives it." if role == "PDO" and oid.startswith("eo_") else ""))
    return res


# ---------------- gazetteer ----------------
def _clean(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


_GAZ = {"rows": None}


def resolve_place(*names, taluk_hint="", district_hint=""):
    """Match free-text place names against the statewide village → GP → taluk → district gazetteer learnt from the data.
    Ties and near-ties (within 0.12) go to the hinted taluk / district, then to the pilot district (ASSUMED default region
    of the demo), so a village name that exists in several districts lands where the demo expects it."""
    from .config import PILOT_DISTRICT
    if _GAZ["rows"] is None:
        _GAZ["rows"] = [dict(r, _v=_clean(r["village"]), _g=_clean(r["gp"])) for r in db.q("SELECT * FROM gazetteer")]
    rows = _GAZ["rows"]
    best, best_pref = None, None
    for name in names:
        n = _clean(name)
        if len(n) < 4:
            continue
        for r in rows:
            for field, cand in (("village", r["_v"]), ("gp", r["_g"])):
                if not cand:
                    continue
                if abs(len(cand) - len(n)) > 4:
                    continue
                score = 1.0 if n == cand else difflib.SequenceMatcher(None, n, cand).ratio()
                if score < 0.84:
                    continue
                if field == "gp":
                    score += 0.01
                hit = {"village": r["village"] if field == "village" else r["gp"], "gp": r["gp"], "taluk": r["taluk"],
                       "district": r.get("district") or "", "score": round(min(score, 1), 2)}
                if not best or score > best["score"]:
                    best = hit
                preferred = (taluk_hint and r["taluk"] == taluk_hint) or (district_hint and r.get("district") == district_hint) or \
                            (not taluk_hint and not district_hint and r.get("district") == PILOT_DISTRICT)
                if preferred and (not best_pref or score > best_pref["score"]):
                    best_pref = hit
    # a hinted taluk / district wins a near-tie (0.12); the pilot default wins a wider one (0.2): transliterated Kannada
    # village names (ಬೈಲಕುಪ್ಪೆ → "bailakuppe" vs Bylakuppe) score ~0.84 against the right row and 1.0 against a lookalike elsewhere
    margin = 0.12 if (taluk_hint or district_hint) else 0.2
    if best_pref and best and best_pref["score"] >= best["score"] - margin:
        return best_pref
    return best


def reset_gazetteer_cache():
    _GAZ["rows"] = None


def find_place_in_text(text):
    """Look for any gazetteer village / GP name written in English inside the text."""
    words = re.findall(r"[A-Za-z][A-Za-z.]{3,}", text or "")
    grams = words + [a + b for a, b in zip(words, words[1:])]
    return resolve_place(*grams) if grams else None


def gp_list(taluk):
    return [r["gp"] for r in db.q("SELECT gp, SUM(n_real) n FROM gazetteer WHERE taluk=? GROUP BY gp ORDER BY n DESC", (taluk,))]
