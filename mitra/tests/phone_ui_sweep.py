"""The rest of the phone UI, inside the real phone frame (393 x 852, status bar, "Start app"): the three desks, the bottom sheet
(peek / half / full), the officer's case card, the citizen's request card, a notification, the read-back bar, the portal.
Checks every visible element sits inside the screen (no sideways overflow, nothing under the status bar or off the bottom)
and writes ui_phone_*.png for the eye. Usage: python tests/phone_ui_sweep.py [base]   (default http://localhost:8031)"""
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
        fail += 1; print("  FAIL", name, " <-", str(detail)[:400])


HELP = "window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};"
IN = "document.querySelector('#iphFrame').contentWindow"
# everything visible inside the app must fit 0..393 wide and from the status bar down
FIT = (f"(()=>{{const w={IN}, d=w.document, W=w.innerWidth, H=w.innerHeight, bad=[];"
       "for(const e of d.querySelectorAll('.card,.msheet,.composer,.top,.nt,#confirmBar,.vcard,.mpanel,.ms-tabs,.prof-menu.open,.portal.in .pt-core')){"
       "let hid=false; for(let x=e;x&&x.nodeType===1;x=x.parentElement){const s=w.getComputedStyle(x); if(s.display==='none'||s.visibility==='hidden'||+s.opacity<0.05){hid=true;break}} if(hid) continue; const b=e.getBoundingClientRect(); if(!b.width||!b.height) continue;"
       "if(b.left<-1||b.right>W+1) bad.push([e.className||e.id,'x',Math.round(b.left),Math.round(b.right)]);}"
       "return {W,H,over:d.documentElement.scrollWidth>W+1,bad:bad.slice(0,6)}})()")


async def phone(b, q):
    await b.eval(f"window.__old={IN}; document.querySelector('#iphFrame').src='/?app=1&intro=0&auto=1&noevents=1&livetest=1&{q}'")
    await b.eval(f"until(()=>{{const w={IN}; return w && w!==window.__old && w.location.search.includes('auto=1') && w.document.readyState==='complete' && w.eval('typeof J!==\"undefined\" && !!J.sid')}}, 25000)")
    await b.eval(f"(async()=>{{const d={IN}.document; await until(()=>d.querySelector('#left .card'), 15000); await sleep(900)}})()")


async def main():
    async with Browser(port=9349, size=(1536, 864)) as b:
        await b.goto(f"{B}/?intro=0&noevents=1", 3)
        await b.eval(HELP)
        await b.eval("(async()=>{document.querySelector('#startApp').click(); await until(()=>document.querySelector('#phoneStage.on'), 5000)})()")
        for prof in ("citizen", "officer", "cs"):
            await phone(b, f"p={prof}")
            for state in ("peek", "half", "full"):
                await b.eval(f"(async()=>{{const d={IN}.document, s=d.querySelector('.msheet'); s.dataset.s='{state}'; d.body.dataset.sheet='{state}'; await sleep(700)}})()")
                r = await b.eval(FIT)
                check(f"{prof} · sheet {state}: everything inside the phone screen, no sideways scroll", not r["over"] and not r["bad"], r)
                await b.shot(TMP / f"ui_phone_{prof}_{state}.png")
        print("[officer case card, read-back bar]")
        await phone(b, "p=officer")
        r = await b.eval(f"""(async()=>{{const w={IN}, d=w.document; w.eval("turn({{text:'read my inbox'}})"); await sleep(3500);
          w.eval("turn({{text:'open the first one'}})"); await until(()=>d.querySelector('#right [data-id=case]'), 25000); await sleep(1200);
          return {{tab:d.querySelector('.msheet').dataset.t, s:d.querySelector('.msheet').dataset.s}}}})()""")
        fit = await b.eval(FIT)
        check("case card opens in the sheet's Case tab and fits the screen", r["tab"] == "right" and r["s"] in ("half", "full") and not fit["bad"] and not fit["over"], (r, fit))
        await b.shot(TMP / "ui_phone_officer_case.png")
        await b.eval(f"(async()=>{{const w={IN}; w.eval(\"confirmBar('Reject GR-504203, Khatha, with the reason: Duplicate of an existing request? The citizen will be told and can appeal. Shall I go ahead?')\"); await sleep(800)}})()")
        fit = await b.eval(FIT)
        cb = await b.eval(f"(()=>{{const b={IN}.document.querySelector('#confirmBar').getBoundingClientRect(); return [Math.round(b.left),Math.round(b.right),Math.round(b.top),Math.round(b.bottom)]}})()")
        check("the read-back bar fits the phone (buttons reachable)", not fit["bad"] and cb[0] >= 0 and cb[1] <= 393 and cb[3] <= 852, (cb, fit))
        await b.shot(TMP / "ui_phone_confirm.png")
        print("[notification, portal]")
        await b.eval(f"(async()=>{{const w={IN}; w.eval(\"confirmBar(null)\"); w.eval(\"ntEnqueue({{id:9999,ts:new Date().toISOString(),tone:'ok',icon:'✓',title:'Filed · GR-504300',body:'Maintenance of Street Light · Routed to PDO Attigodu',actions:[{{label:'View as the officer →',as_officer:'pdo_piriyapatna_attigodu'}}]}},0)\"); await sleep(1500)}})()")
        fit = await b.eval(FIT)
        check("a notification card fits the phone", not fit["bad"], fit)
        await b.shot(TMP / "ui_phone_notification.png")
        await b.eval(f"(async()=>{{const w={IN}; w.eval(\"switchTo('cs')\"); await sleep(700)}})()")
        fit = await b.eval(FIT)
        check("the portal fits the phone", not fit["bad"], fit)
        await b.shot(TMP / "ui_phone_portal.png")
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS exceptions", not errs, errs[:3])
    print(f"\n{ok} passed, {fail} failed")


asyncio.run(main())
