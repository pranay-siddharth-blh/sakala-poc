"""22 Oct 2026: Kannada (and code-mixed Kannada) questions use the SAME router as English: Kannada question words are mapped onto
their English shape (ಎಷ್ಟು -> how many, ಹೇಗಿದೆ -> how is ... doing, N ದಿನ ಉಳಿದಿವೆ -> N days left, escalate ಆಗಿಲ್ಲ -> not escalated ...),
the English router decides, and Kannada place / department names go to the POC as said, where they are normalised (the whole
sentence is searched for a taluk; a district before ಜಿಲ್ಲೆ). The POC drops a Kannada place it cannot resolve instead of guessing."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def patch(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert old in s, f"{rel}: missing\n{old[:140]}"
        s = s.replace(old, new, 1)
    ast.parse(s)
    p.write_text(s, encoding="utf-8")
    print("patched", rel)


p = ROOT / "mitra/server/board.py"
s = p.read_text(encoding="utf-8")
a = s.index("def route_kn(t: str, profile: str, state: dict | None):")
b = s.index("def route(text: str, profile: str, state: dict | None = None):")
NEW = r'''KN2EN = [  # Kannada question words -> the English shape the router knows (longest first)
    (r"ಎಸ್ಕಲೇಟ್ ಆಗಿಲ್ಲ|escalate ಆಗಿಲ್ಲ|escalate ಆಗದ|ಮೇಲಕ್ಕೆ ಹೋಗಿಲ್ಲ|ಮೇಲಕ್ಕೆ ಹೋಗದ", " not escalated "),
    (r"ಎಸ್ಕಲೇಟ್|escalate ಆಗಿ|escalate ಆದ|ಮೇಲಕ್ಕೆ ಹೋದ|ಮೇಲಿನ ಹಂತಕ್ಕೆ ಹೋದ", " escalated "),
    (r"ಇವತ್ತೇ|ಇವತ್ತು|ಇಂದೇ|ಇಂದು", " today "), (r"ನಾಳೆ", " tomorrow "),
    (r"ಹಂತವಾರು|ಹಂತಗಳ ಪ್ರಕಾರ|level ಪ್ರಕಾರ|level wise|levels? ಪ್ರಕಾರ", " level wise "),
    (r"ಮೊದಲ ಹಂತ|ಒಂದನೇ ಹಂತ|ಹಂತ ೧|ಹಂತ 1", " L1 "), (r"ಎರಡನೇ ಹಂತ|ಹಂತ ೨|ಹಂತ 2", " L2 "), (r"ಮೂರನೇ ಹಂತ|ಹಂತ ೩|ಹಂತ 3", " L3 "),
    (r"ದಿನಗಳ? ಉಳಿದಿ\S*|ದಿನ ಬಾಕಿ\S*|ದಿನ ಉಳಿದ\S*|ದಿನ ಇರುವ\S*|days? ಉಳಿದ\S*|days? ಬಾಕಿ\S*|days? left", " days left "),
    (r"deadline ಪ್ರಕಾರ|ಗಡುವಿನ ಪ್ರಕಾರ|timeline|ಟೈಮ್‌?ಲೈನ್", " the 7 day timeline "),
    (r"ಹೇಗೆ perform ಮಾಡ್ತಿದೆ|ಹೇಗೆ perform ಮಾಡ್ತಿದ್ದಾರೆ|ಹೇಗಿದೆ|ಹೇಗಿದ್ದಾರೆ|ಹೇಗೆ ನಡೀತಿದೆ|ಹೇಗೆ ನಡೆಯುತ್ತಿದೆ|ಪರಿಸ್ಥಿತಿ ಏನು|ಸ್ಥಿತಿ ಏನು|ಎಲ್ಲಾ ವಿವರ\S*", " how is it doing "),
    (r"ಎಷ್ಟು", " how many "), (r"ವಿಳಂಬ\S*|ಗಡುವು ಮೀರಿ\S*|overdue ಆಗಿ\S*", " overdue "), (r"ಬಾಕಿ\S*|pending", " pending "),
    (r"ಪರಿಹಾರ ಆಗಿ\S*|ಪರಿಹರಿಸ\S*|ಮುಕ್ತಾಯ\S*", " resolved "), (r"ಒಟ್ಟಾರೆ|ರಾಜ್ಯದಲ್ಲಿ|ರಾಜ್ಯ ಮಟ್ಟದ|ಇಡೀ ರಾಜ್ಯ", " overall statewide "),
    (r"ಮತ್ತೆ |ಹಾಗೇ |ಅಲ್ಲಿ ", " and there "), (r"ಕೇಸ್\S*|ದೂರು\S*|ಪ್ರಕರಣ\S*", " cases "), (r"ಅಧಿಕಾರಿ\S*", " officers "),
    ([0-9೦-೯]+)(?:\s*)ದಿನ" if False else r"(?!x)x", " "),
]
KN_DEPT = [(r"ಕಂದಾಯ", "Revenue"), (r"ಗ್ರಾಮೀಣಾಭಿವೃದ್ಧಿ|ಗ್ರಾಮೀಣ ಅಭಿವೃದ್ಧಿ|ಪಂಚಾಯತ್ ರಾಜ್|ಪಂಚಾಯತ್", "RDPR"), (r"ಆಹಾರ|ಪಡಿತರ", "Food"),
           (r"ನಗರಾಭಿವೃದ್ಧಿ|ನಗರ ಅಭಿವೃದ್ಧಿ|ನಗರಸಭೆ|ಪುರಸಭೆ", "Urban Development"), (r"ಶಿಕ್ಷಣ|ಶಾಲೆ", "Education"), (r"ಆರೋಗ್ಯ|ಆಸ್ಪತ್ರೆ", "Health"),
           (r"ವಿದ್ಯುತ್|ಇಂಧನ|ಕರೆಂಟ್", "Energy"), (r"ಸಾರಿಗೆ|ಬಸ್", "Transport"), (r"ವಸತಿ", "Housing"), (r"ಪೊಲೀಸ್|ಗೃಹ ಇಲಾಖೆ", "Police"),
           (r"ಕೃಷಿ", "Agriculture"), (r"ಮಹಿಳಾ|ಮಕ್ಕಳ", "Women and Child Development")]
KN_DIGITS = str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789")
KN_LOC_RX = re.compile(r"(ನಲ್ಲಿ|ಯಲ್ಲಿ|ದಲ್ಲಿ|ಲ್ಲಿ|ತಾಲ್ಲೂಕ|ತಾಲೂಕ)")


def route_kn(t: str, profile: str, state: dict | None):
    """Kannada / code-mixed Kannada: the same router as English after the question words are mapped to their English shape;
    a Kannada place goes to the POC as said (it finds the taluk in the sentence, or the district before ಜಿಲ್ಲೆ)."""
    en = t.translate(KN_DIGITS)
    for rx, rep in KN2EN:
        en = re.sub(rx, rep, en)
    dep = next((d for rx, d in KN_DEPT if re.search(rx, t)), "")
    latin = re.sub(r"[ಀ-೿]+", " ", en)
    if dep:
        latin += f" {dep} department "
    latin = re.sub(r"\s+", " ", latin).strip()
    rt = route(latin, profile, state, _kn=True)
    m = KN_PLACE_RX.search(t)
    place = {}
    if m and m.group(2).startswith("ಜಿ"):
        place["district"] = m.group(1)
    elif KN_LOC_RX.search(t):
        place["taluk"] = t                              # the POC finds the taluk named in the sentence (Kannada, inflected)
    if not rt:
        if re.search(r"how many|how is it doing", latin) and (place or dep):
            rt = ("dashboard", {}) if "how is it doing" in latin and profile == "cs" else ("find_cases", {"status": "overdue" if "overdue" in latin else "open"})
        else:
            return None
    fn, args = rt[0], dict(rt[1])
    if fn in ("dashboard", "find_cases", "ipgrs_records"):
        for k, v in place.items():
            args.setdefault(k, v)
    return fn, args


'''
# the KN2EN list above has a dummy last entry written so the file stays plain ASCII-safe; drop it
NEW = NEW.replace('''    ([0-9೦-೯]+)(?:\\s*)ದಿನ" if False else r"(?!x)x", " "),\n''', "")
s = s[:a] + NEW + s[b:]
s = s.replace('''def route(text: str, profile: str, state: dict | None = None):
    """(function, args) for the Chief Secretary's everyday questions, or None (the existing router then decides)."""
    t = (text or "").strip()
    if not t or profile not in ("cs", "officer"):
        return None
    if re.search(r"[\\u0c80-\\u0cff]", t):
        return route_kn(t, profile, state)''',
'''def route(text: str, profile: str, state: dict | None = None, _kn: bool = False):
    """(function, args) for the Chief Secretary's everyday questions, or None (the existing router then decides)."""
    t = (text or "").strip()
    if not t or profile not in ("cs", "officer"):
        return None
    if not _kn and re.search(r"[\\u0c80-\\u0cff]", t):
        return route_kn(t, profile, state)''')
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("router patched")

# POC: a Kannada place that cannot be resolved is dropped, never guessed; a district inside the sentence is found too
patch("app/server/query_board.py", [
    ('''        elif k in ("taluk", "district", "gp", "place", "village", "entities"):
            tk = chat.taluk_in_text(v)
            if tk and k in ("taluk", "place"):
                out[k] = tk
                continue''',
     '''        elif k in ("taluk", "district", "gp", "place", "village", "entities"):
            tk = chat.taluk_in_text(v)
            if tk and k in ("taluk", "place"):
                out[k] = tk
                continue
            if k == "taluk" and len(v.split()) > 2:            # a whole Kannada sentence: a district in it, or nothing
                dists = {r[0] for r in db.q("SELECT DISTINCT district FROM gazetteer") if r[0]}
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
                continue'''),
])
print("done")
