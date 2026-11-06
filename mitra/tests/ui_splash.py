"""Splash in a real headless browser (CDP): the cinematic intro (logo traced, halo, title letter by letter, greeting, Start
rises), the breathing orb and the turning Karnataka floor (31 districts, pulses), the greeting by the hour, the orb leaning
towards Start, and Start flying the orb into the live orb before Mitra begins (no JS errors). Screenshots for the eye.
Usage: python tests/ui_splash.py [base]   (default http://localhost:8030)"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8030"
TMP = Path(r"C:\Users\hp\AppData\Local\Temp")
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:320])


async def main():
    async with Browser(port=9339, size=(1536, 864)) as b:
        await b.goto(f"{B}/?intro=1&noevents=1", 0.25)
        await b.shot(TMP / "splash_0.png")
        r0 = await b.eval("""(()=>{const s=document.querySelector('#splash');const op=e=>+getComputedStyle(e).opacity;
          return {intro:s.classList.contains('intro'), title:op(document.querySelector('#spTitle .ch')), start:op(document.querySelector('.sp-row'))}})()""")
        await asyncio.sleep(1.0)
        await b.shot(TMP / "splash_1.png")
        await asyncio.sleep(1.8)
        await b.shot(TMP / "splash_2.png")
        r = await b.eval("""(async()=>{const op=e=>+getComputedStyle(e).opacity; const res={};
          res.letters=document.querySelectorAll('#spTitle .ch').length; res.gl=document.querySelectorAll('#spTitle .gl').length;
          res.titleOp=op(document.querySelectorAll('#spTitle .ch')[4]); res.startOp=op(document.querySelector('.sp-row')); res.greet=document.querySelector('#spGreet').innerText;
          res.mapW=document.querySelector('#spMap').width; res.dist=typeof KA_DIST!=='undefined'?KA_DIST.length:0;
          const c=document.querySelector('#spMap'), x=c.getContext('2d').getImageData(0,0,c.width,c.height).data; let lit=0; for(let i=3;i<x.length;i+=4*37) if(x[i]>20) lit++; res.mapPixels=lit;
          const o=document.querySelector('#spOrb'), y=o.getContext('2d').getImageData(0,0,o.width,o.height).data; let lo=0; for(let i=3;i<y.length;i+=4*37) if(y[i]>20) lo++; res.orbPixels=lo;
          return res})()""")
        print("   ", json.dumps(r0), json.dumps(r))
        check("intro starts dark: title and Start hidden at 0.25 s", r0["intro"] and r0["title"] < .2 and r0["start"] < .2, r0)
        check("after the intro: 'Mitra' letter by letter (gradient letters), greeting, Start visible", r["letters"] == 5 and r["gl"] == 5 and r["titleOp"] > .95 and r["startOp"] > .95 and len(r["greet"]) > 5, r)
        check("the Karnataka floor (31 districts) and the orb are drawn", r["dist"] == 31 and r["mapPixels"] > 200 and r["orbPixels"] > 200, r)
        r = await b.eval("""(async()=>{const s=document.querySelector('#start').getBoundingClientRect();
          document.querySelector('#splash').dispatchEvent(new PointerEvent('pointermove',{clientX:s.left+s.width/2,clientY:s.top+s.height/2,bubbles:true}));
          document.querySelector('#start').dispatchEvent(new PointerEvent('pointerenter')); await new Promise(r=>setTimeout(r,500));
          return {ready:document.querySelector('#splash').classList.contains('ready')}})()""")
        check("hovering Start: the orb leans in, the button glows", r["ready"], r)
        await b.shot(TMP / "splash_hover.png")
        r = await b.eval("""(async()=>{const res={}; const live=document.querySelector('#orb').getBoundingClientRect();
          document.querySelector('#start').click(); await new Promise(r=>setTimeout(r,120)); res.launch=document.querySelector('#splash').classList.contains('launch');
          await new Promise(r=>setTimeout(r,600)); res.midShot=true;
          await new Promise(r=>setTimeout(r,500)); const o=document.querySelector('#spOrb').getBoundingClientRect();
          res.dx=Math.round((o.left+o.width/2)-(live.left+live.width/2)); res.dy=Math.round((o.top+o.height/2)-(live.top+live.height/2)); res.dw=Math.round(o.width-live.width);
          await new Promise(r=>setTimeout(r,1500)); res.off=document.querySelector('#splash').classList.contains('off'); res.vis=getComputedStyle(document.querySelector('#splash')).visibility;
          res.session=!!J.sid; return res})()""")
        print("   ", json.dumps(r))
        check("Start: the orb flies onto the live orb (centre within 6 px, same size), the splash fades, Mitra starts", r["launch"] and abs(r["dx"]) <= 6 and abs(r["dy"]) <= 6 and abs(r["dw"]) <= 8 and r["off"] and r["vis"] == "hidden" and r["session"], r)
        await b.shot(TMP / "splash_after.png")
        await b.goto(f"{B}/?noevents=1", 1.0)
        r = await b.eval("(()=>({intro:document.querySelector('#splash').classList.contains('intro'), op:+getComputedStyle(document.querySelector('.sp-row')).opacity}))()")
        check("a reload in the same tab skips the intro", not r["intro"], r)
        print("[no flash of the plain card in the first frame]")
        for url in (f"{B}/?intro=1&noevents=1", f"{B}/?noevents=1"):
            await b.cmd("Page.navigate", url=url)
            seen = []
            for _ in range(12):
                try:
                    v = await b.eval("(()=>{const d=document.documentElement;const t=document.querySelector('#spTitle'),r=document.querySelector('.sp-row');if(!t||!r)return null;return {intro:d.dataset.intro,title:+getComputedStyle(t).opacity*(t.querySelector('.ch')?+getComputedStyle(t.querySelector('.ch')).opacity:1),start:(e=>{let o=1;for(;e&&e.nodeType===1;e=e.parentElement)o*=+getComputedStyle(e).opacity;return o})(r),ready:typeof Splash!=='undefined'}})()")
                except Exception:
                    v = None
                if v:
                    seen.append(v)
                    if v["ready"]:
                        break
                await asyncio.sleep(0.02)
            early = [v for v in seen if not v["ready"]]
            check(f"{url.split('/')[-1]}: before splash.js runs, the title and Start are not visible ({len(early)} early frames)", all(v["title"] < .05 and v["start"] < .05 for v in early) and all(v["intro"] in ("0", "1") for v in seen), seen[:3])
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS exceptions", not errs, errs[:3])
    print(f"\n{ok} passed, {fail} failed")


asyncio.run(main())
