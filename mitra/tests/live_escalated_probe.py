"""On the REAL Gemini Live (8030): Pranay's exact question 'show me all the grievances that are auto-escalated' must draw the
escalated slice, never the Karnataka board; then the board question, with a screenshot of the composer on the board in
dark and light for a look. Two live turns. Usage: python tests/live_escalated_probe.py [base]"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8030"
OUT = Path(r"C:\Users\hp\AppData\Local\Temp\claude\d--Sakala-POC\5a14e85d-b0dc-4b15-b24d-03ede69632a9\scratchpad")
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:360])


async def main():
    async with Browser(port=9342, size=(1917, 925)) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 4)
        await b.eval("window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};"
                     "window.__tc=0; window.__lastTurn=null; const _le=lvEvent; lvEvent=function(e){ if(e.type==='turn_complete'){__tc++; __lastTurn=e;} return _le(e); };")
        await b.eval("(async()=>{ try{ if(!LV.open) liveOpen(); }catch(e){} return until(()=>LV.open && LV.ready, 60000) })()")
        r = await b.eval("""(async()=>{ const n0=__tc; turn({text:'show me all the grievances that are auto-escalated'}); const done=await until(()=>__tc>n0, 60000); await sleep(1200);
          const cur=Stage.current||{}; return {done, intent:(__lastTurn||{}).intent||'', say:((__lastTurn||{}).mitra||'').slice(0,160), board:!!cur.board, title:cur.title||'', cards:(cur.cards||[]).map(c=>c.title).slice(0,4)} })()""")
        print("   ", json.dumps(r))
        check("the real model + the harness: 'auto-escalated' is a slice (not the board) and the answer talks about escalated cases",
              r["done"] and not r["board"] and "escalat" in r["say"].lower(), r)
        r = await b.eval("""(async()=>{ const n0=__tc; turn({text:'how is Karnataka doing'}); await until(()=>Stage.open && document.body.classList.contains('board-on'), 60000); await until(()=>__tc>n0, 60000); await sleep(1500);
          const e=document.querySelector('#mic'), rr=e.getBoundingClientRect(), t=document.elementFromPoint(rr.x+rr.width/2, rr.y+rr.height/2); return {board:document.body.classList.contains('board-on'), micTop:e.contains(t)} })()""")
        check("the board is up and the mic is under the pointer on the real desk", r["board"] and r["micTop"], r)
        await b.shot(OUT / "board_dark.png")
        await b.eval("Theme.set('light')"); await asyncio.sleep(1.8)
        await b.shot(OUT / "board_light.png")
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
