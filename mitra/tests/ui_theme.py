"""Light / dark mode in a real headless browser (CDP): the header toggle sweeps the light look in (wave from the bottom-left),
it is one setting for every profile (survives a profile switch and a reload), the voice path (UI op from set_theme, typed
'switch to light mode' through the fake Live) works, charts stay legible (dark lens), and no JS errors.
Usage: python tests/ui_theme.py [base]   (default http://localhost:8031)"""
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


def post(p, d):
    req = urllib.request.Request(B + p, json.dumps(d).encode(), {"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


HELP = ("window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=20000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(50)}return false};"
        "window.lum=el=>{const cs=getComputedStyle(el);let m=/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([\\d.]+))?\\)/.exec(cs.backgroundColor);if(!m||(m[4]!==undefined&&+m[4]===0))m=/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/.exec(cs.backgroundImage);return m?(+m[1]*.3+ +m[2]*.59+ +m[3]*.11):-1};"
        "window.th=()=>document.documentElement.dataset.theme||'dark';")


async def main():
    async with Browser(port=9337, size=(1536, 864)) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=citizen", 2)
        await b.eval("try{sessionStorage.setItem('jv_theme','dark')}catch(e){}")        # start from dark (light is the default; ui_map checks that)
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=citizen", 4)
        await b.eval(HELP)
        await b.eval("until(()=>!!document.querySelector('#profBtn')&&!!document.querySelector('#left .card'))")
        print("[toggle]")
        r = await b.eval("""(async()=>{const res={}; res.start=th(); res.darkBody=lum(document.body);
          document.querySelector('#theme').click(); res.wave=await until(()=>!!document.querySelector('.theme-wave'), 3000); res.vt=typeof document.startViewTransition;
          res.now=await until(()=>th()==='light'); await sleep(1500); res.stored=sessionStorage.getItem('jv_theme'); res.lightBody=lum(document.body);
          res.card=lum(document.querySelector('#left .card')); res.title=document.querySelector('#theme').title; res.tx=getComputedStyle(document.body).color;
          return res})()""")
        print("   ", json.dumps(r))
        check("starts dark; the toggle sweeps the light look in with a wave; stored for next time", r["start"] == "dark" and r["now"] and r["wave"] and r["stored"] == "light" and r["darkBody"] < 40 and r["lightBody"] > 200 and "dark" in r["title"], r)
        await b.shot(TMP / "theme_light_citizen.png")
        print("[one setting across profiles]")
        r = await b.eval("""(async()=>{const res={}; await switchTo('cs'); await until(()=>!Portal.busy); await sleep(400);
          res.profile=J.profile; res.theme=th(); res.card=lum(document.querySelector('#left .card')); res.top=lum(document.querySelector('.top'));
          await switchTo('officer'); await until(()=>!Portal.busy); await sleep(300); res.theme2=th(); res.profile2=J.profile; return res})()""")
        print("   ", json.dumps(r))
        check("still light after switching to the Chief Secretary and to the Officer", r["theme"] == "light" and r["theme2"] == "light" and r["profile2"] == "officer" and r["card"] > 180, r)
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 4)
        await b.eval(HELP)
        r = await b.eval("(async()=>{await until(()=>!!document.querySelector('#left .card')); return {theme:th(), body:lum(document.body)}})()")
        check("a reload keeps light mode (applied before first paint)", r["theme"] == "light" and r["body"] > 200, r)
        print("[charts in daylight]")
        r = await b.eval("""(async()=>{const res={}; turn({text:'compare Piriyapatna, Hunsur and Mysore'}); res.stage=await until(()=>Stage.open && Stage.debug().cards.length===1, 40000); await sleep(2600);
          const vc=document.querySelector('.vcard'), vb=document.querySelector('.vcard .vb'); res.cardL=vc?lum(vc):-1; res.lensL=vb?lum(vb):-1;
          const c=getComputedStyle(document.querySelector('.vcard .vh b')).color.match(/\\d+/g); res.titleL=+c[0]*.3+ +c[1]*.59+ +c[2]*.11;
          const g=getComputedStyle(document.querySelector('.brand .grad')); res.clip=g.webkitBackgroundClip||g.backgroundClip; res.ink=g.webkitTextFillColor||g.color; return res})()""")
        print("   ", json.dumps(r))
        check("a light glass card with the chart drawn on it (no dark lens), dark card title; the wordmark is solid black ink (22 Oct)", r["stage"] and r["cardL"] > 180 and (r["lensL"] == -1 or r["lensL"] > 180) and r["titleL"] < 60 and r["clip"] != "text" and r["ink"] == "rgb(11, 11, 12)", r)
        await b.shot(TMP / "theme_light_stage.png")
        print("[by voice]")
        r = await b.eval("""(async()=>{const res={}; UI.theme({theme:'dark'}); res.dark=await until(()=>th()==='dark'); await sleep(1400); res.body=lum(document.body);
          turn({text:'switch to light mode'}); res.light=await until(()=>th()==='light', 20000); await sleep(1400); res.body2=lum(document.body);
          turn({text:'take me back to the dashboard'}); res.closed=await until(()=>!Stage.open, 10000); return res})()""")
        print("   ", json.dumps(r))
        check("the UI op switches to dark; typed 'switch to light mode' (through Live) switches to light; navigation still works", r["dark"] and r["body"] < 40 and r["light"] and r["body2"] > 200 and r["closed"], r)
        await b.shot(TMP / "theme_light_cs.png")
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS exceptions", not errs, errs[:3])
    print("[cascade]")
    s = post("/api/session", {"profile": "officer"})
    for text, want in [("dark mode please", "dark"), ("can you make it bright", "light"), ("switch to the light theme", "light"), ("go dark", "dark")]:
        r = post("/api/turn", {"session": s["session"], "text": text})
        check(f"'{text}' -> set_theme {want}", r["intent"] == "set_theme" and r["ui"] and r["ui"][0] == {"op": "theme", "theme": want} and want in r["say"], (r["intent"], r.get("ui"), r["say"]))
    r = post("/api/turn", {"session": s["session"], "text": "the street light near the bus stand is not working"})
    check("'street light' is not a theme change", r["intent"] != "set_theme", r["intent"])
    print(f"\n{ok} passed, {fail} failed")


asyncio.run(main())
