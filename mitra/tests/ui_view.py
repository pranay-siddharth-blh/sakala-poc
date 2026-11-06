"""Web desk <-> phone app by voice, with any profile, in a real headless browser (CDP):
1. on the web desk (CS) "switch me to the app view of the citizen" -> the phone rises over the desk (which stops listening),
   the app inside starts by itself as the citizen;
2. inside the phone "switch me to the web view of the chief secretary" -> the phone grows into the desk, the desk is the CS's;
3. from the start page: Start app -> inside the phone "take me to the web view of the officer" -> the web desk starts as the officer.
Usage: python tests/ui_view.py [base]   (default http://localhost:8031)"""
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
        fail += 1; print("  FAIL", name, " <-", str(detail)[:320])


HELP = "window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};"
IN = "document.querySelector('#iphFrame').contentWindow"


async def main():
    async with Browser(port=9343, size=(1536, 864)) as b:
        print("[web desk -> app, by voice]")
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 4)
        await b.eval(HELP)
        r = await b.eval(f"""(async()=>{{ const res={{}}; await until(()=>!!J.sid && document.querySelector('#left .card'));
          turn({{text:'switch me to the app view of the citizen'}});
          res.on=await until(()=>document.querySelector('#phoneStage.on'), 15000); res.solo=!!document.querySelector('#phoneStage.solo');
          res.paused=!!J.paused; res.over=document.body.classList.contains('app-over'); res.src=document.querySelector('#iphFrame').getAttribute('src');
          res.inside=await until(()=>{{const w={IN}; return w && w.document.readyState==='complete' && w.eval('typeof J!=="undefined" && !!J.sid && J.started')}}, 25000);
          res.profileInside={IN}.eval('J.profile'); return res}})()""")
        print("   ", json.dumps(r))
        check("the phone rises over the desk (its own backdrop), the desk stops listening", r["on"] and r["solo"] and r["paused"] and r["over"], r)
        check("the app inside starts by itself as the citizen", "p=citizen" in r["src"] and "go=1" in r["src"] and r["inside"] and r["profileInside"] == "citizen", r)
        await b.shot(TMP / "view_web_to_app.png")
        print("[app -> web desk, by voice, another profile]")
        r = await b.eval(f"""(async()=>{{ const res={{}}; const w={IN};
          await until(()=>!w.eval('J.busy') && !w.eval('J.speaking'), 20000); await sleep(400);
          w.eval("turn({{text:'switch me to the web view of the chief secretary'}})");
          res.gone=await until(()=>!document.querySelector('#phoneStage'), 15000); await until(()=>!Portal.busy, 8000); await sleep(600);
          res.profile=J.profile; res.over=document.body.classList.contains('app-over'); res.paused=!!J.paused; return res}})()""")
        print("   ", json.dumps(r))
        check("the phone grows into the web desk; the desk is the Chief Secretary's and listening again", r["gone"] and r["profile"] == "cs" and not r["over"] and not r["paused"], r)
        await b.eval("(async()=>{await sleep(200)})()")
        r = await b.eval(f"""(async()=>{{ const res={{}}; turn({{text:'open the phone app as the officer'}});
          res.on=await until(()=>document.querySelector('#phoneStage.on'), 15000);
          res.inside=await until(()=>{{const w={IN}; return w && w.document.readyState==='complete' && w.eval('typeof J!=="undefined" && !!J.sid && J.started')}}, 25000);
          res.p={IN}.eval('J.profile'); document.querySelector('#psBack').click(); await sleep(1200);
          res.back=!document.querySelector('#phoneStage'); res.paused=!!J.paused; return res}})()""")
        print("   ", json.dumps(r))
        check("'open the phone app as the officer' -> the app as the officer; Back returns to the desk, listening again", r["on"] and r["inside"] and r["p"] == "officer" and r["back"] and not r["paused"], r)
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS exceptions", not errs, errs[:3])
    print("[start page -> app -> web desk as the officer]")
    async with Browser(port=9344, size=(1536, 864)) as b:
        await b.goto(f"{B}/?intro=0&noevents=1", 3)
        await b.eval(HELP)
        r = await b.eval(f"""(async()=>{{ const res={{}}; document.querySelector('#startApp').click();
          await until(()=>document.querySelector('#phoneStage.on'), 5000);
          document.querySelector('#iphFrame').src='/?app=1&intro=0&auto=1&noevents=1&p=citizen';
          res.inside=await until(()=>{{const w={IN}; return w && w.location.search.includes('auto=1') && w.document.readyState==='complete' && w.eval('typeof J!=="undefined" && !!J.sid')}}, 25000);
          {IN}.eval("turn({{text:'take me to the web view of the officer'}})");
          res.started=await until(()=>J.started && J.sid && !document.querySelector('#phoneStage'), 20000); await sleep(1500);
          res.profile=J.profile; res.splash=document.querySelector('#splash').classList.contains('off'); return res}})()""")
        print("   ", json.dumps(r))
        check("from the start page's phone: the web desk starts as the officer (the splash hands over)", r["inside"] and r["started"] and r["profile"] == "officer" and r["splash"], r)
        await b.shot(TMP / "view_app_to_web.png")
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS exceptions", not errs, errs[:3])
    print(f"\n{ok} passed, {fail} failed")


asyncio.run(main())
