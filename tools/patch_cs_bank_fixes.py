"""Fixes from the first CS-bank run (22 Oct 2026): deadline phrasings, zero counts still explained by a breakdown, 'how is X district
performing' is a dashboard (not the 2025 tracker) unless she says Sakala / 2025, Kannada questions on the fallback path."""
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


patch("mitra/server/board.py", [
    ('''TIMELINE_RX = re.compile(r"\\b(days? left|days remaining|time left|deadline(?:s)?(?: wise| distribution| break ?up| split)?|7[- ]day (?:clock|timeline|window)|seven[- ]day|"''',
     '''TIMELINE_RX = re.compile(r"\\b(days? left|days remaining|time left|deadline(?:s)?(?: wise| distribution| break ?up| split)?|7[- ]day (?:clock|timeline|window)|seven[- ]day|close to (?:their |the )?deadlines?|"'''),
    ('''def route(text: str, profile: str, state: dict | None = None):
    """(function, args) for the Chief Secretary's everyday questions, or None (the existing router then decides)."""
    t = (text or "").strip()
    if not t or profile not in ("cs", "officer"):
        return None
    low = t.lower()''',
     '''KN_PLACE_RX = re.compile(r"(\\S+?)(?:ದಲ್ಲಿ|ನಲ್ಲಿ|ಯಲ್ಲಿ|ಲ್ಲಿ)?\\s*(ತಾಲ್ಲೂಕ|ತಾಲೂಕ|ಜಿಲ್ಲೆ)")


def route_kn(t: str, profile: str, state: dict | None):
    """Kannada on the fallback path: the question's shape from Kannada words; place and department names go to the POC as said,
    where they are normalised (ಹುಣಸೂರು -> Hunsur, ಕಂದಾಯ -> Revenue)."""
    args: dict = {}
    m = KN_PLACE_RX.search(t)
    if m:
        args["taluk" if m.group(2).startswith("ತಾ") else "district"] = m.group(1)
    d = dept_of(t) or (re.search(r"(ಕಂದಾಯ|ಗ್ರಾಮೀಣ\\S*|ಪಂಚಾಯ\\S*|ಆಹಾರ|ನಗರ\\S*|ಶಿಕ್ಷಣ|ಆರೋಗ್ಯ|ವಿದ್ಯುತ್|ಸಾರಿಗೆ|ವಸತಿ|ಪೊಲೀಸ್|ಕೃಷಿ)", t) or [None])[0]
    if d:
        args["department"] = d if isinstance(d, str) else d
    lv = re.search(r"(?:ಹಂತ|level|L)\\s*([1-3೧-೩])", t, re.I)
    if lv:
        args["level"] = "L" + lv.group(1).translate(str.maketrans("೧೨೩", "123"))
    if re.search(r"ಹೇಗಿದೆ|ಹೇಗಿದ್ದಾರೆ|ಹೇಗೆ ನಡೆ|ಪರಿಸ್ಥಿತಿ|ಸ್ಥಿತಿ ಏನು|ಎಲ್ಲಾ ವಿವರ|dashboard", t) and args and profile == "cs":
        return "dashboard", args
    if re.search(r"ಎಷ್ಟು|how many", t, re.I):
        st = "overdue" if re.search(r"ವಿಳಂಬ|ಗಡುವು|ತಡ|overdue", t) else "resolved" if re.search(r"ಪರಿಹರ|ಮುಕ್ತಾಯ", t) else "open"
        if re.search(r"ಮೇಲಕ್ಕೆ|escalat", t):
            return "find_cases", {**args, "escalated": True}
        dl = re.search(r"([1-7೧-೭])\\s*ದಿನ", t)
        if dl:
            return "find_cases", {**args, "days_left": int(dl.group(1).translate(str.maketrans("೧೨೩೪೫೬೭", "1234567")))}
        return "find_cases", {**args, "status": st}
    return None


def route(text: str, profile: str, state: dict | None = None):
    """(function, args) for the Chief Secretary's everyday questions, or None (the existing router then decides)."""
    t = (text or "").strip()
    if not t or profile not in ("cs", "officer"):
        return None
    if re.search(r"[\\u0c80-\\u0cff]", t):
        return route_kn(t, profile, state)
    low = t.lower()
    if re.search(r"\\b(sakala|2025|last year|late delivery|rejection rate)\\b", low):
        return None                                    # the Sakala 2025 reports have their own answer'''),
])

patch("mitra/server/brain.py", [
    ('''    if pre["intent"] in ("ask_data", "smalltalk", "open_case", "show_chart_as", "summary") and ctx["profile"] in ("cs", "officer"):''',
     '''    if pre["intent"] in ("ask_data", "smalltalk", "open_case", "show_chart_as", "summary", "tracker", "chat_text") and ctx["profile"] in ("cs", "officer"):'''),
])

patch("mitra/server/query.py", [
    ('''        ctx = await sakala._post("/api/query", {"tool": "ipgrs_records" if name == "ipgrs_records" else tool, "args": {**ctx_args, "group_by": g}})''',
     '''        ctx = await sakala._post("/api/query", {"tool": "ipgrs_records" if name == "ipgrs_records" else tool, "args": {**ctx_args, "group_by": g}})
        if (not ctx.get("groups") or not sum(x["count"] for x in ctx["groups"])) and ctx_args.get("status"):
            ctx_args.pop("status", None)              # nothing matches (0 overdue): show the open picture behind it instead
            ctx = await sakala._post("/api/query", {"tool": "ipgrs_records" if name == "ipgrs_records" else tool, "args": {**ctx_args, "status": "open", "group_by": g}})'''),
])

patch("mitra/tests/cs_bank.py", [
    ('''    ("and in Mysuru?", dict(num=DB.execute("SELECT COUNT(*) FROM ipgrs_records WHERE dept LIKE 'Department of School Education%' AND lower(district)='mysuru'").fetchone()[0], board=True, scope="School Education › Mysuru")),''',
     '''    ("and in Mysuru?", dict(num=DB.execute("SELECT COUNT(*) FROM ipgrs_records WHERE dept LIKE 'Department of School Education%' AND lower(district)='mysuru'").fetchone()[0], viz=3, scope="School Education › Mysuru")),'''),
])
print("done")
