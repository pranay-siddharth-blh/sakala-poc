"""Executes an intent against the Sakala POC and returns what Mitra should say and what the
screen should do. All business rules stay inside the Sakala API; this layer only orchestrates."""
from __future__ import annotations

import difflib
import re
import time
from datetime import datetime, timedelta

import httpx

from . import config, guard, sakala, store
from .speech import clean_for_speech

OPEN = ("Pending", "In progress", "Info requested")
_boot: dict = {}


async def boot() -> dict:
    global _boot
    if not _boot:
        _boot = await sakala.bootstrap()
    return _boot


def officers() -> dict:
    return _boot.get("officers", {})


def on_ladder(viewer: str, owner: str) -> bool:
    """Guardrail 12: an officer may read a case they hold or one held by an officer who reports to them (up the chain)."""
    seen, o = 0, owner
    while o and seen < 8:
        if o == viewer:
            return True
        o = (officers().get(o) or {}).get("up"); seen += 1
    return False


def off_name(oid: str, short: bool = True) -> str:
    o = officers().get(oid) or {}
    return o.get("short" if short else "n") or oid or "the officer"


def find_officer(text: str) -> str | None:
    """Fuzzy match 'tahsildar hunsur', 'pdo attigodu', 'the EO of Piriyapatna'..."""
    low = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    low = re.sub(r"\b(log in as|login as|switch to|the|officer|nudge|remind|send|a|note|message|to|voice|tell|of|please)\b", " ", low)
    low = re.sub(r"\s+", " ", low).strip()
    if not low:
        return None
    best, score = None, 0.0
    for oid, o in officers().items():
        cands = [o.get("short", ""), o.get("n", ""), f"{o.get('role','')} {o.get('taluk','')} {o.get('gp','')}", oid.replace("_", " ")]
        for cnd in cands:
            cl = cnd.lower()
            s = difflib.SequenceMatcher(None, low, cl).ratio()
            words = [w for w in low.split() if len(w) > 2]
            if words and all(w in cl for w in words):
                s = max(s, 0.92)
            if s > score:
                best, score = oid, s
    return best if score >= 0.55 else None


def days_left(c: dict, now: datetime) -> tuple[int, bool]:
    sk = c.get("sakala")
    if sk and sk.get("complete"):
        used = (now - datetime.fromisoformat(sk["complete"])).days
        return int(sk.get("dueDays", 7)) - used, True
    used = (now - datetime.fromisoformat(c["levelSince"])).days
    total = (_boot.get("sla") or {}).get(c.get("level"), 7)
    return total - used, False


def is_open(c: dict) -> bool:
    return c.get("status") in OPEN


def pretty_left(left: int) -> str:
    if left < 0:
        return f"{-left} day{'s' if left != -1 else ''} overdue"
    if left == 0:
        return "due today"
    return f"{left} day{'s' if left != 1 else ''} left"


def case_brief(c: dict, now: datetime) -> dict:
    left, legal = days_left(c, now)
    u = c.get("u") or {}
    return {"id": c["id"], "service": c.get("service") or u.get("svc") or "Scrutiny desk", "dept": u.get("d"),
            "grievance": (c.get("u") or {}).get("gr"), "status": c["status"], "owner": c["owner"],
            "ownerShort": off_name(c["owner"]), "level": c["level"], "left": left, "legal": legal,
            "leftText": pretty_left(left), "vulnerable": bool(c.get("vulnerable")), "taluk": c.get("taluk"),
            "gp": c.get("gp") or "", "masked": c.get("masked") or "", "summary": c.get("summary") or "",
            "src": c.get("src"), "created": c.get("created"), "atr": c.get("atr"), "atrScore": c.get("atrScore"),
            "routeBasis": c.get("routeBasis"), "why": (c.get("u") or {}).get("why"), "conf": (c.get("u") or {}).get("conf"),
            "history": c.get("history") or [], "audit": c.get("audit"), "sakala": c.get("sakala"),
            "real": bool(c.get("real")), "mine": bool(c.get("mine"))}


def spoken_case(b: dict) -> str:
    text = b["summary"] or b["masked"]
    text = clean_for_speech(text)
    if len(text) > 220:
        text = text[:217].rsplit(" ", 1)[0] + "..."
    prio = " Marked priority: vulnerable citizen." if b["vulnerable"] else ""
    where = f"{b['gp']} Gram Panchayat, " if b["gp"] else ""
    holder = f" It is with {b['ownerShort']}, level {b['level']}." if b.get("ownerShort") else ""
    return (f"{b['id']}, {b['service']}, {where}{b['taluk']} taluk. {b['leftText']}.{holder}{prio} "
            f"The citizen says: {text}")


async def load_state(sess: dict, full_ids: list[str] | None = None) -> dict:
    """Statewide caseload: list views use the light shape (no raw text / audit); a specific case is fetched whole."""
    scope = "citizen" if sess["profile"] == "citizen" else "all"
    if sess["profile"] == "officer":
        st = await sakala.state(session=sess["chat_session"], scope=scope, owner=sess["officer"], light=True)
    else:
        st = await sakala.state(session=sess["chat_session"], scope=scope, light=True)
    st["_now"] = datetime.fromisoformat(st["now"])
    if full_ids:
        full = await sakala.state(session=sess["chat_session"], scope="all", id=",".join(full_ids))
        byid = {c["id"]: c for c in full["cases"]}
        st["cases"] = [byid.get(c["id"], c) for c in st["cases"]]
        for cid, c in byid.items():
            if not any(x["id"] == cid for x in st["cases"]):
                st["cases"].append(c)
    return st


async def full_case(cid: str) -> dict | None:
    try:
        return await sakala.case(cid)
    except Exception:
        return None


def inbox_for(st: dict, officer: str) -> list[dict]:
    now = st["_now"]
    rows = [case_brief(c, now) for c in st["cases"] if c["owner"] == officer and is_open(c)]
    rows.sort(key=lambda b: (not b["vulnerable"], b["left"]))
    return rows


# ------------------------------------------------------------------ the dispatcher
# guardrail 17: these change a case or the demo for good, so Mitra reads the action back and waits for a yes
CONFIRM = ("reject", "return_case", "resolve", "comp_order", "comp_hrms", "nudge", "reset_demo")
VERB = {"reject": r"\breject", "return_case": r"\breturn", "resolve": r"\b(resolve|close)", "comp_order": r"\bcompensat",
        "comp_hrms": r"\b(hrms|debit)", "nudge": r"\b(nudge|remind)", "reset_demo": r"\breset"}
PENDING_TTL = 120


async def execute(sess: dict, intent: str, args: dict) -> dict:
    await boot()
    st = sess["state"]
    pend = st.get("pending_action")
    if pend and time.time() - pend.get("t", 0) > PENDING_TTL:
        st.pop("pending_action", None); pend = None
    fn = HANDLERS.get(intent) or t_smalltalk
    try:
        said_now = (args.get("_text") or "").lower()
        restated = bool(pend) and bool(re.search(VERB.get(pend["intent"], r"$^"), said_now)) and not re.search(r"\b(no|not|don.?t|never|cancel|stop|wait)\b", said_now)
        if pend and (intent == "confirm_action" or restated or (intent == "confirm" and sess["profile"] != "citizen")
                     or (intent == "confirm" and pend["intent"] == "reset_demo")
                     or (intent == pend["intent"] and _same_target(sess, intent, args, pend))):
            st.pop("pending_action", None)                   # yes (or the same action asked for again): do it now
            intent, fn = pend["intent"], HANDLERS[pend["intent"]]
            res = await fn(sess, {**pend["args"], "_confirmed": True})
            res.setdefault("ui", [])                          # the question bar goes away the moment it is answered
            res["ui"] = [u for u in res["ui"] if u.get("op") != "confirm"] + [{"op": "confirm", "clear": True}]
        elif pend and (intent == "cancel_action" or intent in ("change", "stop") and re.search(r"\b(no|nope|don.?t|do not|cancel|stop|never ?mind|wait|not now)\b", said_now)):
            st.pop("pending_action", None)
            res = {"say": "Okay, I have not done it. Nothing was changed.", "ui": [{"op": "confirm", "clear": True}]}
        elif sess["profile"] == "citizen" and st.get("awaiting_feedback") and intent in ("confirm_action", "cancel_action", "confirm") \
                and not (st.get("draft") or {}).get("service") and st.get("flow") not in ("confirm", "ask_place", "ask_gp"):
            intent = "feedback_no" if intent == "cancel_action" else "feedback_yes"   # yes / no answers "was it really solved?"
            fn = HANDLERS[intent]
            res = await fn(sess, args)
        elif intent == "confirm_action" and sess["profile"] == "citizen":
            intent, fn = "confirm", HANDLERS["confirm"]                  # nothing pending: the citizen is confirming their request
            res = await fn(sess, args)
        elif intent == "confirm_action":
            res = {"say": "There is nothing waiting for your confirmation.", "ui": []}
        elif intent == "cancel_action":
            res = {"say": "Okay.", "ui": [{"op": "confirm", "clear": True}]}
        elif intent in CONFIRM and not args.get("_confirmed"):
            q = await _confirm_question(sess, intent, args)
            if q:
                st["pending_action"] = {"intent": intent, "args": {k: v for k, v in args.items() if k != "_confirmed"},
                                        "case": st.get("case_id"), "t": time.time(), "question": q}
                res = {"say": q, "ui": [{"op": "confirm", "question": q}]}
            else:
                res = await fn(sess, args)                   # nothing would happen yet (no case open, report too short ...)
        else:
            if pend and intent not in ("smalltalk", "repeat", "help", "identity"):
                st.pop("pending_action", None)               # the person moved on: the waiting action is dropped
            res = await fn(sess, args)
    except httpx.HTTPError:
        res = {"say": "I could not reach the Sakala server just now. Please try again in a moment.",
               "ui": [{"op": "toast", "h": "Sakala", "m": "The Sakala server did not answer."}]}
    res.setdefault("ui", [])
    if any(u.get("op") == "viz" for u in res["ui"]):
        st["last_viz"] = time.time()
    if res.get("say"):
        res["say"] = guard.speakable_ids(guard.scrub(res["say"]))
    res["intent"] = intent
    if res.get("say"):
        sess["state"]["last_say"] = res["say"]
    store.save_session(sess)
    return res


def _same_target(sess, intent, args, pend) -> bool:
    """The same action asked for again while it waits for a yes (a live model often repeats the call): that is the yes."""
    if intent == "reset_demo":
        return True
    if intent == "nudge":
        return (args.get("officer") or args.get("case_id") or "") in ("", pend["args"].get("officer") or pend["args"].get("case_id") or "")
    return sess["state"].get("case_id") == pend.get("case")


async def _confirm_question(sess, intent, args) -> str | None:
    """The read-back for an action that cannot be undone, or None when the handler would not act anyway."""
    if intent == "reset_demo":
        return "Reset the demo to go-live? Everything done since then will be cleared. Shall I go ahead?"
    if intent == "nudge":
        cid, oid, msg, err = await _nudge_target(sess, args)
        if err:
            return None
        st = await load_state(sess)
        c = next((x for x in st["cases"] if x["id"] == cid), None)
        who = off_name(c["owner"]) if c else "the officer"
        spoken = f"the application ending in {cid[-4:]}" if str(cid).upper().startswith("SK") else cid
        return f"Send a reminder to {who} on {spoken}" + (f", with your message: {msg}" if msg else "") + "? Shall I?"
    cid = sess["state"].get("case_id")
    if not cid:
        return None
    st = await load_state(sess)
    c = next((x for x in st["cases"] if x["id"] == cid), None)
    if c and not is_open(c) and intent not in ("comp_order", "comp_hrms"):
        return None                                          # closed: the handler explains why nothing can be done
    sid = f"the application ending in {cid[-4:]}" if cid.upper().startswith("SK") else cid       # long Sakala numbers read badly aloud
    what = sid + (f", {c['service']}," if c and c.get("service") else "")
    if intent == "reject":
        reason = (args.get("reason") or "").strip() or "Duplicate of an existing request"
        return f"Reject {what} with the reason: {reason}? The citizen will be told and can appeal. Shall I go ahead?"
    if intent == "return_case":
        to, place = _return_target(args)
        sug = " · ".join(x for x in (to, place) if x)
        if sug:
            try:                                             # name the officer it will really reach (nothing changes yet)
                pv = await sakala._get(f"/api/cases/{cid}/transfer_preview", officer="" if sess["profile"] == "cs" else sess["officer"], to=to, place=place)
            except Exception:  # noqa: BLE001
                pv = {}
            o = (pv or {}).get("officer")
            if o:
                return f"Return {what} as outside your jurisdiction and send it straight to {o['short']}? They will be notified. Shall I go ahead?"
            if pv and pv.get("scrutiny"):
                why = " (that points back to you)" if "back to the returning officer" in (pv.get("how") or "") else ""
                return (f"I could not match {sug} to an officer{why}. Shall I return {what} to the scrutiny desk instead? "
                        f"Or name the officer or the taluk.")
            return f"Return {what} as outside your jurisdiction and send it straight to {sug}? They will be notified. Shall I go ahead?"
        return f"Return {what} to the scrutiny desk as outside your jurisdiction? Shall I go ahead?"
    if intent == "resolve":
        atr = (args.get("atr") or "").strip()
        if len(atr) < 15:
            return None
        return f"Close {what} with this report: {atr}? The citizen will be asked to confirm. Shall I go ahead?"
    if intent == "comp_order":
        return f"Order Sakala compensation on {what}? It is paid to the citizen and recovered from the officer at fault. Shall I go ahead?"
    if intent == "comp_hrms":
        return f"Approve the HRMS debit note on {what}? Shall I go ahead?"
    return None


async def t_view_as_officer(sess, args):
    """Open a case in the view of the officer who holds it (any grievance, any officer): a number said > an officer named > the
    case on screen > the citizen's latest request > the case filed most recently in the state (the one the notification was about)."""
    said = args.get("_text") or ""
    st = sess["state"]
    cid = str(args.get("case_id") or "").upper().replace(" ", "")
    m = re.search(r"\b(GR)[- ]?(\d{5,})\b|\b(SK-?[A-Z0-9]{8,})\b", said, re.I)
    if not re.match(r"^(GR-\d{5,}|SK-?[A-Z0-9]{8,})$", cid):
        cid = (f"GR-{m.group(2)}" if m.group(2) else m.group(3).upper()) if m else ""
    oid = None
    if not cid and (args.get("officer") or _OFFICER_RX.search(said)):
        oid = find_officer(args.get("officer") or said)
    if not cid and not oid and sess["profile"] == "citizen" and st.get("my_cases"):
        num = lambda x: int(re.sub(r"\D", "", x) or 0)
        cid = max(st["my_cases"], key=lambda x: (x.startswith("GR-"), num(x)))      # the request this citizen filed last
    if not cid and not oid:
        cid = st.get("case_id")
    if not cid and not oid:
        r = await sakala._post("/api/query", {"tool": "find_cases", "args": {"sort": "newest", "limit": 1}})
        cid = ((r.get("cases") or [{}])[0] or {}).get("id")
    c = await full_case(cid) if cid else None
    if cid and not c:
        return {"say": f"I could not find {cid} in Sakala."}
    oid = oid or (c or {}).get("owner")
    if not oid:
        return {"say": "Which case or officer should I open? Say a grievance number or an officer's name."}
    where = f"{cid} on the desk of {off_name(oid, False)}" if cid else f"the desk of {off_name(oid, False)}"
    return {"say": f"Opening {where}.", "ui": [{"op": "view_officer", "officer": oid, "case_id": cid or ""}]}


async def t_ask_knowledge(sess, args):
    """A general question answered from mitra/knowledge.yaml and nothing else; the model only puts the fact into conversation."""
    from . import knowledge
    q = (args.get("question") or args.get("_text") or "").strip()
    st = sess["state"]
    k = knowledge.answer(q, last=st.get("kb_last") or "", strict=False)
    if not k:
        return {"say": "That is not in my notes yet, so I will not guess. I can tell you about Sakala, iPGRS, the Praja Seva Department, "
                       "compensation and appeals, the officers' ladder, how I route a request, or who the Chief Secretary is.",
                "data": {"known_topics": knowledge.topics()[:12]}}
    st["kb_last"] = k["id"]
    say = k["say"]
    html = f"<p>{_esc(k['say'])}</p>" + (f"<p class='more'>{_esc(k['more'])}</p>" if k.get("more") else "") + \
           (f"<div class='src'>Source · {_esc(k['source'])}</div>" if k.get("source") else "")
    return {"say": say, "data": {"topic": k["topic"], "more": k.get("more") or "", "source": k.get("source") or "",
                                 "related": [r["topic"] for r in k.get("related") or []]},
            "ui": [{"op": "answer", "q": k["topic"], "html": html}]}


def _esc(s: str) -> str:
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def t_identity(sess, args):
    return {"say": guard.identity_answer(args.get("_text") or ""), "ui": []}


async def t_forget(sess, args):
    store.forget(sess["id"])
    for k in ("last_say", "last_audio", "pending_action"):
        sess["state"].pop(k, None)
    return {"say": "Done. I have deleted our conversation from this screen.", "ui": [{"op": "forget"}]}


async def t_confirm_action(sess, args):                     # reached only when nothing is pending (see execute)
    return {"say": "There is nothing waiting for your confirmation."}


async def t_cancel_action(sess, args):
    return {"say": "Okay."}



# ------------------------------------------------------------------ the question router (question bank, 17 Oct)
# Data questions asked in many ways all reach the exact SQL-backed function, never a guess: counts with filters, officers,
# places, the iPGRS sample, rankings, comparisons, "my cases". Used by the brain (deterministic fast path) and by ask_data.
PLACE_ALIAS = {"mysore": "Mysuru", "shimoga": "Shivamogga", "belgaum": "Belagavi", "bangalore": "Bengaluru", "bagalkot": "Bagalkote",
               "gulbarga": "Kalaburagi", "bellary": "Ballari", "bijapur": "Vijayapura", "tumkur": "Tumakuru", "chikmagalur": "Chikkamagaluru",
               "hubli": "Dharwad", "mangalore": "Dakshina Kannada", "karwar": "Uttara Kannada", "periyapatna": "Piriyapatna", "hunsuru": "Hunsur"}
DEPT_WORDS = {"revenue": "Revenue", "rdpr": "RDPR", "rural development": "RDPR", "panchayat raj": "RDPR", "food": "Food",
              "civil supplies": "Food", "ration": "Food"}
_PL: dict = {}


def _places():
    if not _PL:
        geo = _boot.get("geo") or {}
        for d, tk in geo.items():
            _PL.setdefault("district", {})[d.lower()] = d
            for t, gps in (tk or {}).items():
                _PL.setdefault("taluk", {})[t.lower()] = t
                for g in gps or []:
                    _PL.setdefault("gp", {})[g.lower()] = g
    return _PL


def _find_place(t: str, kind: str) -> str:
    low = t.lower()
    for a, canon in PLACE_ALIAS.items():
        low = re.sub(r"\b" + a + r"\b", canon.lower(), low)
    names = sorted(_places().get(kind, {}).items(), key=lambda kv: -len(kv[0]))
    for k, v in names:
        if len(k) >= 4 and re.search(r"\b" + re.escape(k) + r"\b", low):
            if kind == "taluk" and k in _places().get("district", {}) and re.search(r"\b" + re.escape(k) + r"\s+district\b", low):
                continue                                      # "Mysuru district" is the district
            if kind == "district" and k in _places().get("taluk", {}) and re.search(r"\b" + re.escape(k) + r"\s+taluk\b", low):
                continue
            return v
    return ""


_COUNT_RX = re.compile(r"\b(how many|how much|count|number of|total|tally|statewide|state ?wide|pending count|figure|caseload|in all)\b", re.I)
_CASEWORD_RX = re.compile(r"\b(cases?|grievances?|complaints?|requests?|applications?|pending|unresolved|open|overdue|backlog|caseload)\b", re.I)
_ACTION_RX = re.compile(r"\b(nudge|remind|tell (him|her|them)|send|reject|accept|resolve|return|approve|order|close (it|this)|file|register)\b", re.I)
_OFFICER_RX = re.compile(r"\b(tahsildar|pdo|eo|aee|ae rdws|food inspector|adlr|ddlr|deputy commissioner|assistant commissioner|zp ceo|ceo|dd food)\b", re.I)


def _filters(t: str) -> dict:
    a = {}
    d, tk = _find_place(t, "district"), _find_place(t, "taluk")
    if tk and (not d or tk.lower() != d.lower() or re.search(r"\btaluk\b", t, re.I)):
        a["taluk"] = tk
    elif d:
        a["district"] = d
    dep = next((v for k, v in DEPT_WORDS.items() if re.search(r"\b" + k, t, re.I)), "")
    if dep:
        a["department"] = dep
    if re.search(r"\b(overdue|late|delayed|past (the )?deadline)\b", t, re.I):
        a["status"] = "overdue"
    elif re.search(r"\b(unresolved|open|pending|live|outstanding|backlog|still)\b", t, re.I):
        a["status"] = "open"
    elif re.search(r"\b(resolved|closed|solved|disposed)\b", t, re.I):
        a["status"] = "resolved"
    elif re.search(r"\brejected\b", t, re.I):
        a["status"] = "rejected"
    if re.search(r"\b(vulnerable|priority|elderly|widow|disabled)\b", t, re.I):
        a["vulnerable"] = True
        a.setdefault("status", "open")
    return a


def route_question(text: str, profile: str, state: dict | None = None):
    """(function, args) for a data question, or None. Functions: Mitra query functions, or 'inbox'."""
    t = (text or "").strip()
    if not t or profile not in ("cs", "officer") or _ACTION_RX.search(t):
        return None
    from . import board
    b = board.route(t, profile, state)                 # dashboards, levels, escalation, the 7-day clock, any department
    if b:
        return b
    low = t.lower()
    # "my cases" on the officer's desk
    if profile == "officer" and re.search(r"\b(my (cases|inbox|desk|pending|queue|work)|pending with me|on my desk|do i have|assigned to me)\b", low):
        return "inbox", {}
    # the iPGRS sample week
    if re.search(r"\bipgrs\b", low):
        args = {}
        g = re.search(r"\b(department|district|taluk|service|source|channel|status)s?\b", low)
        if g or re.search(r"\b(which|top|most|highest)\b", low):
            args["group_by"] = (g.group(1) if g else "department").replace("channel", "source")
        args.update({k: v for k, v in _filters(t).items() if k in ("district", "taluk")})
        return "ipgrs_records", args
    # comparisons, rankings, breakdowns, "where are ..."
    cmp_ = _compare_args(t)
    if cmp_:
        return cmp_
    # an officer: workload, profile
    if _OFFICER_RX.search(t) and re.search(r"\b(about|workload|doing|how many|cases|performance|profile|pending|open|load|record|status)\b", low):
        o = find_officer(t)
        if o:
            return "officer_profile", {"officer": off_name(o, False)}
    # a place: what / where is it, which taluk / district
    m = re.search(r"\b(?:what|where)\s+is\s+([a-z][\w-]+)|\btell me about\s+([a-z][\w-]+)|\bwhich (?:taluk|district)\s+(?:is\s+)?([a-z][\w-]+)|^([a-z][\w-]+)\W+which (?:taluk|district)", low)
    if m:
        w = next(x for x in m.groups() if x)
        pl = _places()
        if w in pl.get("gp", {}) or w in pl.get("taluk", {}) or w in pl.get("district", {}) or w in PLACE_ALIAS:
            return "place_info", {"place": w}
    # counts with filters
    f0 = _filters(t)
    if _COUNT_RX.search(t) and _CASEWORD_RX.search(t) or re.search(r"^\W*(open|pending|overdue) (cases|grievances|complaints)\b", low) or \
            (_CASEWORD_RX.search(t) and any(k in f0 for k in ("district", "taluk", "department")) and re.search(r"\b(cases|grievances|complaints)\b", low)):
        f = _filters(t)
        f.setdefault("status", "open" if re.search(r"\b(open|pending|unresolved|outstanding|live|still)\b", low) else "")
        return "find_cases", {k: v for k, v in f.items() if v not in ("", None)}
    return None


# ------------------------------------------------------------------ global intents
async def t_help(sess, args):
    p = sess["profile"]
    if p == "citizen":
        say = (f"Namaskara, I'm {config.NAME}. Tell me what's wrong in your village and I'll take it to the right officer. "
               "You can also ask me to track your request, or to apply for a certificate.")
    elif p == "officer":
        say = (f"Good day, {off_name(sess['officer'])}. I can read your inbox, open a case, draft the report, and file your decision. "
               "Where would you like to start?")
    else:
        say = ("Hello, Chief Secretary Madam. I'm ready. I can give you the position across the state, show what's overdue, answer questions on any case, "
               "and nudge an officer. What would you like to see?")
    return {"say": say, "ui": [{"op": "hint", "profile": p}]}


async def t_repeat(sess, args):
    return {"say": sess["state"].get("last_say") or "I have not said anything yet."}


async def t_stop(sess, args):
    t = (args.get("_text") or "").lower()
    st = sess["state"]
    if sess["profile"] == "citizen" and st.get("draft", {}).get("service") and re.search(r"cancel|never ?mind|forget|drop|don.t file", t):
        st["draft"] = {}; st["flow"] = "menu"; _set_options(sess, [])
        return {"say": "Okay, I've dropped that request. Nothing was filed.", "ui": [{"op": "stop"}, {"op": "request", "draft": {}, "flow": "menu", "options": []}]}
    if re.search(r"\b(thank|thanks|bye|good ?night|all good|that.s all|nothing)\b", t):
        return {"say": "You're welcome. I'm here whenever you need me.", "ui": [{"op": "stop"}]}
    return {"say": "", "ui": [{"op": "stop"}]}


PROBLEM_RX = re.compile(r"water|road|light|lamp|drain|sewage|garbage|waste|pension|ration|land|rtc|pahani|khata|survey|house|housing|"
                        r"toilet|school|hospital|doctor|power|electric|current|bribe|officer|certificate|wage|nrega|mgnrega|pipe|tap|bore|"
                        r"broken|not working|not received|not paid|not come|pending|delay|complain|problem|issue|help me|please|"
                        r"dog|animal|snake|monkey|tree|flood|crop|loan|bank|bus|teacher|fee|gas|lpg|cylinder|scheme|subsidy|card|aadhaar|"
                        r"document|record|birth|death|caste|income|mutation|encroach|theft|noise|pollution|smell|mosquito|fever|health|"
                        r"medicine|ambulance|police|fire|leak|block|overflow|damage|repair|dirty|smell|unsafe|danger|accident|rti|court|appl|apply|"
                        r"ನೀರು|ರಸ್ತೆ|ದೀಪ|ಚರಂಡಿ|ಕಸ|ಪಿಂಚಣಿ|ಪಡಿತರ|ಜಮೀನು|ಮನೆ|ಶೌಚ|ಶಾಲೆ|ಆಸ್ಪತ್ರೆ|ವಿದ್ಯುತ್|ಕರೆಂಟ್|ಲಂಚ|ಅಧಿಕಾರಿ|ಸಮಸ್ಯೆ|ತೊಂದರೆ|ಕೆಟ್ಟ|ಬರುತ್ತಿಲ್ಲ|ಬಂದಿಲ್ಲ", re.I)


def looks_like_problem(text: str) -> bool:
    return bool(PROBLEM_RX.search(text or ""))


def chit_chat_reply(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"name|who are you|what are you|are you (a )?(robot|human|ai)", t):
        return (f"I'm {config.NAME}, the voice of Sakala, Government of Karnataka. If something is wrong in your village, "
                "tell me and I'll take it to the right officer.")
    if re.search(r"who (made|built|created) you", t):
        return f"I was built for the Praja Seva Department to make sure every request reaches the right officer, on time."
    if re.search(r"joke|sing|song|rain|weather|plus|minus|times", t):
        return "That's not something I can help with, but if anything is wrong in your area, water, roads, lights, ration or pension, I'm all ears."
    if re.search(r"thank|bye|good ?night|all good|nothing|fine", t):
        return "You're welcome. I'm here whenever you need me."
    return "I'm listening. Tell me what's wrong, in a sentence or two, and I'll take it to the right officer."


async def t_smalltalk(sess, args):
    if sess["profile"] == "citizen" and looks_like_problem(args.get("_text") or args.get("text") or ""):
        return await t_citizen_text(sess, {"text": args.get("_text") or args.get("text")})      # a real problem is filed, not chatted
    t = (args.get("text") or args.get("_text") or "").strip()
    if sess["profile"] == "citizen":
        st = sess["state"]
        # mid-flow answers (a village, a reply to the officer) still belong to the flow; chit-chat is answered, never filed
        if t and (st.get("flow") in ("ask_place", "ask_gp", "confirm", "reply", "apply_name", "apply_village") or looks_like_problem(t)):
            return await t_citizen_text(sess, {"text": t})
    from . import knowledge
    if t and not CHIT_RX.search(t) and knowledge.match(t, last=sess["state"].get("kb_last") or "", strict=False)[0]:
        return await t_ask_knowledge(sess, {"question": t})        # a general question the notes cover
    if t and not CHIT_RX.search(t) and (t.rstrip().endswith("?") or knowledge.QWORD_RX.match(t.lower())) and not looks_like_problem(t):
        return await t_ask_knowledge(sess, {"question": t})        # a question the notes do not cover: "not in my notes", never a guess
    if sess["profile"] == "citizen":
        return {"say": chit_chat_reply(t)}
    return {"say": "I can act on Sakala cases and data, and answer questions about Sakala, iPGRS and the Praja Seva Department. Ask me for help any time."}


async def t_switch_profile(sess, args):
    p = (args.get("profile") or "").lower()
    p = {"chief secretary": "cs", "chief": "cs", "cs": "cs", "officer": "officer", "citizen": "citizen"}.get(p, p)
    if p not in config.PROFILES:
        return {"say": "I can switch to citizen, officer or Chief Secretary."}
    sess["profile"] = p
    sess["state"]["case_id"] = None
    store.save_session(sess)
    res = await t_help(sess, {})
    res["ui"] = [{"op": "profile", "profile": p, "officer": sess["officer"]}] + await _profile_ui(sess)
    return res


async def t_upload_document(sess, args):
    """The document door by voice: the request card with its drop zone is raised and lit; the person taps it (a browser never
    opens the file picker without a tap). Nothing is filed by this call."""
    st = sess["state"]
    if st.get("flow") not in (None, "", "menu", "done") and (st.get("draft") or {}).get("doc"):
        return {"say": "Your letter is already on the form. Check it and say submit, or change anything.", "ui": [{"op": "upload", "lit": True}]}
    return {"say": "Tap Upload a written complaint and choose the letter, a PDF or a photo, or take a photo of it. I will read it into the "
                   "official form and send it to the right officer.",
            "ui": _draft_ui(sess, [stage(0, "Waiting for the letter · tap Upload a written complaint", "run")]) + [{"op": "upload"}]}


async def t_go_to(sess, args):
    """Move around the screen: back to the dashboard / main screen, the last chart back, the inbox, or another profile."""
    w = ((args.get("target") or "") + " " + (args.get("_text") or "")).lower()
    w = (w.replace("ನಾಗರಿಕ", " citizen ").replace("ಸಿಟಿಜನ್", " citizen ").replace("ಅಧಿಕಾರಿ", " officer ").replace("ಆಫೀಸರ್", " officer ")
          .replace("ಮುಖ್ಯ ಕಾರ್ಯದರ್ಶಿ", " chief secretary ").replace("ಡ್ಯಾಶ್‌ಬೋರ್ಡ್", " dashboard ").replace("ಡ್ಯಾಶ್ಬೋರ್ಡ್", " dashboard ")
          .replace("ಆ್ಯಪ್", " app ").replace("ಆಪ್", " app ").replace("ಮೊಬೈಲ್", " mobile ").replace("ಫೋನ್", " phone ").replace("ವೆಬ್", " web "))
    p = sess["profile"]
    said0 = (args.get("_text") or "").lower()
    VIEW_WORDS = r"\b(web|website|desktop|browser|laptop|big screen|full screen|app|mobile|phone)\b|ವೆಬ್|ಆ್ಯಪ್|ಆಪ್|ಮೊಬೈಲ್|ಫೋನ್|ಕಂಪ್ಯೂಟರ್"
    view = "web" if re.search(r"\b(web|website|desktop|browser|laptop|big screen|full screen)\b", w) else \
        "app" if re.search(r"\b(app|mobile|phone)\b", w) and not re.search(r"\b(apply|application|whatsapp)\b", w) else ""
    if view and said0 and not re.search(VIEW_WORDS, said0):
        view = ""                                       # 'citizen view' is a profile, unless the person said web / app / phone themselves
    if view:
        to = "cs" if re.search(r"chief|secretary|\bcs\b|madam", w) else "officer" if re.search(r"\bofficer|tahsildar|\bpdo\b", w) else \
            "citizen" if re.search(r"\bcitizen", w) else p
        name = config.PROFILES[to]["title"]
        return {"say": f"Opening the {'web' if view == 'web' else 'phone app'} view of the {name} desk.",
                "ui": [{"op": "view", "view": view, "profile": to, "officer": sess["officer"]}]}
    said = (args.get("_text") or "").lower()
    if said and not re.search(r"dashboard|main screen|main view|main page|home|chart|graph|visual|picture|\bmap\b|inbox|citizen|officer|"
                              r"chief|secretary|screen|close|back|dismiss|exit|leave|go to|take me|return|view|profile|"
                              r"ವಾಪಸ್|ಹಿಂದೆ|ಹೋಗಿ|ಕರ್ಕೊಂಡು|ಕರೆದುಕೊಂಡು|ತೋರಿಸಿ|ಮುಚ್ಚಿ|ತೆರೆಯಿರಿ|ತೆಗೆ|ನಾಗರಿಕ|ಅಧಿಕಾರಿ|ಮುಖ್ಯ ಕಾರ್ಯದರ್ಶಿ|ಡ್ಯಾಶ್", said):
        if p == "citizen":
            return await t_citizen_text(sess, {"text": args.get("_text")})
        return {"say": ""}
    if re.search(r"chief|secretary|\bcs\b", w):
        return await t_switch_profile(sess, {"profile": "cs"})
    if re.search(r"\bcitizen", w):
        return await t_switch_profile(sess, {"profile": "citizen"})
    if re.search(r"\bofficer|\binbox", w) and p != "officer":
        return await t_switch_profile(sess, {"profile": "officer"})
    if re.search(r"\binbox", w):
        r = await t_inbox(sess, {})
        r["ui"] = [{"op": "nav", "target": "inbox"}] + list(r.get("ui") or [])
        return r
    if re.search(r"chart|graph|visual|picture|\bmap\b", w) and not re.search(r"close|dismiss|exit|leave|put away|minimi|back to the (dashboard|main|home)", w):
        return {"say": "Here is the last chart again.", "ui": [{"op": "nav", "target": "chart"}]}
    say = {"cs": "Back to the dashboard, Chief Secretary Madam.", "officer": "Back to your inbox.", "citizen": "Back to the main screen."}.get(p, "Done.")
    return {"say": say, "ui": [{"op": "nav", "target": "dashboard"}] + await _profile_ui(sess)}


async def _profile_ui(sess) -> list[dict]:
    """Panels to show when a profile opens."""
    p = sess["profile"]
    st = await load_state(sess)
    if p == "officer":
        rows = inbox_for(st, sess["officer"])
        sess["state"]["list"] = [r["id"] for r in rows[:12]]
        return [{"op": "inbox", "officer": sess["officer"], "officerName": off_name(sess["officer"], False), "cases": rows[:12], "total": len(rows)},
                {"op": "notes", "notes": store.notes_for("officer", sess["officer"])}]
    if p == "cs":
        k = await _kpi_ui(st)
        sess["state"]["list"] = [c["id"] for c in k["cases"][:12]]
        return [k, {"op": "notes", "notes": store.notes_for("cs")}]
    r = await intake(sess, step="mine")
    cases = r.get("cases") or []
    sess["state"]["my_cases"] = [c["id"] for c in cases]
    return [{"op": "mycases", "cases": cases}, {"op": "notes", "notes": store.notes_for("citizen", session=sess["chat_session"])}]


async def t_set_language(sess, args):
    """Switch the spoken language (by voice, in either language). A flow that is waiting for an answer is not interrupted:
    the acknowledgement is short and whatever Mitra just asked is repeated after it by the caller."""
    lang = (args.get("language") or "").lower()
    if not lang or lang in ("other", "the other", "switch"):
        lang = "en" if sess.get("lang") == "kn" else "kn"
    lang = "kn" if lang.startswith("k") or "ಕನ್ನಡ" in lang else "en"
    same = sess.get("lang") == lang
    sess["lang"] = lang
    store.save_session(sess)
    st = sess.get("state") or {}
    busy = (st.get("flow") or "") not in ("", "menu", "done") or bool(st.get("pending_action"))
    if same:
        say = "ಈಗಾಗಲೇ ಕನ್ನಡದಲ್ಲೇ ಮಾತಾಡ್ತಿದ್ದೀನಿ. ಹೇಳಿ." if lang == "kn" else "We are already in English. Go ahead."
    elif lang == "kn":
        say = "ಸರಿ, ಇನ್ಮೇಲೆ ಕನ್ನಡದಲ್ಲೇ ಮಾತಾಡ್ತೀನಿ." + ("" if busy else " ಹೇಳಿ, ಏನು ಮಾಡ್ಬೇಕು?")
    else:
        say = "Okay, English from here." + ("" if busy else " What would you like to do?")
    return {"say": say, "ui": [{"op": "lang", "lang": lang}]}


async def t_set_theme(sess, args):
    w = ((args.get("theme") or "") + " " + (args.get("_text") or "")).lower()
    t = "dark" if re.search(r"dark|night|darker|lights off", w) else "light"
    return {"say": f"Switching to {t} mode.", "ui": [{"op": "theme", "theme": t}]}


async def t_tick(sess, args):
    days = max(1, min(30, int(args.get("days") or 1)))
    r = await sakala.tick(days)
    when = datetime.fromisoformat(r["now"]).strftime("%d %B %Y")
    say = f"Moved the clock {days} day{'s' if days > 1 else ''} to {when}. {r['escalated']} grievance{'s' if r['escalated'] != 1 else ''} auto-escalated"
    say += f", {r['breached']} Sakala deadline{'s' if r['breached'] != 1 else ''} missed." if r.get("breached") else "."
    ui = [{"op": "clock", "now": r["now"]}] + await _profile_ui(sess)
    return {"say": say, "ui": ui}


async def t_reset(sess, args):
    r = await sakala.reset()
    sess["state"] = {}
    return {"say": "Demo reset to go-live, 14 October 2026.", "ui": [{"op": "clock", "now": r["now"]}, {"op": "reload"}]}


# ------------------------------------------------------------------ citizen: Mitra is the input channel
# The voice agent drives the Sakala pipeline directly through /api/intake (no WhatsApp engine involved).
STAGE_NOTES = {
    0: "Spoken request received by Mitra",
}


async def intake(sess: dict, **payload) -> dict:
    return await sakala._post("/api/intake", {"session": sess["chat_session"], "channel": "mitra", "lang": sess["lang"], **payload})


def stage(i: int, note: str, state: str = "done") -> dict:
    return {"i": i, "state": state, "note": note}


def dept_name(code: str) -> str:
    return {"REV": "Revenue", "RDPR": "Rural Development and Panchayat Raj", "FOOD": "Food and Civil Supplies"}.get(code or "", code or "")


def _draft_ui(sess: dict, stages: list[dict], extra: dict | None = None) -> list[dict]:
    d = sess["state"].get("draft") or {}
    card = {"op": "request", "draft": {k: d.get(k) for k in ("text", "masked", "service", "dept", "grievance", "conf", "vulnerable", "place", "preview", "duplicate", "engine", "why", "doc")},
            "flow": sess["state"].get("flow"), "options": sess["state"].get("options") or []}
    if extra:
        card.update(extra)
    return [{"op": "stages", "items": stages}, card]


def _set_options(sess: dict, opts: list[list[str]]):
    sess["state"]["options"] = opts[:12]


async def _after_understand(sess: dict, r: dict, via: str) -> dict:
    t0 = r.get("text") or ""
    if (r.get("u") or {}).get("intent") != "SERVICE_REQUEST" and len(t0.split()) <= 6 and not looks_like_problem(t0):
        sess["state"]["flow"] = "menu"; sess["state"]["draft"] = {}
        return {"say": chit_chat_reply(t0), "ui": [{"op": "stages", "items": []}]}      # "I love Karnataka": nothing to file
    """Common handling once the pipeline has read the request (text or photo)."""
    u = r["u"]
    st = sess["state"]
    stages = [stage(0, "Photo of the petition read by Mitra" if via == "photo" else
                    (f"Written complaint read · {r.get('pages', 1)} page(s) · {r.get('filename') or 'document'}" if via == "document" else "Spoken request received by Mitra")),
              stage(1, f"{r['masked_items']} personal number(s) masked before AI" if r.get("masked_items") else "Nothing personal to mask")]
    say = ""
    if r.get("gsc"):
        g = r["gsc"]
        say += (f"You quoted Sakala application {g['gsc']}. " + ("It is in the pilot records. " if g.get("found") else "It is not in the pilot records, so the officer will look it up. ")
                + (g.get("advice") or "") + " ")
    intent = u.get("intent")
    if intent == "WRONG_DOOR":
        stages.append(stage(2, "Not a grievance", "warn"))
        st["flow"] = "menu"; st["draft"] = {}
        return {"say": say + (u.get("reason") or "This is not something iPGRS handles as a grievance."), "ui": _draft_ui(sess, stages)}
    if intent == "OUT_OF_SCOPE":
        stages.append(stage(2, f"{u.get('dept')} · outside the pilot", "warn"))
        st["flow"] = "menu"; st["draft"] = {}
        return {"say": say + f"I understood this as a matter for the {u.get('dept') or 'another department'}. That department is outside the three pilot departments, so in production it goes straight to that department's field officer.",
                "ui": _draft_ui(sess, stages)}
    if intent == "SERVICE_REQUEST" and r.get("service"):
        svc = r["service"]
        stages.append(stage(2, f"Service request · {svc['name']} (Sakala-notified)"))
        st["flow"] = "apply_confirm"; st["apply"] = {"key": svc["key"], "name": "", "checklist": svc.get("checklist") or []}
        st["draft"] = {"text": r["text"], "service": svc["name"], "dept": "Sakala service"}
        _set_options(sess, [["Apply now", "confirm"], ["Not now", "change"]])
        return {"say": say + f"This is an application for a {svc['name']}, a Sakala service with a legal deadline of {svc['days']} days. Shall I start the application?",
                "ui": _draft_ui(sess, stages)}
    if intent == "UNCLEAR":
        text0 = r.get("text") or ""
        if not looks_like_problem(text0) and len(text0.split()) <= 10:
            # "tell me a joke", "who made you", "asdf": nothing to file
            st["flow"] = "menu"; st["draft"] = {}
            return {"say": chit_chat_reply(text0), "ui": [{"op": "stages", "items": []}]}
        stages.append(stage(2, "Unclear · no category matches well", "warn"))
        st["flow"] = "scrutiny_confirm"; st["draft"] = {"text": text0, "u": u, "scrutiny": True, "service": "To be decided by the scrutiny desk"}
        _set_options(sess, [["Yes, send it", "confirm"], ["No", "change"]])
        return {"say": say + "I'm not sure which office handles this. Shall I send it to a person at the scrutiny desk, who will route it to the right officer?",
                "ui": _draft_ui(sess, stages)}
    # a grievance
    conf = round(float(u.get("conf") or 0) * 100)
    stages.append(stage(2, f"{dept_name(u.get('dept_code'))} › {u.get('service')} · {conf}% · {r.get('engine')}"))
    st["draft"] = {"text": r["text"], "masked": r.get("masked"), "u": u, "service": u.get("service"), "dept": dept_name(u.get("dept_code")),
                   "grievance": u.get("grievance"), "conf": conf, "vulnerable": bool(u.get("vulnerable")), "engine": r.get("engine"), "why": u.get("why")}
    say += f"I understand this as {u.get('service')}, under {dept_name(u.get('dept_code'))}, {conf} percent sure."
    if u.get("vulnerable"):
        say += " I have marked it priority for a vulnerable citizen."
    return await _apply_place(sess, r, stages, say)


async def _apply_place(sess: dict, r: dict, stages: list[dict], say: str) -> dict:
    st = sess["state"]; d = st["draft"]
    if r.get("place"):
        p = r["place"]; d["place"] = p; d["preview"] = r.get("preview"); d["duplicate"] = r.get("duplicate")
        where = (f"{p['village']} village, " if p.get("village") and p["village"] != p.get("gp") else "") + (f"{p['gp']} Gram Panchayat, " if p.get("gp") else "") + f"{p['taluk']} taluk"
        stages.append(stage(3, f"Location: {where} · {p.get('how', '')}"))
        stages.append(stage(4, "Waiting for you to confirm", "run"))
        st["flow"] = "confirm"
        _set_options(sess, [["Submit", "confirm"], ["Change", "change"]] if d.get("doc") else [["Yes, file it", "confirm"], ["Change", "change"]])
        pv = r.get("preview") or {}
        who = (pv.get("officer") or {}).get("name")
        say += f" The location is {where}."
        if r.get("duplicate"):
            say += f" A similar open request exists, {r['duplicate']}; yours will be linked to it."
        if who:
            say += f" It will go to {who}. Shall I file it?"
        else:
            say += " Shall I file it?"
        return {"say": say, "ui": _draft_ui(sess, stages)}
    if r.get("need") == "gp":
        tk = r["taluk"]; d["taluk_hint"] = tk
        opts = [[g, f"gp:{g}|{tk}"] for g in (r.get("gp_options") or [])]
        _set_options(sess, opts)
        st["flow"] = "ask_gp"
        stages.append(stage(3, f"Taluk found: {tk} · asking for the Gram Panchayat", "run"))
        eg = ", ".join(g for g, _ in opts[:3])
        return {"say": say + f" I can see this is in {tk} taluk. Each Gram Panchayat has its own officer, so which Gram Panchayat is it? For example {eg}.",
                "ui": _draft_ui(sess, stages)}
    opts = [["Share my location", "loc:share"]] + [[t, f"taluk:{t}"] for t in (r.get("taluks") or [])]
    _set_options(sess, opts)
    st["flow"] = "ask_place"
    stages.append(stage(3, "Asking for the village or taluk", "run"))
    return {"say": say + " Which village or taluk is this in? You can also ask me to use your location.", "ui": _draft_ui(sess, stages)}


CHIT_RX = re.compile(r"^\W*(hi|hello|hey|hai|namaskara|good (morning|afternoon|evening|night)|thanks?|thank you|bye|ok(ay)?|hmm+|yes|no|"
                     r"what('s| is) your name|who (are|made|built|created) you|what are you|are you (a )?(robot|human|bot|ai|real)|how are you|"
                     r"tell me a joke|sing( a song)?|testing|test|just (testing|checking)|check(ing)?|what is \d+|what's \d+|\d+ ?[+x*-] ?\d+)\b", re.I)


LOC_RX = re.compile(r"\b(use|share|take|get|go ahead with|send)?\s*(my|the|our)?\s*(current\s+)?(location|gps|where i am|where i'm)\b|\bmy location\b", re.I)


async def t_citizen_text(sess, args):
    text = (args.get("text") or "").strip()
    st = sess["state"]
    if st.get("flow") in ("ask_place", "ask_gp", "apply_village") and LOC_RX.search(text) and (st.get("draft") or {}).get("u"):
        return await _run_option(sess, "loc:share")        # "you can go ahead and use my location": the location, whatever the model called it
    if text and st.get("flow") in (None, "", "menu", "done") and CHIT_RX.search(text) and not looks_like_problem(text):
        return {"say": chit_chat_reply(text)}          # greetings, questions about Mitra, tests, jokes: answered, never filed
    if not text:
        return {"say": "Tell me what is wrong."}
    flow = st.get("flow") or "menu"
    if flow == "reply" and st.get("reply_case") and st.get("my_cases") is not None and st["reply_case"] not in st["my_cases"]:
        st["flow"] = "menu"; st["reply_case"] = None; flow = "menu"          # a stale reply (not this citizen's request)
    if flow == "reply" and st.get("reply_case"):
        return await t_reply(sess, {"text": text})
    if flow == "apply_name":
        st["apply"]["name"] = text.strip(" .")
        st["flow"] = "apply_village"
        return {"say": f"Thank you. Which village is {st['apply']['name']} from?", "ui": _draft_ui(sess, [stage(3, "Checklist: applicant's name ✓ · village …", "run")])}
    if flow == "apply_village":
        r = await intake(sess, step="place", text=text, u={"service_id": 0})
        if not r.get("place"):
            if r.get("need") == "gp":
                opts = [[g, f"gp:{g}|{r['taluk']}"] for g in (r.get("gp_options") or [])]
                _set_options(sess, opts); st["apply"]["taluk"] = r["taluk"]
                return {"say": f"Which Gram Panchayat in {r['taluk']}? For example {', '.join(g for g, _ in opts[:3])}.", "ui": _draft_ui(sess, [stage(3, f"Taluk {r['taluk']} · asking for the Gram Panchayat", "run")])}
            return {"say": "I could not find that village in the pilot area. Please say the Gram Panchayat or the taluk."}
        return await _create_application(sess, r["place"])
    if flow == "confirm" and (st.get("draft") or {}).get("doc"):
        changed = _doc_edits(sess, text)
        if changed:
            return {"say": f"Updated the {changed}. Say submit when the form is right.", "ui": _draft_ui(sess, [stage(4, "Form updated · waiting for submit", "run")])}
        if re.search(r"\b(village|gram panchayat|panchayat|taluk|place|location) (is|in)\b|\bit('s| is) in\b", text.lower()):
            r = await intake(sess, step="place", text=re.sub(r"^.*?\b(?:is|in)\s+", "", text, count=1, flags=re.I), u=d["u"] if (d := st.get("draft")) and d.get("u") else {})
            if r.get("place") or r.get("need") == "gp":
                return await _apply_place(sess, r, [stage(3, "Location changed on the form", "run")], "Location updated.")
    if flow in ("ask_place", "ask_gp", "confirm"):
        # an option label said aloud
        for lab, action in st.get("options") or []:
            if lab and (lab.lower() in text.lower() or text.lower() in lab.lower()) and len(lab) > 2:
                return await t_citizen_option(sess, {"option": lab})
        d = st.get("draft") or {}
        short = len(text.split()) <= 4
        if d.get("u") and (flow != "confirm" or short):
            # a place name (or a correction of the place) while the request is still being completed
            r = await intake(sess, step="place", text=text, u=d["u"], taluk=d.get("taluk_hint", ""))
            if r.get("place") or (flow != "confirm" and r.get("need")):
                stages = [stage(2, f"{d.get('dept')} › {d.get('service')} · {d.get('conf')}%")]
                # a taluk named on its own is understood (Mitra then asks for the Gram Panchayat): no "could not find"
                return await _apply_place(sess, r, stages, "" if r.get("place") or r.get("taluk") else "I could not find that place.")
            if flow == "confirm":
                return {"say": "Shall I file it? Say yes to confirm, or tell me what to change, such as a different village."}
            if flow != "confirm":
                stages = [stage(2, f"{d.get('dept')} › {d.get('service')} · {d.get('conf')}%")]
                return await _apply_place(sess, r, stages, "I could not find that place.")
    # anything else is a new request
    r = await intake(sess, step="understand", text=text, defer_scrutiny=True)
    if not r.get("ok"):
        return {"say": "Tell me what is wrong, in a sentence or two."}
    return await _after_understand(sess, r, "voice")


async def t_citizen_photo(sess, image_b64: str, media_type: str = "image/png") -> dict:
    r = await intake(sess, step="understand", image_b64=image_b64, media_type=media_type, defer_scrutiny=True)
    if not r.get("ok"):
        return {"say": "I received the photo, but it does not look like a readable petition or document, so I will not guess. Please tell me the problem in a sentence.",
                "ui": [{"op": "stages", "items": [stage(0, "Photo received", "warn")]}]}
    st = sess["state"]
    if (st.get("flow") or "") in ("apply_village", "apply_confirm", "apply_name"):
        return {"say": "Document photo received and attached to the application.", "ui": [{"op": "toast", "h": "Document", "m": "attached"}]}
    res = await _after_understand(sess, r, "photo")
    res["say"] = f"I read your petition: {clean_for_speech(r.get('masked') or guard.mask(r.get('text') or ''))[:160]}. " + res["say"]
    return res


async def t_citizen_document(sess, file_b64: str, media_type: str = "application/pdf", filename: str = "") -> dict:
    """A written complaint uploaded as a file: read into the official form by the POC, then the same path as a spoken request."""
    st = sess["state"]
    r = await intake(sess, step="document", file_b64=file_b64, media_type=media_type, filename=filename, defer_scrutiny=True)
    if not r.get("ok"):
        why = {"unreadable": "I could not read a complaint in that file, so I will not guess.", "too_big": "That file is larger than 30 MB.",
               "no_reader": "The document reader is not reachable right now.", "empty": "That file is empty."}.get(r.get("reason"), "I could not read that file.")
        return {"say": why + " You can tell me the problem in a sentence instead.", "ui": [{"op": "stages", "items": [stage(0, "Document received · not readable", "warn")]}]}
    doc = {"filename": r.get("filename") or filename, "pages": r.get("pages"), "reader": r.get("reader"), "thumbs": r.get("thumbs") or [],
           "fields": r.get("fields") or {}, "confidence": r.get("confidence") or {}, "flags": r.get("flags") or [], "evidence": r.get("evidence") or {},
           "missing": r.get("missing") or [], "english": r.get("english") or "", "transcript": (r.get("transcript") or "")[:4000],
           "form": r.get("form"), "several": bool(r.get("several")), "ms": r.get("ms"), "record": r.get("record"),
           "rotation": r.get("rotation") or 0, "language": r.get("language") or ""}
    res = await _after_understand(sess, r, "document")
    u = r.get("u") or {}
    if u.get("intent") in ("OUT_OF_SCOPE", "UNCLEAR"):
        # a letter is never dropped: the form stays, Submit sends it with the letter to the scrutiny desk (a person routes it)
        st["flow"] = "scrutiny_confirm"
        st["draft"] = {"text": r.get("text") or "", "masked": r.get("masked"), "u": u, "scrutiny": True, "engine": r.get("engine"), "why": u.get("reason"),
                       "service": "To be decided by the scrutiny desk", "dept": (u.get("dept") + " · outside the pilot") if u.get("intent") == "OUT_OF_SCOPE" and u.get("dept") else "Unclear category",
                       "taluk_hint": (doc["fields"].get("taluk") or "")}
        _set_options(sess, [["Submit", "confirm"], ["Change", "change"]])
    if st.get("draft") is not None:
        st["draft"]["doc"] = doc
        if st.get("flow") == "confirm":
            _set_options(sess, [["Submit", "confirm"], ["Change", "change"]])
    f = doc["fields"]
    lead = f"I read the letter, {doc['pages']} page{'s' if (doc['pages'] or 1) != 1 else ''}"
    if f.get("name"):
        lead += f", from {f['name']}"
    if f.get("letter_date"):
        lead += f", dated {f['letter_date']}"
    lead += ". "
    if doc.get("record"):
        rec = doc["record"]
        lead += f"It quotes iPGRS grievance {rec.get('gid')}, which is in the records: {rec.get('service')}, {rec.get('taluk')} taluk. "
    gaps = [{"phone": "a phone number", "name": "the complainant's name", "address": "the exact place"}.get(k, k) for k in doc["missing"] if k in ("phone", "name", "address")]
    tail = ""
    if gaps and st.get("flow") == "confirm":
        tail = f" The letter does not give {' or '.join(gaps)}; add it on the form if you have it, or just say submit."
    elif st.get("flow") == "confirm":
        tail = " Check the form and say submit, or change anything."
    elif st.get("flow") == "scrutiny_confirm":
        body = (f"This is a matter for the {u.get('dept')}, outside the three pilot departments. " if u.get("intent") == "OUT_OF_SCOPE" and u.get("dept")
                else "No official category matches it with certainty. ")
        res["say"] = body + "Check the form and say submit: it goes with the letter to the scrutiny desk, where a person routes it to the right officer."
    res["say"] = lead + (res.get("say") or "").replace("Shall I file it?", "").strip() + tail
    res["ui"] = _draft_ui(sess, [s for s in (res.get("ui") or [{}])[0].get("items", [])] if (res.get("ui") or [{}])[0].get("op") == "stages" else []) if st.get("draft") else res.get("ui", [])
    return res


NA_RX = re.compile(r"^\s*(na|n/?a|nil|none|not available|not provided|-+|skip|no)\s*$", re.I)


def _doc_edits(sess: dict, text: str) -> str:
    """Voice edits to the open document form: 'the phone number is 98…', 'my name is …'. Returns what was changed ('' = nothing)."""
    d = (sess["state"].get("draft") or {}); doc = d.get("doc")
    if not doc:
        return ""
    f = doc.setdefault("fields", {})
    low = text.lower()
    m = re.search(r"(\+?91[\s-]?)?([6-9]\d{9})\b", re.sub(r"[\s-]", "", text))
    if m and re.search(r"phone|mobile|number|contact|call", low):
        f["phone"] = m.group(2); return "phone number"
    m = re.search(r"\b(?:my name is|the name is|name is|complainant is|i am|i'm)\s+([A-Z][\w.]+(?:\s+[A-Z][\w.]+){0,3})", text)
    if m:
        f["name"] = m.group(1).strip(" ."); return "name"
    if re.search(r"\b(no phone|no number|phone (is )?not (there|given|available)|skip the phone)\b", low):
        f["phone"] = ""; return "phone (not provided)"
    return ""


async def t_citizen_option(sess, args):
    want = (args.get("option") or "").lower().strip()
    st = sess["state"]
    best, score = None, 0.0
    for lab, action in st.get("options") or []:
        s = difflib.SequenceMatcher(None, want, lab.lower()).ratio()
        if want and (want in lab.lower() or lab.lower() in want):
            s = max(s, 0.9)
        if s > score:
            best, score = action, s
    if "location" in want:
        best = "loc:share"
    if not best or score < 0.5 and best != "loc:share":
        # the brain called it an option but nothing on screen matches: in a flow that takes free speech
        # (a village, a taluk, a confirmation, a reply) the words themselves are the answer
        spoken = (args.get("_text") or args.get("option") or "").strip()
        if spoken and st.get("flow") in ("ask_place", "ask_gp", "confirm", "reply", "apply_name", "apply_village", "apply_confirm"):
            return await t_citizen_text(sess, {"text": spoken})
        return {"say": "I did not catch which option. " + ("Say the village, the taluk, or 'share my location'." if st.get("flow") in ("ask_place", "ask_gp") else "")}
    return await _run_option(sess, best)


async def _run_option(sess, action: str) -> dict:
    st = sess["state"]; d = st.get("draft") or {}
    if action == "confirm":
        return await t_confirm(sess, {})
    if action == "change":
        return await t_change(sess, {})
    if action == "track":
        return await t_track(sess, {})
    if action.startswith("apply:"):
        key = action[6:]
        svc = {"caste_income": ("Caste & Income Certificate", 21, ["Applicant's name", "Village", "Photo of ration card / Aadhaar"]),
               "pension": ("Old-age pension (Sandhya Suraksha)", 45, ["Applicant's name", "Village", "Photo of age proof / Aadhaar"]),
               "ration_new": ("New Ration Card", 30, ["Head of family's name", "Village", "Photo of Aadhaar of the head of family"])}.get(key)
        if not svc:
            return {"say": "I do not know that service."}
        st["flow"] = "apply_confirm"; st["apply"] = {"key": key, "name": "", "checklist": svc[2]}
        st["draft"] = {"text": "", "service": svc[0], "dept": "Sakala service"}
        _set_options(sess, [["Apply now", "confirm"], ["Not now", "change"]])
        return {"say": f"This is an application for a {svc[0]}, a Sakala service with a legal deadline of {svc[1]} days. I will need {', '.join(c.lower() for c in svc[2])}. Shall I start?",
                "ui": _draft_ui(sess, [stage(0, "Spoken request received by Mitra"), stage(2, f"Service request · {svc[0]} (Sakala-notified)")])}
    if st.get("flow") in ("apply_village",) and action.startswith("gp:"):
        gp, tk = action[3:].split("|", 1)
        return await _create_application(sess, {"village": gp, "gp": gp, "taluk": tk, "how": "picked from the list"})
    if not d.get("u"):
        return {"say": "Tell me the problem first."}
    stages = [stage(2, f"{d.get('dept')} › {d.get('service')} · {d.get('conf')}%")]
    if action == "loc:share":
        r = await intake(sess, step="place", text="Gorahalli", u=d["u"])
        if r.get("place"):
            r["place"]["how"] = "GPS location shared"
        return await _apply_place(sess, r, stages, "Location received.")
    if action.startswith("taluk:"):
        r = await intake(sess, step="place", text="", u=d["u"], taluk=action[6:])
        return await _apply_place(sess, r, stages, "")
    if action.startswith("gp:"):
        gp, tk = action[3:].split("|", 1)
        r = await intake(sess, step="place", u=d["u"], taluk=tk, gp=gp, village=gp, how="picked from the list")
        return await _apply_place(sess, r, stages, "")
    return {"say": "I did not understand that option."}


async def t_confirm(sess, args):
    st = sess["state"]; d = st.get("draft") or {}
    flow = st.get("flow")
    if flow == "apply_confirm":
        st["flow"] = "apply_name"
        first = ((st.get("apply") or {}).get("checklist") or ["Applicant's name"])[0]
        return {"say": f"To apply I need a few details. First, what is the {first.lower()}?", "ui": _draft_ui(sess, [stage(3, f"Checklist: {first} …", "run")])}
    if flow == "scrutiny_confirm" and d.get("scrutiny"):
        doc = None
        if d.get("doc"):
            dd = d["doc"]
            doc = {**(dd.get("fields") or {}), "filename": dd.get("filename"), "pages": dd.get("pages"), "reader": dd.get("reader"),
                   "evidence": dd.get("evidence"), "flags": dd.get("flags"), "english": dd.get("english"), "confidence": dd.get("confidence"),
                   "transcript": (dd.get("transcript") or "")[:4000], "record": (dd.get("record") or {}).get("gid")}
        r = await intake(sess, step="scrutiny", text=d["text"], u=d.get("u") or {}, doc=doc, taluk=d.get("taluk_hint") or "", channel="document" if doc else "mitra")
        cid = r.get("case_id") or ""
        st["flow"] = "done"; st["draft"] = {}; _set_options(sess, [["Track my request", "track"], ["Raise another", "change"]])
        if cid:
            st.setdefault("my_cases", []).append(cid)
        return {"say": f"Sent to the scrutiny desk. Your reference is {cid}. A person will route it to the right officer, and you will hear from us here.",
                "ui": [{"op": "stages", "items": [{"i": i, "state": "done"} for i in range(5)] + [{"i": 5, "state": "done", "note": "Scrutiny desk · a person routes it"}]}]}
    if flow != "confirm" or not d.get("place") or not d.get("u"):
        return {"say": "There is nothing waiting for your confirmation. Tell me the problem first."}
    p = d["place"]
    stages = [stage(4, "Confirmed by you · location valid" + (f" · linked to {d['duplicate']}" if d.get("duplicate") else "")), stage(5, "Finding the exact officer…", "run")]
    doc = None
    if d.get("doc"):
        dd = d["doc"]
        doc = {**(dd.get("fields") or {}), "filename": dd.get("filename"), "pages": dd.get("pages"), "reader": dd.get("reader"),
               "evidence": dd.get("evidence"), "flags": dd.get("flags"), "english": dd.get("english"), "confidence": dd.get("confidence"),
               "transcript": (dd.get("transcript") or "")[:4000], "record": (dd.get("record") or {}).get("gid")}
    r = await intake(sess, step="create", text=d["text"], u=d["u"], taluk=p["taluk"], gp=p.get("gp") or "", village=p.get("village") or "",
                     how=p.get("how") or ("document" if doc else "voice"), doc=doc, channel="document" if doc else "mitra")
    st["flow"] = "done"; st["draft"] = {}; _set_options(sess, [["Track my request", "track"], ["Raise another", "change"]])
    if r.get("scrutiny"):
        st.setdefault("my_cases", []).append(r["scrutiny"])
        stages.append(stage(5, "Guardrail: category not in the official master → scrutiny desk", "warn"))
        return {"say": f"I could not match this to an official category with certainty, so a person at the scrutiny desk will route it. Your reference is {r['scrutiny']}.",
                "ui": _draft_ui(sess, stages)}
    st.setdefault("my_cases", []).append(r["id"])
    o = r["officer"]
    stages += [stage(5, o["short"] + (" (fallback)" if r.get("fallback") else "")), stage(6, f"{r['days']} days · then {r['next']}"), stage(7, "Live on the officer's and the Chief Secretary's screens now")]
    where = f"{p['gp']} Gram Panchayat" if o["id"].startswith("pdo_") else f"{p['taluk']} taluk"
    say = (f"Registered. Your reference is {r['id']}. It is assigned to {o['name']}, the officer responsible for {where}. "
           f"Action is due in {r['days']} days; if nothing happens it moves automatically to {r['next']}. I will tell you every update here.")
    ui = _draft_ui(sess, stages) + [{"op": "routed", "caseId": r["id"], "officer": o, "chain": r["chain"], "basis": r["basis"], "title": "Routed to"},
                                    {"op": "toast", "h": "Routed", "m": f"{r['id']} → {o['short']}"}]
    ui += await _profile_ui(sess)
    return {"say": say, "ui": ui}


async def _create_application(sess, place: dict) -> dict:
    st = sess["state"]; a = st.get("apply") or {}
    r = await intake(sess, step="apply", key=a.get("key", ""), name=a.get("name") or "Applicant", taluk=place["taluk"], gp=place.get("gp") or "", village=place.get("village") or "")
    st["flow"] = "done"; st["draft"] = {}; st["apply"] = {}
    if not r.get("ok"):
        return {"say": "I could not register that application."}
    st.setdefault("my_cases", []).append(r["id"])
    due = datetime.fromisoformat(r["due"]) + timedelta(days=int(r["days"]))
    o = r["officer"]
    stages = [stage(3, "All details complete"), stage(4, "Validated · no duplicate application"), stage(5, f"Designated Officer: {o['short']}"),
              stage(6, f"Legal deadline {due:%d %b %Y} ({r['days']} days)"), stage(7, "On the officer's Sakala list now")]
    say = (f"Application accepted. Your Sakala number is {r['id']} for {r['service']}. It is guaranteed by {due:%d %B %Y}, {r['days']} days under the Sakala Act. "
           f"The Designated Officer is {o['name']}. If it is late you can appeal and claim 20 rupees a day, up to 500.")
    ui = _draft_ui(sess, stages) + [{"op": "routed", "caseId": r["id"], "officer": o, "chain": r["chain"], "basis": f"Sakala application {r['id']}", "title": "Sakala application"}]
    ui += await _profile_ui(sess)
    return {"say": say, "ui": ui}


async def t_change(sess, args):
    st = sess["state"]; st["flow"] = "menu"; st["draft"] = {}; st["apply"] = {}; _set_options(sess, [])
    return {"say": "Okay, tell me again what is wrong.", "ui": [{"op": "stages", "items": []}, {"op": "request", "draft": {}, "flow": "menu", "options": []}]}


async def t_track(sess, args):
    r = await intake(sess, step="mine")
    cases = r.get("cases") or []
    sess["state"]["my_cases"] = [c["id"] for c in cases]
    if not cases:
        return {"say": "You have no requests yet. Tell me what is wrong and I will file it.", "ui": [{"op": "mycases", "cases": []}]}
    def line(c):
        s = c["status"]
        if s == "Resolved":
            tail = "resolved"
        elif s == "Rejected":
            tail = "rejected, you can appeal"
        elif s == "Info requested":
            tail = "the officer asked you a question"
        elif c["left"] < 0:
            tail = f"{-c['left']} days overdue, escalated"
        else:
            tail = f"{c['left']} days left"
        return f"{c['id']}, {c['service']}, with {c['ownerShort']}, {tail}"
    say = f"You have {len(cases)} request{'s' if len(cases) != 1 else ''}. " + ". ".join(line(c) for c in cases[:4]) + "."
    upd = await t_updates(sess, {})
    if upd.get("say"):
        say += " " + upd["say"]
    ui = [{"op": "mycases", "cases": cases}] + upd.get("ui", [])
    pend = [c for c in cases if c.get("feedback_pending")]
    if pend and not any(o.get("op") == "resolution" for o in ui):      # resolved earlier, verdict still open: ask again
        c = pend[0]
        sess["state"]["awaiting_feedback"] = c["id"]
        _set_options(sess, [["Yes, solved", "fb:yes"], ["No, not solved", "fb:no"]])
        say += (f" {c['ownerShort']} marked {c['id']} as resolved" + (f": {clean_for_speech(c['atr']).rstrip(' .')}" if c.get("atr") else "")
                + ". Was your problem actually solved? Say yes or no.")
        ui.append({"op": "resolution", "case_id": c["id"], "officer": c["ownerShort"], "officerFull": c["ownerShort"], "atr": c.get("atr") or "", "service": c.get("service") or ""})
    return {"say": say, "ui": ui}


def spoken_update(m: dict) -> str:
    k, off, cid, text = m["kind"], m["officer"], m["case_id"], clean_for_speech(m.get("text") or "")
    if k == "accepted":
        return f"{off} has accepted your request {cid} and started working on it."
    if k == "info":
        return f"{off} needs more information on {cid}: {text}. Say your reply and I will send it."
    if k == "resolved":
        return f"{off} has marked {cid} as resolved. Action taken: {text.rstrip(' .')}. Was your problem actually solved? Say yes or no."
    if k == "rejected":
        return f"{off} could not accept {cid}. Reason: {text}. You may appeal to {m.get('up')} within 30 days; say 'appeal' and I will send it up."
    if k == "returned":
        return f"{cid} is being re-checked by the scrutiny desk to find the right office."
    if k == "escalated":
        return f"{cid} was not acted on in time, so it has moved up to {off} automatically."
    if k == "routed":
        return f"{cid} has been checked by the scrutiny desk and is now with {off}."
    if k == "compensation":
        return f"Sakala compensation of {text} rupees has been ordered for the delay on {cid}."
    return f"{off}: {text}"


async def t_updates(sess, args):
    """Officer -> citizen messages not yet heard; spoken and shown as update cards."""
    r = await intake(sess, step="messages")
    msgs = r.get("messages") or []
    if not msgs:
        # asked out loud ("any update?"): answer; polled in the background: stay quiet
        return {"say": "No new message from the officer yet. I'll tell you the moment there is one." if args.get("_text") else "", "ui": []}
    st = sess["state"]
    for m in msgs:
        if m["kind"] == "info":
            st["flow"] = "reply"; st["reply_case"] = m["case_id"]
            _set_options(sess, [["Reply now", "reply"], ["Later", "later"]])
        elif m["kind"] == "resolved":
            st["awaiting_feedback"] = m["case_id"]
            _set_options(sess, [["Yes, solved", "fb:yes"], ["No, not solved", "fb:no"]])
        elif m["kind"] == "rejected":
            _set_options(sess, [["Appeal", "appeal"], ["Okay", "later"]])
    say = " ".join(spoken_update(m) for m in msgs)
    ui = [{"op": "updates", "messages": msgs}]
    for m in msgs:
        if m["kind"] == "resolved":                                  # the officer's report, with the citizen's two choices
            ui.append({"op": "resolution", "case_id": m["case_id"], "officer": m["officer"], "officerFull": m.get("officerFull") or m["officer"],
                       "atr": m.get("text") or "", "service": m.get("service") or ""})
    return {"say": say, "ui": ui}


async def t_reply(sess, args):
    st = sess["state"]
    text = (args.get("text") or "").strip()
    mine = st.get("my_cases") or []
    if st.get("reply_case") and st.get("my_cases") is not None and st["reply_case"] not in mine:
        st["flow"] = "menu"; st["reply_case"] = None                    # a stale reply target (not this citizen's request)
        if text and looks_like_problem(text):
            return await t_citizen_text(sess, {"text": text})
    cid = st.get("reply_case") or (mine[-1] if mine else None)         # the citizen's own requests only
    if not cid:
        return {"say": "Which request is this about? Ask me to track your requests first and I will list them."}
    if not text or text.lower() in ("reply", "reply now"):
        st["flow"] = "reply"; st["reply_case"] = cid
        return {"say": f"Go ahead, what should I tell the officer about {cid}?"}
    r = await intake(sess, step="reply", case_id=cid, text=text)
    if not r.get("ok"):
        st["flow"] = "menu"; st["reply_case"] = None; _set_options(sess, [])
        if looks_like_problem(text):
            return await t_citizen_text(sess, {"text": text})            # flow is back to menu: filed as a new request
        return {"say": "I could not send that to the officer, so I have cleared it. Tell me what is wrong and I will file it."}
    st["flow"] = "menu"; st["reply_case"] = None; _set_options(sess, [])
    return {"say": f"Sent to {r['officer']} and added to the file of {cid}.", "ui": [{"op": "toast", "h": "Reply delivered", "m": f"{cid} → {r['officer']}"}] + await _profile_ui(sess)}


async def t_feedback(sess, args, yes: bool):
    st = sess["state"]
    cid = st.get("awaiting_feedback") or (st.get("my_cases") or [None])[-1]
    if not cid:
        return {"say": "I have no resolved request from you to record feedback on."}
    r = await intake(sess, step="feedback", case_id=cid, answer="yes" if yes else "no")
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
    return {"say": say, "ui": ui + await _profile_ui(sess)}


async def t_feedback_yes(sess, args):
    return await t_feedback(sess, args, True)


async def t_feedback_no(sess, args):
    return await t_feedback(sess, args, False)


async def t_appeal(sess, args):
    r = await intake(sess, step="appeal")
    if not r.get("ok"):
        if r.get("reason") == "top_level":
            return {"say": "That request is already at the highest level; the appeal has been noted for the Chief Secretary's review."}
        return {"say": "You have no rejected request to appeal."}
    return {"say": f"Your appeal on {r['id']} has been sent to {r['to']}. They must look at it afresh; I will tell you what they decide.", "ui": await _profile_ui(sess)}


async def t_apply(sess, args):
    text = (args.get("text") or "").lower()
    key = "caste_income" if ("caste" in text or "income" in text) else "pension" if "pension" in text else "ration_new" if "ration" in text else ""
    st = sess["state"]
    if not key:
        _set_options(sess, [["Caste & Income Certificate", "apply:caste_income"], ["Old-age pension", "apply:pension"], ["New Ration Card", "apply:ration_new"]])
        return {"say": "Which service do you want to apply for: a caste and income certificate, old-age pension, or a new ration card?",
                "ui": [{"op": "request", "draft": {}, "flow": "apply", "options": st["options"]}]}
    return await _run_option(sess, f"apply:{key}")


async def t_later(sess, args):
    return {"say": "Okay. Whenever you are ready, tell me your reply, or ask me to track your requests."}


# ------------------------------------------------------------------ officer
async def t_login_as(sess, args):
    oid = find_officer(args.get("officer") or "")
    if not oid:
        return {"say": "I could not find that officer. Try 'Tahsildar Hunsur' or 'PDO Chapparadahalli'."}
    sess["officer"] = oid
    sess["state"]["case_id"] = None
    store.save_session(sess)
    st = await load_state(sess)
    rows = inbox_for(st, oid)
    sess["state"]["list"] = [r["id"] for r in rows[:12]]
    say = f"Logged in as {off_name(oid, False)}. {len(rows)} open case{'s' if len(rows) != 1 else ''}"
    od = sum(1 for r in rows if r["left"] < 0)
    say += f", {od} overdue." if od else "."
    return {"say": say, "ui": [{"op": "login", "officer": oid, "officerName": off_name(oid, False)},
                              {"op": "inbox", "officer": oid, "officerName": off_name(oid, False), "cases": rows[:12], "total": len(rows)}]}


async def t_inbox(sess, args):
    st = await load_state(sess)
    rows = inbox_for(st, sess["officer"])
    sess["state"]["list"] = [r["id"] for r in rows[:12]]
    n, od, vul = len(rows), sum(1 for r in rows if r["left"] < 0), sum(1 for r in rows if r["vulnerable"])
    if not rows:
        say = "Your inbox is clear. Nothing is pending with you."
    else:
        say = f"You have {n} open case{'s' if n != 1 else ''}"
        say += f", {od} overdue" if od else ""
        say += f", {vul} from vulnerable citizens" if vul else ""
        say += ". "
        top = rows[0]
        say += f"The most urgent is {top['id']}: {top['service']} in {top['gp'] or top['taluk']}, {top['leftText']}. Shall I open it?"
    sess["state"]["offer_open"] = rows[0]["id"] if rows else None
    return {"say": say, "ui": [{"op": "inbox", "officer": sess["officer"], "officerName": off_name(sess["officer"], False), "cases": rows[:12], "total": n}]}


def _pick_case(sess, st, args) -> dict | None:
    cases = {c["id"]: c for c in st["cases"]}
    cid = (args.get("case_id") or "").upper().replace(" ", "")
    if cid:
        for k in cases:
            if k.upper() == cid or (len(cid) >= 5 and k.upper().endswith(cid)):
                return cases[k]
        return None                              # an id that is not on this screen is never swapped for another case
    lst = sess["state"].get("list") or []
    if not lst and sess["profile"] == "officer":
        lst = [r["id"] for r in inbox_for(st, sess["officer"])[:12]]
    if args.get("ordinal"):
        from .query import ordinal
        n = ordinal(args["ordinal"]) or 1          # the brain may say "first" / "2nd" / "last"
        if lst:
            idx = len(lst) - 1 if n == -1 else max(0, min(len(lst) - 1, n - 1))
            return cases.get(lst[idx])
    text = (args.get("text") or "").lower()
    if text and lst:
        now = st["_now"]
        rows = [case_brief(cases[i], now) for i in lst if i in cases]
        if "overdue" in text or "oldest" in text:
            rows = [r for r in rows if r["left"] < 0] or rows
            return cases.get(min(rows, key=lambda r: r["left"])["id"]) if rows else None
        if "vulnerable" in text or "priority" in text:
            rows = [r for r in rows if r["vulnerable"]] or rows
            return cases.get(rows[0]["id"]) if rows else None
        for r in rows:
            blob = f"{r['service']} {r['grievance']} {r['masked']}".lower()
            if any(w in blob for w in text.split() if len(w) > 3):
                return cases[r["id"]]
    if lst:
        return cases.get(lst[0])
    return None


async def t_open_case(sess, args):
    said = args.get("_text") or ""
    cid0 = str(args.get("case_id") or "").strip().lower()
    if cid0 and not re.search(r"\d", cid0) and re.fullmatch(r"(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|next|top)( one)?", cid0):
        args = {**args, "ordinal": cid0.split()[0], "case_id": None}
    if not args.get("case_id") and not args.get("ordinal") and not re.search(r"\b(GR|SK)[- ]?\w+|\b\d{6}\b", said, re.I) and \
            re.search(r"\b(cases|grievances|complaints|statewide|district|how many|count)\b", said, re.I):
        return await t_ask_data(sess, {"query": said, "_text": said})         # "open cases statewide?" is a question, not "open a case"
    st = await load_state(sess)
    if not any(args.get(k) for k in ("case_id", "ordinal", "text")) and sess["state"].get("offer_open"):
        args = {"case_id": sess["state"]["offer_open"]}
    c = _pick_case(sess, st, args)
    if not c and args.get("case_id"):
        c = await full_case(args["case_id"].upper().replace(" ", ""))     # any case in the state, by id
        if c and sess["profile"] == "officer" and not on_ladder(sess["officer"], c.get("owner") or ""):
            return {"say": f"{c['id']} is not on your desk or your team's, so I can't open it. It is with {off_name(c.get('owner') or '')}."}
    if not c and args.get("case_id"):
        from . import query                  # any case or Excel G.Id, also outside this screen's list
        return await query.run(sess, "lookup_case", {"case_id": args["case_id"]})
    if not c:
        return {"say": "I could not find that case. You can ask me to read your inbox and pick one."}
    c = await full_case(c["id"]) or c
    sess["state"]["case_id"] = c["id"]
    sess["state"]["offer_open"] = None
    b = case_brief(c, st["_now"])
    say = spoken_case(b)
    if sess["profile"] == "officer":
        say += " Say accept, ask the citizen, draft the report, resolve, return or reject."
    return {"say": say, "ui": [{"op": "case", "case": b}]}


async def t_next_case(sess, args):
    st = await load_state(sess)
    rows = inbox_for(st, sess["officer"])
    cur = sess["state"].get("case_id")
    ids = [r["id"] for r in rows]
    nxt = None
    if cur in ids and ids.index(cur) + 1 < len(ids):
        nxt = ids[ids.index(cur) + 1]
    elif ids:
        nxt = ids[0]
    if not nxt:
        return {"say": "No more cases. Your inbox is clear."}
    sess["state"]["list"] = ids[:12]
    return await t_open_case(sess, {"case_id": nxt})


async def t_read_case(sess, args):
    st = await load_state(sess)
    cid = sess["state"].get("case_id")
    c = await full_case(cid) if cid else None
    if not c:
        return {"say": "Open a case first."}
    b = case_brief(c, st["_now"])
    au = b.get("audit") or {}
    route = (au.get("route") or {})
    say = f"{b['id']} came in via {b['src']}. The AI read it as {b['service']}"
    if b.get("conf"):
        say += f", {round(float(b['conf']) * 100)} percent sure"
    say += f". Reason: {clean_for_speech(b.get('why') or '')}. "
    if route:
        say += f"Routing rule: {route.get('role', '')} handled {round(float(route.get('share') or 0) * 100)} percent of {route.get('support', 0)} real cases of this service. "
    say += "History: " + "; ".join(f"{h['what']}" for h in b["history"][-4:]) + "."
    return {"say": say, "ui": [{"op": "case", "case": b, "focus": "evidence"}]}


async def _act(sess, action: str, **extra):
    cid = sess["state"].get("case_id")
    if not cid:
        return None, {"say": "Open a case first: say 'read my inbox' or 'open GR-504203'."}
    officer = "" if sess["profile"] == "cs" else sess["officer"]
    heard = extra.pop("heard", "")
    r = await sakala.action(cid, action=action, officer=officer, via="Mitra (voice)", heard=guard.mask(heard)[:200], **extra)
    if r.get("http"):
        say = await _refusal(sess, cid, action, r)
        return cid, {"say": say, "ui": [{"op": "toast", "h": "Not allowed", "m": say}], "refused": True}
    return cid, r


async def _refusal(sess, cid: str, action: str, r: dict) -> str:
    """Guardrail 19: Sakala's rules (owner only, ladders never mix, closed cases, compensation only on late Sakala
    applications, reasons and reports required) spoken as plain sentences."""
    d, code = (r.get("detail") or "").lower(), r.get("http")
    owner = ""
    try:
        c = await full_case(cid)
        owner = off_name(c["owner"]) if c and c.get("owner") else ""
    except Exception:
        c = None
    if code == 404:
        return f"I could not find {cid} in Sakala."
    if "only the officer who holds" in d:
        if sess["profile"] == "cs":
            return f"Only the officer who holds {cid} can do that" + (f"; it is with {owner}" if owner else "") + ". I can send them a reminder if you like."
        return f"{cid} is not on your desk" + (f"; it is with {owner}" if owner else "") + ". Only the officer who holds a case can act on it."
    if d.startswith("case is "):
        st = d[8:].strip()
        return f"{cid} is already {st}, so " + ("there is nothing to remind them about." if action == "nudge" else "it cannot be changed now.")
    if "only to sakala applications" in d:
        return (f"Compensation applies only to Sakala applications. {cid} is a grievance; it follows the escalation ladder, "
                f"from the field officer to their senior and then the district officer, instead.")
    if "competent officer" in d:
        return f"Only the Competent Officer for {cid} can order compensation or approve the debit note."
    if "no delay" in d:
        return f"{cid} is still within its Sakala deadline, so there is no compensation to order."
    if "reason is mandatory" in d:
        return "A rejection needs a reason. What is the reason?"
    if "action taken report" in d:
        return "Tell me what was done in at least one full sentence, and I will close it with that report."
    if "only scrutiny-desk cases" in d:
        return f"Only cases waiting at the scrutiny desk can be re-routed, and {cid} is not one of them."
    if "designated" in d and "ladder" in d:
        return "Sakala applications follow the Designated, Competent and Appellate officer ladder; they never go to the grievance desk."
    if "unknown officer" in d:
        return "I don't know that officer."
    return "Sakala did not allow that: " + (r.get("detail") or "the action is not permitted") + "."


async def _refresh_case_ui(sess) -> list[dict]:
    st = await load_state(sess)
    cid = sess["state"].get("case_id")
    ui = []
    c = await full_case(cid) if cid else None
    if c:
        ui.append({"op": "case", "case": case_brief(c, st["_now"])})
    if sess["profile"] == "officer":
        rows = inbox_for(st, sess["officer"])
        ui.append({"op": "inbox", "officer": sess["officer"], "officerName": off_name(sess["officer"], False), "cases": rows[:12], "total": len(rows)})
    if sess["profile"] == "cs":
        ui.append(await _kpi_ui(st))
    return ui


async def t_accept(sess, args):
    cid, r = await _act(sess, "accept", heard=args.get("_text", ""))
    if not cid or r.get("refused"):
        return r
    return {"say": f"Accepted {cid}. The citizen has been told you started work.", "ui": await _refresh_case_ui(sess)}


async def t_ask_info(sess, args):
    q = (args.get("question") or "Please share more details about your request.").strip()
    cid, r = await _act(sess, "info", note=q, heard=args.get("_text", ""))
    if not cid or r.get("refused"):
        return r
    return {"say": f"Sent to the citizen: {q}", "ui": await _refresh_case_ui(sess)}


async def t_draft_atr(sess, args):
    cid = sess["state"].get("case_id")
    if not cid:
        return {"say": "Open a case first."}
    r = await sakala.draft_atr(cid)
    text = r.get("text") or ""
    sess["state"]["atr_draft"] = text
    say = "Here is a draft. " + clean_for_speech(text) + " When you are ready, tell me to resolve it and say what you actually did."
    return {"say": say, "ui": [{"op": "atr", "text": text, "engine": r.get("engine")}]}


async def t_resolve(sess, args):
    atr = (args.get("atr") or "").strip()
    if len(atr) < 15:
        return {"say": "Tell me what was done in at least one full sentence, for example: 'resolve: inspected the site, pipeline repaired, supply restored'."}
    cid, r = await _act(sess, "resolve", atr=atr, heard=args.get("_text", ""))
    if not cid or r.get("refused"):
        return r
    score, reason, engine = r.get("score"), r.get("reason", ""), r.get("engine", "")
    if score and score >= 4:
        say = f"Resolved {cid}. The AI resolution check scored it {score} out of 5. The citizen has been asked to confirm."
    else:
        say = f"Not closed. The AI scored this report {score} out of 5: {clean_for_speech(reason)}. Add what was actually done and say resolve again."
    return {"say": say, "ui": [{"op": "atr", "text": atr, "score": score, "reason": reason, "engine": engine}] + await _refresh_case_ui(sess)}


def _return_target(args: dict) -> tuple[str, str]:
    """The suggested officer and place of a return, whatever names the model gave them."""
    to = next((str(args[k]).strip() for k in ("to", "target", "officer", "to_officer", "suggested_officer", "send_to", "destination", "recipient")
               if args.get(k) and str(args[k]).strip()), "")
    place = next((str(args[k]).strip() for k in ("place", "location", "taluk", "gp", "village", "jurisdiction")
                  if args.get(k) and str(args[k]).strip()), "")
    if re.fullmatch(r"(the )?(scrutiny desk|another (office|department)|someone|somebody|other)", to, re.I):
        to = ""
    if not to and not place and args.get("_text"):
        from . import brain
        to = brain.return_suggestion(args["_text"])          # the model left it out: the officer's own words decide
    return to, place


async def t_return_case(sess, args):
    to, place = _return_target(args)
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
    return {"say": say, "ui": ui}


async def t_reject(sess, args):
    reason = (args.get("reason") or "").strip() or "Duplicate of an existing request"
    cid, r = await _act(sess, "reject", reason=reason, heard=args.get("_text", ""))
    if not cid or r.get("refused"):
        return r
    return {"say": f"Rejected {cid}: {reason}. The citizen has been told the reason and their right to appeal.", "ui": await _refresh_case_ui(sess)}


async def t_comp_order(sess, args):
    cid, r = await _act(sess, "comp_order", heard=args.get("_text", ""))
    if not cid or r.get("refused"):
        return r
    return {"say": f"Compensation ordered on {cid}: {r.get('toast', ['', ''])[1]}. Next: the Form C notice, then the HRMS debit.", "ui": await _refresh_case_ui(sess)}


async def t_comp_hrms(sess, args):
    cid, r = await _act(sess, "comp_hrms", heard=args.get("_text", ""))
    if not cid or r.get("refused"):
        return r
    return {"say": f"HRMS debit note approved on {cid}. {r.get('toast', ['', ''])[1]}", "ui": await _refresh_case_ui(sess)}


# ------------------------------------------------------------------ voice notes between roles
async def t_voice_note(sess, args, to_role: str):
    raw = (args.get("text") or "").strip()
    text = re.sub(r"^.*?\b(note|message|tell|inform|send)\b\s+(a\s+|the\s+)?(voice\s+note\s+|message\s+|note\s+)?(to\s+)?(the\s+)?"
                  r"(chief secretary|madam|officer|citizen|tahsildar[\w ]*|pdo[\w ]*|[\w]+)[:,]?\s+(that\s+|saying\s+)?", "", raw, flags=re.I).strip()
    if not text or len(text) < 3:
        text = raw
    cid = sess["state"].get("case_id") or args.get("case_id") or ""
    to_officer = ""
    if to_role == "officer":
        if sess["profile"] == "cs":
            to_officer = find_officer(args.get("officer") or raw) or ""
        elif cid:
            st = await load_state(sess)
            c = next((x for x in st["cases"] if x["id"] == cid), None)
            to_officer = c["owner"] if c else ""
    nid = store.add_note(case_id=cid, from_role=sess["profile"], to_role=to_role,
                         from_officer=sess["officer"] if sess["profile"] != "citizen" else "",
                         to_officer=to_officer, session=sess["chat_session"], transcript=text,
                         audio_b64=sess["state"].pop("last_audio", "") or "")
    if to_role == "citizen" and cid and sess["profile"] == "officer":
        await sakala.action(cid, action="info", officer=sess["officer"], note=f"(voice note) {text}", via="Mitra (voice note)")
    if to_role == "officer" and cid and sess["profile"] == "citizen":
        await intake(sess, step="reply", case_id=cid, text=f"(voice note) {text}")
    who = {"cs": "the Chief Secretary", "officer": off_name(to_officer, False) if to_officer else "the officer", "citizen": "the citizen"}[to_role]
    from .sync import broker
    await broker.publish({"type": "voice_note", "id": nid, "to_role": to_role, "to_officer": to_officer, "case_id": cid,
                          "from_role": sess["profile"], "from_officer": sess.get("officer", ""), "transcript": text})
    from . import notify
    await broker.publish_feed(notify.log_voice(nid, to_role, to_officer, cid, sess["profile"],
                                               sess.get("officer", "") if sess["profile"] != "citizen" else "", text))
    return {"say": f"Voice note sent to {who}.", "ui": [{"op": "toast", "h": "Voice note", "m": f"to {who}"}]}


async def t_voice_note_officer(sess, args):
    return await t_voice_note(sess, args, "officer")


async def t_voice_note_cs(sess, args):
    return await t_voice_note(sess, args, "cs")


async def t_voice_note_citizen(sess, args):
    return await t_voice_note(sess, args, "citizen")


# ------------------------------------------------------------------ chief secretary
async def _kpi_ui(st: dict) -> dict:
    now = st["_now"]
    cases = st["cases"]
    opened = [c for c in cases if is_open(c)]
    overdue = [c for c in opened if days_left(c, now)[0] < 0]
    vul = [c for c in opened if c.get("vulnerable")]
    esc = [c for c in cases if c.get("escalated") or any(h["what"].startswith("Auto-escalated") for h in c.get("history") or [])]
    by_level = {"L1": 0, "L2": 0, "L3": 0}
    for c in opened:
        by_level[c["level"]] = by_level.get(c["level"], 0) + 1
    by_dept = {}
    for c in opened:
        d = (c.get("u") or {}).get("d") or "—"
        by_dept[d] = by_dept.get(d, 0) + 1
    rows = [case_brief(c, now) for c in opened]
    rows.sort(key=lambda b: (b["left"], not b["vulnerable"]))
    board = {}
    try:
        b = await sakala._post("/api/query", {"tool": "dashboard", "args": {}})
        if not b.get("http"):
            board = {"kpis": b["kpis"], "days_left": b["days_left"], "by_level": b["by_level"], "departments": b.get("departments") or [],
                     "places": (b.get("places") or [])[:6], "officers": (b.get("officers") or [])[:5]}
    except Exception:
        board = {}
    return {"op": "kpi", "board": board, "now": st["now"], "pending": len(opened), "overdue": len(overdue), "vulnerable": len(vul),
            "escalated": len(esc), "scrutiny": sum(1 for c in cases if c["status"] == "Scrutiny"),
            "byLevel": by_level, "byDept": by_dept,
            "cases": [{k: b[k] for k in ("id", "service", "ownerShort", "owner", "level", "left", "leftText", "vulnerable", "taluk", "gp")} for b in rows[:60]]}


async def t_summary(sess, args):
    sess["state"]["scope"] = {}                          # the whole state: no department / place filter any more
    st = await load_state(sess)
    k = await _kpi_ui(st)
    try:
        pack = await sakala.review_pack("cs", "")
    except Exception:
        pack = {}
    f = pack.get("facts") or {}
    top = f.get("top_issues") or []
    mo = f.get("most_overdue_officers") or []
    say = (f"Chief Secretary Madam, {k['pending']} cases are pending across Karnataka, {k['overdue']} overdue, "
           f"{k['vulnerable']} from vulnerable citizens, {k['escalated']} auto-escalated. ")
    if top:
        say += "Top issues: " + ", ".join(f"{t[0]}" if isinstance(t, (list, tuple)) else str(t) for t in top[:3]) + ". "
    if mo:
        m0 = mo[0]
        name = m0[0] if isinstance(m0, (list, tuple)) else m0
        n = m0[1] if isinstance(m0, (list, tuple)) and len(m0) > 1 else ""
        say += f"Most overdue officer: {name}{f' with {n}' if n else ''}. "
    sess["state"]["list"] = [c["id"] for c in k["cases"][:12]]
    names = {"REV": "Revenue", "RDPR": "RDPR", "FOOD": "Food & Civil Supplies"}
    viz = {"op": "viz", "title": "The position", "insight": f"{k['pending']} pending across Karnataka, {k['overdue']} overdue",
           "cards": [{"type": "donut", "title": "Pending by department", "subtitle": "live caseload", "metric": "open", "unit": "cases", "by": "department",
                      "items": [{"label": names.get(d, d), "value": n, "aliases": ["rural", "panchayat"] if d == "RDPR" else ["food"] if d == "FOOD" else [], "district": ""} for d, n in sorted((k.get("byDept") or {}).items(), key=lambda x: -x[1])]},
                     {"type": "bars", "title": "Pending by level", "subtitle": "L1 field · L2 · L3", "metric": "open", "unit": "cases", "by": "level",
                      "items": [{"label": l, "value": (k.get("byLevel") or {}).get(l, 0), "aliases": ["field officer", "level one"] if l == "L1" else ["level two"] if l == "L2" else ["level three"], "district": ""} for l in ("L1", "L2", "L3")]}]}
    return {"say": say, "ui": [k, {"op": "facts", "facts": f}, viz, {"op": "scope", "scope": {}, "label": ""}]}


_ID_RX = re.compile(r"\b(SK-?[A-Z0-9]{8,}|GR[-\s]?\d{5,7}|\d{6})\b", re.I)


_CMP_RX = re.compile(r"\b(compare|comparison|versus|vs\.?|against|side by side)\b", re.I)
_RANK_RX = re.compile(r"\b(which|what)\s+(district|taluk|officer|department|service|gp|gram panchayat|channel|source)s?\s+(has|have|had|is|are|with)\b.*\b(most|highest|largest|maximum|top|worst|least|fewest|lowest)\b|\btop\s+\d*\s*(district|taluk|officer|department|service)s?\b", re.I)
_METRIC_RX = re.compile(r"\b(open|pending|overdue|late|resolved|solved|closed|rejected|vulnerable|escalated|scrutiny|total|due soon)\b", re.I)


_DIM = r"(district|taluk|gram panchayat|gp|department|dept|service|officer|channel|source|status|level)"
_BREAK_RX = re.compile(r"\b(each|every|all|all the|per|by|across|between|among)\s+(the\s+)?" + _DIM + r"s?\b|\b" + _DIM + r"[- ]?wise\b", re.I)
_MAPWORD_RX = re.compile(r"\b(map|where|which parts?|across (the )?(state|karnataka)|district[- ]?wise|geograph\w*|spread|footprint)\b", re.I)


def _chart_word(t: str) -> str:
    from . import query
    if _MAPWORD_RX.search(t or ""):
        return "map"
    m = re.search(r"\b(line|trend|donut|doughnut|pie|bar|bars|column)\b", t or "", re.I)
    return query.chart_kind(m.group(1)) if m else ""


def _compare_args(text: str):
    """('compare', args) / ('ranking', args) / ('find_cases', group_by) when the sentence compares things, asks which has the
    most, or asks for a breakdown by a dimension; the chart (bars, line, donut, the Karnataka map) follows the words."""
    r = _compare_args0(text)
    if r:
        ch = _chart_word(text)
        if ch:
            r[1]["chart"] = ch
    return r


_CHARTPHRASE_RX = re.compile(r"\b(on|in|as|with|using|onto)\s+(the\s+|a\s+|an\s+)?(karnataka\s+|state\s+)?(map|donut|doughnut|pie(\s+chart)?|line(\s+graph|\s+chart)?|bar(\s+chart|\s+graph)?|bars|chart|graph)\b", re.I)
_DEPTS = {"revenue": "Revenue", "rdpr": "RDPR", "rural development": "RDPR", "panchayat": "RDPR", "food": "Food", "civil supplies": "Food", "ration": "Food"}


_ACCORDING_RX = re.compile(r"\b(according to|based on|as per|grouped by|split by|broken (?:down|up) by|sorted by|classified by|categori[sz]ed by)\b", re.I)
_SOURCE_WORD_RX = re.compile(r"\binput sources?\b|\borigins?\b|\bsources? of (?:the )?(?:grievances|cases|complaints|requests)\b", re.I)
_DIM_FILLER_RX = re.compile(r"\b(?:(?:their|its|respective|specific|individual|different|various)\s+)+(?=(?:input |)(?:district|taluk|department|dept|service|officer|channel|source|status|level|gram panchayat|gp)s?\b)", re.I)


def _breakdown_words(t: str) -> str:
    """'according to their specific input sources' -> 'by source': the breakdown wording people use, read as one shape."""
    t = _ACCORDING_RX.sub("by", t)
    t = _SOURCE_WORD_RX.sub("source", t)
    t = _DIM_FILLER_RX.sub("", t)
    t = re.sub(r"\bwhere (?:did |do |does |are |is )?(?:they|all )?(?:the |these |those )?(?:cases|grievances|complaints|requests)? ?(?:come|came|coming) from\b", "by source", t, flags=re.I)
    return t


def _compare_args0(text: str):
    t = _breakdown_words(_CHARTPHRASE_RX.sub(" ", (text or "")).strip())
    if not t:
        return None
    metrics = [m.lower() for m in _METRIC_RX.findall(t)]
    # "where are the revenue / overdue cases", "show me across the state where ...": the district breakdown, on the map
    if re.search(r"\bwhere\b|\bwhich parts?\b|\bacross (the )?(state|karnataka)\b|\bdistrict[- ]?wise\b", text or "", re.I) and \
            re.search(r"\b(cases|grievances|complaints|requests|applications)\b", t, re.I) and not re.search(r"\b(GR|SK)[- ]?\w+", t, re.I):
        args = {"group_by": "district", "limit": 31, "chart": "map"}
        d = next((v for k, v in _DEPTS.items() if re.search(r"\b" + k, t, re.I)), "")
        if d:
            args["department"] = d
        m0 = metrics[0] if metrics else ""
        if m0 in ("open", "pending", "overdue", "late", "resolved", "rejected", "scrutiny"):
            args["status"] = {"pending": "open", "late": "overdue"}.get(m0, m0)
        return "find_cases", args
    b = _BREAK_RX.search(t) or re.search(r"\b(district|taluk|department|service|officer|channel|source)s\b.*\b(across|spread|split|breakdown|map|wise|each|every)\b", t, re.I) or \
        re.search(r"\b(district|taluk|department|service|officer|channel|source)s?[- ]?(breakdown|split|spread|wise|mix|distribution)\b", t, re.I)
    if b and not re.search(r"\b(which|what)\b.*\b(most|highest|largest|top|worst|least|fewest|lowest)\b", t, re.I):
        dim = next(g for g in b.groups() if g and re.fullmatch(_DIM, g, re.I)).lower()
        dim = {"gram panchayat": "gp", "dept": "department", "channel": "source"}.get(dim, dim)
        named = len([x for x in re.split(r",|\band\b", re.sub(r"^.*?\bcompare\b", "", t, flags=re.I)) if len(x.strip()) >= 3]) >= 2 and _CMP_RX.search(t)
        if not named or re.search(r"\b(each|every|all)\b", t, re.I):
            args = {"group_by": dim, "limit": 31 if dim == "district" else 12}
            m0 = metrics[0] if metrics else ""
            if m0 in ("open", "pending"):
                args["status"] = "open"
            elif m0 in ("overdue", "late"):
                args["status"] = "overdue"
            elif m0 in ("resolved", "solved", "closed", "rejected", "scrutiny"):
                args["status"] = {"solved": "resolved", "closed": "resolved"}.get(m0, m0)
            return "find_cases", args
    ml = re.search(r"\bhow\s+(?:do|does|are)\s+(.+?)\s+(?:taluks?|districts?|departments?|officers?)?\s*(?:compare|stack up|fare|look)\b", t, re.I)
    if ml and re.search(r",|\band\b", ml.group(1)):                    # "how do Piriyapatna, Hunsur and Mysuru taluks compare on open cases"
        ents = [e.strip(" ,.?!") for e in re.split(r",|\band\b", ml.group(1)) if len(e.strip(" ,.?!")) >= 3]
        if len(ents) >= 2:
            return "compare", {"entities": ", ".join(ents), "metrics": ", ".join(metrics) if metrics else "open"}
    mh = re.search(r"\bwhich\s+(district|taluk|department|service|officer|channel|source)s?\s+(?:has|have|got|gets)\s+how\s+many\b", t, re.I)
    if mh:                                                             # "which department has how many cases" = the breakdown
        return "find_cases", {"group_by": {"channel": "source"}.get(mh.group(1).lower(), mh.group(1).lower()), "limit": 31 if mh.group(1).lower() == "district" else 12}
    mw = re.search(r"\b(?:how (?:does|do|is|are)\s+)?(.+?)\s+(?:compare|compares|stack up|fare)\s+(?:with|to|against)\s+(.+?)[?.!]*$", t, re.I)
    if mw and not re.search(r"^\s*compare\b", t, re.I):
        ents = [e.strip(" ,.?!") for e in re.split(r",|\band\b", mw.group(1) + "," + mw.group(2)) if len(e.strip(" ,.?!")) >= 3]
        ents = [re.sub(r"^(how (does|do|is|are)|the)\s+", "", e, flags=re.I) for e in ents]
        if len(ents) >= 2:
            return "compare", {"entities": ", ".join(ents), "metrics": ", ".join(metrics) if metrics else "open"}
    if _CMP_RX.search(t):
        body = re.sub(r"^.*?\b(compare|comparison of|comparison between)\b", "", re.sub(r"\bside by side\b\W*", " ", t, flags=re.I), count=1, flags=re.I)
        body = re.sub(r"\b(on|by|in terms of|for|regarding|their|the number of|number of)\b.*$", "", body, count=1, flags=re.I) if _METRIC_RX.search(body) else body
        body = re.sub(r"\b(open|pending|overdue|late|resolved|solved|closed|rejected|vulnerable|escalated|scrutiny|total|cases|grievances|please|can you|could you|me|madam|sir)\b", " ", body, flags=re.I)
        ents = [e.strip(" ,.?!") for e in re.split(r",|\band\b|\bversus\b|\bvs\.?\b|\bagainst\b|\bwith\b|;", body, flags=re.I)]
        ents = [e for e in ents if len(e) >= 3]
        if len(ents) >= 2:
            return "compare", {"entities": ", ".join(ents), "metrics": ", ".join(metrics) if metrics else "open"}
    m = _RANK_RX.search(t) or re.search(r"\b(?:rank|ranking|order|sort|league table)\b.*?\b(district|taluk|officer|department|service|channel|source)s?\b|"
                                     r"\b(district|taluk|officer|department|service)s?\b.*?\b(?:ranked|in order|league table)\b|"
                                     r"\bwhere\b.*\b(?:most|biggest|largest|highest)\b.*\b(?:pile|number|count)?\b", t, re.I)
    if m:
        by = next((g for g in m.groups() if g and g.lower() in ("district", "taluk", "officer", "department", "service", "gp", "gram panchayat", "channel", "source")), "district").lower()
        by = {"gram panchayat": "gp", "channel": "source"}.get(by, by)
        return "ranking", {"by": by, "metric": metrics[0] if metrics else "open", "limit": 8}
    return None


async def t_ask_data(sess, args):
    q = (args.get("query") or "").strip()
    m = _ID_RX.search(q) or _ID_RX.search(args.get("_text") or "")
    if m:                                    # a question about one case / one iPGRS G.Id: answer it exactly
        from . import query
        return await query.run(sess, "lookup_case", {"case_id": m.group(1)})
    rt = route_question(args.get("_text") or q or "", sess["profile"], sess["state"]) or route_question(q or "", sess["profile"], sess["state"])
    if rt:                                   # a data question with an exact SQL answer: comparison, ranking, count, officer, place
        if rt[0] == "inbox":
            return await t_inbox(sess, {})
        from . import query
        return await query.run(sess, rt[0], {**rt[1], "_text": args.get("_text") or q})
    try:
        r = await sakala.ask(q)
    except Exception:
        r = {}
    if r.get("engine") == "ai" and r.get("html"):
        say = clean_for_speech(r["html"])
        ui = [{"op": "answer", "html": r["html"], "q": q}]
        viz = viz_from_chart(r.get("chart") or {}, q[:60], by="district" if re.search(r"district", q, re.I) else "")
        if viz:
            ui.append(viz)
        return {"say": say, "ui": ui}
    st = await load_state(sess)
    k = await _kpi_ui(st)
    low = q.lower()
    if "overdue" in low and "officer" in low:
        cnt = {}
        for c in k["cases"]:
            if c["left"] < 0:
                cnt[c["ownerShort"]] = cnt.get(c["ownerShort"], 0) + 1
        top = sorted(cnt.items(), key=lambda x: -x[1])[:5]
        if top:
            say = f"{top[0][0]} has the most overdue cases, {top[0][1]}. " + ", ".join(f"{a} {b}" for a, b in top[1:4])
            chart = {"type": "bar", "labels": [a for a, _ in top], "values": [b for _, b in top], "series_label": "Overdue", "unit": "", "title": "Overdue cases by officer", "source": "Live pilot cases"}
            return {"say": say, "ui": [{"op": "answer", "html": f"<b>{say}</b>", "chart": chart, "q": q}]}
        return {"say": "No case is overdue right now."}
    if "department" in low:
        items = sorted(k["byDept"].items(), key=lambda x: -x[1])
        names = {"REV": "Revenue", "RDPR": "RDPR", "FOOD": "Food & Civil Supplies"}
        say = "Pending by department: " + ", ".join(f"{names.get(a, a)} {b}" for a, b in items) + "."
        chart = {"type": "bar", "labels": [names.get(a, a) for a, _ in items], "values": [b for _, b in items], "series_label": "Pending", "unit": "", "title": "Pending cases by department", "source": "Live pilot cases"}
        return {"say": say, "ui": [{"op": "answer", "html": f"<b>{say}</b>", "chart": chart, "q": q}]}
    say = f"{k['pending']} pending, {k['overdue']} overdue, {k['vulnerable']} vulnerable, {k['escalated']} auto-escalated. The AI data mode needs the gateway for anything deeper."
    return {"say": say, "ui": [k]}


async def t_filter_cases(sess, args):
    cat = (args.get("category") or "all").lower().replace("-", "_").replace(" ", "_")
    cat = {"ontime": "on_time", "on_time": "on_time", "overdue": "overdue", "vulnerable": "vulnerable", "all": "all"}.get(cat, "all")
    said = args.get("_text") or ""
    if cat == "all" and re.search(r"\b(map|district[- ]?wise|across (the )?(state|karnataka)|which parts?|where (are|is))\b", said, re.I):
        from . import query                              # "all the grievances across the map": the per-district picture, not the dot filter
        return await query.run(sess, "find_cases", {"_text": said, "chart": "map"})
    st = await load_state(sess)
    k = await _kpi_ui(st)
    rows = k["cases"]
    if cat == "overdue":
        rows = [r for r in rows if r["left"] < 0]
    elif cat == "vulnerable":
        rows = [r for r in rows if r["vulnerable"]]
    elif cat == "on_time":
        rows = [r for r in rows if r["left"] >= 0]
    sess["state"]["list"] = [r["id"] for r in rows[:12]]
    label = {"overdue": "overdue", "vulnerable": "vulnerable-citizen", "on_time": "on-time", "all": "open"}[cat]
    say = f"Showing {len(rows)} {label} case{'s' if len(rows) != 1 else ''}."
    if rows and cat != "all":
        r0 = rows[0]
        say += f" The first is {r0['id']}, {r0['service']}, with {r0['ownerShort']}, {r0['leftText']}."
    return {"say": say, "ui": [{"op": "filter", "category": cat, "cases": rows[:40], "total": len(rows)}]}


def viz_from_chart(chart: dict, title: str, insight: str = "", by: str = "") -> dict | None:
    """The POC's AI-mode chart ({type, labels, values, unit}) as a stage card, so every visual answer builds on the stage."""
    if not chart or not chart.get("labels"):
        return None
    labels, values = list(chart["labels"]), list(chart.get("values") or [])
    items = [{"label": str(l), "value": v, "aliases": [], "district": str(l) if by == "district" else ""} for l, v in zip(labels, values)]
    t = (chart.get("type") or "bar").lower()
    kind = "line" if t == "line" else ("donut" if t in ("doughnut", "pie") else ("bars" if len(items) <= 5 else "race"))
    card = {"type": kind, "title": chart.get("title") or title, "subtitle": chart.get("source") or "", "metric": chart.get("series_label") or "",
            "unit": "%" if chart.get("unit") == "%" else "cases", "by": by, "items": items}
    if not insight and items:
        top = max(items, key=lambda x: x["value"] or 0)
        insight = f"{top['label']} is the highest at {top['value']}{'%' if card['unit'] == '%' else ''}"
    return {"op": "viz", "title": title, "insight": insight, "cards": [card]}


async def t_officers_attention(sess, args):
    st = await load_state(sess)
    now = st["_now"]
    cnt = {}
    for c in st["cases"]:
        if is_open(c):
            o = cnt.setdefault(c["owner"], {"officer": c["owner"], "name": off_name(c["owner"]), "level": c["level"], "open": 0, "overdue": 0})
            o["open"] += 1
            if days_left(c, now)[0] < 0:
                o["overdue"] += 1
    rows = sorted(cnt.values(), key=lambda o: (-o["overdue"], -o["open"]))[:7]
    if not rows:
        return {"say": "No officer has open cases."}
    say = "Officers needing attention: " + "; ".join(f"{o['name']}, {o['overdue']} overdue of {o['open']}" for o in rows[:4]) + "."
    sess["state"]["officers"] = [o["officer"] for o in rows]
    viz = {"op": "viz", "title": "Officers needing attention", "insight": f"{rows[0]['name']} has the most: {rows[0]['overdue']} overdue of {rows[0]['open']} open",
           "cards": [{"type": "race", "title": "Overdue cases by officer", "subtitle": "open cases in brackets", "metric": "overdue", "unit": "cases", "by": "officer",
                      "items": [{"label": o["name"], "value": o["overdue"], "aliases": [], "district": ""} for o in rows]},
                     {"type": "race", "title": "Open cases by officer", "subtitle": "", "metric": "open", "unit": "cases", "by": "officer",
                      "items": [{"label": o["name"], "value": o["open"], "aliases": [], "district": ""} for o in rows]}]}
    return {"say": say, "ui": [{"op": "officers", "rows": rows}, viz]}


async def _nudge_target(sess, args):
    """(case id, officer id, her message, error sentence) for a nudge."""
    st = await load_state(sess)
    now = st["_now"]
    raw0 = args.get("_text") or ""
    cid = args.get("case_id") or sess["state"].get("case_id")
    if cid and not args.get("officer") and re.search(r"\b(this|that|the same|its)\s+(case|officer|one)\b|\b(him|her|them)\b", raw0, re.I):
        oid = None                                          # "remind this officer": the case on screen, not a search by name
    else:
        oid = find_officer(args.get("officer") or "") or (find_officer(raw0) if _OFFICER_RX.search(raw0) else None)
    if oid and cid and next((c for c in st["cases"] if c["id"] == cid and c["owner"] == oid and is_open(c)), None):
        oid = None                                          # the named officer holds the case on screen: nudge that one
    if oid:
        rows = [case_brief(c, now) for c in st["cases"] if c["owner"] == oid and is_open(c)]
        rows.sort(key=lambda b: b["left"])
        if not rows:
            return None, oid, "", f"{off_name(oid, False)} has no open cases to nudge."
        cid = rows[0]["id"]
    if not cid:
        return None, oid, "", "Which officer or case should I nudge?"
    # her own words travel with the reminder ("only one day left, he needs to get on top of this")
    raw = args.get("_text") or ""
    said = re.search(r"\b(?:tell|telling|say|saying|let)\s+(?:him|her|them|the officer)?\s*(?:know\s+)?(?:that\s+)?(.{6,})$", raw, re.I)
    msg = args.get("text") or args.get("reason") or (said.group(1) if said else "")
    msg = re.sub(r"\s+", " ", msg).strip(" .,")
    if len(msg) < 6 or (oid and msg.lower() in off_name(oid, False).lower()):
        msg = ""
    msg = (msg[0].upper() + msg[1:] + ".") if msg else ""
    return cid, oid, msg, ""


async def t_nudge(sess, args):
    cid, oid, msg, err = await _nudge_target(sess, args)
    if err:
        return {"say": err}
    r = await sakala.action(cid, action="nudge", officer="", note=msg, via="Mitra (voice)", heard=guard.mask(args.get("_text") or "")[:200])
    if r.get("http"):
        return {"say": await _refusal(sess, cid, "nudge", r)}
    who = r.get("toast", ["", ""])[1]
    return {"say": f"Done. Reminder sent on {cid}: {who}." + (f" I passed on your message: {msg}" if msg else ""), "ui": []}


async def t_wednesday_pack(sess, args):
    level = (args.get("level") or "cs").lower()
    oid = {"dc": "dc_mys", "ac": "ac_hunsur", "eo": "eo_piriyapatna"}.get(level, "")
    r = await sakala.review_pack(level, oid)
    html = r.get("html") or ""
    f = r.get("facts") or {}
    if html:
        say = clean_for_speech(html)
        if len(say) > 900:
            say = say[:880].rsplit(".", 1)[0] + "."
    else:
        missed = f.get("sakala_deadlines_missed")
        missed = len(missed) if isinstance(missed, list) else missed
        top = f.get("top_issues") or []
        say = (f"Wednesday pack, {level.upper()} level. Open {f.get('open')}, overdue {f.get('overdue')}, vulnerable waiting {f.get('vulnerable_waiting')}, "
               f"auto-escalated {f.get('auto_escalated')}, Sakala deadlines missed {missed}.")
        if top:
            say += " Top issues: " + ", ".join(f"{t[0]}" if isinstance(t, (list, tuple)) else str(t) for t in top[:3]) + "."
        mo = f.get("most_overdue_officers") or []
        if mo:
            say += " Most overdue: " + ", ".join(f"{m[0]} ({m[1]})" if isinstance(m, (list, tuple)) and len(m) > 1 else str(m) for m in mo[:3]) + "."
    return {"say": say, "ui": [{"op": "pack", "level": level, "html": html, "kn": r.get("kn"), "facts": f}]}


async def t_e4(sess, args):
    rows = await sakala.e4()
    if not rows:
        return {"say": "No officer has more than 7 overdue cases, so no Form E-4 is due.", "ui": [{"op": "e4", "rows": []}]}
    say = "Form E-4 show-cause is due for " + ", ".join(f"{r['officer']} with {r['defaults']} defaults" for r in rows[:4]) + "."
    viz = {"op": "viz", "title": "Form E-4 show-cause", "insight": f"{rows[0]['officer']} has the most defaults: {rows[0]['defaults']}",
           "cards": [{"type": "race", "title": "Defaults by officer (more than 7 = Form E-4)", "subtitle": "Sakala Act s.14(4)", "metric": "defaults", "unit": "cases", "by": "officer",
                      "items": [{"label": r["officer"], "value": r["defaults"], "aliases": [], "district": ""} for r in rows[:10]]}]}
    return {"say": say, "ui": [{"op": "e4", "rows": rows}, viz]}


CHART_KINDS = {"bar": "bars", "bars": "bars", "column": "bars", "line": "line", "trend": "line", "donut": "donut", "doughnut": "donut", "pie": "donut",
               "ring": "donut", "map": "map", "karnataka": "map", "race": "race", "ranking": "race"}


async def t_show_chart_as(sess, args):
    """The chart on screen, redrawn in another form (the client keeps the numbers; this only names the shape)."""
    said = args.get("_text") or ""
    from . import board as _board
    pronoun = re.search(r"^\W*(now\s+)?(can you\s+)?(show|switch|change|turn|make|put|draw|display)\s+(me\s+)?(it|that|this|them|these|the same)\b", said, re.I)
    if sess["profile"] == "cs" and not pronoun and (_board.dept_of(said) or _board._place(said) or _board.level_of(said)):
        ent = {**_board._place(said), **({"department": _board.dept_of(said)} if _board.dept_of(said) else {}), **({"level": _board.level_of(said)} if _board.level_of(said) else {})}
        from . import query
        return await query.run(sess, "dashboard", {**ent, "_text": said})     # 'show me RDPR on the map': a new map question, not a redraw
    if not sess["state"].get("last_viz") or route_question(said, sess["profile"]) and not pronoun:
        rt = route_question(said, sess["profile"])
        if rt:                                   # a new question that mentions a chart: answer it (the chart kind rides along)
            return await t_ask_data(sess, {"query": said, "_text": said})
    word = (args.get("kind") or args.get("_text") or "").lower()
    kind = next((CHART_KINDS[k] for k in CHART_KINDS if re.search(r"\b" + k + r"\b", word)), "")
    if not kind:
        return {"say": "I can show it as bars, a line graph, a donut or on the Karnataka map. Which one?", "ui": []}
    name = {"bars": "a bar chart", "line": "a line graph", "donut": "a donut", "map": "the Karnataka map", "race": "a ranking"}[kind]
    return {"say": f"Here it is as {name}.", "ui": [{"op": "morph", "kind": kind}]}


async def t_tracker(sess, args):
    r = await sakala.tracker()
    s = r.get("state") or {}
    d = r.get("districts") or []
    worst = d[0] if d else {}
    best = d[-1] if d else {}
    say = (f"Sakala 2025, statewide: {round(s.get('receipts', 0) / 1e7, 1)} crore applications, {s.get('late_pct', 0):.2f} percent late, "
           f"{s.get('rej_pct', 0):.2f} percent rejected. Overdue fell from {int(s.get('overdue_first', 0)):,} to {int(s.get('overdue_last', 0)):,}. "
           f"Worst district {worst.get('district')} at {worst.get('late_pct', 0):.1f} percent late; best {best.get('district')} at {best.get('late_pct', 0):.1f}.")
    chart = {"type": "bar", "labels": [x["district"] for x in d[:8]], "values": [round(x["late_pct"], 2) for x in d[:8]],
             "series_label": "Delivered late", "unit": "%", "title": "Late delivery by district, 2025", "source": "Sakala district performance reports, 2025"}
    monthly = r.get("monthly") or []
    line = {"type": "line", "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][:len(monthly)],
            "values": [int(m.get("overdue", 0)) for m in monthly], "series_label": "Overdue", "unit": "", "title": "Overdue applications, month by month", "source": "Sakala 2025"}
    viz = {"op": "viz", "title": "Sakala 2025 district performance", "insight": f"Overdue fell {round(100 * (1 - s.get('overdue_last', 0) / max(1, s.get('overdue_first', 1))))}% over the year",
           "cards": [{"type": "race", "title": "Late delivery by district, 2025", "subtitle": "worst 8 of 31", "metric": "late_pct", "unit": "%", "by": "district",
                      "items": [{"label": x["district"], "value": round(x["late_pct"], 2), "aliases": [], "district": x["district"]} for x in d[:8]]},
                     {"type": "line", "title": "Overdue applications, month by month", "subtitle": "Sakala 2025, statewide", "metric": "overdue", "unit": "cases", "by": "month",
                      "items": [{"label": line["labels"][i], "value": v, "aliases": [["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"][i]], "district": ""} for i, v in enumerate(line["values"])]}]}
    return {"say": say, "ui": [{"op": "answer", "html": f"<b>{say}</b>", "q": "Sakala 2025"}, viz]}


async def t_voice_note_officer_cs(sess, args):
    return await t_voice_note(sess, args, "officer")


HANDLERS = {
    "help": t_help, "repeat": t_repeat, "stop": t_stop, "smalltalk": t_smalltalk,
    "switch_profile": t_switch_profile, "go_to": t_go_to, "upload_document": t_upload_document, "ask_knowledge": t_ask_knowledge, "view_as_officer": t_view_as_officer, "identity": t_identity, "forget_conversation": t_forget,
    "confirm_action": t_confirm_action, "cancel_action": t_cancel_action, "set_language": t_set_language, "set_theme": t_set_theme, "tick": t_tick, "reset_demo": t_reset,
    "chat_text": t_citizen_text, "chat_option": t_citizen_option, "confirm": t_confirm, "change": t_change,
    "track": t_track, "apply_service": t_apply, "feedback_yes": t_feedback_yes, "feedback_no": t_feedback_no,
    "appeal": t_appeal, "voice_note_officer": t_voice_note_officer, "updates": t_updates, "reply": t_reply, "later": t_later,
    "login_as": t_login_as, "inbox": t_inbox, "open_case": t_open_case, "next_case": t_next_case,
    "read_case": t_read_case, "accept": t_accept, "ask_info": t_ask_info, "draft_atr": t_draft_atr,
    "resolve": t_resolve, "return_case": t_return_case, "reject": t_reject, "comp_order": t_comp_order,
    "comp_hrms": t_comp_hrms, "voice_note_cs": t_voice_note_cs, "voice_note_citizen": t_voice_note_citizen,
    "summary": t_summary, "ask_data": t_ask_data, "filter_cases": t_filter_cases,
    "officers_attention": t_officers_attention, "nudge": t_nudge, "wednesday_pack": t_wednesday_pack,
    "e4": t_e4, "tracker": t_tracker, "show_chart_as": t_show_chart_as, "voice_note_officer_cs": t_voice_note_officer_cs,
}
