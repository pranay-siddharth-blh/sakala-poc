"""The three real handwritten letters (Pranay's WhatsApp photos) through the document door, end to end on the live POC
(8020): read -> form -> understanding -> place -> officer preview. Prints the key fields, the retrieved iPGRS record and the
timing, and checks them against tools/tests/letters/expected.json when it exists.
Run from anywhere: PYTHONIOENCODING=utf-8 python tools/tests/doc_letters.py [--submit]"""
import base64
import glob
import json
import os
import sys
import time

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "letters")
POC = os.environ.get("POC", "http://localhost:8020")
EXP = json.load(open(os.path.join(DIR, "expected.json"), encoding="utf-8")) if os.path.exists(os.path.join(DIR, "expected.json")) else {}
KEYS = ["name", "phone", "letter_date", "grievance_id", "district", "taluk", "gp", "village", "subject", "language"]
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    ok += cond; fail += (not cond)
    print(("  ok   " if cond else "  FAIL ") + name + (f"  ({detail})" if detail and not cond else ""))


for f in sorted(glob.glob(DIR + "/*.jpeg") + glob.glob(DIR + "/*.pdf")):
    base = os.path.basename(f)
    print("==", base)
    b64 = base64.b64encode(open(f, "rb").read()).decode()
    t0 = time.time()
    r = httpx.post(POC + "/api/intake", json={"session": "letters-" + base[:2], "step": "document", "file_b64": b64, "filename": base,
                                              "media_type": "application/pdf" if base.endswith(".pdf") else "image/jpeg", "channel": "document", "defer_scrutiny": True}, timeout=180).json()
    dt = time.time() - t0
    if not r.get("ok"):
        print("  not ok:", r); fail += 1; continue
    fl = r["fields"]; u = r.get("u") or {}
    print(f"  {dt:5.1f} s wall ({r.get('ms', 0) / 1000:.1f} s read, look {(r.get('ms_look') or 0) / 1000:.1f} s) · rotation {r.get('rotation')} · {r.get('reader')} · flags {[x['field'] for x in r.get('flags', [])]}")
    print("  fields:", json.dumps({k: fl.get(k) for k in KEYS}, ensure_ascii=False))
    print("  intent:", u.get("intent"), "·", u.get("dept"), "›", u.get("service"), "·", round(float(u.get("conf") or 0) * 100), "% ·", r.get("engine"))
    rec = r.get("record")
    print("  record:", (f"{rec['gid']} · {rec['dept']} › {rec['service']} · {rec['district']}/{rec['taluk']}/{rec.get('gp')}" if rec else "none"))
    print("  place :", r.get("place") or ("taluk " + r["taluk"] if r.get("taluk") else "none"), "· officer:", ((r.get("preview") or {}).get("officer") or {}).get("name"))
    print("  english:", (r.get("english") or "")[:200].replace("\n", " "))
    e = EXP.get(base)
    if e:
        for k, v in e.get("fields", {}).items():
            got = (fl.get(k) or "")
            check(f"{k} = {v!r}", got.lower().strip() == str(v).lower().strip() or (k == "name" and str(v).lower().split()[0] in got.lower()), f"got {got!r}")
        if "record" in e:
            check(f"record {e['record']}", (rec or {}).get("gid") == e["record"], f"got {(rec or {}).get('gid')}")
        if "intent" in e:
            check(f"intent {e['intent']}", u.get("intent") == e["intent"], f"got {u.get('intent')}")
        if "service" in e:
            check(f"service {e['service']}", (u.get("service") or "") == e["service"], f"got {u.get('service')}")
        if "place_gp" in e:
            check(f"place gp {e['place_gp']}", ((r.get("place") or {}).get("gp") or "").lower() == e["place_gp"].lower(), f"got {(r.get('place') or {}).get('gp')}")
        if "taluk" in e:
            check(f"taluk {e['taluk']}", (((r.get("place") or {}).get("taluk") or r.get("taluk") or "")).lower() == e["taluk"].lower(), f"got {(r.get('place') or {}).get('taluk') or r.get('taluk')}")
        check("read under 15 s", dt < 15, f"{dt:.1f} s")
        check("no invented phone", not fl.get("phone") or fl["phone"] == e.get("fields", {}).get("phone", fl["phone"]))
    if "--submit" in sys.argv:
        fields = {k: fl.get(k) or "" for k in fl}
        doc = {**fields, "filename": base, "pages": r["pages"], "reader": r["reader"], "evidence": r["evidence"], "flags": r["flags"], "english": r["english"],
               "confidence": r["confidence"], "transcript": (r.get("transcript") or "")[:4000], "record": (rec or {}).get("gid")}
        if u.get("intent") == "GRIEVANCE" and r.get("place"):
            p = r["place"]
            res = httpx.post(POC + "/api/intake", json={"session": "letters-" + base[:2], "step": "create", "text": fl.get("description") or r["text"], "u": u, "taluk": p["taluk"], "gp": p.get("gp") or "",
                                                        "village": p.get("village") or "", "how": "read from the letter", "channel": "document", "doc": doc}, timeout=60).json()
            print("  filed:", res.get("id"), "→", (res.get("officer") or {}).get("name"), f"{res.get('days')} days")
            check("filed to an officer", bool(res.get("id")) and bool(res.get("officer")))
        else:
            res = httpx.post(POC + "/api/intake", json={"session": "letters-" + base[:2], "step": "scrutiny", "text": fl.get("description") or r["text"], "u": u, "taluk": fl.get("taluk") or "",
                                                        "channel": "document", "doc": doc}, timeout=60).json()
            cid = res.get("case_id")
            c = httpx.get(POC + f"/api/case/{cid}", timeout=30).json() if cid else {}
            print("  scrutiny:", cid, "→", c.get("owner_name") or c.get("owner"), "· doc stored:", bool(c.get("doc")))
            check("scrutiny case with the letter", bool(cid) and bool(c.get("doc")))
print(f"\n{ok} ok, {fail} failed")
sys.exit(1 if fail else 0)
