"""27 Oct 2026 (Pranay, after the demo): (1) 'show me all the grievances that are auto-escalated' drew the whole Karnataka
board; (2) on the stage board the mic / stop buttons could not be clicked and looked washed out; (3) mute stopped everything.

Found:
  1. query.run's "show me all / everything" -> board rule ran even when the words (or the model's arguments) carried a
     filter: escalated, overdue, vulnerable, due today, a level ... The router had already chosen find_cases escalated=true.
  2. The composer is inside `.stage` (position:relative; z-index:2), its own stacking context, so its z-index 46 never
     beat the stage host (z 40): the dock chips bar (#dockChips, full width) sat on top of the mic and stop buttons and the
     dock's gradient shaded them. elementFromPoint over the mic returned #dockChips.
  3. setMuted() closed the live session (liveClose('muted')), so the answer in progress died with it.

Fixes (applied by this script, backups in tools/backups/viz26/):
  query.py : the board rule yields to a filter in the words or the arguments (the "how is X doing" form keeps the board).
  stage.js : the composer is moved to <body> while the stage is up and put back on exit (above the dock, clickable, unshaded);
  mitra.css: composer above the stage host; the dock only catches clicks on its chips; the chips bar never crosses the
             composer; on boards and the map the composer sits in a glass pill.
  mitra.js : mute = the microphone track off, nothing else: the live session stays open, the answer keeps playing, typed
             text still goes to Live; Stop is the only thing that cuts her off. State / pill labels say 'Muted · the answer
             still plays'. Assets mitra.js 79, stage.js 68, mitra.css 78.
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BK = ROOT / "tools" / "backups" / "viz26"
BK.mkdir(parents=True, exist_ok=True)


def patch(rel: str, edits: list[tuple[str, str]]):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    if not (BK / (p.name + ".2")).exists():
        shutil.copy2(p, BK / (p.name + ".2"))
    for old, new in edits:
        assert s.count(old) == 1, (rel, s.count(old), old[:90])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
    print("patched", rel, len(edits), "edits")


# ---------------------------------------------------------------------------------------------------------- query.py
patch("mitra/server/query.py", [
    ('''def group_by_said(said: str) -> str:''',
     '''_FILTER_SAID_RX = re.compile(r"\\b(auto[- ]?escalat\\w*|escalat\\w*|overdue|delayed|vulnerable|due (?:today|tomorrow|soon)|within \\d+ days|\\d+ days? (?:left|remaining)|"
                             r"resolved|rejected|scrutiny|re-?opened|appealed|at l[123]|level [123]|with l[123])\\b", re.I)


def filter_said(said: str) -> bool:
    """The words carry a filter (escalated, overdue, vulnerable, due today, a level...): a slice, never the whole board."""
    return bool(_FILTER_SAID_RX.search(said or ""))


def group_by_said(said: str) -> str:'''),
    ('''    if s.get("profile") == "cs" and name in ("ipgrs_records", "find_cases", "officer_profile", "place_info", "statewide_stats") \\
            and (board.DASH_RX.search(said) or board.KN_DASH_RX.search(said)) and not (board.COUNTQ_RX.search(said) or board.KN_COUNT_RX.search(said)) \\
            and not group_by_said(said):                      # 'show me all the grievances according to their sources' is a breakdown, not the board''',
     '''    dash_m = board.DASH_RX.search(said) or board.KN_DASH_RX.search(said)
    dash_how = bool(dash_m) and dash_m.group(0).lower().startswith("how")       # 'how is X doing' is always the board
    sliced = bool(group_by_said(said) or filter_said(said) or any(k in args for k in ("escalated", "status", "days_left", "level")))
    if s.get("profile") == "cs" and name in ("ipgrs_records", "find_cases", "officer_profile", "place_info", "statewide_stats") \\
            and dash_m and not (board.COUNTQ_RX.search(said) or board.KN_COUNT_RX.search(said)) \\
            and (dash_how or not sliced):                     # 'show me all the escalated / overdue / by-source cases' is a slice, not the board'''),
])

# ---------------------------------------------------------------------------------------------------------- stage.js
patch("mitra/web/stage.js", [
    ('''  function enter() {
    if (S.open) return;
    host(); S.open = true;''',
     '''  // the composer leaves the dashboard's stacking context while the stage is up (`.stage` has its own z-index, so the fixed
  // composer could never rise above the stage host and its dock covered the mic and stop buttons); it goes back on exit
  function liftComposer() {
    const comp = $('.composer');
    if (!comp || S.compHome || comp.parentNode === document.body) return;
    S.compHome = document.createComment('composer'); comp.parentNode.insertBefore(S.compHome, comp); document.body.appendChild(comp);
  }
  function homeComposer() {
    if (!S.compHome) return;
    const comp = $('.composer');
    if (comp && S.compHome.parentNode) S.compHome.parentNode.insertBefore(comp, S.compHome);
    S.compHome.remove(); S.compHome = null;
  }
  function enter() {
    if (S.open) return;
    host(); S.open = true; liftComposer();'''),
    ('''    const done = () => { S.exitT = null; S.exitDone = null; document.body.classList.remove('stage-on', 'board-on');''',
     '''    const done = () => { S.exitT = null; S.exitDone = null; homeComposer(); document.body.classList.remove('stage-on', 'board-on');'''),
])

# ---------------------------------------------------------------------------------------------------------- mitra.js
patch("mitra/web/mitra.js", [
    ('''function setMuted(on, { quiet = false } = {}) {
  J.muted = !!on; applyTrack();
  if (J.muted && LV.open) liveClose('muted');
  setTimeout(modePill, 0);
  document.body.classList.toggle('muted', J.muted);
  mic.classList.toggle('muted', J.muted);
  mic.dataset.tip = J.muted ? 'Muted · tap to unmute · hold to talk anyway' : 'Tap to mute · hold to talk (or hold Space)';
  $('#wakeLabel').textContent = J.muted ? 'Muted' : `“Hey ${J.name}”`;
  if (J.muted) {
    cancelCapture(); scanDrop();
    if (J.wakeRec) { try { J.wakeRec.onend = null; J.wakeRec.abort(); } catch (e) { } J.wakeRec = null; }
    if (!J.speaking && !J.busy) setState('muted', 'Tap the mic to unmute');
  } else {
    if (J.wakeOn) startWake();
    if (!J.speaking && !J.busy) setState('idle', `Say “Hey ${J.name}”`);
  }
  if (!quiet) { chime(!J.muted); toast(J.muted ? 'Microphone muted' : 'Listening again', J.muted ? `${J.name} will not hear anything until you unmute. Hold the mic to talk anyway.` : `Say “Hey ${J.name}” any time.`); }
}''',
     '''// mute is the microphone only: the track is switched off, the live session stays open, an answer in progress keeps
// playing and typed text still goes to Live. Only Stop cuts her off.
const MUTED_TEXT = 'Muted · the answer still plays';
function setMuted(on, { quiet = false } = {}) {
  J.muted = !!on; applyTrack();
  setTimeout(modePill, 0);
  document.body.classList.toggle('muted', J.muted);
  mic.classList.toggle('muted', J.muted);
  mic.dataset.tip = J.muted ? 'Muted · tap to unmute · hold to talk anyway' : 'Tap to mute · hold to talk (or hold Space)';
  $('#wakeLabel').textContent = J.muted ? 'Muted' : `“Hey ${J.name}”`;
  if (J.muted) {
    cancelCapture(); scanDrop();
    if (J.wakeRec) { try { J.wakeRec.onend = null; J.wakeRec.abort(); } catch (e) { } J.wakeRec = null; }
    if (!J.speaking && !J.busy && !LV.playing) setState('muted', LV.open ? MUTED_TEXT : 'Tap the mic to unmute');
  } else {
    if (J.wakeOn && !LV.open) startWake();
    if (!J.speaking && !J.busy && !LV.playing) setState(LV.open ? 'listening' : 'idle', LV.open ? 'Listening…' : `Say “Hey ${J.name}”`);
  }
  if (!quiet) { chime(!J.muted); toast(J.muted ? 'Microphone muted' : 'Listening again', J.muted ? `${J.name} cannot hear you until you unmute; her answer still plays. Hold the mic to talk anyway.` : `Say “Hey ${J.name}” any time.`); }
}'''),
    ('''function liveWanted() { return Date.now() > LV.fallbackUntil && (!!J.mic || J.liveTest) && !J.muted; }''',
     '''function liveWanted() { return Date.now() > LV.fallbackUntil && (!!J.mic || J.liveTest); }     // muted = the track is off; the session may still open for typed text'''),
    ('''  src.onended = () => { LV.srcs = LV.srcs.filter(x => x !== src); if (!LV.srcs.length) { LV.playing = false; J.speaking = false; Orb.setSource(J.analyser); duck(false); if (LV.open) setState('listening', 'Listening…'); lvIdle(); } };''',
     '''  src.onended = () => { LV.srcs = LV.srcs.filter(x => x !== src); if (!LV.srcs.length) { LV.playing = false; J.speaking = false; Orb.setSource(J.analyser); duck(false); if (LV.open) setState(J.muted ? 'muted' : 'listening', J.muted ? MUTED_TEXT : 'Listening…'); lvIdle(); } };'''),
    ('''  if (!silent && LV.open) { setState('listening', 'Listening…'); Orb.setSource(J.analyser); }''',
     '''  if (!silent && LV.open) { setState(J.muted ? 'muted' : 'listening', J.muted ? MUTED_TEXT : 'Listening…'); Orb.setSource(J.analyser); }'''),
    ('''      LV.ready = true; modePill(); chime(true); setState('listening', 'Listening…'); Orb.setSource(J.analyser); traceReset(); trace('listen', 'run');''',
     '''      LV.ready = true; modePill(); chime(true); setState(J.muted ? 'muted' : 'listening', J.muted ? MUTED_TEXT : 'Listening…'); Orb.setSource(J.analyser); traceReset(); trace('listen', 'run');'''),
    ('''  if (was) { Orb.setSource(null); if (!J.busy && !J.speaking) setState('idle', `Say “Hey ${J.name}”`); }''',
     '''  if (was) { Orb.setSource(null); if (!J.busy && !J.speaking) setState(J.muted ? 'muted' : 'idle', J.muted ? 'Tap the mic to unmute' : `Say “Hey ${J.name}”`); }'''),
])

# ---------------------------------------------------------------------------------------------------------- css + versions
css = ROOT / "mitra/web/mitra.css"
if not (BK / "mitra.css.2").exists():
    shutil.copy2(css, BK / "mitra.css.2")
css.write_text(css.read_text(encoding="utf-8").rstrip("\n") + '''

/* v78 · the composer on the stage: above the stage host and its dock (it sat under the dock chips: unclickable, shaded); the dock
   only catches clicks on its chips; the chips bar stops short of the composer; on boards and the map the composer sits in a glass pill */
body.stage-in .composer{z-index:60}
.stage-dock{pointer-events:none}.stage-dock>*{pointer-events:auto}
#dockChips{flex:0 1 auto;max-width:calc(50vw - 270px);overflow-x:auto;scrollbar-width:none}
#dockChips::-webkit-scrollbar{display:none}
@media (min-width:601px){
  body.stage-in.board-on .composer,body.stage-in.mapfocus-on .composer{padding:6px 8px 6px 6px;border-radius:999px;background:rgba(12,13,18,.62);backdrop-filter:blur(16px) saturate(1.3);border:1px solid rgba(255,255,255,.1);box-shadow:0 18px 50px rgba(0,0,0,.35);max-width:470px}
  html[data-theme=light] body.stage-in.board-on .composer,html[data-theme=light] body.stage-in.mapfocus-on .composer{background:rgba(255,255,255,.8);border-color:rgba(12,16,28,.1);box-shadow:0 18px 50px rgba(12,16,28,.12)}
}
body.muted .mode-pill[data-m=live]{border-color:rgba(255,92,106,.55);box-shadow:0 0 24px rgba(255,92,106,.2)}
body.muted .mode-pill[data-m=live] i{background:#ff7a86;box-shadow:0 0 10px #ff7a86;animation:none}
''', encoding="utf-8")
print("patched mitra/web/mitra.css")

patch("mitra/web/index.html", [("mitra.css?v=77", "mitra.css?v=78"), ("stage.js?v=67", "stage.js?v=68"), ("mitra.js?v=78", "mitra.js?v=79")])
print("done")
