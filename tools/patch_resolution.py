"""Resolution loop (19 Oct 2026, Pranay): after an officer resolves a case the citizen accepts it (closed) or rejects it,
which RE-OPENS the case and moves it ONE RUNG UP the escalation ladder (L1 -> L2 -> L3) with the senior's clock starting
now. One shared POC step (sla.citizen_verdict) serves WhatsApp and Mitra. "Track my request" with the live status, the
officer and the ladder now lives inside the WhatsApp chat (the separate citizen page is gone). Mitra shows the officer's
report as a resolution card with yes / no, and on a "no" the ladder climbing live.

Applies to: app/server/{sla,api,chat}.py, wireframe/index.html, app/web/index.html, mitra/server/{tools,brain,live,sync,
notify}.py, mitra/web/{mitra.js,mitra.css,app.js,index.html}, three tests. Safe to run once."""
import io
import re

ROOT = r"D:\Sakala POC"


def rd(path):
    return io.open(ROOT + "\\" + path, encoding="utf-8").read()


def wr(path, s):
    io.open(ROOT + "\\" + path, "w", encoding="utf-8", newline="").write(s)


def edit(path, pairs, regex=False):
    s = rd(path)
    for a, b in pairs:
        if regex:
            s, n = re.subn(a, b, s, count=1, flags=re.S)
            assert n == 1, (path, a[:80])
        else:
            assert s.count(a) == 1, (path, a[:90], s.count(a))
            s = s.replace(a, b)
    wr(path, s)
    print("patched", path)


# ============================================================================ POC · stage 8 closes the loop with the citizen
edit(r"app\server\sla.py", [
    ('''def notify(officer_id, msg):
    db.run("INSERT INTO notifications(officer_id,t,msg) VALUES (?,?,?)", (officer_id, now().isoformat(), msg))
''', '''def notify(officer_id, msg):
    db.run("INSERT INTO notifications(officer_id,t,msg) VALUES (?,?,?)", (officer_id, now().isoformat(), msg))


def ladder_up(c):
    """The next rung above the case's holder: the senior on the grievance ladder, or the next Sakala authority
    (Designated -> Competent -> Appellate) for an application. The two ladders never mix."""
    if c.get("sakala"):
        sk = json.loads(c["sakala"])
        order = [sk.get("DO"), sk.get("CO"), sk.get("AA")]
        if c["owner"] in order:
            i = order.index(c["owner"])
            return officer(order[i + 1]) if i + 1 < len(order) and order[i + 1] else None
    cur = officer(c["owner"])
    return officer(cur["up_id"]) if cur and cur["up_id"] else None


def feedback_pending(c) -> bool:
    """The officer filed a resolution and the citizen has not yet said whether it is really solved."""
    if c["status"] != "Resolved":
        return False
    last = db.q1("SELECT what FROM case_events WHERE case_id=? AND (what LIKE 'Resolved with ATR%' OR what LIKE 'Citizen confirmed%') "
                 "ORDER BY id DESC LIMIT 1", (c["id"],))
    return bool(last) and last["what"].startswith("Resolved")


def citizen_verdict(c, accepted: bool, who: str, channel: str) -> dict:
    """Stage 8, the citizen's verdict on the officer's resolution. Accepted: the case is closed and the confirmation sits
    on the officer's report. Rejected: the case is RE-OPENED and moves ONE RUNG UP the escalation ladder (L1 -> L2 -> L3);
    the senior's clock starts now, both officers and the Chief Secretary are told. Shared by WhatsApp and Sakala Mitra."""
    cid = c["id"]
    cur = officer(c["owner"]) or {"id": c["owner"], "name": "the officer", "short": "the officer", "level": c["level"], "up_id": None}
    if accepted:
        event(cid, who, "Citizen confirmed: problem solved 👍", "#1f9d57", f"Resolution accepted on {channel}")
        db.run("UPDATE cases SET status='Resolved' WHERE id=?", (cid,))
        notify(cur["id"], f"{cid} closed: the citizen confirmed the problem is solved")
        return {"accepted": True, "status": "Resolved", "officer": cur["short"], "officer_id": cur["id"], "level": cur["level"]}
    up = ladder_up(c)
    t = now().isoformat()
    if up:
        days = SLA_DAYS.get(up["level"], 7)
        db.run("UPDATE cases SET owner=?, level=?, level_since=?, status='Pending' WHERE id=?", (up["id"], up["level"], t, cid))
        event(cid, who, f"Re-opened by the citizen · escalated to {up['short']}", "#c8372d",
              f"Resolution by {cur['short']} rejected on {channel} · {cur['level']} → {up['level']} · clock restarted: {days} days")
        notify(up["id"], f"{cid} escalated to you from {cur['short']}: the citizen rejected the resolution")
        notify(cur["id"], f"{cid} re-opened by the citizen after your ATR · moved up to {up['short']}")
        return {"accepted": False, "status": "Pending", "escalated": True, "from": cur["short"], "from_level": cur["level"],
                "officer": up["short"], "officer_id": up["id"], "officer_name": up["name"], "level": up["level"], "days": days,
                "chain": [{"lv": x["level"], "short": x["short"], "id": x["id"]} for x in chain(up["id"])]}
    days = SLA_DAYS.get(cur["level"], 7)
    db.run("UPDATE cases SET status='Pending', level_since=? WHERE id=?", (t, cid))
    event(cid, who, "Re-opened by the citizen · top of the ladder", "#c8372d",
          f"Resolution by {cur['short']} rejected on {channel} · no senior to escalate to · clock restarted: {days} days · flagged for the Chief Secretary")
    notify(cur["id"], f"{cid} re-opened by the citizen after your ATR · top of the ladder, the Chief Secretary is informed")
    return {"accepted": False, "status": "Pending", "escalated": False, "from": cur["short"], "from_level": cur["level"],
            "officer": cur["short"], "officer_id": cur["id"], "officer_name": cur.get("name") or cur["short"], "level": cur["level"], "days": days,
            "chain": [{"lv": x["level"], "short": x["short"], "id": x["id"]} for x in chain(cur["id"])]}
'''),
])

edit(r"app\server\api.py", [
    ('''    if s == "feedback":
        if not c:
            return {"step": s, "ok": False, "reason": "not_yours"}
        o = officer(c["owner"])
        if r.answer == "yes":
            event(c["id"], "Citizen (Sakala Mitra)", "Citizen confirmed: problem solved 👍", "#1f9d57", "Feedback given by voice")
            db.run("UPDATE cases SET status='Resolved' WHERE id=?", (c["id"],))
            return {"step": s, "ok": True, "status": "Resolved"}
        event(c["id"], "Citizen (Sakala Mitra)", "Citizen says NOT solved · re-opened 👎", "#c8372d", "Back to the officer; the senior officer is informed")
        db.run("UPDATE cases SET status='Pending', level_since=? WHERE id=?", (now().isoformat(), c["id"]))
        notify(c["owner"], f"{c['id']} re-opened: citizen says the problem is not solved")
        if o and o["up_id"]:
            notify(o["up_id"], f"{c['id']} re-opened by the citizen after an ATR from {o['short']}")
        return {"step": s, "ok": True, "status": "Pending", "officer": o["short"] if o else ""}''',
     '''    if s == "feedback":
        if not c:
            return {"step": s, "ok": False, "reason": "not_yours"}
        if not sla.feedback_pending(c):
            return {"step": s, "ok": False, "reason": "nothing_to_answer", "status": c["status"]}
        return {"step": s, "ok": True, **sla.citizen_verdict(c, r.answer == "yes", "Citizen (Sakala Mitra)", "Sakala Mitra (voice)")}'''),
    ('''        for c in rows:
            info = sla_info(db.q1("SELECT * FROM cases WHERE id=?", (c["id"],)))
            out.append({"id": c["id"], "service": c["u"]["svc"] or "Scrutiny desk", "status": c["status"], "owner": c["owner"],
                        "ownerShort": (officer(c["owner"]) or {}).get("short", ""), "level": c["level"], "left": info["left"],
                        "legal": info["legal"], "created": c["created"], "gp": c["gp"], "taluk": c["taluk"], "kind": c["u"]["type"],
                        "last": (c["history"] or [{}])[-1].get("what", "")})''',
     '''        for c in rows:
            row = db.q1("SELECT * FROM cases WHERE id=?", (c["id"],))
            info = sla_info(row)
            out.append({"id": c["id"], "service": c["u"]["svc"] or "Scrutiny desk", "status": c["status"], "owner": c["owner"],
                        "ownerShort": (officer(c["owner"]) or {}).get("short", ""), "level": c["level"], "left": info["left"],
                        "total": info["total"], "legal": info["legal"], "created": c["created"], "gp": c["gp"], "taluk": c["taluk"],
                        "kind": c["u"]["type"], "last": (c["history"] or [{}])[-1].get("what", ""),
                        "atr": row["atr"] or "", "feedback_pending": sla.feedback_pending(row),
                        "chain": [{"lv": x["level"], "short": x["short"]} for x in sla.chain(c["owner"])]})'''),
])

# ---------------------------------------------------------------- WhatsApp chat: verdict + live tracking inside the chat
edit(r"app\server\chat.py", [
    ("from .sla import now, officer, create_application, sla_info, chain, event, notify",
     "from .sla import now, officer, create_application, sla_info, chain, event, notify, citizen_verdict, feedback_pending"),
    ('''        elif a.startswith("fb:"):
            feedback(o, sid, a[3:])''',
     '''        elif a.startswith("fb:"):
            feedback(o, sid, a[3:])
        elif a.startswith("case:"):
            case_card(o, sid, a[5:])
        elif a == "appeal":
            appeal(o, sid)'''),
    # the track card: live status, officer and ladder per request, open any one of them
    ('''def track(o, sid):
    mine = db.q("SELECT * FROM cases WHERE session=? ORDER BY created DESC LIMIT 4", (sid,))
    if not mine:
        o.bot(o.t("You have no requests yet. Raise one from the menu 🙂", "ಇನ್ನೂ ಯಾವುದೇ ಅರ್ಜಿ ಇಲ್ಲ. ಮೆನುವಿನಿಂದ ಸಲ್ಲಿಸಿ 🙂"))
        return menu(o)
    rows = []
    for c in mine:
        s = sla_info(c)
        st = ("✅ Resolved" if c["status"] == "Resolved" else "❌ Rejected · you can appeal" if c["status"] == "Rejected" else
              "📩 Officer asked for information · reply in this chat" if c["status"] == "Info requested" else
              f"⚠️ {-s['left']} days overdue · escalated" if s["left"] < 0 else f"⏳ {s['left']} days left")
        cls = "ok" if c["status"] == "Resolved" else "bad" if s["left"] < 0 or c["status"] == "Rejected" else ""
        rows.append(f"<div class=\\"wa-trk\\"><b>{c['id']}</b><span>{E(c['service'] or 'Scrutiny desk')}</span>"
                    f"<span>With {E(officer(c['owner'])['short'])} · {c['level']}</span><span class=\\"{cls}\\">{st}</span></div>")
    o.bot("<b>Your requests</b>" + "".join(rows), type="card", buttons=[{"label": "🏠 Main menu", "action": "menu"}])
''',
     '''def _status_line(o, c):
    """One line a citizen understands, plus its colour class."""
    s = sla_info(c)
    if c["status"] == "Resolved":
        if feedback_pending(c):
            return o.t("🟢 Resolved by the officer · is it really solved? Tell us below", "🟢 ಅಧಿಕಾರಿ ಪರಿಹರಿಸಿದ್ದಾರೆ · ನಿಜವಾಗಿ ಬಗೆಹರಿಯಿತೇ?"), "ok"
        return o.t("✅ Resolved · confirmed by you", "✅ ಪರಿಹಾರವಾಗಿದೆ · ನೀವು ಖಚಿತಪಡಿಸಿದ್ದೀರಿ"), "ok"
    if c["status"] == "Rejected":
        return o.t("❌ Rejected · you can appeal", "❌ ತಿರಸ್ಕೃತ · ಮೇಲ್ಮನವಿ ಸಲ್ಲಿಸಬಹುದು"), "bad"
    if c["status"] == "Info requested":
        return o.t("📩 Officer asked for information · reply in this chat", "📩 ಅಧಿಕಾರಿ ಮಾಹಿತಿ ಕೇಳಿದ್ದಾರೆ · ಇಲ್ಲಿ ಉತ್ತರಿಸಿ"), ""
    if c["status"] == "Scrutiny":
        return o.t("🔎 Being checked by the scrutiny desk", "🔎 ಪರಿಶೀಲನಾ ಡೆಸ್ಕ್ ಪರಿಶೀಲಿಸುತ್ತಿದೆ"), ""
    if s["left"] < 0:
        return o.t(f"⚠️ {-s['left']} days overdue · escalated", f"⚠️ {-s['left']} ದಿನ ವಿಳಂಬ · ಮೇಲಧಿಕಾರಿಗೆ"), "bad"
    return o.t(f"⏳ {s['left']} day{'s' if s['left'] != 1 else ''} left for the officer to act", f"⏳ ಅಧಿಕಾರಿಗೆ {s['left']} ದಿನ ಬಾಕಿ"), ""


def _ladder_html(c):
    """The escalation ladder as the citizen sees it: rungs already passed, the rung holding it now, the rungs above."""
    above = chain(c["owner"])                                     # the holder first, then every senior
    first = db.q1("SELECT what FROM case_events WHERE case_id=? AND what LIKE 'Routed to %' ORDER BY id LIMIT 1", (c["id"],))
    levels = ["L1", "L2", "L3"]
    cur_i = levels.index(c["level"]) if c["level"] in levels else 0
    rungs = []
    for i in range(cur_i):                                       # passed rungs (the first one is known from the routing event)
        nm = first["what"][10:] if first and i == 0 else levels[i]
        rungs.append(f"<span class=\\"done\\">{E(levels[i])} · {E(nm)}</span>")
    for j, x in enumerate(above):
        rungs.append(f"<span class=\\"{'cur' if j == 0 else ''}\\">{E(x['level'])} · {E(x['short'])}</span>")
    return "<div class=\\"wa-lad\\">" + "<i>→</i>".join(rungs) + "</div>"


def _when(t):
    try:
        return datetime.fromisoformat(t).strftime("%d %b, %H:%M")
    except Exception:  # noqa: BLE001
        return ""


def track(o, sid):
    mine = db.q("SELECT * FROM cases WHERE session=? ORDER BY created DESC LIMIT 6", (sid,))
    if not mine:
        o.bot(o.t("You have no requests yet. Raise one from the menu 🙂", "ಇನ್ನೂ ಯಾವುದೇ ಅರ್ಜಿ ಇಲ್ಲ. ಮೆನುವಿನಿಂದ ಸಲ್ಲಿಸಿ 🙂"))
        return menu(o)
    rows, items = [], []
    for c in mine:
        st, cls = _status_line(o, c)
        off = officer(c["owner"]) or {"short": "Scrutiny desk"}
        rows.append(f"<div class=\\"wa-trk\\"><b>{c['id']}</b><span>{E(c['service'] or 'Scrutiny desk')}</span>"
                    f"<span>With {E(off['short'])} · {c['level']}</span><span class=\\"{cls}\\">{st}</span></div>")
        items.append({"t": c["id"], "d": f"{c['service'] or 'Scrutiny desk'} · {c['status']}", "action": f"case:{c['id']}"})
    pend = [c for c in mine if feedback_pending(c)]
    o.bot(o.t("<b>Your requests · live</b>", "<b>ನಿಮ್ಮ ಅರ್ಜಿಗಳು · ಲೈವ್</b>") + "".join(rows)
          + f"<p class=\\"wa-muted\\">{o.t('Open a request for the officer ladder, days left and your options.', 'ಅಧಿಕಾರಿ ಹಂತಗಳು ಮತ್ತು ಆಯ್ಕೆಗಳಿಗೆ ಅರ್ಜಿ ತೆರೆಯಿರಿ.')}</p>",
          type="card", list={"button": o.t("Open a request", "ಅರ್ಜಿ ತೆರೆಯಿರಿ"), "title": o.t("Your requests", "ನಿಮ್ಮ ಅರ್ಜಿಗಳು"), "rows": items},
          buttons=[{"label": o.t("🔄 Refresh", "🔄 ನವೀಕರಿಸಿ"), "action": "track"}, {"label": "🏠 Main menu", "action": "menu"}])
    if pend:                                                     # a resolution is waiting for the citizen's word: ask right here
        case_card(o, sid, pend[0]["id"])


def case_card(o, sid, cid):
    """One request in full, live: status, the officer holding it, the ladder, the clock, the last event, and what the
    citizen can do now (confirm or reject a resolution, reply, appeal)."""
    c = own_case(o, sid, cid)
    if not c:
        return
    st, cls = _status_line(o, c)
    s = sla_info(c)
    off = officer(c["owner"]) or {"short": "Scrutiny desk", "name": "Scrutiny desk"}
    last = db.q1("SELECT what, t FROM case_events WHERE case_id=? ORDER BY id DESC LIMIT 1", (cid,)) or {}
    clock = ("" if c["status"] in ("Resolved", "Rejected") else
             f"<span>⏱ {'Sakala legal deadline' if s['legal'] else 'Action due'}: {s['total']} days · "
             + (f"<b class=\\"bad\\">{-s['left']} overdue</b>" if s["left"] < 0 else f"<b>{s['left']} left</b>") + "</span>")
    html = (f"<div class=\\"wa-trk\\"><b>{cid}</b><span>{E(c['service'] or 'Scrutiny desk')}</span>"
            f"<span>{o.t('With', 'ಇವರ ಬಳಿ')} <b>{E(off.get('name') or off['short'])}</b> · {c['level']}</span>"
            f"{_ladder_html(c)}{clock}<span class=\\"{cls}\\">{st}</span>"
            + (f"<div class=\\"last\\">{o.t('Last', 'ಕೊನೆಯದು')}: {E(last.get('what', ''))} · {_when(last.get('t', ''))}</div>" if last else "")
            + (f"<div class=\\"last\\">{o.t('Officer’s report', 'ಅಧಿಕಾರಿಯ ವರದಿ')}: “{E(c['atr'])}”</div>" if c.get("atr") and c["status"] == "Resolved" else "")
            + "</div>")
    if feedback_pending(c):
        btns = [{"label": o.t("👍 Yes, solved", "👍 ಹೌದು, ಬಗೆಹರಿಯಿತು"), "action": f"fb:{cid}:yes"},
                {"label": o.t("👎 No, not solved", "👎 ಇಲ್ಲ, ಬಗೆಹರಿದಿಲ್ಲ"), "action": f"fb:{cid}:no"}]
    elif c["status"] == "Rejected":
        btns = [{"label": o.t("⚖️ Appeal", "⚖️ ಮೇಲ್ಮನವಿ"), "action": "appeal"}, {"label": "🏠 Main menu", "action": "menu"}]
    elif c["status"] == "Info requested":
        btns = [{"label": o.t("✍️ Reply now", "✍️ ಈಗ ಉತ್ತರಿಸಿ"), "action": f"reply:{cid}"}, {"label": "🏠 Main menu", "action": "menu"}]
    elif c["status"] in ("Resolved",):
        btns = [{"label": o.t("🔄 Refresh", "🔄 ನವೀಕರಿಸಿ"), "action": f"case:{cid}"}, {"label": "🏠 Main menu", "action": "menu"}]
    else:
        btns = [{"label": o.t("✍️ Add details", "✍️ ವಿವರ ಸೇರಿಸಿ"), "action": f"reply:{cid}"},
                {"label": o.t("🔄 Refresh", "🔄 ನವೀಕರಿಸಿ"), "action": f"case:{cid}"}]
    o.bot(html, type="card", buttons=btns)
'''),
    # the verdict: accepted = closed; rejected = re-opened and one rung up, shown in "Behind the chat" like a routing
    ('''    if ans == "yes":
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
    o.st.update(flow="menu", draft={})''',
     '''    if not feedback_pending(c):
        o.bot(o.t(f"<b>{cid}</b> is not waiting for your answer right now.", f"<b>{cid}</b> ಈಗ ನಿಮ್ಮ ಉತ್ತರಕ್ಕಾಗಿ ಕಾಯುತ್ತಿಲ್ಲ."))
        return case_card(o, sid, cid)
    r = citizen_verdict(c, ans == "yes", "Citizen (WhatsApp)", "WhatsApp")
    if r["accepted"]:
        o.stage(7, "Closed · the citizen confirmed it is solved")
        o.bot(o.t(f"Thank you 🙏 <b>{cid}</b> is closed. Your confirmation is recorded against <b>{E(r['officer'])}</b>'s report. Glad it is solved!",
                  f"ಧನ್ಯವಾದಗಳು 🙏 <b>{cid}</b> ಮುಕ್ತಾಯವಾಗಿದೆ. ನಿಮ್ಮ ಖಚಿತಪಡಿಸುವಿಕೆ <b>{E(r['officer'])}</b> ಅವರ ವರದಿಯಲ್ಲಿ ದಾಖಲಾಗಿದೆ."),
              buttons=[{"label": "🔎 Track", "action": "track"}, {"label": "🏠 Main menu", "action": "menu"}])
    else:
        if r["escalated"]:
            o.stage(5, f"Re-opened · escalated {r['from_level']} → {r['level']}: {r['officer']}", "warn")
        else:
            o.stage(5, f"Re-opened · {r['officer']} is at the top of the ladder · Chief Secretary informed", "warn")
        o.stage(6, f"Clock restarted · {r['days']} days for {r['officer']}")
        o.stage(7, "Visible to officer & Chief Secretary now")
        o.ev.append({"kind": "result", "caseId": cid, "officer": {"id": r["officer_id"], "name": r["officer_name"], "short": r["officer"]},
                     "chain": [{"lv": x["lv"], "short": x["short"]} for x in r["chain"]],
                     "basis": f"The citizen rejected the resolution of {r['from']} on WhatsApp · moved one rung up the ladder, clock restarted",
                     "title": "Escalated to" if r["escalated"] else "Re-opened with"})
        if r["escalated"]:
            o.bot(o.t(f"Noted. <b>{cid}</b> has been <b>re-opened</b> and moved up the ladder: from <b>{E(r['from'])}</b> ({r['from_level']}) to "
                      f"<b>{E(r['officer_name'])}</b> ({r['level']}). They have <b>{r['days']} days</b> to act, and the Chief Secretary can see it.",
                      f"<b>{cid}</b> ಅನ್ನು <b>ಮರು-ತೆರೆದು</b> ಮೇಲಧಿಕಾರಿ <b>{E(r['officer_name'])}</b> ({r['level']}) ಅವರಿಗೆ ವರ್ಗಾಯಿಸಲಾಗಿದೆ. "
                      f"ಅವರಿಗೆ <b>{r['days']} ದಿನ</b> ಕಾಲಾವಕಾಶ; ಮುಖ್ಯ ಕಾರ್ಯದರ್ಶಿಗೂ ಇದು ಕಾಣುತ್ತದೆ."),
                  buttons=[{"label": "✍️ Add details", "action": f"reply:{cid}"}, {"label": "🔎 Track", "action": f"case:{cid}"}, {"label": "🏠 Main menu", "action": "menu"}])
        else:
            o.bot(o.t(f"Noted. <b>{cid}</b> has been <b>re-opened</b>. <b>{E(r['officer_name'])}</b> is already at the top of the ladder, so it stays with "
                      f"them with a fresh clock of <b>{r['days']} days</b>, and the Chief Secretary has been informed.",
                      f"<b>{cid}</b> ಅನ್ನು <b>ಮರು-ತೆರೆಯಲಾಗಿದೆ</b>. <b>{E(r['officer_name'])}</b> ಅತ್ಯುನ್ನತ ಹಂತದಲ್ಲಿದ್ದಾರೆ; ಮುಖ್ಯ ಕಾರ್ಯದರ್ಶಿಗೆ ತಿಳಿಸಲಾಗಿದೆ."),
                  buttons=[{"label": "✍️ Add details", "action": f"reply:{cid}"}, {"label": "🏠 Main menu", "action": "menu"}])
        o.ev.append({"kind": "toast", "h": "Re-opened from WhatsApp", "m": f"{cid} → {r['officer']}"})
    o.st.update(flow="menu", draft={})'''),
])

# ---------------------------------------------------------------- citizen UI: tracking lives in the chat (wireframe + app)
TRACK_BTN = re.compile(r"\n\s*<button class=\"\$\{S\.citizenView==='track'\?'on':''\}\" data-cv=\"track\">.*?</button>")
LAD_CSS = ('''.wa-lad{display:flex;align-items:center;gap:4px;margin:6px 0 2px;font-size:.68rem;flex-wrap:wrap}
.wa-lad span{padding:3px 7px;border-radius:999px;background:#f0f2f5;color:#54656f;border:1px solid #e9edef;white-space:nowrap}
.wa-lad span.cur{background:#d9fdd3;color:#0b6b3a;border-color:#9fe3a9;font-weight:700}
.wa-lad span.done{color:#8696a0;text-decoration:line-through}
.wa-lad i{color:#8696a0;font-style:normal}
.wa-trk .last{font-size:.72rem;color:#8696a0;margin-top:4px;line-height:1.35}
.wa-trk .bad{color:#c8372d}
''')
for path in (r"wireframe\index.html", r"app\web\index.html"):
    s = rd(path)
    s, n = TRACK_BTN.subn("", s, count=1); assert n == 1, path
    a = '<button class="${S.citizenView!==\'track\'?\'on\':\'\'}" data-cv="wa">'
    assert s.count(a) == 1, (path, "wa button"); s = s.replace(a, '<button class="on" data-cv="wa">')
    a = "  if (S.citizenView==='track') return renderTrack();\n"
    assert s.count(a) == 1, (path, "renderTrack call"); s = s.replace(a, "  S.citizenView='wa';                                   /* tracking lives inside the chat (19 Oct) */\n")
    a = ".wa-trk{margin-top:8px;"
    assert s.count(a) == 1, (path, "wa-trk css"); s = s.replace(a, LAD_CSS + a)
    wr(path, s); print("patched", path)
s = rd(r"tools\wa_future.css")
a = ".wa-trk{margin-top:8px;"
if LAD_CSS not in s and s.count(a) == 1:
    wr(r"tools\wa_future.css", s.replace(a, LAD_CSS + a)); print("patched tools/wa_future.css")

# ============================================================================ Mitra
edit(r"mitra\server\sync.py", [
    ('''    w = (what or "").lower()
    if w.startswith("routed to") or w.startswith("application registered"):
        return "new"''',
     '''    w = (what or "").lower()
    if w.startswith("re-opened by the citizen"):        # the citizen rejected the resolution (one rung up the ladder)
        return "reopened"
    if w.startswith("routed to") or w.startswith("application registered"):
        return "new"'''),
])

edit(r"mitra\server\notify.py", [
    ('''        bad = re.search(r"escalated|re-opened|missed", what, re.I)
        c.update(tone="bad" if bad else "warn", icon="⏰" if not bad else "⚠", title="Deadline" if re.search(r"due", what) else "Heads up",
                 body=what, actions=open_, speak=what)
        return c''',
     '''        if re.search(r"re-opened by the citizen", what, re.I):      # the officer whose resolution was rejected
            c.update(tone="bad", icon="↩", title=f"Re-opened · {cid}", body=what, actions=open_, speak=what, sticky=True)
            return c
        bad = re.search(r"escalated|re-opened|missed", what, re.I)
        c.update(tone="bad" if bad else "warn", icon="⏰" if not bad else "⚠", title="Deadline" if re.search(r"due", what) else "Heads up",
                 body=what, actions=open_, speak=what)
        return c'''),
    ('''        elif ch == "reopened":
            c.update(tone="bad", icon="↩", title=f"Re-opened · {cid}", body="The citizen says it is not solved. The clock has restarted.",
                     actions=open_, speak=f"{cid} was re-opened: the citizen says it is not solved.", sticky=True)''',
     '''        elif ch == "reopened":
            c.update(tone="bad", icon="↩", title=f"Re-opened · {cid}", body=note or "The citizen says it is not solved. The clock has restarted.",
                     actions=open_, speak=f"{cid} was re-opened by the citizen and is with you now; the clock has restarted.", sticky=True)'''),
    ('''        elif ch == "reopened":
            c.update(tone="bad", icon="↩", title=f"Re-opened by the citizen · {cid}", body=f"{svc} · {owner_short}", actions=open_)''',
     '''        elif ch == "reopened":
            c.update(tone="bad", icon="↩", title=f"Re-opened by the citizen · {cid}", body=f"{svc} · now with {owner_short}" + (f" · {note}" if note else ""), actions=open_)'''),
])

edit(r"mitra\server\brain.py", [
    ('''        if has("not solved", "still not", "not fixed", "not resolved", "re-open", "reopen", "no it is not", "no, it is not", "ಆಗಿಲ್ಲ"):
            return {"intent": "feedback_no"}''',
     '''        if c.get("awaiting_feedback") and flow not in ("confirm", "ask_place", "ask_gp", "apply_name", "apply_village", "apply_confirm"):
            # Mitra asked whether the officer's resolution solved it: any yes / no / accept / reject is the verdict
            if has("not solved", "still not", "not fixed", "not resolved", "re-open", "reopen", "not okay", "not ok", "don't accept", "do not accept",
                   "not accept", "not satisfied", "not happy", "reject", "unhappy", "no it is not", "no, it is not", "ಆಗಿಲ್ಲ") \\
                    or re.match(r"^\\s*(no|nope|nah|never)\\b", low):
                return {"intent": "feedback_no"}
            if has("solved", "fixed", "resolved", "accept", "okay with", "ok with", "satisfied", "happy with", "fine with", "thank", "ಆಗಿದೆ") or YES.search(low):
                return {"intent": "feedback_yes"}
        if has("not solved", "still not", "not fixed", "not resolved", "re-open", "reopen", "no it is not", "no, it is not", "ಆಗಿಲ್ಲ"):
            return {"intent": "feedback_no"}'''),
    ('"feedback_yes":   (("citizen",), "The citizen confirms the problem is solved.", ()),',
     '"feedback_yes":   (("citizen",), "The citizen accepts the officer\'s resolution / confirms the problem is solved (case closed).", ()),'),
    ('"feedback_no":    (("citizen",), "The citizen says the problem is NOT solved / re-open it.", ()),',
     '"feedback_no":    (("citizen",), "The citizen rejects the officer\'s resolution / says it is NOT solved: the case re-opens and moves up to the senior officer.", ()),'),
])

edit(r"mitra\server\live.py", [
    ('''"apply_service. They can only see their own requests. If you offered to send an unclear request to the scrutiny "
                     "desk, yes -> confirm, no -> change. Never say a request was filed, sent or registered unless a function result "
                     "says so.")''',
     '''"apply_service. They can only see their own requests. If you offered to send an unclear request to the scrutiny "
                     "desk, yes -> confirm, no -> change. Never say a request was filed, sent or registered unless a function result "
                     "says so. When an officer has marked their request resolved, Mitra asks whether it is really solved: accepting it, "
                     "okay with it, satisfied, solved -> feedback_yes (the case closes); not okay, does not accept, still not solved -> "
                     "feedback_no (the case re-opens and moves one rung up to the senior officer with a fresh clock; say so).")'''),
])

edit(r"mitra\server\tools.py", [
    # a plain yes / no while Mitra waits for the verdict is the verdict, not a filing confirmation
    ('''        elif intent == "confirm_action" and sess["profile"] == "citizen":
            intent, fn = "confirm", HANDLERS["confirm"]                  # nothing pending: the citizen is confirming their request
            res = await fn(sess, args)''',
     '''        elif sess["profile"] == "citizen" and st.get("awaiting_feedback") and intent in ("confirm_action", "cancel_action", "confirm") \\
                and not (st.get("draft") or {}).get("service") and st.get("flow") not in ("confirm", "ask_place", "ask_gp"):
            intent = "feedback_no" if intent == "cancel_action" else "feedback_yes"   # yes / no answers "was it really solved?"
            fn = HANDLERS[intent]
            res = await fn(sess, args)
        elif intent == "confirm_action" and sess["profile"] == "citizen":
            intent, fn = "confirm", HANDLERS["confirm"]                  # nothing pending: the citizen is confirming their request
            res = await fn(sess, args)'''),
    # track: a resolution waiting for the citizen's word is asked right there
    ('''    say = f"You have {len(cases)} request{'s' if len(cases) != 1 else ''}. " + ". ".join(line(c) for c in cases[:4]) + "."
    upd = await t_updates(sess, {})
    if upd.get("say"):
        say += " " + upd["say"]
    return {"say": say, "ui": [{"op": "mycases", "cases": cases}] + upd.get("ui", [])}''',
     '''    say = f"You have {len(cases)} request{'s' if len(cases) != 1 else ''}. " + ". ".join(line(c) for c in cases[:4]) + "."
    upd = await t_updates(sess, {})
    if upd.get("say"):
        say += " " + upd["say"]
    ui = [{"op": "mycases", "cases": cases}] + upd.get("ui", [])
    pend = [c for c in cases if c.get("feedback_pending")]
    if pend and not any(o.get("op") == "resolution" for o in ui):      # resolved earlier, verdict still open: ask again
        c = pend[0]
        sess["state"]["awaiting_feedback"] = c["id"]
        _set_options(sess, [["Yes, solved", "fb:yes"], ["No, not solved", "fb:no"]])
        say += (f" {c['ownerShort']} marked {c['id']} as resolved" + (f": {clean_for_speech(c['atr'])}" if c.get("atr") else "")
                + ". Was your problem actually solved? Say yes or no.")
        ui.append({"op": "resolution", "case_id": c["id"], "officer": c["ownerShort"], "officerFull": c["ownerShort"], "atr": c.get("atr") or "", "service": c.get("service") or ""})
    return {"say": say, "ui": ui}'''),
    ('''    say = " ".join(spoken_update(m) for m in msgs)
    return {"say": say, "ui": [{"op": "updates", "messages": msgs}]}''',
     '''    say = " ".join(spoken_update(m) for m in msgs)
    ui = [{"op": "updates", "messages": msgs}]
    for m in msgs:
        if m["kind"] == "resolved":                                  # the officer's report, with the citizen's two choices
            ui.append({"op": "resolution", "case_id": m["case_id"], "officer": m["officer"], "officerFull": m.get("officerFull") or m["officer"],
                       "atr": m.get("text") or "", "service": m.get("service") or ""})
    return {"say": say, "ui": ui}'''),
    ('''    r = await intake(sess, step="feedback", case_id=cid, answer="yes" if yes else "no")
    if not r.get("ok"):
        return {"say": "I could not record that; the request was not filed from here."}
    st["awaiting_feedback"] = None; _set_options(sess, [])
    say = "Thank you. Your feedback is recorded against the officer's report. Glad it is solved." if yes else \\
          f"Noted. {cid} has been re-opened and sent back to {r.get('officer')}; their senior officer has been informed."
    return {"say": say, "ui": await _profile_ui(sess)}''',
     '''    r = await intake(sess, step="feedback", case_id=cid, answer="yes" if yes else "no")
    if not r.get("ok"):
        st["awaiting_feedback"] = None; _set_options(sess, [])
        if r.get("reason") == "nothing_to_answer":
            return {"say": f"{cid} is not waiting for your answer right now; it is {r.get('status', 'open').lower()}.", "ui": await _profile_ui(sess)}
        return {"say": "I could not record that; the request was not filed from here."}
    st["awaiting_feedback"] = None; _set_options(sess, [])
    if r.get("accepted"):
        say = f"Thank you. {cid} is closed, and your confirmation is recorded against {r.get('officer')}'s report. Glad it is solved."
        ui = [{"op": "verdict", "case_id": cid, "accepted": True, "officer": r.get("officer")},
              {"op": "stages", "items": [stage(7, "Closed · you confirmed it is solved")]}]
    elif r.get("escalated"):
        say = (f"Noted. I have re-opened {cid} and moved it up the ladder: from {r['from']} to {r.get('officer_name') or r['officer']}, "
               f"the {r['level']} officer. Their clock starts now, {r['days']} days to act, and the Chief Secretary can see it.")
        ui = [{"op": "verdict", "case_id": cid, "accepted": False, "escalated": True, "from": r["from"], "from_level": r["from_level"],
               "to": r["officer"], "to_name": r.get("officer_name"), "level": r["level"], "days": r["days"], "chain": r.get("chain") or []},
              {"op": "stages", "items": [stage(5, f"Escalated {r['from_level']} → {r['level']}: {r['officer']}", "warn"),
                                         stage(6, f"Clock restarted · {r['days']} days for {r['officer']}"),
                                         stage(7, "Re-opened · visible to the officer and the Chief Secretary")]}]
    else:
        say = (f"Noted. I have re-opened {cid}. {r.get('officer_name') or r['officer']} is already at the top of the ladder, so it stays "
               f"with them with a fresh clock of {r['days']} days, and the Chief Secretary has been informed.")
        ui = [{"op": "verdict", "case_id": cid, "accepted": False, "escalated": False, "from": r["from"], "from_level": r["from_level"],
               "to": r["officer"], "to_name": r.get("officer_name"), "level": r["level"], "days": r["days"], "chain": r.get("chain") or []},
              {"op": "stages", "items": [stage(5, f"Re-opened · {r['officer']} is at the top of the ladder", "warn"),
                                         stage(6, f"Clock restarted · {r['days']} days"), stage(7, "The Chief Secretary has been informed")]}]
    return {"say": say, "ui": ui + await _profile_ui(sess)}'''),
])

# ---------------------------------------------------------------- Mitra browser: the resolution card and the ladder
edit(r"mitra\web\mitra.js", [
    ("  // ---------------- officer\n  inbox(op) {",
     '''  // the officer's resolution: a report the citizen judges with one word (or a tap); shown on the web and in the phone
  resolution(op) {
    const cid = op.case_id || '', ini = (op.officer || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
    panel('resolution', 'right', `<h3>Resolution <small>${esc(cid)}</small></h3>
      <div class="resv" data-cid="${esc(cid)}">
        <div class="ring"><svg viewBox="0 0 64 64"><circle class="trk" cx="32" cy="32" r="28"/><circle class="arc" cx="32" cy="32" r="28"/><path class="tick" d="M20 33l8 8 16-17"/></svg></div>
        <div class="rtx"><div class="who"><span class="av">${ini}</span><div><b>${esc(op.officerFull || op.officer || 'The officer')}</b><small>${esc(op.officer || '')} · marked it resolved</small></div></div>
          ${op.service ? `<div class="svc">${esc(op.service)}</div>` : ''}
          <div class="atr">“${esc(op.atr || 'Action taken report filed')}”</div>
          <div class="q">Was your problem actually solved?</div>
          <div class="yn"><button class="yes" data-say="yes, it is solved">👍 Yes, it’s solved</button><button class="no" data-say="no, it is not solved">👎 No, not solved</button></div>
          <div class="hint">Say it, or tap. A “no” re-opens it and moves it up to the senior officer.</div></div></div>`, { top: true });
    document.querySelectorAll('#right .resv .yn button').forEach(b => b.onclick = () => turn({ text: b.dataset.say }));
    flyLabel(`${cid} · solved?`);
  },
  // the verdict: closed with thanks, or the ladder climbing one rung with a fresh clock
  verdict(op) {
    const cid = op.case_id || '', host = document.querySelector('#right .resv');
    let html;
    if (op.accepted) {
      html = `<div class="resv closed"><div class="ring ok"><svg viewBox="0 0 64 64"><circle class="trk" cx="32" cy="32" r="28"/><circle class="arc" cx="32" cy="32" r="28"/><path class="tick" d="M20 33l8 8 16-17"/></svg></div>
        <div class="rtx"><b class="ttl">Closed · thank you</b><div class="sub">${esc(cid)} is solved. Your confirmation sits on ${esc(op.officer || 'the officer')}’s report.</div></div></div>`;
    } else {
      const chain = op.chain || [];
      const rungs = (op.escalated === false ? [] : [{ lv: op.from_level || '', short: op.from || '', st: 'passed' }])
        .concat(chain.map((c, i) => ({ lv: c.lv, short: c.short, st: i ? 'next' : 'cur' })));
      html = `<div class="resv reopened"><div class="rtx"><b class="ttl">${op.escalated === false ? 'Re-opened · top of the ladder' : 'Re-opened · moved up the ladder'}</b>
        <div class="ladder">${rungs.map((r, i) => `<div class="rung ${r.st}" style="--i:${i}"><span class="lv">${esc(r.lv)}</span><span class="nm">${esc(r.short)}</span>${r.st === 'cur' ? '<span class="now">holds it now</span>' : r.st === 'passed' ? '<span class="now">rejected</span>' : ''}</div>`).join('<i class="up"></i>')}</div>
        <div class="clock"><span class="dot"></span>Clock restarted · <b>${op.days || 7} days</b> for ${esc(op.to_name || op.to || '')}</div>
        <div class="sub">The Chief Secretary can see it. You will hear every update here.</div></div></div>`;
    }
    if (host) host.outerHTML = html; else panel('resolution', 'right', `<h3>Resolution <small>${esc(cid)}</small></h3>${html}`, { top: true });
    if (op.accepted) { Orb.burst(); flyLabel(`${cid} · closed ✓`); } else flyLabel(`${cid} ↑ ${op.to || 're-opened'}`);
  },
  // ---------------- officer
  inbox(op) {'''),
    ("if (J.profile === 'citizen' && e.mine && !['citizen_reply', 'feedback_yes', 'appeal', 'new'].includes(e.change)) {",
     "if (J.profile === 'citizen' && e.mine && !['citizen_reply', 'feedback_yes', 'reopened', 'appeal', 'new'].includes(e.change)) {"),
])

edit(r"mitra\web\app.js", [
    ("const AUTO = { case: 'right', request: 'left', inbox: 'left', mycases: 'left', kpi: 'left', filter: 'left', routed: 'left', atr: 'right', pack: 'right' };",
     "const AUTO = { case: 'right', request: 'left', inbox: 'left', mycases: 'left', kpi: 'left', filter: 'left', routed: 'left', atr: 'right', pack: 'right', resolution: 'right', verdict: 'right' };"),
])

css = rd(r"mitra\web\mitra.css")
assert "/* v56 · resolution" not in css
css += '''
/* v56 · resolution: the officer's report, the citizen's verdict, and the ladder climbing on a "no" (web + phone) */
.resv{display:flex;gap:12px;align-items:flex-start;padding:12px;border-radius:18px;background:linear-gradient(135deg,rgba(255,196,60,.16),rgba(22,199,132,.06));border:1px solid rgba(255,196,60,.4);animation:up .5s both;position:relative;overflow:hidden}
.resv .ring{width:56px;height:56px;flex:none}
.resv .ring svg{width:100%;height:100%;transform:rotate(-90deg)}
.resv .ring .trk{fill:none;stroke:rgba(255,255,255,.12);stroke-width:4}
.resv .ring .arc{fill:none;stroke:var(--gold);stroke-width:4;stroke-linecap:round;stroke-dasharray:176;stroke-dashoffset:176;animation:resArc 1.2s .2s cubic-bezier(.2,.8,.2,1) forwards}
.resv .ring .tick{fill:none;stroke:var(--gold);stroke-width:4.5;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:40;stroke-dashoffset:40;transform:rotate(90deg);transform-origin:50% 50%;animation:resTick .5s 1.1s ease-out forwards}
.resv .ring.ok .arc,.resv .ring.ok .tick{stroke:var(--em)}
@keyframes resArc{to{stroke-dashoffset:0}}
@keyframes resTick{to{stroke-dashoffset:0}}
.resv .rtx{flex:1;min-width:0}
.resv .who{display:flex;gap:8px;align-items:center}
.resv .who .av{width:30px;height:30px;border-radius:50%;background:var(--gold);color:#1a1200;font-weight:800;font-size:11px;display:grid;place-items:center;flex:none}
.resv .who b{font-size:13px;display:block}.resv .who small{font-size:11px;color:var(--mute)}
.resv .svc{font-size:11px;color:var(--mute);margin-top:6px}
.resv .atr{font-size:13px;line-height:1.45;margin:8px 0;padding:8px 10px;border-left:3px solid var(--gold);background:var(--s2);border-radius:0 10px 10px 0}
.resv .q{font-weight:700;font-size:14px;margin-top:6px}
.resv .yn{display:flex;gap:8px;margin-top:8px}
.resv .yn button{flex:1;padding:10px 8px;border-radius:12px;border:1px solid var(--line2);background:var(--s2);color:var(--tx);font-weight:700;font-size:13px;cursor:pointer;transition:transform .15s,background .2s}
.resv .yn button:hover{transform:translateY(-1px)}
.resv .yn .yes{background:rgba(22,199,132,.18);border-color:rgba(22,199,132,.5)}.resv .yn .no{background:rgba(255,92,106,.14);border-color:rgba(255,92,106,.45)}
.resv .hint{font-size:11px;color:var(--mute2);margin-top:8px}
.resv .ttl{display:block;font-size:14px}.resv .sub{font-size:12px;color:var(--mute);margin-top:6px}
.resv.closed{background:linear-gradient(135deg,rgba(22,199,132,.22),rgba(22,199,132,.05));border-color:rgba(22,199,132,.45)}
.resv.reopened{background:linear-gradient(135deg,rgba(255,92,106,.16),rgba(255,154,60,.06));border-color:rgba(255,92,106,.4)}
.ladder{display:flex;flex-direction:column-reverse;margin:10px 0 6px}
.ladder .rung{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:12px;border:1px solid var(--line2);background:var(--s2);font-size:12px;animation:rungIn .45s calc(.25s + var(--i)*.35s) both}
@keyframes rungIn{from{opacity:0;transform:translateY(8px)}}
.ladder .rung .lv{font-size:10px;font-weight:800;letter-spacing:.08em;padding:2px 6px;border-radius:6px;background:rgba(255,255,255,.08);color:var(--mute)}
.ladder .rung .nm{font-weight:600;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ladder .rung .now{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;white-space:nowrap}
.ladder .rung.passed{opacity:.6;border-style:dashed}.ladder .rung.passed .nm{text-decoration:line-through}
.ladder .rung.passed .now{color:var(--bad)}
.ladder .rung.cur{border-color:var(--saf);background:rgba(255,154,60,.14);box-shadow:0 0 0 1px rgba(255,154,60,.3),0 6px 20px rgba(255,154,60,.18)}
.ladder .rung.cur .lv{background:var(--saf);color:#1a0d00}.ladder .rung.cur .now{color:var(--saf)}
.ladder .rung.next{opacity:.55}
.ladder .up{display:block;width:2px;height:14px;margin:0 0 0 22px;background:linear-gradient(180deg,var(--saf),transparent);position:relative}
.ladder .up::after{content:"";position:absolute;left:-3px;top:-4px;width:8px;height:8px;border-radius:50%;background:var(--saf);box-shadow:0 0 10px var(--saf);animation:climb 1.6s .9s ease-in-out infinite}
@keyframes climb{0%{transform:translateY(14px);opacity:0}30%{opacity:1}100%{transform:translateY(-4px);opacity:0}}
.resv .clock{display:flex;align-items:center;gap:8px;font-size:12px;margin-top:4px}
.resv .clock .dot{width:8px;height:8px;border-radius:50%;background:var(--saf);box-shadow:0 0 10px var(--saf);animation:blink 1.4s infinite}
html[data-theme=light] .resv .ring .trk{stroke:rgba(0,0,0,.08)}
html[data-theme=light] .ladder .rung .lv{background:rgba(0,0,0,.06)}
@media (max-width:600px){.resv{flex-direction:column}.resv .ring{width:44px;height:44px}.resv .yn button{padding:12px 8px}}
'''
wr(r"mitra\web\mitra.css", css); print("patched mitra/web/mitra.css")

h = rd(r"mitra\web\index.html")
h = re.sub(r"/mitra\.css\?v=\d+", "/mitra.css?v=56", h); h = re.sub(r"/mitra\.js\?v=\d+", "/mitra.js?v=61", h); h = re.sub(r"/app\.js\?v=\d+", "/app.js?v=46", h)
wr(r"mitra\web\index.html", h); print("patched mitra/web/index.html")

# ============================================================================ tests that asserted the old "sent back" behaviour
edit(r"tools\tests\test_twoway.py", [
    ('''check("👎 re-opens the case and tells the senior", c["status"] == "Pending" and any("re-opened" in n["m"] for n in get("/api/state")["notifs"]), c["status"])
rr = post(f"/api/cases/{cid}/action", {"action": "reject", "officer": own, "reason": "Duplicate of an existing request"})''',
     '''check("👎 re-opens the case one rung UP the ladder and tells both officers", c["status"] == "Pending" and c["owner"] != own and c["level"] != "L1"
      and any("re-opened" in n["m"] for n in get("/api/state")["notifs"]) and any("rejected the resolution" in n["m"] for n in get("/api/state")["notifs"]), (c["status"], c["owner"], c["level"]))
check("the citizen's chat shows the escalation like a routing", any(e.get("kind") == "result" and e.get("title") == "Escalated to" for e in r["events"]), [e.get("kind") for e in r["events"]])
r = post("/api/chat", {"session": s, "action": f"case:{cid}"})
check("track inside the chat: live card with the ladder and the new holder", "wa-lad" in json.dumps(r) and c["owner"] in json.dumps(get("/api/state?session=" + s)), json.dumps(r)[:200])
own = c["owner"]                                                   # the senior holds it now
rr = post(f"/api/cases/{cid}/action", {"action": "reject", "officer": own, "reason": "Duplicate of an existing request"})'''),
])

edit(r"mitra\tests\test_notify.py", [
    ('''say(cit, "no it is not solved")
c = lo.wait("reopened", cid, 8)
check("officer gets 'Re-opened' live", bool(c) and c["tone"] == "bad", lo.cards)''',
     '''say(cit, "no it is not solved")
t0, c = time.time(), None
while time.time() - t0 < 8 and not c:          # the resolver is told (a notification), the senior gets the case event
    c = next((x for x in lo.cards if x["case_id"] == cid and x["title"].startswith("Re-opened")), None); time.sleep(0.2)
check("the officer whose resolution was rejected gets 'Re-opened' live", bool(c) and c["tone"] == "bad", lo.cards)'''),
])

edit(r"mitra\tests\test_realtime.py", [
    ('''check("feedback no re-opens", r["intent"] == "feedback_no" and "re-opened" in r["say"], r["say"])''',
     '''check("feedback no re-opens and moves it up the ladder", r["intent"] == "feedback_no" and "re-opened" in r["say"] and "up the ladder" in r["say"], r["say"])'''),
])
print("done")
