"""The document door, Mitra side (19 Oct 2026): upload a written complaint (PDF / photo, Kannada / English / mixed) -> the POC
reads it into the official iPGRS form (server/docread.py) -> the same understand / place / confirm / create path as a spoken
request. The form is reviewed on screen (every field editable, "not in the letter" accepted), then ONE Submit (or "submit" /
"file it" by voice). Voice edits while the form is open: "the phone number is …", "my name is …", "the village is …"."""
import io
import re

ROOT = r"D:\Sakala POC"


def edit(path, pairs):
    p = ROOT + "\\" + path
    s = io.open(p, encoding="utf-8").read()
    for a, b in pairs:
        assert s.count(a) == 1, (path, a[:90], s.count(a))
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("patched", path)


edit(r"mitra\server\tools.py", [
    # the draft card carries the document review
    ('''    card = {"op": "request", "draft": {k: d.get(k) for k in ("text", "masked", "service", "dept", "grievance", "conf", "vulnerable", "place", "preview", "duplicate", "engine", "why")},''',
     '''    card = {"op": "request", "draft": {k: d.get(k) for k in ("text", "masked", "service", "dept", "grievance", "conf", "vulnerable", "place", "preview", "duplicate", "engine", "why", "doc")},'''),
    # stage 0 names the door
    ('''    stages = [stage(0, "Photo of the petition read by Sakala Mitra" if via == "photo" else "Spoken request received by Sakala Mitra"),''',
     '''    stages = [stage(0, "Photo of the petition read by Sakala Mitra" if via == "photo" else
                    (f"Written complaint read · {r.get('pages', 1)} page(s) · {r.get('filename') or 'document'}" if via == "document" else "Spoken request received by Sakala Mitra")),'''),
    # the document review keeps its own options: Submit / Change
    ('''        st["flow"] = "confirm"
        _set_options(sess, [["Yes, file it", "confirm"], ["Change", "change"]])
        pv = r.get("preview") or {}
        who = (pv.get("officer") or {}).get("name")
        say += f" The location is {where}."''',
     '''        st["flow"] = "confirm"
        _set_options(sess, [["Submit", "confirm"], ["Change", "change"]] if d.get("doc") else [["Yes, file it", "confirm"], ["Change", "change"]])
        pv = r.get("preview") or {}
        who = (pv.get("officer") or {}).get("name")
        say += f" The location is {where}."'''),
    # the reviewed form rides with the case
    ('''    r = await intake(sess, step="create", text=d["text"], u=d["u"], taluk=p["taluk"], gp=p.get("gp") or "", village=p.get("village") or "", how=p.get("how") or "voice")
    st["flow"] = "done"; st["draft"] = {}; _set_options(sess, [["Track my request", "track"], ["Raise another", "change"]])''',
     '''    doc = None
    if d.get("doc"):
        dd = d["doc"]
        doc = {**(dd.get("fields") or {}), "filename": dd.get("filename"), "pages": dd.get("pages"), "reader": dd.get("reader"),
               "evidence": dd.get("evidence"), "flags": dd.get("flags"), "english": dd.get("english"), "confidence": dd.get("confidence")}
    r = await intake(sess, step="create", text=d["text"], u=d["u"], taluk=p["taluk"], gp=p.get("gp") or "", village=p.get("village") or "",
                     how=p.get("how") or ("document" if doc else "voice"), doc=doc, channel="document" if doc else "mitra")
    st["flow"] = "done"; st["draft"] = {}; _set_options(sess, [["Track my request", "track"], ["Raise another", "change"]])'''),
    # the document tool itself, after the photo tool
    ('''async def t_citizen_option(sess, args):''',
     '''async def t_citizen_document(sess, file_b64: str, media_type: str = "application/pdf", filename: str = "") -> dict:
    """A written complaint uploaded as a file: read into the official form by the POC, then the same path as a spoken request."""
    st = sess["state"]
    r = await intake(sess, step="document", file_b64=file_b64, media_type=media_type, filename=filename, defer_scrutiny=True)
    if not r.get("ok"):
        why = {"unreadable": "I could not read a complaint in that file, so I will not guess.", "too_big": "That file is larger than 30 MB.",
               "no_reader": "The document reader is not reachable right now.", "empty": "That file is empty."}.get(r.get("reason"), "I could not read that file.")
        return {"say": why + " You can tell me the problem in a sentence instead.", "ui": [{"op": "stages", "items": [stage(0, "Document received · not readable", "warn")]}]}
    doc = {"filename": r.get("filename") or filename, "pages": r.get("pages"), "reader": r.get("reader"), "thumbs": r.get("thumbs") or [],
           "fields": r.get("fields") or {}, "confidence": r.get("confidence") or {}, "flags": r.get("flags") or [], "evidence": r.get("evidence") or {},
           "missing": r.get("missing") or [], "english": r.get("english") or "", "transcript": (r.get("transcript") or "")[:4000],
           "form": r.get("form"), "several": bool(r.get("several")), "ms": r.get("ms")}
    res = await _after_understand(sess, r, "document")
    if st.get("draft") is not None:
        st["draft"]["doc"] = doc
        if st.get("flow") == "confirm":
            _set_options(sess, [["Submit", "confirm"], ["Change", "change"]])
    f = doc["fields"]
    lead = f"I read the letter, {doc['pages']} page{'s' if (doc['pages'] or 1) != 1 else ''}"
    if f.get("name"):
        lead += f", from {f['name']}"
    if f.get("letter_date"):
        lead += f", dated {f['letter_date']}"
    lead += ". "
    gaps = [{"phone": "a phone number", "name": "the complainant's name", "address": "the exact place"}.get(k, k) for k in doc["missing"] if k in ("phone", "name", "address")]
    tail = ""
    if gaps and st.get("flow") == "confirm":
        tail = f" The letter does not give {' or '.join(gaps)}; add it on the form if you have it, or just say submit."
    elif st.get("flow") == "confirm":
        tail = " Check the form and say submit, or change anything."
    res["say"] = lead + (res.get("say") or "").replace("Shall I file it?", "").strip() + tail
    res["ui"] = _draft_ui(sess, [s for s in (res.get("ui") or [{}])[0].get("items", [])] if (res.get("ui") or [{}])[0].get("op") == "stages" else []) if st.get("draft") else res.get("ui", [])
    return res


NA_RX = re.compile(r"^\\s*(na|n/?a|nil|none|not available|not provided|-+|skip|no)\\s*$", re.I)


def _doc_edits(sess: dict, text: str) -> str:
    """Voice edits to the open document form: 'the phone number is 98…', 'my name is …'. Returns what was changed ('' = nothing)."""
    d = (sess["state"].get("draft") or {}); doc = d.get("doc")
    if not doc:
        return ""
    f = doc.setdefault("fields", {})
    low = text.lower()
    m = re.search(r"(\\+?91[\\s-]?)?([6-9]\\d{9})\\b", re.sub(r"[\\s-]", "", text))
    if m and re.search(r"phone|mobile|number|contact|call", low):
        f["phone"] = m.group(2); return "phone number"
    m = re.search(r"\\b(?:my name is|the name is|name is|complainant is|i am|i'm)\\s+([A-Z][\\w.]+(?:\\s+[A-Z][\\w.]+){0,3})", text)
    if m:
        f["name"] = m.group(1).strip(" ."); return "name"
    if re.search(r"\\b(no phone|no number|phone (is )?not (there|given|available)|skip the phone)\\b", low):
        f["phone"] = ""; return "phone (not provided)"
    return ""


async def t_citizen_option(sess, args):'''),
    # voice edits while the form is open (confirm flow with a document): before the option matching
    ('''    if flow in ("ask_place", "ask_gp", "confirm"):
        # an option label said aloud
        for lab, action in st.get("options") or []:''',
     '''    if flow == "confirm" and (st.get("draft") or {}).get("doc"):
        changed = _doc_edits(sess, text)
        if changed:
            return {"say": f"Updated the {changed}. Say submit when the form is right.", "ui": _draft_ui(sess, [stage(4, "Form updated · waiting for submit", "run")])}
        if re.search(r"\\b(village|gram panchayat|panchayat|taluk|place|location) (is|in)\\b|\\bit('s| is) in\\b", text.lower()):
            r = await intake(sess, step="place", text=re.sub(r"^.*?\\b(?:is|in)\\s+", "", text, count=1, flags=re.I), u=d["u"] if (d := st.get("draft")) and d.get("u") else {})
            if r.get("place") or r.get("need") == "gp":
                return await _apply_place(sess, r, [stage(3, "Location changed on the form", "run")], "Location updated.")
    if flow in ("ask_place", "ask_gp", "confirm"):
        # an option label said aloud
        for lab, action in st.get("options") or []:'''),
])

edit(r"mitra\server\main.py", [
    ('''@app.post("/api/photo")''',
     '''class DocReq(BaseModel):
    session: str
    file_b64: str
    media_type: str = "application/pdf"
    filename: str = ""


class DocSubmit(BaseModel):
    session: str
    fields: dict = {}


@app.post("/api/document")
async def document(req: DocReq):
    """The document door: a written complaint (PDF / photo) read into the official form, then the usual pipeline."""
    s = store.get_session(req.session)
    if not s:
        raise HTTPException(404, "unknown session")
    await tools.boot()
    res = await tools.t_citizen_document(s, req.file_b64, req.media_type, req.filename)
    store.save_session(s)
    say = res.get("say") or ""
    store.log_turn(s["id"], "user", f"(document: {guard.mask(req.filename or 'file')})", "document")
    store.log_turn(s["id"], "mitra", guard.mask(say), "document")
    return await _with_voice(s, say, res.get("ui", []), intent="document")


@app.post("/api/document/submit")
async def document_submit(req: DocSubmit):
    """Submit the reviewed form (typed edits applied; NA / empty accepted), then the same create step as 'yes, file it'."""
    s = store.get_session(req.session)
    if not s:
        raise HTTPException(404, "unknown session")
    await tools.boot()
    st = s["state"]; d = st.get("draft") or {}
    if not d.get("doc"):
        raise HTTPException(409, "no document form is open")
    f = d["doc"].setdefault("fields", {})
    for k, v in (req.fields or {}).items():
        v = "" if tools.NA_RX.match(str(v or "")) else str(v or "").strip()
        f[k] = v
    # a changed place is resolved again through the shared completion step
    p = d.get("place") or {}
    want = (req.fields or {}).get("gp") or (req.fields or {}).get("village") or ""
    if want and want.lower() not in ((p.get("gp") or "").lower(), (p.get("village") or "").lower()):
        r = await tools.intake(s, step="place", text=want, u=d.get("u") or {}, taluk=(req.fields or {}).get("taluk") or "")
        if r.get("place"):
            d["place"] = r["place"]; d["preview"] = r.get("preview"); d["duplicate"] = r.get("duplicate")
        elif r.get("need") == "gp":
            res = await tools._apply_place(s, r, [tools.stage(3, "Location changed on the form", "run")], "Which Gram Panchayat?")
            store.save_session(s)
            return await _with_voice(s, res.get("say") or "", res.get("ui", []), intent="document")
    if not d.get("place"):
        res = {"say": "I still need the place: which village, Gram Panchayat or taluk is this in?", "ui": tools._draft_ui(s, [tools.stage(3, "Asking for the place", "run")])}
    else:
        st["flow"] = "confirm"
        res = await tools.execute(s, "confirm", {"_text": "submit", "_confirmed": True})
    store.save_session(s)
    say = res.get("say") or ""
    store.log_turn(s["id"], "user", "(form submitted)", "confirm")
    store.log_turn(s["id"], "mitra", guard.mask(say), res.get("intent", "confirm"))
    return await _with_voice(s, say, res.get("ui", []), intent=res.get("intent", "confirm"))


@app.post("/api/photo")'''),
])

edit(r"mitra\server\live.py", [
    ('''"feedback_no (the case re-opens and moves one rung up to the senior officer with a fresh clock; say so).")''',
     '''"feedback_no (the case re-opens and moves one rung up to the senior officer with a fresh clock; say so). "
                     "If they said to use their location (\\"use my location\\", \\"go ahead with my location\\", \\"GPS\\") while you are asking "
                     "where the problem is -> chat_option with option 'Share location', never chat_text. A written complaint they "
                     "uploaded shows as a form on screen: 'submit' / 'file it' -> confirm; 'the phone number is …' / 'my name is …' / "
                     "'the village is …' -> chat_text with those words.")'''),
])
print("done")
