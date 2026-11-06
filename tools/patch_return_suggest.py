"""22 Oct 2026 (Pranay): a return with a suggestion goes straight to the suggested officer / place; only a return with
nothing usable goes to the scrutiny desk. POC action + citizen message + drawer form; Mitra voice + notifications."""
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


# ------------------------------------------------------------------ POC: the return action
patch("app/server/api.py", [
    ('''    to: str = ""
    via: str = ""''',
     '''    to: str = ""
    place: str = ""      # return: where the case really belongs (taluk / GP / village), optional
    via: str = ""'''),
    ('''    elif a.action == "return":
        event(cid, who, "Returned: not my jurisdiction", "#c98a00", (a.reason or "Wrong jurisdiction") + ". Logged as a routing correction for the learning loop."); status("Scrutiny")
        message_citizen(cid, me["id"], "returned")
        out["toast"] = ["Returned", "Sent to the scrutiny desk for re-routing"]''',
     '''    elif a.action == "return":
        from . import transfer
        why = a.reason or "Wrong jurisdiction"
        sug = transfer.resolve(dict(c), a.to, a.place, me["id"]) if (a.to or a.place) and c["kind"] != "APPLICATION" else \\
            {"officer": None, "place": None, "how": "a Sakala application follows its own ladder" if (a.to or a.place) else "", "asked": " · ".join(x for x in (a.to, a.place) if x)}
        target = sug["officer"]
        if target:
            # the suggestion names a real officer: the case goes straight to them, with a fresh clock, and they are told
            pl = sug.get("place") or {}
            new_taluk = pl.get("taluk") or target.get("taluk") or c["taluk"]
            new_gp = pl.get("gp") if pl.get("gp") else (c["gp"] if new_taluk == c["taluk"] else "")
            new_dist = pl.get("district") or target.get("district") or c["district"]
            audit = json.loads(c["audit"]) if c.get("audit") else {}
            audit["human_decision"] = {"by": who, "to": target["id"], "note": f"Returned as not my jurisdiction; suggested {sug['asked']}",
                                       "how": sug["how"], "at": now().isoformat(timespec="seconds")}
            db.run("UPDATE cases SET owner=?, level=?, level_since=?, status='Pending', route_basis=?, audit=?, taluk=?, gp=?, district=?, "
                   "village=CASE WHEN ?<>'' THEN ? ELSE village END WHERE id=?",
                   (target["id"], target["level"], now().isoformat(), f"Transferred by {who} (not their jurisdiction) to {target['short']}: {sug['how']}",
                    json.dumps(audit), new_taluk, new_gp or "", new_dist, pl.get("village") or "", pl.get("village") or "", cid))
            event(cid, who, f"Transferred to {target['short']}", "#0e9f6e",
                  f"Returned as not my jurisdiction ({why}); suggested: {sug['asked']} → {target['short']} ({sug['how']}). Clock restarted. Logged as a routing correction for the learning loop.")
            notify(target["id"], f"{cid} transferred to you by {who}: not their jurisdiction")
            message_citizen(cid, target["id"], "transferred", who)
            out.update(routed_to={"id": target["id"], "short": target["short"], "name": target["name"], "level": target["level"]},
                       how=sug["how"], scrutiny=False)
            out["toast"] = ["Transferred", f"{cid} → {target['short']} · notified"]
        else:
            note = why + (f" · suggested: {sug['asked']} (no matching officer" + (f": {sug['how']}" if sug.get("how") else "") + ")" if sug.get("asked") else "")
            event(cid, who, "Returned: not my jurisdiction", "#c98a00", note + ". Logged as a routing correction for the learning loop."); status("Scrutiny")
            message_citizen(cid, me["id"], "returned")
            out.update(scrutiny=True, suggestion_unmatched=sug.get("asked") or "", why_unmatched=sug.get("how") or "")
            out["toast"] = ["Returned", "Sent to the scrutiny desk for re-routing" + (" · the suggestion matched no officer" if sug.get("asked") else "")]'''),
])

patch("app/server/chat.py", [
    ('''    "routed": ("📍 <b>{cid}</b> has been checked by the scrutiny desk and is now with <b>{off}</b>. {text}",''',
     '''    "transferred": ("↪️ <b>{cid}</b> was outside the jurisdiction of {text}, so it has been sent straight to <b>{off}</b>, who now holds it. You will hear from them here.",
                    "↪️ <b>{cid}</b> {text} ಅವರ ವ್ಯಾಪ್ತಿಗೆ ಬರದ ಕಾರಣ ನೇರವಾಗಿ <b>{off}</b> ಅವರಿಗೆ ಕಳುಹಿಸಲಾಗಿದೆ. ಅವರಿಂದ ಇಲ್ಲೇ ಮಾಹಿತಿ ಬರುತ್ತದೆ."),
    "routed": ("📍 <b>{cid}</b> has been checked by the scrutiny desk and is now with <b>{off}</b>. {text}",'''),
])

# drawer form (generator + the generated app page; the wireframe keeps its simulated version)
OLD_FORM = '''<div class="field"><label>Suggest correct office (optional)</label><input id="retS" placeholder="e.g. PDO Attigodu"></div><button class="btn primary sm" id="doRet">Return to scrutiny desk</button>`); $('#doRet').onclick=()=>act({action:'return', reason:$('#retR').value+($('#retS').value?' · suggested: '+$('#retS').value:'')}, true); };'''
NEW_FORM = '''<div class="field"><label>Suggest the right officer (optional)</label><input id="retS" placeholder="e.g. PDO Attigodu, Tahsildar Hunsur"></div><div class="field"><label>Or where it belongs (optional)</label><input id="retP" placeholder="taluk, Gram Panchayat or village, e.g. Hunsur"></div><div class="tiny" id="retHint" style="margin:-4px 0 10px;opacity:.75">With an officer or a place it goes straight to that officer, who is notified. With neither, the scrutiny desk routes it.</div><button class="btn primary sm" id="doRet">Return to scrutiny desk</button>`); const _rl=()=>{ $('#doRet').textContent=($('#retS').value.trim()||$('#retP').value.trim())?'Send to the suggested officer':'Return to scrutiny desk'; }; $('#retS').oninput=_rl; $('#retP').oninput=_rl; $('#doRet').onclick=()=>act({action:'return', reason:$('#retR').value, to:$('#retS').value.trim(), place:$('#retP').value.trim()}, true); };'''
patch("tools/make_app_ui.py", [(OLD_FORM, NEW_FORM)], py=False)
patch("app/web/index.html", [(OLD_FORM, NEW_FORM)], py=False)
print("done")
