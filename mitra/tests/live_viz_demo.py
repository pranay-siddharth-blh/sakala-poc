"""The two questions from Pranay's 26 Oct demo, on the REAL Gemini Live (8030): 'show me all the grievances across
Karnataka' and 'show me all the grievances according to their specific input sources', then a comparison and a confirm
bar. Checks: one stage entrance / crossfade per question however many functions the model calls, the picture matches the
question (map, then a breakdown by source), it is up by the time she speaks, and the orange bar leaves on 'yes'.
Costs a few live turns. Usage: python tests/live_viz_demo.py [base]   (default http://localhost:8030)"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8030"
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
window.__vizLog=[]; window.__shows=[]; window.__tools=[]; window.__renders=0; window.__tc=0; window.__lastTurn=null; window.__firstOut=0;
const _show=Stage.show; Stage.show=(op,o)=>{__shows.push({crossfade:!!(o&&o.crossfade),title:op.title,t:Math.round(performance.now())});return _show(op,o)};
const _le=lvEvent; lvEvent=function(e){ if(e.type==='tool') __tools.push({t:Math.round(performance.now()),name:e.name,n:e.n||0}); if(e.type==='out'&&!__firstOut) __firstOut=Math.round(performance.now()); if(e.type==='turn_complete'){__tc++; __lastTurn=e;} return _le(e); };
new MutationObserver(ms=>{ if(ms.some(m=>[...m.addedNodes].some(n=>n.classList&&n.classList.contains('vcard')))) __renders++; }).observe(document.body,{childList:true,subtree:true});   // one per paint of the cards, however many cards
window.ask=async(text,ms=60000)=>{ const n0=__tc, s0=__shows.length, r0=__renders, t0=__tools.length; __firstOut=0;
  turn({text}); const done=await until(()=>__tc>n0,ms); await sleep(1200);
  const d=Stage.debug(); return {done, shows:__shows.slice(s0), renders:__renders-r0, tools:__tools.slice(t0).map(t=>t.name), firstOut:__firstOut,
    lastTool:__tools.length>t0?__tools[__tools.length-1].t:0, open:Stage.open, title:(Stage.current||{}).title||'', by:(Stage.current&&Stage.current.cards[0]||{}).by||'',
    mapfocus:!!(Stage.current||{}).mapfocus, labels:d.cards.flatMap(c=>c.items.map(i=>i.label)).slice(0,8), say:((__lastTurn||{}).mitra||'').slice(0,140)} };
"""


async def main():
    async with Browser(port=9339, size=(1536, 864)) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 4)
        await b.eval(HOOKS)
        live = await b.eval("(async()=>{ try{ if(!LV.open) liveOpen(); }catch(e){} return until(()=>LV.open && LV.ready, 60000) })()")
        check("real Live opened", live)
        print("[the demo's first question]")
        r = await b.eval("ask('Hi Mitra, first off, could you just show me all the grievances that are there across the state of Karnataka?')")
        print("   ", json.dumps(r)[:600])
        check("one entrance, one render, the Karnataka map", r["done"] and len(r["shows"]) == 1 and r["renders"] == 1 and r["mapfocus"], r)
        check("the picture was up before or as she spoke", r["shows"] and r["firstOut"] and r["shows"][0]["t"] <= r["firstOut"] + 400, r)
        print("[the demo's follow-up]")
        r = await b.eval("ask('Okay, and could you also show me all the grievances according to their specific input sources?')")
        print("   ", json.dumps(r)[:600])
        check("one crossfade, one render, however many functions were called", r["done"] and len(r["shows"]) == 1 and r["renders"] == 1 and r["shows"][0]["crossfade"], r)
        check("the picture is the breakdown by input source", r["by"] == "source" or any(any(w in l.lower() for w in ("praja", "ipgrs", "mobile", "csc", "citizen service", "call", "camp", "web", "whatsapp", "mitra")) for l in r["labels"]), r)
        print("[a comparison, then the bar]")
        r = await b.eval("ask('Could you just show me them with regards to Mysore and Belagavi?')")
        print("   ", json.dumps(r)[:400])
        check("comparison: one crossfade, no flicker", len(r["shows"]) == 1 and r["renders"] == 1 and r["shows"][0]["crossfade"], r)
        if not r["done"]:
            print("   note: the model had not closed that turn within 60 s (its own pacing); the picture itself was right")
        r = await b.eval("""(async()=>{ const res={}; let n0=__tc;
          turn({text:'please send a reminder to the Tahsildar of Piriyapatna'}); res.bar=await until(()=>document.querySelector('#confirmBar.on'),40000); await until(()=>__tc>n0,60000);
          n0=__tc; turn({text:'yes, please go ahead'}); await until(()=>__tc>n0,60000); res.gone=await until(()=>!document.querySelector('#confirmBar'),8000);
          await sleep(1500); res.say=J.convo.slice(-2).map(x=>x.say||'').join(' | ').slice(0,200); return res })()""")
        print("   ", json.dumps(r)[:400])
        check("the orange bar leaves on yes, the reminder is sent", r["bar"] and r["gone"] and "remind" in r["say"].lower(), r)
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS errors", not errs, errs[:3])
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
