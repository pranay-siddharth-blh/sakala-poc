"""The document door (19 Oct 2026): a written complaint -> the official form -> the same pipeline. Against the POC on 8020 and Mitra's
test instance on 8031 (fallback brain). Also the "use my location" rule.
1. a typed English+Kannada letter: every field read, place resolved to Attigodu GP, the PDO previewed;
2. filed with the form: src=document, the doc on the case (phone, name, not-provided list), the event in the file;
3. the sample handwritten letter (Telugu script!): read, not guessed into a pilot category, English rendering present;
4. a letter without the place: missing list, no place, nothing filed;
5. "school children" in a street-light letter is still a street light (keyword rule no longer overrides a pilot service);
6. Mitra: "you can go ahead and use my location" while asked for the place -> the demo GPS point (Chapparadahalli GP).
Run from app/: PYTHONIOENCODING=utf-8 python ../tools/tests/test_docdoor.py"""
import base64
import json
import pathlib
import urllib.request

B = "http://localhost:8020"
M = "http://localhost:8031"
HERE = pathlib.Path(__file__).resolve().parent
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:400])


def post(base, p, b, timeout=240):
    return json.loads(urllib.request.urlopen(urllib.request.Request(base + p, json.dumps(b).encode(), {"Content-Type": "application/json"}), timeout=timeout).read())


def get(p):
    return json.loads(urllib.request.urlopen(B + p, timeout=60).read())


def b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()


print("[1. typed letter, English + Kannada]")
r = post(B, "/api/intake", {"session": "doc-t1", "step": "document", "file_b64": b64(HERE / "letter_typed.pdf"), "media_type": "application/pdf", "filename": "letter_typed.pdf", "channel": "document"})
f = r.get("fields") or {}
check("read", r.get("ok") and r.get("pages") == 1 and r.get("thumbs"), r.get("reason"))
check("every field read exactly", f.get("name") == "Ramesh Gowda" and f.get("phone") == "9876543210" and f.get("pincode") == "571107" and f.get("letter_date") == "2026-10-12" and f.get("village", "").lower() == "attigodu" and "bus stand" in f.get("address", "").lower(), {k: f.get(k) for k in ("name", "phone", "pincode", "letter_date", "village", "address")})
check("the Kannada line kept (description and transcript)", "ಬೀದಿ ದೀಪ" in f.get("description", "") and "ಬೀದಿ ದೀಪ" in (r.get("transcript") or ""), f.get("description", "")[-80:])
check("understood as a street light (not 'school')", (r.get("u") or {}).get("intent") == "GRIEVANCE" and "street light" in (r["u"].get("service") or "").lower(), r.get("u"))
check("place resolved to Attigodu GP, PDO previewed", (r.get("place") or {}).get("gp") == "Attigodu" and ((r.get("preview") or {}).get("officer") or {}).get("id") == "pdo_piriyapatna_attigodu", (r.get("place"), r.get("preview")))
check("nothing missing, no flags", not r.get("missing") and not r.get("flags"), (r.get("missing"), r.get("flags")))

print("[2. filed with the form]")
c = post(B, "/api/intake", {"session": "doc-t1", "step": "create", "text": r["text"], "u": r["u"], "taluk": r["place"]["taluk"], "gp": r["place"]["gp"], "village": r["place"]["village"], "how": "read from the letter", "channel": "document",
                           "doc": {**f, "filename": "letter_typed.pdf", "pages": 1, "reader": r.get("reader")}})
cid = c.get("id")
check("filed to PDO Attigodu", cid and (c.get("officer") or {}).get("id") == "pdo_piriyapatna_attigodu", c)
cj = get(f"/api/case/{cid}")
check("src=document, the doc with the complainant on the case", cj["src"] == "document" and (cj.get("doc") or {}).get("phone") == "9876543210" and cj["doc"].get("name") == "Ramesh Gowda" and cj["doc"].get("not_provided") == [], cj.get("doc"))
check("the letter is in the case file", any("Written complaint read" in h["what"] for h in cj["history"]) and any(h["what"].startswith("Routed to") for h in cj["history"]), [h["what"] for h in cj["history"]])
check("the phone is masked in the event, not shown", all("9876543210" not in (h.get("note") or "") for h in cj["history"]), [h.get("note") for h in cj["history"]])

print("[3. the sample handwritten letter]")
r3 = post(B, "/api/intake", {"session": "doc-t3", "step": "document", "file_b64": b64(HERE.parent.parent / "docs/ipgrs_form/sample_handwritten_letter.png"), "media_type": "image/png", "filename": "letter.png", "channel": "document"})
f3 = r3.get("fields") or {}
check("handwritten letter read: date and village found", r3.get("ok") and f3.get("letter_date") == "2019-12-21" and f3.get("village"), {k: f3.get(k) for k in ("letter_date", "village", "language")})
check("an English rendering is given for a non-Latin letter", r3.get("english") and r3["english"] != f3.get("description") and "bor" in r3["english"].lower(), (r3.get("english") or "")[:160])
check("no phone / name invented", not f3.get("phone") and "phone" in (r3.get("missing") or []), (f3.get("phone"), r3.get("missing")))

print("[4. a letter without the place]")
import pymupdf
d = pymupdf.open(); pg = d.new_page()
for i, l in enumerate(["To the Tahsildar. My RTC Pahani has a wrong survey number since 2024 and I need it corrected.",
                       "I have visited the office three times. Please correct the record. Thank you."]):
    pg.insert_text((50, 80 + i * 22), l, fontsize=11, fontname="helv")
p4 = HERE / "letter_noplace.pdf"; d.save(p4)
r4 = post(B, "/api/intake", {"session": "doc-t4", "step": "document", "file_b64": b64(p4), "media_type": "application/pdf", "filename": "letter_noplace.pdf", "channel": "document"})
check("read, no place, name and phone missing, nothing filed", r4.get("ok") and not r4.get("place") and {"name", "phone"} <= set(r4.get("missing") or []) and r4.get("need") in ("place", "gp", None) and not get("/api/state?session=doc-t4&scope=citizen")["cases"], (r4.get("missing"), r4.get("need"), r4.get("place")))

print("[5. keyword rule: a pilot service wins over 'school'/'bus' words]")
u5 = post(B, "/api/intake", {"session": "doc-t5", "step": "understand", "text": "the street light near the bus stand is not working and school children find it dark at night", "channel": "mitra"})
check("street light, not Education or Transport", (u5.get("u") or {}).get("intent") == "GRIEVANCE" and "street light" in (u5["u"].get("service") or "").lower(), u5.get("u"))

print("[6. Mitra: 'use my location' in any wording]")
s = post(M, "/api/session", {"profile": "citizen", "officer": "", "lang": "en"})["session"]
r = post(M, "/api/turn", {"session": s, "text": "the street light near the temple is not working"}, timeout=120)
check("asks for the place", "village" in (r.get("say") or "").lower() or "taluk" in (r.get("say") or "").lower(), r.get("say"))
r = post(M, "/api/turn", {"session": s, "text": "You can go ahead and use my location."}, timeout=120)
check("'you can go ahead and use my location' -> the demo location (Chapparadahalli GP)", "chapparadahalli" in (r.get("say") or "").lower() and "could not find" not in (r.get("say") or "").lower(), r.get("say"))

print(f"\n{ok} passed, {fail} failed")
