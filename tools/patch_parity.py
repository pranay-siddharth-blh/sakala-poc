"""WhatsApp and Sakala Mitra run the SAME routing pipeline (19 Oct 2026, Pranay). Two places where WhatsApp still differed:
1. The completion step's answer (a village / GP / taluk typed by the citizen) is resolved by one shared function,
   chat.place_reply, for both channels: a taluk named outright beats a look-alike village elsewhere, and a bare taluk
   name means that taluk (GP list, or straight to confirm for a taluk-level officer) instead of a new complaint.
2. An unclear request is offered to the human scrutiny desk and filed only on a yes (Mitra already did this), so junk
   typed into WhatsApp never becomes a case."""
import io

ROOT = r"D:\Sakala POC"


def edit(path, pairs):
    p = ROOT + "\\" + path
    s = io.open(p, encoding="utf-8").read()
    for a, b in pairs:
        assert s.count(a) == 1, (path, a[:90], s.count(a))
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("patched", path)


edit(r"app\server\chat.py", [
    # one resolver for the completion step, used by WhatsApp and by Mitra's /api/intake place step
    ('''def ask_gp(o, tk):''',
     '''def place_reply(text, taluk_hint=""):
    """Stage 4 (completion): the citizen's answer to "where is it?" resolved the same way on every channel.
    Returns (place or None, taluk named outright or "")."""
    cands = local_ai.place_candidates(text)
    named_tk = taluk_in_text(text)
    place = resolve_place(*cands, taluk_hint=named_tk or taluk_hint) if cands else None
    if place and named_tk and place["taluk"] != named_tk:     # a taluk named outright beats a look-alike village elsewhere (Hunsur != Hunur)
        place = None
    return place, named_tk or ""


def ask_gp(o, tk):'''),
    ('''    if o.st.get("flow") in ("ask_place", "ask_gp"):
        place = resolve_place(*local_ai.place_candidates(text), taluk_hint=o.st["draft"].get("taluk", ""))
        if place:
            o.st["draft"].update(gp=place["gp"], taluk=place["taluk"], village=place["village"], how="village typed by the citizen")
            o.stage(3, f"Village: {place['village']} → {place['gp']} GP, {place['taluk']}")
            return confirm(o)
        if o.st["flow"] == "ask_gp":
            o.bot(o.t("I could not find that village in the pilot area. Please pick from the list or check the spelling.",
                      "ಆ ಗ್ರಾಮ ಸಿಗಲಿಲ್ಲ. ಪಟ್ಟಿಯಿಂದ ಆಯ್ಕೆ ಮಾಡಿ."))
            return
    grievance(o, sid, text, via="text")''',
     '''    if o.st.get("flow") in ("ask_place", "ask_gp") and (o.st.get("draft") or {}).get("u"):
        place, tk = place_reply(text, o.st["draft"].get("taluk", ""))
        if place:
            o.st["draft"].update(gp=place["gp"], taluk=place["taluk"], village=place["village"], how="village typed by the citizen")
            o.stage(3, f"Village: {place['village']} → {place['gp']} GP, {place['taluk']}")
            return confirm(o)
        if tk:                                                  # a taluk alone: taluk-level officer -> confirm, else its GP list
            from .routing import route
            rt = route(o.st["draft"]["u"]["service_id"], tk, "")
            if rt and not rt["need_gp"]:
                o.st["draft"].update(gp="", taluk=tk, village="", how="taluk named by the citizen")
                o.stage(3, f"Taluk: {tk} · taluk-level officer, no village needed")
                return confirm(o)
            o.stage(3, f"Taluk: {tk} · asking for the Gram Panchayat", "run")
            return ask_gp(o, tk)
        if o.st["flow"] == "ask_gp" or len(text.split()) <= 3:   # a short answer that is no place we know: ask again, never a new case
            o.bot(o.t("I could not find that village. Please pick from the list, share your location, or check the spelling.",
                      "ಆ ಗ್ರಾಮ ಸಿಗಲಿಲ್ಲ. ಪಟ್ಟಿಯಿಂದ ಆಯ್ಕೆ ಮಾಡಿ ಅಥವಾ ಸ್ಥಳ ಹಂಚಿಕೊಳ್ಳಿ."),
                  buttons=[{"label": "📍 Share location", "action": "loc:share", "silent": True},
                           {"label": "Piriyapatna", "action": "tk:Piriyapatna"}, {"label": "Hunsur", "action": "tk:Hunsur"}])
            return
    grievance(o, sid, text, via="text")'''),
    # an unclear request: ask before it goes to the scrutiny desk (same as Mitra); junk is never filed
    ('''    if u["intent"] == "UNCLEAR":
        o.stage(2, "Unclear · no category matches well", "warn")
        cid = pipeline.scrutiny_case(text, masked, u, src, session=sid)
        o.bot(o.t(f"I want to be sure this reaches the right office, so a <b>person at the scrutiny desk</b> will check it. "
                  f"Reference <b>{cid}</b>. You will hear from us here. 🙏",
                  f"ಸರಿಯಾದ ಕಚೇರಿಗೆ ತಲುಪಲು <b>ಪರಿಶೀಲನಾ ಅಧಿಕಾರಿ</b> ಇದನ್ನು ನೋಡುತ್ತಾರೆ. ಸಂಖ್ಯೆ <b>{cid}</b>. 🙏"))
        return menu(o)''',
     '''    if u["intent"] == "UNCLEAR":
        o.stage(2, "Unclear · no category matches well · asking the citizen", "warn")
        o.st.update(flow="scrutiny_ask", draft={"text": text, "masked": masked, "u": {k: v for k, v in u.items() if k != "similar"}, "src": src})
        o.bot(o.t("I am not sure which office handles this. Shall I send it to a <b>person at the scrutiny desk</b> who will route it, "
                  "or would you like to describe the problem again?",
                  "ಇದು ಯಾವ ಕಚೇರಿಗೆ ಸೇರಿದೆ ಎಂದು ಖಚಿತವಿಲ್ಲ. <b>ಪರಿಶೀಲನಾ ಅಧಿಕಾರಿಗೆ</b> ಕಳುಹಿಸಲೇ, ಅಥವಾ ಸಮಸ್ಯೆಯನ್ನು ಮತ್ತೆ ವಿವರಿಸುವಿರಾ?"),
              buttons=[{"label": o.t("✅ Send to the scrutiny desk", "✅ ಪರಿಶೀಲನಾ ಡೆಸ್ಕ್‌ಗೆ ಕಳುಹಿಸಿ"), "action": "scrutiny:yes"},
                       {"label": o.t("✏️ Describe it again", "✏️ ಮತ್ತೆ ವಿವರಿಸಿ"), "action": "grievance"}])
        return'''),
    ('''        elif a.startswith("case:"):
            case_card(o, sid, a[5:])''',
     '''        elif a.startswith("case:"):
            case_card(o, sid, a[5:])
        elif a == "scrutiny:yes":
            d = st.get("draft") or {}
            if st.get("flow") != "scrutiny_ask" or not d.get("text"):
                menu(o)
            else:
                cid = pipeline.scrutiny_case(d["text"], d["masked"], {**d["u"], "intent": "UNCLEAR"}, d["src"], session=sid)
                o.stage(2, "Unclear · the citizen asked for the scrutiny desk", "warn")
                o.stage(5, f"Scrutiny desk · {cid}")
                st.update(flow="done", draft={})
                o.bot(o.t(f"Sent. A <b>person at the scrutiny desk</b> will route it to the right office. Reference <b>{cid}</b>. You will hear from us here. 🙏",
                          f"ಕಳುಹಿಸಲಾಗಿದೆ. <b>ಪರಿಶೀಲನಾ ಅಧಿಕಾರಿ</b> ಸರಿಯಾದ ಕಚೇರಿಗೆ ಕಳುಹಿಸುತ್ತಾರೆ. ಸಂಖ್ಯೆ <b>{cid}</b>. 🙏"),
                      buttons=[{"label": "🔎 Track", "action": f"case:{cid}"}, {"label": "🏠 Main menu", "action": "menu"}])'''),
])

edit(r"app\server\api.py", [
    ('''        cands = local_ai.place_candidates(r.text)
        named_tk = chat.taluk_in_text(r.text)
        place = _resolve_place(*cands, taluk_hint=named_tk or r.taluk) if cands else None
        if place and named_tk and place["taluk"] != named_tk:   # a taluk named outright beats a look-alike village elsewhere (Hunsur ≠ Hunur, Lingsugur)
            place = None
        if place:''',
     '''        place, named_tk = chat.place_reply(r.text, r.taluk)   # the same completion step WhatsApp uses
        if place:'''),
])
print("done")
