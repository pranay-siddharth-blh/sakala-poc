"""The Chief Secretary bank on the REAL live voice (22 Oct 2026): one question per group from tests/cs_bank.py, in one or two
sessions (so follow-ups and the scope are exercised), checking the function called, that a visual was drawn, and that the
number spoken matches the database. Run from mitra/: PYTHONIOENCODING=utf-8 python tests/cs_live_bank.py [base]"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cs_bank as CB  # noqa: E402
import live_battery as LB  # noqa: E402

if len(sys.argv) > 1:
    LB.B = sys.argv[1]; LB.W = LB.B.replace("http", "ws")
else:
    LB.B = "http://localhost:8030"; LB.W = "ws://localhost:8030"


def fresh(q, chk):
    """The expected number recomputed right before the question (other tests file cases while this runs)."""
    import importlib
    importlib.reload(CB)
    for g, q2, c2 in CB.BANK:
        if q2 == q:
            return c2
    for q2, c2 in CB.SEQ:
        if q2 == q:
            return c2
    return chk


def check(chk, q=None):
    def f(n, s, t):
        nonlocal chk
        if q:
            chk = fresh(q, chk)
        viz = [u for x in t for u in x["ui"] if u.get("op") == "viz"]
        if not n or not viz:
            return False
        if chk.get("board") and max(len(v["cards"]) for v in viz) < 3:
            return False
        if "num" in chk:
            said = s.replace(",", "")
            spoken = " ".join(x.get("say", "") for x in t).replace(",", "")
            return str(chk["num"]) in said or str(chk["num"]) in spoken
        return True
    return f


def pick():
    seen, out = set(), []
    for g, q, chk in CB.BANK:
        if g in seen or g.startswith("edge"):
            continue
        seen.add(g)
        out.append((q, check(chk, q)))
    return out


async def main():
    import os
    qs = pick()
    sh = os.environ.get("SHARD", "")
    if sh:
        i, nsh = map(int, sh.split("/"))
        qs = qs[i::nsh]
    print(f"[{len(qs)} questions, one per group, real live voice, a fresh session each (no scope carried)]")
    for i in range(0, len(qs), 1):
        await LB.session("cs", qs[i:i + 1])
    if not sh or sh.startswith("0/"):
        print("[scoped follow-ups]")
        await LB.session("cs", [(q, check(c, q)) for q, c in CB.SEQ])
    print(f"\n{LB.ok}/{LB.ok + LB.fail} checks passed")
    for f in LB.FAILS:
        print("  FAIL:", f)


asyncio.run(main())
