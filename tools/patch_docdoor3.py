"""Document door v2.1 (21 Oct 2026): orientation by a comparative chooser (four turns on one sheet, two fast voters), a model mix
for the three parallel reads, letter-date plausibility, the quoted iPGRS record as a deterministic guardrail (a record outside the
pilot departments -> scrutiny desk with the letter), municipal addressee rule, taluk returned for scrutiny-bound letters."""
import ast
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BK = ROOT / "tools" / "backups" / "res21"
BK.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ docread.py
p = ROOT / "app/server/docread.py"
s = p.read_text(encoding="utf-8")
shutil.copy(p, BK / "docread_v2.py.bak")

a = s.index('LOOK_SCHEMA = {'); b = s.index('TRANSCRIBE = (')
s = s[:a] + '''ORIENT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["upright"], "properties": {"upright": {"type": "string", "enum": ["A", "B", "C", "D"]}}}
ORIENT = ("The four panels A, B, C, D show the same photo of a document turned by 0, 90, 180 and 270 degrees. Exactly one panel shows it "
          "UPRIGHT: the lines of writing run horizontally, the letters stand on their feet, the heading / date at the top and the signature at "
          "the bottom. Which panel is upright? Answer with the letter of the panel.")
ORIENT_MODELS = ("gemini-3.1-flash-lite", "gemini-3.6-flash")      # two voters, 12/12 each on the gold letters at every rotation (~3 s)
READ_MODELS = {"transcript": "gemini-3.6-flash", "fields": None, "check": "gemini-3.6-flash"}   # None = the main model (gemini-3.8-flash)

''' + s[b:]

old = '''def _gemini(parts: list[dict], schema: dict | None = None, timeout: float = 90.0, model: str | None = None) -> str:
    c = ai._env()
    key = c.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("no Gemini key")
    gen = {"temperature": 0, "thinkingConfig": {"thinkingLevel": "low"}}
    if schema:
        gen.update(responseMimeType="application/json", responseJsonSchema=schema)
    body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": gen}
    last = None
    for m in ([model] if model else []) + [_model(), c.get("GEMINI_FALLBACK_MODEL") or "gemini-3.6-flash"]:'''
new = '''def _gemini(parts: list[dict], schema: dict | None = None, timeout: float = 90.0, model: str | None = None, think: bool = True) -> str:
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
    for m in chain:'''
assert old in s; s = s.replace(old, new)

a = s.index('def look(pages: list[dict]) -> dict:'); b = s.index('def _read_gemini(')
s = s[:a] + '''def _sheet(im, cell: int = 460) -> bytes:
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


''' + s[b:]

old = '''    with ThreadPoolExecutor(3) as ex:                     # three independent reads of the upright page, side by side
        fa = ex.submit(_gemini, inline + [{"text": TRANSCRIBE}])
        fb = ex.submit(_gemini, inline + [{"text": EXTRACT_B + hint}], SCHEMA_B)
        fc = ex.submit(_gemini, inline + [{"text": EXTRACT_C + hint}], SCHEMA)
        transcript, ex1, ex2 = fa.result().strip(), _json(fb.result()), _json(fc.result())'''
new = '''    with ThreadPoolExecutor(3) as ex:                     # three independent reads of the upright page, side by side
        fa = ex.submit(_gemini, inline + [{"text": TRANSCRIBE}], None, 90.0, READ_MODELS["transcript"])
        fb = ex.submit(_gemini, inline + [{"text": EXTRACT_B + hint}], SCHEMA_B, 90.0, READ_MODELS["fields"])
        fc = ex.submit(_gemini, inline + [{"text": EXTRACT_C + hint}], SCHEMA, 90.0, READ_MODELS["check"])   # another model: truly independent
        transcript, ex1, ex2 = fa.result().strip(), _json(fb.result()), _json(fc.result())'''
assert old in s; s = s.replace(old, new)

old = '''    is_pdf = media_type == "application/pdf" or data[:4] == b"%PDF"
    lk = {"rotation": 0, "language": "", "complaint": True} if is_pdf else look(pages)
    if not lk["complaint"] and not is_pdf:
        return {"ok": False, "reason": "unreadable", "detail": "not a complaint", "ms": int((time.time() - t0) * 1000)}
    pages = upright(pages, lk["rotation"])
    t_look = time.time() - t0
    engine_err = ""
    try:
        rd = _read_gemini(data, media_type, pages)
    except Exception as e:  # noqa: BLE001
        engine_err = str(e)[:120]
        try:
            rd = _read_gateway(pages)
        except Exception as e2:  # noqa: BLE001
            return {"ok": False, "reason": "no_reader", "detail": f"{engine_err}; {str(e2)[:120]}"}'''
new = '''    is_pdf = media_type == "application/pdf" or data[:4] == b"%PDF"
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
    lk = {"rotation": rotation, "language": ""}'''
assert old in s; s = s.replace(old, new)

old = '''        v = v1 or v2
        c = float((ex1.get("confidence") or {}).get(k) or (0.9 if v1 else 0))'''
new = '''        v = v1 or v2
        if k == "letter_date" and v1 and v2 and v1 != v2:     # a date far from today is the unlikely reading of a handwritten year
            v = v1 if _plausible_date(v1) or not _plausible_date(v2) else v2
        c = float((ex1.get("confidence") or {}).get(k) or (0.9 if v1 else 0))'''
assert old in s; s = s.replace(old, new)

old = '''def _clean_place(s: str) -> str:'''
new = '''def _plausible_date(s: str) -> bool:
    """A letter is dated within the last two years and not more than a month ahead."""
    from datetime import date, timedelta
    try:
        d = date.fromisoformat(s)
    except ValueError:
        return False
    today = date.today()
    return today - timedelta(days=730) <= d <= today + timedelta(days=31)


def _clean_place(s: str) -> str:'''
assert old in s; s = s.replace(old, new)

old = '''    r = db.q1("SELECT gid, dept, line, service, grievance, district, taluk, gp, status, source, created FROM ipgrs_records WHERE gid=? OR gid LIKE ?", (g, "%" + g))'''
new = '''    r = db.q1("SELECT gid, dept, dept_code, line, service, grievance, district, taluk, gp, status, source, created, role FROM ipgrs_records WHERE gid=? OR gid LIKE ?", (g, "%" + g))'''
assert old in s; s = s.replace(old, new)
old = '''           "several": bool(ex1.get("several")), "rotation": lk["rotation"], "language": fields.get("language") or lk["language"],'''
new = '''           "several": bool(ex1.get("several")), "rotation": rotation, "language": fields.get("language") or lk["language"],'''
assert old in s; s = s.replace(old, new)
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("docread ok")

# ------------------------------------------------------------------ api.py
p = ROOT / "app/server/api.py"
s = p.read_text(encoding="utf-8")
shutil.copy(p, BK / "api_v2.py.bak")
old = '''        if rec and u.get("intent") == "GRIEVANCE" and u.get("similar") is not None:
            u["record"] = rec["gid"]'''
new = '''        u = _doc_rules(u, f, rec)'''
assert old in s; s = s.replace(old, new)
old = '''        if u["intent"] == "GRIEVANCE":
            if rd.get("place"):
                out.update(_place_block(u, rd["place"]))
            else:
                out.update(_place_block(u, taluk=rd.get("taluk") or ""))
        return out'''
new = '''        if u["intent"] == "GRIEVANCE":
            if rd.get("place"):
                out.update(_place_block(u, rd["place"]))
            else:
                out.update(_place_block(u, taluk=rd.get("taluk") or ""))
        else:
            out["taluk"] = (rd.get("place") or {}).get("taluk") or rd.get("taluk") or ""     # picks the scrutiny desk of that taluk
        return out'''
assert old in s; s = s.replace(old, new)
old = '''def _place_block(u, place=None, taluk=""):'''
new = '''_MUNICIPAL_RX = re.compile(r"\\b(municipal|municipality|city corporation|town panchayat|nagara ?sabhe|purasabhe|cmc|tmc|bbmp|ward no)\\b|ನಗರಸಭೆ|ಪುರಸಭೆ|ಮಹಾನಗರ ಪಾಲಿಕೆ|ಪಟ್ಟಣ ಪಂಚಾಯಿತಿ", re.I)


def _doc_rules(u: dict, f: dict, rec: dict | None) -> dict:
    """Deterministic guardrails on a read letter: the iPGRS record it quotes is official evidence of its department (a record outside
    the three pilot departments means the letter is outside the pilot, whatever the words suggest), and a letter addressed to a
    municipal body is an urban matter, not a Gram Panchayat one. Both go to the scrutiny desk with the letter, never to a wrong officer."""
    u = dict(u)
    pilot = {"REV", "RDPR", "FOOD"}
    if rec:
        u["record"] = rec["gid"]
        if (rec.get("dept_code") or "") not in pilot and rec.get("dept"):
            if u.get("intent") in ("GRIEVANCE", "UNCLEAR"):
                u.update(intent="OUT_OF_SCOPE", dept=rec["dept"], line=rec.get("line") or "", conf=0.98, engine="llm+rules",
                         reason=f"The letter quotes iPGRS grievance {rec['gid']}, filed under the {rec['dept']} ({rec.get('service') or rec.get('grievance')}), outside the three pilot departments.")
                u["why"] = u["reason"]
            return u
    to = " ".join(str(f.get(k) or "") for k in ("addressed_to", "complainant_address", "address"))
    if u.get("intent") == "GRIEVANCE" and _MUNICIPAL_RX.search(to) and not re.search(r"gram|grama|panchayat|ಗ್ರಾಮ", to, re.I):
        u.update(intent="OUT_OF_SCOPE", dept="Urban Development Department", line="", conf=0.9, engine="llm+rules",
                 reason=f"Addressed to {f.get('addressed_to') or 'a municipal body'}: an urban local body matter, outside the three pilot departments.")
        u["why"] = u["reason"]
    return u


def _place_block(u, place=None, taluk=""):'''
assert old in s; s = s.replace(old, new)
assert "\nimport re\n" in s, "api.py needs import re"
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("api ok")
