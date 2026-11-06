"""Local AI engine (no internet needed): classifiers trained on the 9,999 real iPGRS grievances.

* department model  – all 38 departments  → spots requests outside the 3 pilot departments
* service model     – 124 pilot services   → Department › Line department › Service
* nearest neighbours – the most similar real grievances, shown as evidence
* keyword rules     – high-precision overrides and the Sakala-application / wrong-door checks
Character n-grams work directly on Kannada script, so no translation step is needed.
"""
import re
import threading
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.model_selection import train_test_split

import joblib

from . import db
from .config import DATA

MODEL_PATH = DATA / "local_models.joblib"

_M = {}
_lock = threading.Lock()


def _clf():
    return SGDClassifier(loss="modified_huber", alpha=2e-5, max_iter=10, tol=None, random_state=7)


def _vec():
    return TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2, sublinear_tf=True, max_features=60000)


def train(evaluate=True):
    recs = db.q("SELECT gid, text_masked, dept_code, dept, service_id FROM ipgrs_records WHERE length(text_masked) > 3")
    X = [r["text_masked"] for r in recs]
    yd = [r["dept_code"] or "OTHER:" + r["dept"] for r in recs]
    t0 = time.time()
    report = {}
    if evaluate:
        Xtr, Xte, ytr, yte = train_test_split(X, yd, test_size=0.2, random_state=7)
        v = _vec().fit(Xtr)
        m = _clf().fit(v.transform(Xtr), ytr)
        report["dept_acc"] = round(float((m.predict(v.transform(Xte)) == np.array(yte)).mean()), 3)
        p = [(x, r["service_id"]) for x, r in zip(X, recs) if r["service_id"]]
        Ptr, Pte = train_test_split(p, test_size=0.2, random_state=7)
        v2 = _vec().fit([a for a, _ in Ptr])
        m2 = _clf().fit(v2.transform([a for a, _ in Ptr]), [b for _, b in Ptr])
        pred = m2.predict(v2.transform([a for a, _ in Pte]))
        report["service_acc"] = round(float((pred == np.array([b for _, b in Pte])).mean()), 3)
        top3 = np.argsort(-m2.predict_proba(v2.transform([a for a, _ in Pte])), axis=1)[:, :3]
        report["service_top3"] = round(float(np.mean([b in m2.classes_[row] for row, (_, b) in zip(top3, Pte)])), 3)
        report["n_test_dept"], report["n_test_service"] = len(Xte), len(Pte)
    vd = _vec().fit(X)
    md = _clf().fit(vd.transform(X), yd)
    pil = [(x, r) for x, r in zip(X, recs) if r["service_id"]]
    vs = _vec().fit([x for x, _ in pil])
    Ms = vs.transform([x for x, _ in pil])
    ms = _clf().fit(Ms, [r["service_id"] for _, r in pil])
    with _lock:
        _M.update(vd=vd, md=md, vs=vs, ms=ms, Ms=Ms, pil=pil)
    joblib.dump(dict(_M), MODEL_PATH, compress=3)
    report["train_seconds"] = round(time.time() - t0, 1)
    if evaluate:
        db.kv_set("model_eval", report)
    return report


def load():
    if MODEL_PATH.exists():
        _M.update(joblib.load(MODEL_PATH))
        return True
    return False


def ready():
    return "ms" in _M


def predict(text):
    """Return department guess, top service candidates and similar real cases."""
    vd, md, vs, ms = _M["vd"], _M["md"], _M["vs"], _M["ms"]
    pd_ = md.predict_proba(vd.transform([text]))[0]
    order = np.argsort(-pd_)
    depts = [(md.classes_[i], float(pd_[i])) for i in order[:3]]
    xs = vs.transform([text])
    ps = ms.predict_proba(xs)[0]
    so = np.argsort(-ps)[:5]
    services = [(int(ms.classes_[i]), float(ps[i])) for i in so]
    sims = (_M["Ms"] @ xs.T).toarray().ravel()
    nn = np.argsort(-sims)[:5]
    similar = [{"gid": _M["pil"][i][1]["gid"], "text": _M["pil"][i][0][:160], "service_id": _M["pil"][i][1]["service_id"],
                "score": round(float(sims[i]), 2)} for i in nn if sims[i] > 0.05]
    return {"depts": depts, "services": services, "similar": similar}


def alternatives(text, k=3):
    """Top-k service names for the scrutiny desk."""
    names = {s["id"]: s["name"] for s in db.q("SELECT id, name FROM services")}
    return [names.get(sid, "") for sid, _ in predict(text)["services"][:k] if names.get(sid)]


# ---------------- high-precision keyword rules ----------------
def _has(t, *words):
    for w in words:
        if re.fullmatch(r"[a-z ]+", w):
            if re.search(r"(^|[^a-z])" + w + r"([^a-z]|$)", t):
                return True
        elif w in t:
            return True
    return False


RULES = [  # (keywords, service_id, grievance hint)
    (("ಪೌತಿ", "pouthi", "mutation", "ಮ್ಯುಟೇಷನ್"), 108, None),
    (("khata", "khatha", "ಖಾತಾ", "ಖಾತೆ"), 106, None),
    (("podi", "ಪೋಡಿ", "survey", "ಸರ್ವೆ ಮಾಡ", "sketch", "ನಕ್ಷೆ"), 119, None),
    (("rtc", "pahani", "ಪಹಣಿ", "ಆರ್‌ಟಿಸಿ"), 109, None),
    (("sandhya suraksha", "ಸಂಧ್ಯಾ ಸುರಕ್ಷಾ", "old age pension", "ವೃದ್ಧಾಪ್ಯ ವೇತನ", "pension", "ಪಿಂಚಣಿ", "ಮಾಸಾಶನ"), 57, None),
    (("ration card", "ಪಡಿತರ ಚೀಟಿ", "ರೇಷನ್ ಕಾರ್ಡ್"), 6, None),
    (("ration", "ಪಡಿತರ", "ನ್ಯಾಯಬೆಲೆ", "fair price", "rice", "ಅಕ್ಕಿ"), 6, "Denial"),
    (("drinking water", "ಕುಡಿಯುವ ನೀರು", "borewell", "ಬೋರ್‌ವೆಲ್", "no water", "ನೀರು ಬರುತ್ತಿಲ್ಲ", "water supply"), 40, None),
    (("street light", "streetlight", "ಬೀದಿ ದೀಪ", "light"), 28, None),
    (("drain", "ಚರಂಡಿ", "culvert"), 15, None),
    (("road", "ರಸ್ತೆ", "pothole"), 17, None),
    (("house", "housing", "ಮನೆ", "ವಸತಿ", "awas", "ashraya"), 25, None),
    (("toilet", "garbage", "ಕಸ", "sanitation", "ಶೌಚಾಲಯ"), 42, None),
    (("e-khata", "e khata", "form 9", "form 11", "ನಮೂನೆ 9", "ಇ-ಖಾತಾ"), 24, None),
    (("nrega", "job card", "ಉದ್ಯೋಗ ಖಾತ್ರಿ"), 39, None),
    (("marriage registration", "ವಿವಾಹ ನೋಂದಣಿ"), 53, None),
    (("temple", "ದೇವಸ್ಥಾನ", "ದೇವಾಲಯ"), 71, None),
    (("flood", "crop loss", "ಬೆಳೆ ಹಾನಿ", "ಪರಿಹಾರ", "compensation for rain"), 61, None),
]
APPLY = [(("caste", "income", "ಜಾತಿ", "ಆದಾಯ"), "caste_income"), (("new ration card", "ಹೊಸ ಪಡಿತರ"), "ration_new")]
APPLY_VERBS = ("need", "want", "apply", "require", "ಬೇಕು", "ಅರ್ಜಿ ಸಲ್ಲಿಸ", "ಕೊಡಿ", "get a", "issue me")
COMPLAINT_WORDS = ("not received", "delay", "ವಿಳಂಬ", "ಸಿಕ್ಕಿಲ್ಲ", "ಬಂದಿಲ್ಲ", "pending", "still", "months", "ತಿಂಗಳಾದರೂ", "rejected")
VULNERABLE = ("widow", "ವಿಧವೆ", "old", "ವೃದ್ಧ", "elderly", "senior", "disabled", "ಅಂಗವಿಕಲ", "handicap", "pension", "ಪಿಂಚಣಿ",
              "ration", "ಪಡಿತರ", "years old", "ವರ್ಷ", "sick", "ಅನಾರೋಗ್ಯ", "pregnant", "ಗರ್ಭಿಣಿ")
WRONG_DOOR = {"rti": "This is an RTI request, which iPGRS does not treat as a grievance. File it on RTI Online.",
              "information act": "This is an RTI request, which iPGRS does not treat as a grievance. File it on RTI Online.",
              "transfer of my posting": "Government employees' service matters are not handled as public grievances."}
OUT_OF_SCOPE = [(("power cut", "power", "electric", "electricity", "ವಿದ್ಯುತ್", "transformer", "ಕರೆಂಟ್"), "Energy Department", "CESC Mysuru (Chamundeshwari Electricity Supply Corporation)"),
                (("bus", "ksrtc", "ಬಸ್"), "Transport Department", "KSRTC"),
                (("hospital", "doctor", "ಆಸ್ಪತ್ರೆ"), "Health & Family Welfare Department", "District Health Office"),
                (("school", "teacher", "ಶಾಲೆ"), "School Education Department", "Block Education Office"),
                (("police", "ಪೊಲೀಸ್", "fir"), "Home Department", "Police (outside iPGRS · call 112)")]


def understand(text):
    """Local understanding. Returns the same structure as the Claude path."""
    t = (text or "").lower()
    for k, msg in WRONG_DOOR.items():
        if _has(t, k):
            return {"intent": "WRONG_DOOR", "reason": msg, "engine": "local", "conf": 0.9}
    for words, key in APPLY:
        if _has(t, *words) and _has(t, *APPLY_VERBS) and not _has(t, *COMPLAINT_WORDS):
            return {"intent": "SERVICE_REQUEST", "sakala_key": key, "engine": "local", "conf": 0.9,
                    "why": "The citizen is asking for a new certificate / card, which is a Sakala-notified service."}
    rule = next(((sid, hint, words) for words, sid, hint in RULES if _has(t, *words)), None)
    for words, dept, line in OUT_OF_SCOPE:
        # a pilot-service keyword in the same text wins ("the street light near the bus stand", "school children find it dark"):
        # letters mention many things; only a text with no pilot service in it is sent to another department
        if _has(t, *words) and not rule:
            return {"intent": "OUT_OF_SCOPE", "dept": dept, "line": line, "engine": "local", "conf": 0.88,
                    "why": f"Mentions {words[0]}; this belongs to the {dept}, outside the 3 pilot departments."}
    p = predict(text)
    top_dept, dprob = p["depts"][0]
    if top_dept.startswith("OTHER:") and dprob > 0.55 and not rule:
        return {"intent": "OUT_OF_SCOPE", "dept": top_dept[6:], "line": "", "engine": "local", "conf": round(dprob, 2),
                "why": f"Similar real grievances belong to the {top_dept[6:]}, outside the 3 pilot departments.", "similar": p["similar"]}
    sid, prob = p["services"][0]
    why = ""
    if rule:
        if rule[0] != sid:
            prob = max(0.82, dict(p["services"]).get(rule[0], 0) + 0.5)
        else:
            prob = max(prob, 0.9)
        sid = rule[0]
        why = f"Mentions “{next(w for w in rule[2] if _has(t, w))}”"
    else:
        why = "Closest match among real grievances from the sample week"
    nsim0 = sum(1 for s in p["similar"] if s["service_id"] == sid)
    if not rule and (prob < 0.55 or nsim0 < 2):
        return {"intent": "UNCLEAR", "engine": "local", "conf": round(prob, 2), "similar": p["similar"],
                "reason": "The text does not clearly match any service. A person at the scrutiny desk will check it."}
    svc = db.q1("SELECT s.*, l.name line FROM services s JOIN line_departments l ON l.id=s.line_id WHERE s.id=?", (sid,))
    grs = db.q("SELECT name FROM grievance_types WHERE service_id=? ORDER BY n_real DESC", (sid,))
    gr = grs[0]["name"] if grs else "General"
    if rule and rule[1]:
        gr = next((g["name"] for g in grs if rule[1].lower() in g["name"].lower()), gr)
    vul = _has(t, *VULNERABLE)
    nsim = sum(1 for s in p["similar"] if s["service_id"] == sid)
    return {"intent": "GRIEVANCE", "engine": "local", "dept_code": svc["dept_code"], "line": svc["line"], "service": svc["name"],
            "service_id": sid, "grievance": gr, "conf": round(min(0.97, prob), 2),
            "why": f"{why}; {nsim} of the 5 most similar real grievances were filed under '{svc['name']}'.",
            "vulnerable": vul, "vuln_reason": "Elderly / widow / pension / ration-dependent citizen" if vul else "",
            "similar": p["similar"]}


# ---------------- Kannada → Latin (for matching village names written in Kannada) ----------------
_V = {"ಅ": "a", "ಆ": "aa", "ಇ": "i", "ಈ": "ee", "ಉ": "u", "ಊ": "oo", "ಎ": "e", "ಏ": "e", "ಐ": "ai", "ಒ": "o", "ಓ": "o", "ಔ": "au"}
_C = {"ಕ": "k", "ಖ": "kh", "ಗ": "g", "ಘ": "gh", "ಙ": "n", "ಚ": "ch", "ಛ": "chh", "ಜ": "j", "ಝ": "jh", "ಞ": "n", "ಟ": "t", "ಠ": "th",
      "ಡ": "d", "ಢ": "dh", "ಣ": "n", "ತ": "t", "ಥ": "th", "ದ": "d", "ಧ": "dh", "ನ": "n", "ಪ": "p", "ಫ": "ph", "ಬ": "b", "ಭ": "bh",
      "ಮ": "m", "ಯ": "y", "ರ": "r", "ಲ": "l", "ವ": "v", "ಶ": "sh", "ಷ": "sh", "ಸ": "s", "ಹ": "h", "ಳ": "l", "ೞ": "l", "ಱ": "r"}
_M_ = {"ಾ": "aa", "ಿ": "i", "ೀ": "ee", "ು": "u", "ೂ": "oo", "ೃ": "ru", "ೆ": "e", "ೇ": "e", "ೈ": "ai", "ೊ": "o", "ೋ": "o", "ೌ": "au"}


def kn_to_latin(s):
    out, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch in _C:
            nxt = s[i + 1] if i + 1 < len(s) else ""
            if nxt == "್":
                out.append(_C[ch]); i += 2; continue
            if nxt in _M_:
                out.append(_C[ch] + _M_[nxt]); i += 2; continue
            out.append(_C[ch] + "a")
        elif ch in _V:
            out.append(_V[ch])
        elif ch in ("ಂ",):
            out.append("m")
        elif ch == "ಃ":
            out.append("h")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


# Everyday Kannada nouns that are also village names somewhere in the statewide gazetteer (ಬೀದಿ "street" = Beedi,
# Khanapur). On their own, or with a short case ending (ಬೀದಿಯಲ್ಲಿ), they are never taken as a place.
KN_COMMON = {
    "ಬೀದಿ", "ದೀಪ", "ದೀಪಗಳು", "ನೀರು", "ನೀರಿನ", "ರಸ್ತೆ", "ಊರು", "ಊರಲ್ಲಿ", "ನಮ್ಮೂರು", "ನಮ್ಮೂರಲ್ಲಿ", "ಮನೆ", "ಕೆರೆ", "ಹಳ್ಳಿ",
    "ಗ್ರಾಮ", "ಚರಂಡಿ", "ಕಸ", "ಶಾಲೆ", "ಆಸ್ಪತ್ರೆ", "ಅಂಗಡಿ", "ಪಡಿತರ", "ಚೀಟಿ", "ಕಾರ್ಡ್", "ವಿದ್ಯುತ್", "ಕರೆಂಟ್", "ಪಿಂಚಣಿ",
    "ಜಮೀನು", "ಹೊಲ", "ಬೆಳಕು", "ಕಂಬ", "ಬಸ್", "ನಿಲ್ದಾಣ", "ದೇವಸ್ಥಾನ", "ಮಾರುಕಟ್ಟೆ", "ಕಚೇರಿ", "ಸರ್ಕಾರ", "ಅಧಿಕಾರಿ", "ಸಮಸ್ಯೆ",
    "ಕೆಲಸ", "ಕೊಳವೆ", "ಪೈಪ್", "ನಲ್ಲಿ", "ಟ್ಯಾಂಕ್", "ಮಳೆ", "ಹಾಲು", "ಆಹಾರ", "ಅಕ್ಕಿ", "ಮರ", "ಗುಂಡಿ", "ಸೇತುವೆ", "ಬಾವಿ",
}


def _kn_common(w):
    return w in KN_COMMON or any(w.startswith(c) and 0 < len(w) - len(c) <= 4 for c in KN_COMMON if len(c) >= 3)


def place_candidates(text):
    """Words that might be village names: English words plus transliterated Kannada words."""
    words = re.findall(r"[A-Za-z][A-Za-z.]{3,}", text or "")
    for w in re.findall(r"[ಀ-೿]{3,}", text or ""):
        if _kn_common(w):
            continue
        stem = re.sub(r"(ಯಲ್ಲಿ|ದಲ್ಲಿ|ನಲ್ಲಿ|ರಲ್ಲಿ|ಲ್ಲಿ|ಯಿಂದ|ದಿಂದ|ಕ್ಕೆ|ಗೆ)$", "", w)    # "ಬೈಲಕುಪ್ಪೆಯಲ್ಲಿ" (in Bylakuppe) -> ಬೈಲಕುಪ್ಪೆ
        if stem != w and len(stem) >= 3 and not _kn_common(stem):
            words.append(kn_to_latin(stem))
        lat = kn_to_latin(w)
        words.append(lat)
        words.append(re.sub(r"(du|dalli|nalli|ge|ra|da|li)$", "", lat))       # drop common case endings
    return words + [a + b for a, b in zip(words, words[1:])]
