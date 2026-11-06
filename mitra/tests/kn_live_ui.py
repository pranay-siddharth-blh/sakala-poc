"""22 Oct 2026 (Pranay): Kannada stays Kannada on every path, and the language changes by voice, both ways, no button.
On the REAL live voice (main instance 8030), in the browser, web and phone:
  web  - an English session is asked (typed, which goes to Live like speech) 'ಕನ್ನಡದಲ್ಲಿ ಮಾತಾಡಿ' -> the session reopens in Kannada
         (mode pill, toggle), 'can I upload a letter' in Kannada lights the drop zone, the real letter is dropped and Mitra's live
         voice reads the form reply IN KANNADA (Kannada script in the live transcript, the iPGRS number kept, no browser / TTS voice),
         'ಸಲ್ಲಿಸಿ' files it (Kannada reply, a GR id on screen), 'switch to English' reopens in English, 'hello' is answered in
         English, 'ಕನ್ನಡಕ್ಕೆ ಬದಲಾಯಿಸಿ' brings Kannada back.
  phone - a Kannada session from Standby: the letter dropped in the app opens the live voice, which reads the reply in Kannada;
         'switch to English' reopens in English.
Run from mitra/: PYTHONIOENCODING=utf-8 python tests/kn_live_ui.py"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8030"
LET = Path(__file__).resolve().parents[2] / "tools" / "tests" / "letters"
L1 = str(LET / "l1_kodigenahalli_water.jpeg")
TMP = Path(r"C:\Users\hp\AppData\Local\Temp")
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:500])


async def set_file(b, selector, path):
    doc = await b.cmd("DOM.getDocument", depth=-1, pierce=True)
    node = await b.cmd("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
    await b.cmd("DOM.setFileInputFiles", files=[path], nodeId=node["nodeId"])


HELPERS = """window.__kn = s => (s||'').split('').filter(ch => ch >= 'ಀ' && ch <= '೿').length;
window.__sl = ms => new Promise(r => setTimeout(r, ms));
window.__until = async (f, ms) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (f()) return true; } catch (e) {} await __sl(100); } return false; };
window.__pill = () => ((document.querySelector('#modePill') || {}).innerText || '').trim();
window.__langOn = () => ((document.querySelector('#lang button.on') || {}).dataset || {}).l || '';
window.__spoke = 0; window.__synth = 0; window.__cnt = 0;
// the strip keeps only the last 6 exchanges, so count them instead of measuring the strip
if (!window.__cntHooked) { window.__cntHooked = 1; const oc = convoAdd; window.convoAdd = function (e) { const r = oc.apply(this, arguments); if (r) window.__cnt++; return r; }; }
if (!window.__hooked) { window.__hooked = 1; const os = speak; window.speak = async function(){ window.__spoke++; return os.apply(this, arguments) };
  const osp = speakParts; window.speakParts = async function(){ window.__spoke++; return osp.apply(this, arguments) }; }
// a typed line goes to the live voice like speech; wait for the session to settle on the given language
window.__say = async (text, wantLang, ms) => { const n = window.__cnt; turn({ text });
  // the new session's acknowledgement is a read-out turn (no 'you' side): wait for that exchange, not just for the reopen
  const inScript = s => wantLang === 'kn' ? __kn(s) > 5 : (s.length > 3 && __kn(s) === 0);
  await __until(() => LV.open && LV.ready && J.lang === wantLang && window.__cnt > n && inScript(J.convo[J.convo.length - 1].say || '') && !LV.playing && LV.outTx === '' && !J.busy, ms || 40000); await __sl(400);
  return { lang: J.lang, pill: __pill(), on: __langOn(), live: !!(LV.open && LV.ready) }; };
window.__ask = async (text, ms) => { const n = window.__cnt; turn({ text });
  await __until(() => window.__cnt > n && !LV.playing && LV.outTx === '' && !J.busy, ms || 30000); await __sl(300); return __lastSaid(); };
// the last thing Mitra said on the live voice (the transcript of the turn that just completed)
window.__lastSaid = () => { const c = (J.convo || []); return c.length ? (c[c.length - 1].say || '') : ''; };
"""

WEB = """(async()=>{ const res = {};
  for (let i = 0; i < 100 && !J.sid; i++) await __sl(100);
  turn({ text: 'hello' }); await __until(() => LV.open && LV.ready, 20000); await __until(() => !LV.playing && LV.outTx === '', 25000); await __sl(300);
  res.enLive = !!(LV.open && LV.ready); res.enPill = __pill();
  // 1 ask for Kannada by voice (typed = the same path as speech)
  res.kn = await __say('ಕನ್ನಡದಲ್ಲಿ ಮಾತಾಡಿ', 'kn', 30000); res.knAck = __lastSaid();
  // 2 can I upload a letter, in Kannada
  res.uploadSaid = await __ask('ನಾನು ಒಂದು letter upload ಮಾಡ್ಬಹುದಾ', 30000);
  res.lit = await __until(() => document.querySelector('.dropz.lit') || document.querySelector('.dropz'), 5000);
  window.__spoke = 0; return res })()"""

AFTER_DROP = """(async()=>{ const res = {}; const t0 = Date.now(); const n0 = window.__cnt;
  res.form = await __until(() => document.querySelector('.docrev'), 150000); res.formT = (Date.now() - t0) / 1000;
  let played = false, tx = '';
  for (let i = 0; i < 400; i++) { await __sl(100); if (LV.playing) played = true; tx = LV.outTx || __lastSaid(); if (played && __kn(tx) > 15 && /502806|Narasimhaiah|Kodigenahalli|Madhugiri/i.test(tx)) break; }
  // the read-out is its own exchange (no 'you' side): wait for it to finish before the next word
  await __until(() => window.__cnt >= n0 + 2 && !J.convo[J.convo.length - 1].you && !LV.playing && LV.outTx === '', 40000); await __sl(500);
  res.played = played; res.tx = tx.slice(0, 260); res.knLetters = __kn(tx); res.spoke = window.__spoke; res.synth = ('speechSynthesis' in window) ? speechSynthesis.speaking : false;
  res.lang = J.lang; res.pill = __pill();
  // 3 submit, in Kannada: filed in THIS exchange (a fresh session, so any GR id on screen is this letter's)
  res.filedSaid = await __ask('ಸಲ್ಲಿಸಿ', 60000); res.filedKn = __kn(res.filedSaid);
  res.filed = /GR-\\d{6}/.test(document.body.innerText);
  // 4 back to English by voice, then a plain turn is answered in English
  res.en = await __say('switch to English', 'en', 30000); res.enAck = __lastSaid();
  res.enSaid = await __ask('hello, how many requests do I have?', 30000); res.enSaidKn = __kn(res.enSaid);
  // 5 and Kannada again, asked in Kannada
  // 5 and Kannada again, asked in Kannada: judged from a timeline (the session reopens in Kannada and a Kannada exchange follows)
  { const n = window.__cnt, t0 = Date.now(); let sw = false, ack = '';
    turn({ text: 'ಕನ್ನಡಕ್ಕೆ ಬದಲಾಯಿಸಿ' });
    while (Date.now() - t0 < 45000) { await __sl(100);
      if (J.lang === 'kn' && LV.open && LV.ready && __langOn() === 'kn' && /ಕನ್ನಡ/.test(__pill())) sw = true;
      if (window.__cnt > n) { const s = J.convo[J.convo.length - 1].say || ''; if (__kn(s) > 5) { ack = s; if (sw && !LV.playing) break; } } }
    res.kn2 = { lang: J.lang, switched: sw, pill: __pill(), on: __langOn() }; res.kn2Ack = ack; }
  return res })()"""

PHONE = """(async()=>{ const res = {};
  for (let i = 0; i < 100 && !J.sid; i++) await __sl(100);
  res.lang = J.lang; res.standby = !LV.open; window.__spoke = 0; return res })()"""

PHONE_AFTER = """(async()=>{ const res = {}; const t0 = Date.now();
  res.form = await __until(() => document.querySelector('.docrev'), 150000); res.formT = (Date.now() - t0) / 1000;
  let played = false, tx = '';
  for (let i = 0; i < 400; i++) { await __sl(100); if (LV.playing) played = true; tx = LV.outTx || __lastSaid(); if (played && __kn(tx) > 15) break; }
  await __until(() => !LV.playing && LV.outTx === '', 30000);
  res.played = played; res.tx = tx.slice(0, 200); res.knLetters = __kn(tx); res.spoke = window.__spoke; res.live = !!(LV.open && LV.ready); res.pill = __pill();
  res.en = await __say('switch to English', 'en', 30000); res.enAck = __lastSaid(); res.enKn = __kn(res.enAck);
  return res })()"""


async def web():
    print("[web desk, real live voice: English -> Kannada by voice -> letter read in Kannada -> filed -> English -> Kannada]")
    async with Browser(port=9451, size=(1536, 864), gpu=True) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=citizen", 4)
        await b.eval("localStorage.clear(); localStorage.setItem('jv_lang','en'); 1")     # a fresh session: a GR id on screen is this test's
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=citizen", 4)
        await b.eval(HELPERS)
        r = await b.eval(WEB, timeout=200)
        check(f"the English live session is open ({r.get('enPill')})", r.get("enLive") and "Live" in (r.get("enPill") or ""), r)
        k = r.get("kn") or {}
        check("'ಕನ್ನಡದಲ್ಲಿ ಮಾತಾಡಿ' by voice: the session reopens in Kannada (pill, toggle), still live", k.get("lang") == "kn" and "ಕನ್ನಡ" in (k.get("pill") or "") and k.get("on") == "kn" and k.get("live"), r)
        check("the acknowledgement is spoken in Kannada", sum(1 for ch in (r.get("knAck") or "") if "ಀ" <= ch <= "೿") > 5, r.get("knAck"))
        check("'can I upload a letter' in Kannada raises the request card with the drop zone", r.get("lit"), r)
        check("and the answer is in Kannada", sum(1 for ch in (r.get("uploadSaid") or "") if "ಀ" <= ch <= "೿") > 5, r.get("uploadSaid"))
        await set_file(b, "#reqFile", L1)
        r = await b.eval(AFTER_DROP, timeout=400)
        check(f"the letter is read into the form in {r.get('formT', 0):.0f} s", r.get("form"), r)
        check("Mitra's LIVE voice reads the document reply IN KANNADA (Kannada script, the letter's facts kept); no browser / TTS voice",
              r.get("played") and r.get("knLetters", 0) > 15 and not r.get("spoke") and not r.get("synth"), r)
        check("still a Kannada live session after the reply", r.get("lang") == "kn" and "ಕನ್ನಡ" in (r.get("pill") or ""), r)
        check("'ಸಲ್ಲಿಸಿ' files it: a GR id on screen, the reply in Kannada", r.get("filed") and r.get("filedKn", 0) > 5, (r.get("filed"), r.get("filedSaid")))
        e = r.get("en") or {}
        check("'switch to English' by voice: the session reopens in English (pill, toggle), the acknowledgement in English",
              e.get("lang") == "en" and "Live" in (e.get("pill") or "") and e.get("on") == "en" and sum(1 for ch in (r.get("enAck") or "") if "ಀ" <= ch <= "೿") == 0, r)
        check("the next answer is in English", r.get("enSaid") and r.get("enSaidKn", 0) == 0, r.get("enSaid"))
        k2 = r.get("kn2") or {}
        check("'ಕನ್ನಡಕ್ಕೆ ಬದಲಾಯಿಸಿ': Kannada again, acknowledged in Kannada", k2.get("lang") == "kn" and "ಕನ್ನಡ" in (k2.get("pill") or "") and sum(1 for ch in (r.get("kn2Ack") or "") if "ಀ" <= ch <= "೿") > 5, {"kn2": k2, "ack": r.get("kn2Ack")})
        await b.shot(TMP / "kn_live_web.png")
        check("no JS exceptions", not [e for e in b.events if e[0] == "exception"], b.events[:3])


async def phone():
    print("[phone app, real live voice, Kannada session from Standby: the letter opens the live voice, read in Kannada; then English by voice]")
    async with Browser(port=9452, size=(393, 852), gpu=True) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=citizen&app=1&intro=0", 4)
        await b.eval("localStorage.setItem('jv_lang','kn'); 1")
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=citizen&app=1&intro=0", 4)
        await b.eval(HELPERS)
        r = await b.eval(PHONE, timeout=60)
        check("phone: a Kannada session, the live voice in Standby", r.get("lang") == "kn" and r.get("standby"), r)
        await set_file(b, "#reqFile", L1)
        r = await b.eval(PHONE_AFTER, timeout=400)
        check(f"phone: the letter is read into the form in {r.get('formT', 0):.0f} s", r.get("form"), r)
        check("phone: the live voice opens for the reply and reads it IN KANNADA; no browser / TTS voice", r.get("played") and r.get("knLetters", 0) > 15 and not r.get("spoke"), r)
        e = r.get("en") or {}
        check("phone: 'switch to English' by voice reopens in English, acknowledged in English", e.get("lang") == "en" and r.get("enKn", 0) == 0 and e.get("live"), r)
        await b.shot(TMP / "kn_live_phone.png")
        check("phone: no JS exceptions", not [e for e in b.events if e[0] == "exception"], b.events[:3])


async def main():
    await web()
    await phone()
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
