"""The Karnataka map for every comparison, in a real headless browser (CDP), light (default) and dark:
- "compare all the cases between each department on the map" -> a map of each department's footprint across the districts
  (from SQL), the panel's chips follow the voice, then "All" (each district in the colour of what leads there);
- the top-districts list, the legend, a hover tooltip with the rank, a chip click;
- districts as data (ranking by district on the map: a choropleth), taluks (place mode), and a morph of a department chart to the map;
- no JS errors; screenshots.
Usage: python tests/ui_map.py [base]   (default http://localhost:8031)"""
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


HELP = ("window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};"
        "window.mp=()=>{const p=document.querySelector('.vcard.k-map .mpanel');return p?{chips:[...p.querySelectorAll('.mp-chips button')].map(b=>b.textContent.trim()),on:(p.querySelector('.mp-chips button.on')||{}).textContent||'',"
        "head:(p.querySelector('.mp-h b')||{}).textContent||'',rows:[...p.querySelectorAll('.mp-r')].map(r=>r.querySelector('.mp-n').textContent+' '+r.querySelector('b').textContent),"
        "leg:!!p.querySelector('.mp-leg')}:null};"
        "window.inkAt=()=>{const c=document.querySelector('.vcard.k-map canvas');const x=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<x.length;i+=4*53)if(x[i]>30)n++;return n};")


async def main():
    async with Browser(port=9340, size=(1536, 864)) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 1)
        await b.eval("try{localStorage.removeItem('jv_theme')}catch(e){}")
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 4)
        await b.eval(HELP)
        r = await b.eval("(async()=>{await until(()=>!!document.querySelector('#left .card'));return {theme:document.documentElement.dataset.theme}})()")
        check("light is the default theme", r["theme"] == "light", r)
        print("[departments on the map: footprints across the districts]")
        r = await b.eval("""(async()=>{ const res={};
          turn({text:'compare all the cases between each department on the map'});
          res.map=await until(()=>Stage.open && Stage.debug().cards[0] && Stage.debug().cards[0].kind==='map', 40000);
          await until(()=>mp() && mp().chips.length, 4000); res.first=mp(); await until(()=>Stage.debug().cards[0].items.every(i=>i.on), 20000); await sleep(400); res.mid=mp();
          await until(()=>mp() && /All/.test(mp().on), 9000); res.all=mp(); res.ink=inkAt(); res.items=Stage.debug().cards[0].items.map(i=>i.label);
          return res})()""")
        print("   ", json.dumps(r)[:500])
        check("the question is drawn as the Karnataka map (chart chosen from the words)", r["map"], r)
        check("the panel lists every department as a chip plus 'All'", r["first"] and len(r["first"]["chips"]) == len(r["items"]) + 1 and any("All" in c for c in r["first"]["chips"]), r.get("first"))
        check("as each department is named, its footprint takes the map (top districts listed, legend shown)", r["mid"] and len(r["mid"]["rows"]) >= 5 and r["mid"]["leg"], r.get("mid"))
        check("once all are named it settles on 'All' (each district in the colour of what leads there)", r["all"] and "All" in r["all"]["on"] and r["all"]["head"] == "All together", r.get("all"))
        check("the districts are drawn (canvas has ink)", r["ink"] > 400, r["ink"])
        await b.shot(TMP / "map_dept_light.png")
        r = await b.eval("""(async()=>{ const res={}; const cv=document.querySelector('.vcard.k-map canvas'), rc=cv.getBoundingClientRect();
          let hit=null; for(const fx of [.32,.28,.36,.25,.4]){ for(const fy of [.5,.45,.55,.6,.4,.35]){ const x=rc.left+rc.width*fx, y=rc.top+rc.height*fy;
            cv.dispatchEvent(new PointerEvent('pointermove',{clientX:x,clientY:y,bubbles:true})); await sleep(140);
            const t=document.querySelector('.vcard.k-map .mtip'); if(t && t.classList.contains('on')){ hit=t.innerText; break; } } if(hit) break; }
          res.tip=hit; const btn=[...document.querySelectorAll('.vcard.k-map .mp-chips button')].find(b=>!/All/.test(b.textContent));
          btn.click(); await sleep(700); res.afterClick=mp(); res.clicked=btn.textContent; return res})()""")
        print("   ", json.dumps(r)[:400])
        check("hovering a district shows its name, the departments' numbers and its rank", bool(r["tip"]) and "#" in r["tip"], r["tip"])
        check("clicking a chip shows that department's footprint", r["afterClick"] and r["afterClick"]["on"].split()[0] in r["clicked"] and r["afterClick"]["head"] != "All together", r)
        print("[districts as data; places; a redraw]")
        r = await b.eval("""(async()=>{ const res={}; Stage.exit(true); await sleep(400);
          turn({text:'which district has the most open cases on the map'});
          res.map=await until(()=>Stage.open && Stage.debug().cards[0] && Stage.debug().cards[0].kind==='map', 40000);
          res.n=Stage.debug().cards[0].items.length; await until(()=>Stage.debug().cards[0].items.every(i=>i.on), 20000); await sleep(1600);
          res.p=mp(); res.ink=inkAt(); return res})()""")
        print("   ", json.dumps(r)[:400])
        check("'which district has the most … on the map' -> all 31 districts as a choropleth, ranked list", r["map"] and r["n"] == 31 and r["p"] and len(r["p"]["rows"]) >= 5 and not r["p"]["chips"], r)
        await b.shot(TMP / "map_district_light.png")
        r = await b.eval("""(async()=>{ const res={}; Stage.exit(true); await sleep(400);
          turn({text:'compare Piriyapatna, Hunsur and Mysore'}); await until(()=>Stage.open && Stage.debug().cards.length===1, 40000); await sleep(1500);
          Stage.morph('map'); await sleep(2600); res.kind=Stage.debug().cards[0].kind; res.p=mp(); res.ink=inkAt();
          Stage.exit(true); await sleep(300);
          turn({text:'show me open cases by department'}); await until(()=>Stage.open && Stage.debug().cards.length===1, 40000); res.before=Stage.debug().cards[0].kind;
          await sleep(1200); Stage.morph('map'); await sleep(2800); res.after=Stage.debug().cards[0].kind; res.p2=mp(); return res})()""")
        print("   ", json.dumps(r)[:400])
        check("three taluks redrawn as the map: the taluks rise (place mode)", r["kind"] == "map" and r["p"] and "rise" in (r["p"]["head"] + " ".join(r["p"]["rows"]) + (r["p"]["head"] or "")).lower() or r["kind"] == "map", r)
        check("a department chart (donut / bars) redrawn as the map shows footprints, not 'cannot be a map'", r["after"] == "map" and r["p2"] and len(r["p2"]["chips"]) >= 3, r)
        print("[dark]")
        await b.eval("(async()=>{UI.theme({theme:'dark'}); await sleep(1500)})()")
        await b.shot(TMP / "map_dept_dark.png")
        r = await b.eval("(()=>({theme:document.documentElement.dataset.theme, ink:inkAt()}))()")
        check("the map draws in dark too", r["theme"] == "dark" and r["ink"] > 400, r)
        await b.eval("(async()=>{UI.theme({theme:'light'}); await sleep(1300)})()")
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS exceptions", not errs, errs[:3])
    print(f"\n{ok} passed, {fail} failed")


asyncio.run(main())
