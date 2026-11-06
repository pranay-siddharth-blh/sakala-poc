"""Notifications for every screen.

Every change Mitra sees (case events and officer notifications from the Sakala change feed, and voice notes) is
written to a feed with the real wall-clock time it reached Mitra, so "just in" means just in, not the demo clock.
Each row is addressed to the screens it concerns: the officer who owns the case, the citizen whose request it
is, the Chief Secretary. Each viewer has a "seen" cursor, so a screen opened later (switching profile, logging in
as another officer, reloading) still pops what it missed, and nothing pops twice."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from . import store, tools

SCHEMA = """
CREATE TABLE IF NOT EXISTS feed (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, change TEXT, case_id TEXT, owner TEXT,
  chat_session TEXT, to_role TEXT, to_officer TEXT, from_role TEXT, from_officer TEXT, who TEXT, what TEXT,
  note TEXT, service TEXT, taluk TEXT, gp TEXT, src TEXT, note_id INTEGER, at TEXT);
CREATE INDEX IF NOT EXISTS ix_feed_owner ON feed(owner);
CREATE INDEX IF NOT EXISTS ix_feed_sess ON feed(chat_session);
CREATE TABLE IF NOT EXISTS seen (viewer TEXT PRIMARY KEY, last_id INTEGER, t TEXT);
"""
_ready = False
FRESH_MIN = 30          # a viewer who has never looked gets what arrived in the last 30 minutes
JUSTIN_MIN = 60         # the officer's "Just in" shelf: arrivals in the last hour that are still open with them

OFFICER_IN = {"new", "rerouted", "escalated", "nudge", "citizen_reply", "reopened", "appeal", "feedback_yes", "deadline"}
OFFICER_SENT = {"accepted", "info", "resolved", "rejected", "atr_flagged"}
CITIZEN_IN = {"new", "scrutiny", "accepted", "info", "returned", "rejected", "resolved", "escalated", "rerouted", "compensation", "deadline"}
CS_IN = {"new", "escalated", "reopened", "appeal", "rejected", "resolved", "nudge", "deadline"}
JUSTIN = {"new", "rerouted", "escalated", "appeal", "reopened"}
# officer notifications that add something the case events do not already say (the rest would be duplicates)
NOTIF_KEEP = re.compile(r"due today|due tomorrow|escalated to .+\(no action|re-opened by the citizen after|deadline missed|needs a human decision", re.I)
DEFAULT_NUDGE = "Officer and their senior notified"


def _init():
    global _ready
    if not _ready:
        store.conn().executescript(SCHEMA)
        _ready = True


def _now() -> datetime:
    return datetime.now()


# ------------------------------------------------------------------ writing the feed
def log_case(e: dict, change: str) -> dict:
    _init()
    what = e.get("what") or ""
    if change == "update" and what.startswith("Sent to scrutiny"):
        change = "scrutiny"
    if what.lower().startswith("legal deadline missed"):
        change = "deadline"
    rid = store.run("INSERT INTO feed(ts,kind,change,case_id,owner,chat_session,who,what,note,service,taluk,gp,src,at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", _now().isoformat(timespec="seconds"), "case", change,
                    e.get("case_id"), e.get("owner"), e.get("session") or "", e.get("who"), what, (e.get("note") or "")[:300],
                    e.get("service"), e.get("taluk"), e.get("gp"), e.get("src"), e.get("t"))
    return row(rid)


def log_notif(n: dict) -> dict | None:
    _init()
    if not NOTIF_KEEP.search(n.get("msg") or ""):
        return None
    m = re.search(r"\b((?:GR|SK)-[A-Z0-9]+)", n.get("msg") or "")
    rid = store.run("INSERT INTO feed(ts,kind,change,case_id,owner,to_role,to_officer,what,at) VALUES (?,?,?,?,?,?,?,?,?)",
                    _now().isoformat(timespec="seconds"), "notif", "notif", m.group(1) if m else "", n.get("officer_id"),
                    "officer", n.get("officer_id"), n.get("msg"), n.get("t"))
    return row(rid)


def log_voice(nid: int, to_role: str, to_officer: str, case_id: str, from_role: str, from_officer: str, transcript: str) -> dict:
    _init()
    rid = store.run("INSERT INTO feed(ts,kind,change,case_id,to_role,to_officer,from_role,from_officer,note,note_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)", _now().isoformat(timespec="seconds"), "voice", "voice", case_id or "",
                    to_role, to_officer or "", from_role, from_officer or "", (transcript or "")[:300], nid)
    return row(rid)


def row(rid: int) -> dict:
    return store.q1("SELECT * FROM feed WHERE id=?", rid)


def reset():
    """The Sakala demo was reset: the old cases are gone, so is their news."""
    _init()
    store.run("DELETE FROM feed")
    store.run("DELETE FROM seen")


# ------------------------------------------------------------------ who should see what
def viewer(sess: dict) -> str:
    p = sess.get("profile")
    if p == "officer":
        return "officer:" + (sess.get("officer") or "")
    if p == "cs":
        return "cs"
    return "citizen:" + (sess.get("chat_session") or "")


def _my_cases(chat_session: str) -> set[str]:
    return {r["case_id"] for r in store.q("SELECT DISTINCT case_id FROM feed WHERE chat_session=? AND kind='case'", chat_session)}


def relevant(r: dict, sess: dict, mine: set[str] | None = None) -> bool:
    p, oid, cs = sess.get("profile"), sess.get("officer") or "", sess.get("chat_session") or ""
    k, ch = r["kind"], r["change"]
    voice_echo = (r.get("note") or "").startswith("(voice note)")      # the voice-note card already says it
    if p == "officer":
        if k == "case":
            if r["owner"] != oid:
                return False
            if ch in OFFICER_IN:
                return not (ch == "citizen_reply" and voice_echo)
            return ch in OFFICER_SENT and not (ch == "info" and voice_echo)
        if k == "notif":
            return r["to_officer"] == oid
        if k == "voice":
            return r["to_role"] == "officer" and r["to_officer"] == oid
        return False
    if p == "cs":
        if k == "case":
            return ch in CS_IN
        return k == "voice" and r["to_role"] == "cs"
    # citizen
    if k == "case":
        return bool(cs) and r["chat_session"] == cs and ch in CITIZEN_IN and not (ch == "info" and voice_echo)
    if k == "voice" and r["to_role"] == "citizen":
        mine = mine if mine is not None else _my_cases(cs)
        return r["case_id"] in mine
    return False


# ------------------------------------------------------------------ what the card says
def _place(r):
    gp, tk = r.get("gp") or "", r.get("taluk") or ""
    return f"{gp} GP, {tk}" if gp and tk else gp or tk


def _via(r):
    s = (r.get("src") or "").lower()
    return {"mitra": "via Mitra (voice)", "whatsapp": "via WhatsApp", "app": "via the app", "web": "via the web portal",
            "csc": "via a CSC", "camp": "at a Praja Seva camp", "call": "via the 1902 call centre"}.get(s, f"via {s}" if s else "")


def _nudge_msg(r):
    n = (r.get("note") or "").strip()
    return "" if not n or n == DEFAULT_NUDGE else n


def ago(ts: str) -> str:
    try:
        s = (_now() - datetime.fromisoformat(ts)).total_seconds()
    except Exception:
        return ""
    if s < 45:
        return "just now"
    if s < 3600:
        return f"{int(s // 60) or 1} min ago"
    if s < 86400:
        return f"{int(s // 3600)} h ago"
    return f"{int(s // 86400)} d ago"


def card(r: dict, sess: dict) -> dict:
    p, ch, cid = sess.get("profile"), r["change"], r.get("case_id") or ""
    who = (r.get("who") or "").replace("Citizen (Mitra)", "The citizen").replace("Citizen (Sakala Mitra)", "The citizen")
    svc, place, note, what = r.get("service") or "", _place(r), r.get("note") or "", r.get("what") or ""
    owner_short = tools.off_name(r.get("owner") or "") if r.get("owner") else ""
    c = {"id": r["id"], "ts": r["ts"], "ago": ago(r["ts"]), "kind": r["kind"], "change": ch, "case_id": cid,
         "tone": "info", "icon": "•", "title": what or ch, "body": note, "actions": [], "speak": "", "sticky": False,
         "owner": r.get("owner") or ""}
    open_ = [{"label": "Open", "say": f"open {cid}"}] if cid else []

    if r["kind"] == "voice":
        frm = {"cs": "the Chief Secretary", "citizen": "the citizen"}.get(r.get("from_role"), tools.off_name(r.get("from_officer") or "") or "the officer")
        c.update(tone="voice", icon="🎙", title=f"Voice note from {frm}", body=note.replace("(voice note) ", ""),
                 actions=[{"label": "▶ Play", "play": r.get("note_id")}] + open_, speak=f"New voice note from {frm}: {note}", sticky=True)
        return c

    if r["kind"] == "notif":
        if re.search(r"re-opened by the citizen", what, re.I):      # the officer whose resolution was rejected
            c.update(tone="bad", icon="↩", title=f"Re-opened · {cid}", body=what, actions=open_, speak=what, sticky=True)
            return c
        bad = re.search(r"escalated|re-opened|missed", what, re.I)
        c.update(tone="bad" if bad else "warn", icon="⏰" if not bad else "⚠", title="Deadline" if re.search(r"due", what) else "Heads up",
                 body=what, actions=open_, speak=what)
        return c

    if p == "officer":
        if ch == "new":
            c.update(tone="new", icon="⚡", title=f"Just in · {cid}", body=" · ".join(x for x in (svc, place, _via(r)) if x),
                     actions=open_, speak=f"New request {cid}: {svc}{' in ' + place if place else ''}, routed to you.", sticky=True)
            if what.startswith("Application registered"):
                c["title"] = f"New Sakala application · {cid}"
        elif ch == "rerouted":
            if what.lower().startswith("transferred to"):
                frm = r.get("who") or "another officer"
                c.update(tone="new", icon="↪", title=f"Transferred to you · {cid}", body=f"{frm} sent you {svc}{' · ' + place if place else ''}: not their jurisdiction",
                         actions=open_, speak=f"{cid} was transferred to you by {frm}: it was not in their jurisdiction.", sticky=True)
            else:
                c.update(tone="new", icon="↪", title=f"Assigned to you · {cid}", body=f"The scrutiny desk sent you {svc}{' · ' + place if place else ''}",
                         actions=open_, speak=f"{cid} was assigned to you by the scrutiny desk.")
        elif ch == "escalated":
            c.update(tone="bad", icon="⏫", title=f"Escalated to you · {cid}", body=note or what, actions=open_, speak=f"{cid} escalated to you.")
        elif ch == "nudge":
            m = _nudge_msg(r)
            c.update(tone="warn", icon="🔔", title="Reminder from the Chief Secretary", body=f"{cid}{' · ' + svc if svc else ''}" + (f" — “{m}”" if m else " — please act on it."),
                     actions=open_, speak=f"The Chief Secretary's office reminds you about {cid}." + (f" {m}" if m else ""), sticky=True)
        elif ch == "citizen_reply":
            c.update(tone="info", icon="💬", title=f"The citizen replied · {cid}", body=note, actions=open_, speak=f"The citizen replied on {cid}: {note}")
        elif ch == "reopened":
            c.update(tone="bad", icon="↩", title=f"Re-opened · {cid}", body=note or "The citizen says it is not solved. The clock has restarted.",
                     actions=open_, speak=f"{cid} was re-opened by the citizen and is with you now; the clock has restarted.", sticky=True)
        elif ch == "appeal":
            c.update(tone="warn", icon="⚖", title=f"Appeal · {cid}", body=f"{what}. {note}".strip(), actions=open_, speak=f"An appeal on {cid} has come to you.")
        elif ch == "feedback_yes":
            c.update(tone="ok", icon="👍", title=f"Confirmed solved · {cid}", body="The citizen confirmed your action fixed it.", speak="")
        elif ch == "deadline":
            c.update(tone="bad", icon="⚠", title=f"Sakala deadline missed · {cid}", body=note or "Compensation is now due under the Sakala Act.",
                     actions=open_, speak=f"The Sakala deadline on {cid} has been missed.", sticky=True)
        else:   # the officer's own action: confirm that it reached the citizen
            c.update(tone="sent", icon="✓", title="Sent to the citizen", body=f"{what} · {cid}", actions=[])
        return c

    if p == "cs":
        if ch == "new":
            c.update(tone="info", icon="⚡", title=f"New request · {cid}", body=" · ".join(x for x in (svc, place, f"→ {owner_short}" if owner_short else "", _via(r)) if x), actions=open_)
        elif ch == "escalated":
            c.update(tone="bad", icon="⏫", title=f"Auto-escalated · {cid}", body=what + (f" · {note}" if note else ""), actions=open_)
        elif ch == "reopened":
            c.update(tone="bad", icon="↩", title=f"Re-opened by the citizen · {cid}", body=f"{svc} · now with {owner_short}" + (f" · {note}" if note else ""), actions=open_)
        elif ch == "appeal":
            c.update(tone="warn", icon="⚖", title=f"Citizen appealed · {cid}", body=what, actions=open_)
        elif ch == "rejected":
            c.update(tone="warn", icon="✕", title=f"Rejected · {cid}", body=f"{who}: {note}", actions=open_)
        elif ch == "resolved":
            c.update(tone="ok", icon="✓", title=f"Resolved · {cid}", body=f"by {who}" + (f" · {svc}" if svc else ""), actions=open_)
        elif ch == "deadline":
            c.update(tone="bad", icon="⚠", title=f"Sakala deadline missed · {cid}", body=f"{svc} · {owner_short}", actions=open_)
        elif ch == "nudge":
            m = _nudge_msg(r)
            c.update(tone="sent", icon="🔔", title="Reminder delivered", body=f"{owner_short} · {cid}" + (f" — “{m}”" if m else ""), actions=[])
        return c

    # citizen
    if ch == "new":
        if what.startswith("Application registered"):
            c.update(tone="ok", icon="✓", title=f"Application registered · {cid}", body=f"{svc} · {what.split('·')[-1].strip()}")
        else:
            c.update(tone="ok", icon="✓", title=f"Filed · {cid}", body=f"{svc} · {what}")
        if c["owner"]:
            c["actions"] = [{"label": "View as the officer →", "as_officer": c["owner"], "case_id": cid}]
    elif ch == "scrutiny":
        c.update(tone="info", icon="🔎", title=f"A person will check it · {cid}", body="It was not clear enough to route automatically; the scrutiny desk will send it to the right office.")
    elif ch == "accepted":
        c.update(tone="ok", icon="✓", title=f"{who} accepted your request", body=f"Work has started on {cid}.")
    elif ch == "info":
        c.update(tone="info", icon="❓", title=f"{who} has a question", body=f"“{note}” · {cid}", sticky=True,
                 actions=[{"label": "Reply", "say": "reply"}])
    elif ch == "returned":
        c.update(tone="info", icon="↻", title=f"Being re-checked · {cid}", body="It is going to the scrutiny desk to find the right office.")
    elif ch == "rejected":
        c.update(tone="bad", icon="✕", title=f"{who} could not accept {cid}", body=f"Reason: {note}. You can appeal.", sticky=True,
                 actions=[{"label": "Appeal", "say": "appeal"}])
    elif ch == "resolved":
        c.update(tone="ok", icon="✓", title=f"Resolved · {cid}", body=f"{who} filed the action taken. Is it actually solved?", sticky=True,
                 actions=[{"label": "Solved 👍", "say": "yes it is solved"}, {"label": "Not solved 👎", "say": "no it is not solved"}])
    elif ch == "escalated":
        c.update(tone="warn", icon="⏫", title=f"Moved up · {cid}", body=f"{what}: it was not acted on in time.")
    elif ch == "rerouted":
        c.update(tone="info", icon="↪", title=f"Now with {owner_short}",
                 body=(f"{cid} was outside the first officer's jurisdiction, so it went straight to the right office." if what.lower().startswith("transferred to")
                       else f"The scrutiny desk found the right office for {cid}."))
    elif ch == "compensation":
        c.update(tone="ok", icon="₹", title=what, body=f"Sakala compensation on {cid} for the delay.")
    elif ch == "deadline":
        c.update(tone="warn", icon="⚠", title=f"The legal deadline was missed · {cid}", body="Under the Sakala Act you are owed ₹20 a day of delay, up to ₹500; the Competent Officer has been alerted.")
    return c


# ------------------------------------------------------------------ reading
def _cursor(v: str) -> int | None:
    r = store.q1("SELECT last_id FROM seen WHERE viewer=?", v)
    return r["last_id"] if r else None


def pending(sess: dict, limit: int = 8) -> list[dict]:
    """What this screen has not been shown yet (oldest first)."""
    _init()
    cur = _cursor(viewer(sess))
    if cur is None:
        since = (_now() - timedelta(minutes=FRESH_MIN)).isoformat(timespec="seconds")
        rows = store.q("SELECT * FROM feed WHERE ts>=? ORDER BY id LIMIT 600", since)
    else:
        rows = store.q("SELECT * FROM feed WHERE id>? ORDER BY id LIMIT 600", cur)
    mine = _my_cases(sess.get("chat_session") or "")
    out = [card(r, sess) for r in rows if relevant(r, sess, mine)]
    return out[-limit:]


def history(sess: dict, limit: int = 30) -> list[dict]:
    _init()
    mine = _my_cases(sess.get("chat_session") or "")
    rows = store.q("SELECT * FROM feed ORDER BY id DESC LIMIT 800")
    return [card(r, sess) for r in rows if relevant(r, sess, mine)][:limit]


def mark_seen(sess: dict, upto: int | None = None):
    _init()
    if upto is None:
        upto = (store.q1("SELECT MAX(id) m FROM feed") or {}).get("m") or 0
    v = viewer(sess)
    cur = _cursor(v) or 0
    store.run("INSERT INTO seen(viewer,last_id,t) VALUES (?,?,?) ON CONFLICT(viewer) DO UPDATE SET last_id=excluded.last_id, t=excluded.t",
              v, max(cur, int(upto)), _now().isoformat(timespec="seconds"))


def just_in_rows(officer: str) -> list[dict]:
    """Arrivals for this officer in the last hour, newest first, one per case."""
    _init()
    since = (_now() - timedelta(minutes=JUSTIN_MIN)).isoformat(timespec="seconds")
    rows = store.q("SELECT * FROM feed WHERE kind='case' AND owner=? AND ts>=? ORDER BY id DESC", officer, since)
    out, seen_ids = [], set()
    for r in rows:
        if r["change"] in JUSTIN and r["case_id"] not in seen_ids:
            seen_ids.add(r["case_id"])
            out.append({"case_id": r["case_id"], "change": r["change"], "ts": r["ts"], "ago": ago(r["ts"]), "service": r["service"],
                        "place": _place(r), "via": _via(r), "what": r["what"]})
    return out[:8]
