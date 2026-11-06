"""The Kannada question bank (22 Oct 2026): the Chief Secretary's questions in casual, code-mixed Kannada (the way people talk in
Bengaluru), the same groups as the English bank (tests/cs_bank.py), plus citizen complaints and knowledge in Kannada. Every number
is checked against app/data/sakala.db. Because a Kannada answer may say a number in words, the check looks at the numbers DRAWN
on screen (the viz cards: KPI tiles, bars) and at the answer text; the answer must contain Kannada script.

Paths: --cascade (default; /api/turn on the test instance 8031 with a Kannada session) or --live (the real live voice on 8030,
Kannada session: the function called, the board drawn, the spoken Kannada).
Usage (from mitra/): PYTHONIOENCODING=utf-8 python tests/kn_bank.py [--live] [--base URL] [--only GROUP] [--workers N]"""
import argparse
import asyncio
import concurrent.futures as cf
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cs_bank as CB  # noqa: E402

live, ipg, ipg_total, esc_all, ROWS, DB = CB.live, CB.ipg, CB.ipg_total, CB.esc_all, CB.ROWS, CB.DB
OPEN = CB.OPEN
KN = lambda s: sum(1 for ch in s or "" if "ಀ" <= ch <= "೿")
BANK = []


def add(group, qs, **chk):
    for q in qs:
        BANK.append((group, q, chk))


add("level-L1", ["L1 ಹಂತದಲ್ಲಿ ಎಷ್ಟು ಕೇಸ್ ಇವೆ?", "field officers ಹತ್ರ ಎಷ್ಟು cases pending ಇದೆ?", "ಮೊದಲ ಹಂತದಲ್ಲಿ ಎಷ್ಟು ದೂರುಗಳು ಬಾಕಿ ಇವೆ?"], num=live(level="L1"))
add("level-L2", ["L2 ನಲ್ಲಿ ಎಷ್ಟು cases ಇವೆ?", "ಎರಡನೇ ಹಂತದ ಅಧಿಕಾರಿಗಳ ಹತ್ರ ಎಷ್ಟು ದೂರುಗಳು ಬಾಕಿ ಇವೆ?"], num=live(level="L2"))
add("level-L3", ["L3 officers ಹತ್ರ ಎಷ್ಟು cases ಇವೆ?", "ಮೂರನೇ ಹಂತದಲ್ಲಿ ಎಷ್ಟು ಕೇಸ್ ಇವೆ?"], num=live(level="L3"))
add("level-split", ["ಹಂತವಾರು breakup ತೋರಿಸಿ", "L1, L2, L3 ಪ್ರಕಾರ cases ತೋರಿಸಿ"], num=live(level="L1"))
add("escalated", ["ಎಷ್ಟು ಕೇಸ್ escalate ಆಗಿವೆ?", "ಇಲ್ಲಿವರೆಗೆ ಎಷ್ಟು ದೂರುಗಳು ಮೇಲಕ್ಕೆ ಹೋದವು?"], num=esc_all())
add("not-escalated", ["ಎಷ್ಟು ಕೇಸ್ escalate ಆಗಿಲ್ಲ?"], num=live(esc=False))
add("days-3", ["ಎಷ್ಟು ಕೇಸ್‌ಗಳಿಗೆ 3 ದಿನ ಉಳಿದಿವೆ?", "ಮೂರು ದಿನ ಬಾಕಿ ಇರೋ cases ಎಷ್ಟು?"], num=live(left=3))
add("days-1", ["1 ದಿನ ಉಳಿದಿರೋ ಕೇಸ್ ಎಷ್ಟು?"], num=live(left=1))
add("days-5", ["5 ದಿನ ಉಳಿದಿರೋ cases ಎಷ್ಟು?"], num=live(left=5))
add("due-today", ["ಇವತ್ತೇ due ಇರೋ ಕೇಸ್ ಎಷ್ಟು?"], num=live(left=0))
add("due-tomorrow", ["ನಾಳೆ due ಇರೋ ಕೇಸ್ ಎಷ್ಟು?"], num=live(left=1))
add("timeline", ["7 day timeline ತೋರಿಸಿ", "deadline ಪ್ರಕಾರ cases ತೋರಿಸಿ"], num=live(left=3))
for pl, kn in (("Hunsur", "ಹುಣಸೂರು"), ("Piriyapatna", "ಪಿರಿಯಾಪಟ್ಟಣ"), ("Alur", "ಆಲೂರು"), ("Sagar", "ಸಾಗರ")):
    add(f"pending-{pl.lower()}", [f"{kn} ತಾಲ್ಲೂಕಿನಲ್ಲಿ ಎಷ್ಟು ಕೇಸ್ ಬಾಕಿ ಇದೆ?"], num=live(taluk=pl))
for pl, kn in (("Mysuru", "ಮೈಸೂರು"), ("Belagavi", "ಬೆಳಗಾವಿ"), ("Shivamogga", "ಶಿವಮೊಗ್ಗ")):
    add(f"pending-{pl.lower()}", [f"{kn} ಜಿಲ್ಲೆಯಲ್ಲಿ ಎಷ್ಟು ಕೇಸ್ ಬಾಕಿ ಇವೆ?"], num=live(district=pl))
add("dash-rdpr", ["RDPR ಹೇಗೆ perform ಮಾಡ್ತಿದೆ?", "ಗ್ರಾಮೀಣಾಭಿವೃದ್ಧಿ ಇಲಾಖೆ ಹೇಗಿದೆ?"], num=live(dept="RDPR"), board=True)
add("dash-revenue", ["ಕಂದಾಯ ಇಲಾಖೆ ಹೇಗಿದೆ?"], num=live(dept="REV"), board=True)
add("dash-food", ["ಆಹಾರ ಇಲಾಖೆ ಹೇಗಿದೆ?"], num=live(dept="FOOD"), board=True)
for kn, like in (("ಶಿಕ್ಷಣ ಇಲಾಖೆ ಹೇಗಿದೆ?", "Department of School Education%"), ("ಆರೋಗ್ಯ ಇಲಾಖೆ ಹೇಗಿದೆ?", "Health and Family%"),
                 ("ನಗರಾಭಿವೃದ್ಧಿ ಇಲಾಖೆ ಹೇಗಿದೆ?", "Urban Development%"), ("ವಿದ್ಯುತ್ ಇಲಾಖೆ ಹೇಗಿದೆ?", "Energy%"), ("ಪೊಲೀಸ್ ಇಲಾಖೆ ಹೇಗಿದೆ?", "Home%"),
                 ("ಸಾರಿಗೆ ಇಲಾಖೆ ಹೇಗಿದೆ?", "Transport%"), ("ವಸತಿ ಇಲಾಖೆ ಹೇಗಿದೆ?", "Housing%"), ("ಕೃಷಿ ಇಲಾಖೆ ಹೇಗಿದೆ?", "Agriculture%")):
    add("dash-" + like.split()[0].lower()[:10], [kn], num=ipg_total(like), board=True)
add("count-health", ["ಆರೋಗ್ಯ ಇಲಾಖೆಯಲ್ಲಿ ಎಷ್ಟು ದೂರು ಬಾಕಿ ಇವೆ?"], num=ipg("Health and Family%"))
add("count-rdpr-overdue", ["RDPR ನಲ್ಲಿ ಎಷ್ಟು overdue ಇದೆ?"], num=live(dept="RDPR", overdue=True))
add("dash-hunsur", ["ಹುಣಸೂರು ಹೇಗಿದೆ?", "ಹುಣಸೂರು ತಾಲ್ಲೂಕಿನ ಎಲ್ಲಾ ವಿವರ ತೋರಿಸಿ"], num=live(taluk="Hunsur"), board=True)
add("dash-piriyapatna", ["ಪಿರಿಯಾಪಟ್ಟಣ ಹೇಗಿದೆ?"], num=live(taluk="Piriyapatna"), board=True)
add("dash-mysuru", ["ಮೈಸೂರು ಜಿಲ್ಲೆ ಹೇಗಿದೆ?"], num=live(district="Mysuru"), board=True)
add("dash-state", ["ಒಟ್ಟಾರೆ ರಾಜ್ಯದ dashboard ತೋರಿಸಿ"], num=len([r for r in ROWS if r["status"] in OPEN]), board=True)
add("knowledge", ["ಸಕಾಲ ಅಂದ್ರೆ ಏನು?", "Chief Secretary ಯಾರು?", "ತಡವಾದರೆ ಎಷ್ಟು compensation ಸಿಗುತ್ತೆ?"], kn_text=True, knowledge=True)
SEQ = [("RDPR ಹೇಗಿದೆ?", dict(num=live(dept="RDPR"), board=True)),
       ("ಮತ್ತೆ ಹುಣಸೂರು?", dict(num=sum(1 for r in ROWS if r["status"] in OPEN and r["dept_code"] == "RDPR" and r["taluk"] == "Hunsur"), board=True)),
       ("ಒಟ್ಟಾರೆ L1 ನಲ್ಲಿ ಎಷ್ಟು ಕೇಸ್ ಇವೆ?", dict(num=live(level="L1")))]
CITIZEN = [("ನಮ್ಮ ಊರು ಗೊರಹಳ್ಳಿಯಲ್ಲಿ ಒಂದು ವಾರದಿಂದ ಕುಡಿಯುವ ನೀರು ಬರ್ತಿಲ್ಲ", dict(op="request", kn_text=True)),
           ("ನಮ್ಮ ಬೀದಿಯಲ್ಲಿ street light ಕೆಟ್ಟು ಹೋಗಿದೆ, ಪಿರಿಯಾಪಟ್ಟಣ ತಾಲ್ಲೂಕು", dict(op="request", kn_text=True)),
           ("ನನ್ನ ration card ಇನ್ನೂ ಬಂದಿಲ್ಲ, ಹುಣಸೂರು", dict(op="request", kn_text=True))]


def post(base, p, d):
    r = urllib.request.Request(base + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=180).read())


def drawn(ui) -> set:
    vals = set()
    for u in ui or []:
        if u.get("op") == "viz":
            for c in u.get("cards") or []:
                for it in c.get("items") or []:
                    try:
                        vals.add(int(round(float(it.get("value") or 0))))
                    except (TypeError, ValueError):
                        pass
    return vals


def judge(chk, say, ui, tools_said=""):
    bad = []
    if not say and not ui:
        bad.append("no answer")
    viz = [u for u in ui or [] if u.get("op") == "viz"]
    if "num" in chk:
        txt = (say + " " + tools_said).replace(",", "")
        if chk["num"] not in drawn(ui) and str(chk["num"]) not in txt:
            bad.append(f"expected {chk['num']} drawn or said; drawn {sorted(drawn(ui))[:10]}")
    if chk.get("board") and (not viz or len(viz[-1]["cards"]) < 3):
        bad.append(f"expected a board, got {[len(v['cards']) for v in viz]}")
    if chk.get("op") and not any(u.get("op") == chk["op"] for u in ui or []):
        bad.append(f"expected a {chk['op']} card")
    if chk.get("kn_text", True) and KN(say) < 6 and not chk.get("num"):
        bad.append("the answer is not in Kannada")
    if re.search(r"could not read the Sakala data|traceback", say, re.I):
        bad.append("error")
    return bad


def run_cascade(a):
    def one(item, sid=None, profile="cs"):
        group, q, chk = item
        sid = sid or post(a.base, "/api/session", {"profile": profile, "lang": "kn"})["session"]
        t = time.time()
        try:
            r = post(a.base, "/api/turn", {"session": sid, "text": q, "want_audio": False})
        except Exception as e:  # noqa: BLE001
            return group, q, ["http " + str(e)[:80]], 0, ""
        return group, q, judge(chk, r.get("say") or "", r.get("ui") or []), time.time() - t, r.get("say") or ""
    bank = [b for b in BANK if not a.only or a.only in b[0]]
    with cf.ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(one, bank))
    if not a.only or a.only in "seq":
        sid = post(a.base, "/api/session", {"profile": "cs", "lang": "kn"})["session"]
        res += [one(("seq-scope", q, c), sid) for q, c in SEQ]
    if not a.only or a.only in "citizen":
        res += [one(("citizen", q, c), None, "citizen") for q, c in CITIZEN]
    return res


async def run_live(a):
    import websockets
    W = a.base.replace("http", "ws")
    res = []

    async def session(profile, items):
        sid = post(a.base, "/api/session", {"profile": profile, "lang": "kn"})["session"]
        ev = []
        async with websockets.connect(f"{W}/ws/live?session={sid}", max_size=None) as ws:
            async def rd():
                try:
                    async for m in ws:
                        if isinstance(m, str):
                            ev.append(json.loads(m))
                except Exception:
                    pass
            tk = asyncio.create_task(rd())
            for _ in range(100):
                if any(e.get("type") in ("ready", "fallback") for e in ev):
                    break
                await asyncio.sleep(0.1)
            for group, q, chk in items:
                n = len(ev); t0 = time.time()
                await ws.send(json.dumps({"type": "text", "text": q}))
                tc = None
                for _ in range(500):
                    await asyncio.sleep(0.1)
                    tc = next((e for e in ev[n:] if e.get("type") == "turn_complete"), None)
                    if tc:
                        break
                tools = [e for e in ev[n:] if e.get("type") == "tool"]
                ui = [u for x in tools for u in x.get("ui") or []]
                said = (tc or {}).get("mitra", "")
                bad = judge(chk, said, ui, " ".join(x.get("say", "") for x in tools))
                if KN(said) < 6:
                    bad.append("not spoken in Kannada")
                res.append((group, q, bad, time.time() - t0, f"{[x['name'] for x in tools]} {said}"))
            tk.cancel()
    seen, pick = set(), []
    for b in BANK:
        if b[0] not in seen and (not a.only or a.only in b[0]):
            seen.add(b[0]); pick.append(b)
    import os
    sh = os.environ.get("SHARD", "")
    if sh:
        i, nsh = map(int, sh.split("/"))
        pick = pick[i::nsh]
    for item in pick:
        await session("cs", [item])
    if sh and not sh.startswith("0/"):
        return res
    if not a.only or a.only in "seq":
        await session("cs", [("seq-scope", q, c) for q, c in SEQ])
    if not a.only or a.only in "citizen":
        await session("citizen", [("citizen", q, c) for q, c in CITIZEN[:2]])
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    a.base = a.base or ("http://localhost:8030" if a.live else "http://localhost:8031")
    res = asyncio.run(run_live(a)) if a.live else run_cascade(a)
    ok = 0
    for g, q, bad, dt, say in res:
        ok += not bad
        print(f"  {'PASS' if not bad else 'FAIL'} [{g}] {q!r} ({dt:.1f}s){'' if not bad else '  <- ' + '; '.join(bad) + ' :: ' + say[:140]}")
    print(f"\n{ok}/{len(res)} passed ({'live' if a.live else 'cascade'})")
    Path(__file__).with_name(f"kn_bank_report{'_live' if a.live else ''}.json").write_text(
        json.dumps([{"group": g, "q": q, "bad": b, "secs": round(d, 1), "say": s[:300]} for g, q, b, d, s in res], ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(0 if ok == len(res) else 1)


if __name__ == "__main__":
    main()
