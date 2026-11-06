"""Headless-Edge check of the full-duplex client against the fake Live server (Mitra test instance on 8031): the page opens
a live conversation by typing (no microphone in headless), files a grievance end to end, and reports the mode pill,
captions, the conversation strip, the panels and any JS error. Usage: python tests/dbg_live.py <out.png> [base]"""
import json
import re
import subprocess
import sys
import html as H
from pathlib import Path

out = Path(sys.argv[1])
B = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8031"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
page = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
inject = """<script>
window.__errs=[];window.onerror=(m,s,l)=>{__errs.push(m+' @'+l)};window.onunhandledrejection=e=>{__errs.push('rej '+(e.reason&&e.reason.message||e.reason))};
localStorage.clear();
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function until(f,ms=20000){const t=Date.now();while(Date.now()-t<ms){if(f())return true;await sleep(100)}return false}
window.addEventListener('load',()=>{setTimeout(async()=>{
  const res={};
  try{
    J.profile='citizen'; await session(false);
    turn({text:'the street light near the bus stand is not working'});
    res.opened=await until(()=>LV.open&&LV.ready); res.pill1=$('#modePill').dataset.m;
    res.req=await until(()=>!!document.querySelector('#left .req .big'));
    await until(()=>J.convo.length>=1);
    for(const t of ['Piriyapatna','Attigodu','yes, file it']){const n=J.convo.length; turn({text:t}); await until(()=>J.convo.length>n,25000);}
    res.routed=!!document.querySelector('[data-id=routed]'); res.routedText=(document.querySelector('[data-id=routed]')||{}).innerText||'';
    res.convo=J.convo.length; res.capWords=document.querySelectorAll('#capJv .w').length; res.trace=[...document.querySelectorAll('#trace span.done')].map(x=>x.dataset.k);
    res.audioBufs=J.convo.filter(x=>x.bufs&&x.bufs.length).length;
    Orb.onTap(); await sleep(300); res.afterTap=$('#modePill').dataset.m;
  }catch(e){__errs.push('run '+e.message)}
  document.body.dataset.res=JSON.stringify(res); document.body.dataset.err=JSON.stringify(__errs);
},800)});
</script>"""
tmp = Path(__file__).resolve().parents[1] / "web" / "dbg.html"
tmp.write_text(page.replace("</body>", inject + "</body>"), encoding="utf-8")
args = [EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars", "--window-size=1536,864", "--autoplay-policy=no-user-gesture-required",
        f"--user-data-dir={Path.home() / 'AppData/Local/Temp/jv_edge_live'}", "--virtual-time-budget=90000", "--timeout=120000"]
dom = subprocess.run(args + ["--dump-dom", f"{B}/dbg.html?auto=1&noevents=1&livetest=1"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=200).stdout
shot = Path(r"C:\Users\hp\AppData\Local\Temp\jv_live.png")
subprocess.run(args + [f"--screenshot={shot}", f"{B}/dbg.html?auto=1&noevents=1&livetest=1"], timeout=200)
tmp.unlink(missing_ok=True)
m = re.search(r'data-err="([^"]*)"', dom); r = re.search(r'data-res="([^"]*)"', dom)
print("errors:", H.unescape(m.group(1)) if m else "(no hook result)")
print("result:", H.unescape(r.group(1)) if r else "(none)")
if shot.exists():
    out.write_bytes(shot.read_bytes())
