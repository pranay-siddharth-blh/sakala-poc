"""The words of a breakdown question decide the picture (26 Oct 2026): 'according to their specific input sources',
'based on department', 'source-wise', 'where did they come from' -> a group-by, on the rules router AND on whatever
function the live model chose. Pure Python against the POC on 8020. Run from mitra/: python tests/test_viz_route.py"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import query, tools  # noqa: E402

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:300])


async def main():
    await tools.boot()
    print("[route_question: the rules router]")
    for text, want in [
        ("show me all the grievances according to their specific input sources", ("find_cases", "source")),
        ("could you also show me all the grievances according to their input sources?", ("find_cases", "source")),
        ("break up the complaints based on department", ("find_cases", "department")),
        ("grievances source-wise please", ("find_cases", "source")),
        ("where did the grievances come from", ("find_cases", "source")),
        ("show me the cases as per their district", ("find_cases", "district")),
        ("split the open cases by taluk", ("find_cases", "taluk")),
    ]:
        rt = tools.route_question(text, "cs", {})
        check(f"{text!r} -> {want}", rt and rt[0] == want[0] and rt[1].get("group_by") == want[1], rt)
    rt = tools.route_question("show me all the grievances across Karnataka", "cs", {})
    check("'across Karnataka' stays the map (the board drawn as one big map, or the district map)", rt and (rt[0] == "dashboard" or (rt[0] == "find_cases" and rt[1].get("group_by") == "district")), rt)
    rt = tools.route_question("which district has the most open cases", "cs", {})
    check("a ranking question is still a ranking", rt and rt[0] == "ranking", rt)

    print("[group_by_said]")
    for text, want in [("according to their input sources", "source"), ("by their respective departments", "department"), ("per officer", "officer"),
                       ("district-wise", "district"), ("how many overdue cases are there", ""), ("show me the overdue cases", ""), ("sort them by status", "status")]:
        check(f"{text!r} -> {want!r}", query.group_by_said(text) == want, query.group_by_said(text))

    print("[query.run: the model chose find_cases with no group_by, the words asked for sources]")
    s = {"id": "t", "profile": "cs", "officer": "", "lang": "en", "state": {}}
    r = await query.run(s, "find_cases", {"status": "open", "_text": "show me all the grievances according to their specific input sources"})
    viz = [u for u in r.get("ui", []) if u.get("op") == "viz"]
    card = viz[-1]["cards"][0] if viz and viz[-1].get("cards") else {}
    labels = [i.get("label", "").lower() for i in card.get("items", [])]
    check("a viz by source came back", viz and card.get("by") == "source" or any(any(w in l for w in ("praja", "ipgrs", "mobile", "csc", "call", "camp", "web", "whatsapp", "mitra")) for l in labels), (card.get("by"), labels[:6]))
    r = await query.run(s, "statewide_stats", {"_text": "show me all the grievances according to their input sources"})
    viz = [u for u in r.get("ui", []) if u.get("op") == "viz"]
    card = viz[-1]["cards"][0] if viz and viz[-1].get("cards") else {}
    check("statewide_stats chosen by the model becomes the breakdown by source", card.get("by") == "source", (card.get("by"), card.get("title")))
    r = await query.run(s, "find_cases", {"group_by": "district", "chart": "map", "_text": "show me all the grievances across Karnataka"})
    viz = [u for u in r.get("ui", []) if u.get("op") == "viz"]
    check("the Karnataka map is untouched", viz and viz[-1].get("mapfocus"), [u.get("op") for u in r.get("ui", [])])
    r = await query.run(s, "statewide_stats", {"_text": "show me all the grievances that are there across the state of Karnataka"})
    viz = [u for u in r.get("ui", []) if u.get("op") == "viz"]
    check("the demo's first question (statewide_stats chosen) is still the one big map", viz and viz[-1].get("mapfocus"), [u.get("op") for u in r.get("ui", [])])

    print("[a filter in the words is a slice, never the whole board]")
    import re as _re
    for name, args in [("find_cases", {"escalated": True}), ("find_cases", {}), ("statewide_stats", {})]:
        r = await query.run(s, name, {**args, "_text": "show me all the grievances that are auto-escalated"})
        viz = [u for u in r.get("ui", []) if u.get("op") == "viz"]
        check(f"'auto-escalated' with the model choosing {name} {args} -> the escalated slice", viz and not viz[-1].get("board") and _re.match(r"^\d[\d,]* cases? ha(?:ve|s) been escalated", r.get("say", "")), (r.get("say", "")[:90], viz and viz[-1].get("title")))
    r = await query.run(s, "find_cases", {"_text": "show me all the overdue cases"})
    viz = [u for u in r.get("ui", []) if u.get("op") == "viz"]
    check("'show me all the overdue cases' -> the overdue slice", viz and not viz[-1].get("board") and "overdue" in r.get("say", "").lower(), (r.get("say", "")[:90], viz and viz[-1].get("title")))
    r = await query.run(s, "find_cases", {"_text": "how is Karnataka doing"})
    viz = [u for u in r.get("ui", []) if u.get("op") == "viz"]
    check("'how is Karnataka doing' is still the board", viz and viz[-1].get("board"), viz and viz[-1].get("title"))
    r = await query.run(s, "find_cases", {"_text": "show me everything"})
    viz = [u for u in r.get("ui", []) if u.get("op") == "viz"]
    check("'show me everything' is still the board", viz and viz[-1].get("board"), viz and viz[-1].get("title"))
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
