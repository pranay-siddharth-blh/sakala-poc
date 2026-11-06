"""Where the frame time goes while a chart draws: CPU profile (self time per function) + frame rate, on the web desk and inside the
phone frame. Against the test instance on the fake Live (no credit). Usage: python tests/perf_probe.py [base] [web|phone|both]"""
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8031"
WHICH = next((a for a in sys.argv[1:] if a in ("web", "phone", "both")), "both")
HELP = "window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};"
Q = "compare all the cases between each department on the map"


async def profile(b, win, label, secs=5):
    await b.cmd("Profiler.enable")
    await b.cmd("Profiler.setSamplingInterval", interval=500)
    await b.cmd("Profiler.start")
    r = await b.eval(f"""(async()=>{{ const W={win}; let frames=0, worst=0, last=performance.now(), run=true;
      const tick=()=>{{ const n=performance.now(); worst=Math.max(worst,n-last); last=n; frames++; if(run) W.requestAnimationFrame(tick); }};
      W.requestAnimationFrame(tick); const t0=performance.now(); W.turn({{text:{json.dumps(Q)}}});
      await until(()=>W.eval('Stage.open && Stage.debug().cards.length>0'), 30000); await sleep({secs * 1000}); run=false;
      return {{fps:Math.round(frames/((performance.now()-t0)/1000)), worst:Math.round(worst), kinds:W.eval('Stage.debug()').cards.map(c=>c.kind)}} }})()""", timeout=90)
    prof = (await b.cmd("Profiler.stop"))["profile"]
    nodes = {n["id"]: n for n in prof["nodes"]}
    dt = Counter()
    for sid, d in zip(prof["samples"], prof["timeDeltas"]):
        n = nodes[sid]["callFrame"]
        url = n["url"].rsplit("/", 1)[-1].split("?")[0]
        dt[f"{n['functionName'] or '(anon)'} {url}:{n['lineNumber'] + 1}"] += d
    total = sum(dt.values())
    print(f"[{label}] {json.dumps(r)}  total sampled {total / 1000:.0f} ms")
    for k, v in dt.most_common(22):
        print(f"   {v / total * 100:5.1f}%  {k}")


async def main():
    if WHICH in ("web", "both"):
        async with Browser(port=9381, size=(1536, 864), gpu=("gpu" in sys.argv)) as b:
            await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 5)
            await b.eval(HELP)
            await b.eval("until(()=>!!J.sid && document.querySelector('#left .card'), 20000)")
            await asyncio.sleep(3)
            await profile(b, "window", "web")
    if WHICH in ("phone", "both"):
        async with Browser(port=9382, size=(1536, 864), gpu=("gpu" in sys.argv)) as b:
            await b.goto(f"{B}/?intro=0&noevents=1", 3)
            await b.eval(HELP)
            await b.eval("""(async()=>{ document.querySelector('#startApp').click(); await until(()=>document.querySelector('#phoneStage.on'), 5000);
              await sleep(800); document.querySelector('#iphFrame').src='/?app=1&intro=0&auto=1&noevents=1&livetest=1&p=cs';
              await sleep(1500); await until(()=>{const w=document.querySelector('#iphFrame').contentWindow; return w && w.document.readyState==='complete' && w.eval('typeof J!=="undefined" && !!J.sid')}, 25000);
              await until(()=>document.querySelector('#iphFrame').contentWindow.document.querySelector('#left .card'), 20000); await sleep(3000); })()""", timeout=90)
            await profile(b, "document.querySelector('#iphFrame').contentWindow", "phone")


asyncio.run(main())
