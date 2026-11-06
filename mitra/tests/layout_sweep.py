"""Layout sweep, web (1536 x 864) or phone (393 x 852): every chart kind, screenshots + geometry, incl. no overlap between the
stage zones (title, caption, cards, insight, composer). Usage: python tests/layout_sweep.py [base] [web|phone]
For each view: is every card inside the screen (left >= 0, right <= width, top >= header, bottom <= screen), is the canvas not
squeezed, does anything overlap the composer / the show-as row. Writes phone_*.png to %TEMP%.
Usage: python tests/phone_sweep.py [base]   (default http://localhost:8031)"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

B = next((a for a in sys.argv[1:] if a.startswith("http")), "http://localhost:8031")
MODE = "web" if "web" in sys.argv[1:] else "phone"
SIZE = (1536, 864) if MODE == "web" else (393, 852)
TMP = Path(r"C:\Users\hp\AppData\Local\Temp")
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:400])


HELP = ("window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};"
        "window.geo=()=>{const W=innerWidth,H=innerHeight;const r=e=>{if(!e)return null;const b=e.getBoundingClientRect();return [Math.round(b.left),Math.round(b.top),Math.round(b.right),Math.round(b.bottom)]};"
        "const cards=[...document.querySelectorAll('#stageCards .vcard')].map(c=>({k:c.className.match(/k-(\\w+)/)?.[1],box:r(c),cv:r(c.querySelector('canvas')),panel:r(c.querySelector('.mpanel')),leg:r(c.querySelector('.dleg'))}));"
        "return {W,H,cards,kinds:r(document.querySelector('#stageKinds')),insight:r(document.querySelector('#stageInsight>*')),composer:r(document.querySelector('.composer')),"
        "title:r(document.querySelector('#stageTitle')),caps:r(document.querySelector('.captions')),dock:r(document.querySelector('.stage-dock')),scroll:document.querySelector('#stageCards').scrollHeight>document.querySelector('#stageCards').clientHeight+2,"
        "host:r(document.querySelector('#stageCards'))}};")
ITEMS3 = [{"label": "Piriyapatna", "value": 390, "aliases": [], "district": "Mysuru"}, {"label": "Hunsur", "value": 10, "aliases": [], "district": "Mysuru"},
          {"label": "Mysuru", "value": 14, "aliases": [], "district": "Mysuru"}]
RACE = [{"label": d, "value": v, "aliases": [], "district": d} for d, v in [("Shivamogga", 712), ("Mysuru", 473), ("Belagavi", 287), ("Bagalkote", 178),
                                                                           ("Bengaluru Urban", 151), ("Chikkamagaluru", 120), ("Hassan", 96), ("Tumakuru", 80)]]
LINE = [{"label": m, "value": v, "aliases": []} for m, v in zip(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                                                                [51172, 47000, 43800, 40100, 36000, 33300, 30500, 27900, 25000, 23100, 21000, 19129])]
DONUT = [{"label": "Revenue", "value": 1880, "aliases": []}, {"label": "Rural Development & Panchayat Raj", "value": 1061, "aliases": []},
         {"label": "Food & Civil Supplies", "value": 115, "aliases": []}]
VIEWS = {
    "bars": {"title": "Comparison by taluk", "insight": "Piriyapatna holds 94% of the open cases among these", "cards": [{"type": "bars", "title": "Open cases", "subtitle": "by taluk", "by": "taluk", "unit": "cases", "items": ITEMS3}]},
    "race": {"title": "Ranking by district", "insight": "Shivamogga leads with 712", "cards": [{"type": "race", "title": "Districts by open cases", "subtitle": "top 8 of 31", "by": "district", "unit": "cases", "items": RACE}]},
    "line": {"title": "Sakala 2025", "insight": "Overdue fell 63%", "cards": [{"type": "line", "title": "Overdue applications, month by month", "subtitle": "2025", "unit": "cases", "items": LINE}]},
    "donut": {"title": "By department", "insight": "Revenue is the largest with 1,880", "cards": [{"type": "donut", "title": "Open by department", "subtitle": "live caseload", "by": "department", "unit": "cases", "items": DONUT}]},
    "two": {"title": "Position", "insight": "", "cards": [{"type": "donut", "title": "Open by department", "by": "department", "unit": "cases", "items": DONUT},
                                                            {"type": "bars", "title": "Open by level", "by": "level", "unit": "cases", "items": [{"label": "L1", "value": 2900, "aliases": []}, {"label": "L2", "value": 120, "aliases": []}, {"label": "L3", "value": 40, "aliases": []}]}]},
    "bars8": {"title": "Comparison by district", "insight": "Shivamogga leads", "cards": [{"type": "bars", "title": "Open cases in eight districts", "subtitle": "by district", "by": "district", "unit": "cases", "items": RACE}]},
    "dept_bars": {"title": "Comparison by department", "insight": "Revenue leads", "cards": [{"type": "bars", "title": "Open cases by department", "subtitle": "live caseload", "by": "department", "unit": "cases", "items": DONUT}]},
    "kpi": {"title": "State", "insight": "", "cards": [{"type": "kpi", "title": "Open cases", "unit": "cases", "items": [{"label": "open across Karnataka", "value": 3066, "aliases": []}]}]},
}


def inside(g, box, top=56):
    return box and box[0] >= -1 and box[2] <= g["W"] + 1 and box[1] >= top - 1 and box[3] <= g["H"] + 1


async def main():
    async with Browser(port=9348 if MODE == 'phone' else 9349, size=SIZE, gpu=True) as b:
        for theme in ("light", "dark"):
            await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 1)
            await b.eval(f"try{{sessionStorage.setItem('jv_theme','{theme}')}}catch(e){{}}")
            await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 4)
            await b.eval(HELP)
            await b.eval("until(()=>!!J.sid && document.querySelector('#left .card'))")
            print(f"[{theme}]")
            for name, op in VIEWS.items():
                g = await b.eval(f"(async()=>{{Stage.exit(true); await sleep(300); UI.viz({json.dumps({'op': 'viz', **op})}); await sleep(900); Stage.flush(0); await sleep(2600); return geo()}})()")
                cards = g["cards"]
                top = g["host"][1] if g.get("host") else 56
                if MODE == "web":                      # web: the 3-D tilt makes a card's box a few px taller; it must clear the caption
                    top = (g["caps"][3] if g.get("caps") else 140) + 4
                bad = [c for c in cards if not inside(g, c["box"], top) and not (g["scroll"] and c["box"][1] >= top - 1)]
                cvsmall = [c for c in cards if c["cv"] and (c["cv"][3] - c["cv"][1] < 180 or c["cv"][2] - c["cv"][0] < 280)]
                leg_out = [c for c in cards if c["leg"] and not inside(g, c["leg"])]
                over = g["kinds"] and cards and any(c["box"][3] > g["kinds"][1] + 2 and not g["scroll"] for c in cards)
                if MODE == "web":
                    over = False
                check(f"{theme} · {name}: cards on screen, canvas not squeezed, legend inside, nothing under the show-as row",
                      cards and not bad and not cvsmall and not leg_out and not over, {"cards": cards, "kinds": g["kinds"], "scroll": g["scroll"]})
                def ov(a, c):
                    return a and c and a[0] < c[2] - 2 and c[0] < a[2] - 2 and a[1] < c[3] - 2 and c[1] < a[3] - 2
                zones = [("title", g["title"]), ("caption", g["caps"]), ("insight", g["insight"]), ("composer", g["composer"])] + [(f"card{i}", c["box"]) for i, c in enumerate(cards)]
                clash = [(x, y) for i, (x, a) in enumerate(zones) for (y, c) in zones[i + 1:] if ov(a, c) and not (x.startswith("card") and y.startswith("card")) and not (g["scroll"] and (x.startswith("card") or y.startswith("card")) and ("caption" not in (x, y)) and ("title" not in (x, y)))]
                check(f"{theme} · {name}: title, caption, cards, insight and composer do not overlap", not clash, {"clash": clash, "zones": zones})
                await b.shot(TMP / f"{MODE}_{theme}_{name}.png")
            g = await b.eval("""(async()=>{Stage.exit(true); await sleep(300); turn({text:'compare all the cases between each department on the map'});
              await until(()=>Stage.open && Stage.debug().cards[0] && Stage.debug().cards[0].kind==='map', 40000); await sleep(400); Stage.flush(0); await sleep(3500); return geo()})()""")
            c = (g["cards"] or [{}])[0]
            area = (c["panel"][1] - c["cv"][1]) if c.get("panel") and c.get("cv") else 0          # the map's own space above its panel
            panelH = c["panel"][3] - c["panel"][1] if c.get("panel") else 0
            check(f"{theme} · map: card on screen, the map has its own space above a compact panel",
                  c and inside(g, c["box"]) and (MODE == "web" or (area >= 200 and c.get("panel") and inside(g, c["panel"]) and panelH <= 135)), {"card": c, "area": area, "panelH": panelH})
            await b.shot(TMP / f"{MODE}_{theme}_map.png")
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS exceptions", not errs, errs[:3])
    print(f"\n{ok} passed, {fail} failed")


asyncio.run(main())
