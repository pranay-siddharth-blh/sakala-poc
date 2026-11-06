"""The resolution loop on the citizen's screen (web and phone): the officer's report arrives as a resolution card with
Yes / No; "no" re-opens the case and the ladder climbs one rung (L1 -> L2) with a fresh clock; "yes" closes it.
1. file -> officer resolves (POC API) -> the citizen screen shows the resolution card (ring, report, two buttons);
2. "no, it is not solved" -> the card becomes the ladder: the resolver rejected, the senior holds it now, clock restarted;
   the case is really with the senior in the POC;
3. a second case, tap "Yes" -> closed card; the case is Resolved and the confirmation is on the file;
4. the same card inside the phone frame (393 px), light mode, no JS errors.
Usage: python tests/ui_resolution.py [base]   (default http://localhost:8031, the test instance on the fake Live)"""
import asyncio
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8031"
POC = "http://localhost:8020"
TMP = Path(r"C:\Users\hp\AppData\Local\Temp")
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:320])


def poc(path, body=None):
    req = urllib.request.Request(POC + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


HELP = "window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};"
FILE = """(async()=>{ const res={}; await until(()=>!!J.sid); try{dropPanel('routed','right')}catch(e){}; await sleep(200);
  const say=async t=>{const n=J.convo.length; turn({text:t}); await until(()=>J.convo.length>n,40000); await sleep(300)};
  await say(%s);
  for (const t of ['Attigodu','yes, file it']) { if (document.querySelector('[data-id=routed]')) break; await say(t); }
  res.routed=await until(()=>!!document.querySelector('[data-id=routed]'),8000);
  res.cid=((document.querySelector('[data-id=routed]')||{}).innerText||'').match(/GR-\\d+/)?.[0];
  res.said=J.convo.slice(-4).map(x=>(x.you||'')+' => '+(x.say||'').slice(0,300)); res.flow=J.lastFlow||'';
  await until(()=>!J.busy && !J.speaking, 15000); return res})()"""
ATR = "Inspected the spot on 19 October, the street light near the bus stand was repaired, a new fixture fitted and it was switched on at night."


WATER = "Inspected Attigodu on 19 October: the broken pipeline at the village tank was replaced and drinking water supply was restored to every street; checked with residents."
DRAIN = "Cleared the blocked drain near the school in Attigodu on 19 October with the GP team, removed the silt and checked that water now flows freely."


def resolve(cid, atr=ATR):
    c = poc(f"/api/case/{cid}")
    r = poc(f"/api/cases/{cid}/action", {"action": "resolve", "officer": c["owner"], "atr": atr})
    return c["owner"], r


async def main():
    async with Browser(port=9351, size=(1536, 864)) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=citizen", 4)
        await b.eval(HELP)
        print("[the officer's report arrives as a resolution card]")
        r = await b.eval(FILE % "'the street light near the bus stand in Attigodu is not working'")
        check("filed and routed", r["routed"] and r["cid"], r)
        cid = r["cid"]
        owner, rr = resolve(cid)
        check("officer resolved it (POC)", rr.get("score", 0) >= 4, rr)
        r = await b.eval("""(async()=>{ const res={}; await citizenUpdates(); await until(()=>!!document.querySelector('#right .resv'),8000);
          const c=document.querySelector('#right .resv'); res.card=!!c; res.btns=c?c.querySelectorAll('.yn button').length:0; res.text=c?c.innerText:'';
          res.ring=!!(c&&c.querySelector('.ring .arc')); res.opts=(J.lastOptions||[]).length; return res})()""")
        check("resolution card with the report and two choices", r["card"] and r["btns"] == 2 and "actually solved" in r["text"] and "repaired" in r["text"], r)
        check("the check ring draws", r["ring"], r)
        await b.shot(TMP / "res_card.png")
        print("[no -> re-opened, one rung up the ladder]")
        r = await b.eval("""(async()=>{ const res={}; const n=J.convo.length; turn({text:'no, it is not solved'}); await until(()=>J.convo.length>n,40000);
          res.reopened=await until(()=>!!document.querySelector('#right .resv.reopened'),10000);
          const c=document.querySelector('#right .resv.reopened'); res.text=c?c.innerText:'';
          res.rungs=[...document.querySelectorAll('#right .ladder .rung')].map(x=>x.className.replace('rung','').trim()+':'+x.innerText.replace(/\\s+/g,' '));
          res.cur=((document.querySelector('#right .ladder .rung.cur')||{}).innerText||'').toLowerCase();
          await until(()=>J.convo.some(x=>/up the ladder/.test(x.say||'')),8000); res.say=(J.convo.find(x=>/up the ladder/.test(x.say||''))||{}).say||'';
          res.stages=[...document.querySelectorAll('#right .pipe .step.done, #right .pipe .step.warn')].length; return res})()""")
        c = poc(f"/api/case/{cid}")
        check("the card turns into the ladder", r["reopened"] and "moved up the ladder" in r["text"] and "Clock restarted" in r["text"], r)
        check("L1 rejected, the senior holds it now", any(x.startswith("passed") and "rejected" in x.lower() for x in r["rungs"]) and "holds it now" in r["cur"] and "l2" in r["cur"], r["rungs"])
        check("Mitra says it moved up the ladder with a fresh clock", "up the ladder" in r["say"] and "days" in r["say"], r["say"])
        check("the case really is with the senior, re-opened, clock restarted", c["status"] == "Pending" and c["owner"] != owner and c["level"] == "L2"
              and any("Re-opened by the citizen" in h["what"] for h in c["history"]), (c["status"], c["owner"], c["level"]))
        check("the pipeline rail shows escalation + clock + leadership", r["stages"] >= 3, r["stages"])
        await b.shot(TMP / "res_ladder.png")
        print("[yes -> closed]")
        r = await b.eval(FILE % "'there is no drinking water in Attigodu for three days'")
        check("second request filed", r["routed"] and r["cid"], r)
        cid2 = r["cid"]
        owner2, rr = resolve(cid2, WATER)
        check("officer resolved the water case (POC)", rr.get("score", 0) >= 4, rr)
        r = await b.eval("""(async()=>{ const res={}; await citizenUpdates(); await until(()=>!!document.querySelector('#right .resv .yn .yes'),8000);
          const n=J.convo.length; document.querySelector('#right .resv .yn .yes').click(); await until(()=>J.convo.length>n,40000);
          res.closed=await until(()=>!!document.querySelector('#right .resv.closed'),10000);
          res.text=(document.querySelector('#right .resv.closed')||{}).innerText||''; await until(()=>J.convo.some(x=>/is closed/.test(x.say||'')),8000);
          res.say=(J.convo.find(x=>/is closed/.test(x.say||''))||{}).say||''; return res})()""")
        c = poc(f"/api/case/{cid2}")
        check("tapping Yes closes it with thanks", r["closed"] and "Closed" in r["text"] and "closed" in r["say"].lower(), r)
        check("the case is Resolved and the confirmation is on the file", c["status"] == "Resolved" and any("Citizen confirmed" in h["what"] for h in c["history"]), c["history"][-2:])
        errs = [e for e in b.events if "favicon" not in str(e)]
        check("no JS errors (web)", not errs, errs[:3])
    print("[inside the phone, light mode]")
    async with Browser(port=9352, size=(393, 852)) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=citizen&app=1&intro=0", 4)
        await b.eval(HELP)
        r = await b.eval(FILE % "'the street light in front of the temple in Attigodu is not working'")
        check("filed in the app", r["routed"] and r["cid"], r)
        _, rr = resolve(r["cid"], "Inspected the street light in front of the temple in Attigodu on 19 October, replaced the fused fixture and confirmed it lights up at night.")
        check("officer resolved the case filed in the app (POC)", rr.get("score", 0) >= 4, rr)
        r = await b.eval("""(async()=>{ const res={}; await citizenUpdates(); res.card=await until(()=>!!document.querySelector('#right .resv'),8000);
          const c=document.querySelector('#right .resv'); const rc=c?c.getBoundingClientRect():{}; res.w=rc.width|0; res.fits=rc.right<=innerWidth+1&&rc.left>=-1; res.vw=innerWidth;
          res.light=document.documentElement.dataset.theme!=='dark'; res.sheet=document.querySelector('#msheet')?.dataset.s||document.querySelector('.msheet')?.dataset.s||'';
          res.btnsWide=[...c.querySelectorAll('.yn button')].every(x=>x.getBoundingClientRect().height>=36); return res})()""")
        check("the resolution card fits the phone, light theme, big enough to tap", r["card"] and r["fits"] and r["light"] and r["btnsWide"], r)
        await b.shot(TMP / "res_phone.png")
        errs = [e for e in b.events if "favicon" not in str(e)]
        check("no JS errors (phone)", not errs, errs[:3])
    print(f"\n{ok}/{ok + fail} checks passed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
