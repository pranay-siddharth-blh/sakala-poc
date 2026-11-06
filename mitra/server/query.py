"""Ask-anything over the whole Sakala data, as Live functions (and a screen panel for every answer).

The numbers come from the POC's deterministic query engine (`POST /api/query`, SQL over the live caseload, the 9,999 real
iPGRS records, officers, gazetteer, Sakala 2025); the model only picks the function and the filters, then speaks
the result. Each answer is also drawn on screen: a case card, a list of cases, a chart, or a short fact sheet."""
from __future__ import annotations

import html
import re

from . import sakala, tools

S, I, B = {"type": "STRING"}, {"type": "INTEGER"}, {"type": "BOOLEAN"}
CHART = {"type": "STRING", "description": "how to show the answer: bars, line, donut or map (the Karnataka map). Choose map whenever the person mentions a map, where, which parts of the state, across Karnataka, district-wise, spread, footprint or geography; otherwise leave it empty."}
CASE_FILTERS = {
    "district": S, "taluk": S, "gp": S, "department": S, "service": S,
    "status": {"type": "STRING", "description": "open, pending, in progress, info requested, resolved, rejected, scrutiny, closed, overdue"},
    "overdue": B, "due_within_days": I, "vulnerable": B, "level": {"type": "STRING", "description": "L1, L2 or L3"},
    "officer": {"type": "STRING", "description": "officer name or post, e.g. Tahsildar Hunsur, PDO Attigodu"},
    "source": {"type": "STRING", "description": "channel: camp, csc, web, app, call, whatsapp, mitra"},
    "kind": {"type": "STRING", "description": "grievance or application (Sakala service)"},
    "escalated": {"type": "BOOLEAN", "description": "true = escalated (auto-escalated, re-opened up the ladder or appealed); false = never escalated"},
    "days_left": {"type": "INTEGER", "description": "open cases with exactly this many days left on their deadline (0 = due today)"},
    "since_go_live": {"type": "BOOLEAN", "description": "only requests filed since the pilot went live (WhatsApp / Mitra)"},
    "created_from": {"type": "STRING", "description": "YYYY-MM-DD"}, "created_to": {"type": "STRING", "description": "YYYY-MM-DD"},
    "text": {"type": "STRING", "description": "a word that must appear in the complaint"},
    "group_by": {"type": "STRING", "description": "district, taluk, gp, department, service, officer, status, source, level, days_left (the 7-day clock: overdue, due today, 1..7 days left), escalated (escalated vs not), kind, vulnerable, day, month"},
    "sort": {"type": "STRING", "description": "urgent (default), newest, oldest"}, "limit": I, "chart": CHART,
}
IPGRS_FILTERS = {
    "district": S, "taluk": S, "gp": S, "department": {"type": "STRING", "description": "any of the 38 departments, e.g. Urban Development, Revenue, Health"},
    "line_department": S, "service": S, "status": {"type": "STRING", "description": "open/pending (InProcess), closed, resolved, scrutiny"},
    "source": {"type": "STRING", "description": "Praja Seva Abhiyana, Citizen Service Centre, iPGRS website, Mobile App, call centre"},
    "service_type": {"type": "STRING", "description": "sakala or non sakala"}, "level": S, "officer": S,
    "created_from": S, "created_to": S, "text": S,
    "group_by": {"type": "STRING", "description": "department, line_department, service, grievance, district, taluk, gp, status, source, service_type, level, officer, day"},
    "limit": I, "chart": CHART,
}
FUNCS = {
    "dashboard": ("The full dashboard of one thing, drawn as a board of cards: KPIs (open, overdue, escalated, due soon, at L1 / L2 / L3, "
                  "resolved), by level, the days-left clock, by place, the officers holding the most, top services. Use it for 'how is X doing', "
                  "'show me everything about X', 'X's position / performance / status', 'dashboard for X', where X is any department in "
                  "the Excel (RDPR, Revenue, Food, Urban Development, Education, Health, Energy, Police ...), a district, a taluk, a Gram "
                  "Panchayat, a level (L1, L2, L3), an officer or the whole state. Follow-ups ('and Hunsur?', 'only L2') stay inside "
                  "the last department / place unless she says overall or statewide.",
                  {"department": S, "district": S, "taluk": S, "gp": S, "level": {"type": "STRING", "description": "L1, L2 or L3"},
                   "officer": S, "service": S}, (), "dashboard"),
    "lookup_case": ("Everything about one case or iPGRS grievance: give any case id (GR-504227, SK-...) or the 6-digit G.Id from the "
                    "Excel. Returns status, officer, level, place, department, service, days left, escalation chain, history, the "
                    "complaint text and the original iPGRS record.", {"case_id": S}, ("case_id",), "case_info"),
    "find_cases": ("Search, count, rank or list the live caseload (statewide, pilot departments Revenue, RDPR, Food) with any "
                   "filters; group_by gives counts per district/officer/service/etc.", CASE_FILTERS, (), "find_cases"),
    "ipgrs_records": ("Search, count or rank the 9,999 real iPGRS grievances of the sample week (3-9 Oct 2026, all 38 "
                      "departments, all 31 districts).", IPGRS_FILTERS, (), "ipgrs_records"),
    "officer_profile": ("Everything about one officer: post, department, place, who they report to, open / overdue / resolved "
                        "cases, the most urgent one.", {"officer": S}, ("officer",), "officer_profile"),
    "place_info": ("What is in a village, Gram Panchayat, taluk or district: where it is, which officers serve it, how many cases are "
                   "open or overdue there, the top services.", {"place": S}, ("place",), "place_info"),
    "statewide_stats": ("The overall position right now: totals open / overdue / resolved / vulnerable / escalated / at the "
                        "scrutiny desk, by level, department and channel, filed since go-live and today.", {}, (), "statewide_stats"),
    "sakala_2025": ("Sakala 2025 performance from the official reports: state late-delivery and rejection rates, best and worst "
                    "districts, a district's figures, month-by-month overdue.", {"district": S, "monthly": B}, (), "sakala_2025"),
    "compare": ("Compare two to eight named things side by side with a chart that builds as you speak: districts, taluks, Gram "
                "Panchayats, departments (Revenue, RDPR, Food), officers, services or channels. Use it whenever the person says "
                "compare / versus / against / which of these / side by side, or names several places or departments in one question.",
                {"entities": {"type": "STRING", "description": "the names, comma separated, exactly as said (e.g. 'Piriyapatna, Hunsur, Mysore')"},
                 "metrics": {"type": "STRING", "description": "comma separated from: open, overdue, resolved, rejected, vulnerable, escalated, scrutiny, total, due_soon (default open)"},
                 "by": {"type": "STRING", "description": "district, taluk, gp, department, officer, service or source (optional; detected from the names)"},
                 "chart": CHART},
                ("entities",), "compare"),
    "ranking": ("Top N by a metric with a ranked chart over the LIVE caseload: which districts / taluks / officers / services / departments "
                "have the most open, overdue, resolved, vulnerable or escalated cases. For the iPGRS sample week use ipgrs_records with group_by.",
                {"by": {"type": "STRING", "description": "district, taluk, gp, department, officer, service, source"},
                 "metric": {"type": "STRING", "description": "open, overdue, resolved, rejected, vulnerable, escalated, scrutiny, total"}, "limit": I,
                 "chart": CHART},
                ("by",), "ranking"),
}
PROFILES = {"officer": set(FUNCS) - {"dashboard"}, "cs": set(FUNCS)}
ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "last": -1}


def declarations(profile: str) -> list[dict]:
    out = []
    for name in sorted(PROFILES.get(profile, ())):
        desc, props, req, _ = FUNCS[name]
        d = {"name": name, "description": desc}
        if props:
            d["parameters"] = {"type": "OBJECT", "properties": props, **({"required": list(req)} if req else {})}
        out.append(d)
    return out


def handles(name: str) -> bool:
    return name in FUNCS


def ordinal(v) -> int | None:
    if v in (None, ""):
        return None
    s = str(v).strip().lower()
    if s.lstrip("-").isdigit():
        return int(s)
    return ORD.get(re.sub(r"(st|nd|rd|th)$", "", s) if s[:1].isdigit() else s)


def _e(v) -> str:
    return html.escape(str(v if v is not None else ""))


_GB_WORDS = {"input source": "source", "input sources": "source", "source": "source", "sources": "source", "channel": "source", "channels": "source",
             "origin": "source", "origins": "source", "department": "department", "departments": "department", "dept": "department",
             "district": "district", "districts": "district", "taluk": "taluk", "taluks": "taluk", "service": "service", "services": "service",
             "officer": "officer", "officers": "officer", "status": "status", "statuses": "status", "level": "level", "levels": "level",
             "gram panchayat": "gp", "gram panchayats": "gp", "gp": "gp", "gps": "gp", "month": "month", "months": "month", "day": "day", "days": "day"}
_GB_RX = re.compile(r"\b(?:according to|based on|as per|grouped by|split by|broken (?:down|up) by|sorted by|classified by|categori[sz]ed by|by|per)\s+"
                    r"(?:their|the|its|each|every)?\s*(?:specific |individual |respective |different |various )?"
                    r"(input sources?|sources?|channels?|origins?|departments?|dept|districts?|taluks?|services?|officers?|status(?:es)?|levels?|gram panchayats?|gps?|months?|days?)\b"
                    r"|\b(input sources?|sources?|channels?|departments?|districts?|taluks?|services?|officers?|levels?)[- ]wise\b"
                    r"|\bwhere (?:did |do |does |are |is )?(?:they|all )?(?:the |these |those )?(?:cases|grievances|complaints|requests)? ?(?:come|came|coming) from\b", re.I)


_FILTER_SAID_RX = re.compile(r"\b(auto[- ]?escalat\w*|escalat\w*|overdue|delayed|vulnerable|due (?:today|tomorrow|soon)|within \d+ days|\d+ days? (?:left|remaining)|"
                             r"resolved|rejected|scrutiny|re-?opened|appealed|at l[123]|level [123]|with l[123])\b", re.I)


def filter_said(said: str) -> bool:
    """The words carry a filter (escalated, overdue, vulnerable, due today, a level...): a slice, never the whole board."""
    return bool(_FILTER_SAID_RX.search(said or ""))


def filter_args_said(said: str, name: str) -> dict:
    """The filter the words asked for, as find_cases arguments ('auto-escalated' -> escalated=True), for the harness to add
    when the model passed none. ipgrs_records knows only status."""
    t = said or ""
    out = {}
    if re.search(r"\bescalat\w*", t, re.I) and name == "find_cases":
        out["escalated"] = True
    if re.search(r"\b(overdue|delayed|late)\b", t, re.I) and not re.search(r"\bnot (overdue|late)\b", t, re.I):
        out["status"] = "overdue"
    elif re.search(r"\b(resolved|solved|closed)\b", t, re.I):
        out["status"] = "resolved"
    elif re.search(r"\brejected\b", t, re.I):
        out["status"] = "rejected"
    elif re.search(r"\bscrutiny\b", t, re.I):
        out["status"] = "scrutiny"
    if name == "find_cases":
        if re.search(r"\bdue today\b", t, re.I):
            out["days_left"] = 0
        m = re.search(r"\b(?:at|with|in|on)\s+l([123])\b|\blevel\s+([123])\b", t, re.I)
        if m:
            out["level"] = "L" + (m.group(1) or m.group(2))
    return out


def group_by_said(said: str) -> str:
    """The breakdown the words asked for ('according to their input sources' -> source), or ''."""
    m = _GB_RX.search(said or "")
    if not m:
        return ""
    w = (m.group(1) or m.group(2) or "source").lower()
    return _GB_WORDS.get(w, _GB_WORDS.get(w.rstrip("s"), ""))


async def run(s: dict, name: str, args: dict) -> dict:
    said = str((args or {}).get("_text") or "")
    args = {k: v for k, v in (args or {}).items() if not k.startswith("_") and v not in (None, "")}
    from . import board
    st = s.get("state") if isinstance(s.get("state"), dict) else None
    if s.get("profile") in ("cs", "officer") and name == "place_info" and (board.COUNTQ_RX.search(said) or board.KN_COUNT_RX.search(said)) and args.get("place"):
        name, args = "find_cases", {"taluk": args["place"], "status": "overdue" if re.search(r"overdue|late|ವಿಳಂಬ", said, re.I) else "open"}   # a count is a picture
    dash_m = board.DASH_RX.search(said) or board.KN_DASH_RX.search(said)
    dash_how = bool(dash_m) and dash_m.group(0).lower().startswith("how")       # 'how is X doing' is always the board
    sliced = bool(group_by_said(said) or filter_said(said) or any(k in args for k in ("escalated", "status", "days_left", "level")))
    if s.get("profile") == "cs" and name in ("ipgrs_records", "find_cases", "officer_profile", "place_info", "statewide_stats") \
            and dash_m and not (board.COUNTQ_RX.search(said) or board.KN_COUNT_RX.search(said)) \
            and (dash_how or not sliced):                     # 'show me all the escalated / overdue / by-source cases' is a slice, not the board
        ent = {}                                          # 'how is X doing' is always the board, whichever function the model chose
        for k in ("department", "district", "taluk", "gp", "level"):
            if args.get(k):
                ent[k] = args[k]
        if name == "officer_profile" and args.get("officer"):
            ent["officer"] = args["officer"]
        if name == "place_info" and args.get("place"):
            ent["taluk"] = args["place"]
        rt = board.route(said, "cs", st)
        if rt and rt[0] == "dashboard":
            ent = {**rt[1], **ent} if not ent else ent
        name, args = "dashboard", ent
    wants_map = s.get("profile") == "cs" and (chart_kind(str(args.get("chart") or "")) == "map" or bool(board.MAP_RX.search(said)))
    if wants_map and (name in ("dashboard", "statewide_stats") or (name in ("find_cases", "ipgrs_records") and str(args.get("status") or "").lower() in ("", "open", "pending")
                                                                 and str(args.get("group_by") or "").lower() in ("", "district") and not args.get("level") and not args.get("days_left"))):
        name = "dashboard"                                # a map question: the big map + a small KPI column, not the six-card board
        args = {k: v for k, v in args.items() if k in ("department", "district", "taluk", "gp", "level", "officer")}
    if name == "find_cases" and (args.get("level") or str(args.get("group_by") or "").lower() == "level") and not args.get("status") \
            and not args.get("days_left") and "escalated" not in args:
        args["status"] = "open"                           # 'cases with L1' = cases sitting with L1 now
    if s.get("profile") == "cs" and board.CLEAR_RX.search(said):
        for k in ("department", "district", "taluk", "gp"):  # 'overall': drop what the model carried over from the screen
            if args.get(k) and str(args[k]).lower().split()[0] not in said.lower():
                args.pop(k, None)
    if s.get("profile") == "cs":
        args = board.scope_args(st, said, args, name)      # a follow-up stays inside the department / place on screen
    scoped = bool(args.pop("_scoped", False))
    if st is not None and name in ("dashboard", "find_cases", "ipgrs_records", "compare", "ranking", "officer_profile", "place_info", "statewide_stats"):
        st["scope_live"] = name == "dashboard" or scoped  # the next question may follow up only if this answer was inside the scope
    chart = chart_kind(args.pop("chart", "") or "")
    if not chart and re.search(r"\b(map|district[- ]?wise|across (the )?(state|karnataka)|which parts?|where (are|is) (the|most|all))\b", said, re.I):
        chart = "map"                             # the words asked for the map even if the model did not pass chart
    if name in ("ranking", "find_cases", "compare") and re.search(r"\bipgrs\b|\bsample week\b", said, re.I):
        by = args.get("group_by") or args.get("by") or "department"     # the iPGRS sample, not the live caseload
        args = {"group_by": "source" if by in ("channel",) else by, **{k: v for k, v in args.items() if k in ("district", "taluk", "department", "status")}}
        name = "ipgrs_records"
    if chart == "map" and name == "statewide_stats":       # "show me the grievances across the map": the per-district picture
        name, args = "find_cases", {"group_by": "district"}
    if chart == "map" and name in ("find_cases", "ipgrs_records") and not args.get("group_by"):
        args["group_by"] = "district"                # a map needs a number per district, not one total
    if chart == "map" and (name == "ranking" and (args.get("by") or "district") == "district" or args.get("group_by") == "district"):
        args["limit"] = 31                           # a map shows every district, not a top slice
    if s.get("profile") in ("cs", "officer") and name in ("find_cases", "ipgrs_records", "statewide_stats") and not args.get("group_by"):
        fa = filter_args_said(said, "find_cases" if name == "statewide_stats" else name)
        if fa and not any(k in args for k in ("escalated", "status", "days_left", "level")):
            if name == "statewide_stats":              # 'show me all the auto-escalated grievances' answered with the totals: the slice instead
                name, args = "find_cases", {}
            args.update(fa)                          # the words carried the filter the model dropped
    gb = group_by_said(said) if s.get("profile") in ("cs", "officer") else ""
    if gb and name in ("find_cases", "ipgrs_records", "statewide_stats") and str(args.get("group_by") or "").lower() != gb \
            and not (chart == "map" and gb == "district"):
        # the words asked for a breakdown ('according to their input sources'): that is the picture, whatever the model passed
        if name == "statewide_stats":
            name, args = "find_cases", {}
        args = {k: v for k, v in args.items() if k in ("district", "taluk", "department", "status", "level", "officer", "source", "kind", "escalated", "created_from", "created_to", "text", "viewer")}
        args["group_by"] = gb
        args["limit"] = 31 if gb == "district" else 12
        if chart == "map" and gb != "district":
            chart = "bars"                           # a map cannot show a breakdown by source / department / status
    tool = FUNCS[name][3]
    if s.get("profile") == "officer" and tool in ("case_info", "find_cases", "ipgrs_records"):
        args["viewer"] = s["officer"]                # guardrail 12: an officer reads only the cases on their own ladder
    r = await sakala._post("/api/query", {"tool": tool, "args": args})
    if r.get("http"):
        return {"say": "I could not read the Sakala data just now.", "ui": [], "data": r}
    if r.get("delegated") == "ipgrs_records":           # a department outside the pilot: answered from the iPGRS sample week
        name = "ipgrs_records"
    if name == "dashboard":
        say, ui = board.map_view(r) if wants_map and r.get("geo") else board.dashboard_view(r)
        sc = board.scope_from(r)
        if st is not None:
            st["scope"] = sc
            st["last_viz"] = __import__("time").time()
            try:
                from . import store
                store.save_session(s)
            except Exception:
                pass
        return {"say": say, "ui": ui + [board.scope_op(sc)], "data": _trim({k: v for k, v in r.items() if k not in ("geo",)})}
    say, ui = _speak(name, r, {**args, "chart": chart}, s)
    if name in ("find_cases", "ipgrs_records") and not r.get("groups") and s.get("profile") in ("cs", "officer"):
        g = board.context_group(args)                 # a single count is a picture too: tiles + the breakdown behind it
        ctx_args = {k: v for k, v in args.items() if k not in ("group_by", "limit", "sort", "viewer")}
        if name == "ipgrs_records":
            g = "level" if g == "days_left" else g
            g = "district" if g in ("taluk", "service") and not args.get("district") else ("taluk" if g == "service" else g)
        if g == "days_left":
            ctx_args.pop("days_left", None)
        if g == "level":
            ctx_args.pop("level", None)
        if s.get("profile") == "officer" and tool in ("find_cases", "ipgrs_records"):
            ctx_args["viewer"] = s["officer"]
        ctx = await sakala._post("/api/query", {"tool": "ipgrs_records" if name == "ipgrs_records" else tool, "args": {**ctx_args, "group_by": g}})
        if (not ctx.get("groups") or not sum(x["count"] for x in ctx["groups"])) and ctx_args.get("status"):
            ctx_args.pop("status", None)              # nothing matches (0 overdue): show the open picture behind it instead
            ctx = await sakala._post("/api/query", {"tool": "ipgrs_records" if name == "ipgrs_records" else tool, "args": {**ctx_args, "status": "open", "group_by": g}})
        cards = board.count_view(r, args, ctx if not ctx.get("http") else None)
        ui = [u for u in ui if u.get("op") != "viz"] + [{"op": "viz", "title": board._filters_text(args).capitalize(), "insight": say.split(". ")[0], "cards": cards}]
    if scoped and st and st.get("scope") and say:
        say = f"In {board.scope_op(st['scope'])['label']}: " + say
        ui = ui + [board.scope_op(st["scope"])]
    if any(op.get("op") == "viz" for op in ui) and isinstance(s.get("state"), dict):
        import time as _t
        s["state"]["last_viz"] = _t.time()
        try:
            from . import store
            store.save_session(s)
        except Exception:
            pass
    if chart:
        for op in ui:
            if op.get("op") == "viz":
                for c in op["cards"]:
                    if c["type"] not in ("kpi", "tiles"):
                        c["type"] = chart
    return {"say": say, "ui": ui, "data": _trim({k: v for k, v in r.items() if k != "geo"} if isinstance(r, dict) else r)}


CHART_WORDS = {"bar": "bars", "bars": "bars", "column": "bars", "line": "line", "trend": "line", "donut": "donut", "doughnut": "donut",
               "pie": "donut", "ring": "donut", "map": "map", "karnataka": "map", "geography": "map", "geographic": "map", "where": "map"}


def chart_kind(word: str) -> str:
    w = (word or "").lower()
    return next((CHART_WORDS[k] for k in CHART_WORDS if re.search(r"\b" + k, w)), "")


def _trim(r, depth=0):
    if isinstance(r, dict):
        return {k: _trim(v, depth + 1) for k, v in r.items()}
    if isinstance(r, list):
        return [_trim(x, depth + 1) for x in r[:40]]     # 31 districts must fit
    if isinstance(r, str) and len(r) > 400:
        return r[:400] + "…"
    return r


def _kv(title: str, rows: list[tuple[str, object]]) -> dict:
    body = "".join(f"<dt>{_e(k)}</dt><dd>{_e(v)}</dd>" for k, v in rows if v not in (None, "", []))
    return {"op": "answer", "q": title, "html": f"<div class='kv'>{body}</div>"}


METRIC_WORDS = {"open": "open", "overdue": "overdue", "resolved": "resolved", "rejected": "rejected", "vulnerable": "from vulnerable citizens",
                "escalated": "auto-escalated", "scrutiny": "at the scrutiny desk", "total": "in all", "due_soon": "due within two days"}


def _viz_card(title, items, metric, kind="bars", unit="cases", subtitle="", by=""):
    """One stage card. items: [{name, value, aliases, district}]. kind: bars (2-5 named things), race (ranked, >5), line, donut,
    kpi, map. `by` tells the client what the items are (district / taluk / ...), so it knows whether a map makes sense."""
    return {"type": kind, "title": title, "subtitle": subtitle, "metric": metric, "unit": unit, "by": by,
            "items": [{"label": it["name"], "value": it["value"], "aliases": it.get("aliases") or [], "district": it.get("district") or "",
                       "geo": it.get("geo") or {}} for it in items]}


def _say_compare(r: dict) -> tuple[str, list, str]:
    ents, metrics = r["entities"], r["metrics"]
    by = r["by"]
    cards, sents = [], []
    for m in metrics:
        items = [{"name": e["name"], "value": e["values"][m], "aliases": e["aliases"], "district": e.get("district", ""),
                  "geo": (e.get("geo") or {}).get(m) or {}} for e in ents]
        kind = "bars" if len(items) <= 5 else "race"
        cards.append(_viz_card(f"{METRIC_WORDS[m].capitalize()} cases", items, m, kind, subtitle=f"by {by}", by=by))
        parts = [f"{e['name']} {e['values'][m]}" for e in ents]
        sents.append(f"{METRIC_WORDS[m].capitalize()}: " + ", ".join(parts[:-1]) + (f" and {parts[-1]}" if len(parts) > 1 else parts[0]) + ".")
    m0 = metrics[0]
    top = max(ents, key=lambda e: e["values"][m0])
    tot = sum(e["values"][m0] for e in ents)
    insight = f"{top['name']} holds {round(100 * top['values'][m0] / tot)}% of the {METRIC_WORDS[m0]} cases among these" if tot and len(ents) > 1 else ""
    say = " ".join(sents)
    if insight:
        say += f" {insight}."
    if r.get("unmatched"):
        say += f" I could not match {', '.join(r['unmatched'])}."
    return say, cards, insight


def _speak(name: str, r: dict, args: dict, s: dict) -> tuple[str, list]:
    if name == "compare":
        if not r.get("found"):
            return f"I could not match {', '.join(r.get('asked') or [])} to any district, taluk, department or officer in Sakala.", []
        say, cards, insight = _say_compare(r)
        return say, [{"op": "viz", "cards": cards, "insight": insight, "title": f"Comparison by {r['by']}"}]
    if name == "ranking":
        ents, m = r["entities"], r["metric"]
        if not ents:
            return "Nothing to rank there.", []
        say = (f"By {METRIC_WORDS[m]} cases, the top {r['by']}s are " + ", ".join(f"{e['name']} with {e['values'][m]}" for e in ents[:4]) +
               f". {ents[0]['name']} leads, with {round(100 * ents[0]['values'][m] / max(1, r['total']))}% of the state's {r['total']}.")
        items = [{"name": e["name"], "value": e["values"][m], "aliases": e["aliases"], "district": e.get("district", ""),
                  "geo": (e.get("geo") or {}).get(m) or {}} for e in ents]
        card = _viz_card(f"{r['by'].capitalize()}s by {METRIC_WORDS[m]} cases", items, m, "race", subtitle=f"top {len(items)} of {r['distinct']}", by=r["by"])
        return say, [{"op": "viz", "cards": [card], "insight": f"{ents[0]['name']} leads with {ents[0]['values'][m]}", "title": f"Ranking by {r['by']}"}]
    if name == "lookup_case" and r.get("restricted"):
        return (f"{r.get('asked')} is not on your desk or your team's, so I can't open it"
                + (f"; it is with {r['holder']}." if r.get("holder") else ".") + " Ask me about the cases in your inbox.", [])
    if name == "lookup_case":
        if not r.get("found"):
            near = r.get("similar_ids") or []
            return (f"I could not find {r.get('asked')} in Sakala." + (f" Did you mean {', '.join(near)}?" if near else ""), [])
        lc, rec = r.get("live_case"), r.get("ipgrs_record")
        if lc:
            s["state"]["case_id"] = lc["id"]
            place = ", ".join(x for x in (lc.get("gp") and f"{lc['gp']} Gram Panchayat", lc.get("taluk") and f"{lc['taluk']} taluk", lc.get("district")) if x)
            say = (f"{lc['id']} is a {lc['service']} {lc['kind']} from {place}. It is {lc['status'].lower()} with {lc['officer']} at level "
                   f"{lc['level']}, {lc['time']}.")
            if rec:
                say += f" In iPGRS it came via {rec['source']} on {rec['created'][:10]}."
            ui = [{"op": "case", "case": {"id": lc["id"], "service": lc["service"], "dept": lc["department"], "grievance": lc.get("grievance"),
                                          "status": lc["status"], "owner": "", "ownerShort": lc["officer"], "level": lc["level"],
                                          "left": lc["days_left"] if lc["days_left"] is not None else 0, "legal": lc["kind"] == "application",
                                          "leftText": lc["time"], "vulnerable": lc["vulnerable"], "taluk": lc["taluk"], "gp": lc["gp"],
                                          "src": lc["source"], "masked": lc.get("complaint"), "history": [{"what": h["what"], "who": h["who"], "note": h["note"]} for h in lc.get("history", [])],
                                          "atr": lc.get("atr"), "atrScore": lc.get("atr_score")}}]
            return say, ui
        say = (f"G.Id {rec['gid']} is an iPGRS grievance to the {rec['department']}, {rec['service']}, from {rec['district']}"
               f"{', ' + rec['taluk'] if rec.get('taluk') else ''}. In iPGRS it is {rec['status_in_ipgrs']}, with {rec['pending_with_or_closed_by']}. "
               "It is outside the pilot's live caseload.")
        return say, [_kv(f"G.Id {rec['gid']}", [("Department", rec["department"]), ("Line department", rec["line_department"]), ("Service", rec["service"]),
                                                  ("Grievance", rec["grievance"]), ("Type", rec["service_type"]), ("Place", f"{rec['village'] or ''} {rec['gp'] or ''} {rec['taluk'] or ''} {rec['district']}".strip()),
                                                  ("Filed", rec["created"]), ("Via", rec["source"]), ("Status", rec["status_in_ipgrs"]),
                                                  ("With", rec["pending_with_or_closed_by"]), ("Complaint", rec["complaint"])])]
    if name in ("find_cases", "ipgrs_records"):
        what = "live cases" if name == "find_cases" else "iPGRS records from the sample week"
        if r.get("groups") and r.get("group_by") in ("days_left", "escalated"):
            g = r["groups"]
            if r["group_by"] == "days_left":
                nz = [x for x in g if x["count"]]
                say = f"Of the {r.get('of_open', 0):,} open cases: " + ", ".join(f"{x['count']:,} " + (x["name"].lower() if x["name"] in ("Overdue", "Due today") else "with " + x["name"].lower()) for x in nz[:6]) + "."
                items = [{"name": x["name"].replace(" left", ""), "value": x["count"], "aliases": [x["name"].lower()]} for x in g]
                card = _viz_card("Days left on the clock", items, "count", "bars", subtitle="open cases · 7-day timeline")
                ins = f"{g[0]['count']} overdue · {g[1]['count']} due today"
            else:
                say = f"Of the {r.get('of_open', 0):,} open cases, {g[0]['count']:,} have been escalated and {g[1]['count']:,} have not."
                items = [{"name": x["name"], "value": x["count"], "aliases": [x["name"].lower()]} for x in g]
                card = _viz_card("Escalated or not", items, "count", "donut", subtitle="open cases")
                ins = f"{g[0]['count']} escalated"
            return say, [{"op": "viz", "cards": [card], "insight": ins, "title": "The 7-day clock" if r["group_by"] == "days_left" else "Escalation"}]
        if r.get("groups"):
            g = r["groups"]
            top = ", ".join(f"{x['name']} {x['count']}" for x in g[:4])
            say = f"{r['total']} {what}, across {r.get('distinct', len(g))} {r['group_by']}s. Highest: {top}."
            if r["group_by"] == "level":
                for x in g:
                    x["name"] = {"LMF": "L1"}.get(x["name"], x["name"])
                say = "Open cases by level: " + ", ".join(f"{x['name']} {x['count']:,}" for x in sorted(g, key=lambda x: str(x['name']))) + "."
            kind = "bars" if r["group_by"] == "level" else "line" if r["group_by"] in ("day", "month") else ("donut" if r["group_by"] in ("department", "dept", "source", "channel", "status", "level") and len(g) <= 6 else ("bars" if len(g) <= 5 else "race"))
            items = [{"name": str(x["name"]), "value": x["count"], "aliases": [], "geo": (r.get("geo") or {}).get(x["name"]) or {}} for x in g]
            by = {"dept": "department", "channel": "source"}.get(r["group_by"], r["group_by"])
            if by == "district":
                for it in items:
                    it["district"] = it["name"]
            card = _viz_card(f"{what.capitalize()} by {r['group_by']}", items, "count", kind, subtitle="Sakala live caseload" if name == "find_cases" else "iPGRS sample week, 3-9 Oct 2026", by=by)
            return say, [{"op": "answer", "q": f"{what.capitalize()} by {r['group_by']}", "html": f"<p>{_e(say)}</p>"},
                         {"op": "viz", "cards": [card], "insight": f"{g[0]['name']} is the largest with {g[0]['count']}", "title": f"By {r['group_by']}"}]
        if name == "find_cases":
            rows = r.get("cases") or []
            s["state"]["list"] = [c["id"] for c in rows]
            say = f"{r['total']} matching cases: {r['open']} open, {r['overdue']} overdue, {r['resolved']} resolved."
            fa = args or {}
            if fa.get("days_left") is not None:
                n = int(fa["days_left"])
                say = f"{r['total']:,} open case{'s' if r['total'] != 1 else ''} " + ("are due today." if n == 0 else f"have {n} day{'s' if n != 1 else ''} left.")
            elif fa.get("level") and not fa.get("officer"):
                lv = str(fa["level"]).upper()
                say = f"{r['open']:,} open cases are with {lv}{' field officers' if lv == 'L1' else ' officers'}, {r['overdue']:,} of them overdue."
            elif fa.get("escalated") is True:
                say = f"{r['total']:,} cases have been escalated; {r['open']:,} of them are still open."
            elif fa.get("escalated") is False:
                say = f"{r['open']:,} open cases have never been escalated."
            if r.get("officer_matched"):
                say = f"For {r['officer_matched']}: " + say
            if rows:
                say += " The most urgent is " + f"{rows[0]['id']}, {rows[0]['service']} in {rows[0]['gp'] or rows[0]['taluk']}, {rows[0]['time']}."
            ui = [{"op": "filter", "category": "Search results", "total": r["total"],
                   "cases": [{"id": c["id"], "service": c["service"], "ownerShort": c["officer"], "gp": c["gp"], "taluk": c["taluk"], "level": c["level"],
                              "left": c["days_left"] if c["days_left"] is not None else 99, "leftText": c["time"], "vulnerable": c["vulnerable"]} for c in rows]}]
            return say, ui
        recs = r.get("records") or []
        say = f"{r['total']} of the 9,999 iPGRS records match" + (f", {r['open']} still in process." if r.get("open") is not None else ".")
        if r.get("department_short"):
            stw = (r.get("filters") or {}).get("status")
            say = (f"{r['department_short']} is outside the live pilot; in the real iPGRS records of the sample week it has "
                   + (f"{r['total']:,} grievances still in process." if stw == "open" else f"{r['total']:,} grievances, {r.get('open', 0):,} still in process."))
        if recs:
            say += f" The latest is G.Id {recs[0]['gid']}, {recs[0]['service']} in {recs[0]['district']}, {recs[0]['status']}."
        rows = "".join(f"<tr><td>{_e(x['gid'])}</td><td>{_e(x['department'])}</td><td>{_e(x['service'])}</td><td>{_e(x['district'])}</td><td>{_e(x['status'])}</td></tr>" for x in recs)
        return say, [{"op": "answer", "q": "iPGRS records", "html": f"<p>{_e(say)}</p><table class='tbl'><tr><th>G.Id</th><th>Department</th><th>Service</th><th>District</th><th>Status</th></tr>{rows}</table>"}]
    if name == "officer_profile":
        if not r.get("found"):
            return f"I could not find an officer called {r.get('asked')}.", []
        mu = r.get("most_urgent")
        say = (f"{r['officer']}, {r['department']}, level {r['level']}, reports to {', then '.join(r['reports_to']) or 'nobody above in the pilot'}. "
               f"{r['open']} open cases, {r['overdue']} overdue, {r['resolved']} resolved.")
        if mu:
            say += f" Most urgent: {mu['id']}, {mu['service']}, {mu['time']}."
        return say, [_kv(r["full_title"], [("Department", r["department"]), ("Level", r["level"]), ("Place", " · ".join(x for x in (r.get("gp"), r.get("taluk"), r.get("district")) if x)),
                                           ("Reports to", " → ".join(r["reports_to"])), ("Open", r["open"]), ("Overdue", r["overdue"]), ("Resolved", r["resolved"]),
                                           ("Vulnerable waiting", r["vulnerable_open"]), ("Most urgent", mu and f"{mu['id']} · {mu['service']} · {mu['time']}")])]
    if name == "place_info":
        if not r.get("found"):
            return f"I could not find a place called {r.get('asked')}.", []
        where = {"village": f"a village in {r['gp']} Gram Panchayat, {r['taluk']} taluk, {r['district']} district",
                 "gp": f"a Gram Panchayat in {r['taluk']} taluk, {r['district']} district", "taluk": f"a taluk in {r['district']} district",
                 "district": "a district"}[r["is_a"]]
        say = f"{r['name']} is {where}. {r['open']} open cases there, {r['overdue']} overdue, {r['live_cases']} in all."
        if r.get("officers_here"):
            say += f" Officers: {', '.join(o.split(' ', 1)[1] for o in r['officers_here'][:4])}."
        return say, [_kv(r["name"], [("Is", where), ("Officers", ", ".join(r["officers_here"])), ("Open", r["open"]), ("Overdue", r["overdue"]),
                                     ("All live cases", r["live_cases"]), ("Top services", ", ".join(f"{a} ({b})" for a, b in r["top_services"])),
                                     ("iPGRS sample records", r["ipgrs_records"])])]
    if name == "statewide_stats":
        say = (f"Across Karnataka, {r['open']} cases are open, {r['overdue']} overdue, {r['vulnerable_open']} from vulnerable citizens, "
               f"{r['auto_escalated']} auto-escalated and {r['at_scrutiny_desk']} at the scrutiny desk. {r['resolved']} resolved. "
               f"{r['filed_since_go_live']} filed since go-live.")
        dept = [{"name": a, "value": b, "aliases": []} for a, b in r["open_by_department"]]
        viz = {"op": "viz", "title": "Statewide position", "insight": f"{r['open']} open across {r['districts']} districts",
               "cards": [_viz_card("Open by department", dept, "open", "donut"),
                         _viz_card("Open by level", [{"name": a, "value": b, "aliases": ["field officer" if a == "L1" else "level " + a[-1]]} for a, b in r["open_by_level"]], "open", "bars")]}
        return say, [viz, _kv("Statewide position", [("Open", r["open"]), ("Overdue", r["overdue"]), ("Vulnerable", r["vulnerable_open"]),
                                                ("Auto-escalated", r["auto_escalated"]), ("Scrutiny desk", r["at_scrutiny_desk"]), ("Resolved", r["resolved"]),
                                                ("Open by level", ", ".join(f"{a} {b}" for a, b in r["open_by_level"])),
                                                ("Open by department", ", ".join(f"{a} {b}" for a, b in r["open_by_department"])),
                                                ("By channel", ", ".join(f"{a} {b}" for a, b in r["by_channel"])),
                                                ("Filed since go-live", r["filed_since_go_live"]), ("Districts", r["districts"])])]
    if name == "sakala_2025":
        st = r["state"]
        if r.get("district"):
            d = r["district"][0]
            say = (f"{d['district']} in Sakala 2025: {d['late_pct']} percent delivered late, {d['rej_pct']} percent rejected, "
                   f"{int(d['overdue_last'])} overdue in December, rank {int(d['rank_last'])} of 31. The state average is {st['late_pct']} percent late.")
        else:
            w, b = r["worst_by_late_delivery"][0], r["best_by_late_delivery"][-1]
            say = (f"In 2025 Sakala handled {round(st['receipts'] / 1e7, 1)} crore applications; {st['late_pct']} percent were late and "
                   f"{st['rej_pct']} percent rejected. Worst: {w['district']} at {w['late_pct']} percent. Best: {b['district']} at {b['late_pct']} percent. "
                   f"Overdue fell from {st['overdue_first']:,} in January to {st['overdue_last']:,} in December.")
        ui = [{"op": "answer", "q": "Sakala 2025", "html": f"<p>{_e(say)}</p>"}]
        cards = []
        if r.get("district"):
            d = r["district"][0]
            cards.append(_viz_card(f"{d['district']} · Sakala 2025", [{"name": "Late delivery", "value": d["late_pct"], "aliases": ["late"]},
                                                                      {"name": "Rejected", "value": d["rej_pct"], "aliases": ["reject"]},
                                                                      {"name": "State late", "value": st["late_pct"], "aliases": ["state", "average"]}], "pct", "bars", unit="%"))
        else:
            w = r["worst_by_late_delivery"] + r["best_by_late_delivery"]
            cards.append(_viz_card("Late delivery by district, 2025", [{"name": x["district"], "value": x["late_pct"], "aliases": [], "district": x["district"]} for x in w], "late_pct", "race", unit="%", subtitle="worst 5 and best 5 of 31", by="district"))
        if r.get("monthly_state"):
            mm = r["monthly_state"]
            names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
            cards.append(_viz_card("Overdue applications, month by month", [{"name": names[i][:3], "value": x["overdue"], "aliases": [names[i].lower()]} for i, x in enumerate(mm)], "overdue", "line", subtitle="Sakala 2025, statewide"))
        ui.append({"op": "viz", "cards": cards, "insight": f"Overdue fell {round(100 * (1 - st['overdue_last'] / max(1, st['overdue_first'])))}% over 2025", "title": "Sakala 2025"})
        return say, ui
    return "Done.", []
