"""The document door (19–21 Oct 2026): a written complaint (PDF, PNG, JPG; typed or handwritten; Kannada, English or both,
photographed at any angle) read into the official iPGRS form, then handed to the SAME pipeline every other door uses
(understand -> place -> create).

Reader, v2 (built on Pranay's three real handwritten letters, tools/tests/letters/):
  0. orientation: a small, fast look at the photo (rotation needed, language, is it a complaint) and the page is turned upright
     before anything is read from it: a Kannada letter read sideways loses names;
  1–3. three INDEPENDENT reads of the upright page run side by side: the faithful transcription (original script, unsure words
     marked [?]), the form fields with a confidence and the page/line evidence each, and a second extraction with a differently
     worded prompt; a field counts as confirmed only when the two extractions agree (after normalising), otherwise it is flagged
     for the person reviewing the form. The English rendering comes with the first extraction (no extra call).
  4. the letter's own grievance / complaint number, when written, is looked up in the 9,999 real iPGRS records: a hit is shown
     on the form and handed to the understanding step as retrieved evidence (the RAG anchor); the place of the record fills a
     place the letter does not name.
Engines: Gemini (reads the image / PDF directly; strongest on Kannada handwriting) first, the office gateway's vision model as
the fallback, a typed PDF's text layer as a third, model-free reading. Results are cached by file hash. Personal numbers are
masked before the text goes to understanding (the privacy shield is unchanged); name and phone go only to the complainant fields."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from . import ai, chat, db
from .privacy import mask

FORM = json.load(open(__file__.replace("docread.py", "ipgrs_form.json"), encoding="utf-8"))
FIELDS = ["description", "district", "taluk", "gp", "village", "pincode", "address", "name", "phone", "complainant_address",
          "letter_date", "addressed_to", "subject", "grievance_id", "since", "asked_for", "language"]
_CACHE: dict[str, dict] = {}
KN_DIGITS = str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789")
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL = None            # set from app/.env on first use (GEMINI_MODEL, default gemini-3.8-flash)

SCHEMA = {"type": "object", "additionalProperties": False, "required": FIELDS + ["confidence", "evidence", "readable", "several"],
          "properties": {**{k: {"type": "string"} for k in FIELDS},
                         "confidence": {"type": "object", "additionalProperties": {"type": "number"}},
                         "evidence": {"type": "object", "additionalProperties": {"type": "string"}},
                         "readable": {"type": "boolean"}, "several": {"type": "boolean"}}}
SCHEMA_B = {**SCHEMA, "required": SCHEMA["required"] + ["english"], "properties": {**SCHEMA["properties"], "english": {"type": "string"}}}
ORIENT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["upright"], "properties": {"upright": {"type": "string", "enum": ["A", "B", "C", "D"]}}}
ORIENT = ("The four panels A, B, C, D show the same photo of a document turned by 0, 90, 180 and 270 degrees. Exactly one panel shows it "
          "UPRIGHT: the lines of writing run horizontally, the letters stand on their feet, the heading / date at the top and the signature at "
          "the bottom. Which panel is upright? Answer with the letter of the panel.")
ORIENT_MODELS = ("gemini-3.1-flash-lite", "gemini-3.6-flash")      # two voters, 12/12 each on the gold letters at every rotation (~3 s)
READ_MODELS = {"transcript": "gemini-3.6-flash", "fields": "gemini-3.6-flash", "check": "gemini-3.6-flash"}   # 17/17 gold fields at ~6 s; the main model (3.8) is the fallback chain

TRANSCRIBE = ("This is a written complaint (petition) by a citizen to the Government of Karnataka. Transcribe EVERYTHING written on it, "
              "faithfully, in the script it is written in (Kannada stays Kannada, English stays English; mixed stays mixed). Keep the "
              "reading order, one line per written line, and put [?] after any word you are not sure of. Do not translate, summarise, "
              "correct or add anything. Include the date, the addressee, the subject, every number, the name, the signature line, any stamp.")
EXTRACT = ("From this written complaint fill the official iPGRS grievance form. Copy values exactly as written (original script); never "
           "invent a value: when the letter does not say it, return an empty string. Fields: description = the complaint itself in the "
           "citizen's own words, complete, original script (the body, not the header); district / taluk / gp (Gram Panchayat) / village = "
           "the place of the PROBLEM as written (an office address names the place too); pincode = 6 digits if written; address = the "
           "exact spot (street, landmark, door number, ward); name = the complainant's name as signed or written under 'Complainant Name'; "
           "phone = the mobile number digits if written; complainant_address = the complainant's own address if written; letter_date = the "
           "date on the letter normalised to YYYY-MM-DD; addressed_to = the office or officer the letter is addressed to; subject = the "
           "subject line; grievance_id = any grievance / complaint / reference / ID number written (digits only); since = since when the "
           "problem exists, as written; asked_for = what the citizen asks to be done; language = kn, en or mixed. confidence = 0-1 per "
           "field; evidence = per field, the written words it came from. readable = false if this is not a complaint or cannot be read; "
           "several = true if the letter holds more than one separate complaint.")
EXTRACT_B = EXTRACT + (" english = a plain English rendering of the whole complaint for an officer (names, places, dates and amounts kept "
                       "exactly; transliterate names and places, never translate them); if the letter is already English, english = the description.")
EXTRACT_C = ("You are checking a colleague's data entry. Read this written complaint yourself, independently, and fill the same iPGRS form "
             "fields from what is actually written, exactly as written (original script). Empty string when the letter does not say it; "
             "never guess. ") + EXTRACT.split("Fields: ", 1)[1]


# ------------------------------------------------------------------ files, pages, orientation
def pages_of(data: bytes, media_type: str) -> list[dict]:
    """[{png: bytes, text: str}] per page (PDF rendered at 200 dpi; images as they are)."""
    out = []
    if media_type == "application/pdf" or data[:4] == b"%PDF":
        import pymupdf
        doc = pymupdf.open(stream=data, filetype="pdf")
        for pg in doc:
            out.append({"png": pg.get_pixmap(dpi=200).tobytes("png"), "text": (pg.get_text() or "").strip()})
        doc.close()
    else:
        out.append({"png": data, "text": ""})
    return out


def _img(data: bytes):
    from PIL import Image, ImageOps
    return ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")


def _jpeg(im, max_side: int = 1600, q: int = 88) -> bytes:
    im = im.copy(); im.thumbnail((max_side, max_side))
    b = io.BytesIO(); im.save(b, "JPEG", quality=q); return b.getvalue()


def upright(pages: list[dict], rotation: int) -> list[dict]:
    """Turn every page by the rotation the reader asked for (clockwise degrees)."""
    if rotation % 360 == 0:
        return pages
    out = []
    for p in pages:
        im = _img(p["png"]).rotate(-rotation, expand=True)            # PIL rotates counter-clockwise
        out.append({"png": _jpeg(im, 2000, 92), "text": p["text"], "jpeg": True})
    return out


def thumbs(pages: list[dict], width: int = 480) -> list[str]:
    out = []
    for p in pages:
        try:
            im = _img(p["png"]); im.thumbnail((width, width * 2))
            b = io.BytesIO(); im.save(b, "JPEG", quality=80)
            out.append("data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode())
        except Exception:  # noqa: BLE001
            out.append("data:image/png;base64," + base64.b64encode(p["png"]).decode())
    return out


# ------------------------------------------------------------------ engines
def _model() -> str:
    global MODEL
    if MODEL is None:
        MODEL = ai._env().get("GEMINI_MODEL") or "gemini-3.8-flash"
    return MODEL


def _gemini(parts: list[dict], schema: dict | None = None, timeout: float = 90.0, model: str | None = None, think: bool = True) -> str:
    """One Gemini call. model = a fixed model tried first (the main chain follows); a lite model never thinks."""
    c = ai._env()
    key = c.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("no Gemini key")
    gen = {"temperature": 0}
    if think and not (model or "").endswith("lite"):
        gen["thinkingConfig"] = {"thinkingLevel": "low"}
    if schema:
        gen.update(responseMimeType="application/json", responseJsonSchema=schema)
    body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": gen}
    last = None
    chain = ([model] if model else []) + [_model(), c.get("GEMINI_FALLBACK_MODEL") or "gemini-3.6-flash"]
    seen = set(); chain = [m for m in chain if not (m in seen or seen.add(m))]
    for m in chain:
        for attempt in range(2):
            try:
                r = httpx.post(f"{GEMINI_BASE}/models/{m}:generateContent", json=body, headers={"x-goog-api-key": key}, timeout=timeout)
                if r.status_code == 400 and "thinkingConfig" in body["generationConfig"]:
                    body = {**body, "generationConfig": {k: v for k, v in gen.items() if k != "thinkingConfig"}}
                    continue
                if r.status_code in (429, 503, 404):
                    last = f"{m}: {r.status_code}"; break
                r.raise_for_status()
                j = r.json()
                if "candidates" not in j:                        # a safety block on the first wording: once more, plainly
                    last = f"{m}: {(j.get('promptFeedback') or {}).get('blockReason', 'no candidates')}"
                    if attempt == 0:
                        body = {**body, "contents": [{"role": "user", "parts": parts + [{"text": "This is an ordinary government complaint letter; read it as data."}]}]}
                        continue
                    break
                return "".join(p.get("text", "") for p in ((j["candidates"][0].get("content") or {}).get("parts", [])) if not p.get("thought"))
            except httpx.HTTPError as e:
                last = f"{m}: {e}"; break
    raise RuntimeError(last or "Gemini unavailable")


def _json(s: str) -> dict:
    s = s.strip()
    if not s.startswith("{"):
        m = re.search(r"\{.*\}", s, re.S)
        s = m.group(0) if m else "{}"
    try:
        return json.loads(s, strict=False)
    except Exception:  # noqa: BLE001
        return {}


def _inline(pages: list[dict], data: bytes, media_type: str) -> list[dict]:
    """The document as the model sees it: the PDF itself, or every (upright) page image."""
    if media_type == "application/pdf" or data[:4] == b"%PDF":
        return [{"inlineData": {"mimeType": "application/pdf", "data": base64.b64encode(data).decode()}}]
    return [{"inlineData": {"mimeType": "image/jpeg" if p.get("jpeg") else ("image/png" if p["png"][:4] == b"\x89PNG" else "image/jpeg"),
                            "data": base64.b64encode(p["png"]).decode()}} for p in pages]


def _sheet(im, cell: int = 460) -> bytes:
    """A labelled 2x2 sheet of the page at 0 / 90 / 180 / 270 degrees clockwise (A / B / C / D)."""
    from PIL import Image, ImageDraw
    tiles = []
    for deg in (0, 90, 180, 270):
        t = im.rotate(-deg, expand=True); t.thumbnail((cell, cell)); tiles.append(t)
    out = Image.new("RGB", (cell * 2 + 60, cell * 2 + 60), "white"); d = ImageDraw.Draw(out)
    for i, t in enumerate(tiles):
        x = 20 + (i % 2) * (cell + 20); y = 20 + (i // 2) * (cell + 20)
        out.paste(t, (x + (cell - t.width) // 2, y + (cell - t.height) // 2))
        d.rectangle([x - 2, y - 2, x + cell + 2, y + cell + 2], outline="black", width=3)
        d.rectangle([x, y, x + 46, y + 40], fill="black"); d.text((x + 12, y + 6), "ABCD"[i], fill="white")
    b = io.BytesIO(); out.save(b, "JPEG", quality=82); return b.getvalue()


def orient(pages: list[dict]) -> int:
    """Pass 0: which way up is the photo? A comparative question (the four turns side by side, 'which reads upright') is answered
    reliably where 'how many degrees' was not. Two fast voters; when they differ the stronger one decides. Returns clockwise degrees."""
    try:
        sheet = _sheet(_img(pages[0]["png"]))
        parts = [{"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(sheet).decode()}}, {"text": ORIENT}]

        def vote(m):
            try:
                return _json(_gemini(parts, ORIENT_SCHEMA, timeout=30, model=m)).get("upright")
            except Exception:  # noqa: BLE001
                return None
        with ThreadPoolExecutor(2) as ex:
            votes = list(ex.map(vote, ORIENT_MODELS))
        pick = votes[0] if votes[0] == votes[1] else (votes[1] or votes[0])
        return "ABCD".index(pick) * 90 if pick in ("A", "B", "C", "D") else 0
    except Exception:  # noqa: BLE001
        return 0


def _read_gemini(data: bytes, media_type: str, pages: list[dict]) -> dict:
    inline = _inline(pages, data, media_type)
    layer = "\n".join(p["text"] for p in pages if p["text"]).strip()
    hint = f"\n\nText layer of the PDF (may help):\n{layer[:6000]}" if layer else ""
    with ThreadPoolExecutor(3) as ex:                     # three independent reads of the upright page, side by side
        fa = ex.submit(_gemini, inline + [{"text": TRANSCRIBE}], None, 90.0, READ_MODELS["transcript"])
        fb = ex.submit(_gemini, inline + [{"text": EXTRACT_B + hint}], SCHEMA_B, 90.0, READ_MODELS["fields"])
        fc = ex.submit(_gemini, inline + [{"text": EXTRACT_C + hint}], SCHEMA, 90.0, READ_MODELS["check"])   # another model: truly independent
        transcript, ex1, ex2 = fa.result().strip(), _json(fb.result()), _json(fc.result())
    return {"engine": "Sakala AI (document reader)", "transcript": transcript, "ex1": ex1, "ex2": ex2}


def _read_gateway(pages: list[dict]) -> dict:
    """The office gateway's vision model, page by page, then guided JSON from the transcription."""
    texts = []
    for p in pages:
        if p["text"] and len(p["text"]) > 40:
            texts.append(p["text"]); continue
        j = ai.chat("ocr", [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(_jpeg(_img(p["png"]))).decode()}},
            {"type": "text", "text": TRANSCRIBE}]}], max_tokens=1500, timeout=90)
        texts.append(j if isinstance(j, str) else json.dumps(j, ensure_ascii=False))
    transcript = "\n\n".join(f"[page {i + 1}]\n{t}" for i, t in enumerate(texts))
    ex = ai.chat("docread", [{"role": "system", "content": EXTRACT_B}, {"role": "user", "content": transcript[:8000]}], schema=SCHEMA_B, max_tokens=1500, timeout=90)
    return {"engine": "Sakala AI (office reader)", "transcript": transcript, "ex1": ex, "ex2": ex}


# ------------------------------------------------------------------ normalise, agree, retrieve
def _digits(s: str) -> str:
    return re.sub(r"\D", "", (s or "").translate(KN_DIGITS))


def _norm_phone(s: str) -> str:
    d = _digits(s)
    d = d[-10:] if len(d) > 10 and d.startswith(("91", "091", "0")) else d
    return d


def _norm_date(s: str) -> str:
    s = (s or "").translate(KN_DIGITS).strip()
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", s)
    if m:
        y = int(m.group(3)); y = y + 2000 if y < 100 else y
        return f"{y}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return s


def _plausible_date(s: str) -> bool:
    """A letter is dated within the last two years and not more than a month ahead."""
    from datetime import date, timedelta
    try:
        d = date.fromisoformat(s)
    except ValueError:
        return False
    today = date.today()
    return today - timedelta(days=730) <= d <= today + timedelta(days=31)


def _clean_place(s: str) -> str:
    return re.sub(r"\b(gram(a)? panchayat|grama panchayath|panchayat|taluk|taluka|district|village|town|city)\b\.?", "", s or "", flags=re.I).strip(" ,.")


def _same(a: str, b: str) -> bool:
    ka = re.sub(r"[\W_]+", "", (a or "").lower()); kb = re.sub(r"[\W_]+", "", (b or "").lower())
    if not ka and not kb:
        return True
    if not ka or not kb:
        return False
    return ka == kb or ka in kb or kb in ka


def ipgrs_match(gid: str) -> dict | None:
    """The letter's own grievance number looked up in the real iPGRS records: the retrieval anchor."""
    g = _digits(gid)
    if len(g) < 5:
        return None
    r = db.q1("SELECT gid, dept, dept_code, line, service, grievance, district, taluk, gp, status, source, created, role FROM ipgrs_records WHERE gid=? OR gid LIKE ?", (g, "%" + g))
    return dict(r) if r else None


def _place(ex: dict, rec: dict | None) -> dict:
    """The place of the problem resolved through the shared completion-step resolver (gazetteer + transliteration); the
    matching iPGRS record fills in what the letter does not name."""
    tries = [(k, _clean_place(ex.get(k) or "")) for k in ("village", "gp", "address", "taluk")]
    if rec:
        tries += [("record gp", rec.get("gp") or ""), ("record taluk", rec.get("taluk") or "")]
    for key, v in tries:
        if not v:
            continue
        place, tk = chat.place_reply(v, _clean_place(ex.get("taluk") or "") or (rec or {}).get("taluk") or "")
        if place:
            return {"place": {**place, "how": f"read from the letter ({key}: {v})" if not key.startswith("record") else f"from iPGRS record {rec['gid']} ({key})"}}
        if tk and key.endswith("taluk"):
            return {"taluk": tk}
    tk = chat.taluk_in_text(" ".join(str(ex.get(k) or "") for k in ("taluk", "address", "addressed_to", "description")))
    return {"taluk": tk} if tk else {}


def read(data: bytes, media_type: str = "application/pdf", filename: str = "") -> dict:
    """Read a written complaint into the form. Returns {ok, fields, confidence, flags, evidence, transcript, english, pages, thumbs,
    engine, masked, masked_items, place|taluk, several, rotation, language, record, hint, hash, ms}."""
    h = hashlib.sha256(data).hexdigest()[:20]
    if h in _CACHE:
        return _CACHE[h]
    t0 = time.time()
    pages = pages_of(data, media_type)
    if not pages:
        return {"ok": False, "reason": "empty"}
    is_pdf = media_type == "application/pdf" or data[:4] == b"%PDF"
    rotation, rd, engine_err = 0, None, ""
    if not is_pdf:
        im0 = _img(pages[0]["png"])
        if im0.width > im0.height:                     # a sideways page: find which way up first (~3 s), then read it upright
            rotation = orient(pages)
            pages = upright(pages, rotation)
        else:                                          # a portrait photo is almost always upright: read at once, check beside it
            with ThreadPoolExecutor(2) as ex:
                fo = ex.submit(orient, pages)
                try:
                    rd = _read_gemini(data, media_type, pages)
                except Exception as e:  # noqa: BLE001
                    engine_err = str(e)[:120]
                rotation = fo.result()
            if rotation:                               # upside down after all: read it again the right way up
                pages = upright(pages, rotation); rd = None
    t_look = time.time() - t0
    if rd is None:
        try:
            rd = _read_gemini(data, media_type, pages)
        except Exception as e:  # noqa: BLE001
            engine_err = str(e)[:120]
            try:
                rd = _read_gateway(pages)
            except Exception as e2:  # noqa: BLE001
                return {"ok": False, "reason": "no_reader", "detail": f"{engine_err}; {str(e2)[:120]}"}
    lk = {"rotation": rotation, "language": ""}
    ex1, ex2 = rd["ex1"], rd["ex2"]
    if not ex1 and not ex2:
        return {"ok": False, "reason": "unreadable", "engine": rd["engine"], "transcript": rd["transcript"][:400]}
    if not ex1:
        ex1 = ex2
    if not ex1.get("readable", True) and not (ex1.get("description") or "").strip():
        return {"ok": False, "reason": "unreadable", "engine": rd["engine"], "transcript": rd["transcript"][:400]}
    fields, conf, flags, evidence = {}, {}, [], {}
    for k in FIELDS:
        v1, v2 = str(ex1.get(k) or "").strip(), str(ex2.get(k) or "").strip()
        if k == "phone":
            v1, v2 = _norm_phone(v1), _norm_phone(v2)
        elif k == "letter_date":
            v1, v2 = _norm_date(v1), _norm_date(v2)
        elif k == "pincode":
            v1, v2 = _digits(v1)[:6], _digits(v2)[:6]
        elif k == "grievance_id":
            v1, v2 = _digits(v1), _digits(v2)
        elif k in ("district", "taluk", "gp", "village"):
            v1, v2 = _clean_place(v1), _clean_place(v2)
        v = v1 or v2
        if k == "letter_date" and v1 and v2 and v1 != v2:     # a date far from today is the unlikely reading of a handwritten year
            v = v1 if _plausible_date(v1) or not _plausible_date(v2) else v2
        c = float((ex1.get("confidence") or {}).get(k) or (0.9 if v1 else 0))
        agree = _same(v1, v2) if k != "description" else (bool(v1) and bool(v2))
        if v and not agree:
            flags.append({"field": k, "read": v1, "second": v2, "why": "the two readings differ"})
            c = min(c, 0.5)
        if k == "phone" and v and not re.fullmatch(r"[6-9]\d{9}", v):
            flags.append({"field": k, "read": v, "why": "not a valid 10-digit mobile number"})
            c = min(c, 0.4)
        fields[k] = v
        conf[k] = round(c, 2)
        evidence[k] = str((ex1.get("evidence") or {}).get(k) or "")
    # the grievance number on the letter as a pincode by mistake
    if fields["pincode"] and fields["pincode"] == fields["grievance_id"][:6]:
        fields["pincode"] = ""
    if fields["pincode"] and (len(fields["pincode"]) != 6 or not fields["pincode"].startswith("5")):
        fields["pincode"] = ""
    rec = ipgrs_match(fields["grievance_id"])
    desc = fields["description"] or rd["transcript"]
    english = str(ex1.get("english") or "").strip()
    if not english or not re.search(r"[A-Za-z]{3,}", english):
        english = desc
    if re.search(r"[ऀ-෿]", english) and english == desc and re.search(r"[ऀ-෿]", desc):
        try:                                               # the extraction gave no English: one short call
            english = _gemini([{"text": "Translate this Karnataka citizen's complaint into plain English for a government officer. Keep every "
                                        "name, place, date and number exactly as written (transliterate names and places). Output only the English.\n\n" + desc[:4000]}], timeout=40).strip()
        except Exception:  # noqa: BLE001
            pass
    masked, n = mask(desc)
    hint = ""
    if rec:
        hint = (f"iPGRS grievance {rec['gid']} (the number written on this letter): department {rec['dept']}, line department {rec['line']}, "
                f"service {rec['service']}, grievance type {rec['grievance']}, {rec['district']} district, {rec['taluk']} taluk"
                + (f", {rec['gp']} GP" if rec.get("gp") else "") + f", filed {rec['created'][:10]} via {rec['source']}, status {rec['status']}.")
    out = {"ok": True, "fields": fields, "confidence": conf, "flags": flags, "evidence": evidence, "transcript": rd["transcript"],
           "english": english, "masked": masked, "masked_items": n, "pages": len(pages), "thumbs": thumbs(pages), "engine": rd["engine"],
           "several": bool(ex1.get("several")), "rotation": rotation, "language": fields.get("language") or lk["language"],
           "record": rec, "hint": hint, "hash": h, "filename": filename, "ms": int((time.time() - t0) * 1000),
           "ms_look": int(t_look * 1000), **_place(fields, rec)}
    _CACHE[h] = out
    return out


def missing(fields: dict) -> list[str]:
    """Required form fields the letter did not give (a paper letter may leave them; the form accepts 'not provided')."""
    req = [f["key"] for s in FORM["steps"] for f in s["fields"] if f.get("required") and f["key"] not in ("department", "line", "service", "grievance", "attachment", "description")]
    return [k for k in req if not (fields.get(k) or "").strip()]
