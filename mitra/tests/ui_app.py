"""Mitra as a phone app, in a real headless browser (CDP):
1. desktop: the splash offers "Start web" and "Start app"; Start app raises the phone with the real Mitra inside (393 x 852),
   "Behind the app" follows it (profile, pipeline steps, what was heard and said); Back returns to the start page;
2. inside the phone: the phone layout (compact header with the profile switcher, the orb, the composer at the thumb, the side
   columns in a bottom sheet with tabs that rise by themselves), profile switching through the portal, charts on the stage;
3. a real phone-sized window (393 x 852): the same layout, nothing wider than the screen.
Usage: python tests/ui_app.py [base]   (default http://localhost:8031)"""
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
    async with Browser(port=9341, size=(1536, 864)) as b:
        print("[desktop: Start app]")
        await b.goto(f"{B}/?intro=0&noevents=1", 3)
        await b.eval(HELP)
        r = await b.eval("""(async()=>{ const res={}; res.web=!!document.querySelector('#start'); res.app=!!document.querySelector('#startApp');
          res.webTxt=document.querySelector('#start').innerText.trim(); document.querySelector('#startApp').click();
          res.on=await until(()=>document.querySelector('#phoneStage.on'), 4000);
          res.frame=await until(()=>{const w=document.querySelector('#iphFrame').contentWindow; return w && w.document.readyState==='complete' && w.document.querySelector('#splash')}, 15000);
          const w=document.querySelector('#iphFrame').contentWindow; res.vw=w.innerWidth; res.vh=w.innerHeight; res.inapp=w.document.documentElement.classList.contains('inapp');
          res.appBtnInside=getComputedStyle(w.document.querySelector('#startApp')).display; res.startInside=w.document.querySelector('#start').innerText.trim();
          const ph=document.querySelector('#iph').getBoundingClientRect(); res.phone=[Math.round(ph.width),Math.round(ph.height)]; res.fits=ph.bottom<=innerHeight && ph.top>=0;
          return res})()""")
        print("   ", json.dumps(r))
        check("the splash has Start web and Start app", r["web"] and r["app"] and "web" in r["webTxt"].lower(), r)
        check("Start app raises the phone; inside runs Mitra at phone size (393 x 852) in app mode", r["on"] and r["frame"] and r["vw"] == 393 and r["vh"] == 852 and r["inapp"], r)
        check("inside the phone there is one Start (no Start app)", r["appBtnInside"] == "none" and r["startInside"] == "Start", r)
        check("the phone fits the window", r["fits"], r["phone"])
        await b.shot(TMP / "app_stage_splash.png")
        # drive the app inside the phone (typed, against the fake live voice)
        await b.eval(f"window.__old={IN}; document.querySelector('#iphFrame').src='/?app=1&intro=0&auto=1&noevents=1&livetest=1&p=officer'")
        r = await b.eval(f"""(async()=>{{ const res={{}};
          await until(()=>{{const w={IN}; return w && w!==window.__old && w.location.search.includes('auto=1') && w.document.readyState==='complete' && w.eval('typeof J!=="undefined" && !!J.sid')}}, 20000);
          const w={IN}, d=w.document; await until(()=>d.querySelector('#left .card'), 15000); await sleep(800);
          res.m=d.body.classList.contains('m'); res.header=Math.round(d.querySelector('.top').getBoundingClientRect().height);
          res.profInHeader=!!d.querySelector('.hdr-right #prof'); res.sheet=!!d.querySelector('.msheet'); res.tabs=[...d.querySelectorAll('.ms-tabs .ms-l')].map(x=>x.textContent);
          res.sheetState=d.querySelector('.msheet').dataset.s; res.inSheet=!!d.querySelector('.msheet #left .card');
          const c=d.querySelector('.composer').getBoundingClientRect(); res.composer=[Math.round(c.left),Math.round(c.right),Math.round(c.bottom)];
          res.orb=Math.round(d.querySelector('.orb-wrap').getBoundingClientRect().width);
          res.overflow=d.documentElement.scrollWidth>w.innerWidth+1;
          res.behind=document.querySelector('#psProf b').textContent;
          return res}})()""")
        print("   ", json.dumps(r))
        check("phone layout: compact header with the profile switcher in it", r["m"] and r["header"] <= 60 and r["profInHeader"], r)
        check("the side columns live in a bottom sheet with the officer's tabs (Inbox / Case)", r["sheet"] and r["tabs"] == ["Inbox", "Case"] and r["inSheet"], r)
        check("the orb fits the phone and the composer sits at the thumb, nothing wider than the screen",
              180 <= r["orb"] <= 320 and r["composer"][0] >= 0 and r["composer"][1] <= 393 and r["composer"][2] < 852 and not r["overflow"], r)
        check("'Behind the app' shows the profile inside the phone", r["behind"] == "Officer", r["behind"])
        await b.shot(TMP / "app_officer.png")
        r = await b.eval(f"""(async()=>{{ const res={{}}; const w={IN}, d=w.document;
          w.eval("turn({{text:'read my inbox'}})"); await until(()=>d.querySelector('.msheet').dataset.s!=='peek', 20000);
          res.raised=d.querySelector('.msheet').dataset.s; res.tab=d.querySelector('.msheet').dataset.t;
          await sleep(600); w.eval("turn({{text:'open the first one'}})"); await until(()=>d.querySelector('#right [data-id=case]'), 20000); await sleep(700);
          res.caseTab=d.querySelector('.msheet').dataset.t; res.steps=[...document.querySelectorAll('#psSteps .ps-st')].map(s=>s.className.replace('ps-st','').trim());
          res.heard=document.querySelector('#psYou').textContent; res.said=document.querySelector('#psJv').textContent;
          return res}})()""")
        print("   ", json.dumps(r))
        check("asking for the inbox raises the sheet on the Inbox tab", r["raised"] in ("half", "full") and r["tab"] == "left", r)
        check("opening a case switches the sheet to the Case tab", r["caseTab"] == "right", r)
        check("'Behind the app' follows the pipeline and what was heard and said", any("done" in s for s in r["steps"]) and "first" in r["heard"].lower() and len(r["said"]) > 10, r)
        await b.shot(TMP / "app_case.png")
        r = await b.eval(f"""(async()=>{{ const res={{}}; const w={IN}, d=w.document;
          w.eval("switchTo('cs')"); await sleep(300); res.portal=!!d.querySelector('#portal.in'); await until(()=>!w.eval('Portal.busy'), 8000); await sleep(600);
          res.tabs=[...d.querySelectorAll('.ms-tabs .ms-l')].map(x=>x.textContent); res.behind=document.querySelector('#psProf b').textContent;
          w.eval("turn({{text:'compare all the cases between each department on the map'}})");
          res.stage=await until(()=>w.eval("Stage.open && Stage.debug().cards[0] && Stage.debug().cards[0].kind==='map'"), 30000); await sleep(2500);
          const v=d.querySelector('.vcard').getBoundingClientRect(); res.card=[Math.round(v.left),Math.round(v.right)]; res.sheetHidden=getComputedStyle(d.querySelector('.msheet')).transform!=='none';
          return res}})()""")
        print("   ", json.dumps(r))
        check("profile switch inside the phone goes through the portal; tabs become the CS's (State / Activity)", r["portal"] and r["tabs"] == ["State", "Activity"] and r["behind"] == "Chief Secretary", r)
        check("a chart on the phone: the map card fits the screen, the sheet steps aside", r["stage"] and r["card"][0] >= 0 and r["card"][1] <= 393 and r["sheetHidden"], r)
        await b.shot(TMP / "app_map.png")
        r = await b.eval("""(async()=>{ document.querySelector('#psBack').click(); await sleep(1200);
          return {gone:!document.querySelector('#phoneStage'), card:getComputedStyle(document.querySelector('#splash .sp-card')).visibility}})()""")
        check("Back returns to the start page", r["gone"] and r["card"] == "visible", r)
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS exceptions (desktop + inside the phone)", not errs, errs[:3])
    print("[a real phone-sized window]")
    async with Browser(port=9342, size=(393, 852)) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=citizen", 5)
        await b.eval(HELP)
        r = await b.eval("""(async()=>{ await until(()=>document.querySelector('#left .card'), 15000); await sleep(500);
          return {m:document.body.classList.contains('m'), w:innerWidth, over:document.documentElement.scrollWidth>innerWidth+1, tabs:[...document.querySelectorAll('.ms-tabs .ms-l')].map(x=>x.textContent),
                  composerBottom:Math.round(document.querySelector('.composer').getBoundingClientRect().bottom), h:innerHeight}})()""")
        print("   ", json.dumps(r))
        check("a phone-sized window gets the phone layout (citizen tabs: My request / Updates), no sideways scroll",
              r["m"] and not r["over"] and r["tabs"] == ["My request", "Updates"] and r["composerBottom"] < r["h"], r)
        await b.shot(TMP / "app_native_citizen.png")
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS exceptions on a phone", not errs, errs[:3])
    print(f"\n{ok} passed, {fail} failed")


asyncio.run(main())
