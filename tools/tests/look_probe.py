"""How fast can the orientation look be? Models x thinking settings on a 900 px copy of each letter.
Run from app/: PYTHONIOENCODING=utf-8 python ../tools/tests/look_probe.py"""
import base64
import glob
import io
import json
import os
import sys
import time

import httpx
from PIL import Image, ImageOps

sys.path.insert(0, ".")
from server import ai, docread  # noqa: E402

KEY = ai._env()["GEMINI_API_KEY"]
BASE = "https://generativelanguage.googleapis.com/v1beta"
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "letters")


def call(model, b64, think, size):
    gen = {"temperature": 0, "responseMimeType": "application/json", "responseJsonSchema": docread.LOOK_SCHEMA}
    if think:
        gen["thinkingConfig"] = think
    body = {"contents": [{"role": "user", "parts": [{"inlineData": {"mimeType": "image/jpeg", "data": b64}}, {"text": docread.LOOK}]}], "generationConfig": gen}
    t0 = time.time()
    r = httpx.post(f"{BASE}/models/{model}:generateContent", json=body, headers={"x-goog-api-key": KEY}, timeout=60)
    dt = time.time() - t0
    if r.status_code != 200:
        return dt, f"{r.status_code} {r.text[:90]}"
    j = r.json()
    if "candidates" not in j:
        return dt, "no candidates " + json.dumps(j.get("promptFeedback"))[:80]
    txt = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"] if not p.get("thought"))
    return dt, txt.strip()


for f in sorted(glob.glob(DIR + "/*.jpeg")):
    im = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
    print("==", os.path.basename(f), im.size)
    for size in (900, 600):
        s = im.copy(); s.thumbnail((size, size)); b = io.BytesIO(); s.save(b, "JPEG", quality=80); b64 = base64.b64encode(b.getvalue()).decode()
        for model, think in [("gemini-3.8-flash", {"thinkingLevel": "low"}), ("gemini-3.8-flash", {"thinkingLevel": "minimal"}), ("gemini-3.8-flash", {"thinkingBudget": 0}),
                             ("gemini-3.6-flash", {"thinkingLevel": "low"}), ("gemini-3.5-flash-lite", None), ("gemini-3.1-flash-lite", None)]:
            dt, out = call(model, b64, think, size)
            print(f"  {size}px {model:22s} {json.dumps(think):28s} {dt:5.1f} s  {out[:90]}")
