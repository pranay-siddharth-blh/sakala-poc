"""Fixes from the first live CS-bank run (22 Oct 2026), made on the server so they hold whatever the model picks:
- 'cases with L1' = open cases at that level (the model often omits the status); a level split counts open cases;
- 'how is X doing / everything about X / X's performance' always becomes the dashboard board, even if the model chose
  ipgrs_records, find_cases, officer_profile, place_info or statewide_stats;
- the scope carries only to an immediate follow-up (the previous data answer set or used it), not across unrelated questions."""
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


patch("mitra/server/query.py", [
    ('''    from . import board
    st = s.get("state") if isinstance(s.get("state"), dict) else None
    if s.get("profile") == "cs":
        args = board.scope_args(st, said, args, name)      # a follow-up stays inside the department / place on screen
    scoped = bool(args.pop("_scoped", False))''',
     '''    from . import board
    st = s.get("state") if isinstance(s.get("state"), dict) else None
    if s.get("profile") == "cs" and name in ("ipgrs_records", "find_cases", "officer_profile", "place_info", "statewide_stats") \\
            and board.DASH_RX.search(said) and not board.COUNTQ_RX.search(said):
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
    if name == "find_cases" and (args.get("level") or str(args.get("group_by") or "").lower() == "level") and not args.get("status") \\
            and not args.get("days_left") and "escalated" not in args:
        args["status"] = "open"                           # 'cases with L1' = cases sitting with L1 now
    if s.get("profile") == "cs":
        args = board.scope_args(st, said, args, name)      # a follow-up stays inside the department / place on screen
    scoped = bool(args.pop("_scoped", False))
    if st is not None and name in ("dashboard", "find_cases", "ipgrs_records", "compare", "ranking", "officer_profile", "place_info", "statewide_stats"):
        st["scope_live"] = name == "dashboard" or scoped  # the next question may follow up only if this answer was inside the scope'''),
])

patch("mitra/server/board.py", [
    ('''    sc = (state or {}).get("scope") or {}
    t = text or ""
    if CLEAR_RX.search(t):''',
     '''    sc = (state or {}).get("scope") or {}
    t = text or ""
    if sc and state is not None and state.get("scope_live") is False:
        sc = {}                                         # an unrelated question came in between: the scope has lapsed
    if CLEAR_RX.search(t):'''),
])

patch("mitra/tests/cs_live_bank.py", [
    ('''    qs = pick()
    half = len(qs) // 2
    print(f"[{len(qs)} questions, one per group, real live voice]")
    await LB.session("cs", qs[:half])
    await LB.session("cs", qs[half:])''',
     '''    qs = pick()
    print(f"[{len(qs)} questions, one per group, real live voice, a fresh session each (no scope carried)]")
    for i in range(0, len(qs), 1):
        await LB.session("cs", qs[i:i + 1])'''),
])
print("done")
