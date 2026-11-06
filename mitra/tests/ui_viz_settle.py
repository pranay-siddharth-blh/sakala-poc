"""The visual settles before it shows (26 Oct 2026, Pranay's demo): one picture per question however many times the model
calls, the last call wins, it is up by the time Mitra speaks, a new question's picture crossfades in place, and the orange
'shall I go ahead?' bar leaves the moment yes / no is answered (by the model, or by the relay when the model stays silent).
Runs in headless Edge over CDP against the test instance on the fake Live (8031), which imitates the model's bad days
with the '!!repeat N', '!!twice' and '!!silent on' directives. Usage: python tests/ui_viz_settle.py [base]"""
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
window.__vizLog=[]; window.__shows=[]; window.__tools=[]; window.__renders=0;
const _show=Stage.show; Stage.show=(op,o)=>{__shows.push({crossfade:!!(o&&o.crossfade),morph:!!(o&&o.morph),title:op.title,t:Math.round(performance.now())});return _show(op,o)};
window.__tc=0; window.__lastTurn=null;
const _le=lvEvent; lvEvent=function(e){ if(e.type==='tool') __tools.push({t:Math.round(performance.now()),name:e.name,n:e.n||0,auto:!!e.auto}); if(e.type==='turn_complete'){__tc++; __lastTurn=e;} return _le(e); };
new MutationObserver(ms=>{ if(ms.some(m=>[...m.addedNodes].some(n=>n.classList&&n.classList.contains('vcard')))) __renders++; }).observe(document.body,{childList:true,subtree:true});   // one per paint of the cards, however many cards
window.waitTurn=async(n0,ms=40000)=>until(()=>__tc>n0,ms);      // the conversation strip keeps 6 exchanges: count turns, not the strip
window.lastSay=()=>(__lastTurn&&__lastTurn.mitra)||'';
"""


async def main():
    async with Browser(port=9337, size=(1536, 864)) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 4)
        await b.eval(HOOKS)
        await b.eval("until(()=>LV.open && LV.ready, 20000)")

        print("[one picture per question, the last call wins]")
        r = await b.eval("""(async()=>{ const n0=__tc, s0=__shows.length, r0=__renders;
          turn({text:'!!repeat 4 which district has the most open cases'}); await waitTurn(n0); await sleep(800);
          const d=Stage.debug(); return {shows:__shows.slice(s0), renders:__renders-r0, tools:__tools.length, open:Stage.open, items:d.cards[0]?d.cards[0].items.length:0,
            kind:d.cards[0]&&d.cards[0].kind, log:__vizLog.slice(-1), say:lastSay().slice(0,80)} })()""")
        print("   ", json.dumps(r)[:400])
        check("four calls in one turn -> the stage entered once, no flicker (one render)", len(r["shows"]) == 1 and r["renders"] == 1 and r["open"], r)
        check("the picture is the LAST call's (limit 11 -> 11 districts), a ranking", r["items"] == 11 and r["kind"] == "race", r)
        check("it was shown as she started speaking or on settling, not per call", r["log"] and r["log"][0]["why"] in ("speech", "settled", "audio", "turn"), r)

        print("[a wrong first call then the right one: only the right picture appears]")
        r = await b.eval("""(async()=>{ const n0=__tc, s0=__shows.length, r0=__renders, t0=__tools.length;
          turn({text:'!!twice show me all the grievances according to their specific input sources'}); await waitTurn(n0); await sleep(900);
          const d=Stage.debug(); const labels=d.cards.flatMap(c=>c.items.map(i=>i.label));
          return {shows:__shows.slice(s0), renders:__renders-r0, tools:__tools.slice(t0).map(t=>t.name), labels, by:(Stage.current.cards[0]||{}).by||'', title:Stage.current.title} })()""")
        print("   ", json.dumps(r)[:500])
        check("two different calls -> one crossfade onto the stage already up, one render", len(r["shows"]) == 1 and r["shows"][0]["crossfade"] and r["renders"] == 1, r)
        check("the picture answers the question: a breakdown by input source", r["by"] == "source" or any(any(w in l.lower() for w in ("praja", "ipgrs", "mobile", "csc", "citizen service", "call", "camp", "web", "whatsapp", "mitra")) for l in r["labels"]), r)
        check("the wrong first call (statewide_stats) came first and never painted", r["tools"] and r["tools"][0] == "statewide_stats" and len(r["tools"]) >= 2, r)

        print("[timing: the picture is up before her first words, never after]")
        r = await b.eval("""(async()=>{ const n0=__tc, s0=__shows.length, t0=__tools.length;
          turn({text:'compare Piriyapatna, Hunsur and Mysore'}); await waitTurn(n0); await sleep(300);
          const sh=__shows.slice(s0)[0], tl=__tools.slice(t0); return {show:sh, lastTool:tl.length?tl[tl.length-1].t:0, firstOut:LV.__firstOutT||0, n:tl.length} })()""")
        print("   ", json.dumps(r)[:300])
        check("a single call shows within 1.2 s of its result (speech start or the settle window)", r["show"] and r["lastTool"] and 0 <= r["show"]["t"] - r["lastTool"] <= 1300, r)

        print("[the orange bar leaves when yes / no is answered]")
        r = await b.eval("""(async()=>{ const res={}; let n0=__tc;
          turn({text:'nudge the Tahsildar of Piriyapatna'}); res.bar1=await until(()=>document.querySelector('#confirmBar.on'),20000); await waitTurn(n0);
          n0=__tc; turn({text:'yes'}); await waitTurn(n0); res.gone1=await until(()=>!document.querySelector('#confirmBar'),6000); res.say1=lastSay().slice(0,100);
          n0=__tc; turn({text:'nudge the Tahsildar of Piriyapatna'}); res.bar2=await until(()=>document.querySelector('#confirmBar.on'),20000); await waitTurn(n0);
          n0=__tc; turn({text:'no'}); await waitTurn(n0); res.gone2=await until(()=>!document.querySelector('#confirmBar'),6000); res.say2=lastSay().slice(0,100);
          return res })()""")
        print("   ", json.dumps(r)[:400])
        check("yes -> the action runs and the bar is gone", r["bar1"] and r["gone1"] and "remind" in r["say1"].lower(), r)
        check("no -> nothing done and the bar is gone", r["bar2"] and r["gone2"] and "not done" in r["say2"].lower(), r)

        print("[the model stays silent on yes / no: the relay answers the bar itself]")
        r = await b.eval("""(async()=>{ const res={}; let n0=__tc;
          turn({text:'nudge the Tahsildar of Piriyapatna'}); res.bar=await until(()=>document.querySelector('#confirmBar.on'),20000); await waitTurn(n0);
          n0=__tc; turn({text:'!!silent on'}); await waitTurn(n0);
          n0=__tc; turn({text:'yes'}); await waitTurn(n0); res.gone=await until(()=>!document.querySelector('#confirmBar'),8000);
          await sleep(1500); res.say=J.convo.slice(-2).map(x=>x.say||'').join(' | ').slice(0,200); res.intent=J.convo.slice(-3).map(x=>x.intent||'').join(' ');
          n0=__tc; turn({text:'nudge the Tahsildar of Piriyapatna'}); res.bar2=await until(()=>document.querySelector('#confirmBar.on'),20000); await waitTurn(n0);
          n0=__tc; turn({text:'!!silent on'}); await waitTurn(n0);
          n0=__tc; turn({text:'no'}); await waitTurn(n0); res.gone2=await until(()=>!document.querySelector('#confirmBar'),8000); res.intent2=J.convo.slice(-3).map(x=>x.intent||'').join(' ');
          return res })()""")
        print("   ", json.dumps(r)[:500])
        check("silent model + 'yes' -> the relay runs the reminder, reads it, the bar is gone", r["bar"] and r["gone"] and "confirm_action" in r["intent"] and "remind" in r["say"].lower(), r)
        check("silent model + 'no' -> the relay cancels, the bar is gone", r["bar2"] and r["gone2"] and "cancel_action" in r["intent2"], r)

        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS errors", not errs, errs[:3])
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
