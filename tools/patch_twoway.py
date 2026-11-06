"""Two-way WhatsApp: officer actions reach the citizen's chat; the citizen can reply and give feedback."""
import sys

APP = sys.argv[1] if len(sys.argv) > 1 else r"D:\Sakala POC\app"


def edit(p, old, new, count=1):
    s = open(p, encoding="utf-8").read()
    assert old in s, (p, old[:70])
    open(p, "w", encoding="utf-8").write(s.replace(old, new, count))


p = APP + r"\server\chat.py"
edit(p, "from .sla import now, officer, create_application, sla_info, chain", "from .sla import now, officer, create_application, sla_info, chain, event, notify")
edit(p, '''    def me(self, type_, html_=""):''', '''    def officer_msg(self, html_, off, case_id, **kw):
        self.ev.append({"kind": "msg", "me": False, "type": "officer", "html": html_, "officer": off["short"], "officerFull": off["name"],
                        "caseId": case_id, **kw})

    def me(self, type_, html_=""):''')
edit(p, '''    try:
        if a == "start":
            start(o)''', '''    try:
        if a == "poll":
            pass                                    # only deliver pending officer messages (below)
        elif a == "start":
            start(o)''')
edit(p, '''        elif a == "submit":
            submit(o, sid)''', '''        elif a.startswith("reply:"):
            start_reply(o, a[6:])
        elif a.startswith("fb:"):
            feedback(o, sid, a[3:])
        elif a == "submit":
            submit(o, sid)''')
edit(p, '''        elif req.get("text", "").strip():
            free_text(o, sid, req["text"].strip())''', '''        elif req.get("text", "").strip():
            free_text(o, sid, req["text"].strip())
        if a != "start":
            deliver(o, sid)''')
edit(p, '''def photo(o, sid, req):
    if o.st.get("flow") in ("apply_doc", "apply_village") and o.st.get("draft", {}).get("gp"):
        return apply_doc(o, sid)''', '''def photo(o, sid, req):
    if o.st.get("flow") == "reply" and (o.st.get("draft") or {}).get("case"):
        o.me("image", "")
        return send_reply(o, sid, "Photo of the site attached", photo=True)
    if o.st.get("flow") in ("apply_doc", "apply_village") and o.st.get("draft", {}).get("gp"):
        return apply_doc(o, sid)''')
edit(p, '''    if low.startswith(("track", "status", "ಸ್ಥಿತಿ")):
        return track(o, sid)''', '''    if low.startswith(("track", "status", "ಸ್ಥಿತಿ")):
        return track(o, sid)
    if o.st.get("flow") == "reply" and (o.st.get("draft") or {}).get("case"):
        return send_reply(o, sid, text)''')
edit(p, '''        st = ("✅ Resolved" if c["status"] == "Resolved" else f"⚠️ {-s['left']} days overdue · escalated" if s["left"] < 0 else f"⏳ {s['left']} days left")
        cls = "ok" if c["status"] == "Resolved" else "bad" if s["left"] < 0 else ""''', '''        st = ("✅ Resolved" if c["status"] == "Resolved" else "❌ Rejected · you can appeal" if c["status"] == "Rejected" else
              "📩 Officer asked for information · reply in this chat" if c["status"] == "Info requested" else
              f"⚠️ {-s['left']} days overdue · escalated" if s["left"] < 0 else f"⏳ {s['left']} days left")
        cls = "ok" if c["status"] == "Resolved" else "bad" if s["left"] < 0 or c["status"] == "Rejected" else ""''')

NEW = r'''# ---------------- officer → citizen (two-way WhatsApp) ----------------
KIND_TEXT = {
    "accepted": ("✅ <b>{off}</b> has accepted your request <b>{cid}</b> and started working on it.",
                 "✅ <b>{off}</b> ನಿಮ್ಮ ಅರ್ಜಿ <b>{cid}</b> ಸ್ವೀಕರಿಸಿ ಕೆಲಸ ಪ್ರಾರಂಭಿಸಿದ್ದಾರೆ."),
    "info": ("📩 <b>{off}</b> needs more information on <b>{cid}</b>:<br><i>“{text}”</i>",
             "📩 <b>{off}</b> ಅವರಿಗೆ <b>{cid}</b> ಬಗ್ಗೆ ಹೆಚ್ಚಿನ ಮಾಹಿತಿ ಬೇಕು:<br><i>“{text}”</i>"),
    "resolved": ("🎉 <b>{off}</b> has marked <b>{cid}</b> as resolved.<br><span class=\"wa-muted\">Action taken: “{text}”</span><br><br>Was your problem actually solved?",
                 "🎉 <b>{off}</b> <b>{cid}</b> ಅನ್ನು ಪರಿಹರಿಸಲಾಗಿದೆ ಎಂದು ಗುರುತಿಸಿದ್ದಾರೆ.<br><span class=\"wa-muted\">ಕೈಗೊಂಡ ಕ್ರಮ: “{text}”</span><br><br>ನಿಮ್ಮ ಸಮಸ್ಯೆ ನಿಜವಾಗಿ ಬಗೆಹರಿಯಿತೇ?"),
    "rejected": ("❌ <b>{off}</b> could not accept <b>{cid}</b>.<br><i>Reason: {text}</i><br><span class=\"wa-muted\">You can appeal to the senior officer within 30 days.</span>",
                 "❌ <b>{off}</b> <b>{cid}</b> ಅನ್ನು ಸ್ವೀಕರಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ.<br><i>ಕಾರಣ: {text}</i><br><span class=\"wa-muted\">30 ದಿನಗಳೊಳಗೆ ಮೇಲ್ಮನವಿ ಸಲ್ಲಿಸಬಹುದು.</span>"),
    "returned": ("↩️ <b>{cid}</b> is being re-checked by the scrutiny desk to find the right office. You will hear from us here.",
                 "↩️ <b>{cid}</b> ಸರಿಯಾದ ಕಚೇರಿ ಗುರುತಿಸಲು ಪರಿಶೀಲನಾ ಡೆಸ್ಕ್‌ನಲ್ಲಿ ಮರುಪರಿಶೀಲನೆಯಾಗುತ್ತಿದೆ."),
    "escalated": ("⏫ <b>{cid}</b> was not acted on in time, so it has moved up to <b>{off}</b> automatically. <span class=\"wa-muted\">({text})</span>",
                  "⏫ <b>{cid}</b> ಸಮಯಕ್ಕೆ ಕ್ರಮವಾಗದ ಕಾರಣ ಸ್ವಯಂಚಾಲಿತವಾಗಿ <b>{off}</b> ಅವರಿಗೆ ವರ್ಗಾಯಿಸಲಾಗಿದೆ."),
    "compensation": ("💰 Sakala compensation of <b>₹{text}</b> has been ordered for the delay on <b>{cid}</b> (₹20 per day, Sakala Act s.9).",
                     "💰 <b>{cid}</b> ವಿಳಂಬಕ್ಕೆ ಸಕಾಲ ಪರಿಹಾರ <b>₹{text}</b> ಆದೇಶಿಸಲಾಗಿದೆ (ದಿನಕ್ಕೆ ₹20)."),
}


def deliver(o, sid):
    """Push every undelivered officer message for this chat as an incoming WhatsApp message."""
    rows = db.q("SELECT * FROM citizen_msgs WHERE session=? AND delivered=0 ORDER BY id", (sid,))
    for m in rows:
        off = officer(m["officer_id"]) or {"short": "Sakala desk", "name": "Sakala desk"}
        en, kn = KIND_TEXT.get(m["kind"], ("{off}: {text}", "{off}: {text}"))
        html = o.t(en, kn).format(off=E(off["short"]), cid=m["case_id"], text=E(m["text"] or ""))
        btns = None
        if m["kind"] == "info":
            btns = [{"label": o.t("✍️ Reply now", "✍️ ಈಗ ಉತ್ತರಿಸಿ"), "action": f"reply:{m['case_id']}"},
                    {"label": o.t("Later", "ನಂತರ"), "action": "later", "silent": True}]
        elif m["kind"] == "resolved":
            btns = [{"label": o.t("👍 Yes, solved", "👍 ಹೌದು, ಬಗೆಹರಿಯಿತು"), "action": f"fb:{m['case_id']}:yes"},
                    {"label": o.t("👎 No, not solved", "👎 ಇಲ್ಲ, ಬಗೆಹರಿದಿಲ್ಲ"), "action": f"fb:{m['case_id']}:no"}]
        o.officer_msg(html, off, m["case_id"], buttons=btns)
        db.run("UPDATE citizen_msgs SET delivered=1 WHERE id=?", (m["id"],))
    if rows:
        last = officer(rows[-1]["officer_id"])
        o.ev.append({"kind": "notify", "n": len(rows), "from": last["short"] if last else "Sakala"})


def start_reply(o, cid):
    c = db.q1("SELECT * FROM cases WHERE id=?", (cid,))
    if not c:
        return menu(o)
    o.st.update(flow="reply", draft={"case": cid})
    o.chips(None)
    o.bot(o.t(f"Type your reply to <b>{E(officer(c['owner'])['short'])}</b>, or send a <b>📷 photo</b> of the problem. It goes straight into the officer's file.",
              f"<b>{E(officer(c['owner'])['short'])}</b> ಅವರಿಗೆ ಉತ್ತರ ಟೈಪ್ ಮಾಡಿ ಅಥವಾ <b>📷 ಫೋಟೋ</b> ಕಳುಹಿಸಿ."))


def send_reply(o, sid, text, photo=False):
    cid = o.st["draft"]["case"]
    c = db.q1("SELECT * FROM cases WHERE id=?", (cid,))
    if not c:
        o.st.update(flow="menu", draft={})
        return menu(o)
    masked = pipeline.mask(text)[0]
    event(cid, "Citizen (WhatsApp)", "Citizen replied" + (" with a photo" if photo else ""), "#128c4b", masked)
    if c["status"] == "Info requested":
        db.run("UPDATE cases SET status='In progress' WHERE id=?", (cid,))
    notify(c["owner"], f"Citizen replied on {cid}: {masked[:80]}")
    o.st.update(flow="menu", draft={})
    o.bot(o.t(f"✓ Sent to <b>{E(officer(c['owner'])['short'])}</b> and added to the file of <b>{cid}</b>. You can send more any time.",
              f"✓ <b>{E(officer(c['owner'])['short'])}</b> ಅವರಿಗೆ ಕಳುಹಿಸಲಾಗಿದೆ · <b>{cid}</b>."),
          buttons=[{"label": o.t("✍️ Add more", "✍️ ಇನ್ನಷ್ಟು ಸೇರಿಸಿ"), "action": f"reply:{cid}"}, {"label": "🏠 Main menu", "action": "menu"}])
    o.ev.append({"kind": "toast", "h": "Reply delivered", "m": f"{cid} → {officer(c['owner'])['short']}"})


def feedback(o, sid, arg):
    cid, ans = arg.rsplit(":", 1)
    c = db.q1("SELECT * FROM cases WHERE id=?", (cid,))
    if not c:
        return menu(o)
    if ans == "yes":
        event(cid, "Citizen (WhatsApp)", "Citizen confirmed: problem solved 👍", "#1f9d57", "Feedback taken on WhatsApp")
        db.run("UPDATE cases SET status='Resolved' WHERE id=?", (cid,))
        o.bot(o.t("Thank you 🙏 Your feedback is recorded against the officer's report. Glad it is solved!", "ಧನ್ಯವಾದಗಳು 🙏 ನಿಮ್ಮ ಅಭಿಪ್ರಾಯ ದಾಖಲಾಗಿದೆ."))
    else:
        event(cid, "Citizen (WhatsApp)", "Citizen says NOT solved · re-opened 👎", "#c8372d", "Back to the officer; the senior officer is informed")
        db.run("UPDATE cases SET status='Pending', level_since=? WHERE id=?", (now().isoformat(), cid))
        notify(c["owner"], f"{cid} re-opened: citizen says the problem is not solved")
        up = officer(c["owner"])["up_id"]
        if up:
            notify(up, f"{cid} re-opened by the citizen after an ATR from {officer(c['owner'])['short']}")
        o.bot(o.t(f"Noted. <b>{cid}</b> has been <b>re-opened</b> and sent back to <b>{E(officer(c['owner'])['short'])}</b>; their senior officer has been informed.",
                  f"<b>{cid}</b> ಅನ್ನು <b>ಮರು-ತೆರೆಯಲಾಗಿದೆ</b> ಮತ್ತು <b>{E(officer(c['owner'])['short'])}</b> ಅವರಿಗೆ ಹಿಂತಿರುಗಿಸಲಾಗಿದೆ."),
              buttons=[{"label": "✍️ Add details", "action": f"reply:{cid}"}, {"label": "🏠 Main menu", "action": "menu"}])
    o.st.update(flow="menu", draft={})


def gp_taluks():'''
edit(p, "def gp_taluks():", NEW)
# "later" action: do nothing but acknowledge
edit(p, '''        elif a == "menu":
            menu(o)''', '''        elif a == "menu":
            menu(o)
        elif a == "later":
            o.bot(o.t("No problem. Tap <b>Reply now</b> on the officer's message whenever you are ready, or type TRACK.",
                      "ಸರಿ. ಸಿದ್ಧವಾದಾಗ ಅಧಿಕಾರಿಯ ಸಂದೇಶದಲ್ಲಿ <b>ಉತ್ತರಿಸಿ</b> ಒತ್ತಿ."))''')
print("chat patched")
