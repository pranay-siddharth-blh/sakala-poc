"""Voice: a grievance in its officer's view (any grievance, any officer), and the Chief Secretary's greeting.
1. citizen files a grievance -> "can you show it to me in that specific officer's view" -> the portal opens that officer's desk
   (the officer it was routed to) and the case itself is open there;
2. CS: "open <id> as the officer handling it" -> that case's officer, case open;
3. the CS screen greets "Hello, Chief Secretary Madam".
Usage: python tests/ui_officer_view.py [base]   (default http://localhost:8031)"""
import asyncio
import json
import sys
import urllib.request
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


async def main():
    async with Browser(port=9345, size=(1536, 864)) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=citizen", 4)
        await b.eval(HELP)
        print("[citizen files, then asks for the officer's view]")
        r = await b.eval("""(async()=>{ const res={}; await until(()=>!!J.sid);
          const say=async t=>{const n=J.convo.length; turn({text:t}); await until(()=>J.convo.length>n,40000); await sleep(300)};
          await say('the street light near the bus stand in Attigodu is not working');
          for (const t of ['Attigodu','yes, file it']) { if (document.querySelector('[data-id=routed]')) break; await say(t); }
          res.routed=await until(()=>!!document.querySelector('[data-id=routed]'),8000);
          res.cid=(document.querySelector('[data-id=routed]')||{}).innerText.match(/GR-\\d+/)?.[0];
          await until(()=>!J.busy && !J.speaking && !LV.playing, 15000); await sleep(500);
          turn({text:"can you show it to me in that specific officer's view"});
          res.portal=await until(()=>!!document.querySelector('#portal.in'), 15000); res.title=(document.querySelector('#ptTitle')||{}).textContent;
          await until(()=>!Portal.busy && J.profile==='officer', 15000);
          res.caseOpen=await until(()=>{const c=document.querySelector('#right [data-id=case]'); return c && c.innerText.includes(res.cid)}, 30000);
          res.profile=J.profile; res.officer=J.officer; return res})()""")
        print("   ", json.dumps(r))
        owner = None
        if r.get("cid"):
            owner = json.loads(urllib.request.urlopen(f"http://localhost:8020/api/case/{r['cid']}", timeout=20).read()).get("owner")
        check("filed and routed", r["routed"] and r["cid"], r)
        check("'show it to me in that specific officer's view' -> the portal opens the routed officer's desk", r["portal"] and r["profile"] == "officer" and r["officer"] == owner, (r, owner))
        check("... with that very case open", r["caseOpen"], r)
        await b.shot(TMP / "officer_view.png")
        print("[CS: a grievance number in its officer's view; the greeting]")
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 4)
        await b.eval(HELP)
        r = await b.eval("""(async()=>{ const res={}; await until(()=>!!J.sid && document.querySelector('#left .card'));
          const n0=J.convo.length; turn({text:'hello'}); await until(()=>J.convo.length>n0, 20000); res.greet=(J.convo[J.convo.length-1]||{}).say||'';
          await until(()=>!J.busy && !J.speaking && !LV.playing, 15000); await sleep(400);
          turn({text:'open GR-493168 as the officer handling it'});
          await until(()=>!!document.querySelector('#portal.in'), 15000); await until(()=>!Portal.busy && J.profile==='officer', 15000);
          res.caseOpen=await until(()=>{const c=document.querySelector('#right [data-id=case]'); return c && c.innerText.includes('GR-493168')}, 30000);
          res.officer=J.officer; return res})()""")
        print("   ", json.dumps(r))
        check("the Chief Secretary is greeted 'Hello, Chief Secretary Madam'", r["greet"].startswith("Hello, Chief Secretary Madam"), r["greet"][:80])
        check("'open GR-493168 as the officer handling it' -> Tahsildar Piriyapatna's desk with the case open", r["officer"] == "tah_piriyapatna" and r["caseOpen"], r)
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS exceptions", not errs, errs[:3])
    print(f"\n{ok} passed, {fail} failed")


asyncio.run(main())
