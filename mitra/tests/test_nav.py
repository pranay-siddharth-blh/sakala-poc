"""Navigation by voice: 'take me back to the dashboard' moves the screen (go_to) instead of charting the position; 'show me
the dashboard / position' still briefs; chart words still morph; the tool returns the right UI op for every target and
profile. Rules brain offline, then the cascade on a test instance.
Usage: python tests/test_nav.py [base]   (default http://localhost:8031)"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import brain  # noqa: E402

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8031"
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:300])


def rules(prof, text):
    return brain.rules({"profile": prof, "context": {}, "options": [], "history": []}, text)


r = rules("citizen", "take me to the chief secretary screen")
check("citizen: 'take me to the chief secretary screen' -> the CS profile", r["intent"] in ("go_to", "switch_profile") and (r.get("profile") == "cs" or r.get("target") == "chief secretary"), r)
print("[rules brain]")
for prof, text, want, target in [
    ("cs", "can you take me back to the dashboard", "go_to", "dashboard"),
    ("cs", "take me back to the dashboard", "go_to", "dashboard"),
    ("cs", "go back to the main screen", "go_to", "main screen"),
    ("cs", "okay close the chart", "go_to", "chart"),
    ("cs", "bring the chart back", "go_to", "chart"),
    ("cs", "take me to the officer screen", "go_to", "officer"),
    ("cs", "show me the dashboard", "summary", None),
    ("cs", "can you just show me the position", "summary", None),
    ("cs", "switch it to a donut graph", "show_chart_as", None),
    ("cs", "show it on the karnataka map", "show_chart_as", None),
    ("cs", "which district has the most open cases", "ask_data", None),
    ("officer", "go back to my inbox", "go_to", "inbox"),
    ("officer", "read my inbox", "inbox", None),
    ("citizen", "take me back to the main screen", "go_to", "main screen"),
]:
    r = rules(prof, text)
    same = want == "go_to" and target in ("officer", "citizen", "chief secretary", "cs") and r["intent"] == "switch_profile"   # same screen move
    check(f"{prof}: '{text}' -> {want}" + (f" ({target})" if target else ""), same or r["intent"] == want and (target is None or r.get("target") == target), r)


def post(p, d):
    req = urllib.request.Request(B + p, json.dumps(d).encode(), {"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


print("[cascade, CS]")
s = post("/api/session", {"profile": "cs"})
sid = s["session"]
r = post("/api/turn", {"session": sid, "text": "compare Piriyapatna, Hunsur and Mysuru"})
ops = [u["op"] for u in r.get("ui", [])]
check("comparison draws a chart", "viz" in ops, (r["intent"], ops))
r = post("/api/turn", {"session": sid, "text": "can you take me back to the dashboard"})
ops = [u["op"] for u in r.get("ui", [])]
check("'take me back to the dashboard' -> go_to: nav dashboard + the dashboard panels, no chart", r["intent"] == "go_to" and ops[:1] == ["nav"] and r["ui"][0]["target"] == "dashboard" and "kpi" in ops and "viz" not in ops and "dashboard" in r["say"].lower(), (r["intent"], ops, r["say"]))
r = post("/api/turn", {"session": sid, "text": "bring the chart back"})
check("'bring the chart back' -> nav chart", r["intent"] == "go_to" and r["ui"] and r["ui"][0] == {"op": "nav", "target": "chart"}, r.get("ui"))
r = post("/api/turn", {"session": sid, "text": "show me the dashboard"})
check("'show me the dashboard' still briefs (summary with a chart)", r["intent"] == "summary" and "pending" in r["say"], (r["intent"], r["say"][:100]))
r = post("/api/turn", {"session": sid, "text": "take me to the officer screen"})
ops = [u["op"] for u in r.get("ui", [])]
check("'take me to the officer screen' -> officer profile + inbox", r["intent"] == "go_to" and ops[:1] == ["profile"] and r["ui"][0]["profile"] == "officer" and "inbox" in ops, (r["intent"], ops))
r = post("/api/turn", {"session": sid, "text": "go back to my inbox"})
ops = [u["op"] for u in r.get("ui", [])]
check("officer: 'go back to my inbox' -> nav inbox + inbox", r["intent"] == "go_to" and ops[:2] == ["nav", "inbox"] and "open case" in r["say"], (r["intent"], ops, r["say"][:80]))
r = post("/api/turn", {"session": sid, "text": "take me back to the citizen screen"})
check("officer: 'take me back to the citizen screen' -> citizen profile", r["intent"] == "go_to" and r["ui"] and r["ui"][0].get("profile") == "citizen", r.get("ui", [])[:1])
print(f"\n{ok} passed, {fail} failed")
