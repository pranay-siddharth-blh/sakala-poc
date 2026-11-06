"""Every web <-> app switch by voice, all three profiles, and the desk must be fully alive afterwards (19 Oct regression: after
"open the chief secretary view in web" from the phone the orb stopped drawing and the cards stayed invisible, because the page
behind the phone was left frozen). For each start profile P, each app profile Q and each web profile R:
web as P -> "switch me to the app view of Q" (phone opens, app runs Q) -> inside the app "switch me to the web view of R" ->
the phone grows into the desk; then: no phone stage left, the page is not frozen, the orb canvas has ink AND changes between
two frames, every side card is fully opaque, the right profile, no JS errors. Also web P -> app Q -> Back.
Usage: python tests/ui_switch_matrix.py [base]   (default http://localhost:8031, fake Live)"""
import asyncio
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

B = next((a for a in sys.argv[1:] if a.startswith("http")), "http://localhost:8031")
ONLY = [a for a in sys.argv[1:] if a in ("citizen", "officer", "cs")]
PROFS = ["citizen", "officer", "cs"]
NAME = {"citizen": "citizen", "officer": "officer", "cs": "chief secretary"}
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:360])


HELP = "window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};"
IN = "document.querySelector('#iphFrame').contentWindow"
ALIVE = """(async()=>{ const res={};
  await sleep(1600);
  res.stage=!!document.getElementById('phoneStage'); res.frozen=document.documentElement.classList.contains('phone-on');
  const ink=()=>{ const cv=document.getElementById('orb'); const x=cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data; let n=0, s=0; for(let i=3;i<x.length;i+=193){ if(x[i]>10){n++; s+=x[i-3]+x[i-2]+x[i-1];} } return [n,s]; };
  const a=ink(); await sleep(350); const b=ink(); res.orbInk=a[0]; res.orbMoves=a[1]!==b[1]||a[0]!==b[0];
  const cards=[...document.querySelectorAll('#left .card, #right .card')]; res.cards=cards.length;
  res.dim=cards.filter(c=>+getComputedStyle(c).opacity<.98 || getComputedStyle(c).visibility!=='visible').length;
  res.cols=[...document.querySelectorAll('.col.left,.col.right')].map(c=>+getComputedStyle(c).opacity).every(o=>o>.98);
  res.profile=J.profile; res.pill=(document.querySelector('.mode-pill')||{}).textContent||''; res.paused=!!J.paused;
  res.anims=[...document.getAnimations()].filter(a=>a.playState==='paused').length; return res })()"""


async def main():
    port = 9395 + (PROFS.index(ONLY[0]) if ONLY else 3)
    async with Browser(port=port, size=(1536, 864), gpu=True) as b:
        for P, Q, R in itertools.product(ONLY or PROFS, PROFS, PROFS):
            label = f"web {P} -> app {Q} -> web {R}"
            await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p={P}", 4)
            await b.eval(HELP)
            await b.eval("until(()=>!!J.sid && document.querySelector('#left .card, #right .card'), 20000)")
            r1 = await b.eval(f"""(async()=>{{ const res={{}}; turn({{text:'switch me to the app view of the {NAME[Q]}'}});
              res.on=await until(()=>document.querySelector('#phoneStage.on'), 15000);
              res.inside=await until(()=>{{try{{const w={IN}; return w && w.document.readyState==='complete' && w.eval('typeof J!=="undefined" && !!J.sid && J.started && J.profile==="{Q}"')}}catch(e){{return false}}}}, 25000);
              await until(()=>{IN}.document.querySelector('#left .card, #right .card'), 15000);
              await until(()=>{{const w={IN}; return !w.eval('J.busy') && !w.eval('J.speaking')}}, 20000); await sleep(400);
              {IN}.eval("turn({{text:'switch me to the web view of the {NAME[R]}'}})");
              res.expand=await until(()=>!document.querySelector('#phoneStage') || document.querySelector('#phoneStage.expand'), 20000);
              await until(()=>J.profile==='{R}' && !(typeof Portal!=='undefined' && Portal.busy), 25000);
              await until(()=>document.querySelector('#left .card, #right .card'), 15000);
              return res }})()""", timeout=120)
            r2 = await b.eval(ALIVE, timeout=60)
            good = r1.get("on") and r1.get("inside") and r1.get("expand") and not r2["stage"] and not r2["frozen"] and r2["orbInk"] > 50 and r2["orbMoves"] \
                and r2["cards"] > 0 and r2["dim"] == 0 and r2["cols"] and r2["profile"] == R and not r2["paused"] and r2["anims"] == 0
            check(label, good, (r1, r2))
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS exceptions across the matrix", not errs, errs[:3])
        # Back from the phone (not by voice) must also wake the desk
        for P in (ONLY or PROFS):
            await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p={P}", 4)
            await b.eval(HELP)
            await b.eval("until(()=>!!J.sid && document.querySelector('#left .card, #right .card'), 20000)")
            r1 = await b.eval(f"""(async()=>{{ const res={{}}; turn({{text:'open the phone app as the {NAME[P]}'}});
              res.on=await until(()=>document.querySelector('#phoneStage.on'), 15000); await sleep(2500);
              const bk=document.querySelector('#psBack'); if(bk) bk.click(); res.back=!!bk; await sleep(300); return res }})()""", timeout=60)
            r2 = await b.eval(ALIVE, timeout=60)
            check(f"web {P} -> app -> Back: the desk is alive", r1.get("on") and r1.get("back") and not r2["stage"] and not r2["frozen"] and r2["orbMoves"] and r2["dim"] == 0 and not r2["paused"], (r1, r2))
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
