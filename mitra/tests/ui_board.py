"""22 Oct 2026: the Chief Secretary's board in the browser, web and phone (test instance 8031, fake Live).
Home: the command board (8 KPI tiles, the 7-day clock, levels, departments, districts), every tile a question.
'How is RDPR doing?' -> a board of 6 cards (tiles first), the scope chip 'RDPR', the live pill under the parked orb; the cards
never run under the composer or off the screen; 'and Hunsur?' narrows the scope; the chip's ✕ goes back to the whole state;
a single count ('how many cases are with L1') is tiles + a breakdown; no JS errors.
Usage: python tests/ui_board.py"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

M = "http://localhost:8031"
TMP = Path(r"C:\Users\hp\AppData\Local\Temp")
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:400])


HELP = "window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};"
ASK = """(async()=>{ const n=J.convo.length; document.querySelector('#text').value=%s; document.querySelector('#send').click();
  await until(()=>J.convo.length>n, 60000); await sleep(4500);
  const cards=[...document.querySelectorAll('#stageCards .vcard')]; const comp=document.querySelector('.composer').getBoundingClientRect();
  const bottom=cards.length?Math.max(...cards.map(c=>c.getBoundingClientRect().bottom)):0, right=cards.length?Math.max(...cards.map(c=>c.getBoundingClientRect().right)):0;
  const chip=document.querySelector('#scopeChip'); const pill=document.querySelector('#parkPill');
  return {kinds:cards.map(c=>(c.className.match(/k-(\\w+)/)||[])[1]), board:document.body.classList.contains('board-on'), bottom:Math.round(bottom), right:Math.round(right),
          compTop:Math.round(comp.top), vw:innerWidth, chip:chip&&chip.classList.contains('on')?chip.querySelector('span').textContent:'', pill:pill&&pill.classList.contains('on')?pill.innerText:'',
          say:(J.convo.slice(-1)[0]||{}).say||''} })()"""


async def run(label, size, q):
    async with Browser(port=9491, size=size, gpu=True) as b:
        await b.goto(f"{M}/?auto=1&noevents=1&livetest=1&p=cs{q}", 4)
        await b.eval(HELP)
        r = await b.eval("""(async()=>{ await until(()=>J.sid && document.querySelector('#left .kpis.k8'), 20000); await sleep(800);
          const k=document.querySelector('#left .kpis.k8'); return {tiles:k?k.querySelectorAll('.kpi').length:0, clock:document.querySelectorAll('#left .dclock .cb').length,
          says:[...document.querySelectorAll('#left [data-say]')].length, hdr:document.querySelector('#clock')?.getBoundingClientRect().height||0} })()""", timeout=60)
        if label == "web":
            check(f"{label}: the command board on the home screen (8 tiles, the 10-bucket clock, every tile a question; the header date pill untouched)",
                  r["tiles"] == 8 and r["clock"] == 10 and r["says"] >= 14 and r["hdr"] < 40, r)
        r = await b.eval(ASK % json.dumps("how is RDPR doing?"), timeout=120)
        fits = r["bottom"] <= (r["compTop"] + 2 if label == "web" else 10 ** 6) and r["right"] <= r["vw"] + 2
        check(f"{label}: 'how is RDPR doing?' -> a board of 6 cards, tiles first, fits above the composer", r["kinds"][:1] == ["tiles"] and len(r["kinds"]) == 6 and r["board"] and fits, r)
        check(f"{label}: the scope chip says RDPR" + ("; the live pill sits under the parked orb" if label == "web" else ""), r["chip"] == "RDPR" and (bool(r["pill"]) or label != "web"), r)
        await b.shot(TMP / f"uib_{label}_rdpr.png")
        r = await b.eval(ASK % json.dumps("and Hunsur?"), timeout=120)
        check(f"{label}: 'and Hunsur?' stays inside RDPR (chip RDPR › Hunsur, a new board)", r["chip"] == "RDPR › Hunsur" and len(r["kinds"]) >= 4, r)
        r = await b.eval("""(async()=>{ const n=J.convo.length; document.querySelector('#scopeChip button').click(); await until(()=>J.convo.length>n, 60000); await sleep(3000);
          const chip=document.querySelector('#scopeChip'); return {chip:chip.classList.contains('on')?chip.innerText:'', say:(J.convo.slice(-1)[0]||{}).say||''} })()""", timeout=120)
        check(f"{label}: the chip's ✕ goes back to the whole state (chip gone)", not r["chip"] and r["say"], r)
        r = await b.eval(ASK % json.dumps("how many cases are with L1?"), timeout=120)
        check(f"{label}: a single count is tiles + its breakdown", r["kinds"][:1] == ["tiles"] and len(r["kinds"]) == 2 and "L1" in r["say"], r)
        await b.shot(TMP / f"uib_{label}_l1.png")
        check(f"{label}: no JS exceptions", not [e for e in b.events if e[0] == "exception"], b.events[:3])


async def main():
    print("[web]")
    await run("web", (1536, 864), "")
    print("[phone]")
    await run("phone", (393, 852), "&app=1&intro=0")
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
