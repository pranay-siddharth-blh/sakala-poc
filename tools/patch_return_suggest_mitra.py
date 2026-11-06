"""22 Oct 2026 (Pranay): Mitra side of 'return with a suggestion'. The officer can say who should have the case and / or
where it belongs ('not my jurisdiction, send it to the Tahsildar of Hunsur', 'this is Attigodu GP', 'Hunsur ಗೆ ಕಳಿಸಿ');
with either the case goes straight to that officer (who gets the 'Assigned to you' card and hears it), otherwise to the
scrutiny desk. The read-back names the suggestion; the reply names who holds it now."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def patch(rel, pairs, py=True):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert old in s, f"{rel}: missing\n{old[:160]}"
        s = s.replace(old, new, 1)
    if py:
        ast.parse(s)
    assert "\x08" not in s
    p.write_text(s, encoding="utf-8")
    print("patched", rel)


patch("mitra/server/brain.py", [
    ('''    "return_case":    (("officer",), "Return the case: not my jurisdiction / wrong office. `reason` optional.", ("reason",)),''',
     '''    "return_case":    (("officer",), "Return the case: not my jurisdiction / wrong office. `reason` optional. If the officer says who "
                                      "should have it, put that in `to` (a name or role, in English: 'PDO Attigodu', 'Tahsildar Hunsur', "
                                      "'the AEE'); if they say where it belongs, put the taluk / Gram Panchayat / village in `place` "
                                      "(English letters: ಹುಣಸೂರು -> Hunsur). Either one sends it straight to that officer, who is notified; "
                                      "with neither it goes to the scrutiny desk.", ("reason", "to", "place")),'''),
    ('''        if has("not my jurisdiction", "not mine", "wrong office", "return it", "return this", "send it back", "belongs to another"):
            return {"intent": "return_case", "reason": t}''',
     '''        if has("not my jurisdiction", "not mine", "wrong office", "return it", "return this", "send it back", "belongs to another",
               "not under me", "outside my jurisdiction", "transfer it", "transfer this", "forward it to", "send it to the") or \\
                re.search(r"ನನ್ನ ವ್ಯಾಪ್ತಿ|ವ್ಯಾಪ್ತಿಗೆ ಬರಲ್ಲ|ವ್ಯಾಪ್ತಿಗೆ ಬರುವುದಿಲ್ಲ|ವಾಪಸ್ ಕಳಿಸಿ|ಹಿಂದಿರುಗಿಸಿ", t):
            out = {"intent": "return_case", "reason": "Location is outside my jurisdiction"}
            m = re.search(r"\\b(?:send|give|pass|transfer|forward|route|move|return)\\s+(?:it|this|the case)?\\s*(?:back\\s+)?to\\s+(.+)$|"
                          r"\\b(?:should go to|belongs to|is for|it'?s for|meant for|handled by|goes to|comes under|falls under)\\s+(.+)$", t, re.I)
            sug = (m.group(1) or m.group(2)) if m else ""
            if not sug and re.search(r"ಗೆ ಕಳಿಸಿ|ಗೆ ಕಳುಹಿಸಿ|ಗೆ ವರ್ಗಾಯಿಸಿ|ಗೆ ಸೇರಿದ್ದು|ಗೆ ಬರುತ್ತೆ|ಗೆ ಬರುತ್ತದೆ", t):
                sug = t                                      # Kannada: the POC finds the taluk / role in the sentence
            sug = re.sub(r"^(the\\s+)?(scrutiny desk|another (office|department))\\b.*$", "", (sug or "").strip(" .,!?"), flags=re.I)
            if sug and not re.fullmatch(r"(another|other|someone|somebody)( one| office| officer| department)?", sug, re.I):
                out["to"] = sug[:120]
            return out'''),
])

patch("mitra/server/tools.py", [
    ('''    if intent == "return_case":
        return f"Return {what} to the scrutiny desk as outside your jurisdiction? Shall I go ahead?"''',
     '''    if intent == "return_case":
        sug = " · ".join(x for x in ((args.get("to") or "").strip(), (args.get("place") or "").strip()) if x)
        if sug:
            return f"Return {what} as outside your jurisdiction and send it straight to {sug}? They will be notified. Shall I go ahead?"
        return f"Return {what} to the scrutiny desk as outside your jurisdiction? Shall I go ahead?"'''),
    ('''async def t_return_case(sess, args):
    cid, r = await _act(sess, "return", reason=args.get("reason") or "Location is outside my jurisdiction", heard=args.get("_text", ""))
    if not cid or r.get("refused"):
        return r
    return {"say": f"{cid} returned to the scrutiny desk as not your jurisdiction.", "ui": await _refresh_case_ui(sess)}''',
     '''async def t_return_case(sess, args):
    to, place = (args.get("to") or "").strip(), (args.get("place") or "").strip()
    reason = args.get("reason") or "Location is outside my jurisdiction"
    if len(reason) > 120 or reason.strip().lower() == (args.get("_text") or "").strip().lower():
        reason = "Location is outside my jurisdiction"           # the whole sentence is not a reason
    cid, r = await _act(sess, "return", reason=reason, to=to, place=place, heard=args.get("_text", ""))
    if not cid or r.get("refused"):
        return r
    ui = await _refresh_case_ui(sess)
    rt = r.get("routed_to")
    if rt:
        say = (f"Done. {cid} is not yours, so it has gone straight to {rt.get('short') or rt.get('name')}, who now holds it with a fresh "
               f"clock and has been notified. The citizen has been told too.")
        return {"say": say, "data": {"routed_to": rt, "how": r.get("how")},
                "ui": ui + [{"op": "toast", "h": "Transferred", "m": f"{cid} → {rt.get('short')} · notified"}]}
    if r.get("suggestion_unmatched"):
        say = (f"I could not match {r['suggestion_unmatched']} to an officer"
               + (" (it points back to you)" if "back to the returning officer" in (r.get("why_unmatched") or "") else "")
               + f", so {cid} has gone to the scrutiny desk, which will route it. You can name the officer or the taluk next time.")
    else:
        say = f"{cid} returned to the scrutiny desk as not your jurisdiction. If you know who should have it, name the officer or the place and I will send it straight there."
    return {"say": say, "ui": ui}'''),
])

patch("mitra/server/sync.py", [
    ('''    if "returned" in w:
        return "returned"''',
     '''    if w.startswith("transferred to"):                  # returned with a suggestion: straight to the suggested officer
        return "rerouted"
    if "returned" in w:
        return "returned"'''),
])

patch("mitra/server/notify.py", [
    ('''            c.update(tone="new", icon="↪", title=f"Assigned to you · {cid}", body=f"The scrutiny desk sent you {svc}{' · ' + place if place else ''}",
                     actions=open_, speak=f"{cid} was assigned to you by the scrutiny desk.")''',
     '''            if what.lower().startswith("transferred to"):
                frm = r.get("who") or "another officer"
                c.update(tone="new", icon="↪", title=f"Transferred to you · {cid}", body=f"{frm} sent you {svc}{' · ' + place if place else ''}: not their jurisdiction",
                         actions=open_, speak=f"{cid} was transferred to you by {frm}: it was not in their jurisdiction.", sticky=True)
            else:
                c.update(tone="new", icon="↪", title=f"Assigned to you · {cid}", body=f"The scrutiny desk sent you {svc}{' · ' + place if place else ''}",
                         actions=open_, speak=f"{cid} was assigned to you by the scrutiny desk.")'''),
    ('''        c.update(tone="info", icon="↪", title=f"Now with {owner_short}", body=f"The scrutiny desk found the right office for {cid}.")''',
     '''        c.update(tone="info", icon="↪", title=f"Now with {owner_short}",
                 body=(f"{cid} was outside the first officer's jurisdiction, so it went straight to the right office." if what.lower().startswith("transferred to")
                       else f"The scrutiny desk found the right office for {cid}."))'''),
])
print("done")
