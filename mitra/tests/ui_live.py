"""Real-time UI test of the full-duplex client (headless Edge over CDP) against a Mitra instance (default: the test instance
on 8031 wired to the fake Live server). Types a full citizen filing into a live conversation, then an officer session, and
checks the mode pill, captions, conversation strip, panels, tap-to-close and JS errors. Screenshots go to the temp folder.
Usage: python tests/ui_live.py [base]"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8031"
TMP = Path(r"C:\Users\hp\AppData\Local\Temp")
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:300])


HELPERS = """
window.sleep=ms=>new Promise(r=>setTimeout(r,ms));
window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};
"""


async def main():
    async with Browser() as b:
        print("[citizen · live conversation by typing]")
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=citizen", 4)
        await b.eval(HELPERS)
        r = await b.eval("""(async()=>{
          const res={};
          turn({text:'the street light near the bus stand is not working'});
          res.opened=await until(()=>LV.open&&LV.ready); res.pill=$('#modePill').dataset.m;
          res.req=await until(()=>!!document.querySelector('#left .req .big'));
          await until(()=>J.convo.length>=1);
          for(const t of ['Piriyapatna','Attigodu','yes, file it']){const n=J.convo.length; turn({text:t}); await until(()=>J.convo.length>n,40000);}
          res.routed=await until(()=>!!document.querySelector('[data-id=routed]'),5000);
          res.routedText=(document.querySelector('[data-id=routed]')||{}).innerText||'';
          res.convo=J.convo.length; res.capWords=document.querySelectorAll('#capJv .w').length;
          res.convoBubbles=document.querySelectorAll('#right .convo .ex').length;
          res.audioBufs=J.convo.filter(x=>x.bufs&&x.bufs.length).length;
          res.liveClass=document.body.classList.contains('live');
          return res})()""")
        print("   ", json.dumps(r)[:400])
        check("typing opens a live conversation", r["opened"] and r["pill"] == "live", r)
        check("request card on screen", r["req"], r)
        check("filed and routed to PDO Attigodu", r["routed"] and "Attigodu" in r["routedText"], r)
        check("conversation strip has every exchange", r["convoBubbles"] >= 4, r)
        check("live captions word by word", r["capWords"] > 3, r)
        check("Mitra's streamed audio kept per exchange (replay)", r["audioBufs"] >= 3, r)
        await b.shot(TMP / "ui_live_citizen.png")
        r = await b.eval("(async()=>{const cv=$('#orb'),q=cv.getBoundingClientRect(),x=q.left+q.width/2,y=q.top+q.height/2,ev=t=>cv.dispatchEvent(new PointerEvent(t,{clientX:x,clientY:y,pointerId:5,bubbles:true}));"
                         "await until(()=>!LV.playing,15000); ev('pointerdown'); ev('pointerup'); await sleep(400); return {pill:$('#modePill').dataset.m, open:LV.open}})()")
        check("tapping the orb closes the conversation (standby)", not r["open"] and r["pill"] in ("standby", "cascade"), r)

        r = await b.eval("""(async()=>{ await until(()=>!LV.open,8000); const n=J.convo.length; await session(true);
          const opened=await until(()=>LV.open&&LV.ready,20000); const greeted=await until(()=>J.convo.length>n,30000);
          return {opened, greeted, pill:$('#modePill').dataset.m, said:(J.convo[J.convo.length-1]||{}).say||''}})()""")
        check("opening a screen greets in the live voice (conversation already open)", r["opened"] and r["greeted"] and r["pill"] == "live", r)

        print("[officer · live]")
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=officer", 4)
        await b.eval(HELPERS)
        r = await b.eval("""(async()=>{
          const res={};
          turn({text:'read my inbox'}); res.opened=await until(()=>LV.open&&LV.ready);
          res.inbox=await until(()=>!!document.querySelector('#left [data-id=inbox] .row'),30000);
          const n=J.convo.length; turn({text:'open the first one'}); await until(()=>J.convo.length>n,30000);
          res.case=!!document.querySelector('[data-id=case] .case');
          return res})()""")
        check("officer inbox + open case through the live session", r["opened"] and r["inbox"] and r["case"], r)
        await b.shot(TMP / "ui_live_officer.png")
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS exceptions", not errs, errs[:3])
    print(f"\n{ok}/{ok + fail} checks passed")


asyncio.run(main())
