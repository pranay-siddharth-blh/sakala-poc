"""Sakala on WhatsApp — the conversation engine.

Stateless HTTP in, a list of events out. A real WhatsApp Business webhook would call `handle()` exactly like the
web iPhone simulator does; buttons and list rows map 1:1 to WhatsApp interactive reply buttons and list messages.
Event kinds: msg (bot or citizen bubble) · stage (pipeline panel) · result (routed-officer card) · chips · reset · toast
"""
import base64
import html
import json
import re
import uuid
from datetime import datetime, timedelta

from . import ai, analytics, db, pipeline
from .pipeline import STAGES, DEPT_SHORT
from .routing import gp_list, resolve_place
from .sla import now, officer, create_application, sla_info, chain, event, notify, citizen_verdict, feedback_pending
from . import local_ai

E = html.escape
SAMPLES = [["💧 No drinking water", "ನಮ್ಮ ಗೊರಹಳ್ಳಿ ಗ್ರಾಮದಲ್ಲಿ ಕಳೆದ ಒಂದು ವಾರದಿಂದ ಕುಡಿಯುವ ನೀರು ಬರುತ್ತಿಲ್ಲ"],
           ["📜 Khata delay", "ಪೌತಿ ಖಾತಾ ಮಾಡಲು ಮೂರು ತಿಂಗಳಿಂದ ವಿಳಂಬ ಆಗುತ್ತಿದೆ, ಸರ್ವೇ ನಂಬರ್ 53"],
           ["👵 Pension stopped", "ನಾನು ವಿಧವೆ, ಐದು ತಿಂಗಳಿಂದ ಸಂಧ್ಯಾ ಸುರಕ್ಷಾ ಪಿಂಚಣಿ ಬಂದಿಲ್ಲ"],
           ["🍚 Ration card", "Applied for a new ration card three months ago at Bylakuppe, still not received."],
           ["💡 Street light", "Street light near the bus stand is not working for two weeks."],
           ["⚡ Power cut", "Power cut every evening in our village for one week."]]
VOICE_SAMPLE = "ನಾನು ವಿಧವೆ, ಐದು ತಿಂಗಳಿಂದ ಸಂಧ್ಯಾ ಸುರಕ್ಷಾ ಪಿಂಚಣಿ ಬಂದಿಲ್ಲ. ನಮ್ಮದು ಅತ್ತಿಗೋಡು ಗ್ರಾಮ."
PETITION_SAMPLE = "ಹೊಸ ಪಡಿತರ ಚೀಟಿ ಅರ್ಜಿ ಸಲ್ಲಿಸಿ ಮೂರು ತಿಂಗಳಾದರೂ ಸಿಕ್ಕಿಲ್ಲ. ಬೈಲಕುಪ್ಪೆ ಗ್ರಾಮ. ಮೊಬೈಲ್ 9845012345"
DEMO_GPS = ("Gorahalli", "Chapparadahalli", "Piriyapatna")


class Out:
    def __init__(self, st):
        self.ev, self.st = [], st

    def t(self, en, kn=None):
        return kn if (kn and self.st.get("lang") == "kn") else en

    def bot(self, html_, **kw):
        self.ev.append({"kind": "msg", "me": False, "type": kw.pop("type", "text"), "html": html_, **kw})

    def officer_msg(self, html_, off, case_id, **kw):
        self.ev.append({"kind": "msg", "me": False, "type": "officer", "html": html_, "officer": off["short"], "officerFull": off["name"],
                        "caseId": case_id, **kw})

    def me(self, type_, html_=""):
        self.ev.append({"kind": "msg", "me": True, "type": type_, "html": html_})

    def stage(self, i, note, state="done"):
        self.st.setdefault("stage", {})[str(i)] = {"state": state, "note": note}
        self.ev.append({"kind": "stage", "i": i, "state": state, "note": note})

    def chips(self, items):
        self.ev.append({"kind": "chips", "items": items})

    def reset(self):
        self.st["stage"] = {}
        self.ev.append({"kind": "reset"})


def load(sid):
    r = db.q1("SELECT state FROM chat_sessions WHERE id=?", (sid,))
    return json.loads(r["state"]) if r else {"lang": "en", "flow": "new", "draft": {}, "stage": {}}


def save(sid, st):
    db.run("INSERT INTO chat_sessions(id,state,updated) VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state, updated=excluded.updated",
           (sid, json.dumps(st, default=str), datetime.now().isoformat()))


def log_events(sid, events, user=None):
    if user:
        db.run("INSERT INTO chat_messages(session,t,me,payload) VALUES (?,?,1,?)", (sid, datetime.now().isoformat(), json.dumps(user)))
    for e in events:
        if e["kind"] == "msg":
            db.run("INSERT INTO chat_messages(session,t,me,payload) VALUES (?,?,?,?)", (sid, datetime.now().isoformat(), int(e["me"]), json.dumps(e)))


def handle(sid, req):
    """req: {action?, text?, image_b64?, media_type?, voice_text?}. Returns {session, events}."""
    sid = sid or uuid.uuid4().hex[:12]
    st = load(sid)
    o = Out(st)
    a = (req.get("action") or "").strip()
    try:
        if a == "poll":
            pass                                    # only deliver pending officer messages (below)
        elif a == "start":
            start(o)
        elif a.startswith("lang:"):
            st["lang"] = a[5:]
            menu(o)
        elif a == "menu":
            menu(o)
        elif a == "later":
            o.bot(o.t("No problem. Tap <b>Reply now</b> on the officer's message whenever you are ready, or type TRACK.",
                      "ಸರಿ. ಸಿದ್ಧವಾದಾಗ ಅಧಿಕಾರಿಯ ಸಂದೇಶದಲ್ಲಿ <b>ಉತ್ತರಿಸಿ</b> ಒತ್ತಿ."))
        elif a == "grievance":
            ask_problem(o)
        elif a == "apply":
            apply_menu(o)
        elif a == "track":
            track(o, sid)
        elif a == "officer":
            o.bot(o.t("A helpline officer will call you back within 2 working hours.", "ಸಹಾಯವಾಣಿ ಅಧಿಕಾರಿ 2 ಕೆಲಸದ ಗಂಟೆಗಳಲ್ಲಿ ನಿಮಗೆ ಕರೆ ಮಾಡುತ್ತಾರೆ.")
                  + ' <span class="wa-prod">PRODUCTION PHASE</span>')
            menu(o)
        elif a.startswith("tk:") and a[3:] in gp_taluks():
            ask_gp(o, a[3:])
        elif a.startswith(("gp:", "loc:share")) and not (st.get("draft") or {}).get("u"):
            o.bot(o.t("That request is already finished. What would you like to do next?", "ಆ ಅರ್ಜಿ ಮುಗಿದಿದೆ. ಮುಂದೇನು ಮಾಡಬೇಕು?"))
            menu(o)
        elif a.startswith("gp:"):
            gp, tk = a[3:].split("|")
            st["draft"].update(gp=gp, taluk=tk, village=gp, how="picked from the GP list")
            o.stage(3, f"Village: {gp} GP, {tk}")
            confirm(o)
        elif a == "loc:share":
            v, gp, tk = DEMO_GPS
            o.me("loc", f"{v}, {tk}")
            st["draft"].update(gp=gp, taluk=tk, village=v, how="GPS location shared")
            o.stage(3, f"GPS → {v} village → {gp} GP, {tk}")
            confirm(o)
        elif a.startswith("reply:"):
            start_reply(o, a[6:], sid)
        elif a.startswith("fb:"):
            feedback(o, sid, a[3:])
        elif a.startswith("case:"):
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
                      buttons=[{"label": "🔎 Track", "action": f"case:{cid}"}, {"label": "🏠 Main menu", "action": "menu"}])
        elif a == "appeal":
            appeal(o, sid)
        elif a == "submit":
            submit(o, sid)
        elif a == "change":
            ask_problem(o)
        elif a.startswith("svc:") or a.startswith("apply_now:"):
            apply_start(o, a.split(":", 1)[1])
        elif a.startswith("village:"):
            gp, tk = a[8:].split("|")
            if not (st.get("draft") or {}).get("sakala_key"):
                menu(o)
            else:
                apply_village(o, gp, tk)
        elif a == "doc":
            apply_doc(o, sid)
        elif a == "photo":
            photo(o, sid, req)
        elif a == "voice":
            said, real = req.get("voice_text") or "", bool(req.get("voice_text"))
            if req.get("audio_b64"):
                try:
                    said = ai.transcribe(base64.b64decode(req["audio_b64"]), "kn" if st.get("lang") == "kn" else "en")
                    real = bool(said)
                except Exception:  # noqa: BLE001
                    said = ""
                if not said:
                    o.bot("🎤 I could not hear that clearly. Please try again or type the problem 🙏")
                    o.st.update(flow="grievance", draft={})
                    save(sid, st)
                    log_events(sid, o.ev, user="voice")
                    return {"session": sid, "events": o.ev}
            voice(o, sid, said or VOICE_SAMPLE, real)
        elif req.get("text", "").strip():
            free_text(o, sid, req["text"].strip())
        elif a and a != "poll":
            o.bot("Sorry, I did not understand that option.")
            menu(o)
        if a != "start":
            deliver(o, sid)
    except Exception as e:  # noqa: BLE001 - never leave the citizen without a reply
        o.bot("Sorry, something went wrong on our side. Your message is saved and an officer will look at it. 🙏")
        o.ev.append({"kind": "toast", "h": "Server error", "m": str(e)[:160]})
    save(sid, st)
    log_events(sid, o.ev, user=req.get("text") or a)
    return {"session": sid, "events": o.ev}


# ---------------- flows ----------------
def start(o):
    o.st.update(flow="lang", draft={})
    o.bot("ನಮಸ್ಕಾರ 🙏 <b>Namaskara!</b><br>I am <b>Sakala AI</b>, the Government of Karnataka’s citizen assistant. "
          "Raise a grievance, apply for a service or track a request, right here on WhatsApp. No app to install.")
    o.bot("Which language would you like? · ಯಾವ ಭಾಷೆ?", buttons=[{"label": "English", "action": "lang:en"}, {"label": "ಕನ್ನಡ", "action": "lang:kn"}])


def menu(o):
    o.st["flow"] = "menu"
    o.chips(None)
    o.bot(o.t("How can I help you today? 👇", "ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ? 👇"),
          list={"button": o.t("View options", "ಆಯ್ಕೆಗಳು"), "title": "Sakala AI",
                "rows": [{"t": o.t("📝 Raise a grievance", "📝 ದೂರು ನೀಡಿ"), "d": "Water, roads, pension, land records, ration…", "action": "grievance"},
                         {"t": o.t("📄 Apply for a service", "📄 ಸೇವೆಗೆ ಅರ್ಜಿ"), "d": "Sakala-guaranteed services with a legal deadline", "action": "apply"},
                         {"t": o.t("🔎 Track my request", "🔎 ನನ್ನ ಅರ್ಜಿ ಸ್ಥಿತಿ"), "d": "Status, officer and days left", "action": "track"},
                         {"t": o.t("☎️ Talk to an officer", "☎️ ಅಧಿಕಾರಿಯೊಂದಿಗೆ ಮಾತನಾಡಿ"), "d": "Call-back from the helpline · production", "action": "officer"}]})


def ask_problem(o):
    o.st.update(flow="grievance", draft={})
    o.reset()
    o.bot(o.t("Tell me what is wrong. You can <b>type</b>, send a <b>🎤 voice note</b> or a <b>📷 photo of your petition</b>, in Kannada or English.",
              "ಸಮಸ್ಯೆ ಏನು ಎಂದು ತಿಳಿಸಿ. <b>ಟೈಪ್</b> ಮಾಡಿ, <b>🎤 ಧ್ವನಿ ಸಂದೇಶ</b> ಅಥವಾ <b>📷 ಅರ್ಜಿಯ ಫೋಟೋ</b> ಕಳುಹಿಸಿ."))
    o.chips(SAMPLES)


def free_text(o, sid, text):
    low = text.lower().strip(" !.")
    if o.st.get("flow") == "apply_name":
        return apply_name(o, text)
    if low in ("hi", "hii", "hello", "hey", "menu", "start", "namaskara", "namaste", "ನಮಸ್ಕಾರ", "ನಮಸ್ತೆ"):
        return menu(o)
    if low.startswith(("track", "status", "ಸ್ಥಿತಿ")):
        return track(o, sid)
    if low in ("appeal", "ಮೇಲ್ಮನವಿ"):
        return appeal(o, sid)
    if o.st.get("flow") == "reply" and (o.st.get("draft") or {}).get("case"):
        return send_reply(o, sid, text)
    if o.st.get("flow") in ("ask_place", "ask_gp") and (o.st.get("draft") or {}).get("u"):
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
    grievance(o, sid, text, via="text")


def grievance(o, sid, text, via="text"):
    if o.st.get("flow") != "grievance" or o.st.get("draft"):
        o.reset()
    o.st.update(flow="grievance", draft={})
    o.chips(None)
    o.stage(0, {"text": "Message received on WhatsApp", "voice": "Voice note received on WhatsApp", "photo": "Photo of petition received"}[via])
    o.stage(2, "Reading the request…", "run")
    masked, n, u = pipeline.understand(text)
    o.stage(1, f"{n} personal number{'s' if n != 1 else ''} masked before AI" if n else "Nothing personal to mask")
    eng = pipeline.engine_label(u)
    br = analytics.gsc_bridge(text)
    if br and br.get("found") and db.q1("SELECT 1 FROM cases WHERE id=? AND session=?", (br["case_id"], sid)) is None:
        br.update(found=False)                                    # guardrail 9: someone else's application is never revealed
    if br:
        o.bot(f"🔗 You quoted Sakala application <b>{E(br['gsc'])}</b>. " + (
            f"It is <b>{E(br['status'])}</b> with <b>{E(br['officer'])}</b> ({E(br['service'])}). {E(br['rights'])}<br>" if br["found"] else
            "It is not in the pilot records, so the officer will look it up in Sakala.<br>") + f"<span class=\"wa-muted\">{E(br['advice'])}</span>")
    src = {"text": "whatsapp", "voice": "whatsapp-voice", "photo": "whatsapp-photo"}[via]
    if u["intent"] == "WRONG_DOOR":
        o.stage(2, "Not a grievance", "warn")
        o.bot(f"ℹ️ {E(u['reason'])}")
        return menu(o)
    if u["intent"] == "OUT_OF_SCOPE":
        o.stage(2, f"{u['dept']} · outside pilot", "warn")
        o.bot(f"I understood this as <b>{E(u['dept'])}</b>{(' → <b>' + E(u['line']) + '</b>') if u.get('line') else ''}.<br><br>"
              "This department is outside the 3 pilot departments, so in production it goes straight to that department’s field "
              "officer through iPGRS. <span class=\"wa-prod\">PRODUCTION PHASE</span>")
        return menu(o)
    if u["intent"] == "SERVICE_REQUEST":
        sv = db.q1("SELECT * FROM sakala_services WHERE key=?", (u["sakala_key"],))
        o.stage(2, f"Service request · {sv['name']} (Sakala-notified)")
        o.bot(o.t(f"This is a request for a <b>Sakala-guaranteed service</b>: <b>{E(sv['name'])}</b>.<br>It has a legal deadline of "
                  f"<b>{sv['days']} days</b>. Shall I start the application?",
                  f"ಇದು <b>ಸಕಾಲ ಸೇವೆ</b>: <b>{E(sv['name_kn'])}</b>. ಕಾನೂನುಬದ್ಧ ಅವಧಿ <b>{sv['days']} ದಿನ</b>. ಅರ್ಜಿ ಪ್ರಾರಂಭಿಸಲೇ?"),
              buttons=[{"label": "📄 Apply now", "action": f"apply_now:{sv['key']}"}, {"label": "🏠 Main menu", "action": "menu"}])
        return
    if u["intent"] == "UNCLEAR" and re.match(r"\s*(hi+|hello|hey|namaskara|namaste|good (morning|afternoon|evening)|thanks?|thank you|how are you|ok(ay)?|bye)\b", text, re.I):
        o.stage(2, "Small talk · nothing to file", "warn")             # a greeting is not a request: the menu, never the scrutiny desk
        return menu(o)
    if u["intent"] == "UNCLEAR":
        o.stage(2, "Unclear · no category matches well · asking the citizen", "warn")
        o.st.update(flow="scrutiny_ask", draft={"text": text, "masked": masked, "u": {k: v for k, v in u.items() if k != "similar"}, "src": src})
        o.bot(o.t("I am not sure which office handles this. Shall I send it to a <b>person at the scrutiny desk</b> who will route it, "
                  "or would you like to describe the problem again?",
                  "ಇದು ಯಾವ ಕಚೇರಿಗೆ ಸೇರಿದೆ ಎಂದು ಖಚಿತವಿಲ್ಲ. <b>ಪರಿಶೀಲನಾ ಅಧಿಕಾರಿಗೆ</b> ಕಳುಹಿಸಲೇ, ಅಥವಾ ಸಮಸ್ಯೆಯನ್ನು ಮತ್ತೆ ವಿವರಿಸುವಿರಾ?"),
              buttons=[{"label": o.t("✅ Send to the scrutiny desk", "✅ ಪರಿಶೀಲನಾ ಡೆಸ್ಕ್‌ಗೆ ಕಳುಹಿಸಿ"), "action": "scrutiny:yes"},
                       {"label": o.t("✏️ Describe it again", "✏️ ಮತ್ತೆ ವಿವರಿಸಿ"), "action": "grievance"}])
        return
    o.st["draft"] = {"text": text, "masked": masked, "u": {k: v for k, v in u.items() if k != "similar"}, "src": src}
    o.stage(2, f"{DEPT_SHORT[u['dept_code']]} › {u['service']} · {round(u['conf'] * 100)}% · {eng}")
    o.bot(o.t("Got it 👍 I understand this as:", "ಅರ್ಥವಾಯಿತು 👍 ಇದು:") +
          f"<br><b>{E(dept_name(u['dept_code']))}</b> → {E(u['line'])} → <b>{E(u['service'])}</b><br>"
          f"<span class=\"wa-muted\">“{E(u['grievance'])}” · {round(u['conf'] * 100)}% sure</span>"
          + ("<br>♥ <i>Marked as priority (vulnerable citizen)</i>" if u.get("vulnerable") else ""))
    place = pipeline.locate(text, u)
    _tk = taluk_in_text(text, u.get("taluk_text", ""))
    if place and _tk and place["taluk"] != _tk:          # a taluk named outright beats a same-named village elsewhere in the state
        place = None
    if place:
        o.st["draft"].update(gp=place["gp"], taluk=place["taluk"], village=place["village"], how="village named in the message")
        o.stage(3, f"Found in message: {place['village']} → {place['gp']} GP, {place['taluk']}")
        return confirm(o)
    tk = taluk_in_text(text, u.get("taluk_text", ""))
    if tk:
        from .routing import route
        rt = route(u["service_id"], tk, "")
        if rt and not rt["need_gp"]:                         # taluk-level officer: no village needed
            o.st["draft"].update(gp="", taluk=tk, village="", how="taluk named in the message")
            o.stage(3, f"Taluk found in message: {tk} · taluk-level officer, no village needed")
            return confirm(o)
        o.stage(3, f"Taluk found in message: {tk} · asking for the Gram Panchayat", "run")
        o.bot(o.t(f"I can see this is in <b>{tk}</b> taluk. Each Gram Panchayat has its own officer, so one more detail:",
                  f"ಇದು <b>{tk}</b> ತಾಲ್ಲೂಕಿನಲ್ಲಿದೆ. ಪ್ರತಿ ಗ್ರಾಮ ಪಂಚಾಯಿತಿಗೆ ಪ್ರತ್ಯೇಕ ಅಧಿಕಾರಿ ಇರುವುದರಿಂದ ಇನ್ನೊಂದು ವಿವರ:"))
        return ask_gp(o, tk)
    o.st["flow"] = "ask_place"
    o.stage(3, "Asking for the village / GP", "run")
    o.bot(o.t("Where is this problem? Share your <b>📍 location</b>, choose the taluk, or type the village name.",
              "ಈ ಸಮಸ್ಯೆ ಎಲ್ಲಿದೆ? <b>📍 ಸ್ಥಳ</b> ಹಂಚಿಕೊಳ್ಳಿ, ತಾಲ್ಲೂಕು ಆಯ್ಕೆ ಮಾಡಿ ಅಥವಾ ಗ್ರಾಮದ ಹೆಸರು ಬರೆಯಿರಿ."),
          buttons=[{"label": "📍 Share location", "action": "loc:share", "silent": True},
                   {"label": "Piriyapatna", "action": "tk:Piriyapatna"}, {"label": "Hunsur", "action": "tk:Hunsur"}])


def place_reply(text, taluk_hint=""):
    """Stage 4 (completion): the citizen's answer to "where is it?" resolved the same way on every channel.
    Returns (place or None, taluk named outright or "")."""
    cands = local_ai.place_candidates(text)
    named_tk = taluk_in_text(text)
    place = resolve_place(*cands, taluk_hint=named_tk or taluk_hint) if cands else None
    if place and named_tk and place["taluk"] != named_tk:     # a taluk named outright beats a look-alike village elsewhere (Hunsur != Hunur)
        place = None
    return place, named_tk or ""


def ask_gp(o, tk):
    o.st["flow"] = "ask_gp"
    o.st["draft"]["taluk"] = tk
    rows = [{"t": g, "d": f"{tk} taluk · Gram Panchayat", "action": f"gp:{g}|{tk}"} for g in gp_list(tk)[:10]]
    o.bot(o.t(f"Which village / Gram Panchayat in <b>{tk}</b>? Pick one, or type the village name.",
              f"<b>{tk}</b> ತಾಲ್ಲೂಕಿನ ಯಾವ ಗ್ರಾಮ ಪಂಚಾಯಿತಿ? ಆಯ್ಕೆ ಮಾಡಿ ಅಥವಾ ಗ್ರಾಮದ ಹೆಸರು ಬರೆಯಿರಿ."),
          list={"button": o.t("Choose village", "ಗ್ರಾಮ ಆಯ್ಕೆ"), "title": f"{tk} · Gram Panchayats", "rows": rows})


def confirm(o):
    d = o.st["draft"]
    u = d["u"]
    o.st["flow"] = "confirm"
    o.stage(4, "Waiting for citizen to confirm", "run")
    dup = pipeline.find_duplicate(u, d.get("gp"))
    d["dup"] = dup["id"] if dup else None
    loc = (f"{E(d['village'])} village, " if d.get("village") and d["village"] != d.get("gp") else "") + f"{E(d['gp'])} GP, {E(d['taluk'])} taluk, Mysuru"
    o.bot(f"<div class=\"wa-sum\"><b>{o.t('Please confirm', 'ದಯವಿಟ್ಟು ಖಚಿತಪಡಿಸಿ')}</b><span>Problem</span><p>{E(u['grievance'])}</p>"
          f"<span>Service</span><p>{E(u['service'])} · {E(dept_name(u['dept_code']))}</p><span>Location</span><p>{loc}</p>"
          + (f"<span>Note</span><p>A similar open request exists ({dup['id']}); yours will be linked to it.</p>" if dup else "") + "</div>",
          type="card", buttons=[{"label": o.t("✅ Submit", "✅ ಸಲ್ಲಿಸಿ"), "action": "submit"}, {"label": o.t("✏️ Change", "✏️ ಬದಲಿಸಿ"), "action": "change"}])


def submit(o, sid):
    d = o.st.get("draft") or {}
    if not d.get("u"):
        return menu(o)
    if not d.get("taluk"):
        o.st["flow"] = "ask_place"
        return o.bot(o.t("I still need the location. Share it, choose the taluk, or type the village name.", "ಸ್ಥಳ ಬೇಕು: ಹಂಚಿಕೊಳ್ಳಿ, ತಾಲ್ಲೂಕು ಆಯ್ಕೆ ಮಾಡಿ ಅಥವಾ ಗ್ರಾಮದ ಹೆಸರು ಬರೆಯಿರಿ."),
                     buttons=[{"label": "📍 Share location", "action": "loc:share", "silent": True}, {"label": "Piriyapatna", "action": "tk:Piriyapatna"}, {"label": "Hunsur", "action": "tk:Hunsur"}])
    u = d["u"]
    o.stage(4, "Confirmed by citizen · location valid" + (f" · linked to {d['dup']}" if d.get("dup") else ""))
    o.stage(5, "Finding the exact officer…", "run")
    res = pipeline.create_grievance(d["text"], d["masked"], u, d["src"], d["taluk"], d["gp"], d.get("village", ""), session=sid, dup=d.get("dup"), how=d.get("how", ""))
    if "scrutiny" in res:
        o.stage(5, "Guardrail: category not in the official master → scrutiny desk", "warn")
        o.st.update(flow="done", draft={})
        return o.bot(f"I could not match this to an official category with certainty, so a person at the scrutiny desk will route it. Reference <b>{res['scrutiny']}</b>.")
    o.stage(5, f"{res['officer']['short']}{' (fallback)' if res['fallback'] else ''}")
    o.stage(6, f"{res['days']} days · then {res['next']}")
    o.stage(7, "Visible to officer & Chief Secretary now")
    o.ev.append({"kind": "result", "caseId": res["id"], "officer": res["officer"], "chain": res["chain"], "basis": res["basis"],
                 "title": "Routed to"})
    o.st.update(flow="done", draft={})
    where = f"{E(d['gp'])} Gram Panchayat" if res["officer"]["id"].startswith("pdo_") else f"{E(d['taluk'])} taluk"
    o.bot(f"<div class=\"wa-ok\"><span class=\"wa-okic\">✓</span><b>{o.t('Registered', 'ನೋಂದಣಿಯಾಗಿದೆ')} · {res['id']}</b>"
          f"<p>{o.t('Assigned to', 'ನಿಯೋಜಿಸಲಾಗಿದೆ')} <b>{E(res['officer']['name'])}</b>, the officer responsible for {where}.</p>"
          f"<p>⏱ Action due in <b>{res['days']} days</b>. If not acted on, it moves automatically to <b>{E(res['next'])}</b>.</p>"
          f"<p class=\"wa-muted\">You will get every update here. Reply <b>TRACK</b> anytime.</p></div>",
          type="card", buttons=[{"label": "🔎 Track this", "action": "track"}, {"label": "🏠 Main menu", "action": "menu"}])
    o.ev.append({"kind": "toast", "h": "Routed from WhatsApp", "m": f"{res['id']} → {res['officer']['short']}"})


# ---------------- Sakala service applications ----------------
def apply_menu(o):
    o.st.update(flow="apply", draft={})
    o.reset()
    rows = [{"t": s["name"], "d": f"{dept_name(s['dept_code'])} · {s['days']} days", "action": f"svc:{s['key']}"}
            for s in db.q("SELECT * FROM sakala_services")]
    o.bot(o.t("Which service do you want to apply for? Each one has a <b>legal deadline</b> under the Sakala Act.",
              "ಯಾವ ಸೇವೆಗೆ ಅರ್ಜಿ? ಪ್ರತಿಯೊಂದಕ್ಕೂ ಸಕಾಲ ಕಾಯ್ದೆಯಡಿ <b>ಕಾನೂನುಬದ್ಧ ಗಡುವು</b> ಇದೆ."),
          list={"button": o.t("Choose service", "ಸೇವೆ ಆಯ್ಕೆ"), "title": "Sakala services", "rows": rows})


def apply_start(o, key):
    sv = db.q1("SELECT * FROM sakala_services WHERE key=?", (key,))
    o.reset()
    o.st.update(flow="apply_name", draft={"sakala_key": key})
    o.stage(0, f"Service application: {sv['name']}")
    o.stage(1, "Personal data protected")
    o.stage(2, f"{sv['name']} · Sakala-notified")
    o.stage(3, "Checklist: " + ", ".join(json.loads(sv["checklist"])).lower(), "run")
    items = json.loads(sv["checklist"])
    o.bot(f"To apply for <b>{E(sv['name'])}</b> I need {len(items)} things:<br>" + "<br>".join(f"{i + 1}️⃣ {E(x)}" for i, x in enumerate(items))
          + f"<br><br>What is the <b>{E(items[0].lower())}</b>?")
    o.chips([["Lakshmi K", "Lakshmi K"]])


def apply_name(o, name):
    o.st["draft"]["name"] = name
    o.st["flow"] = "apply_village"
    o.chips(None)
    rows = [{"t": g, "d": "Piriyapatna taluk", "action": f"village:{g}|Piriyapatna"} for g in gp_list("Piriyapatna")[:6]] + \
           [{"t": g, "d": "Hunsur taluk", "action": f"village:{g}|Hunsur"} for g in gp_list("Hunsur")[:4]]
    o.bot(f"Thank you. Which village is <b>{E(name)}</b> from?", list={"button": "Choose village", "title": "Villages · pilot taluks", "rows": rows})


def apply_village(o, gp, tk):
    o.st["draft"].update(gp=gp, taluk=tk)
    o.st["flow"] = "apply_doc"
    o.bot("Now send a <b>📷 photo</b> of the document (use the camera button, or tap below).",
          buttons=[{"label": "📷 Send document photo", "action": "doc", "silent": True}])


def apply_doc(o, sid, doc_text=None):
    d = o.st.get("draft") or {}
    if not d.get("sakala_key") or not d.get("gp"):
        return menu(o)
    if doc_text is None:
        o.me("image", "Ration card")
    o.stage(3, "Document received · reading…", "run")
    o.bot(f"📄 I read the document:<br><span class=\"wa-muted\">Card type: BPL ration card · Card no: [ID-MASKED] · Village: {E(d['gp'])}</span>")
    o.stage(3, "All details complete")
    o.stage(4, "Validated · no duplicate application")
    cid = create_application(d["sakala_key"], d.get("name", "Applicant"), d["gp"], d["taluk"], "whatsapp", session=sid,
                             doc_note="document photo received on WhatsApp")
    c = db.q1("SELECT * FROM cases WHERE id=?", (cid,))
    sk = json.loads(c["sakala"])
    do, co, aa = officer(sk["DO"]), officer(sk["CO"]), officer(sk["AA"])
    due = datetime.fromisoformat(sk["complete"]) + timedelta(days=sk["dueDays"])
    o.stage(5, f"Designated Officer: {do['short']}")
    o.stage(6, f"Legal deadline {due:%d %b %Y} ({sk['dueDays']} days)")
    o.stage(7, "On officer’s Sakala list now")
    o.ev.append({"kind": "result", "caseId": cid, "officer": {"id": do["id"], "name": do["name"], "short": do["short"], "level": do["level"]},
                 "chain": [{"lv": "Designated", "short": do["short"]}, {"lv": "Competent", "short": co["short"]}, {"lv": "Appellate", "short": aa["short"]}],
                 "basis": f"Sakala application {cid}", "title": f"Sakala application {cid}"})
    o.st.update(flow="done", draft={})
    o.bot(f"<div class=\"wa-ok\"><span class=\"wa-okic\">✓</span><b>Application accepted</b><p>Sakala No. <b>{cid}</b><br>{E(sk['service'])} · {E(sk['applicant'])}</p>"
          f"<p>⏱ Guaranteed by <b>{due:%d %b %Y}</b> ({sk['dueDays']} days, Sakala Act). Designated Officer: <b>{E(do['short'])}</b>.</p>"
          "<p class=\"wa-muted\">If it is late, you can appeal and claim ₹20 per day (up to ₹500).</p></div>",
          type="card", buttons=[{"label": "🔎 Track", "action": "track"}, {"label": "🏠 Main menu", "action": "menu"}])
    o.ev.append({"kind": "toast", "h": "Sakala application", "m": f"{cid} → {do['short']}"})


# ---------------- media ----------------
def photo(o, sid, req):
    if o.st.get("flow") == "reply" and (o.st.get("draft") or {}).get("case"):
        o.me("image", "")
        return send_reply(o, sid, "Photo of the site attached", photo=True)
    if o.st.get("flow") in ("apply_doc", "apply_village") and o.st.get("draft", {}).get("gp"):
        return apply_doc(o, sid)
    o.me("image", "")
    text = ""
    if req.get("image_b64"):
        if ai.status()["llm"]:
            try:
                text = ai.read_petition(req["image_b64"], req.get("media_type", "image/png"))
            except Exception:  # noqa: BLE001
                text = ""
        if not text:
            o.bot(o.t("📷 Photo received, but it does not look like a readable petition or document, so I will not guess. Please type the problem in one line 🙏",
                      "📷 ಫೋಟೋ ಓದಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಸಮಸ್ಯೆಯನ್ನು ಟೈಪ್ ಮಾಡಿ 🙏"))
            o.st.update(flow="grievance", draft={})
            return
    else:
        text = PETITION_SAMPLE
    o.bot(f"📷 I read your petition: <i>“{E(pipeline.mask(text)[0])}”</i>")
    grievance(o, sid, text, via="photo")


def voice(o, sid, said, real):
    o.bot(f"🎤 I heard: <i>“{E(said)}”</i>" + ("" if real else ' <span class="wa-prod">SAMPLE VOICE NOTE</span>'))
    grievance(o, sid, said, via="voice")


def _status_line(o, c):
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
        rungs.append(f"<span class=\"done\">{E(levels[i])} · {E(nm)}</span>")
    for j, x in enumerate(above):
        rungs.append(f"<span class=\"{'cur' if j == 0 else ''}\">{E(x['level'])} · {E(x['short'])}</span>")
    return "<div class=\"wa-lad\">" + "<i>→</i>".join(rungs) + "</div>"


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
        rows.append(f"<div class=\"wa-trk\"><b>{c['id']}</b><span>{E(c['service'] or 'Scrutiny desk')}</span>"
                    f"<span>With {E(off['short'])} · {c['level']}</span><span class=\"{cls}\">{st}</span></div>")
        items.append({"t": c["id"], "d": f"{c['service'] or 'Scrutiny desk'} · {c['status']}", "action": f"case:{c['id']}"})
    pend = [c for c in mine if feedback_pending(c)]
    o.bot(o.t("<b>Your requests · live</b>", "<b>ನಿಮ್ಮ ಅರ್ಜಿಗಳು · ಲೈವ್</b>") + "".join(rows)
          + f"<p class=\"wa-muted\">{o.t('Open a request for the officer ladder, days left and your options.', 'ಅಧಿಕಾರಿ ಹಂತಗಳು ಮತ್ತು ಆಯ್ಕೆಗಳಿಗೆ ಅರ್ಜಿ ತೆರೆಯಿರಿ.')}</p>",
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
    clock = ("" if c["status"] in ("Resolved", "Rejected") or not s["legal"] else          # grievances: the status line already counts the days
             f"<span>⏱ {'Sakala legal deadline' if s['legal'] else 'Action due'}: {s['total']} days · "
             + (f"<b class=\"bad\">{-s['left']} overdue</b>" if s["left"] < 0 else f"<b>{s['left']} left</b>") + "</span>")
    html = (f"<div class=\"wa-trk\"><b>{cid}</b><span>{E(c['service'] or 'Scrutiny desk')}</span>"
            f"<span>{o.t('With', 'ಇವರ ಬಳಿ')} <b>{E(off.get('name') or off['short'])}</b> · {c['level']}</span>"
            f"{_ladder_html(c)}{clock}<span class=\"{cls}\">{st}</span>"
            + (f"<div class=\"last\">{o.t('Last', 'ಕೊನೆಯದು')}: {E(last.get('what', ''))} · {_when(last.get('t', ''))}</div>" if last else "")
            + (f"<div class=\"last\">{o.t('Officer’s report', 'ಅಧಿಕಾರಿಯ ವರದಿ')}: “{E(c['atr'])}”</div>" if c.get("atr") and c["status"] == "Resolved" else "")
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


# ---------------- officer → citizen (two-way WhatsApp) ----------------
KIND_TEXT = {
    "accepted": ("✅ <b>{off}</b> has accepted your request <b>{cid}</b> and started working on it.",
                 "✅ <b>{off}</b> ನಿಮ್ಮ ಅರ್ಜಿ <b>{cid}</b> ಸ್ವೀಕರಿಸಿ ಕೆಲಸ ಪ್ರಾರಂಭಿಸಿದ್ದಾರೆ."),
    "info": ("📩 <b>{off}</b> needs more information on <b>{cid}</b>:<br><i>“{text}”</i>",
             "📩 <b>{off}</b> ಅವರಿಗೆ <b>{cid}</b> ಬಗ್ಗೆ ಹೆಚ್ಚಿನ ಮಾಹಿತಿ ಬೇಕು:<br><i>“{text}”</i>"),
    "resolved": ("🎉 <b>{off}</b> has marked <b>{cid}</b> as resolved.<br><span class=\"wa-muted\">Action taken: “{text}”</span><br><br>Was your problem actually solved?",
                 "🎉 <b>{off}</b> <b>{cid}</b> ಅನ್ನು ಪರಿಹರಿಸಲಾಗಿದೆ ಎಂದು ಗುರುತಿಸಿದ್ದಾರೆ.<br><span class=\"wa-muted\">ಕೈಗೊಂಡ ಕ್ರಮ: “{text}”</span><br><br>ನಿಮ್ಮ ಸಮಸ್ಯೆ ನಿಜವಾಗಿ ಬಗೆಹರಿಯಿತೇ?"),
    "rejected": ("❌ <b>{off}</b> could not accept <b>{cid}</b>.<br><i>Reason: {text}</i><br><span class=\"wa-muted\">Your right: you may appeal to <b>{up}</b> within 30 days. Reply <b>APPEAL</b> and I will send it up now.</span>",
                 "❌ <b>{off}</b> <b>{cid}</b> ಅನ್ನು ಸ್ವೀಕರಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ.<br><i>ಕಾರಣ: {text}</i><br><span class=\"wa-muted\">ನಿಮ್ಮ ಹಕ್ಕು: 30 ದಿನಗಳೊಳಗೆ <b>{up}</b> ಅವರಿಗೆ ಮೇಲ್ಮನವಿ ಸಲ್ಲಿಸಬಹುದು. <b>APPEAL</b> ಎಂದು ಉತ್ತರಿಸಿ.</span>"),
    "returned": ("↩️ <b>{cid}</b> is being re-checked by the scrutiny desk to find the right office. You will hear from us here.",
                 "↩️ <b>{cid}</b> ಸರಿಯಾದ ಕಚೇರಿ ಗುರುತಿಸಲು ಪರಿಶೀಲನಾ ಡೆಸ್ಕ್‌ನಲ್ಲಿ ಮರುಪರಿಶೀಲನೆಯಾಗುತ್ತಿದೆ."),
    "escalated": ("⏫ <b>{cid}</b> was not acted on in time, so it has moved up to <b>{off}</b> automatically. <span class=\"wa-muted\">({text})</span>",
                  "⏫ <b>{cid}</b> ಸಮಯಕ್ಕೆ ಕ್ರಮವಾಗದ ಕಾರಣ ಸ್ವಯಂಚಾಲಿತವಾಗಿ <b>{off}</b> ಅವರಿಗೆ ವರ್ಗಾಯಿಸಲಾಗಿದೆ."),
    "transferred": ("↪️ <b>{cid}</b> was outside the jurisdiction of {text}, so it has been sent straight to <b>{off}</b>, who now holds it. You will hear from them here.",
                    "↪️ <b>{cid}</b> {text} ಅವರ ವ್ಯಾಪ್ತಿಗೆ ಬರದ ಕಾರಣ ನೇರವಾಗಿ <b>{off}</b> ಅವರಿಗೆ ಕಳುಹಿಸಲಾಗಿದೆ. ಅವರಿಂದ ಇಲ್ಲೇ ಮಾಹಿತಿ ಬರುತ್ತದೆ."),
    "routed": ("📍 <b>{cid}</b> has been checked by the scrutiny desk and is now with <b>{off}</b>. {text}",
               "📍 <b>{cid}</b> ಪರಿಶೀಲನಾ ಡೆಸ್ಕ್ ಪರಿಶೀಲಿಸಿ ಈಗ <b>{off}</b> ಅವರಿಗೆ ವಹಿಸಲಾಗಿದೆ. {text}"),
    "compensation": ("💰 Sakala compensation of <b>₹{text}</b> has been ordered for the delay on <b>{cid}</b> (₹20 per day, Sakala Act s.9).",
                     "💰 <b>{cid}</b> ವಿಳಂಬಕ್ಕೆ ಸಕಾಲ ಪರಿಹಾರ <b>₹{text}</b> ಆದೇಶಿಸಲಾಗಿದೆ (ದಿನಕ್ಕೆ ₹20)."),
}


def deliver(o, sid):
    """Push every undelivered officer message for this chat as an incoming WhatsApp message."""
    rows = db.q("SELECT * FROM citizen_msgs WHERE session=? AND delivered=0 ORDER BY id", (sid,))
    for m in rows:
        off = officer(m["officer_id"]) or {"short": "Sakala desk", "name": "Sakala desk"}
        en, kn = KIND_TEXT.get(m["kind"], ("{off}: {text}", "{off}: {text}"))
        text = m["text"] or ""
        if o.st.get("lang") == "kn" and m["kind"] in ("info", "rejected", "resolved") and text and ai.status()["llm"]:
            try:
                text = ai.to_kannada(text)
            except Exception:  # noqa: BLE001 - keep the English text
                pass
        case = db.q1("SELECT * FROM cases WHERE id=?", (m["case_id"],)) or {}
        upo = officer((officer(case.get("owner")) or {}).get("up_id") or "") if case else None
        if case.get("kind") == "APPLICATION" and case.get("sakala"):
            upo = officer(json.loads(case["sakala"]).get("CO", "")) or upo       # Sakala appeal goes to the Competent Officer
        html = o.t(en, kn).format(off=E(off["short"]), cid=m["case_id"], text=E(text), up=E((upo or {}).get("short", "the senior officer")))
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


def own_case(o, sid, cid):
    """Guardrail 9: a chat can only touch the cases it filed."""
    c = db.q1("SELECT * FROM cases WHERE id=? AND session=?", (cid, sid))
    if not c:
        o.bot(o.t("That request was not filed from this chat, so I cannot open it here. Reply TRACK for your own requests.",
                  "ಆ ಅರ್ಜಿ ಈ ಚಾಟ್‌ನಿಂದ ಸಲ್ಲಿಸಿಲ್ಲ. ನಿಮ್ಮ ಅರ್ಜಿಗಳಿಗೆ TRACK ಎಂದು ಉತ್ತರಿಸಿ."))
    return c


def start_reply(o, cid, sid=None):
    c = own_case(o, sid, cid) if sid else db.q1("SELECT * FROM cases WHERE id=?", (cid,))
    if not c:
        return
    o.st.update(flow="reply", draft={"case": cid})
    o.chips(None)
    o.bot(o.t(f"Type your reply to <b>{E(officer(c['owner'])['short'])}</b>, or send a <b>📷 photo</b> of the problem. It goes straight into the officer's file.",
              f"<b>{E(officer(c['owner'])['short'])}</b> ಅವರಿಗೆ ಉತ್ತರ ಟೈಪ್ ಮಾಡಿ ಅಥವಾ <b>📷 ಫೋಟೋ</b> ಕಳುಹಿಸಿ."))


def send_reply(o, sid, text, photo=False):
    cid = o.st["draft"]["case"]
    c = own_case(o, sid, cid)
    if not c:
        o.st.update(flow="menu", draft={})
        return
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


def appeal(o, sid):
    """Guardrail 16: a rejected citizen can appeal to the senior officer (grievance ladder) or the Competent Officer (Sakala)."""
    c = db.q1("SELECT * FROM cases WHERE session=? AND status='Rejected' ORDER BY created DESC LIMIT 1", (sid,))
    if not c:
        return o.bot(o.t("You have no rejected request to appeal. Reply TRACK to see your requests.", "ಮೇಲ್ಮನವಿ ಸಲ್ಲಿಸಲು ತಿರಸ್ಕೃತ ಅರ್ಜಿ ಇಲ್ಲ."))
    cur = officer(c["owner"])
    up = officer(json.loads(c["sakala"])["CO"]) if c["kind"] == "APPLICATION" else officer(cur["up_id"]) if cur and cur["up_id"] else None
    if not up:
        return o.bot(o.t("This request is already at the highest level; the appeal has been noted for the Chief Secretary's review.", "ಈ ಅರ್ಜಿ ಈಗಾಗಲೇ ಅತ್ಯುನ್ನತ ಹಂತದಲ್ಲಿದೆ."))
    db.run("UPDATE cases SET owner=?, level=?, level_since=?, status='Pending' WHERE id=?", (up["id"], up["level"], now().isoformat(), c["id"]))
    event(c["id"], "Citizen (WhatsApp)", f"Appealed to {up['short']}", "#6d4ce6", "Citizen used the appeal right after a rejection")
    notify(up["id"], f"Appeal on {c['id']} from the citizen (rejected by {cur['short'] if cur else '-'})")
    o.bot(o.t(f"✓ Your appeal on <b>{c['id']}</b> has been sent to <b>{E(up['short'])}</b>. They must look at it afresh; you will hear from us here.",
              f"✓ <b>{c['id']}</b> ಮೇಲ್ಮನವಿಯನ್ನು <b>{E(up['short'])}</b> ಅವರಿಗೆ ಕಳುಹಿಸಲಾಗಿದೆ."))


def feedback(o, sid, arg):
    cid, ans = arg.rsplit(":", 1)
    c = own_case(o, sid, cid)
    if not c:
        return
    if not feedback_pending(c):
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
    o.st.update(flow="menu", draft={})


TALUK_WORDS = {"Piriyapatna": ("piriyapatna", "periyapatna", "piriyapattana", "ಪಿರಿಯಾಪಟ್ಟಣ"), "Hunsur": ("hunsur", "hunasuru", "hunsuru", "ಹುಣಸೂರು"),
               "Mysuru": ("mysuru taluk", "mysore taluk", "ಮೈಸೂರು ತಾಲ್ಲೂಕು")}


_TALUK_INDEX = {}


def _taluk_index():
    """Every taluk in the gazetteer (statewide) plus the known alternate spellings."""
    if not _TALUK_INDEX:
        for tk in gp_taluks():
            if tk:
                _TALUK_INDEX[tk] = {tk.lower()}
        for tk, words in TALUK_WORDS.items():
            _TALUK_INDEX.setdefault(tk, {tk.lower()}).update(words)
        _TALUK_INDEX.get("Mysuru", set()).discard("mysuru")       # "Mysuru" alone is the district; the taluk needs "Mysuru taluk"
    return _TALUK_INDEX


def taluk_in_text(text, hint=""):
    t = (text or "").lower() + " " + (hint or "").lower()
    t_ns = re.sub(r"\s+", "", t)                 # speech-to-text may split a Kannada name: "ಪಿರಿಯಾ ಪಟ್ಟಣ"
    best, best_len = "", 0
    for tk, words in _taluk_index().items():
        for w in words:
            hit = (w in t or w in t_ns) if re.search("[ಀ-೿]", w) else re.search(r"\b" + re.escape(w) + r"\b", t)
            if hit and len(w) > best_len:
                best, best_len = tk, len(w)
    if not best and re.search("[ಀ-೿]", text or ""):
        best = _taluk_from_kannada(text)
    return best


def _taluk_from_kannada(text):
    """Any taluk in the state written in Kannada script: transliterate the words (and pairs of words, and the
    words without a case ending) and compare them with the gazetteer's taluk names."""
    import difflib
    from .local_ai import kn_to_latin
    toks = re.findall(r"[ಀ-೿]{2,}", text or "")
    toks = toks + [a + b for a, b in zip(toks, toks[1:])]
    toks = toks + [re.sub(r"(ಯಲ್ಲಿ|ದಲ್ಲಿ|ನಲ್ಲಿ|ರಲ್ಲಿ|ಲ್ಲಿ|ಯಿಂದ|ದಿಂದ|ಕ್ಕೆ|ಗೆ|ದ|ನ|ಯ)$", "", x) for x in toks]
    cands = {_phon(kn_to_latin(x), kn=True) for x in toks}
    cands = {c for c in cands if len(c) >= 4}
    taluk_said = bool(re.search(r"ತಾಲೂಕು|ತಾಲ್ಲೂಕು|taluk", text or "", re.I))
    best, best_s = "", 0.0
    for tk in _taluk_index():
        if tk == "Mysuru" and not taluk_said:      # "ಮೈಸೂರು" alone is the district (same rule as the English path)
            continue
        n = _phon(tk)
        for c in cands:
            if abs(len(c) - len(n)) > 2:
                continue
            s = 1.0 if c == n else difflib.SequenceMatcher(None, c, n).ratio()
            if s > best_s:
                best, best_s = tk, s
    return best if best_s >= 0.88 else ""


def _phon(s, kn=False):
    """A rough phonetic key, applied to both sides, so Kannada transliteration and the English gazetteer spelling
    meet: long vowels collapsed, aspirates and doubled consonants dropped, final vowels dropped."""
    s = re.sub(r"[^a-z]", "", (s or "").lower())
    for a, b in (("aa", "a"), ("ee", "i"), ("ii", "i"), ("oo", "u"), ("uu", "u"), ("ai", "y"), ("w", "v"), ("z", "j")):
        s = s.replace(a, b)
    s = re.sub(r"([kgcjtdpbs])h", r"\1", s)
    if kn:                                          # the Kannada nasal sign before a consonant: ಖಂಡಿ "khamdi" = "khandi"
        s = re.sub(r"m(?=[kgcjtdn])", "n", s)
    s = re.sub(r"(.)\1+", r"\1", s)
    return re.sub(r"[aeiou]+$", "", s)


def gp_taluks():
    return {r["taluk"] for r in db.q("SELECT DISTINCT taluk FROM gazetteer")}


def dept_name(code):
    r = db.q1("SELECT name FROM departments WHERE code=?", (code,))
    return {"REV": "Revenue Department", "RDPR": "Rural Development & Panchayat Raj", "FOOD": "Food & Civil Supplies"}.get(code, r["name"] if r else code)
