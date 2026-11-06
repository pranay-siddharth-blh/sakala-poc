"""26 Oct 2026 (Pranay's demo): the visual popped in 3-8 times per question and sometimes the wrong one stayed; the orange
'shall I go ahead?' bar stayed after yes / no.

Found in the live relay + browser:
  1. Gemini calls functions repeatedly inside one turn (and the 4 s 'speak' nudge after each result asked it again, so
     it looped: 'I apologize for the repetition'); every call pushed a `viz` at once and the client re-entered the stage
     with the full fly-in each time.
  2. The picture of the LAST call stayed, whatever the question was; the model's find_cases for 'according to their
     input sources' carried no group_by, and the router never saw the words because a function had been called.
  3. tools.execute's yes-path returned the action's result without a {op:confirm, clear} op, so the bar lived on until
     its 120 s timeout; a 'yes' the model answered without calling confirm_action left the action pending.

Fixes (applied by this script, backups in tools/backups/viz26/):
  live.py   : one nudge per turn and it says 'call no function'; identical repeated calls in a turn are answered from the
              first result and not pushed again; tool events carry a sequence number; a plain yes / no with an action
              pending is executed by the relay itself when the model called nothing (and read in the session's language).
  tools.py  : the yes-path clears the bar; route_question reads 'according to / based on / as per / per / by their X',
              'input sources', 'origin' as a breakdown by X (channel / input source / origin = source).
  query.py  : the same reading applied to whatever function the model chose (find_cases / ipgrs_records / statewide_stats
              + the group-by the words asked for), so the picture matches the question on the live path too.
  mitra.js  : a per-turn visual coalescer: a viz waits up to 900 ms for the turn to settle (a newer one replaces it, an
              identical one is ignored), is shown the moment Mitra starts speaking, once per turn with the entrance, and
              any later picture in the same turn crossfades in place; an interrupted answer drops its pending picture.
  stage.js  : Stage.refine(on) = a soft 'refining' shimmer on the title while a further function runs with a picture up.
  mitra.css : the shimmer; assets re-versioned (mitra.js 78, stage.js 67, mitra.css 77).
"""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BK = ROOT / "tools" / "backups" / "viz26"
BK.mkdir(parents=True, exist_ok=True)


def patch(rel: str, edits: list[tuple[str, str]]):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    if not (BK / p.name).exists():
        shutil.copy2(p, BK / p.name)
    for old, new in edits:
        assert s.count(old) == 1, (rel, s.count(old), old[:90])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
    print("patched", rel, len(edits), "edits")


# ---------------------------------------------------------------------------------------------------------- live.py
patch("mitra/server/live.py", [
    ('SPEAK_NUDGE = "(Sakala has returned the result of that request. Tell the person now, briefly, in your own words.)"',
     'SPEAK_NUDGE = "(Sakala has returned the result of that request. Tell the person now, briefly, in your own words. Do not call any function.)"'),
    ('''    await asyncio.sleep(wait)
    if turn.get("resp_at") != at or turn.get("last_out", 0) >= at:
        return                                         # it spoke, or another result superseded this one
    try:
        STATS["nudges"] = STATS.get("nudges", 0) + 1''',
     '''    await asyncio.sleep(wait)
    if turn.get("resp_at") != at or turn.get("last_out", 0) >= at or turn.get("nudged"):
        return                                         # it spoke, another result superseded this one, or it was nudged already this turn
    try:
        turn["nudged"] = True                          # once per turn: a nudge after every result made the model call again, in a loop
        STATS["nudges"] = STATS.get("nudges", 0) + 1'''),
    ('''    turn = {"user": "", "mitra": "", "intent": "", "t0": time.time(), "tool_wait": False}''',
     '''    turn = {"user": "", "mitra": "", "intent": "", "t0": time.time(), "tool_wait": False, "calls": {}, "tool_n": 0, "nudged": False}'''),
    ('''                for fc in m["toolCall"].get("functionCalls", []):
                    name, args = fc.get("name", ""), dict(fc.get("args") or {})
                    args["_text"] = turn["user"]
                    turn["intent"] = name
                    turn["tool_wait"] = True          # Gemini closes the tool-call turn first, then speaks in the next one
                    await ws.send_json({"type": "tool_start", "name": name})
                    cur = store.get_session(sid)
                    before = (cur["profile"], cur["officer"], cur["lang"])
                    try:
                        res = await run_tool(cur, name, args)
                    except Exception as e:
                        res = {"say": "Sakala could not complete that just now.", "ui": [], "error": str(e)[:200]}
                    after = store.get_session(sid)''',
     '''                for fc in m["toolCall"].get("functionCalls", []):
                    name, args = fc.get("name", ""), dict(fc.get("args") or {})
                    args["_text"] = turn["user"]
                    turn["intent"] = name
                    turn["tool_wait"] = True          # Gemini closes the tool-call turn first, then speaks in the next one
                    key = name + json.dumps({k: v for k, v in args.items() if k != "_text"}, sort_keys=True, default=str)
                    if key in turn["calls"]:          # the same call again in this turn: the first answer, no second picture
                        resps.append({"id": fc.get("id"), "name": name, "response": turn["calls"][key]})
                        continue
                    turn["tool_n"] += 1
                    await ws.send_json({"type": "tool_start", "name": name, "n": turn["tool_n"]})
                    cur = store.get_session(sid)
                    before = (cur["profile"], cur["officer"], cur["lang"])
                    try:
                        res = await run_tool(cur, name, args)
                    except Exception as e:
                        res = {"say": "Sakala could not complete that just now.", "ui": [], "error": str(e)[:200]}
                    after = store.get_session(sid)'''),
    ('''                    await ws.send_json({"type": "tool", "name": name, "say": res.get("say", ""), "ui": res.get("ui", []),
                                        "profile": after["profile"], "officer": after["officer"], "lang": after["lang"]})
                    cx = _ctx(after)
                    guard.facts_from([res.get("say", ""), res.get("data"), cx, args], facts)
                    ids.update(guard.spoken_ids(json.dumps([res.get("say", ""), res.get("data"), cx], ensure_ascii=False)))
                    resps.append({"id": fc.get("id"), "name": name,
                                  "response": guard.sanitize({"say": guard.speakable_ids(guard.scrub(res.get("say", ""))), "data": res.get("data"), "context": cx})})''',
     '''                    await ws.send_json({"type": "tool", "name": name, "say": res.get("say", ""), "ui": res.get("ui", []), "n": turn["tool_n"],
                                        "profile": after["profile"], "officer": after["officer"], "lang": after["lang"]})
                    cx = _ctx(after)
                    guard.facts_from([res.get("say", ""), res.get("data"), cx, args], facts)
                    ids.update(guard.spoken_ids(json.dumps([res.get("say", ""), res.get("data"), cx], ensure_ascii=False)))
                    response = guard.sanitize({"say": guard.speakable_ids(guard.scrub(res.get("say", ""))), "data": res.get("data"), "context": cx})
                    turn["calls"][key] = response
                    resps.append({"id": fc.get("id"), "name": name, "response": response})'''),
    ('''                if u and not turn["intent"] and SUBMIT_RX.match(u):''',
     '''                if u and not turn["intent"] and (brain.YES.search(u.lower()) or NO_RX.match(u)):
                    # the harness: an action is waiting for a yes / no (reject, return, resolve, nudge...) and the person answered
                    # without the model calling confirm_action / cancel_action: the relay answers it, and the live voice reads the result
                    try:
                        cur = store.get_session(sid)
                        pend = (cur.get("state") or {}).get("pending_action") if cur else None
                        if pend and not (cur["profile"] == "citizen" and (cur.get("state") or {}).get("flow") in ("confirm", "scrutiny_confirm", "apply_confirm")):
                            which = "cancel_action" if NO_RX.match(u) else "confirm_action"
                            res = await tools.execute(cur, which, {"_text": u})
                            store.save_session(cur)
                            await ws.send_json({"type": "tool", "name": which, "say": res.get("say", ""), "ui": res.get("ui", []), "auto": True})
                            turn["intent"] = which + " (auto)"
                            guard.facts_from([res.get("say", ""), res.get("data")], facts)
                            ids.update(guard.spoken_ids(res.get("say", "")))
                            await server_read(up, await kn_say(res.get("say", ""), cur["lang"]), cur["lang"])
                    except Exception as e:  # noqa: BLE001
                        STATS["last_error"] = f"auto yes/no: {str(e)[:120]}"
                if u and not turn["intent"] and SUBMIT_RX.match(u):'''),
    ('''                turn.update(user="", mitra="", intent="", t0=time.time(), tool_wait=False)''',
     '''                turn.update(user="", mitra="", intent="", t0=time.time(), tool_wait=False, calls={}, tool_n=0, nudged=False)'''),
    ('''SUBMIT_RX = re.compile(r"^\\s*(yes|yeah|yep|ya|sure|ok|okay|confirm|submit( it)?|file it|go ahead|send it|do it|ಹೌದು|ಸರಿ|ಹಾಂ|ಸಲ್ಲಿಸಿ|ಸಲ್ಲಿಸು|ಸಬ್ಮಿಟ್|submit ಮಾಡಿ|file ಮಾಡಿ|ಫೈಲ್ ಮಾಡಿ|ಕಳಿಸಿ|ಕಳುಹಿಸಿ|ಓಕೆ|ಆಯ್ತು)\\b[\\s.!]*$", re.I)''',
     '''SUBMIT_RX = re.compile(r"^\\s*(yes|yeah|yep|ya|sure|ok|okay|confirm|submit( it)?|file it|go ahead|send it|do it|ಹೌದು|ಸರಿ|ಹಾಂ|ಸಲ್ಲಿಸಿ|ಸಲ್ಲಿಸು|ಸಬ್ಮಿಟ್|submit ಮಾಡಿ|file ಮಾಡಿ|ಫೈಲ್ ಮಾಡಿ|ಕಳಿಸಿ|ಕಳುಹಿಸಿ|ಓಕೆ|ಆಯ್ತು)\\b[\\s.!]*$", re.I)
# a plain no to 'shall I go ahead?' (English or Kannada), nothing else in the sentence
NO_RX = re.compile(r"^\\s*(?:no|nope|nah|don'?t|do not|cancel|stop|wait|never ?mind|not now|leave it|hold on|ಬೇಡ|ಬೇಡಿ|ಇಲ್ಲ|ಮಾಡ್ಬೇಡಿ|ಮಾಡಬೇಡಿ)\\b[\\s.,!]*(?:please|thanks|thank you|ದಯವಿಟ್ಟು)?[\\s.!]*$", re.I)'''),
])

# ---------------------------------------------------------------------------------------------------------- tools.py
patch("mitra/server/tools.py", [
    ('''            st.pop("pending_action", None)                   # yes (or the same action asked for again): do it now
            intent, fn = pend["intent"], HANDLERS[pend["intent"]]
            res = await fn(sess, {**pend["args"], "_confirmed": True})''',
     '''            st.pop("pending_action", None)                   # yes (or the same action asked for again): do it now
            intent, fn = pend["intent"], HANDLERS[pend["intent"]]
            res = await fn(sess, {**pend["args"], "_confirmed": True})
            res.setdefault("ui", [])                          # the question bar goes away the moment it is answered
            res["ui"] = [u for u in res["ui"] if u.get("op") != "confirm"] + [{"op": "confirm", "clear": True}]'''),
    ('''def _compare_args0(text: str):
    t = _CHARTPHRASE_RX.sub(" ", (text or "")).strip()
    if not t:
        return None''',
     '''_ACCORDING_RX = re.compile(r"\\b(according to|based on|as per|grouped by|split by|broken (?:down|up) by|sorted by|classified by|categori[sz]ed by)\\b", re.I)
_SOURCE_WORD_RX = re.compile(r"\\binput sources?\\b|\\borigins?\\b|\\bsources? of (?:the )?(?:grievances|cases|complaints|requests)\\b", re.I)
_DIM_FILLER_RX = re.compile(r"\\b(their|its|respective|specific|individual|different|various)\\s+(?=(?:input |)(?:district|taluk|department|dept|service|officer|channel|source|status|level|gram panchayat|gp)s?\\b)", re.I)


def _breakdown_words(t: str) -> str:
    """'according to their specific input sources' -> 'by source': the breakdown wording people use, read as one shape."""
    t = _ACCORDING_RX.sub("by", t)
    t = _SOURCE_WORD_RX.sub("source", t)
    t = _DIM_FILLER_RX.sub("", t)
    t = re.sub(r"\\bwhere (?:they|the (?:cases|grievances|complaints|requests)) (?:come|came) from\\b", "by source", t, flags=re.I)
    return t


def _compare_args0(text: str):
    t = _breakdown_words(_CHARTPHRASE_RX.sub(" ", (text or "")).strip())
    if not t:
        return None'''),
])

# ---------------------------------------------------------------------------------------------------------- query.py
patch("mitra/server/query.py", [
    ('''async def run(s: dict, name: str, args: dict) -> dict:
    said = str((args or {}).get("_text") or "")''',
     '''_GB_WORDS = {"input source": "source", "input sources": "source", "source": "source", "sources": "source", "channel": "source", "channels": "source",
             "origin": "source", "origins": "source", "department": "department", "departments": "department", "dept": "department",
             "district": "district", "districts": "district", "taluk": "taluk", "taluks": "taluk", "service": "service", "services": "service",
             "officer": "officer", "officers": "officer", "status": "status", "statuses": "status", "level": "level", "levels": "level",
             "gram panchayat": "gp", "gram panchayats": "gp", "gp": "gp", "gps": "gp", "month": "month", "months": "month", "day": "day", "days": "day"}
_GB_RX = re.compile(r"\\b(?:according to|based on|as per|grouped by|split by|broken (?:down|up) by|sorted by|classified by|categori[sz]ed by|by|per)\\s+"
                    r"(?:their|the|its|each|every)?\\s*(?:specific |individual |respective |different |various )?"
                    r"(input sources?|sources?|channels?|origins?|departments?|dept|districts?|taluks?|services?|officers?|status(?:es)?|levels?|gram panchayats?|gps?|months?|days?)\\b"
                    r"|\\b(input sources?|sources?|channels?|departments?|districts?|taluks?|services?|officers?|levels?)[- ]wise\\b"
                    r"|\\bwhere (?:they|the (?:cases|grievances|complaints|requests)) (?:come|came) from\\b", re.I)


def group_by_said(said: str) -> str:
    """The breakdown the words asked for ('according to their input sources' -> source), or ''."""
    m = _GB_RX.search(said or "")
    if not m:
        return ""
    w = (m.group(1) or m.group(2) or "source").lower()
    return _GB_WORDS.get(w, _GB_WORDS.get(w.rstrip("s"), ""))


async def run(s: dict, name: str, args: dict) -> dict:
    said = str((args or {}).get("_text") or "")'''),
    ('''    if chart == "map" and (name == "ranking" and (args.get("by") or "district") == "district" or args.get("group_by") == "district"):
        args["limit"] = 31                           # a map shows every district, not a top slice
    tool = FUNCS[name][3]''',
     '''    if chart == "map" and (name == "ranking" and (args.get("by") or "district") == "district" or args.get("group_by") == "district"):
        args["limit"] = 31                           # a map shows every district, not a top slice
    gb = group_by_said(said) if s.get("profile") in ("cs", "officer") else ""
    if gb and name in ("find_cases", "ipgrs_records", "statewide_stats") and str(args.get("group_by") or "").lower() != gb \\
            and not (chart == "map" and gb == "district"):
        # the words asked for a breakdown ('according to their input sources'): that is the picture, whatever the model passed
        if name == "statewide_stats":
            name, args = "find_cases", {}
        args = {k: v for k, v in args.items() if k in ("district", "taluk", "department", "status", "level", "officer", "source", "kind", "escalated", "created_from", "created_to", "text", "viewer")}
        args["group_by"] = gb
        args["limit"] = 31 if gb == "district" else 12
        if chart == "map" and gb != "district":
            chart = "bars"                           # a map cannot show a breakdown by source / department / status
    tool = FUNCS[name][3]'''),
])

# ---------------------------------------------------------------------------------------------------------- stage.js
patch("mitra/web/stage.js", [
    ('''  function show(op, { replay = true, kind = null, morph = false } = {}) {
    if (!op || !(op.cards || []).length) return;
    enter();
    if (morph) ghost();''',
     '''  function show(op, { replay = true, kind = null, morph = false, crossfade = false } = {}) {
    if (!op || !(op.cards || []).length) return;
    enter();
    if (morph || crossfade) ghost();                  // crossfade: a new picture replaces one already up, in place; the reveal still follows her words'''),
    ('''      const el = document.createElement('div'); el.className = `vcard k-${k}${morph ? ' morphing' : ''}`; el.style.animationDelay = `${ci * (morph ? 140 : 420)}ms`;''',
     '''      const el = document.createElement('div'); el.className = `vcard k-${k}${(morph || crossfade) ? ' morphing' : ''}`; el.style.animationDelay = `${ci * ((morph || crossfade) ? 140 : 420)}ms`;'''),
    ('''  // leaving through a dock chip glides back and lights the card it named
  function exitTo(title) { exit(); setTimeout(() => focusCard(title), 650); }''',
     '''  // a further function is running while a picture is up: the title shimmers until the next picture settles
  function refine(on) { const h = $('#stageHost'); if (h) h.classList.toggle('refining', !!on && S.open); }
  // leaving through a dock chip glides back and lights the card it named
  function exitTo(title) { exit(); setTimeout(() => focusCard(title), 650); }'''),
    ('''  return { show, hear, flush, exit, exitTo, focusCard, morph, debug, get open() { return S.open; }, get last() { return S.last; } };''',
     '''  return { show, hear, flush, exit, exitTo, focusCard, morph, refine, debug, get open() { return S.open; }, get last() { return S.last; }, get current() { return S.current; } };'''),
])

# ---------------------------------------------------------------------------------------------------------- mitra.js
patch("mitra/web/mitra.js", [
    ('''function applyUi(ops) {
  // an answer that needs the dashboard (a case, the inbox, a list) brings it back; charts keep the stage
  if (Stage.open && !ops.some(o => o.op === 'viz') && ops.some(o => STAGE_DOWN.has(o.op))) Stage.exit();''',
     '''function applyUi(ops, keepStage = false) {
  // an answer that needs the dashboard (a case, the inbox, a list) brings it back; charts keep the stage
  if (Stage.open && !keepStage && !ops.some(o => o.op === 'viz') && ops.some(o => STAGE_DOWN.has(o.op))) Stage.exit();'''),
    ('''const LV = { ws: null, open: false, ready: false, q: [], nextT: 0, srcs: [], an: null, idleT: null, fallbackUntil: 0,
             inTx: '', outTx: '', bufs: [], pcm: [], lastVoice: 0, playing: false, turnT0: 0, firstAudio: 0, cutTurn: false };''',
     '''const LV = { ws: null, open: false, ready: false, q: [], nextT: 0, srcs: [], an: null, idleT: null, fallbackUntil: 0,
             inTx: '', outTx: '', bufs: [], pcm: [], lastVoice: 0, playing: false, turnT0: 0, firstAudio: 0, cutTurn: false,
             viz: null, vizT: null, vizShown: false, vizN: 0 };
// one picture per turn: the model may call several functions before it speaks (and sometimes the same one again), so a
// picture waits for the turn to settle (a newer one replaces it, the same one is ignored), is shown the moment Mitra starts
// speaking, enters once, and anything later in the same turn crossfades in place instead of flying in again
const VIZ_SETTLE_MS = 900;
function vizHold(op, e) {
  LV.viz = op; clearTimeout(LV.vizT); LV.vizT = null;
  if (LV.outTx || LV.firstAudio || (e && e.auto)) { vizFlush('now'); return; }
  LV.vizT = setTimeout(() => vizFlush('settled'), VIZ_SETTLE_MS);
}
function vizFlush(why) {
  clearTimeout(LV.vizT); LV.vizT = null;
  const op = LV.viz; LV.viz = null; Stage.refine(false);
  if (!op) return;
  const same = Stage.open && Stage.current && JSON.stringify(Stage.current) === JSON.stringify(op);
  if (same) { LV.vizShown = true; return; }
  Stage.show(op, { crossfade: Stage.open });          // a picture already up crossfades in place; the first one makes the entrance
  LV.vizShown = true; LV.vizN++;
  if (window.__vizLog) window.__vizLog.push({ why, title: op.title, t: Math.round(performance.now()) });
}
function vizDrop() { clearTimeout(LV.vizT); LV.vizT = null; LV.viz = null; Stage.refine(false); }'''),
    ('''    case 'tool_start':
      trace('hear', 'done'); trace('think', 'done', e.name.replace(/_/g, ' ')); trace('act', 'run'); setState('thinking', 'Working on it…'); Orb.pulse();
      break;
    case 'tool':
      trace('act', 'done');
      if (e.lang && e.lang !== J.lang) { J.lang = e.lang; localStorage.setItem('jv_lang', J.lang); renderLang(); }
      if (e.profile && e.profile !== J.profile) { Portal.flash(e.profile, { from: J.profile }); J.profile = e.profile; localStorage.setItem('jv_profile', J.profile); renderProfile(); clearPanels(); }
      if (e.officer && e.officer !== J.officer) { J.officer = e.officer; localStorage.setItem('jv_officer', J.officer); renderProfile(); }
      applyUi(e.ui || []);
      break;
    case 'out':
      if (!LV.outTx) { $('#capJv').innerHTML = ''; LV.firstAudio = LV.firstAudio || 0; }
      LV.outTx += e.text; captionLive(e.text); Stage.hear(LV.outTx);
      break;
    case 'interrupted':
      lvCut(); LV.cutTurn = false; ripple();
      break;''',
     '''    case 'tool_start':
      trace('hear', 'done'); trace('think', 'done', e.name.replace(/_/g, ' ')); trace('act', 'run'); setState('thinking', 'Working on it…'); Orb.pulse();
      if ((e.n || 1) > 1 && (Stage.open || LV.viz)) Stage.refine(true);
      break;
    case 'tool': {
      trace('act', 'done');
      if (e.lang && e.lang !== J.lang) { J.lang = e.lang; localStorage.setItem('jv_lang', J.lang); renderLang(); }
      if (e.profile && e.profile !== J.profile) { Portal.flash(e.profile, { from: J.profile }); J.profile = e.profile; localStorage.setItem('jv_profile', J.profile); renderProfile(); clearPanels(); }
      if (e.officer && e.officer !== J.officer) { J.officer = e.officer; localStorage.setItem('jv_officer', J.officer); renderProfile(); }
      const ops = e.ui || [], viz = ops.filter(o => o.op === 'viz');
      applyUi(ops.filter(o => o.op !== 'viz'), viz.length > 0);
      if (viz.length) vizHold(viz[viz.length - 1], e);
      break;
    }
    case 'out':
      if (!LV.outTx) { $('#capJv').innerHTML = ''; LV.firstAudio = LV.firstAudio || 0; }
      vizFlush('speech');
      LV.outTx += e.text; captionLive(e.text); Stage.hear(LV.outTx);
      break;
    case 'interrupted':
      vizDrop(); lvCut(); LV.cutTurn = false; ripple();
      break;'''),
    ('''    case 'turn_complete': {
      trace('speak', 'done');
      const clip = LV.pcm.length ? clipBars(LV.pcm, J.inRate) : null; LV.pcm = [];
      Stage.flush();''',
     '''    case 'turn_complete': {
      trace('speak', 'done');
      const clip = LV.pcm.length ? clipBars(LV.pcm, J.inRate) : null; LV.pcm = [];
      vizFlush('turn'); LV.vizShown = false;
      Stage.flush();'''),
    ('''  if (!LV.playing) { LV.playing = true; J.speaking = true; Orb.setSource(LV.an); setState('speaking', J.name); trace('speak', 'run'); if (!LV.firstAudio) { LV.firstAudio = performance.now(); const ms = LV.firstAudio - LV.turnT0; if (LV.turnT0 && ms > 0 && ms < 20000) latency(ms); } }''',
     '''  if (!LV.playing) { LV.playing = true; J.speaking = true; Orb.setSource(LV.an); setState('speaking', J.name); trace('speak', 'run'); if (!LV.firstAudio) { LV.firstAudio = performance.now(); const ms = LV.firstAudio - LV.turnT0; if (LV.turnT0 && ms > 0 && ms < 20000) latency(ms); vizFlush('audio'); } }'''),
])

# ---------------------------------------------------------------------------------------------------------- css + versions
css = ROOT / "mitra/web/mitra.css"
if not (BK / css.name).exists():
    shutil.copy2(css, BK / css.name)
css.write_text(css.read_text(encoding="utf-8").rstrip("\n") + '''

/* v77 · a further function runs while a picture is up: the title's underline shimmers until the next picture settles */
.stage-host.refining .stage-title::after{background:linear-gradient(90deg,var(--em),rgba(121,227,255,.9),var(--em));background-size:200% 100%;animation:stageRefine 1.1s linear infinite;transform:scaleX(1)}
.stage-host.refining .stage-title::before{animation:refineDot 1.1s ease-in-out infinite}
@keyframes stageRefine{from{background-position:0 0}to{background-position:200% 0}}
@keyframes refineDot{0%,100%{box-shadow:0 0 12px var(--em)}50%{box-shadow:0 0 22px var(--em),0 0 40px rgba(121,227,255,.6)}}
@media (prefers-reduced-motion:reduce){.stage-host.refining .stage-title::after,.stage-host.refining .stage-title::before{animation:none}}
''', encoding="utf-8")
print("patched mitra/web/mitra.css")

patch("mitra/web/index.html", [("mitra.css?v=76", "mitra.css?v=77"), ("stage.js?v=66", "stage.js?v=67"), ("mitra.js?v=77", "mitra.js?v=78")])

# ---------------------------------------------------------------------------------------------------------- fake Live: test directives
patch("mitra/tests/fake_live.py", [
    ('''        ctx = {"profile": prof, "context": state["context"], "options": [], "history": []}
        if text.startswith("(") and "then stop" in text[:200]:   # a line Mitra asks the model to read out (a notification, a document reply): say it, never act on it
            state["speaking"] = asyncio.create_task(speak(text.split(")", 1)[-1].strip()))
            return
        dec = brain.rules(ctx, text)
        name = dec.pop("intent", "smalltalk")''',
     '''        ctx = {"profile": prof, "context": state["context"], "options": [], "history": []}
        if text.startswith("(") and "then stop" in text[:200]:   # a line Mitra asks the model to read out (a notification, a document reply): say it, never act on it
            state["speaking"] = asyncio.create_task(speak(text.split(")", 1)[-1].strip()))
            return
        # test directives (26 Oct): imitate the real model's bad days. '!!repeat N <text>' calls the function N times with
        # slightly different arguments before speaking (what Gemini did in the demo); '!!twice <text>' calls statewide_stats
        # first, then the right function; '!!silent on' makes the NEXT turn call nothing and just say 'Okay.' (the harness must act).
        repeat, twice = 1, False
        if state.pop("silent", False):
            state["speaking"] = asyncio.create_task(speak("Okay."))
            return
        if text.strip() == "!!silent on":
            state["silent"] = True
            state["speaking"] = asyncio.create_task(speak("Okay."))
            return
        mr = re.match(r"!!repeat (\\d+)\\s+", text)
        if mr:
            repeat, text = int(mr.group(1)), text[mr.end():]
        if text.startswith("!!twice "):
            twice, text = True, text[8:]
        dec = brain.rules(ctx, text)
        name = dec.pop("intent", "smalltalk")'''),
    ('''        if name not in fns:
            say = "I can help with Sakala cases and data. What would you like to do?"
        else:
            fut = asyncio.get_event_loop().create_future()
            state["tool"] = fut
            await ws.send(json.dumps({"toolCall": {"functionCalls": [{"id": "fc1", "name": name, "args": dec}]}}))
            await ws.send(json.dumps({"serverContent": {"turnComplete": True}}))     # like Gemini: the tool-call turn ends first
            resp = await asyncio.wait_for(fut, 60)
            r = resp["functionResponses"][0]["response"]
            state["context"] = r.get("context") or state["context"]
            say = r.get("say") or "Done."''',
     '''        if name not in fns:
            say = "I can help with Sakala cases and data. What would you like to do?"
        else:
            calls = ([("statewide_stats", {})] if twice and "statewide_stats" in fns else []) + [(name, {**dec, **({"limit": 8 + i} if i else {})}) for i in range(repeat)]
            say = "Done."
            for i, (nm, ar) in enumerate(calls):
                fut = asyncio.get_event_loop().create_future()
                state["tool"] = fut
                await ws.send(json.dumps({"toolCall": {"functionCalls": [{"id": f"fc{i + 1}", "name": nm, "args": ar}]}}))
                await ws.send(json.dumps({"serverContent": {"turnComplete": True}}))     # like Gemini: the tool-call turn ends first
                resp = await asyncio.wait_for(fut, 60)
                r = resp["functionResponses"][0]["response"]
                state["context"] = r.get("context") or state["context"]
                say = r.get("say") or "Done."
                if len(calls) > 1:
                    await asyncio.sleep(0.25)'''),
])
print("done")
