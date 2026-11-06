"""Runs the Sakala Mitra question bank (tests/question_bank.py) through the full pipeline (/api/turn: hearing skipped, brain,
tools, Sakala data) on a test instance, one fresh session per group, and writes a report per area and per paraphrase group.
Usage: python tests/run_bank.py [base] [--only 3,17] [--group cs-open-state] [--failed] [--workers 4]
Writes tests/bank_report.json and tests/BANK_REPORT.md."""
import argparse
import concurrent.futures as cf
import json
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import question_bank as QB  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("base", nargs="?", default="http://localhost:8031")
ap.add_argument("--only", default="")
ap.add_argument("--group", default="")
ap.add_argument("--failed", action="store_true")
ap.add_argument("--workers", type=int, default=4)
A = ap.parse_args()
REPORT = HERE / "bank_report.json"


def post(p, d):
    r = urllib.request.Request(A.base + p, json.dumps(d).encode(), {"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=180).read())


def fill(q):
    if "{CASE}" in q:
        q = q.replace("{CASE}", QB.case_id())
    if "{FOREIGN}" in q:
        q = q.replace("{FOREIGN}", QB.foreign())
    return q


def run_one(item):
    t0 = time.time()
    sid = post("/api/session", {"profile": item["profile"], "officer": item["officer"], "lang": "en"})["session"]
    q = fill(item["q"])
    try:
        r = post("/api/turn", {"session": sid, "text": q, "want_audio": False})
    except Exception as e:  # noqa: BLE001
        r = {"intent": "ERROR", "say": str(e), "ui": []}
    probs = []
    for chk in item["checks"]:
        try:
            ok, why = chk(r, {})
        except Exception as e:  # noqa: BLE001
            ok, why = False, f"check error {e}"
        if not ok:
            probs.append(why)
    if any(u.get("op") == "confirm" for u in r.get("ui", [])):
        post("/api/turn", {"session": sid, "text": "no", "want_audio": False})      # never leave an action waiting
    return {"id": item["id"], "group": item["group"], "area": item["area"], "profile": item["profile"], "q": q, "ok": not probs,
            "problems": probs, "intent": r.get("intent"), "say": (r.get("say") or "")[:300],
            "ops": [u.get("op") for u in r.get("ui", [])], "secs": round(time.time() - t0, 1)}


def main():
    items = QB.BANK
    prev = {}
    if REPORT.exists():
        prev = {x["id"]: x for x in json.loads(REPORT.read_text(encoding="utf-8")).get("results", [])}
    if A.only:
        ids = {int(x) for x in A.only.split(",") if x.strip()}
        items = [x for x in items if x["id"] in ids]
    if A.group:
        items = [x for x in items if x["group"] == A.group]
    if A.failed:
        items = [x for x in items if not prev.get(x["id"], {}).get("ok") or prev.get(x["id"], {}).get("q") != x["q"]]
    print(f"{len(items)} questions on {A.base}", flush=True)
    results = dict(prev)
    with cf.ThreadPoolExecutor(A.workers) as ex:
        for res in ex.map(run_one, items):
            results[res["id"]] = res
            print(f"  {'PASS' if res['ok'] else 'FAIL'} #{res['id']:>3} [{res['group']}] {res['q'][:60]!r} -> {res['intent']} ({res['secs']}s)"
                  + ("" if res["ok"] else f"  :: {res['problems'][0][:140]}"), flush=True)
    allr = [results[k] for k in sorted(results) if k <= len(QB.BANK)]
    byarea, bygroup = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for x in allr:
        byarea[x["area"]][0] += x["ok"]; byarea[x["area"]][1] += 1
        bygroup[x["group"]][0] += x["ok"]; bygroup[x["group"]][1] += 1
    passed = sum(x["ok"] for x in allr)
    REPORT.write_text(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M"), "passed": passed, "total": len(allr), "results": allr}, indent=1), encoding="utf-8")
    md = [f"# Sakala Mitra question bank — {passed}/{len(allr)} passed ({time.strftime('%d %b %Y %H:%M')})", "",
          "| Area | Passed |", "|---|---|"] + [f"| {a} | {p}/{t} |" for a, (p, t) in sorted(byarea.items())] + ["", "## Paraphrase groups", "",
          "| Group | Passed |", "|---|---|"] + [f"| {g} | {p}/{t} |" for g, (p, t) in sorted(bygroup.items())] + ["", "## Failures", ""] + \
         [f"- #{x['id']} [{x['group']}] “{x['q']}” → {x['intent']}: {'; '.join(x['problems'])[:200]}" for x in allr if not x["ok"]]
    (HERE / "BANK_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\n{passed}/{len(allr)} passed")


main()
