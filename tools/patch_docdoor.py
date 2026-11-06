"""The document door, POC side (19 Oct 2026): a written complaint (PDF / image) read into the official iPGRS form by
server/docread.py, then the SAME pipeline as every other door. Adds: /api/intake step=document, the `doc` column on cases
(extraction, complainant details, what was not provided), the event line, the officer's case JSON carrying it, and the
"use my location" rule for Mitra (any wording while Mitra asks for the place)."""
import io

ROOT = r"D:\Sakala POC"


def edit(path, pairs):
    p = ROOT + "\\" + path
    s = io.open(p, encoding="utf-8").read()
    for a, b in pairs:
        assert s.count(a) == 1, (path, a[:90], s.count(a))
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("patched", path)


edit(r"app\server\db.py", [
    ('''    if "audit" not in cols:
        c.execute("ALTER TABLE cases ADD COLUMN audit TEXT")''',
     '''    if "audit" not in cols:
        c.execute("ALTER TABLE cases ADD COLUMN audit TEXT")
    if "doc" not in cols:                                    # the document door: extraction + complainant details (JSON)
        c.execute("ALTER TABLE cases ADD COLUMN doc TEXT")'''),
])

edit(r"app\server\api.py", [
    ("from . import ai, analytics, chat, db, local_ai, sla", "from . import ai, analytics, chat, db, docread, local_ai, sla"),
    # the officer sees the letter's details on the case
    ('''            "sakala": sk, "history": events.get(c["id"], [])}


def all_cases(''',
     '''            "sakala": sk, "history": events.get(c["id"], []), "doc": json.loads(c["doc"]) if ("doc" in c.keys() and c["doc"]) else None}


def all_cases('''),
    ('''    defer_scrutiny: bool = False      # Mitra: report UNCLEAR without filing; it asks the citizen first
    answer: str = ""
    key: str = ""
    name: str = ""''',
     '''    defer_scrutiny: bool = False      # Mitra: report UNCLEAR without filing; it asks the citizen first
    answer: str = ""
    key: str = ""
    name: str = ""
    file_b64: str = ""                # the document door: a PDF / PNG / JPG of a written complaint
    filename: str = ""
    doc: dict | None = None           # the reviewed form (complainant details, not-provided fields, evidence) stored with the case'''),
    # step=document: read -> understand (same function) -> place (same resolver) -> the draft
    ('''    if s == "scrutiny":                    # the citizen agreed: send an unclear request to the human scrutiny desk''',
     '''    if s == "document":                    # the document door: a written complaint read into the form, then the same pipeline
        if not r.file_b64:
            raise HTTPException(400, "file_b64 needed")
        import base64 as _b64
        try:
            data = _b64.b64decode(r.file_b64)
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "bad file")
        if len(data) > 30 * 1024 * 1024:
            return {"step": s, "ok": False, "reason": "too_big"}
        rd = docread.read(data, r.media_type or "application/pdf", r.filename)
        if not rd.get("ok"):
            return {"step": s, "ok": False, "reason": rd.get("reason", "unreadable"), "detail": rd.get("detail", ""), "transcript": rd.get("transcript", "")}
        f = rd["fields"]
        text = (f.get("description") or rd["transcript"]).strip()
        masked, n, u = _pl.understand(rd["english"] if rd["english"] and rd["english"] != text else text)
        if rd["english"] and rd["english"] != text:
            masked, n = _pl.mask(text)[0], _pl.mask(text)[1]          # the case keeps the citizen's own words (masked)
        out = {"step": s, "ok": True, "text": text, "english": rd["english"], "masked": masked, "masked_items": n, "engine": _pl.engine_label(u),
               "u": {k: v for k, v in u.items() if k != "similar"}, "reader": rd["engine"], "pages": rd["pages"], "thumbs": rd["thumbs"],
               "fields": f, "confidence": rd["confidence"], "flags": rd["flags"], "evidence": rd["evidence"], "several": rd["several"],
               "missing": docread.missing(f), "filename": r.filename, "ms": rd["ms"],
               "form": {"steps": [{"id": st["id"], "title": st["title"], "fields": [{"key": x["key"], "label": x["label"], "required": x.get("required", False)} for x in st["fields"]]} for st in docread.FORM["steps"]]}}
        if u["intent"] == "GRIEVANCE":
            if rd.get("place"):
                out.update(_place_block(u, rd["place"]))
            else:
                out.update(_place_block(u, taluk=rd.get("taluk") or ""))
        return out
    if s == "scrutiny":                    # the citizen agreed: send an unclear request to the human scrutiny desk'''),
    # create: the reviewed form rides with the case
    ('''        res = _pl.create_grievance(r.text, masked, u, r.channel, r.taluk, r.gp, r.village, session=r.session,
                                   dup=dup["id"] if dup else None, how=r.how or "voice", place=place)
        return {"step": s, "ok": True, **res, "duplicate": dup["id"] if dup else None}''',
     '''        res = _pl.create_grievance(r.text, masked, u, r.channel, r.taluk, r.gp, r.village, session=r.session,
                                   dup=dup["id"] if dup else None, how=r.how or "voice", place=place)
        if r.doc and res.get("id"):                            # the document door: the reviewed form stays with the case
            d = dict(r.doc)
            d["not_provided"] = [k for k in ("name", "phone", "complainant_address", "pincode", "since", "letter_date") if not str(d.get(k) or "").strip()]
            db.run("UPDATE cases SET doc=? WHERE id=?", (json.dumps(d, ensure_ascii=False), res["id"]))
            event(res["id"], "Sakala AI", f"Written complaint read from {d.get('filename') or 'a document'}", "#6d4ce6",
                  f"{d.get('pages', 1)} page(s) · {d.get('reader') or 'document reader'} · complainant {d.get('name') or 'not given'}"
                  + (f" · {d['phone'][:2]}XXXXXX{d['phone'][-2:]}" if d.get("phone") else " · no phone given")
                  + (f" · not in the letter: {', '.join(d['not_provided'])}" if d["not_provided"] else ""))
        return {"step": s, "ok": True, **res, "duplicate": dup["id"] if dup else None}'''),
])

# ---------------------------------------------------------------- Mitra: "use my location" in any wording, any function the model picked
edit(r"mitra\server\tools.py", [
    ('''async def t_citizen_text(sess, args):
    text = (args.get("text") or "").strip()
    st = sess["state"]''',
     '''LOC_RX = re.compile(r"\\b(use|share|take|get|go ahead with|send)?\\s*(my|the|our)?\\s*(current\\s+)?(location|gps|where i am|where i'm)\\b|\\bmy location\\b", re.I)


async def t_citizen_text(sess, args):
    text = (args.get("text") or "").strip()
    st = sess["state"]
    if st.get("flow") in ("ask_place", "ask_gp", "apply_village") and LOC_RX.search(text) and (st.get("draft") or {}).get("u"):
        return await _run_option(sess, "loc:share")        # "you can go ahead and use my location": the location, whatever the model called it'''),
])
print("done")
