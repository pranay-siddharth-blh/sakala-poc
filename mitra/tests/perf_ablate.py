"""Which effect costs the frames: open the department map on the CS desk (test instance, fake Live), then measure the frame rate
for 3 s with each effect switched off in turn. Usage: python tests/perf_ablate.py [base]"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

B = next((a for a in sys.argv[1:] if a.startswith("http")), "http://localhost:8031")
HELP = "window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};"
FPS = """(async()=>{ let f=0; const t0=performance.now(); let run=true; const k=()=>{f++; if(run) requestAnimationFrame(k)}; requestAnimationFrame(k); await sleep(3000); run=false; return Math.round(f/((performance.now()-t0)/1000)) })()"""
OFF = {
    "baseline": "",
    "no backdrop-filter": "*,*::before,*::after{backdrop-filter:none!important;-webkit-backdrop-filter:none!important}",
    "no filter (blur/drop-shadow)": "*,*::before,*::after{filter:none!important}",
    "no box-shadow": "*,*::before,*::after{box-shadow:none!important}",
    "no CSS animations": "*,*::before,*::after{animation:none!important;transition:none!important}",
    "hide orb canvas": "#orb,.orb-wrap canvas{display:none!important}",
    "hide stage fx canvas": "#stageFx{display:none!important}",
    "hide background (aurora/mesh/grid)": ".aurora,.bg,#bgMesh,.mesh,.grid-bg,body::before,body::after,.aur{display:none!important}",
    "hide stage cards": "#stage .vcard{display:none!important}",
    "everything above off": None,
    "baseline again": "",
}


async def main():
    async with Browser(port=9391, size=(1536, 864), gpu=("gpu" in sys.argv)) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=cs", 5)
        await b.eval(HELP)
        await b.eval("until(()=>!!J.sid && document.querySelector('#left .card'), 20000)")
        await asyncio.sleep(2)
        await b.eval("""(async()=>{ turn({text:'compare all the cases between each department on the map'}); await until(()=>Stage.open && Stage.debug().cards.length>0, 30000); await sleep(8000); })()""", timeout=60)
        allcss = " ".join(v for v in OFF.values() if v)
        for name, css in OFF.items():
            css = allcss if css is None else css
            await b.eval(f"(()=>{{ let s=document.getElementById('__abl'); if(!s){{s=document.createElement('style'); s.id='__abl'; document.head.appendChild(s)}} s.textContent={json.dumps(css)}; }})()")
            await asyncio.sleep(0.5)
            fps = await b.eval(FPS)
            print(f"  {fps:3d} fps  {name}")


asyncio.run(main())
