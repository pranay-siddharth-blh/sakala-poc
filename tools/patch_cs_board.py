"""22 Oct 2026 (Pranay): the Chief Secretary's questions (levels, escalation, the 7-day clock, any department in the Excel,
dashboards, a conversational scope) wired into Mitra's query layer, the router, t_ask_data and the CS home panel."""
import ast
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BK = ROOT / "tools" / "backups" / "res22b"
BK.mkdir(parents=True, exist_ok=True)


def patch(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    shutil.copy(p, BK / (p.name + ".bak"))
    for old, new in pairs:
        assert old in s, f"{rel}: missing\n{old[:140]}"
        s = s.replace(old, new, 1)
    if rel.endswith(".py"):
        ast.parse(s)
    p.write_text(s, encoding="utf-8")
    print("patched", rel)


patch("mitra/server/query.py", [
    ('''    "kind": {"type": "STRING", "description": "grievance or application (Sakala service)"}, "escalated": B,''',
     '''    "kind": {"type": "STRING", "description": "grievance or application (Sakala service)"},
    "escalated": {"type": "BOOLEAN", "description": "true = escalated (auto-escalated, re-opened up the ladder or appealed); false = never escalated"},
    "days_left": {"type": "INTEGER", "description": "open cases with exactly this many days left on their deadline (0 = due today)"},'''),
    ('''    "group_by": {"type": "STRING", "description": "district, taluk, gp, department, service, officer, status, source, level, day, month"},
    "sort": {"type": "STRING", "description": "urgent (default), newest, oldest"}, "limit": I, "chart": CHART,
}''',
     '''    "group_by": {"type": "STRING", "description": "district, taluk, gp, department, service, officer, status, source, level, days_left (the 7-day clock: overdue, due today, 1..7 days left), escalated (escalated vs not), kind, vulnerable, day, month"},
    "sort": {"type": "STRING", "description": "urgent (default), newest, oldest"}, "limit": I, "chart": CHART,
}'''),
    ('''FUNCS = {
    "lookup_case":''',
     '''FUNCS = {
    "dashboard": ("The full dashboard of one thing, drawn as a board of cards: KPIs (open, overdue, escalated, due soon, at L1 / L2 / L3, "
                  "resolved), by level, the days-left clock, by place, the officers holding the most, top services. Use it for 'how is X doing', "
                  "'show me everything about X', 'X's position / performance / status', 'dashboard for X', where X is any department in "
                  "the Excel (RDPR, Revenue, Food, Urban Development, Education, Health, Energy, Police ...), a district, a taluk, a Gram "
                  "Panchayat, a level (L1, L2, L3), an officer or the whole state. Follow-ups ('and Hunsur?', 'only L2') stay inside "
                  "the last department / place unless she says overall or statewide.",
                  {"department": S, "district": S, "taluk": S, "gp": S, "level": {"type": "STRING", "description": "L1, L2 or L3"},
                   "officer": S, "service": S}, (), "dashboard"),
    "lookup_case":'''),
    ('''PROFILES = {"officer": set(FUNCS), "cs": set(FUNCS)}''',
     '''PROFILES = {"officer": set(FUNCS) - {"dashboard"}, "cs": set(FUNCS)}'''),
    ('''    said = str((args or {}).get("_text") or "")
    args = {k: v for k, v in (args or {}).items() if not k.startswith("_") and v not in (None, "")}''',
     '''    said = str((args or {}).get("_text") or "")
    args = {k: v for k, v in (args or {}).items() if not k.startswith("_") and v not in (None, "")}
    from . import board
    st = s.get("state") if isinstance(s.get("state"), dict) else None
    if s.get("profile") == "cs":
        args = board.scope_args(st, said, args, name)      # a follow-up stays inside the department / place on screen
    scoped = bool(args.pop("_scoped", False))'''),
    ('''    r = await sakala._post("/api/query", {"tool": tool, "args": args})
    if r.get("http"):
        return {"say": "I could not read the Sakala data just now.", "ui": [], "data": r}
    say, ui = _speak(name, r, {**args, "chart": chart}, s)''',
     '''    r = await sakala._post("/api/query", {"tool": tool, "args": args})
    if r.get("http"):
        return {"say": "I could not read the Sakala data just now.", "ui": [], "data": r}
    if r.get("delegated") == "ipgrs_records":           # a department outside the pilot: answered from the iPGRS sample week
        name = "ipgrs_records"
    if name == "dashboard":
        say, ui = board.dashboard_view(r)
        sc = board.scope_from(r)
        if st is not None:
            st["scope"] = sc
            st["last_viz"] = __import__("time").time()
            try:
                from . import store
                store.save_session(s)
            except Exception:
                pass
        if scoped and sc and say:
            say = f"Within {board.scope_op(sc)['label']}: " + say[0].lower() + say[1:]
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
        cards = board.count_view(r, args, ctx if not ctx.get("http") else None)
        ui = [u for u in ui if u.get("op") != "viz"] + [{"op": "viz", "title": board._filters_text(args).capitalize(), "insight": say.split(". ")[0], "cards": cards}]
    if scoped and st and st.get("scope") and say:
        say = f"Within {board.scope_op(st['scope'])['label']}: " + say[0].lower() + say[1:]
        ui = ui + [board.scope_op(st["scope"])]'''),
    ('''        if r.get("groups"):
            g = r["groups"]
            top = ", ".join(f"{x['name']} {x['count']}" for x in g[:4])
            say = f"{r['total']} {what}, across {r.get('distinct', len(g))} {r['group_by']}s. Highest: {top}."
            kind = "line" if r["group_by"] in ("day", "month") else''',
     '''        if r.get("groups") and r.get("group_by") in ("days_left", "escalated"):
            g = r["groups"]
            if r["group_by"] == "days_left":
                nz = [x for x in g if x["count"]]
                say = f"Of the {r.get('of_open', 0):,} open cases: " + ", ".join(f"{x['count']:,} {x['name'].lower()}" for x in nz[:6]) + "."
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
                say = "Open cases by level: " + ", ".join(f"{x['name']} {x['count']:,}" for x in sorted(g, key=lambda x: str(x['name']))) + "."
            kind = "bars" if r["group_by"] == "level" else "line" if r["group_by"] in ("day", "month") else'''),
    ('''            say = f"{r['total']} matching cases: {r['open']} open, {r['overdue']} overdue, {r['resolved']} resolved."''',
     '''            say = f"{r['total']} matching cases: {r['open']} open, {r['overdue']} overdue, {r['resolved']} resolved."
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
                say = f"{r['open']:,} open cases have never been escalated."'''),
    ('''        recs = r.get("records") or []
        say = f"{r['total']} of the 9,999 iPGRS records match."''',
     '''        recs = r.get("records") or []
        say = f"{r['total']} of the 9,999 iPGRS records match" + (f", {r['open']} still in process." if r.get("open") is not None else ".")
        if r.get("department_short"):
            say = (f"{r['department_short']} is outside the live pilot; in the real iPGRS records of the sample week it has {r['total']:,} grievances"
                   f" matching, {r.get('open', 0):,} still in process.")'''),
])

patch("mitra/server/tools.py", [
    ('''def route_question(text: str, profile: str):
    """(function, args) for a data question, or None. Functions: Mitra query functions, or 'inbox'."""
    t = (text or "").strip()
    if not t or profile not in ("cs", "officer") or _ACTION_RX.search(t):
        return None''',
     '''def route_question(text: str, profile: str, state: dict | None = None):
    """(function, args) for a data question, or None. Functions: Mitra query functions, or 'inbox'."""
    t = (text or "").strip()
    if not t or profile not in ("cs", "officer") or _ACTION_RX.search(t):
        return None
    from . import board
    b = board.route(t, profile, state)                 # dashboards, levels, escalation, the 7-day clock, any department
    if b:
        return b'''),
    ('''    rt = route_question(q or args.get("_text") or "", sess["profile"]) or route_question(args.get("_text") or "", sess["profile"])
    if rt:                                   # a data question with an exact SQL answer: comparison, ranking, count, officer, place
        if rt[0] == "inbox":
            return await t_inbox(sess, {})
        from . import query
        return await query.run(sess, rt[0], rt[1])''',
     '''    rt = route_question(args.get("_text") or q or "", sess["profile"], sess["state"]) or route_question(q or "", sess["profile"], sess["state"])
    if rt:                                   # a data question with an exact SQL answer: comparison, ranking, count, officer, place
        if rt[0] == "inbox":
            return await t_inbox(sess, {})
        from . import query
        return await query.run(sess, rt[0], {**rt[1], "_text": args.get("_text") or q})'''),
])
print("done")
