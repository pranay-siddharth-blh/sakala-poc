"""The Chief Secretary's question bank (22 Oct 2026): 110+ questions she will ask every day, in paraphrase groups, run through
the full pipeline (/api/turn on a test instance, or the real live voice with --live), each checked against numbers computed
here straight from app/data/sakala.db (independent SQL; the deadline clock uses the POC's own sla_info, which defines it).

Checks per question: the answer comes as a VISUAL (a viz op; a board of >= 4 cards for 'how is X doing'), the right number is
spoken, the scope chip says what the numbers are about (follow-ups stay inside it; 'overall' clears it), nothing crashes.
Usage (from mitra/): PYTHONIOENCODING=utf-8 python tests/cs_bank.py [--base URL] [--only GROUP] [--live] [--workers N]"""
import argparse
import concurrent.futures as cf
import json
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))
from server.sla import sla_info  # noqa: E402

DB = sqlite3.connect(f"file:{ROOT / 'app/data/sakala.db'}?mode=ro", uri=True)
DB.row_factory = sqlite3.Row
OPEN = ("Pending", "In progress", "Info requested")
ROWS = [dict(r) for r in DB.execute("SELECT * FROM cases")]
ESC = {r[0] for r in DB.execute("SELECT DISTINCT case_id FROM case_events WHERE what LIKE 'Auto-escalated%' OR what LIKE 'Re-opened by the citizen%' OR what LIKE 'Appealed%'")}
LEFT = {r["id"]: sla_info(r)["left"] for r in ROWS if r["status"] in OPEN}


def live(**f):
    """Open cases in the live caseload matching simple filters."""
    out = [r for r in ROWS if r["status"] in OPEN]
    for k, v in f.items():
        if k == "level":
            out = [r for r in out if r["level"] == v]
        elif k == "dept":
            out = [r for r in out if r["dept_code"] == v]
        elif k in ("taluk", "district"):
            out = [r for r in out if (r[k] or "").lower() == v.lower()]
        elif k == "overdue":
            out = [r for r in out if LEFT[r["id"]] < 0]
        elif k == "left":
            out = [r for r in out if LEFT[r["id"]] == v]
        elif k == "esc":
            out = [r for r in out if (r["id"] in ESC) == v]
        elif k == "owner":
            out = [r for r in out if r["owner"] == v]
    return len(out)


def esc_all():
    return sum(1 for r in ROWS if r["id"] in ESC)


def ipg(dept_like, status="InProcess", extra=""):
    q = "SELECT COUNT(*) FROM ipgrs_records WHERE dept LIKE ?" + (" AND status=?" if status else "") + extra
    return DB.execute(q, (dept_like,) + ((status,) if status else ())).fetchone()[0]


def ipg_total(dept_like):
    return DB.execute("SELECT COUNT(*) FROM ipgrs_records WHERE dept LIKE ?", (dept_like,)).fetchone()[0]


def n(v):
    return {f"{v:,}", str(v)}


# (group, question, checks) ; checks: num = expected number spoken; viz = min cards; board = a dashboard board;
# scope = scope label expected ('' = no scope / cleared); fn = a function the live run must call
BANK = []


def add(group, qs, **chk):
    for q in qs:
        BANK.append((group, q, chk))


# 1. levels
add("level-L1", ["How many cases are with L1?", "how many cases are pending with field officers", "what's the count at level one"], num=live(level="L1"), viz=2)
add("level-L2", ["How many cases are at L2?", "cases pending at the second level?", "number of cases with level 2 officers"], num=live(level="L2"), viz=2)
add("level-L3", ["How many are sitting with L3 officers?", "how many complaints are at the third level", "L3 pending count"], num=live(level="L3"), viz=2)
add("level-overdue", ["how many overdue cases are with L1"], num=live(level="L1", overdue=True), viz=2)
add("level-split", ["show me the level wise breakup", "show me cases by level", "how are cases spread across levels", "L1, L2 and L3 split"], num=live(level="L1"), viz=1)
# 2. escalation
add("escalated", ["How many cases have been escalated?", "how many have been escalated so far", "show me the escalated cases"], num=esc_all(), viz=2)
add("not-escalated", ["how many have not been escalated", "how many open cases were never escalated"], num=live(esc=False), viz=2)
add("escalation-split", ["escalated vs not escalated", "show me the escalation break up"], num=live(esc=True), viz=1)
# 3. the 7-day clock
for d, words in ((1, ["how many cases have 1 day left", "how many have one day left before the deadline"]),
                 (2, ["how many cases have two days left"]), (3, ["how many cases have 3 days left", "how many have three days remaining"]),
                 (5, ["how many cases have five days left"]), (7, ["how many cases have seven days left"])):
    add(f"days-{d}", words, num=live(left=d), viz=2)
add("due-today", ["how many cases are due today"], num=live(left=0), viz=2)
add("due-tomorrow", ["how many cases are due tomorrow"], num=live(left=1), viz=2)
add("timeline", ["show me the 7 day timeline", "what's the deadline distribution", "give me the days left breakup", "how close are cases to their deadlines"], num=live(left=3), viz=1)
# 4. places
for pl, kind in (("Alur", "taluk"), ("Hunsur", "taluk"), ("Piriyapatna", "taluk"), ("Sagar", "taluk"), ("Gadag", "taluk")):
    add(f"pending-{pl.lower()}", [f"How many pending cases are there in {pl}?", f"open cases in {pl} taluk"], num=live(**{kind: pl}), viz=2)
for pl in ("Mysuru", "Belagavi", "Shivamogga", "Hassan"):
    add(f"pending-{pl.lower()}-district", [f"how many pending cases in {pl} district"], num=live(district=pl), viz=2)
add("alias-mysore", ["how many pending cases in Mysore district"], num=live(district="Mysuru"), viz=2)
add("alias-bangalore", ["open cases in Bangalore district"], num=live(district="Bengaluru"), viz=2)
# 5. department dashboards (pilot = live; others = iPGRS sample week)
add("dash-rdpr", ["How is RDPR doing?", "show me everything about RDPR"], num=live(dept="RDPR"), board=True, scope="RDPR")
add("dash-revenue", ["How is the Revenue department doing?", "give me the dashboard for Revenue"], num=live(dept="REV"), board=True, scope="Revenue")
add("dash-food", ["how is Food and Civil Supplies performing?"], num=live(dept="FOOD"), board=True, scope="Food & Civil Supplies")
for word, like, short in (("Urban Development", "Urban Development%", "Urban Development"), ("Education", "Department of School Education%", "School Education"),
                          ("Health", "Health and Family%", "Health and Family Welfare"), ("the power department", "Energy%", "Energy"),
                          ("Police", "Home%", "Home"), ("Housing", "Housing%", "Housing"), ("Transport", "Transport%", "Transport"),
                          ("Agriculture", "Agriculture%", "Agriculture"), ("Women and Child Development", "Department of Women%", "Women & Child Development")):
    add(f"dash-{short.lower().replace(' ', '-')[:14]}", [f"How is {word} doing?"], num=ipg_total(like), board=True, scope=short)
# 6. department counts
add("count-health", ["how many open grievances in the health department"], num=ipg("Health and Family%"), viz=2)
add("count-urban", ["how many pending complaints in urban development"], num=ipg("Urban Development%"), viz=2)
add("count-police", ["how many complaints are pending in the police department"], num=ipg("Home%"), viz=2)
add("count-revenue", ["how many open cases in revenue"], num=live(dept="REV"), viz=2)
add("count-rdpr-overdue", ["how many overdue cases in RDPR"], num=live(dept="RDPR", overdue=True), viz=2)
# 7. place, level and officer dashboards
add("dash-hunsur", ["How is Hunsur doing?", "show me everything about Hunsur taluk"], num=live(taluk="Hunsur"), board=True, scope="Hunsur")
add("dash-mysuru", ["give me the dashboard for Mysuru district"], num=live(district="Mysuru"), board=True, scope="Mysuru")
add("dash-piriyapatna", ["how is Piriyapatna taluk doing"], num=live(taluk="Piriyapatna"), board=True, scope="Piriyapatna")
add("dash-belagavi", ["how is Belagavi district performing"], num=live(district="Belagavi"), board=True, scope="Belagavi")
add("dash-l2", ["How is L2 doing?", "dashboard for level two"], num=live(level="L2"), board=True, scope="L2")
add("dash-officer", ["How is the Tahsildar of Piriyapatna doing?"], num=live(owner="tahsildar_piriyapatna"), board=True)
add("dash-state", ["show me the overall dashboard statewide", "how is Karnataka doing overall"], num=len([r for r in ROWS if r["status"] in OPEN]), board=True, scope="")
# 8. comparisons / rankings (existing functions, still visual)
add("compare", ["compare Piriyapatna, Hunsur and Mysuru"], num=live(taluk="Piriyapatna"), viz=1)
add("ranking", ["which district has the most open cases?"], viz=1)
# 9. edge cases: never a crash, never an invented number
add("edge", ["how is xyzzy doing", "how many cases have 10 days left", "how many cases are with L4", "how is the moon department doing"], ok=True)
SEQ = [  # scoped follow-ups: one session, in order
    ("How is RDPR doing?", dict(num=live(dept="RDPR"), board=True, scope="RDPR")),
    ("and Hunsur?", dict(num=sum(1 for r in ROWS if r["status"] in OPEN and r["dept_code"] == "RDPR" and r["taluk"] == "Hunsur"), board=True, scope="RDPR › Hunsur")),
    ("how many with L1 there", dict(num=sum(1 for r in ROWS if r["status"] in OPEN and r["dept_code"] == "RDPR" and r["taluk"] == "Hunsur" and r["level"] == "L1"), viz=2, scope="RDPR › Hunsur")),
    ("what about Piriyapatna", dict(num=sum(1 for r in ROWS if r["status"] in OPEN and r["dept_code"] == "RDPR" and r["taluk"] == "Piriyapatna"), board=True, scope="RDPR › Piriyapatna")),
    ("overall, how many cases are with L1?", dict(num=live(level="L1"), viz=2, scope="")),
    ("How is Education doing?", dict(num=ipg_total("Department of School Education%"), board=True, scope="School Education")),
    ("and in Mysuru?", dict(num=DB.execute("SELECT COUNT(*) FROM ipgrs_records WHERE dept LIKE 'Department of School Education%' AND lower(district)='mysuru'").fetchone()[0], viz=3, scope="School Education › Mysuru")),
]
KN = [("ಹುಣಸೂರು ತಾಲ್ಲೂಕಿನಲ್ಲಿ ಎಷ್ಟು ಕೇಸ್ ಬಾಕಿ ಇದೆ?", dict(num=live(taluk="Hunsur"), viz=1)),
      ("RDPR ಹೇಗಿದೆ?", dict(num=live(dept="RDPR"), viz=1))]


def post(base, p, d):
    r = urllib.request.Request(base + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=180).read())


def judge(q, chk, r):
    say = r.get("say") or ""
    ui = r.get("ui") or []
    viz = [u for u in ui if u.get("op") == "viz"]
    sc = [u for u in ui if u.get("op") == "scope"]
    bad = []
    if not say:
        bad.append("no answer")
    drawn = {int(round(float(it.get("value") or 0))) for v in viz for c in v.get("cards") or [] for it in c.get("items") or [] if str(it.get("value") or "0").replace(".", "", 1).isdigit()}
    if "num" in chk and not any(x in re.sub(r"(?<=\d),(?=\d{3})", ",", say) for x in n(chk["num"])) and chk["num"] not in drawn:
        bad.append(f"expected {chk['num']} in the answer")
    if chk.get("viz") and (not viz or len(viz[-1]["cards"]) < chk["viz"]):
        bad.append(f"expected a visual with >= {chk['viz']} cards, got {[len(v['cards']) for v in viz]}")
    if chk.get("board") and (not viz or len(viz[-1]["cards"]) < 4):
        bad.append(f"expected a dashboard board, got {[len(v['cards']) for v in viz]}")
    if "scope" in chk and chk["scope"] is not None:
        lab = sc[-1]["label"] if sc else ""
        if chk["scope"] and chk["scope"] not in lab:
            bad.append(f"scope '{lab}' should contain '{chk['scope']}'")
        if chk["scope"] == "" and lab:
            bad.append(f"scope should be cleared, got '{lab}'")
    if re.search(r"could not read the Sakala data|traceback|error", say, re.I):
        bad.append("error in the answer")
    return bad


def run_one(base, group, q, chk, sid=None, lang="en"):
    sid = sid or post(base, "/api/session", {"profile": "cs", "lang": lang})["session"]
    t = time.time()
    try:
        r = post(base, "/api/turn", {"session": sid, "text": q, "want_audio": False})
    except Exception as e:  # noqa: BLE001
        return group, q, ["http " + str(e)[:80]], 0, {}
    return group, q, judge(q, chk, r), time.time() - t, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8031")
    ap.add_argument("--only", default="")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    bank = [b for b in BANK if not a.only or a.only in b[0]]
    res = []
    with cf.ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(lambda b: run_one(a.base, *b), bank))
    if not a.only or a.only in "seq":
        sid = post(a.base, "/api/session", {"profile": "cs", "lang": "en"})["session"]
        for q, chk in SEQ:
            res.append(run_one(a.base, "seq-scope", q, chk, sid))
    if not a.only or a.only in "kannada":
        for q, chk in KN:
            res.append(run_one(a.base, "kannada", q, chk, None, "kn"))
    ok = 0
    for g, q, bad, dt, r in res:
        ok += not bad
        print(f"  {'PASS' if not bad else 'FAIL'} [{g}] {q!r} ({dt:.1f}s){'' if not bad else '  <- ' + '; '.join(bad) + ' :: ' + (r.get('say') or '')[:140]}")
    print(f"\n{ok}/{len(res)} passed")
    Path(__file__).with_name("cs_bank_report.json").write_text(json.dumps([{"group": g, "q": q, "bad": b, "secs": round(d, 1), "say": (r.get("say") or "")[:300]} for g, q, b, d, r in res], ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(0 if ok == len(res) else 1)


if __name__ == "__main__":
    main()
