"""Client side of two-way WhatsApp: officer bubbles, polling, notifications."""
import sys

T = sys.argv[1] if len(sys.argv) > 1 else r"D:\Sakala POC\tools"


def edit(p, old, new, count=1):
    s = open(p, encoding="utf-8").read()
    assert old in s, (p, old[:70])
    open(p, "w", encoding="utf-8").write(s.replace(old, new, count))


js = T + r"\app_wa_client.js"
# 1. officer bubble rendering
edit(js, "  else if (m.type==='card') inner = `<div class=\"wa-card\">${m.html}</div>${time}`;",
     "  else if (m.type==='card') inner = `<div class=\"wa-card\">${m.html}</div>${time}`;\n"
     "  else if (m.type==='officer') inner = `<div class=\"wa-off\"><span class=\"wa-off-av\">👮</span><span><b>${esc(m.officer||'Officer')}</b><small>${esc(m.officerFull||'')} · via Sakala AI</small></span></div><div class=\"wa-txt\">${m.html}</div>${time}`;")
edit(js, "  return `<div class=\"wa-row ${m.me?'me':'bot'}\"><div class=\"wa-bub ${m.type==='card'?'cardb':''}\">",
     "  return `<div class=\"wa-row ${m.me?'me':'bot'} ${m.type==='officer'?'officer':''}\"><div class=\"wa-bub ${m.type==='card'||m.type==='officer'?'cardb':''}\">")
# 2. split the event player out of waSend and add polling
edit(js, '''    WA.sid = res.session; persistWA();
    let first=true;
    for (const e of res.events){
      if (e.kind==='msg' && !e.me){ typing(true); await sleep(first?350:650); typing(false); first=false; waPush({me:false,type:e.type,html:e.html,buttons:e.buttons,list:e.list,t:tnow()}); }
      else if (e.kind==='msg' && e.me){ waPush({me:true,type:e.type,html:esc(e.html||''),t:tnow(),read:true}); await sleep(250); }
      else if (e.kind==='stage'){ stage(e.i, e.note, e.state); await sleep(e.state==='run'?380:200); }
      else if (e.kind==='reset') resetStages();
      else if (e.kind==='chips') setChips(e.items);
      else if (e.kind==='result') showResult(e);
      else if (e.kind==='toast') toast(e.h, e.m);
    }
    typing(false);
    if (res.events.some(e=>e.kind==='result' || (e.kind==='msg' && /GR-\\d+|SK-/.test(e.html||'')))) { try { await loadState(); bumpTrack(); } catch(e) {} }
    WA.busy=false;''', '''    WA.sid = res.session; persistWA();
    await playEvents(res.events);
    WA.busy=false;''')
edit(js, "/* one request at a time; events are played back with WhatsApp-like timing */", '''async function playEvents(events){
  let first=true;
  for (const e of events){
    if (e.kind==='msg' && !e.me){ typing(true); await sleep(first?350:650); typing(false); first=false; waPush({me:false,type:e.type,html:e.html,buttons:e.buttons,list:e.list,officer:e.officer,officerFull:e.officerFull,caseId:e.caseId,t:tnow()}); }
    else if (e.kind==='msg' && e.me){ waPush({me:true,type:e.type,html:esc(e.html||''),t:tnow(),read:true}); await sleep(250); }
    else if (e.kind==='stage'){ stage(e.i, e.note, e.state); await sleep(e.state==='run'?380:200); }
    else if (e.kind==='reset') resetStages();
    else if (e.kind==='chips') setChips(e.items);
    else if (e.kind==='result') showResult(e);
    else if (e.kind==='toast') toast(e.h, e.m);
    else if (e.kind==='notify'){ toast('WhatsApp · '+e.from, e.n>1?`${e.n} new messages from the officer`:'New message from the officer'); waPing(); }
  }
  typing(false);
  if (events.some(e=>e.kind==='result' || e.kind==='notify' || (e.kind==='msg' && /GR-\\d+|SK-/.test(e.html||'')))) { try { await loadState(); bumpTrack(); } catch(e) {} }
}
/* officer → citizen: poll the chat for delivered officer messages while the phone is on screen */
async function waPoll(){
  if (!WA.sid || WA.busy || !waBody() || S.profile!=='citizen') return;
  let res; try { res = await API('/api/chat', {session:WA.sid, action:'poll'}); } catch(e){ return; }
  if (!res.events.length || WA.busy) return;
  WA.queue = WA.queue.then(async ()=>{ WA.busy=true; await playEvents(res.events); WA.busy=false; });
}
if (!window._waPollTimer) window._waPollTimer = setInterval(waPoll, 3500);
function waPing(){ const ph=$('#iphone'); if(!ph) return; ph.classList.remove('ping'); void ph.offsetWidth; ph.classList.add('ping'); try{ const ctx=new (window.AudioContext||window.webkitAudioContext)(); const o=ctx.createOscillator(), g=ctx.createGain(); o.type='sine'; o.frequency.setValueAtTime(880,ctx.currentTime); o.frequency.setValueAtTime(1175,ctx.currentTime+.09); g.gain.setValueAtTime(.0001,ctx.currentTime); g.gain.exponentialRampToValueAtTime(.12,ctx.currentTime+.02); g.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+.35); o.connect(g); g.connect(ctx.destination); o.start(); o.stop(ctx.currentTime+.4); }catch(e){} }
/* one request at a time; events are played back with WhatsApp-like timing */''')
# 3. poll right after the phone renders (e.g. coming back from the officer screen)
edit(js, "  if (!WA.started){ WA.started=true; waSend({action:'start'}); }", "  if (!WA.started){ WA.started=true; waSend({action:'start'}); } else setTimeout(waPoll, 400);")

css = T + r"\future2.css"
open(css, "a", encoding="utf-8").write('''
/* officer → citizen messages inside WhatsApp */
.wa-row.officer .wa-bub{border-left:3px solid var(--em);background:#f1fbf5}
.wa-row.officer .wa-bub::before{border-right-color:#f1fbf5}
.wa-off{display:flex;align-items:center;gap:8px;margin:0 0 6px;padding-bottom:6px;border-bottom:1px solid rgba(14,159,110,.18)}
.wa-off-av{width:26px;height:26px;border-radius:50%;background:var(--em);display:grid;place-items:center;font-size:.8rem;flex:0 0 auto}
.wa-off b{display:block;font-size:.8rem;color:var(--em-ink)}
.wa-off small{display:block;font-size:.64rem;color:#54656f}
@keyframes waPing{0%{transform:translateY(0)}20%{transform:translateY(-6px)}40%{transform:translateY(0)}60%{transform:translateY(-3px)}100%{transform:translateY(0)}}
.iphone.ping{animation:waPing .6s ease}
''')
print("ui patched")
