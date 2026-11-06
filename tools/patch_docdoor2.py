"""Document door v2 (21 Oct 2026): the letter's own iPGRS number retrieved from the real records and shown on the form, letters
outside the pilot / unclear keep the form and go to the scrutiny desk WITH the letter on Submit, the photo is turned upright,
the reads run in parallel. Applies to Mitra (tools.py, main.py, mitra.js, mitra.css) and the POC (docupload.js)."""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BK = ROOT / "tools" / "backups" / "res21"
BK.mkdir(parents=True, exist_ok=True)


def patch(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    shutil.copy(p, BK / (p.name + ".bak"))
    for old, new in pairs:
        assert old in s, f"{rel}: missing\n{old[:120]}"
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("patched", rel)


# ---------------------------------------------------------------- Mitra tools.py
patch("mitra/server/tools.py", [
    ('''           "missing": r.get("missing") or [], "english": r.get("english") or "", "transcript": (r.get("transcript") or "")[:4000],
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
    res["say"] = lead + (res.get("say") or "").replace("Shall I file it?", "").strip() + tail''',
     '''           "missing": r.get("missing") or [], "english": r.get("english") or "", "transcript": (r.get("transcript") or "")[:4000],
           "form": r.get("form"), "several": bool(r.get("several")), "ms": r.get("ms"), "record": r.get("record"),
           "rotation": r.get("rotation") or 0, "language": r.get("language") or ""}
    res = await _after_understand(sess, r, "document")
    u = r.get("u") or {}
    if u.get("intent") in ("OUT_OF_SCOPE", "UNCLEAR"):
        # a letter is never dropped: the form stays, Submit sends it with the letter to the scrutiny desk (a person routes it)
        st["flow"] = "scrutiny_confirm"
        st["draft"] = {"text": r.get("text") or "", "masked": r.get("masked"), "u": u, "scrutiny": True, "engine": r.get("engine"), "why": u.get("reason"),
                       "service": "To be decided by the scrutiny desk", "dept": (u.get("dept") + " · outside the pilot") if u.get("intent") == "OUT_OF_SCOPE" and u.get("dept") else "Unclear category",
                       "taluk_hint": (doc["fields"].get("taluk") or "")}
        _set_options(sess, [["Submit", "confirm"], ["Change", "change"]])
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
    if doc.get("record"):
        rec = doc["record"]
        lead += f"It quotes iPGRS grievance {rec.get('gid')}, which is in the records: {rec.get('service')}, {rec.get('taluk')} taluk. "
    gaps = [{"phone": "a phone number", "name": "the complainant's name", "address": "the exact place"}.get(k, k) for k in doc["missing"] if k in ("phone", "name", "address")]
    tail = ""
    if gaps and st.get("flow") == "confirm":
        tail = f" The letter does not give {' or '.join(gaps)}; add it on the form if you have it, or just say submit."
    elif st.get("flow") == "confirm":
        tail = " Check the form and say submit, or change anything."
    elif st.get("flow") == "scrutiny_confirm":
        body = (f"This is a matter for the {u.get('dept')}, outside the three pilot departments. " if u.get("intent") == "OUT_OF_SCOPE" and u.get("dept")
                else "No official category matches it with certainty. ")
        res["say"] = body + "Check the form and say submit: it goes with the letter to the scrutiny desk, where a person routes it to the right officer."
    res["say"] = lead + (res.get("say") or "").replace("Shall I file it?", "").strip() + tail'''),
    ('''    if flow == "scrutiny_confirm" and d.get("scrutiny"):
        r = await intake(sess, step="scrutiny", text=d["text"], u=d.get("u") or {})
        cid = r.get("case_id") or ""''',
     '''    if flow == "scrutiny_confirm" and d.get("scrutiny"):
        doc = None
        if d.get("doc"):
            dd = d["doc"]
            doc = {**(dd.get("fields") or {}), "filename": dd.get("filename"), "pages": dd.get("pages"), "reader": dd.get("reader"),
                   "evidence": dd.get("evidence"), "flags": dd.get("flags"), "english": dd.get("english"), "confidence": dd.get("confidence"),
                   "transcript": (dd.get("transcript") or "")[:4000], "record": (dd.get("record") or {}).get("gid")}
        tk = chat_taluk(d.get("taluk_hint") or "") if d.get("taluk_hint") else ""
        r = await intake(sess, step="scrutiny", text=d["text"], u=d.get("u") or {}, doc=doc, taluk=tk, channel="document" if doc else "mitra")
        cid = r.get("case_id") or ""'''),
    ('''        doc = {**(dd.get("fields") or {}), "filename": dd.get("filename"), "pages": dd.get("pages"), "reader": dd.get("reader"),
               "evidence": dd.get("evidence"), "flags": dd.get("flags"), "english": dd.get("english"), "confidence": dd.get("confidence"),
               "transcript": (dd.get("transcript") or "")[:4000]}
    r = await intake(sess, step="create",''',
     '''        doc = {**(dd.get("fields") or {}), "filename": dd.get("filename"), "pages": dd.get("pages"), "reader": dd.get("reader"),
               "evidence": dd.get("evidence"), "flags": dd.get("flags"), "english": dd.get("english"), "confidence": dd.get("confidence"),
               "transcript": (dd.get("transcript") or "")[:4000], "record": (dd.get("record") or {}).get("gid")}
    r = await intake(sess, step="create",'''),
    ('''NA_RX = re.compile(''',
     '''def chat_taluk(text: str) -> str:
    """The taluk named on a letter, through the POC's own taluk reader (every statewide taluk, Kannada too)."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))
        from server import chat as _chat  # noqa: WPS433
        return _chat.taluk_in_text(text) or ""
    except Exception:  # noqa: BLE001
        return ""


NA_RX = re.compile('''),
])

# the stage line for a scrutiny-bound letter in _draft_ui is fine as is; make sure Path is imported in tools.py
s = (ROOT / "mitra/server/tools.py").read_text(encoding="utf-8")
if "from pathlib import Path" not in s:
    s = s.replace("import re\n", "import re\nfrom pathlib import Path\n", 1)
    (ROOT / "mitra/server/tools.py").write_text(s, encoding="utf-8")

# ---------------------------------------------------------------- Mitra main.py: submit of a scrutiny-bound letter needs no place
patch("mitra/server/main.py", [
    ('''    if not d.get("place"):
        res = {"say": "I still need the place: which village, Gram Panchayat or taluk is this in?", "ui": tools._draft_ui(s, [tools.stage(3, "Asking for the place", "run")])}
    else:
        st["flow"] = "confirm"
        res = await tools.execute(s, "confirm", {"_text": "submit", "_confirmed": True})''',
     '''    if d.get("scrutiny"):
        st["flow"] = "scrutiny_confirm"
        res = await tools.execute(s, "confirm", {"_text": "submit", "_confirmed": True})
    elif not d.get("place"):
        res = {"say": "I still need the place: which village, Gram Panchayat or taluk is this in?", "ui": tools._draft_ui(s, [tools.stage(3, "Asking for the place", "run")])}
    else:
        st["flow"] = "confirm"
        res = await tools.execute(s, "confirm", {"_text": "submit", "_confirmed": True})'''),
    ('''    p = d.get("place") or {}
    want = (req.fields or {}).get("gp") or (req.fields or {}).get("village") or ""
    if want and want.lower() not in ((p.get("gp") or "").lower(), (p.get("village") or "").lower()):''',
     '''    p = d.get("place") or {}
    want = (req.fields or {}).get("gp") or (req.fields or {}).get("village") or ""
    if d.get("scrutiny"):
        d["taluk_hint"] = (req.fields or {}).get("taluk") or d.get("taluk_hint") or ""
        want = ""
    if want and want.lower() not in ((p.get("gp") or "").lower(), (p.get("village") or "").lower()):'''),
])

# ---------------------------------------------------------------- Mitra UI
patch("mitra/web/mitra.js", [
    ("""  { title: '3 · Complainant', keys: [['name', 'Name'], ['phone', 'Mobile number'], ['complainant_address', 'Address'], ['letter_date', 'Date of the letter'], ['addressed_to', 'Addressed to'], ['asked_for', 'What is asked for']] },""",
     """  { title: '3 · Complainant', keys: [['name', 'Name'], ['phone', 'Mobile number'], ['complainant_address', 'Address'], ['letter_date', 'Date of the letter'], ['addressed_to', 'Addressed to'], ['asked_for', 'What is asked for'], ['grievance_id', 'iPGRS number quoted in the letter']] },"""),
    ("""  const head = `<div class="dhead"><div class="dthumbs">${thumbs}</div><div class="dmeta"><b>${esc(doc.filename || 'Written complaint')}</b><span>${doc.pages || 1} page${(doc.pages || 1) > 1 ? 's' : ''} · read by Sakala AI${doc.ms ? ' in ' + (doc.ms / 1000).toFixed(0) + ' s' : ''}</span>${doc.several ? '<span class="pill warn">The letter seems to hold more than one complaint</span>' : ''}""",
     """  const rec = doc.record;
  const recRow = rec ? `<div class="drec"><i>⌘</i><div><b>Matches iPGRS record ${esc(rec.gid)}</b><span>${esc(rec.service || rec.grievance || '')} · ${esc([rec.gp, rec.taluk, rec.district].filter(Boolean).join(', '))} · filed ${esc((rec.created || '').slice(0, 10))} via ${esc(rec.source || 'iPGRS')} · ${esc(rec.status || '')}</span></div></div>` : '';
  const head = `<div class="dhead"><div class="dthumbs">${thumbs}</div><div class="dmeta"><b>${esc(doc.filename || 'Written complaint')}</b><span>${doc.pages || 1} page${(doc.pages || 1) > 1 ? 's' : ''} · read by Sakala AI${doc.ms ? ' in ' + (doc.ms / 1000).toFixed(0) + ' s' : ''}${doc.rotation ? ' · photo turned upright' : ''}${doc.language ? ' · ' + esc({ kn: 'Kannada', en: 'English', mixed: 'Kannada + English', te: 'Telugu', hi: 'Hindi', ta: 'Tamil' }[doc.language] || doc.language) : ''}</span>${doc.several ? '<span class="pill warn">The letter seems to hold more than one complaint</span>' : ''}${recRow}"""),
    ("""  const bar = flow === 'confirm' ? `<div class="dsubmit"><button class="dgo" id="docSubmit"><span>Submit</span><small>files it to ${o ? esc(o.short) : 'the officer'}</small></button><button class="dchg" id="docChange">Change</button></div>`
    : `<div class="dnote">""",
     """  const bar = flow === 'confirm' ? `<div class="dsubmit"><button class="dgo" id="docSubmit"><span>Submit</span><small>files it to ${o ? esc(o.short) : 'the officer'}</small></button><button class="dchg" id="docChange">Change</button></div>`
    : flow === 'scrutiny_confirm' ? `<div class="dnote">${esc(d.why || 'No official category matches with certainty.')} On submit the letter goes to the scrutiny desk, where a person routes it to the right officer.</div><div class="dsubmit"><button class="dgo" id="docSubmit"><span>Submit</span><small>to the scrutiny desk, with the letter</small></button><button class="dchg" id="docChange">Change</button></div>`
    : `<div class="dnote">"""),
])
patch("mitra/web/mitra.css", [
    (""".dnote{font-size:12px;color:var(--mute);padding:8px 10px;border-radius:10px;background:rgba(255,154,60,.08);border:1px solid rgba(255,154,60,.3)}""",
     """.dnote{font-size:12px;color:var(--mute);padding:8px 10px;border-radius:10px;background:rgba(255,154,60,.08);border:1px solid rgba(255,154,60,.3)}
.drec{display:flex;gap:9px;align-items:flex-start;margin-top:6px;padding:8px 10px;border-radius:12px;background:linear-gradient(135deg,rgba(14,159,110,.14),rgba(0,200,255,.08));border:1px solid rgba(14,159,110,.4);animation:drecIn .6s cubic-bezier(.2,.8,.2,1) both}
.drec i{flex:none;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font-style:normal;font-size:12px;background:var(--em);color:#031;box-shadow:0 0 12px var(--em)}
.drec b{display:block;font-size:12px}.drec span{display:block;font-size:11px;color:var(--mute);line-height:1.35;margin-top:2px;white-space:normal}
@keyframes drecIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}"""),
])

# ---------------------------------------------------------------- POC WhatsApp upload
patch("app/web/docupload.js", [
    ("""  const S3 = [['name', 'Name'], ['phone', 'Mobile number'], ['complainant_address', 'Address'], ['letter_date', 'Date of the letter'], ['addressed_to', 'Addressed to'], ['asked_for', 'What is asked for']];""",
     """  const S3 = [['name', 'Name'], ['phone', 'Mobile number'], ['complainant_address', 'Address'], ['letter_date', 'Date of the letter'], ['addressed_to', 'Addressed to'], ['asked_for', 'What is asked for'], ['grievance_id', 'iPGRS number quoted in the letter']];"""),
    ("""      : `<div class="du-note">${u.intent === 'UNCLEAR' ? 'No official category matches well; on submit a person at the scrutiny desk will route it.' : u.intent === 'OUT_OF_SCOPE' ? 'This belongs to ' + E(u.dept || 'another department') + ', outside the pilot.' : E(u.reason || u.intent || '')}</div>`;
    ov.querySelector('#duBody').innerHTML = `<div class="du-grid"><div class="du-pages">${(r.thumbs || []).map((t, i) => `<img src="${t}" alt="page ${i + 1}">`).join('')}<div class="du-sec2"><b>${E(r.filename || 'Letter')}</b> · ${r.pages} page${r.pages > 1 ? 's' : ''} · read by Sakala AI in ${((r.ms || 0) / 1000).toFixed(0)} s""",
     """      : `<div class="du-note">${u.intent === 'UNCLEAR' ? 'No official category matches well; on submit the letter goes to the scrutiny desk, where a person routes it.' : u.intent === 'OUT_OF_SCOPE' ? 'This belongs to ' + E(u.dept || 'another department') + ', outside the three pilot departments; on submit the letter goes to the scrutiny desk, where a person routes it to that department.' : E(u.reason || u.intent || '')}</div>`;
    const rec = r.record, recRow = rec ? `<div class="du-rec"><i>⌘</i><div><b>Matches iPGRS record ${E(rec.gid)}</b><div>${E(rec.service || rec.grievance || '')} · ${E([rec.gp, rec.taluk, rec.district].filter(Boolean).join(', '))} · filed ${E((rec.created || '').slice(0, 10))} via ${E(rec.source || 'iPGRS')} · ${E(rec.status || '')}</div></div></div>` : '';
    ov.querySelector('#duBody').innerHTML = `<div class="du-grid"><div class="du-pages">${(r.thumbs || []).map((t, i) => `<img src="${t}" alt="page ${i + 1}">`).join('')}<div class="du-sec2"><b>${E(r.filename || 'Letter')}</b> · ${r.pages} page${r.pages > 1 ? 's' : ''} · read by Sakala AI in ${((r.ms || 0) / 1000).toFixed(0)} s${r.rotation ? ' · photo turned upright' : ''}${recRow}"""),
    ("""      <div class="du-bar"><button class="du-go" id="duGo">Submit the grievance</button></div></div></div>`;""",
     """      <div class="du-bar"><button class="du-go" id="duGo">${u.intent === 'GRIEVANCE' ? 'Submit the grievance' : 'Submit to the scrutiny desk'}</button></div></div></div>`;"""),
    ("""        res = await API('/api/intake', { session: WA.sid, step: 'scrutiny', text: fields.description || r.text, u, channel: 'document' });""",
     """        res = await API('/api/intake', { session: WA.sid, step: 'scrutiny', text: fields.description || r.text, u, channel: 'document', taluk: fields.taluk || '',
          doc: Object.assign({}, fields, { filename: r.filename, pages: r.pages, reader: r.reader, evidence: r.evidence, flags: r.flags, english: r.english, confidence: r.confidence, transcript: (r.transcript || '').slice(0, 4000), record: rec && rec.gid }) });"""),
    ("""          doc: Object.assign({}, fields, { filename: r.filename, pages: r.pages, reader: r.reader, evidence: r.evidence, flags: r.flags, english: r.english, confidence: r.confidence, transcript: (r.transcript || '').slice(0, 4000) }) });
      }""",
     """          doc: Object.assign({}, fields, { filename: r.filename, pages: r.pages, reader: r.reader, evidence: r.evidence, flags: r.flags, english: r.english, confidence: r.confidence, transcript: (r.transcript || '').slice(0, 4000), record: rec && rec.gid }) });
      }"""),
    ("""    const r = draft, u = r.u || {};
    let place = r.place;""",
     """    const r = draft, u = r.u || {}, rec = r.record;
    let place = r.place;"""),
    (""".du-sec2{padding:12px 14px;border-radius:14px;background:#f6f8fa;color:#667781;font-size:.82rem}""",
     """.du-sec2{padding:12px 14px;border-radius:14px;background:#f6f8fa;color:#667781;font-size:.82rem}
.du-rec{display:flex;gap:9px;align-items:flex-start;margin-top:10px;padding:9px 11px;border-radius:12px;background:linear-gradient(135deg,#eafaf0,#e8f6ff);border:1px solid #9fe3a9;color:#0b0b0c}
.du-rec i{flex:none;width:24px;height:24px;border-radius:50%;display:grid;place-items:center;font-style:normal;font-size:12px;background:#0e9f6e;color:#fff}
.du-rec b{display:block;font-size:.84rem}.du-rec div div{font-size:.76rem;color:#667781;margin-top:2px;line-height:1.35}"""),
])

# the scrutiny step in the POC must accept taluk for the desk: scrutiny_case(taluk=) is already threaded in api.py
print("done")
