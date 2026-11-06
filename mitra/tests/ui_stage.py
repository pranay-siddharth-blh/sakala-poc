"""Stage mode (canvas edition) in a real headless browser (CDP): the dashboard sinks, the orb flies to the corner, cards arc
in, bars grow one by one as the transcript names them (slowly, so they are still growing while she talks), flush brings the
rest, the insight chip appears, "close" brings the dashboard back; morphing the same numbers to line / donut / map by
voice; and a real end-to-end comparison through the fake Live server (rules brain -> compare -> viz).
Usage: python tests/ui_stage.py [base]   (default http://localhost:8031)"""
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


OP = {"op": "viz", "title": "Comparison by taluk", "insight": "Piriyapatna holds 94% of the open cases among these",
      "cards": [{"type": "bars", "title": "Open cases", "subtitle": "by taluk", "metric": "open", "unit": "cases", "by": "taluk",
                 "items": [{"label": "Piriyapatna", "value": 393, "aliases": ["periyapatna"], "district": "Mysuru"}, {"label": "Hunsur", "value": 10, "aliases": ["hunsuru"], "district": "Mysuru"},
                           {"label": "Mysuru", "value": 14, "aliases": ["mysore"], "district": "Mysuru"}]}]}
DIST = {"op": "viz", "title": "Ranking by district", "insight": "Shivamogga leads with 712",
        "cards": [{"type": "race", "title": "Districts by open cases", "subtitle": "top 6 of 31", "metric": "open", "unit": "cases", "by": "district",
                   "items": [{"label": l, "value": v, "aliases": a, "district": l} for l, v, a in [("Shivamogga", 712, ["shimoga"]), ("Mysuru", 461, ["mysore"]), ("Belagavi", 287, ["belgaum"]), ("Bagalkote", 178, []), ("Vijayapura", 150, ["bijapur"]), ("Hassan", 120, [])]]}]}


async def main():
    async with Browser(port=9335, size=(1536, 864)) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 4)
        await b.eval("window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};window.st=()=>Stage.debug().cards.map(c=>c.items.map(i=>i.on));window.pp=()=>Stage.debug().cards.map(c=>c.items.map(i=>i.p));")
        print("[stage mechanics with a scripted transcript]")
        r = await b.eval(f"""(async()=>{{
          const op={json.dumps(OP)}; const res={{}};
          await until(()=>!!document.querySelector('#left .card'));
          UI.viz(op); await sleep(2400);
          res.stageOn=document.body.classList.contains('stage-in'); res.cards=document.querySelectorAll('.vcard canvas').length;
          res.orbTx=getComputedStyle(document.querySelector('.orb-wrap')).transform!=='none';
          res.leftHidden=getComputedStyle(document.querySelector('.col.left')).visibility;
          res.chips=document.querySelectorAll('.dock-chip').length; res.kinds=document.querySelector('#stageKinds').classList.contains('on');
          res.before=st()[0]; res.mapData=(typeof KA_DIST!=='undefined')&&KA_DIST.length;
          Stage.hear('Open cases: Piriyapatna has three hundred and ninety three'); await sleep(400); res.afterFirst=st()[0]; res.pEarly=pp()[0][0];
          await sleep(1200); res.pMid=pp()[0][0];
          Stage.hear('Open cases: Piriyapatna has 393, Hunsur 10'); await sleep(200); res.afterSecond=st()[0];
          res.insightBefore=document.querySelector('#stageInsight').classList.contains('on');
          Stage.hear('Open cases: Piriyapatna 393, Hunsur 10 and Mysore 14. Piriyapatna holds 94%'); await sleep(300); res.afterThird=st()[0];
          await sleep(2200); res.insightAfter=document.querySelector('#stageInsight').classList.contains('on'); res.pLate=pp()[0];
          return res}})()""")
        print("   ", json.dumps(r)[:420])
        check("stage opens: dashboard sinks, orb flies, canvas cards in, dock chips, 'show as' buttons, map data loaded", r["stageOn"] and r["cards"] == 1 and r["orbTx"] and r["leftHidden"] == "hidden" and r["chips"] >= 2 and r["kinds"] and r["mapData"] == 31, r)
        check("nothing revealed before she speaks", r["before"] == [False, False, False], r)
        check("Piriyapatna starts growing when named, others wait", r["afterFirst"] == [True, False, False], r)
        check("growth is slow: still rising after 0.4 s and 1.6 s", 0 < r["pEarly"] < 0.6 and r["pEarly"] < r["pMid"] < 1, (r["pEarly"], r["pMid"]))
        check("Hunsur when named; 'Mysore' reveals Mysuru (alias); insight after all", r["afterSecond"] == [True, True, False] and r["afterThird"] == [True, True, True] and r["insightAfter"] and not r["insightBefore"], r)
        await b.eval("(async()=>{UI.viz(JSON.parse(JSON.stringify(%s))); await sleep(1500); Stage.hear('Open cases: Piriyapatna 393'); await sleep(1100)})()" % json.dumps(OP))
        await b.shot(TMP / "stage3d_bars.png")

        print("[morph by voice: line, donut, map; close]")
        r = await b.eval("""(async()=>{ const res={};
          turn({text:'can you show it as a line graph'}); await sleep(700); res.line=Stage.debug().cards[0].kind; res.onLine=Stage.debug().cards[0].items.every(i=>i.on)||await until(()=>Stage.debug().cards[0].items.every(i=>i.on),8000);
          turn({text:'switch it to a donut'}); await sleep(700); res.donut=Stage.debug().cards[0].kind;
          turn({text:'show it on the Karnataka map'}); await sleep(700); res.map=Stage.debug().cards[0].kind; res.mapNote=!!document.querySelector('.map-note');
          await until(()=>Stage.debug().cards[0].items.every(i=>i.on),10000); await sleep(2200);
          return res})()""")
        check("'show it as a line graph' -> line", r["line"] == "line" and r["onLine"], r)
        check("'switch it to a donut' -> donut", r["donut"] == "donut", r)
        check("'show it on the Karnataka map' -> map (taluks placed by their district)", r["map"] == "map" and not r["mapNote"], r)
        await b.shot(TMP / "stage3d_map.png")
        r = await b.eval("""(async()=>{ turn({text:'close the chart'}); await sleep(1100); return {open:Stage.open, stageIn:document.body.classList.contains('stage-in')}})()""")
        check("'close the chart' brings the dashboard back", not r["open"] and not r["stageIn"], r)

        print("[district ranking: race, then map]")
        r = await b.eval(f"""(async()=>{{ UI.viz({json.dumps(DIST)}); await sleep(1800); const res={{}};
          Stage.hear('Shimoga leads with 712, then Mysore 461 and Belgaum'); await sleep(500); res.race=st()[0];
          Stage.morph('map'); await sleep(900); res.kind=Stage.debug().cards[0].kind; res.note=!!document.querySelector('.map-note');
          await until(()=>Stage.debug().cards[0].items.every(i=>i.on),12000); await sleep(2300); res.p=pp()[0];
          return res}})()""")
        check("race: Shimoga / Mysore / Belgaum glow when named (aliases)", r["race"][:3] == [True, True, True] and not any(r["race"][3:]), r)
        check("district ranking on the Karnataka map, all six raised", r["kind"] == "map" and not r["note"] and all(p >= .99 for p in r["p"]), r)
        await b.shot(TMP / "stage3d_distmap.png")
        r = await b.eval("""(async()=>{ UI.viz({op:'viz',title:'By department',insight:'',cards:[{type:'donut',title:'Open by department',by:'department',items:[{label:'Revenue',value:1879,aliases:[]},{label:'RDPR',value:1060,aliases:[]},{label:'Food',value:115,aliases:[]}]}]});
          await sleep(1200); const r=Stage.morph('map'); await sleep(600); return {ok:r.ok, note:!!document.querySelector('.map-note')}})()""")
        check("a department breakdown with no district footprint is not placed by guesswork (morph reports it)", r["ok"] is False, r)

        print("[end to end through the fake Live server]")
        r = await b.eval("""(async()=>{ Stage.exit(true); await sleep(400);
          turn({text:'compare Piriyapatna, Hunsur and Mysore'}); const got=await until(()=>Stage.open && Stage.debug().cards.length===1 && Stage.debug().cards[0].items.length===3, 40000);
          const all=await until(()=>Stage.debug().cards[0].items.every(i=>i.on), 40000);
          return {got, all, labels:Stage.debug().cards[0].items.map(i=>i.label), say:(J.convo[J.convo.length-1]||{}).say||''}})()""")
        check("'compare Piriyapatna, Hunsur and Mysore' -> 3 bars, built from speech", r["got"] and r["all"] and r["labels"] == ["Piriyapatna", "Hunsur", "Mysuru"], r)
        print("[speed: a trend and a redraw build at once, not after she finishes]")
        r = await b.eval("""(async()=>{ const res={}; Stage.exit(true); await sleep(300);
          const items=Array.from({length:12},(_,i)=>({label:'M'+i,value:100-i*3,aliases:[],district:''}));
          UI.viz({op:'viz',title:'Monthly',cards:[{type:'line',title:'Overdue',metric:'overdue',unit:'cases',by:'month',items}]});
          const t0=performance.now(); await until(()=>Stage.debug().cards[0].items.every(i=>i.on),8000); res.allIn=Math.round(performance.now()-t0);
          const t1=performance.now(); Stage.morph('donut'); await until(()=>Stage.debug().cards[0].kind==='donut' && Stage.debug().cards[0].items.every(i=>i.on),8000); res.morphIn=Math.round(performance.now()-t1);
          Stage.exit(true); return res})()""")
        print("   ", json.dumps(r))
        check("a 12-point trend with nothing named is all drawing within 2.6 s; a redraw to a donut within 2.2 s", r["allIn"] < 2600 and r["morphIn"] < 2200, r)
        await b.eval("(async()=>{UI.viz(%s); await sleep(600); Stage.flush(0); await sleep(300)})()" % json.dumps(OP))
        print("[navigation back and morph crossfade]")
        r = await b.eval("""(async()=>{ const res={};
          turn({text:'can you take me back to the dashboard'}); res.closed=await until(()=>!Stage.open && !document.body.classList.contains('stage-on'), 15000);
          res.left=getComputedStyle(document.querySelector('.col.left')).visibility;
          res.kept=!!Stage.last; turn({text:'bring the chart back'}); res.back=await until(()=>Stage.open, 8000); await sleep(1200);
          Stage.morph('donut'); await sleep(80);
          res.ghost=document.querySelectorAll('.stage-cards.ghost .vcard').length; res.morphing=document.querySelectorAll('#stageCards .vcard.morphing').length; res.fx=!!document.querySelector('#stageFx');
          await sleep(900); res.ghostGone=document.querySelectorAll('.stage-cards.ghost').length===0; res.kind=Stage.debug().cards[0].kind;
          turn({text:'close the chart'}); res.closed2=await until(()=>!Stage.open, 8000);
          return res})()""")
        print("   ", json.dumps(r))
        check("typed 'can you take me back to the dashboard' closes the stage, dashboard columns back, chart kept", r["closed"] and r["left"] == "visible" and r["kept"], r)
        check("'bring the chart back' reopens the last chart", r["back"], r)
        check("a morph crossfades: old cards fade as a ghost while the new ones turn in; ambient light layer present", r["ghost"] >= 1 and r["morphing"] >= 1 and r["fx"] and r["ghostGone"] and r["kind"] == "donut", r)
        check("'close the chart' closes it", r["closed2"], r)
        await b.eval("(async()=>{turn({text:'bring the chart back'}); await until(()=>Stage.open, 8000); await sleep(2600)})()")
        await b.shot(TMP / "stage_fluid.png")
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS exceptions", not errs, errs[:3])
    print(f"\n{ok}/{ok + fail} checks passed")


asyncio.run(main())
