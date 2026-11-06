/* ================= CITIZEN · Sakala on WhatsApp (server-driven: /api/chat) ================= */
const WA = { started:false, lang:'en', sid:'', history:[], stage:{}, busy:false, queue:Promise.resolve() };
try { WA.sid = sessionStorage.getItem('wa_sid') || ''; WA.history = JSON.parse(sessionStorage.getItem('wa_hist')||'[]'); WA.stage = JSON.parse(sessionStorage.getItem('wa_stage')||'{}'); WA.started = WA.history.length>0; } catch(e) {}
const persistWA = () => { try { sessionStorage.setItem('wa_sid', WA.sid); sessionStorage.setItem('wa_hist', JSON.stringify(WA.history.slice(-80).map(m=>({...m, used:true})))); sessionStorage.setItem('wa_stage', JSON.stringify(WA.stage)); } catch(e) {} };
const STAGES = [
  ['Entry','WhatsApp · one number for every citizen'],
  ['Privacy shield','Phone, Aadhaar, ration-card numbers masked'],
  ['AI understanding','Department → Line dept → Service → Grievance'],
  ['Completion agent','Asks only for what is missing'],
  ['Validate & confirm','Location, duplicates, citizen confirms'],
  ['Exact-officer routing','Village / GP → named field officer'],
  ['Deadlines & reminders','Clock starts · escalation chain armed'],
  ['Leadership view','Live on the officer & Chief Secretary screens'],
];
const tnow = () => new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:false});
const waBody = () => $('#waBody');
const sleep = ms => new Promise(r=>setTimeout(r,ms));
function waScroll(){ const b=waBody(); if(!b) return; cancelAnimationFrame(WA.sr); clearTimeout(WA.st); const from=b.scrollTop, t0=performance.now();
  const step=()=>{ const to=b.scrollHeight-b.clientHeight, k=Math.min(1,(performance.now()-t0)/340), e=1-Math.pow(1-k,3); b.scrollTop=from+(to-from)*e; if(k<1) WA.sr=requestAnimationFrame(step); };
  WA.sr=requestAnimationFrame(step); WA.st=setTimeout(()=>{ b.scrollTop=b.scrollHeight; },420); }
function bumpTrack(){ const c=document.querySelector('[data-cv="track"] .cnt'); if(c) c.textContent=S.cases.filter(x=>x.mine).length; }
function waPush(m){ WA.history.push(m); persistWA(); const b=waBody(); if(b){ b.insertAdjacentHTML('beforeend', waRender(m)); bindWaMsg(b.lastElementChild, m); waScroll(); } }
function waRender(m){
  const time = `<span class="wa-time">${m.t}${m.me?`<svg class="wa-tick ${m.read?'read':''}" viewBox="0 0 16 11"><path d="M11.1.7 4.8 7.3 2.2 4.6.9 5.9l3.9 4L12.4 2zM15.1.7 8.8 7.3l-.9-.9-1.3 1.3 2.2 2.2L16.4 2z"/></svg>`:''}</span>`;
  let inner='';
  if (m.type==='text') inner = `<div class="wa-txt">${m.html}</div>${time}`;
  else if (m.type==='voice') inner = `<div class="wa-voice"><span class="wa-play">▶</span><span class="wa-wave">${Array.from({length:28},(_,i)=>`<i style="height:${4+Math.round(10*Math.abs(Math.sin(i*1.7)))}px"></i>`).join('')}</span><span class="wa-vlen">0:${m.len||'07'}</span></div>${time}`;
  else if (m.type==='image') inner = `<div class="wa-img">${m.src?`<img src="${m.src}" alt="" style="width:100%;height:100%;object-fit:cover">`:`<div class="paper"><b>ಮನವಿ ಪತ್ರ</b><i></i><i></i><i></i><i style="width:60%"></i><i></i><i style="width:40%"></i></div>`}</div><div class="wa-txt">${m.html||''}</div>${time}`;
  else if (m.type==='loc') inner = `<div class="wa-loc"><div class="mapmini"><span class="pinmini"></span></div><b>📍 ${m.html}</b><small>Location shared (demo GPS)</small></div>${time}`;
  else if (m.type==='card') inner = `<div class="wa-card">${m.html}</div>${time}`;
  else if (m.type==='officer') inner = `<div class="wa-off"><span class="wa-off-av">👮</span><span><b>${esc(m.officer||'Officer')}</b><small>${esc(m.officerFull||'')} · via Sakala AI</small></span></div><div class="wa-txt">${m.html}</div>${time}`;
  const dis = m.used ? ' disabled' : '';
  const btns = m.buttons ? `<div class="wa-btns">${m.buttons.map((b,i)=>`<button data-i="${i}"${dis}>${b.label}</button>`).join('')}</div>` : '';
  const list = m.list ? `<div class="wa-btns"><button class="wa-listbtn"${dis}>☰ ${m.list.button}</button></div>` : '';
  return `<div class="wa-row ${m.me?'me':'bot'} ${m.type==='officer'?'officer':''}"><div class="wa-bub ${m.type==='card'||m.type==='officer'?'cardb':''}">${inner}</div>${btns}${list}</div>`;
}
function bindWaMsg(el, m){
  if (m.buttons) el.querySelectorAll('.wa-btns button[data-i]').forEach(b=>b.onclick=()=>{ if(m.used||WA.busy) return; m.used=true; persistWA(); el.querySelectorAll('.wa-btns button').forEach(x=>x.disabled=true); const bt=m.buttons[+b.dataset.i]; waSend({action:bt.action}, bt.silent?null:bt.label); });
  if (m.list) el.querySelector('.wa-listbtn').onclick=()=>{ if(!m.used && !WA.busy) openSheet(m, el); };
}
function openSheet(m, el){
  const ph=$('#iphone'); ph.insertAdjacentHTML('beforeend', `<div class="wa-sheet-bg"></div><div class="wa-sheet"><div class="grab"></div><h4>${esc(m.list.title)}</h4>${m.list.rows.map((r,i)=>`<button data-i="${i}"><span><b>${esc(r.t)}</b><small>${esc(r.d||'')}</small></span><i></i></button>`).join('')}</div>`);
  const sh=ph.querySelector('.wa-sheet:last-of-type'), sbg=sh.previousElementSibling;
  requestAnimationFrame(()=>requestAnimationFrame(()=>{ sh.classList.add('on'); sbg.classList.add('on'); }));
  const close=()=>{ sh.classList.remove('on'); sbg.classList.remove('on'); setTimeout(()=>{sh.remove();sbg.remove();},280); };
  sbg.onclick=close;
  sh.querySelectorAll('button[data-i]').forEach(b=>b.onclick=()=>{ const r=m.list.rows[+b.dataset.i]; m.used=true; persistWA(); el?.querySelector('.wa-listbtn')?.setAttribute('disabled',''); close(); setTimeout(()=>waSend({action:r.action}, r.t),180); });
}
function userSay(text, type='text', extra={}){ const m={me:true,type,html:esc(text),t:tnow(),...extra}; waPush(m); setTimeout(()=>{ m.read=true; waBody()?.querySelectorAll('.wa-row.me .wa-tick').forEach(t=>t.classList.add('read')); },700); return m; }
function typing(on){ const b=waBody(); $('#waStatus') && ($('#waStatus').textContent=on?'typing…':'online');
  if(on){ if(b && !b.querySelector('.wa-typing-row')){ b.insertAdjacentHTML('beforeend','<div class="wa-row bot wa-typing-row"><div class="wa-bub"><span class="wa-dots"><i></i><i></i><i></i></span></div></div>'); waScroll(); } }
  else b?.querySelector('.wa-typing-row')?.remove(); }
function setChips(list){ const q=$('#waQuick'); if(!q) return; WA.chips=list||null; q.innerHTML = (list||[]).map((c,i)=>`<button data-i="${i}">${esc(c[0])}</button>`).join(''); q.querySelectorAll('button').forEach(b=>b.onclick=()=>{ const c=list[+b.dataset.i]; q.innerHTML=''; WA.chips=null; waSend({text:c[1]}, c[1]); }); }
function stage(i, note, state='done'){ WA.stage[i]={note,state}; persistWA(); const el=document.querySelector(`.pl-step[data-s="${i}"]`); if(el){ el.className='pl-step '+state; el.querySelector('.pl-note').textContent=note||el.querySelector('.pl-note').dataset.def; } }
function resetStages(){ WA.stage={}; WA.result=null; persistWA(); document.querySelectorAll('.pl-step').forEach(el=>{ el.className='pl-step'; el.querySelector('.pl-note').textContent=el.querySelector('.pl-note').dataset.def; }); const r=$('#plResult'); if(r) r.innerHTML=''; }
function showResult(e){
  WA.result=e; const r=$('#plResult'); if(!r) return;
  r.innerHTML = `<div class="pl-route"><div class="avatar">${esc(e.officer.short.split(' ').map(w=>w[0]).join('').slice(0,2))}</div><div><small>${esc(e.title)}</small><b>${esc(e.officer.name)}</b><div class="chain">${e.chain.map((x,i)=>`<span class="lv ${i===0?'cur':''}">${esc(x.lv)} · ${esc(x.short)}</span>${i<e.chain.length-1?'<i>→</i>':''}`).join('')}</div></div></div>
    ${e.basis && !e.basis.startsWith('Sakala application')?`<p class="pl-basis">${esc(e.basis)}</p>`:''}<button class="btn primary sm" id="plOpen">${svg('inbox')}Open in officer’s inbox</button>`;
  const pp=document.querySelector('.pipeline-panel'); if(pp) setTimeout(()=>pp.scrollTo({top:pp.scrollHeight,behavior:'smooth'}),120);
  $('#plOpen').onclick=()=>{ S.profile='officer'; S.officer=e.officer.id; S.officerView=e.caseId.startsWith('SK-')?'sakala':'inbox'; render(); setTimeout(()=>openCase(e.caseId),350); };
}
async function playEvents(events){
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
  if (events.some(e=>e.kind==='result' || e.kind==='notify' || (e.kind==='msg' && /GR-\d+|SK-/.test(e.html||'')))) { try { await loadState(); bumpTrack(); } catch(e) {} }
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
/* one request at a time; events are played back with WhatsApp-like timing */
function waSend(payload, echo){
  if (echo) userSay(echo);
  setChips(null);
  WA.queue = WA.queue.then(async ()=>{
    WA.busy=true; typing(true);
    let res;
    try { res = await API('/api/chat', {session:WA.sid, ...payload}); }
    catch(err){ typing(false); waPush({me:false,type:'text',html:'⚠️ Network problem. Please try again.',t:tnow()}); WA.busy=false; return; }
    WA.sid = res.session; persistWA();
    await playEvents(res.events);
    WA.busy=false;
  });
  return WA.queue;
}
/* voice note: real microphone → 16 kHz WAV → speech model on the server; sample note when no microphone */
function encodeWav(chunks, inRate, outRate=16000){
  const len=chunks.reduce((a,c)=>a+c.length,0), data=new Float32Array(len); let o=0; for(const c of chunks){ data.set(c,o); o+=c.length; }
  const ratio=inRate/outRate, n=Math.floor(len/ratio), buf=new ArrayBuffer(44+n*2), v=new DataView(buf), w=(off,str)=>{ for(let i=0;i<str.length;i++) v.setUint8(off+i,str.charCodeAt(i)); };
  w(0,'RIFF'); v.setUint32(4,36+n*2,true); w(8,'WAVE'); w(12,'fmt '); v.setUint32(16,16,true); v.setUint16(20,1,true); v.setUint16(22,1,true);
  v.setUint32(24,outRate,true); v.setUint32(28,outRate*2,true); v.setUint16(32,2,true); v.setUint16(34,16,true); w(36,'data'); v.setUint32(40,n*2,true);
  for(let i=0;i<n;i++){ let x=0; const a=Math.floor(i*ratio), b=Math.min(len,Math.floor((i+1)*ratio)); for(let j=a;j<b;j++) x+=data[j]; x/=Math.max(1,b-a); x=Math.max(-1,Math.min(1,x)); v.setInt16(44+i*2, x<0?x*0x8000:x*0x7fff, true); }
  return buf;
}
const b64 = buf => { const u=new Uint8Array(buf); let s=''; for(let i=0;i<u.length;i+=0x8000) s+=String.fromCharCode.apply(null,u.subarray(i,i+0x8000)); return btoa(s); };
async function startVoice(){
  const comp=$('.wa-compose'); if(!comp || WA.busy) return;
  if (WA.rec){ return WA.rec.finish(); }                                   // second tap = send
  setChips(null); comp.classList.add('rec');
  let sec=0; const rt=comp.querySelector('.rec-t'); const iv=setInterval(()=>{ sec++; if(rt) rt.textContent='0:'+String(sec).padStart(2,'0'); },1000);
  const hint=comp.querySelector('.rec-hint'); if(hint) hint.textContent='tap ● again to send';
  const done = (payload, len) => { clearInterval(iv); comp.classList.remove('rec'); WA.rec=null; waPush({me:true,type:'voice',len:String(Math.max(2,len)).padStart(2,'0'),t:tnow(),read:true}); waSend({action:'voice', ...payload}); };
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('no mic');
    WA.rec = { finish: () => {} };                                          // busy until the microphone answers
    const stream = await Promise.race([navigator.mediaDevices.getUserMedia({audio:{channelCount:1, echoCancellation:true, noiseSuppression:true}}),
                                       new Promise((_,rej)=>setTimeout(()=>rej(new Error('mic timeout')),5000))]);
    const ctx = new (window.AudioContext||window.webkitAudioContext)(); const src=ctx.createMediaStreamSource(stream); const proc=ctx.createScriptProcessor(4096,1,1); const chunks=[];
    proc.onaudioprocess = e => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0))); src.connect(proc); proc.connect(ctx.destination);
    let finished=false;
    WA.rec = { finish: () => { if(finished) return; finished=true; try{ proc.disconnect(); src.disconnect(); }catch(e){} stream.getTracks().forEach(t=>t.stop()); const rate=ctx.sampleRate; ctx.close();
      const secs = chunks.reduce((a,c)=>a+c.length,0)/rate; if (secs < 0.6) { clearInterval(iv); comp.classList.remove('rec'); WA.rec=null; toast('Voice note','Too short. Tap the mic, speak, then tap again.'); return; }
      done({audio_b64: b64(encodeWav(chunks, rate))}, Math.round(secs)); } };
    setTimeout(()=>WA.rec && WA.rec.finish(), 20000);
  } catch(e) {                                                              // no microphone / permission denied → sample voice note
    WA.rec = { finish: () => {} }; setTimeout(()=>done({}, 7), 2300);
  }
}
function fitWA(){ const h=document.querySelector('.gov-header'); if(h) document.documentElement.style.setProperty('--hdr', h.offsetHeight+'px'); }
if (!window._waFit){ window._waFit=true; window.addEventListener('resize', fitWA); }
function renderCitizen(){
  fitWA();
  $('#sidebar').innerHTML = `
    <div><div class="side-h">Citizen services</div><div class="nav">
      <button class="${S.citizenView!=='track'?'on':''}" data-cv="wa"><span class="ic wa-ic"><svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2z"/><path d="M8.5 7.5c.3-.6.7-.6 1-.6h.6c.2 0 .4.1.5.4l.8 1.9c.1.2 0 .5-.1.7l-.5.6c-.1.2-.1.4 0 .6.6 1 1.4 1.8 2.4 2.4.2.1.4.1.6 0l.6-.5c.2-.2.5-.2.7-.1l1.9.8c.3.1.4.3.4.5v.6c0 .3 0 .7-.6 1-1 .5-2.5.6-4.6-.9-2.1-1.4-3.4-3.3-3.8-4.6-.3-1-.2-2 .1-2.8z"/></svg></span><span>Sakala on WhatsApp<small>Raise · apply · track, in one chat</small></span><span class="cnt live">LIVE</span></button>
      <button class="${S.citizenView==='track'?'on':''}" data-cv="track"><span class="ic">${svg('track')}</span><span>Track my requests<small>Live status & officer</small></span><span class="cnt">${S.cases.filter(c=>c.mine).length}</span></button>
    </div></div>
    <div class="side-note"><b>One assistant, every channel.</b> WhatsApp, the 1902 call centre, Praja Seva camps, Grama One / CSC counters and the app all feed this same AI pipeline.</div>`;
  $('#sidebar').querySelectorAll('[data-cv]').forEach(b=>b.onclick=()=>{ S.citizenView=b.dataset.cv; render(); });
  if (S.citizenView==='track') return renderTrack();
  $('#content').innerHTML = `
    <div class="wa-stage">
      <div class="wa-left">
        <h1>Sakala on <span>WhatsApp</span></h1>
        <p>Say <b>“Hi”</b> to Sakala AI on WhatsApp, in Kannada or English. It understands the problem, asks only for what is missing, and sends it to the <b>exact officer for your village</b> in seconds.</p>
        <div class="wa-feats">
          <div><i>💬</i><span><b>Type, speak or snap</b>Text, voice note, photo of a paper petition, live location</span></div>
          <div><i>🔒</i><span><b>Privacy first</b>Phone, Aadhaar and ration-card numbers are masked before the AI reads anything</span></div>
          <div><i>🎯</i><span><b>Exact officer</b>Village → Gram Panchayat → PDO, Tahsildar, ADLR or Food Inspector · ${Math.round((BOOT.evals.routing?.rate||0)*1000)/10}% agreement with real iPGRS assignments</span></div>
          <div><i>⏱️</i><span><b>Deadline you can see</b>Days left, reminders and automatic escalation; Sakala legal timelines for services</span></div>
        </div>
        <div class="wa-qr"><div class="qrbox">${Array.from({length:49},(_,i)=>`<i class="${[0,1,2,4,6,7,8,13,14,16,18,20,21,22,24,27,28,30,31,33,35,36,40,42,43,44,45,46,48].includes(i)?'on':''}"></i>`).join('')}</div>
          <div><b>Scan to chat with Sakala AI</b><small>Posters at Grama One, GP offices, ration shops & Praja Seva camps</small><small class="wa-muted">WhatsApp number allotted at go-live · <span class="prodtag">PRODUCTION</span></small></div></div>
      </div>
      <div class="iphone" id="iphone"><div class="island"></div>
        <div class="ios-status"><b>9:41</b><span class="ios-ic"><i></i><i></i><i></i><i></i><em></em><s></s></span></div>
        <div class="wa-head"><span class="wa-back" id="waRestart" title="New chat">‹</span><div class="wa-av"><img src="assets/sakala-logo.svg" alt="Sakala" class="sk-logo"></div>
          <div class="wa-title"><b>Sakala AI <svg class="wa-ver" viewBox="0 0 24 24"><path d="M12 1l2.6 2.2 3.4-.4.9 3.3 3 1.7-1.3 3.2 1.3 3.2-3 1.7-.9 3.3-3.4-.4L12 23l-2.6-2.2-3.4.4-.9-3.3-3-1.7L3.4 13 2.1 9.8l3-1.7.9-3.3 3.4.4z" fill="#25d366"/><path d="M7.5 12.2l3 3 6-6.2" stroke="#fff" stroke-width="2.2" fill="none"/></svg></b><small id="waStatus">online</small></div>
          <span class="wa-hic">📹</span><span class="wa-hic">📞</span></div>
        <div class="wa-body" id="waBody"><div class="wa-day">TODAY</div><div class="wa-enc">🔒 Official Government of Karnataka account · messages are end-to-end encrypted</div></div>
        <div class="wa-quick" id="waQuick"></div>
        <div class="wa-compose"><div class="wa-field"><span>🙂</span><input id="waIn" placeholder="Message" autocomplete="off"><span id="waAttach" title="Send a photo of a petition from your computer">📎</span><span id="waCam" title="Sample petition photo">📷</span>
          <div class="wa-rec"><span class="rec-dot"></span><span class="rec-t">0:00</span><span class="rec-wave">${'<i></i>'.repeat(14)}</span><span class="rec-hint">listening…</span></div></div>
          <button id="waSend" class="wa-mic" title="Voice note (Kannada / English)"><svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg></button></div>
        <input type="file" id="waFile" accept="image/*" hidden>
        <div class="home-bar"></div>
      </div>
      <div class="pipeline-panel"><div class="pp-h"><span class="pulse-dot"></span><div><b>Behind the chat</b><small>Sakala AI pipeline · live</small></div></div>
        <div class="pl">${STAGES.map((s,i)=>`<div class="pl-step ${WA.stage[i]?WA.stage[i].state:''}" data-s="${i}"><span class="pl-n">${i+1}</span><div><b>${s[0]}</b><span class="pl-note" data-def="${esc(s[1])}">${esc(WA.stage[i]?.note||s[1])}</span></div></div>`).join('')}</div>
        <div id="plResult"></div></div>
    </div>`;
  const body=waBody(); WA.history.forEach(m=>{ body.insertAdjacentHTML('beforeend', waRender(m)); bindWaMsg(body.lastElementChild, m); }); body.scrollTop=body.scrollHeight;
  if (WA.result) showResult(WA.result);
  if (WA.chips) setChips(WA.chips);
  const inp=$('#waIn'), send=$('#waSend');
  const setBtn=()=>{ const has=inp.value.trim().length>0; send.classList.toggle('send',has); send.innerHTML = has ? '<svg viewBox="0 0 24 24"><path d="M3 20l18-8L3 4v6l12 2-12 2z" fill="#fff" stroke="none"/></svg>' : '<svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>'; };
  const sendText=()=>{ const v=inp.value.trim(); if(!v) return; inp.value=''; setBtn(); waSend({text:v}, v); };
  inp.oninput=setBtn; inp.onkeydown=e=>{ if(e.key==='Enter') sendText(); };
  send.onclick=()=>{ if(inp.value.trim()) return sendText(); startVoice(); };
  $('#waCam').onclick=()=>{ if(!WA.busy) waSend({action:WA.flowDoc?'doc':'photo'}); };
  $('#waAttach').onclick=()=>$('#waFile').click();
  $('#waFile').onchange=e=>{ const f=e.target.files[0]; if(!f) return; const rd=new FileReader(); rd.onload=()=>{ const [head,b64]=String(rd.result).split(','); waSend({action:'photo', image_b64:b64, media_type:(head.match(/data:(.*?);/)||[])[1]||'image/png'}); }; rd.readAsDataURL(f); e.target.value=''; };
  $('#waRestart').onclick=()=>{ if(WA.busy) return; WA.history=[]; WA.sid=''; WA.stage={}; WA.result=null; WA.chips=null; WA.started=false; persistWA(); renderCitizen(); };
  if (!WA.started){ WA.started=true; waSend({action:'start'}); } else setTimeout(waPoll, 400);
}
