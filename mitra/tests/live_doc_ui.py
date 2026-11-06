"""22 Oct 2026: the document reply is spoken by the REAL Gemini Live voice (main instance 8030), web and phone. A real letter is
dropped while the live session is open: no browser / TTS voice plays (J.speaking stays false), Mitra's live voice reads the reply
(the live output transcript mentions the letter), and Stop cuts it at once. Run from mitra/: python tests/live_doc_ui.py"""
import asyncio
import json
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
        fail += 1; print("  FAIL", name, " <-", str(detail)[:400])


async def set_file(b, selector, path):
    doc = await b.cmd("DOM.getDocument", depth=-1, pierce=True)
    node = await b.cmd("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
    await b.cmd("DOM.setFileInputFiles", files=[path], nodeId=node["nodeId"])


JS = """(async()=>{ const sl=ms=>new Promise(r=>setTimeout(r,ms)); const res={}; const t0=Date.now();
  for(let i=0;i<100&&!J.sid;i++) await sl(100);
  if (OPEN) { turn({text:'hello'}); for(let i=0;i<200&&!(LV.open&&LV.ready);i++) await sl(100); for(let i=0;i<150&&LV.playing;i++) await sl(100); await sl(500); }
  res.live=!!(LV.open&&LV.ready); res.liveT=(Date.now()-t0)/1000;
  window.__spoke=0; window.__synth=0; const os=speak; window.speak=async function(){ window.__spoke++; return os.apply(this, arguments) };
  const osp=speakParts; window.speakParts=async function(){ window.__spoke++; return osp.apply(this, arguments) };
  return res })()"""
AFTER = """(async()=>{ const sl=ms=>new Promise(r=>setTimeout(r,ms)); const res={}; const t0=Date.now();
  for(let i=0;i<1500&&!document.querySelector('.docrev');i++) await sl(100); res.form=!!document.querySelector('.docrev'); res.formT=(Date.now()-t0)/1000;
  let played=false, tx=''; for(let i=0;i<300;i++){ await sl(100); if(LV.playing) played=true; tx=LV.outTx||''; if(played && /letter|narasimhaiah|kodigenahalli|502806/i.test(tx)) break; }
  res.played=played; res.tx=tx.slice(0,200); res.spoke=window.__spoke; res.jspeaking=J.speaking; res.synth=('speechSynthesis' in window)?speechSynthesis.speaking:false;
  res.cap=(document.querySelector('#capJv')||{}).innerText||''; res.state=document.body.dataset.state;
  document.querySelector('#stop').click(); await sl(700); res.stopped=!LV.playing && !J.speaking; res.pill=(document.querySelector('#modePill')||{}).innerText||'';
  return res })()"""


async def run(label, url, port, size, open_first=True):
    async with Browser(port=port, size=size, gpu=True) as b:
        await b.goto(url, 4)
        r = await b.eval(JS.replace("OPEN", "true" if open_first else "false"), timeout=90)
        check(f"{label}: the live voice is {'open' if open_first else 'in standby, as it should be'} ({r.get('liveT', 0):.1f} s)", bool(r.get("live")) == open_first, r)
        if bool(r.get("live")) != open_first:
            return
        await set_file(b, "#reqFile", L1)
        r = await b.eval(AFTER, timeout=240)
        check(f"{label}: the letter is read into the form in {r.get('formT', 0):.0f} s", r.get("form"), r)
        check(f"{label}: Mitra's LIVE voice reads the reply (live audio played, transcript about the letter); no browser / TTS voice was used",
              r.get("played") and r.get("tx") and not r.get("spoke") and not r.get("synth"), r)
        check(f"{label}: Stop cuts it at once", r.get("stopped"), r)
        await b.shot(TMP / f"live_doc_{label}.png")
        check(f"{label}: no JS exceptions", not [e for e in b.events if e[0] == "exception"], b.events[:3])


async def main():
    print("[web desk, real Live]")
    await run("web", f"{B}/?auto=1&noevents=1&livetest=1&p=citizen", 9441, (1536, 864))
    print("[phone app, real Live, from STANDBY: the live voice opens for the reply]")
    await run("phone", f"{B}/?auto=1&noevents=1&livetest=1&p=citizen&app=1&intro=0", 9442, (393, 852), open_first=False)
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
