"""Orientation chooser: the four rotations of a letter as one labelled 2x2 sheet, 'which panel reads upright?'.
Ground truth: every real letter needs 270 cw (= 90 ccw); each is also tested pre-rotated so all four answers are exercised.
Run from app/: PYTHONIOENCODING=utf-8 python ../tools/tests/orient_probe.py [models...]"""
import base64
import glob
import io
import json
import os
import sys
import time

import httpx
from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, ".")
from server import ai  # noqa: E402

KEY = ai._env()["GEMINI_API_KEY"]
BASE = "https://generativelanguage.googleapis.com/v1beta"
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "letters")
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["upright"], "properties": {"upright": {"type": "string", "enum": ["A", "B", "C", "D"]}}}
PROMPT = ("The four panels A, B, C, D show the same photo of a handwritten letter turned by 0, 90, 180 and 270 degrees. Exactly one panel shows the letter "
          "UPRIGHT: the lines of writing run horizontally, the letters stand on their feet, the heading/date at the top and the signature at the bottom. "
          "Which panel is upright? Answer with the letter of the panel.")


def sheet(im, cell=520):
    """A 2x2 sheet: A=0, B=90cw, C=180, D=270cw (PIL rotate is counter-clockwise, so cw = negative)."""
    tiles = []
    for deg in (0, 90, 180, 270):
        t = im.rotate(-deg, expand=True); t.thumbnail((cell, cell))
        tiles.append(t)
    W = cell * 2 + 60; H = cell * 2 + 60
    out = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(out)
    for i, t in enumerate(tiles):
        x = 20 + (i % 2) * (cell + 20); y = 20 + (i // 2) * (cell + 20)
        out.paste(t, (x + (cell - t.width) // 2, y + (cell - t.height) // 2))
        d.rectangle([x - 2, y - 2, x + cell + 2, y + cell + 2], outline="black", width=3)
        d.rectangle([x, y, x + 46, y + 40], fill="black"); d.text((x + 12, y + 6), "ABCD"[i], fill="white")
    b = io.BytesIO(); out.save(b, "JPEG", quality=82); return b.getvalue()


def ask(model, jpg, think):
    gen = {"temperature": 0, "responseMimeType": "application/json", "responseJsonSchema": SCHEMA}
    if think:
        gen["thinkingConfig"] = think
    body = {"contents": [{"role": "user", "parts": [{"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(jpg).decode()}}, {"text": PROMPT}]}], "generationConfig": gen}
    t0 = time.time()
    r = httpx.post(f"{BASE}/models/{model}:generateContent", json=body, headers={"x-goog-api-key": KEY}, timeout=60)
    dt = time.time() - t0
    if r.status_code != 200:
        return dt, "?" + str(r.status_code)
    j = r.json()
    if "candidates" not in j:
        return dt, "?block"
    txt = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"] if not p.get("thought"))
    try:
        return dt, json.loads(txt)["upright"]
    except Exception:  # noqa: BLE001
        return dt, "?" + txt[:20]


models = sys.argv[1:] or ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.6-flash"]
score = {m: [0, 0, 0.0] for m in models}
for f in sorted(glob.glob(DIR + "/*.jpeg")):
    raw = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
    base_fix = 270                                 # the real photos need 270 cw to stand upright
    for pre in (0, 90, 180, 270):                  # pre-turn the photo cw by `pre`: the needed fix becomes (base_fix - pre) % 360
        im = raw.rotate(-pre, expand=True)
        need = (base_fix - pre) % 360
        truth = "ABCD"[need // 90]
        jpg = sheet(im)
        for m in models:
            dt, ans = ask(m, jpg, {"thinkingLevel": "low"} if "lite" not in m else None)
            ok = ans == truth
            score[m][0] += ok; score[m][1] += 1; score[m][2] += dt
            print(f"{os.path.basename(f)[:14]:14s} pre {pre:3d} need {need:3d} -> {truth}   {m:22s} {dt:4.1f} s  {ans} {'ok' if ok else 'WRONG'}")
for m, (k, n, t) in score.items():
    print(f"{m}: {k}/{n} right, {t / n:.1f} s avg")
