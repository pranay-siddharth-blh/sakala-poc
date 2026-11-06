"""Statewide data checks (15 Oct 2026): every district / taluk / officer in the sample is in the pipeline.
Run from app/ with the Sakala server up:  PYTHONIOENCODING=utf-8 python ../tools/tests/test_statewide.py"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))
B = "http://localhost:8020"
ok, T = 0, []


def check(n, c, d=""):
    global ok
    ok += bool(c)
    T.append(n)
    print(("  PASS " if c else "  FAIL ") + n + ("" if c else f"  <- {str(d)[:240]}"), flush=True)


def get(p):
    t = time.time()
    r = urllib.request.Request(B + p, headers={"Accept-Encoding": "identity"})
    raw = urllib.request.urlopen(r, timeout=300).read()
    return json.loads(raw), round(time.time() - t, 2), len(raw)


def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=300).read())


from server import db  # noqa: E402
from server.routing import route, resolve_place  # noqa: E402
from server.chat import taluk_in_text  # noqa: E402

print("[masters]")
b, t, n = get("/api/bootstrap")
m = b["masters"]
print(f"    bootstrap {t}s {n // 1000} KB ·", {k: m[k] for k in ("officers", "villages", "gps", "districts", "taluks", "services")})
check("31 districts in the gazetteer", m["districts"] == 31, m)
check("200+ taluks in the gazetteer", m["taluks"] >= 200, m["taluks"])
check("1,000+ Gram Panchayats", m["gps"] >= 1000, m["gps"])
check("2,000+ officers (one per role per taluk + a PDO per GP + district supervisors)", m["officers"] >= 2000, m["officers"])
for oid in ("tah_piriyapatna", "pdo_piriyapatna_attigodu", "ac_hunsur", "dc_mys", "eo_piriyapatna", "dd_food", "ddlr_mys", "ceo_zp"):
    check(f"Mysuru demo id {oid} unchanged", oid in b["officers"], oid)
offs = db.q("SELECT * FROM officers")
by_id = {o["id"]: o for o in offs}
bad = [o["id"] for o in offs if o["up_id"] and o["up_id"] not in by_id]
check("every officer's supervisor exists", not bad, bad[:5])
bad = []
for o in offs:
    seen, cur = set(), o
    while cur and cur["up_id"]:
        if cur["id"] in seen:
            bad.append(o["id"]); break
        seen.add(cur["id"]); cur = by_id.get(cur["up_id"])
    if not cur or cur["level"] != "L3":
        bad.append(o["id"])
check("every chain ends at an L3 head with no loops", not bad, bad[:5])
check("officers carry their district", all(o["district"] for o in offs), [o["id"] for o in offs if not o["district"]][:5])
seen_share = sum(1 for o in offs if o["seen_in_data"]) / len(offs)
print(f"    officers seen in the data: {seen_share:.0%}")

print("[cases statewide]")
st, t, n = get("/api/state?light=true")
cases = st["cases"]
dists = {c["district"] for c in cases}
print(f"    /api/state light {t}s {n // 1000} KB · {len(cases)} cases · {len(dists)} districts")
check("4,000+ live cases loaded", len(cases) >= 4000, len(cases))
check("cases in 25+ districts", len(dists) >= 25, sorted(dists))
check("Mysuru still has its 700+ real cases", sum(1 for c in cases if c["district"] == "Mysuru") >= 700, sum(1 for c in cases if c["district"] == "Mysuru"))
check("every case has an owner that exists", all(c["owner"] in by_id for c in cases), [c["id"] for c in cases if c["owner"] not in by_id][:5])
mism = [(c["id"], c["taluk"], by_id[c["owner"]]["taluk"]) for c in cases if by_id[c["owner"]]["taluk"] not in ("", c["taluk"])]
print(f"    cases whose iPGRS officer sits in another taluk (data as recorded): {len(mism)} of {len(cases)}")
check("owner's taluk matches the case taluk for ≥ 98% of cases", len(mism) <= 0.02 * len(cases), mism[:6])
full, t, n = get("/api/state")
print(f"    /api/state full {t}s {n // 1000} KB")
check("full state under 25 MB and 6 s", n < 25_000_000 and t < 6, (n, t))
ev = b["evals"]["routing"]
print(f"    routing agreement statewide: {ev['rate']:.1%} on {ev['n']} · pilot: {b['evals']['routing_pilot']['rate']:.1%} on {b['evals']['routing_pilot']['n']}")
check("statewide router agreement ≥ 90%", ev["rate"] >= 0.90, ev)
check("Mysuru pilot agreement still ≥ 95%", b["evals"]["routing_pilot"]["rate"] >= 0.95, b["evals"]["routing_pilot"])

print("[routing anywhere]")
svc = {s["name"]: s for s in db.q("SELECT * FROM services")}
for taluk, gp in (("Sagar", ""), ("Bilgi", ""), ("Bengaluru North", ""), ("Khanapur", "")):
    r = route(svc["RTC/Pahani"]["id"], taluk, gp)
    check(f"RTC/Pahani in {taluk} -> Tahsildar {taluk}", r and r["officer"] == f"tah_{taluk.lower().replace(' ', '_')}" and r["officer"] in by_id, r)
r = route(svc["Provision of Drinking Water"]["id"], "Sagar", "")
check("drinking water in Sagar -> AE RDWS Sagar", r and r["officer"] == "rdws_sagar" and r["officer"] in by_id, r)
gp = db.q1("SELECT gp FROM gazetteer WHERE taluk='Sagar' ORDER BY n_real DESC LIMIT 1")["gp"]
r = route(svc["Housing"]["id"], "Sagar", gp)
check(f"housing in {gp} GP, Sagar -> that GP's PDO", r and r["officer"].startswith("pdo_sagar_") and r["officer"] in by_id, r)
p = resolve_place("Holaluru")
check("a Shivamogga GP resolves through the gazetteer", p and p["taluk"] == "Shivamogga" and p["district"] == "Shivamogga", p)
check("taluk_in_text knows every taluk", taluk_in_text("road is bad in Jamkhandi") == "Jamkhandi" and taluk_in_text("no water in sagar town") == "Sagar" and taluk_in_text("Hunsur") == "Hunsur", (taluk_in_text("road is bad in Jamkhandi"), taluk_in_text("no water in sagar town")))

print("[intake from anywhere in the state]")
r = post("/api/intake", {"session": "sw1", "text": "no drinking water in Holaluru village for a week"})
check("Shivamogga village found from the text", r.get("place", {}).get("taluk") == "Shivamogga", r.get("place"))
if r.get("place"):
    c = post("/api/intake", {"session": "sw1", "step": "create", "text": r["text"], "u": r["u"], **{k: r["place"][k] for k in ("taluk", "gp", "village")}})
    check("routed to a Shivamogga officer", c.get("officer", {}).get("id", "").endswith("shivamogga") or by_id.get(c.get("officer", {}).get("id", ""), {}).get("district") == "Shivamogga", c.get("officer"))
    cj, _, _ = get(f"/api/case/{c['id']}")
    check("case carries district Shivamogga", cj["district"] == "Shivamogga", cj["district"])
r = post("/api/intake", {"session": "sw1", "text": "street light not working in Jamkhandi"})
check("taluk outside Mysuru -> its Gram Panchayat list, or the GP of that name", (r.get("need") == "gp" and r.get("taluk") == "Jamkhandi" and len(r.get("gp_options") or []) > 0) or (r.get("place") or {}).get("taluk") == "Jamkhandi", {k: r.get(k) for k in ("need", "taluk", "place")})
r = post("/api/intake", {"session": "sw1", "text": "street light not working, I am in Sorab taluk"})
check("'Sorab taluk' -> asks for its Gram Panchayat", r.get("need") == "gp" and r.get("taluk") == "Sorab" and len(r.get("gp_options") or []) > 0, {k: r.get(k) for k in ("need", "taluk", "place")})
r = post("/api/intake", {"session": "sw1", "text": "The street light is broken and nobody knows where"})
check("no place anywhere -> asks with the taluk list (200+)", r.get("need") == "place" and len(r.get("taluks") or []) >= 200, (r.get("need"), len(r.get("taluks") or [])))

print("[AI mode over the whole dataset]")
gid = db.q1("SELECT gid FROM ipgrs_records WHERE district='Bagalkote' AND dept_code='REV' LIMIT 1")["gid"]
a = post("/api/ask", {"q": f"tell me about grievance {gid}"})
check(f"'tell me about grievance {gid}' answered from the record", a.get("engine") == "ai" and gid in a.get("html", "") and "record" in (a.get("tools") or []), (a.get("engine"), a.get("tools"), a.get("html", "")[:160]))
a = post("/api/ask", {"q": "list the pending cases from the Revenue department in Bagalkote"})
check("'cases from Revenue in Bagalkote' lists cases", a.get("engine") == "ai" and ("GR-" in a.get("html", "") or "Bagalkot" in a.get("html", "")), a.get("html", "")[:200])
a = post("/api/ask", {"q": "how many grievances came from Shivamogga district by department"})
check("district question answered with a chart", a.get("engine") == "ai" and a.get("chart"), (a.get("engine"), bool(a.get("chart"))))
print(f"\n{ok}/{len(T)} statewide checks passed")
sys.exit(0 if ok == len(T) else 1)
