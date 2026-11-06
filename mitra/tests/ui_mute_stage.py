"""Mute is the microphone only, and the composer is reachable on the stage (27 Oct 2026, Pranay's demo):
on the stage board at the demo laptop's size the mic is the element under the pointer (it sat under the dock chips);
the composer returns to the dashboard column when the stage closes; muting while Mitra answers keeps the live session
open and the answer playing; typed text while muted still goes to Live; Stop is what cuts her off; unmuting returns to
listening. Headless Edge over CDP against the fake-Live test instance. Usage: python tests/ui_mute_stage.py [base]"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8031"
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:360])


HOOKS = """
window.sleep=ms=>new Promise(r=>setTimeout(r,ms));
window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};
window.__tc=0; window.__lastTurn=null; window.__closes=0;
const _le=lvEvent; lvEvent=function(e){ if(e.type==='turn_complete'){__tc++; __lastTurn=e;} return _le(e); };
const _lc=liveClose; liveClose=function(w){ __closes++; window.__lastClose=w; return _lc(w); };
window.topOf=sel=>{const e=document.querySelector(sel); if(!e) return null; const r=e.getBoundingClientRect(); const t=document.elementFromPoint(r.x+r.width/2, r.y+r.height/2); return t? ((t.id?'#'+t.id:'')+'.'+String(t.className||'').replace(/\\s+/g,'.').slice(0,30)+' in:'+(e.contains(t))): null};
"""


async def main():
    async with Browser(port=9341, size=(1917, 925)) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 4)
        await b.eval(HOOKS)
        await b.eval("until(()=>LV.open && LV.ready, 30000)")

        print("[the composer on the stage board]")
        r = await b.eval("""(async()=>{ const n0=__tc; turn({text:'how is Karnataka doing'}); await until(()=>Stage.open && document.body.classList.contains('board-on'), 40000); await until(()=>__tc>n0, 40000); await sleep(1800);
          const res={board:document.body.classList.contains('board-on'), mic:topOf('#mic'), field:topOf('#text'), hf:topOf('#handsfree'), inBody:document.querySelector('.composer').parentNode===document.body,
            z:getComputedStyle(document.querySelector('.composer')).zIndex, dockPE:getComputedStyle(document.querySelector('.stage-dock')).pointerEvents, chipPE:getComputedStyle(document.querySelector('.dock-chip')).pointerEvents};
          const cr=document.querySelector('.composer').getBoundingClientRect(), dr=document.querySelector('#dockChips').getBoundingClientRect(); res.chipsClear=dr.right<=cr.left+1;
          return res })()""")
        print("   ", json.dumps(r))
        check("the mic is the element under the pointer (not the dock chips)", r["board"] and r["mic"] and "#mic" in r["mic"] or (r["mic"] and r["mic"].endswith("in:true")), r)
        check("the text field and the wake pill are reachable too", r["field"] and r["field"].endswith("in:true") and r["hf"] and r["hf"].endswith("in:true"), r)
        check("the composer sits above the stage host, the dock only catches clicks on its chips, the chips stop short of it", r["inBody"] and int(r["z"]) >= 60 and r["dockPE"] == "none" and r["chipPE"] == "auto" and r["chipsClear"], r)
        r = await b.eval("""(async()=>{ UI.nav({target:'dashboard'}); await sleep(1100); return {open:Stage.open, home:!!document.querySelector('.col.center .composer'), inBody:document.querySelector('.composer').parentNode===document.body} })()""")
        check("closing the stage puts the composer back in the dashboard column", not r["open"] and r["home"] and not r["inBody"], r)

        print("[mute keeps the session and the answer; Stop cuts]")
        r = await b.eval("""(async()=>{ const res={}; const n0=__tc, c0=__closes;
          turn({text:'compare Piriyapatna, Hunsur and Mysore'}); res.playing=await until(()=>LV.playing, 40000);
          setMuted(true,{quiet:true}); await sleep(450);
          res.muted=J.muted; res.openAfterMute=LV.open; res.stillPlaying=LV.playing; res.closes=__closes-c0;
          res.done=await until(()=>__tc>n0, 40000); await sleep(600);
          res.say=((__lastTurn||{}).mitra||'').slice(0,60); res.state=document.body.dataset.state; res.openAfterTurn=LV.open; res.pill=document.querySelector('#modePill')?.dataset.m;
          return res })()""")
        print("   ", json.dumps(r))
        check("muting mid-answer: the session stays open and the answer keeps playing to the end", r["playing"] and r["muted"] and r["openAfterMute"] and r["stillPlaying"] and r["closes"] == 0 and r["done"] and r["say"], r)
        check("after the answer the state is 'muted' and the pill still says live", r["state"] == "muted" and r["openAfterTurn"] and r["pill"] == "live", r)
        r = await b.eval("""(async()=>{ const res={}; const n0=__tc, c0=__closes; turn({text:'which district has the most open cases'});
          res.done=await until(()=>__tc>n0, 40000); res.open=LV.open; res.closes=__closes-c0; res.live=(__lastTurn||{}).intent||''; res.stage=Stage.open; return res })()""")
        print("   ", json.dumps(r))
        check("typed text while muted still goes to the live session and draws its picture", r["done"] and r["open"] and r["closes"] == 0 and r["stage"], r)
        r = await b.eval("""(async()=>{ const res={}; turn({text:'compare Hunsur and Mysore on overdue'}); res.playing=await until(()=>LV.playing, 40000);
          stopAll(); await sleep(350); res.stopped=!LV.playing; res.open=LV.open; res.muted=J.muted; return res })()""")
        print("   ", json.dumps(r))
        check("Stop cuts the answer at once, the session stays, mute stays", r["playing"] and r["stopped"] and r["open"] and r["muted"], r)
        r = await b.eval("""(async()=>{ setMuted(false,{quiet:true}); await sleep(300); return {muted:J.muted, state:document.body.dataset.state, open:LV.open} })()""")
        check("unmute: listening again on the same session", not r["muted"] and r["state"] == "listening" and r["open"], r)

        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS errors", not errs, errs[:3])
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
