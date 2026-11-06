"""Which model mix for the three parallel reads? Runs docread.read directly (no server) on the gold letters per configuration and
prints timing + the key fields against expected.json. Run from app/: PYTHONIOENCODING=utf-8 python ../tools/tests/doc_models_probe.py"""
import glob
import json
import os
import sys
import time

sys.path.insert(0, ".")
from server import docread  # noqa: E402

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "letters")
EXP = json.load(open(os.path.join(DIR, "expected.json"), encoding="utf-8"))
CONFIGS = {
    "B=3.8 A/C=3.6": {"transcript": "gemini-3.6-flash", "fields": None, "check": "gemini-3.6-flash"},
    "all 3.6":       {"transcript": "gemini-3.6-flash", "fields": "gemini-3.6-flash", "check": "gemini-3.6-flash"},
    "B=3.6 C=3.8":   {"transcript": "gemini-3.6-flash", "fields": "gemini-3.6-flash", "check": None},
}
only = sys.argv[1:]
for name, cfg in CONFIGS.items():
    if only and name not in only:
        continue
    docread.READ_MODELS.update(cfg); docread._CACHE.clear()
    print("=====", name)
    tot = 0; right = 0; n = 0
    for f in sorted(glob.glob(DIR + "/*.jpeg")):
        base = os.path.basename(f)
        t0 = time.time()
        r = docread.read(open(f, "rb").read(), "image/jpeg", base)
        dt = time.time() - t0; tot += dt
        fl = r.get("fields", {})
        miss = []
        for k, v in EXP[base]["fields"].items():
            got = fl.get(k) or ""
            okk = got.lower().strip() == str(v).lower().strip() or (k == "name" and str(v).lower().split()[0] in got.lower())
            right += okk; n += 1
            if not okk:
                miss.append(f"{k}: {got!r} != {v!r}")
        print(f"  {base[:14]:14s} {dt:5.1f} s (orient {r.get('ms_look', 0) / 1000:.1f}) rot {r.get('rotation')} flags {[x['field'] for x in r.get('flags', [])]} {'OK' if not miss else miss}")
    print(f"  => {right}/{n} fields, {tot / 3:.1f} s avg")
