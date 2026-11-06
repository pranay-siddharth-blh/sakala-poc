/* ================= CITIZEN · Sakala on WhatsApp ================= */
const WA = { started:false, lang:'en', flow:'menu', draft:{}, history:[], stage:{} };
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
const WA_SAMPLES = [
  ['💧 No drinking water','ನಮ್ಮ ಗ್ರಾಮದಲ್ಲಿ ಕಳೆದ ಒಂದು ವಾರದಿಂದ ಕುಡಿಯುವ ನೀರು ಬರುತ್ತಿಲ್ಲ'],
  ['📜 Khata delay','ಸಬ್ಬನಹಳ್ಳಿ ಗ್ರಾಮ ಸರ್ವೇ ನಂಬರ್ 53, ಪೌತಿ ಖಾತಾ ಮಾಡಲು ವಿಳಂಬ ಆಗುತ್ತಿದೆ'],
  ['👵 Pension stopped','ನಾನು ವಿಧವೆ, ಐದು ತಿಂಗಳಿಂದ ಸಂಧ್ಯಾ ಸುರಕ್ಷಾ ಪಿಂಚಣಿ ಬಂದಿಲ್ಲ'],
  ['🍚 Ration card','Applied for a new ration card three months ago, still not received.'],
  ['💡 Street light','Street light near the bus stand is not working for two weeks.'],
  ['⚡ Power cut','Power cut every evening in our village for one week.'],
];
const SERVICES = [
  {k:'cert', t:'Caste & Income Certificate', d:'Revenue · Nadakacheri · 21 days', text:'I need a caste and income certificate', days:21, dept:'REV'},
  {k:'pension', t:'Old-age pension (Sandhya Suraksha)', d:'Revenue · Social Security & Pensions', text:'Apply for Sandhya Suraksha old-age pension', days:45, dept:'REV'},
  {k:'ration', t:'New Ration Card', d:'Food & Civil Supplies', text:'Apply for a new ration card', days:30, dept:'FOOD'},
];
const tnow = () => new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:false});
const waBody = () => $('#waBody');
function waScroll(){ const b=waBody(); if(b) b.scrollTo({top:b.scrollHeight, behavior:'smooth'}); }
function waPush(m){ WA.history.push(m); bumpTrack(); const b=waBody(); if(b){ b.insertAdjacentHTML('beforeend', waRender(m)); bindWaMsg(b.lastElementChild, m); waScroll(); } }
function waRender(m){
  const time = `<span class="wa-time">${m.t}${m.me?`<svg class="wa-tick ${m.read?'read':''}" viewBox="0 0 16 11"><path d="M11.1.7 4.8 7.3 2.2 4.6.9 5.9l3.9 4L12.4 2zM15.1.7 8.8 7.3l-.9-.9-1.3 1.3 2.2 2.2L16.4 2z"/></svg>`:''}</span>`;
  let inner='';
  if (m.type==='text') inner = `<div class="wa-txt">${m.html}</div>${time}`;
  else if (m.type==='voice') inner = `<div class="wa-voice"><span class="wa-play">▶</span><span class="wa-wave">${Array.from({length:28},(_,i)=>`<i style="height:${4+Math.round(10*Math.abs(Math.sin(i*1.7)))}px"></i>`).join('')}</span><span class="wa-vlen">0:${m.len}</span></div>${time}`;
  else if (m.type==='image') inner = `<div class="wa-img"><div class="paper"><b>ಮನವಿ ಪತ್ರ</b><i></i><i></i><i></i><i style="width:60%"></i><i></i><i style="width:40%"></i></div></div><div class="wa-txt">${m.html||''}</div>${time}`;
  else if (m.type==='loc') inner = `<div class="wa-loc"><div class="mapmini"><span class="pinmini"></span></div><b>📍 ${m.html}</b><small>Live location shared</small></div>${time}`;
  else if (m.type==='card') inner = `<div class="wa-card">${m.html}</div>${time}`;
  const dis = m.used ? ' disabled' : '';
  const btns = m.buttons ? `<div class="wa-btns">${m.buttons.map((b,i)=>`<button data-i="${i}"${dis}>${b.label}</button>`).join('')}</div>` : '';
  const list = m.list ? `<div class="wa-btns"><button class="wa-listbtn"${dis}>☰ ${m.list.button}</button></div>` : '';
  return `<div class="wa-row ${m.me?'me':'bot'}"><div class="wa-bub ${m.type==='card'?'cardb':''}">${inner}</div>${btns}${list}</div>`;
}
function bindWaMsg(el, m){
  if (m.buttons) el.querySelectorAll('.wa-btns button[data-i]').forEach(b=>b.onclick=()=>{ if(m.used) return; m.used=true; el.querySelectorAll('.wa-btns button').forEach(x=>x.disabled=true); const bt=m.buttons[+b.dataset.i]; if(!bt.silent) userSay(bt.label); bt.go(); });
  if (m.list) el.querySelector('.wa-listbtn').onclick=()=>{ if(!m.used) openSheet(m, el); };
}
function bumpTrack(){ const c=document.querySelector('[data-cv="track"] .cnt'); if(c) c.textContent=S.cases.filter(x=>x.mine).length; }
function openSheet(m, el){
  const ph=$('#iphone'); ph.insertAdjacentHTML('beforeend', `<div class="wa-sheet-bg"></div><div class="wa-sheet"><div class="grab"></div><h4>${m.list.title}</h4>${m.list.rows.map((r,i)=>`<button data-i="${i}"><span><b>${r.t}</b><small>${r.d||''}</small></span><i></i></button>`).join('')}</div>`);
  requestAnimationFrame(()=>{ ph.querySelector('.wa-sheet').classList.add('on'); ph.querySelector('.wa-sheet-bg').classList.add('on'); });
  const close=()=>{ const s=ph.querySelector('.wa-sheet'), bg=ph.querySelector('.wa-sheet-bg'); s.classList.remove('on'); bg.classList.remove('on'); setTimeout(()=>{s.remove();bg.remove();},260); };
  ph.querySelector('.wa-sheet-bg').onclick=close;
  ph.querySelectorAll('.wa-sheet button[data-i]').forEach(b=>b.onclick=()=>{ const r=m.list.rows[+b.dataset.i]; m.used=true; el?.querySelector('.wa-listbtn')?.setAttribute('disabled',''); close(); userSay(r.t); setTimeout(r.go,180); });
}
function userSay(text, type='text', extra={}){ const m={me:true,type,html:esc(text),t:tnow(),...extra}; waPush(m); setTimeout(()=>{ m.read=true; const ticks=waBody()?.querySelectorAll('.wa-row.me .wa-tick'); ticks?.forEach(t=>t.classList.add('read')); },700); return m; }
function botSay(html, opts={}, delay=750){
  return new Promise(res=>{ const b=waBody(); $('#waStatus') && ($('#waStatus').textContent='typing…');
    b?.insertAdjacentHTML('beforeend','<div class="wa-row bot wa-typing-row"><div class="wa-bub"><span class="wa-dots"><i></i><i></i><i></i></span></div></div>'); waScroll();
    setTimeout(()=>{ b?.querySelector('.wa-typing-row')?.remove(); $('#waStatus') && ($('#waStatus').textContent='online'); waPush({me:false,type:opts.type||'text',html,t:tnow(),...opts}); res(); }, delay); });
}
function setChips(list){ const q=$('#waQuick'); if(!q) return; q.innerHTML = (list||[]).map((c,i)=>`<button data-i="${i}">${c[0]}</button>`).join(''); q.querySelectorAll('button').forEach(b=>b.onclick=()=>{ const c=list[+b.dataset.i]; q.innerHTML=''; handleFree(c[1]); }); }
function stage(i, note, state='done'){ WA.stage[i]={note,state}; const el=document.querySelector(`.pl-step[data-s="${i}"]`); if(el){ el.className='pl-step '+state; el.querySelector('.pl-note').textContent=note||el.querySelector('.pl-note').dataset.def; } }
function resetStages(){ WA.stage={}; document.querySelectorAll('.pl-step').forEach(el=>{ el.className='pl-step'; el.querySelector('.pl-note').textContent=el.querySelector('.pl-note').dataset.def; }); const r=$('#plResult'); if(r) r.innerHTML=''; }
const sleep = ms => new Promise(r=>setTimeout(r,ms));

async function waStart(){
  WA.started=true;
  await botSay('ನಮಸ್ಕಾರ 🙏 <b>Namaskara!</b><br>I am <b>Sakala AI</b>, the Government of Karnataka’s citizen assistant. Raise a grievance, apply for a service or track a request, right here on WhatsApp. No app to install.',{},600);
  await botSay('Which language would you like?',{buttons:[{label:'English',go:()=>{WA.lang='en';waMenu();}},{label:'ಕನ್ನಡ',go:()=>{WA.lang='kn';waMenu();}}]},500);
}
async function waMenu(){
  WA.flow='menu'; setChips(null);
  await botSay(WA.lang==='kn'?'ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ? 👇':'How can I help you today? 👇',{list:{button:'View options',title:'Sakala AI · choose an option',rows:[
    {t:'📝 Raise a grievance',d:'Water, roads, pension, land records, ration…',go:waGrievance},
    {t:'📄 Apply for a service',d:'Sakala-guaranteed services with a legal deadline',go:waApply},
    {t:'🔎 Track my request',d:'Status, officer and days left',go:waTrack},
    {t:'☎️ Talk to an officer',d:'Call-back from the helpline · production',go:()=>botSay('A helpline officer will call you back within 2 working hours. <span class="wa-prod">PRODUCTION PHASE</span>').then(waMenu)},
  ]}});
}
async function waGrievance(){
  WA.flow='grievance'; WA.draft={}; resetStages();
  await botSay('Tell me what is wrong. You can <b>type</b>, send a <b>🎤 voice note</b> or a <b>📷 photo of your petition</b>, in Kannada or English.');
  setChips(WA_SAMPLES);
}
async function handleFree(text, viaVoice=false, viaImage=false){
  if (!viaVoice && !viaImage) userSay(text);
  if (WA.flow==='apply_name'){ return applyName(text); }
  const cmd = text.trim().toLowerCase();
  if (/^(hi+|hello|hey|menu|start|namaskara|namaste|ನಮಸ್ಕಾರ|ನಮಸ್ತೆ)[!. ]*$/.test(cmd)) return waMenu();
  if (/^(track|status|ಸ್ಥಿತಿ)\b/.test(cmd)) return waTrack();
  if (WA.flow!=='grievance'){ WA.flow='grievance'; WA.draft={}; resetStages(); }
  setChips(null);
  stage(0, viaVoice?'Voice note received on WhatsApp':viaImage?'Photo of petition received':'Message received on WhatsApp');
  const masked = mask(text); await sleep(250);
  stage(1, masked!==text?'1 personal number masked before AI':'Nothing personal to mask');
  stage(2, 'Reading the request…','run');
  const u = understand(masked); await sleep(650);
  if (u.type==='WRONG_DOOR'){ stage(2,'Not a grievance (RTI)','warn'); return botSay(`ℹ️ ${esc(u.reason)}`).then(waMenu); }
  if (u.type==='OUT_OF_SCOPE'){ stage(2, `${u.dept} · outside pilot`,'warn');
    await botSay(`I understood this as <b>${esc(u.dept)}</b> → <b>${esc(u.line)}</b>.<br><br>This department is outside the 3 pilot departments, so in production it goes straight to the CESC field officer through iPGRS. <span class="wa-prod">PRODUCTION PHASE</span>`); return waMenu(); }
  if (u.type==='LOW'){ stage(2,'Unclear · confidence 41%','warn'); const id='GR-'+(++S.seq);
    S.cases.push({id,text,masked,src:'whatsapp',district:'Mysuru',taluk:'Piriyapatna',gp:'',u,owner:'rd_eo_pp',level:'L2',levelSince:new Date(S.now),created:new Date(S.now),status:'Scrutiny',history:[{t:new Date(S.now),who:'Sakala AI',what:'Sent to scrutiny desk',c:'#c98a00',note:'Low confidence'}],mine:true});
    return botSay(`I want to be sure this reaches the right office, so a <b>person at the scrutiny desk</b> will check it. Reference <b>${id}</b>. You will hear from us here. 🙏`).then(waMenu); }
  if (u.type==='APPLICATION'){ const sv=SERVICES.find(s=>s.t===u.svc)||SERVICES[0]; stage(2,`Service request · ${sv.t} (Sakala-notified)`);
    return botSay(`This is a request for a <b>Sakala-guaranteed service</b>: <b>${esc(sv.t)}</b>.<br>It has a legal deadline of <b>${sv.days} days</b>. Shall I start the application?`,{buttons:[{label:'📄 Apply now',go:()=>applyStart(sv)},{label:'🏠 Main menu',go:waMenu}]}); }
  WA.draft = {text, masked, u, src: viaVoice?'whatsapp-voice':viaImage?'whatsapp-photo':'whatsapp'};
  stage(2, `${DEPTS[u.d].name.split(' ')[0]} › ${u.svc} · ${Math.round(u.conf*100)}%`);
  await botSay(`Got it 👍 I understand this as:<br><b>${esc(DEPTS[u.d].name)}</b> → ${esc(u.line)} → <b>${esc(u.svc)}</b><br><span class="wa-muted">“${esc(u.gr)}” · ${Math.round(u.conf*100)}% sure</span>${u.vulnerable?'<br>♥ <i>Marked as priority (vulnerable citizen)</i>':''}`);
  const gp = detectGP(text);
  if (gp){ WA.draft.gp=gp; WA.draft.taluk=talukOf(gp); stage(3, `Village found in message: ${gp}`); return waConfirm(); }
  stage(3,'Asking for the village / GP','run');
  await botSay('Where is this problem? Share your <b>📍 location</b> or choose the taluk.',{buttons:[
    {label:'📍 Share location', silent:true, go:()=>{ waPush({me:true,type:'loc',html:'Atthigudu, Piriyapatna',t:tnow()}); WA.draft.taluk='Piriyapatna'; WA.draft.gp='Atthigudu'; stage(3,'GPS → Atthigudu GP, Piriyapatna'); setTimeout(waConfirm,300);} },
    {label:'Piriyapatna', go:()=>askGP('Piriyapatna')},{label:'Hunsur', go:()=>askGP('Hunsur')}]});
}
async function askGP(tk){ WA.draft.taluk=tk;
  await botSay(`Which village / Gram Panchayat in <b>${tk}</b>?`,{list:{button:'Choose village',title:`${tk} · villages`,rows:GEO.Mysuru[tk].map(g=>({t:g,d:`${tk} taluk`,go:()=>{ WA.draft.gp=g; stage(3,`Village: ${g} GP`); waConfirm(); }}))}}); }
async function waConfirm(){
  const d=WA.draft; stage(4,'Waiting for citizen to confirm','run');
  const dup = S.cases.find(c=>c.status!=='Resolved' && c.gp===d.gp && c.u.svc===d.u.svc);
  await botSay(`<div class="wa-sum"><b>Please confirm</b><span>Problem</span><p>${esc(d.u.gr)}</p><span>Service</span><p>${esc(d.u.svc)} · ${esc(DEPTS[d.u.d].name)}</p><span>Location</span><p>${d.gp?d.gp+' GP, ':''}${d.taluk} taluk, Mysuru</p>${dup?`<span>Note</span><p>A similar open request exists (${dup.id}); yours will be linked to it.</p>`:''}</div>`,{type:'card',buttons:[{label:'✅ Submit',go:waSubmit},{label:'✏️ Change',go:waGrievance}]});
}
async function waSubmit(){
  const d=WA.draft, u=d.u; stage(4,'Confirmed by citizen · location valid');
  stage(5,'Finding the exact officer…','run'); await sleep(450);
  let off = routeOfficer(u,d.taluk,d.gp), fallback=false; if(off&&off.fallback){off=off.fallback;fallback=true;} if(!off){off='rd_eo_pp';fallback=true;}
  const id='GR-'+(++S.seq);
  const c={id,text:d.text,masked:d.masked,src:'whatsapp',district:'Mysuru',taluk:d.taluk,gp:d.gp||'',u,owner:off,level:OFF[off].lv,levelSince:new Date(S.now),created:new Date(S.now),status:'Pending',history:[],vulnerable:!!u.vulnerable,mine:true};
  c.history.push({t:new Date(S.now),who:'Sakala AI',what:`Routed to ${OFF[off].short}`,c:'#26732f',note:`${u.svc} · via WhatsApp · confidence ${Math.round(u.conf*100)}%`});
  S.cases.push(c); S.notifs.push({to:off,t:new Date(S.now),m:`New grievance ${id} from WhatsApp`});
  const chain=[]; let o=off; while(o){chain.push(o);o=OFF[o].up;}
  stage(5, `${OFF[off].short}${fallback?' (taluk fallback)':''}`);
  stage(6, `${SLA[OFF[off].lv]} days · then ${OFF[off].up?OFF[OFF[off].up].short:'—'}`);
  stage(7, 'Visible to officer & Chief Secretary now');
  $('#plResult').innerHTML = `<div class="pl-route"><div class="avatar">${OFF[off].short.split(' ').map(w=>w[0]).join('').slice(0,2)}</div><div><small>Routed in 2.4 s to</small><b>${esc(OFF[off].n)}</b><div class="chain">${chain.map((x,i)=>`<span class="lv ${i===0?'cur':''}">${OFF[x].lv} · ${esc(OFF[x].short)}</span>${i<chain.length-1?'<i>→</i>':''}`).join('')}</div></div></div><button class="btn primary sm" id="plOpen">${svg('inbox')}Open in officer’s inbox</button>`;
  $('#plOpen').onclick=()=>{ S.profile='officer'; S.officer=off; S.officerView='inbox'; render(); setTimeout(()=>openCase(id),350); };
  await botSay(`<div class="wa-ok"><span class="wa-okic">✓</span><b>Registered · ${id}</b><p>Assigned to <b>${esc(OFF[off].n)}</b>, the officer responsible for ${d.gp?d.gp+' GP':d.taluk+' taluk'}.</p><p>⏱ Action due in <b>${SLA[OFF[off].lv]} days</b>. If not acted on, it moves automatically to <b>${OFF[off].up?esc(OFF[OFF[off].up].short):'senior officers'}</b>.</p><p class="wa-muted">You will get every update here. Reply <b>TRACK</b> anytime.</p></div>`,{type:'card',buttons:[{label:'🔎 Track this',go:waTrack},{label:'🏠 Main menu',go:waMenu}]},900);
  toast('Routed from WhatsApp', `${id} → ${OFF[off].short}`);
}
async function waApply(){
  WA.flow='apply'; resetStages();
  await botSay('Which service do you want to apply for? Each one has a <b>legal deadline</b> under the Sakala Act.',{list:{button:'Choose service',title:'Sakala services',rows:SERVICES.map(sv=>({t:sv.t,d:sv.d,go:()=>applyStart(sv)}))}});
}
async function applyStart(sv){ WA.draft={sv}; stage(0,`Service application: ${sv.t}`); stage(1,'Personal data protected'); stage(2,`${sv.t} · Sakala-notified`);
  stage(3,'Checklist: name, village, documents','run'); WA.flow='apply_name';
  await botSay(`To apply for <b>${sv.t}</b> I need 3 things:<br>1️⃣ Applicant’s name<br>2️⃣ Village<br>3️⃣ Photo of ration card / Aadhaar<br><br>What is the <b>applicant’s full name</b>?`); setChips([['Lakshmi K','Lakshmi K']]); }
async function applyName(name){ WA.draft.name=name; WA.flow='apply'; setChips(null);
  await botSay(`Thank you. Which village is <b>${esc(name)}</b> from?`,{list:{button:'Choose village',title:'Villages · pilot taluks',rows:[...GEO.Mysuru.Piriyapatna.map(g=>({t:g,d:'Piriyapatna taluk',go:()=>applyVillage(g,'Piriyapatna')})),...GEO.Mysuru.Hunsur.map(g=>({t:g,d:'Hunsur taluk',go:()=>applyVillage(g,'Hunsur')}))]}}); }
async function applyVillage(g,tk){ WA.draft.gp=g; WA.draft.taluk=tk;
  await botSay('Now send a <b>📷 photo</b> of the ration card or Aadhaar (use the camera button, or tap below).',{buttons:[{label:'📷 Send document photo',silent:true,go:applyDoc}]}); }
async function applyDoc(){ waPush({me:true,type:'image',html:'Ration card',t:tnow()}); stage(3,'Document received · reading…','run');
  await botSay(`📄 I read the document:<br><span class="wa-muted">Card type: BPL ration card · Card no: [ID-MASKED] · Village: ${WA.draft.gp}</span>`,{},1100);
  stage(3,'All details complete'); stage(4,'Validated · no duplicate application');
  const sv=WA.draft.sv, tk=WA.draft.taluk, off = sv.dept==='FOOD' ? (tk==='Hunsur'?'fi_hn':'fi_pp') : (tk==='Hunsur'?'rev_t_hn':'rev_t_pp');
  const co = sv.dept==='FOOD'?'food_dd':'rev_ac', aa='rev_dc';
  const id = 'SK-'+(sv.dept==='FOOD'?'FD201':'RD855')+'S26'+String(++S.seq).padStart(6,'0');
  const c={id,text:`${sv.text} for ${WA.draft.name}`,masked:`${sv.text} for ${WA.draft.name}`,src:'whatsapp',district:'Mysuru',taluk:tk,gp:WA.draft.gp,u:{...understand(sv.text),type:'APPLICATION'},owner:off,level:'L1',levelSince:new Date(S.now),created:new Date(S.now),status:'Pending',history:[],mine:true,synthetic:true};
  c.u.svc=sv.t; c.sakala={service:sv.t,dueDays:sv.days,DO:off,CO:co,AA:aa,complete:new Date(S.now)};
  c.history.push({t:new Date(S.now),who:'Sakala AI',what:`Application registered · Designated Officer ${OFF[off].short}`,c:'#26732f',note:'Complete on submission · legal clock started'}); S.cases.push(c);
  const due=new Date(+S.now+sv.days*DAY);
  stage(5,`Designated Officer: ${OFF[off].short}`); stage(6,`Legal deadline ${fmt(due)} (${sv.days} days)`); stage(7,'On officer’s Sakala list now');
  $('#plResult').innerHTML = `<div class="pl-route"><div class="avatar">${OFF[off].short.split(' ').map(w=>w[0]).join('').slice(0,2)}</div><div><small>Sakala application ${id}</small><b>${esc(OFF[off].n)}</b><div class="chain"><span class="lv cur">Designated · ${esc(OFF[off].short)}</span><i>→</i><span class="lv">Competent · ${esc(OFF[co].short)}</span><i>→</i><span class="lv">Appellate · ${esc(OFF[aa].short)}</span></div></div></div>`;
  await botSay(`<div class="wa-ok"><span class="wa-okic">✓</span><b>Application accepted</b><p>Sakala No. <b>${id}</b><br>${sv.t} · ${esc(WA.draft.name)}</p><p>⏱ Guaranteed by <b>${fmt(due)}</b> (${sv.days} days, Sakala Act). Designated Officer: <b>${esc(OFF[off].short)}</b>.</p><p class="wa-muted">If it is late, you can appeal and claim ₹20 per day (up to ₹500).</p></div>`,{type:'card',buttons:[{label:'🔎 Track',go:waTrack},{label:'🏠 Main menu',go:waMenu}]},900);
}
async function waTrack(){
  const mine=S.cases.filter(c=>c.mine).slice(-4).reverse();
  if(!mine.length) return botSay('You have no requests yet. Raise one from the menu 🙂').then(waMenu);
  await botSay(`<b>Your requests</b>${mine.map(c=>{const s=slaInfo(c);return `<div class="wa-trk"><b>${c.id}</b><span>${esc(c.u.svc||'')}</span><span>With ${esc(OFF[c.owner].short)} · ${c.level}</span><span class="${c.status==='Resolved'?'ok':s.left<0?'bad':''}">${c.status==='Resolved'?'✅ Resolved':s.left<0?`⚠️ ${-s.left} days overdue · escalated`:`⏳ ${s.left} days left`}</span></div>`}).join('')}`,{type:'card',buttons:[{label:'🏠 Main menu',go:waMenu}]});
}
function renderCitizen(){
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
        <div class="eyebrow">Citizen · no app to install</div>
        <h1>Sakala on <span>WhatsApp</span></h1>
        <p>Say <b>“Hi”</b> to Sakala AI on WhatsApp, in Kannada or English. It understands the problem, asks only for what is missing, and sends it to the <b>exact officer for your village</b> in seconds.</p>
        <div class="wa-feats">
          <div><i>💬</i><span><b>Type, speak or snap</b>Text, voice note, photo of a paper petition, live location</span></div>
          <div><i>🔒</i><span><b>Privacy first</b>Phone, Aadhaar and ration-card numbers are masked before the AI reads anything</span></div>
          <div><i>🎯</i><span><b>Exact officer</b>Village / GP → PDO, Tahsildar or Food Inspector, with the escalation chain set</span></div>
          <div><i>⏱️</i><span><b>Deadline you can see</b>Days left, reminders and automatic escalation; Sakala legal timelines for services</span></div>
        </div>
        <div class="wa-qr"><div class="qrbox">${Array.from({length:49},(_,i)=>`<i class="${[0,1,2,4,6,7,8,13,14,16,18,20,21,22,24,27,28,30,31,33,35,36,40,42,43,44,45,46,48].includes(i)?'on':''}"></i>`).join('')}</div>
          <div><b>Scan to chat with Sakala AI</b><small>Posters at Grama One, GP offices, ration shops & Praja Seva camps</small><small class="wa-muted">WhatsApp number allotted at go-live · <span class="prodtag">PRODUCTION</span></small></div></div>
      </div>
      <div class="iphone" id="iphone"><div class="island"></div>
        <div class="ios-status"><b>9:41</b><span class="ios-ic"><i></i><i></i><i></i><i></i><em></em><s></s></span></div>
        <div class="wa-head"><span class="wa-back">‹</span><div class="wa-av"><img src="assets/sakala-logo.svg" alt="Sakala" class="sk-logo"></div>
          <div class="wa-title"><b>Sakala AI <svg class="wa-ver" viewBox="0 0 24 24"><path d="M12 1l2.6 2.2 3.4-.4.9 3.3 3 1.7-1.3 3.2 1.3 3.2-3 1.7-.9 3.3-3.4-.4L12 23l-2.6-2.2-3.4.4-.9-3.3-3-1.7L3.4 13 2.1 9.8l3-1.7.9-3.3 3.4.4z" fill="#25d366"/><path d="M7.5 12.2l3 3 6-6.2" stroke="#fff" stroke-width="2.2" fill="none"/></svg></b><small id="waStatus">online</small></div>
          <span class="wa-hic">📹</span><span class="wa-hic">📞</span></div>
        <div class="wa-body" id="waBody"><div class="wa-day">TODAY</div><div class="wa-enc">🔒 Official Government of Karnataka account · messages are end-to-end encrypted</div></div>
        <div class="wa-quick" id="waQuick"></div>
        <div class="wa-compose"><div class="wa-field"><span>🙂</span><input id="waIn" placeholder="Message" autocomplete="off"><span id="waAttach" title="Send a photo of a petition">📎</span><span id="waCam" title="Camera">📷</span>
          <div class="wa-rec"><span class="rec-dot"></span><span class="rec-t">0:03</span><span class="rec-wave">${'<i></i>'.repeat(14)}</span><span class="rec-hint">‹ slide to cancel</span></div></div>
          <button id="waSend" class="wa-mic" title="Hold to record a voice note"><svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg></button></div>
        <div class="home-bar"></div>
      </div>
      <div class="pipeline-panel"><div class="pp-h"><span class="pulse-dot"></span><div><b>Behind the chat</b><small>Sakala AI pipeline · live</small></div></div>
        <div class="pl">${STAGES.map((s,i)=>`<div class="pl-step ${WA.stage[i]?WA.stage[i].state:''}" data-s="${i}"><span class="pl-n">${i+1}</span><div><b>${s[0]}</b><span class="pl-note" data-def="${esc(s[1])}">${esc(WA.stage[i]?.note||s[1])}</span></div></div>`).join('')}</div>
        <div id="plResult"></div></div>
    </div>`;
  const body=waBody(); WA.history.forEach(m=>{ body.insertAdjacentHTML('beforeend', waRender(m)); bindWaMsg(body.lastElementChild, m); }); body.scrollTop=body.scrollHeight;
  const inp=$('#waIn'), send=$('#waSend');
  const setBtn=()=>{ const has=inp.value.trim().length>0; send.classList.toggle('send',has); send.innerHTML = has ? '<svg viewBox="0 0 24 24"><path d="M3 20l18-8L3 4v6l12 2-12 2z" fill="#fff" stroke="none"/></svg>' : '<svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>'; };
  inp.oninput=setBtn; inp.onkeydown=e=>{ if(e.key==='Enter' && inp.value.trim()){ const v=inp.value.trim(); inp.value=''; setBtn(); handleFree(v); } };
  send.onclick=()=>{ if(inp.value.trim()){ const v=inp.value.trim(); inp.value=''; setBtn(); return handleFree(v); }
    // voice note: recording state, then a voice bubble + transcript
    const comp=$('.wa-compose'); if(comp.classList.contains('rec')) return; comp.classList.add('rec'); setChips(null);
    let sec=0; const rt=comp.querySelector('.rec-t'); const iv=setInterval(()=>{ sec++; if(rt) rt.textContent='0:0'+Math.min(9,sec); },700);
    setTimeout(()=>{ clearInterval(iv); comp.classList.remove('rec'); if(WA.flow!=='grievance'){ WA.flow='grievance'; resetStages(); }
      const said='ನಾನು ವಿಧವೆ, ಐದು ತಿಂಗಳಿಂದ ಸಂಧ್ಯಾ ಸುರಕ್ಷಾ ಪಿಂಚಣಿ ಬಂದಿಲ್ಲ. ನಮ್ಮದು ಅತ್ತಿಗೋಡು ಗ್ರಾಮ.';
      waPush({me:true,type:'voice',len:'07',t:tnow()}); botSay(`🎤 I heard: <i>“${said}”</i>`,{},900).then(()=>handleFree(said,true)); },2300); };
  const photo=()=>{ if(WA.flow==='apply') return applyDoc(); if(WA.flow!=='grievance'){ WA.flow='grievance'; resetStages(); } const read='ಹೊಸ ಪಡಿತರ ಚೀಟಿ ಅರ್ಜಿ ಸಲ್ಲಿಸಿ ಮೂರು ತಿಂಗಳಾದರೂ ಸಿಕ್ಕಿಲ್ಲ. ಬಿಳಿಕೆರೆ ಗ್ರಾಮ. ಮೊಬೈಲ್ 9845012345';
    waPush({me:true,type:'image',html:'',t:tnow()}); botSay(`📷 I read your petition: <i>“${esc(mask(read))}”</i>`,{},1100).then(()=>handleFree(read,false,true)); };
  $('#waAttach').onclick=photo; $('#waCam').onclick=photo;
  if (!WA.started) waStart(); else if (WA.flow==='grievance') setChips(WA_SAMPLES);
}
