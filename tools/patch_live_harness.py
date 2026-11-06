"""Fixes from the second live CS-bank run (22 Oct 2026):
1. status words the model invents ('active', 'unresolved', 'ongoing', 'live', 'not closed') mean OPEN; an unknown status is
   ignored (never a false zero) in both the live caseload and the iPGRS sample;
2. 'overall / statewide' drops a department or place the model carried over from the screen unless the words name it;
3. the live voice HARNESS: if a data question ends without any function call (the model answered from memory), the server runs
   the deterministic router itself and pushes the picture to the screen, so every data answer still gets its visual;
4. the live bank recomputes each expected number right before its question (other tests file cases while it runs)."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def patch(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert old in s, f"{rel}: missing\n{old[:140]}"
        s = s.replace(old, new, 1)
    ast.parse(s)
    p.write_text(s, encoding="utf-8")
    print("patched", rel)


patch("app/server/query.py", [
    ('''STATUS_WORDS = {"open": OPEN, "pending": OPEN, "unresolved": OPEN, "outstanding": OPEN,''',
     '''STATUS_WORDS = {"open": OPEN, "pending": OPEN, "unresolved": OPEN, "outstanding": OPEN, "active": OPEN, "ongoing": OPEN, "live": OPEN,
                "in process": OPEN, "inprocess": OPEN, "not closed": OPEN, "not resolved": OPEN, "unattended": OPEN, "awaiting action": OPEN,'''),
    ('''    if st and st != "overdue":
        allowed = STATUS_WORDS.get(st) or tuple(s for s in ("Pending", "In progress", "Info requested", "Resolved", "Rejected", "Scrutiny") if _low(s) == st)
        keep("status", lambda r: r["status"] in allowed)''',
     '''    if st and st != "overdue":
        allowed = STATUS_WORDS.get(st) or tuple(s for s in ("Pending", "In progress", "Info requested", "Resolved", "Rejected", "Scrutiny") if _low(s) == st)
        if allowed:                                      # an unknown status word is ignored, never a false zero
            keep("status", lambda r: r["status"] in allowed)'''),
    ('''        s = {"open": "inprocess", "pending": "inprocess", "closed": "closed", "resolved": "resolved", "scrutiny": "scrutiny"}.get(s, s)
        where.append("lower(replace(status,' ','')) LIKE ?"); p.append(f"%{s.replace(' ', '')}%")''',
     '''        openish = ("open", "pending", "active", "unresolved", "outstanding", "ongoing", "live", "in process", "inprocess", "in progress", "not closed", "not resolved")
        s = "inprocess" if s in openish else {"closed": "closed", "disposed": "closed", "resolved": "resolved", "scrutiny": "scrutiny", "registered": "scrutiny"}.get(s, s)
        if s in ("inprocess", "closed", "resolved", "scrutiny"):     # an unknown status word is ignored, never a false zero
            where.append("lower(replace(status,' ','')) LIKE ?"); p.append(f"%{'registered' if s == 'scrutiny' else s}%")'''),
])

patch("mitra/server/query.py", [
    ('''    if s.get("profile") == "cs":
        args = board.scope_args(st, said, args, name)      # a follow-up stays inside the department / place on screen''',
     '''    if s.get("profile") == "cs" and board.CLEAR_RX.search(said):
        for k in ("department", "district", "taluk", "gp"):  # 'overall': drop what the model carried over from the screen
            if args.get(k) and str(args[k]).lower().split()[0] not in said.lower():
                args.pop(k, None)
    if s.get("profile") == "cs":
        args = board.scope_args(st, said, args, name)      # a follow-up stays inside the department / place on screen'''),
])

patch("mitra/server/live.py", [
    ('''                u, a = turn["user"].strip(), guard.scrub(turn["mitra"].strip())''',
     '''                u, a = turn["user"].strip(), guard.scrub(turn["mitra"].strip())
                if u and not turn["intent"]:
                    # the harness: a data question answered without any function call still gets its picture, from SQL
                    try:
                        cur = store.get_session(sid)
                        if cur and cur["profile"] in ("cs", "officer"):
                            rt = tools.route_question(u, cur["profile"], cur.get("state"))
                            if rt and rt[0] != "inbox" and query.handles(rt[0]):
                                res = await query.run(cur, rt[0], {**rt[1], "_text": u})
                                store.save_session(cur)
                                if res.get("ui"):
                                    await ws.send_json({"type": "tool", "name": rt[0], "say": res.get("say", ""), "ui": res["ui"], "auto": True})
                                    turn["intent"] = rt[0] + " (auto)"
                    except Exception as e:  # noqa: BLE001
                        STATS["last_error"] = f"auto picture: {str(e)[:120]}"'''),
])

patch("mitra/tests/cs_live_bank.py", [
    ('''def check(chk):
    def f(n, s, t):''',
     '''def fresh(q, chk):
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
            chk = fresh(q, chk)'''),
    ('''        out.append((q, check(chk)))''', '''        out.append((q, check(chk, q)))'''),
    ('''    await LB.session("cs", [(q, check(c)) for q, c in CB.SEQ])''', '''    await LB.session("cs", [(q, check(c, q)) for q, c in CB.SEQ])'''),
])
print("done")
