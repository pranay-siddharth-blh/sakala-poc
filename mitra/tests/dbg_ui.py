"""Headless-Edge UI check for the v8 chrome: loads a copy of the page with an error hook, opens the profile
switcher, pokes the orb with pointer events, runs the scanner tick, and reports JS errors + screenshots.
Usage: python tests/dbg_ui.py <profile> <out.png>"""
import json, subprocess, sys, time, urllib.request
from pathlib import Path
B = "http://localhost:8030"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
profile, out = sys.argv[1], Path(sys.argv[2])
import os
officer = os.environ.get("DBG_OFFICER", "tah_piriyapatna")  # NOTIF_DEMO
def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=180).read())
s = post("/api/session", {"profile": profile, "officer": officer, "lang": "en"}); sid = s["session"]
html = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
inject = """<script>
window.__errs=[];window.onerror=(m,s,l)=>{__errs.push(m+' @'+l)};window.onunhandledrejection=e=>{__errs.push('rej '+(e.reason&&e.reason.message||e.reason))};
localStorage.setItem('jv_sid','%s');localStorage.setItem('jv_profile','%s');localStorage.setItem('jv_officer','%s');
window.addEventListener('load',()=>{setTimeout(async()=>{
  try{
    J.sid='%s';J.profile='%s';J.officer='%s'; await session(false);
    $('#profBtn').click();
    const cv=document.getElementById('orb'), r=cv.getBoundingClientRect(), cx=r.left+r.width/2, cy=r.top+r.height/2;
    const ev=(t,x,y)=>cv.dispatchEvent(new PointerEvent(t,{clientX:x,clientY:y,pointerId:1,bubbles:true}));
    ev('pointerenter',cx,cy); ev('pointermove',cx+20,cy); ev('pointerdown',cx,cy); ev('pointermove',cx+40,cy+10); ev('pointermove',cx+90,cy+30); ev('pointerup',cx+90,cy+30);
    ev('pointerdown',cx,cy); ev('pointerup',cx,cy);  // tap (no mic in headless -> focuses the text box)
    SC.on=false; scanTick(); startScan(); stopScan();
    // v10 pieces: routed card + burst + fly label, conversation strip with a fake clip, pulse strip (CS), scanner while speaking
    UI.routed({caseId:'GR-TEST', officer:{short:'PDO Chapparadahalli', name:'PDO Chapparadahalli'}, chain:[{lv:'L1',short:'PDO'},{lv:'L2',short:'EO'}], basis:'test'});
    convoAdd({you:'there is no water in my village', clip:{bars:Array.from({length:40},(_,i)=>Math.abs(Math.sin(i/3))), secs:2.4, b64:''}, say:'I understand this as drinking water.', t:Date.now()});
    J.speaking=true; SC.on=false; J.mic={}; J.analyser=null; scanTick(); J.speaking=false; J.mic=null;
    await new Promise(r=>setTimeout(r,700));
    await loadNotifs({replay:false});
    ntShow({id:9001,ts:new Date().toISOString(),tone:'new',icon:'⚡',title:'Just in · GR-504227',body:'Maintenance of Street Light · Attigodu GP, Piriyapatna · via Mitra (voice)',actions:[{label:'Open',say:'open GR-504227'}],sticky:true});
    ntShow({id:9002,ts:new Date().toISOString(),tone:'warn',icon:'🔔',title:'Reminder from the Chief Secretary',body:'GR-504227 · Maintenance of Street Light — “Only one day is left and he needs to get on top of this.”',actions:[{label:'Open',say:'open GR-504227'}],sticky:true});
    ntShow({id:9003,ts:new Date().toISOString(),tone:'bad',icon:'↩',title:'Re-opened · GR-504227',body:'The citizen says it is not solved. The clock has restarted.',actions:[{label:'Open',say:'open GR-504227'}]});
    ncAdd({id:9004,ts:new Date().toISOString(),tone:'ok',icon:'✓',title:'Sent to the citizen',body:'Accepted · GR-504227'});
    await new Promise(r=>setTimeout(r,1500));
    { const m=$('#mic'), ev=t=>m.dispatchEvent(new PointerEvent(t,{pointerId:2,bubbles:true}));
      ev('pointerdown'); ev('pointerup'); const a1={muted:J.muted,body:document.body.classList.contains('muted'),btn:m.classList.contains('muted'),state:document.body.dataset.state,wake:$('#wakeLabel').textContent,tip:m.dataset.tip};
      startCapture(true); const capWhileMuted=J.capturing;
      ev('pointerdown'); await new Promise(r=>setTimeout(r,320)); const held=m.classList.contains('hold'); ev('pointerup'); const stillMuted=J.muted;
      ev('pointerdown'); ev('pointerup'); window.__mute={tap1:a1,capWhileMuted,held,stillMutedAfterHold:stillMuted,afterTap2:{muted:J.muted,state:document.body.dataset.state,wake:$('#wakeLabel').textContent}}; }
    const pulse=document.querySelector('#pulse'); const cells=pulse?pulse.querySelectorAll('.cells i').length:-1;
    window.__v10={routed:!!document.querySelector('[data-id=routed]'), fly:!!document.querySelector('.fly'), convo:document.querySelectorAll('.convo .ex').length, clipBars:document.querySelectorAll('.convo .clip i').length, rings:document.querySelectorAll('.row .ring').length, pulseCells:cells, wave:!!document.querySelector('#wave'), outGain:!!J.outGain};
    setState('hearing','…'); captionMitra('I understand this as Maintenance of Street Light, under Rural Development and Panchayat Raj, 95 percent sure. Which village or taluk is this in? You can also ask me to use your location. If you prefer, share a photo of the petition and I will read it.',0.01); $('#prof').classList.remove('open');
    if("__ENDMUTE__"==="1")setMuted(true,{quiet:true});
    document.body.dataset.res=JSON.stringify({menuOpen:$('#prof').classList.contains('open'),profName:$('#profName').textContent,profSub:$('#profSub').textContent,
      hdrProfiles:!!document.querySelector('header .profiles'),spMeta:!!document.querySelector('#spMeta'),startText:$('#start').textContent,
      words:document.querySelectorAll('#capJv .w').length,capBox:(()=>{const b=document.querySelector('.captions'),t=document.querySelector('#trace');const rb=b.getBoundingClientRect(),rt=t.getBoundingClientRect();return {capBottom:Math.round(rb.bottom),traceTop:Math.round(rt.top),scrollH:b.scrollHeight,clientH:b.clientHeight,compBottom:Math.round(document.querySelector('.composer').getBoundingClientRect().bottom),stageH:Math.round(document.querySelector('.stage').getBoundingClientRect().bottom)}})(),capText:$('#capJv').innerText,officerPickHidden:$('#officerPick').hidden,mute:window.__mute,cards:document.querySelectorAll('#notifs .nt').length,justin:document.querySelectorAll('.ji-row').length,newtags:document.querySelectorAll('.newtag').length,bell:$('#bellN').textContent,textFocused:document.activeElement===$('#text'),v10:window.__v10});
  }catch(e){__errs.push('run '+e.message)}
  document.body.dataset.err=JSON.stringify(__errs);
},900)});
</script>""" % (sid, profile, officer, sid, profile, officer)
inject = inject.replace("__ENDMUTE__", os.environ.get("DBG_END_MUTED", "0"))  # DBG_END_MUTED
tmp = Path(__file__).resolve().parents[1] / "web" / "dbg.html"
tmp.write_text(html.replace("</body>", inject + "</body>"), encoding="utf-8")
tmp_out = Path(r"C:\Users\hp\AppData\Local\Temp\jv_dbg.png"); tmp_dom = Path(r"C:\Users\hp\AppData\Local\Temp\jv_dbg.html")
args = [EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars", "--window-size=" + (sys.argv[3] if len(sys.argv) > 3 else "1536,900"),
        f"--user-data-dir={Path.home() / 'AppData/Local/Temp' / ('jv_edge_dbg_' + profile)}", "--virtual-time-budget=9000", "--timeout=20000"]
subprocess.run(args + [f"--screenshot={tmp_out}", f"{B}/dbg.html?auto=1&noevents=1"], check=False, timeout=90)
dom = subprocess.run(args + ["--dump-dom", f"{B}/dbg.html?auto=1&noevents=1"], check=False, timeout=90, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
tmp.unlink(missing_ok=True)
import re
m = re.search(r'data-err="([^"]*)"', dom); r2 = re.search(r'data-res="([^"]*)"', dom)
import html as H
print("errors:", H.unescape(m.group(1)) if m else "(no hook result)")
print("result:", H.unescape(r2.group(1)) if r2 else "(none)")
out.write_bytes(tmp_out.read_bytes()); print("saved", out)
