"""Real Gemini Live, real browser: the questions Pranay asks, on the web desk and inside the phone. For each: which function Live
called, seconds from the question to the first chart, whether a map card exists and its canvas has ink, whether every card sits
inside the screen, and the frame rate while it draws. Usage: python tests/live_viz_probe.py [base] [web|phone|both]
(default http://localhost:8030, both). Uses real Live credit (a few turns)."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8030"
WHICH = sys.argv[2] if len(sys.argv) > 2 else "both"
TMP = Path(r"C:\Users\hp\AppData\Local\Temp")
QS = [
    ("map", "first of everything, can you show me all the grievances across the map of Karnataka?"),
    ("map", "which district has the most open cases? show it on the map"),
    ("bars", "compare Piriyapatna, Hunsur and Mysuru taluks"),
    ("map", "compare the Revenue, RDPR and Food departments on the Karnataka map"),
    ("nav", "take me back to the dashboard"),
]
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:400])


HELP = "window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};"

# runs inside the Mitra window W (the page itself, or the phone's iframe); measured from the parent's clock
ASK = """(async(W, q, want)=>{ const res={q}; const d=W.document, J=W.eval('J');
  const prevN=J.convo.length, t0=performance.now();
  W.eval("Stage.open && Stage.exit()"); await sleep(900);
  const t1=performance.now(); W.turn({text:q});
  // frames while it works: count rAF ticks in the Mitra window for 8 s
  let frames=0, worst=0, last=performance.now(); let run=true; const tick=()=>{ const n=performance.now(); worst=Math.max(worst,n-last); last=n; frames++; if(run) W.requestAnimationFrame(tick); }; W.requestAnimationFrame(tick);
  if (want==='nav') { res.home=await until(()=>!W.eval('Stage.open'), 30000); res.t=+((performance.now()-t1)/1000).toFixed(1); run=false; res.say=(J.convo[J.convo.length-1]||{}).say||''; return res; }
  res.stage=await until(()=>W.eval('Stage.open && Stage.debug().cards.length>0'), 40000);
  res.t=+((performance.now()-t1)/1000).toFixed(1);
  await sleep(4500); run=false;
  res.fps=Math.round(frames/((performance.now()-t1)/1000)); res.worstFrameMs=Math.round(worst);
  const dbg=W.eval('Stage.debug()'); res.kinds=dbg.cards.map(c=>c.kind); res.items=dbg.cards.map(c=>c.items.length);
  const vw=W.innerWidth, vh=W.innerHeight;
  res.cards=[...d.querySelectorAll('#stageCards .vcard')].map(c=>{ const r=c.getBoundingClientRect(); const cv=c.querySelector('canvas');
    let ink=0; if(cv&&cv.width){ const x=cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data; for(let i=3;i<x.length;i+=97){ if(x[i]>20) ink++; } }
    return {k:(c.className.match(/k-(\w+)/)||[])[1]||'', x:Math.round(r.left), y:Math.round(r.top), w:Math.round(r.width), h:Math.round(r.height), inside:r.left>=-1&&r.top>=-1&&r.right<=vw+1&&r.bottom<=vh+1, ink, cw:cv?cv.width:0, ch:cv?cv.height:0}; });
  await until(()=>J.convo.length>prevN, 30000); const lc=J.convo[J.convo.length-1]||{}; res.say=(lc.say||'').slice(0,160); res.intent=lc.intent||'';
  return res})"""


async def run(b, label, win_expr):
    print(f"[{label}]")
    for want, q in QS:
        r = await b.eval(f"({ASK})({win_expr}, {json.dumps(q)}, {json.dumps(want)})", timeout=120)
        print("   ", json.dumps(r)[:900])
        if want == "nav":
            check(f"{label}: '{q}' closes the chart", r.get("home"), r)
            continue
        got = r.get("stage") and r.get("cards")
        check(f"{label}: '{q[:50]}' -> a chart appears ({r.get('t')} s)", got and r["t"] <= 12, r)
        if want == "map":
            m = [c for c in r.get("cards", []) if "map" in (c["k"] or "") or "map" in r.get("kinds", [])]
            check(f"{label}: ... it is the Karnataka map", "map" in r.get("kinds", []), r.get("kinds"))
        check(f"{label}: ... drawn (canvas has ink)", all(c["ink"] > 30 for c in r.get("cards", [])) and r.get("cards"), r.get("cards"))
        check(f"{label}: ... every card inside the screen", all(c["inside"] for c in r.get("cards", [])) and r.get("cards"), r.get("cards"))
        check(f"{label}: ... smooth while it draws ({r.get('fps')} fps, worst frame {r.get('worstFrameMs')} ms)", (r.get("fps") or 0) >= 50, r.get("fps"))
        await b.shot(TMP / f"probe_{label}_{QS.index((want, q))}.png")


async def main():
    if WHICH in ("web", "both"):
        async with Browser(port=9371, size=(1536, 864), gpu=True) as b:
            await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 5)
            await b.eval(HELP)
            await b.eval("until(()=>!!J.sid && document.querySelector('#left .card'), 20000)")
            await asyncio.sleep(4)
            await run(b, "web", "window")
            check("web: no JS exceptions", not [e for e in b.events if e[0] == "exception"], b.events[:3])
    if WHICH in ("phone", "both"):
        async with Browser(port=9372, size=(1536, 864), gpu=True) as b:
            await b.goto(f"{B}/?intro=0&noevents=1", 3)
            await b.eval(HELP)
            await b.eval("""(async()=>{ document.querySelector('#startApp').click(); await until(()=>document.querySelector('#phoneStage.on'), 5000);
              await sleep(800); document.querySelector('#iphFrame').src='/?app=1&intro=0&auto=1&noevents=1&livetest=1&p=cs';
              await sleep(1500); await until(()=>{const w=document.querySelector('#iphFrame').contentWindow; return w && w.document.readyState==='complete' && w.eval('typeof J!=="undefined" && !!J.sid')}, 25000);
              await until(()=>document.querySelector('#iphFrame').contentWindow.document.querySelector('#left .card'), 20000); await sleep(4000); })()""", timeout=90)
            await run(b, "phone", "document.querySelector('#iphFrame').contentWindow")
            check("phone: no JS exceptions", not [e for e in b.events if e[0] == "exception"], b.events[:3])
    print(f"\n{ok} passed, {fail} failed")


asyncio.run(main())
