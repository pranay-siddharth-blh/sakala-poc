"""Speed vs accuracy of the document reader per model, on the three real handwritten letters: one combined call
(transcript + form fields + English) per model, timed, with the key fields printed so accuracy can be compared.
Run from app/: PYTHONIOENCODING=utf-8 python ../tools/tests/doc_speed_probe.py"""
import base64
import glob
import json
import sys
import time

import httpx

sys.path.insert(0, ".")
from server import ai  # noqa: E402

KEY = ai._env()["GEMINI_API_KEY"]
BASE = "https://generativelanguage.googleapis.com/v1beta"
FIELDS = ["transcript", "description", "english", "district", "taluk", "gp", "village", "address", "name", "phone", "letter_date", "addressed_to",
          "subject", "grievance_id", "since", "asked_for", "language", "rotation"]
SCHEMA = {"type": "object", "additionalProperties": False, "required": FIELDS,
          "properties": {**{k: {"type": "string"} for k in FIELDS if k != "rotation"}, "rotation": {"type": "integer"}}}
PROMPT = ("This is a photo of a written complaint (petition) to the Government of Karnataka; it may be rotated. First work out the orientation "
          "(rotation = degrees clockwise the image must be turned to read it: 0, 90, 180 or 270). Then: transcript = EVERYTHING written, faithfully, "
          "in the script written (Kannada stays Kannada), one line per written line, [?] after an unsure word; description = the complaint body in "
          "the citizen's own words, original script; english = a plain English rendering of the complaint (names, places, numbers kept exactly); "
          "district / taluk / gp / village = the place of the problem as written (Latin letters if written so, else as written); address = the exact "
          "spot (street, landmark, door); name = the complainant's name as written; phone = mobile digits; letter_date = the date normalised to "
          "YYYY-MM-DD; addressed_to = the office / officer addressed; subject = the subject line; grievance_id = any grievance / complaint / "
          "reference number written; since = since when; asked_for = what is asked. Empty string when the letter does not say it. Never invent.")


def call(model, b64, timeout=120):
    body = {"contents": [{"role": "user", "parts": [{"inlineData": {"mimeType": "image/jpeg", "data": b64}}, {"text": PROMPT}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "responseJsonSchema": SCHEMA, "thinkingConfig": {"thinkingLevel": "low"}}}
    t0 = time.time()
    r = httpx.post(f"{BASE}/models/{model}:generateContent", json=body, headers={"x-goog-api-key": KEY}, timeout=timeout)
    if r.status_code == 400:
        body["generationConfig"].pop("thinkingConfig")
        r = httpx.post(f"{BASE}/models/{model}:generateContent", json=body, headers={"x-goog-api-key": KEY}, timeout=timeout)
    dt = time.time() - t0
    if r.status_code != 200:
        return dt, {"error": f"{r.status_code} {r.text[:120]}"}
    j = r.json()
    if "candidates" not in j:
        return dt, {"error": json.dumps(j, ensure_ascii=False)[:300]}
    txt = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"] if not p.get("thought"))
    return dt, json.loads(txt)


import os
DIR = os.environ.get("LETTERS", "../tools/tests/letters")
models = sys.argv[1:] or ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
for f in sorted(glob.glob(DIR + "/*.jpeg")):
    b64 = base64.b64encode(open(f, "rb").read()).decode()
    print("==", f.split("/")[-1])
    for m in models:
        dt, j = call(m, b64)
        keep = {k: j.get(k) for k in ("rotation", "name", "phone", "letter_date", "grievance_id", "taluk", "district", "gp", "village", "subject", "language")}
        print(f"  {m:24s} {dt:5.1f} s  {json.dumps(keep, ensure_ascii=False)[:400]}")
        if "error" in j:
            print("   ", j["error"])
