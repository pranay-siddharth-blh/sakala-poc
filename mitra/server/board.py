"""The Chief Secretary's questions as pictures (22 Oct 2026).

- `route(text, profile, state)`: the deterministic router for her everyday questions: "how is RDPR doing", "within RDPR, how
  is Hunsur", "how many cases are with L1 / L2 / L3", "how many have been escalated / not escalated", "how many have 3 days
  left", "the 7-day timeline", "pending cases in Alur", any of the 38 departments in the Excel ("how is Education doing").
- the conversational scope: a dashboard question sets it (department / district / taluk / level); a follow-up ("and Hunsur?",
  "only L2", "what about overdue there") stays inside it; "overall / statewide / all departments" clears it. It is shown on
  screen as a chip, so the numbers are never read out of context.
- `dashboard_view(r)` and `enrich(...)`: every answer becomes a visual: a board of cards (KPI tiles, by level, the days-left
  clock, by place, the officers holding the most, top services) or, for a single count, KPI tiles plus the breakdown that
  explains it. Numbers come only from the POC's SQL; this module only arranges them."""
from __future__ import annotations

import re

LEVEL_RX = re.compile(r"\b(?:l\s?([123])|level\s?([123]|one|two|three)|(first|second|third)[- ]level)\b", re.I)
DEPT_RX = re.compile(r"\b(rdpr|rural development|panchayat raj|revenue|food(?: and civil supplies| department)?|civil supplies|urban development|"
                     r"municipal(?:ities| bodies)?|housing|women and child|women & child|wcd|energy|power department|electricity|escoms?|bescom|"
                     r"transport|ksrtc|public works|pwd|home department|police|water resources|minor irrigation|health(?: department)?|"
                     r"school education|education(?: department)?|higher education|forest|agriculture|labour|cooperation|social welfare|"
                     r"backward classes|minority welfare|horticulture|sericulture|animal husbandry|fisheries|commerce and industries|industries|"
                     r"tribal welfare|scheduled tribes|finance department|law department|youth (?:empowerment|and sports)|sports|tourism|"
                     r"skill development|e-?governance|dpar|kannada and culture|medical education|information and pr|infrastructure)\b", re.I)
DASH_RX = re.compile(r"\bhow(?:'s| is| are| has| have| did)\b.{0,60}\b(doing|performing|faring|going|placed|looking|holding up|coping)\b|"
                     r"\b(show|give|tell|bring|pull)(?: me| us)?(?: up)? (?:everything|all|the (?:whole|full|complete|entire) (?:picture|dashboard|position|status|story|view))\b|"
                     r"\b(dashboard|scorecard|report card|snapshot|overview|deep dive|health check|break[- ]?up|position|performance|status)\s+(?:of|for|in|on)\b|"
                     r"\beverything (?:about|on|in)\b|\bhow (?:bad|good) is\b|\bwhere do(?:es)? .{1,30} stand\b|\bdashboard\b", re.I)
FOLLOW_RX = re.compile(r"^\s*(and|also|what about|how about|only|just|now|then|ok(?:ay)?,?|within (?:that|it|this|them)|in (?:that|it|this|there)|same|for (?:that|them|those)|"
                       r"there|of (?:those|them|these))\b|\b(in (?:that|this) (?:department|district|taluk)|within (?:that|it|them)|of those|of them|there\??$|same department|inside (?:that|it))\b", re.I)
CLEAR_RX = re.compile(r"ಒಟ್ಟಾರೆ|ಇಡೀ ರಾಜ್ಯ|ರಾಜ್ಯದಲ್ಲಿ|ರಾಜ್ಯ ಮಟ್ಟ|\b(overall|statewide|state[- ]wide|all departments|whole state|across (?:the )?state|across karnataka|in karnataka|in total|entire state|clear (?:the )?(?:scope|filter)|everything overall)\b", re.I)
KN_DASH_RX = re.compile(r"ಹೇಗಿದೆ|ಹೇಗಿದ್ದಾರೆ|ಹೇಗೆ perform|ಹೇಗೆ ನಡೀತಿದೆ|ಹೇಗೆ ನಡೆಯುತ್ತಿದೆ|ಪರಿಸ್ಥಿತಿ|ಸ್ಥಿತಿ ಏನು|ಎಲ್ಲಾ ವಿವರ|dashboard", re.I)
KN_COUNT_RX = re.compile(r"ಎಷ್ಟು")
DAYS_RX = re.compile(r"\b(\d|one|two|three|four|five|six|seven)\s+days?\s+(?:left|remaining|to go|before (?:the )?deadline)\b", re.I)
WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
TIMELINE_RX = re.compile(r"\b(days? left|days remaining|time left|deadline(?:s)?(?: wise| distribution| break ?up| split)?|7[- ]day (?:clock|timeline|window)|seven[- ]day|close to (?:their |the )?deadlines?|"
                         r"timeline|clock(?: wise)?|due (?:today|tomorrow)|by days|how close to (?:the )?deadline|about to (?:breach|expire|go overdue)|near(?:ing)? (?:the )?deadline)\b", re.I)
ESC_RX = re.compile(r"\bescalat", re.I)
NOT_ESC_RX = re.compile(r"\b(not|never|n't|non)[- ]?(?:been |yet )?escalat|\bunescalated\b", re.I)
SPLIT_RX = re.compile(r"\b(by|per|each|every|across|wise|split|break ?up|breakdown|distribution|versus|vs|compared?)\b|\bl1,? l2,? (?:and )?l3\b", re.I)
COUNTQ_RX = re.compile(r"\b(how many|how much|number of|count|total|tally|what is the (?:number|count))\b", re.I)


def level_of(t: str) -> str:
    m = LEVEL_RX.search(t or "")
    if not m:
        if re.search(r"\b(field officers?|last[- ]mile|lmf)\b", t or "", re.I):
            return "L1"
        return ""
    v = (m.group(1) or m.group(2) or m.group(3) or "").lower()
    return "L" + str({"one": 1, "two": 2, "three": 3, "first": 1, "second": 2, "third": 3}.get(v, v))


def dept_of(t: str) -> str:
    m = DEPT_RX.search(t or "")
    return m.group(1) if m else ""


def _place(t: str) -> dict:
    from . import tools
    out = {}
    d, tk = tools._find_place(t, "district"), tools._find_place(t, "taluk")
    if tk and (not d or tk.lower() != d.lower() or re.search(r"\btaluk\b", t, re.I)):
        out["taluk"] = tk
    elif d:
        out["district"] = d
    return out


def scope_args(state: dict, text: str, args: dict, fn: str) -> dict:
    """Merge the conversation's scope into a data call when the question is a follow-up; clear it when asked."""
    sc = (state or {}).get("scope") or {}
    t = text or ""
    if sc and state is not None and state.get("scope_live") is False:
        sc = {}                                         # an unrelated question came in between: the scope has lapsed
    if CLEAR_RX.search(t):
        if state is not None:
            state["scope"] = {}
        return args
    if not sc or fn not in ("dashboard", "find_cases", "ipgrs_records"):
        return args
    words = len(t.split())
    named_dept = bool(dept_of(t)) or bool(args.get("department"))
    if args.get("officer") or re.search(r"\b(tahsildar|pdo|officer|engineer|inspector|commissioner|ceo)\b", t, re.I) and fn == "dashboard":
        return args                                   # an officer has their own department
    marker = bool(FOLLOW_RX.search(t))
    if fn == "dashboard":
        follow = marker or (words <= 6 and not named_dept and not re.search(r"\bdashboard\b", t, re.I))
    else:
        follow = marker or (words <= 5 and not named_dept)
    if not follow:
        if fn == "dashboard" and state is not None:
            state["scope"] = {}
        return args
    out = dict(args)
    if sc.get("department") and not named_dept:
        out["department"] = sc["department"]
    if sc.get("district") and not (out.get("district") or out.get("taluk")):
        out["district"] = sc["district"]
    if sc.get("taluk") and not (out.get("taluk") or out.get("district") or out.get("gp")):
        out["taluk"] = sc["taluk"]
    if sc.get("level") and not out.get("level") and fn == "dashboard":
        out["level"] = sc["level"]
    out["_scoped"] = True
    return out


KN_PLACE_RX = re.compile(r"(\S+?)(?:ದಲ್ಲಿ|ನಲ್ಲಿ|ಯಲ್ಲಿ|ಲ್ಲಿ)?\s*(ತಾಲ್ಲೂಕ|ತಾಲೂಕ|ಜಿಲ್ಲೆ)")


KN2EN = [  # Kannada question words -> the English shape the router knows (longest first)
    (r"ಎಸ್ಕಲೇಟ್ ಆಗಿಲ್ಲ|escalate ಆಗಿಲ್ಲ|escalate ಆಗದ|ಮೇಲಕ್ಕೆ ಹೋಗಿಲ್ಲ|ಮೇಲಕ್ಕೆ ಹೋಗದ", " not escalated "),
    (r"ಎಸ್ಕಲೇಟ್|escalate ಆಗಿ|escalate ಆದ|ಮೇಲಕ್ಕೆ ಹೋದ|ಮೇಲಿನ ಹಂತಕ್ಕೆ ಹೋದ", " escalated "),
    (r"(?:ಇವತ್ತೇ|ಇವತ್ತು|ಇಂದೇ|ಇಂದು)\s*(?:due|ಡ್ಯೂ|ಕೊನೆ ದಿನ)", " due today "), (r"ನಾಳೆ\s*(?:due|ಡ್ಯೂ|ಕೊನೆ ದಿನ)", " due tomorrow "),
    (r"ಇವತ್ತೇ|ಇವತ್ತು|ಇಂದೇ|ಇಂದು", " today "), (r"ನಾಳೆ", " tomorrow "),
    (r"ಹಂತವಾರು|ಹಂತಗಳ ಪ್ರಕಾರ|level ಪ್ರಕಾರ|level wise|levels? ಪ್ರಕಾರ", " level wise "),
    (r"ಮೊದಲ ಹಂತ|ಒಂದನೇ ಹಂತ|ಹಂತ ೧|ಹಂತ 1", " L1 "), (r"ಎರಡನೇ ಹಂತ|ಹಂತ ೨|ಹಂತ 2", " L2 "), (r"ಮೂರನೇ ಹಂತ|ಹಂತ ೩|ಹಂತ 3", " L3 "),
    (r"ದಿನಗಳ? ಉಳಿದಿ\S*|ದಿನ ಬಾಕಿ\S*|ದಿನ ಉಳಿದ\S*|ದಿನ ಇರುವ\S*|days? ಉಳಿದ\S*|days? ಬಾಕಿ\S*|days? left", " days left "),
    (r"deadline ಪ್ರಕಾರ|ಗಡುವಿನ ಪ್ರಕಾರ|timeline|ಟೈಮ್‌?ಲೈನ್", " the 7 day timeline "),
    (r"ಹೇಗೆ perform ಮಾಡ್ತಿದೆ|ಹೇಗೆ perform ಮಾಡ್ತಿದ್ದಾರೆ|ಹೇಗಿದೆ|ಹೇಗಿದ್ದಾರೆ|ಹೇಗೆ ನಡೀತಿದೆ|ಹೇಗೆ ನಡೆಯುತ್ತಿದೆ|ಪರಿಸ್ಥಿತಿ ಏನು|ಸ್ಥಿತಿ ಏನು|ಎಲ್ಲಾ ವಿವರ\S*", " how is it doing "),
    (r"ಎಷ್ಟು", " how many "), (r"ವಿಳಂಬ\S*|ಗಡುವು ಮೀರಿ\S*|overdue ಆಗಿ\S*", " overdue "), (r"ಬಾಕಿ\S*|pending", " pending "),
    (r"ಪರಿಹಾರ ಆಗಿ\S*|ಪರಿಹರಿಸ\S*|ಮುಕ್ತಾಯ\S*", " resolved "), (r"ಒಟ್ಟಾರೆ|ರಾಜ್ಯದಲ್ಲಿ|ರಾಜ್ಯ ಮಟ್ಟದ|ಇಡೀ ರಾಜ್ಯ", " overall statewide "),
    (r"ಮತ್ತೆ |ಹಾಗೇ |ಅಲ್ಲಿ ", " and there "), (r"ಕೇಸ್\S*|ದೂರು\S*|ಪ್ರಕರಣ\S*", " cases "), (r"ಅಧಿಕಾರಿ\S*", " officers "),
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
    elif KN_LOC_RX.search(t) or (not dep and re.search(r"how many|how is it doing", latin_q := re.sub(r"[ಀ-೿]+", " ", en))):
        place["taluk"] = t                              # the POC finds the taluk named in the sentence (Kannada, inflected)
    if not rt and (state or {}).get("scope") and profile == "cs" and len(t.split()) <= 4 and not dep:
        return "dashboard", {"taluk": t}                 # "ಮತ್ತೆ ಹುಣಸೂರು?" = and Hunsur? inside the scope on screen
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


def route(text: str, profile: str, state: dict | None = None, _kn: bool = False):
    """(function, args) for the Chief Secretary's everyday questions, or None (the existing router then decides)."""
    t = (text or "").strip()
    if not t or profile not in ("cs", "officer"):
        return None
    if not _kn and re.search(r"[\u0c80-\u0cff]", t):
        return route_kn(t, profile, state)
    low = t.lower()
    if re.search(r"\b(sakala|2025|last year|late delivery|rejection rate)\b", low):
        if profile == "cs" and re.search(r"\b(2025|last year|late delivery|rejection rate|performance|worst|best|rank|district)\b", low):
            d = _place(t).get("district")              # the Sakala 2025 reports, from SQL, whatever the gateway's state
            return "sakala_2025", ({"district": d} if d else {})
        return None
    if re.search(r"\b(nudge|remind|send|reject|accept|resolve|approve|open (?:case|gr)|gr[- ]?\d|sk-)\b", low):
        return None
    sc = (state or {}).get("scope") or {}
    dept, lvl, pl = dept_of(t), level_of(t), _place(t)
    args: dict = {}
    if dept:
        args["department"] = dept
    args.update(pl)
    # a dashboard: "how is RDPR doing", "show me everything about Hunsur", "dashboard for L2"
    from . import tools
    if profile == "cs" and DASH_RX.search(t) and tools._OFFICER_RX.search(t):
        o = tools.find_officer(t)
        if o:
            return "dashboard", {"officer": tools.off_name(o, False)}
    if profile == "cs" and DASH_RX.search(t) and not (dept or pl or lvl) and (CLEAR_RX.search(t) or re.search(r"\b(karnataka|state|whole)\b", low)):
        return "dashboard", {}                         # the whole state as a board (and the scope cleared)
    if DASH_RX.search(t) and (dept or pl or lvl or sc) and profile == "cs":
        if lvl:
            args["level"] = lvl
        return "dashboard", args
    # "and Hunsur?" / "what about Alur?" inside a scope: the board narrowed
    if sc and profile == "cs" and (pl or lvl) and len(t.split()) <= 7 and FOLLOW_RX.search(t) and not COUNTQ_RX.search(t):
        if lvl:
            args["level"] = lvl
        return "dashboard", args
    # the 7-day clock
    m = DAYS_RX.search(t)
    if m:
        n = m.group(1).lower()
        return "find_cases", {**args, "days_left": WORDNUM.get(n, int(n) if n.isdigit() else 0), **({"level": lvl} if lvl else {})}
    if re.search(r"\bdue today\b", low) and COUNTQ_RX.search(t):
        return "find_cases", {**args, "days_left": 0}
    if re.search(r"\bdue tomorrow\b", low) and COUNTQ_RX.search(t):
        return "find_cases", {**args, "days_left": 1}
    if TIMELINE_RX.search(t) and re.search(r"\b(cases?|grievances?|complaints?|pending|open|how many|show|break|distribution|timeline|clock|left|deadlines?)\b", low):
        return "find_cases", {**args, "group_by": "days_left", **({"level": lvl} if lvl else {})}
    # levels
    if re.search(r"\blevel[- ]?wise\b|\bby levels?\b|\bacross (?:the )?levels\b|\beach level\b|\bl1,? l2,? (?:and |or )?l3\b|\bwhich level\b|\bper level\b", low):
        return "find_cases", {**args, "group_by": "level", "status": "open"}
    if lvl and (COUNTQ_RX.search(t) or re.search(r"\b(with|at|pending (?:with|at)|lying (?:with|at)|stuck (?:with|at)|sitting (?:with|at))\b", low)):
        return "find_cases", {**args, "level": lvl, "status": "overdue" if re.search(r"\boverdue|late\b", low) else "open"}
    # escalation
    if ESC_RX.search(t):
        if SPLIT_RX.search(t) and not NOT_ESC_RX.search(t) or re.search(r"\b(escalated (?:and|or|vs|versus) not|escalation (?:status|break ?up|split|picture))\b", low):
            return "find_cases", {**args, "group_by": "escalated"}
        if NOT_ESC_RX.search(t):
            return "find_cases", {**args, "escalated": False, "status": "open"}
        if COUNTQ_RX.search(t) or re.search(r"\b(show|list|which|cases)\b", low):
            return "find_cases", {**args, "escalated": True}
    # a department outside the pilot, or any department, as a count
    if dept and COUNTQ_RX.search(t):
        st = "overdue" if re.search(r"\boverdue|late\b", low) else "resolved" if re.search(r"\b(resolved|closed|disposed)\b", low) else "open"
        return "find_cases", {**args, "status": st}
    return None


# ------------------------------------------------------------------ pictures
def _card(title, items, kind="bars", subtitle="", by="", unit="cases", metric="count"):
    return {"type": kind, "title": title, "subtitle": subtitle, "metric": metric, "unit": unit, "by": by,
            "items": [{"label": str(it["name"]), "value": it["value"], "aliases": it.get("aliases") or [], "district": it.get("district") or "",
                       "geo": it.get("geo") or {}, "tone": it.get("tone") or ""} for it in items]}


def tiles(pairs: list[tuple[str, int, str]], title="At a glance", subtitle="") -> dict:
    return _card(title, [{"name": a, "value": b, "tone": c, "aliases": [a.lower()]} for a, b, c in pairs], "tiles", subtitle)


LEVEL_ALIAS = {"L1": ["l1", "field officer", "level one", "first level"], "L2": ["l2", "level two", "second level"], "L3": ["l3", "level three", "third level"]}


def _plural(n, w):
    return f"{n:,} {w}{'' if n == 1 else 's'}"


MAP_RX = re.compile(r"\b(on (?:a |the )?(?:single |big |one )?map|map|maps|across (?:the )?(?:state|karnataka)|state of karnataka|all over (?:the )?(?:state|karnataka)|"
                    r"district[- ]?wise|which parts|where (?:are|is) (?:the|most|all))\b|ನಕ್ಷೆ|map", re.I)


def map_view(r: dict) -> tuple[str, list]:
    """The map question: one big Karnataka map (every district, from SQL) + a small KPI column + the level split."""
    k = r["kpis"]
    title = r.get("title") or "Karnataka"
    geo = sorted((r.get("geo") or {}).items(), key=lambda kv: -kv[1])
    ipgrs = r["source"] == "ipgrs"
    what = "grievances in process" if ipgrs else "open grievances"
    top = ", ".join(f"{d} {n:,}" for d, n in geo[:3])
    say = (f"Here are the {k['open']:,} {what} {'in ' + title if title != 'Karnataka' else 'across Karnataka'} on the map."
           + (f" The most are in {top}." if top else "") + (" From the iPGRS sample week." if ipgrs else ""))
    cards = [_card(f"{what.capitalize()} · {title}", [{"name": d, "value": n, "district": d, "aliases": [d.lower()]} for d, n in geo], "map",
                   f"{len(geo)} districts · {r.get('period') or ''}", by="district"),
             tiles([("Open" if not ipgrs else "In process", k["open"], ""), ("Overdue" if not ipgrs else "Closed", k["overdue"] if not ipgrs else k["closed"], "bad" if not ipgrs else "ok"),
                    ("Escalated" if not ipgrs else "At scrutiny", k["escalated_open"] if not ipgrs else k["scrutiny"], "vio"), ("Due soon" if not ipgrs else "Total", k["due_3"] if not ipgrs else k["total"], "warn")],
                   subtitle="at a glance"),
             _card("By level", [{"name": x["name"], "value": x["count"], "aliases": LEVEL_ALIAS[x["name"]]} for x in r["by_level"]], "bars", "open")]
    return say, [{"op": "viz", "title": f"{title} · on the map", "insight": f"{geo[0][0]} has the most, {geo[0][1]:,}" if geo else "", "cards": cards, "mapfocus": True}]


def dashboard_view(r: dict) -> tuple[str, list]:
    k = r["kpis"]
    title = r.get("title") or "Karnataka"
    places = r.get("places") or []
    offs = r.get("officers") or []
    pb = r.get("place_by") or "district"
    by_txt = {"gp": "Gram Panchayat", "taluk": "taluk", "district": "district"}.get(pb, pb)
    if r["source"] == "ipgrs":
        say = (f"{title}, from the real iPGRS records of the sample week, 3 to 9 October: {_plural(k['total'], 'grievance')}, "
               f"{k['open']:,} still in process, {k['closed']:,} closed by officers and {k['scrutiny']:,} at scrutiny. "
               f"Of the open ones, {k['l1']:,} are with L1 field officers, {k['l2']:,} at L2 and {k['l3']:,} at L3.")
        if places:
            say += f" The most are in {places[0]['name']}, {places[0]['count']:,}."
        if offs:
            say += f" {offs[0]['name']} holds the most, {offs[0]['open']:,}."
        say += " This department is outside the live pilot, so there is no deadline clock on it yet."
        cards = [tiles([("Grievances", k["total"], ""), ("In process", k["open"], "warn"), ("Closed", k["closed"], "ok"), ("At scrutiny", k["scrutiny"], "vio"),
                        ("At L1", k["l1"], "l1"), ("At L2", k["l2"], "l2"), ("At L3", k["l3"], "l3"), ("Sakala-tagged", k["sakala_tagged"], "")],
                       subtitle="iPGRS sample week · 3–9 Oct 2026"),
                 _card("Open by level", [{"name": x["name"], "value": x["count"], "aliases": LEVEL_ALIAS[x["name"]]} for x in r["by_level"]], "bars", "in process"),
                 _card("Status", [{"name": x["name"], "value": x["count"]} for x in r["status"]], "donut", "all grievances"),
                 _card(f"Open by {by_txt}", [{"name": x["name"], "value": x["count"], "district": x.get("district") or "", "aliases": [str(x["name"]).lower()]} for x in places[:10]], "race", f"top {min(10, len(places))}", by=pb),
                 _card("Officers holding the most", [{"name": x["name"], "value": x["open"]} for x in offs[:8]], "race", "in process"),
                 _card("Top services", [{"name": x["name"], "value": x["count"]} for x in (r.get("services") or [])[:8]], "race", "in process")]
        insight = f"{k['open']:,} of {k['total']:,} still in process" if k["total"] else "No grievances in the sample week"
        return say, [{"op": "viz", "title": f"{title} · dashboard", "insight": insight, "cards": [c for c in cards if c["items"]], "board": True}]
    oldest = (r.get("oldest_overdue") or [None])[0]
    say = (f"{title}: {k['open']:,} open, {k['overdue']:,} overdue and {k['escalated_open']:,} escalated. "
           f"{k['l1']:,} are with L1 field officers, {k['l2']:,} at L2 and {k['l3']:,} at L3. "
           f"{k['due_today']:,} {'is' if k['due_today'] == 1 else 'are'} due today and {k['due_3']:,} within three days.")
    if places:
        say += f" The most open are in {places[0]['name']}, {places[0]['count']:,}."
    if offs:
        say += f" {offs[0]['name']} holds the most, {offs[0]['open']:,}" + (f", {offs[0]['overdue']} overdue." if offs[0].get("overdue") else ".")
    if oldest:
        say += f" The longest overdue is {oldest['id']}, {oldest['days_overdue']} day{'s' if oldest['days_overdue'] != 1 else ''} late with {oldest['officer']}."
    if not k["open"]:
        say = f"{title}: no open cases right now. {k['resolved']:,} resolved, {k['total']:,} in all."
    cards = [tiles([("Open", k["open"], ""), ("Overdue", k["overdue"], "bad"), ("Escalated", k["escalated_open"], "vio"), ("Due soon", k["due_3"], "warn"),
                    ("At L1", k["l1"], "l1"), ("At L2", k["l2"], "l2"), ("At L3", k["l3"], "l3"), ("Resolved", k["resolved"], "ok")],
                   subtitle=r.get("period") or "live caseload"),
             _card("Open by level", [{"name": x["name"], "value": x["count"], "aliases": LEVEL_ALIAS[x["name"]]} for x in r["by_level"]], "bars", "L1 field · L2 senior · L3 top"),
             _card("Days left on the clock", [{"name": x["name"].replace(" left", ""), "value": x["count"], "aliases": [x["name"].lower()]} for x in r["days_left"]], "bars", "open cases · 7-day timeline"),
             _card(f"Open by {by_txt}", [{"name": x["name"], "value": x["count"], "district": x.get("district") or "", "aliases": [str(x["name"]).lower()]} for x in places[:10]], "race", f"top {min(10, len(places))}", by=pb),
             _card("Officers holding the most", [{"name": x["name"], "value": x["open"], "aliases": [x["name"].lower()]} for x in offs[:8]], "race", "open cases"),
             _card("Top services", [{"name": x["name"], "value": x["count"]} for x in (r.get("services") or [])[:8]], "race", "open cases")]
    insight = (f"{k['overdue']} overdue · {k['due_3']} due within 3 days" if k["open"] else "Nothing open")
    return say, [{"op": "viz", "title": f"{title} · dashboard", "insight": insight, "cards": [c for c in cards if c["items"]], "board": True}]


def scope_from(r: dict) -> dict:
    sc = dict(r.get("scope") or {})
    sc.pop("officer", None); sc.pop("service", None)
    return sc


def scope_op(sc: dict) -> dict:
    label = " › ".join(x for x in (sc.get("department"), sc.get("district"), sc.get("taluk"), sc.get("gp"), sc.get("level")) if x)
    return {"op": "scope", "scope": sc, "label": label}


def context_group(args: dict) -> str:
    """For a single count, the breakdown that explains it best."""
    if args.get("level"):
        return "level"
    if args.get("days_left") is not None or args.get("due_within_days") is not None:
        return "days_left"
    if "escalated" in args:
        return "level"
    if args.get("taluk"):
        return "service"
    if args.get("district"):
        return "taluk"
    if args.get("department"):
        return "district"
    if args.get("status") == "overdue":
        return "district"
    return "level"


def count_view(r: dict, args: dict, ctx: dict | None) -> list:
    """KPI tiles for a single count + the breakdown card that explains it."""
    cards = [tiles([("Matching", r.get("total", 0), ""), ("Open", r.get("open", 0), "warn"), ("Overdue", r.get("overdue", 0), "bad"),
                    ("Resolved", r.get("resolved", 0), "ok")], title="The count", subtitle=_filters_text(args))]
    if ctx and ctx.get("groups"):
        g = ctx["groups"]
        by = ctx.get("group_by")
        kind = "bars" if by in ("level", "days_left") or len(g) <= 5 else "race"
        if by == "escalated":
            kind = "donut"
        items = [{"name": x["name"], "value": x["count"], "aliases": LEVEL_ALIAS.get(x["name"], []), "district": x["name"] if by == "district" else ""} for x in g]
        cards.append(_card({"level": "By level", "days_left": "Days left on the clock", "district": "By district", "taluk": "By taluk",
                            "service": "By service", "escalated": "Escalated or not"}.get(by, f"By {by}"), items, kind, "for the same filters", by=by))
    return cards


def _filters_text(a: dict) -> str:
    parts = []
    for k in ("department", "district", "taluk", "gp", "level", "status"):
        if a.get(k):
            parts.append(str(a[k]))
    if a.get("days_left") is not None:
        n = int(a["days_left"])
        parts.append("due today" if n == 0 else f"{n} day{'s' if n != 1 else ''} left")
    if a.get("escalated") is True:
        parts.append("escalated")
    if a.get("escalated") is False:
        parts.append("not escalated")
    return " · ".join(parts) or "live caseload"
