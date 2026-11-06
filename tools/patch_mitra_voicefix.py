"""22 Oct 2026 (Pranay's second round): (1) the document reply is spoken by Gemini LIVE when the live session is open (web and
phone), like notifications, instead of the cascade TTS; the server skips TTS for those calls (the TTS quota had been burnt by
test runs: all three TTS models 429 -> the browser voice, which Edge's online voices do not cancel cleanly); (2) Stop cancels the
browser voice with the Edge workaround; (3) no-cache headers on the page and scripts + version bumps, so a browser never shows
an old splash.js / phone.js against new markup ("MitraMitra", "Sakala Mitra · App"); (4) phone-frame eyebrow is just MITRA.
Backups in tools/backups/res22/."""
import ast
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BK = ROOT / "tools" / "backups" / "res22"
BK.mkdir(parents=True, exist_ok=True)


def patch(rel, pairs, subs=()):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    shutil.copy(p, BK / (p.name + ".2.bak"))
    for old, new in pairs:
        assert old in s, f"{rel}: missing\n{old[:160]}"
        s = s.replace(old, new, 1)
    for old, new in subs:
        s = s.replace(old, new)
    if rel.endswith(".py"):
        ast.parse(s)
    p.write_text(s, encoding="utf-8")
    print("patched", rel)


# ------------------------------------------------------------------ server
patch("mitra/server/main.py", [
    ('''    resp.headers["permissions-policy"] = "camera=(), microphone=(self), geolocation=()"
    return resp''',
     '''    resp.headers["permissions-policy"] = "camera=(), microphone=(self), geolocation=()"
    path = request.url.path
    if path == "/" or path.endswith((".js", ".css", ".html")):          # the page and its scripts: always revalidated, never a stale splash.js on new markup
        resp.headers["cache-control"] = "no-cache"
    return resp'''),
    ('''class DocReq(BaseModel):
    session: str
    file_b64: str
    media_type: str = "application/pdf"
    filename: str = ""


class DocSubmit(BaseModel):
    session: str
    fields: dict = {}''',
     '''class DocReq(BaseModel):
    session: str
    file_b64: str
    media_type: str = "application/pdf"
    filename: str = ""
    want_audio: bool = True       # False while the live voice is open: Mitra reads the reply through Live, no TTS spent


class DocSubmit(BaseModel):
    session: str
    fields: dict = {}
    want_audio: bool = True'''),
    ('''    return await _with_voice(s, say, res.get("ui", []), intent="document")


@app.post("/api/document/submit")''',
     '''    return await _with_voice(s, say, res.get("ui", []), intent="document", want_audio=req.want_audio)


@app.post("/api/document/submit")'''),
    ('''    return await _with_voice(s, say, res.get("ui", []), intent=res.get("intent", "confirm"))


@app.post("/api/photo")''',
     '''    return await _with_voice(s, say, res.get("ui", []), intent=res.get("intent", "confirm"), want_audio=req.want_audio)


@app.post("/api/photo")'''),
    ('''async def _with_voice(s: dict, say: str, ui: list, intent: str = "") -> dict:
    say = guard.scrub(say)
    audio_b64, tts_prov, tid, parts = "", "browser", "", []
    if say:''',
     '''async def _with_voice(s: dict, say: str, ui: list, intent: str = "", want_audio: bool = True) -> dict:
    say = guard.scrub(say)
    audio_b64, tts_prov, tid, parts = "", "browser", "", []
    if say and want_audio:'''),
])

# the fake Live reads out any system line Mitra hands it (notification or a document reply), like the real model
patch("mitra/tests/fake_live.py", [
    ('''        if text.startswith("(Sakala notification"):       # a line Mitra asks the model to read out: say it, never act on it''',
     '''        if text.startswith("(") and "then stop" in text[:200]:   # a line Mitra asks the model to read out (a notification, a document reply): say it, never act on it'''),
])

# ------------------------------------------------------------------ client
patch("mitra/web/mitra.js", [
    # the reply to a document (read / submit / photo) is spoken by Live when it is open; the cascade voice otherwise
    ('''async function speakParts(r) {''',
     '''// a reply that came back over HTTP (a document read, the form submitted, a photo) while the live voice is open is read by
// Mitra's live voice, like a notification; the cascade voice (server TTS, browser as the last resort) only when Live is closed
async function sayBack(r) {
  if (!r || !r.say) { setState('idle', 'Ready'); return; }
  if (LV.open && LV.ready) { lvRead(r.say); return; }
  if (r.tts_id && (r.parts || []).length > 1) await speakParts(r); else await speak(r.say, r.audio_b64, r.tts);
}
function liveVoiceOn() { return !!(LV.open && LV.ready); }
async function speakParts(r) {'''),
    ('''function stopSpeaking() {
  if (!J.speaking) return; J.speaking = false; clearInterval(J.levelTimer);
  try { outSrc && outSrc.stop(); } catch (e) { }
  if ('speechSynthesis' in window) speechSynthesis.cancel();''',
     '''function stopSpeaking() {
  if ('speechSynthesis' in window) { try { speechSynthesis.pause(); speechSynthesis.cancel(); setTimeout(() => speechSynthesis.cancel(), 120); } catch (e) { } }   // Edge's online voices need the pause + a second cancel
  if (!J.speaking) return; J.speaking = false; clearInterval(J.levelTimer);
  try { outSrc && outSrc.stop(); } catch (e) { }'''),
    ('''function lvText(text, system = false) {''',
     '''// Mitra's live voice reads a reply that arrived over HTTP (a document read, the form submitted): word for word, no function
function lvRead(text) {
  if (!LV.ws || LV.ws.readyState !== 1 || !LV.ready) { LV.q.push({ system: text }); return; }
  lvCut(); LV.ws.send(JSON.stringify({ type: 'text', text: `(Say this to the person now, in these words, then stop. Call no function.) ${text}`, system: true }));
  LV.lastVoice = performance.now(); lvIdle();
}
function lvText(text, system = false) {'''),
    ('''    const r = await api('/api/document', { session: J.sid, file_b64: b64, media_type: file.type || (file.name.toLowerCase().endsWith('.pdf') ? 'application/pdf' : 'image/jpeg'), filename: file.name });
    trace('think', 'done'); trace('act', 'done'); trace('speak', 'run');
    applyUi(r.ui || []); captionYou('📄 ' + file.name); Orb.burst(); flyLabel('letter read → form'); convoAdd({ you: '📄 ' + file.name, say: r.say || '', intent: 'document', t: Date.now() });
    if (r.tts_id && (r.parts || []).length > 1) await speakParts(r); else await speak(r.say, r.audio_b64, r.tts);''',
     '''    const r = await api('/api/document', { session: J.sid, file_b64: b64, media_type: file.type || (file.name.toLowerCase().endsWith('.pdf') ? 'application/pdf' : 'image/jpeg'), filename: file.name, want_audio: !liveVoiceOn() });
    trace('think', 'done'); trace('act', 'done'); trace('speak', 'run');
    applyUi(r.ui || []); captionYou('📄 ' + file.name); Orb.burst(); flyLabel('letter read → form'); convoAdd({ you: '📄 ' + file.name, say: r.say || '', intent: 'document', t: Date.now() });
    await sayBack(r);'''),
    ('''      const r = await api('/api/document/submit', { session: J.sid, fields: collect() });
      trace('think', 'done'); trace('act', 'done'); trace('speak', 'run'); applyUi(r.ui || []); captionYou('Submit'); convoAdd({ you: 'Submit', say: r.say || '', intent: r.intent || 'confirm', t: Date.now() });
      if (r.tts_id && (r.parts || []).length > 1) await speakParts(r); else await speak(r.say, r.audio_b64, r.tts);''',
     '''      const r = await api('/api/document/submit', { session: J.sid, fields: collect(), want_audio: !liveVoiceOn() });
      trace('think', 'done'); trace('act', 'done'); trace('speak', 'run'); applyUi(r.ui || []); captionYou('Submit'); convoAdd({ you: 'Submit', say: r.say || '', intent: r.intent || 'confirm', t: Date.now() });
      await sayBack(r);'''),
])
# the photo path: same voice rule
s = (ROOT / "mitra/web/mitra.js").read_text(encoding="utf-8")
i = s.index("async function sendPhoto(file)")
j = s.index("if (r.tts_id && (r.parts || []).length > 1) await speakParts(r); else await speak(r.say, r.audio_b64, r.tts);", i)
s = s[:j] + "await sayBack(r);" + s[j + len("if (r.tts_id && (r.parts || []).length > 1) await speakParts(r); else await speak(r.say, r.audio_b64, r.tts);"):]
(ROOT / "mitra/web/mitra.js").write_text(s, encoding="utf-8")

# ------------------------------------------------------------------ markup: versions, the phone-frame eyebrow
patch("mitra/web/index.html", [], subs=[
    ("mitra.css?v=64", "mitra.css?v=65"), ("mitra.js?v=66", "mitra.js?v=67"), ("orb.js?v=46", "orb.js?v=47"), ("portal.js?v=32", "portal.js?v=33"),
    ("stage.js?v=60", "stage.js?v=61"), ("splash.js?v=51", "splash.js?v=52"), ("phone.js?v=49", "phone.js?v=50"), ("app.js?v=46", "app.js?v=47"),
    ('<script src="/assets/mapdata.js"></script>', '<script src="/assets/mapdata.js?v=2"></script>'),
])
patch("mitra/web/phone.js", [], subs=[('<div class="ps-k"><i></i>Mitra · App</div>', '<div class="ps-k"><i></i>Mitra</div>')])
print("done")
