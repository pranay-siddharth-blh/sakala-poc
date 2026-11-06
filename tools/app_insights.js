/* ================= Leadership intelligence screens (live API) ================= */
const LOAD = '<div class="loading"><span class="typing"><i></i><i></i><i></i></span> Computing from the data…</div>';
const pct = x => (x==null?'—':(Math.round(x*1000)/10)+'%');
const n0 = x => (x==null?'—':Number(x).toLocaleString('en-IN'));
const safeHtml = h => { const t=document.createElement('template'); t.innerHTML=String(h||''); t.content.querySelectorAll('*').forEach(el=>{ if(!['B','STRONG','I','EM','BR','P','UL','OL','LI'].includes(el.tagName)) el.replaceWith(document.createTextNode(el.textContent)); else [...el.attributes].forEach(a=>el.removeAttribute(a.name)); }); return t.innerHTML; };
const aiNote = (html, label) => html ? `<div class="ai-note"><div class="tag">${esc(label||'AI summary')} · Sakala AI</div>${safeHtml(html)}</div>` : '';
const bars = (rows, color) => { const mx=Math.max(1,...rows.map(r=>r[1])); return `<div class="hbar">${rows.map(([k,v])=>`<div class="hb"><span>${esc(k)}</span><span class="t"><b style="width:${v/mx*100}%;--c:${color||'var(--ink)'}"></b></span><span class="n">${n0(v)}</span></div>`).join('')}</div>`; };
const head = (eyebrow, title, sub, actions='') => `<div class="head"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p class="sub">${sub}</p></div>${actions?`<div class="head-actions">${actions}</div>`:''}</div>`;

async function renderInsights(){
  $('#content').innerHTML = head('Chief Secretary · intelligence','Insights','Hotspots, historical patterns, misrouting and data quality, computed from the real records')+
    `<div class="ins-grid"><div class="card"><div class="card-h"><h3>Hotspots · repeated complaints</h3><span class="r">same service, same Gram Panchayat</span></div><div class="card-b" id="iHot">${LOAD}</div></div>
     <div class="card"><div class="card-h"><h3>Praja Seva historical intelligence</h3><span class="r">9,999 real grievances</span></div><div class="card-b" id="iHist">${LOAD}</div></div>
     <div class="card"><div class="card-h"><h3>Misrouting detector</h3><span class="r">filed category vs what the text says</span></div><div class="card-b" id="iMis">${LOAD}</div></div>
     <div class="card"><div class="card-h"><h3>Data quality · intake validation</h3><span class="r">checks on the real records</span></div><div class="card-b" id="iDq">${LOAD}</div></div></div>`;
  API('/api/insights/hotspots?fix=1').then(h=>{ const el=$('#iHot'); if(!el) return; const rows=(h.open.length?h.open:h.week);
    el.innerHTML = `<p class="tiny" style="margin-top:0">${h.open.length?'Open cases in the pilot':'Real complaints in the sample week (no open cluster ≥3 yet)'}</p>`+
      rows.slice(0,6).map(s=>`<div class="stat-row"><span><b>${esc(s.gp)} GP</b> · ${esc(s.taluk)}<small>${esc(s.service)}</small></span><b>${s.n}</b></div>`).join('')+
      ((h.fixes||[]).length?`<div class="ai-note"><div class="tag">Likely root cause & fix · Sakala AI</div>${h.fixes.map(f=>`<p style="margin:0 0 8px"><b>${esc(f.place)}</b>: ${esc(f.root_cause)} <br><span style="color:var(--em-ink)">→ ${esc(f.fix)}</span></p>`).join('')}</div>`:''); });
  API('/api/insights/historical?summary=1').then(h=>{ const el=$('#iHist'); if(!el) return;
    el.innerHTML = `<div class="stat-row"><span>Praja Seva camps' share of all complaints</span><b>${h.camp_share}%</b></div>
      <div class="stat-row"><span>Busiest day<small>${esc(h.biggest_day)}</small></span><b>${n0(h.biggest_day_n)}</b></div>
      <div class="stat-row"><span>Mobile App complaints stuck in manual scrutiny</span><b>${h.scrutiny_rate_app}%</b></div>
      <div class="stat-row"><span>Vulnerable citizens still waiting (pension, widow, disabled)</span><b>${n0(h.vulnerable_waiting)}</b></div>
      <div class="stat-row"><span>Repeat complaints (same text filed again)</span><b>${n0(h.repeat_complaints)}</b></div>
      <h4 style="margin:14px 0 8px;font-size:.66rem;letter-spacing:1.2px;color:var(--mute-2)">TOP ISSUES · 3 PILOT DEPARTMENTS, STATEWIDE</h4>${bars(h.top_services_state.slice(0,6))}${aiNote(h.summary)}`; });
  API('/api/insights/misrouting').then(m=>{ const el=$('#iMis'); if(!el) return;
    el.innerHTML = `<div class="big-num">${n0(m.n_flagged)}<small>of ${n0(m.n_checked)} real grievances look filed under the wrong service</small></div>
      <p class="tiny">Plus <b>${n0(m.kridl_general)}</b> RDPR complaints parked under a state-level “General” desk with no field officer.</p>
      ${m.examples.slice(0,5).map(x=>`<div class="stat-row"><span style="max-width:78%">${esc(x.text.slice(0,110))}…<small>Filed: <b>${esc(x.filed)}</b> → AI: <b style="color:var(--em-ink)">${esc(x.suggested)}</b> · ${esc(x.district)}</small></span><b>${Math.round(x.confidence*100)}%</b></div>`).join('')}`; });
  API('/api/insights/quality').then(d=>{ const el=$('#iDq'); if(!el) return;
    el.innerHTML = d.checks.map(c=>`<div class="stat-row"><span>${esc(c.k)}<small>→ ${esc(c.fix)}</small></span><b>${n0(c.n)}</b></div>`).join(''); });
}

async function renderAccuracy(){
  const show = a => { const r=a.routing||{}, m=a.local_model||{}, l=a.llm;
    $('#accBody').innerHTML = `<div class="kpis">
      <div class="kpi hero"><div class="l">Exact officer · router</div><div class="v">${pct(r.rate)}</div><div class="d">${n0(r.n)} real Mysuru cases: same officer iPGRS assigned</div></div>
      <div class="kpi"><div class="l">End-to-end officer · AI</div><div class="v">${l?pct(l.officer_acc):'—'}</div><div class="d">${l?`${l.n} real complaints, text only → officer`:'run the live test'}</div></div>
      <div class="kpi"><div class="l">Department · AI</div><div class="v">${l?pct(l.dept_acc):'—'}</div><div class="d">${l?'vs the department filed in iPGRS':'—'}</div></div>
      <div class="kpi"><div class="l">Exact service · AI</div><div class="v">${l?pct(l.service_acc):'—'}</div><div class="d">iPGRS labels are themselves noisy (see misrouting)</div></div></div>
      <div class="card"><div class="card-h"><h3>How these are measured</h3></div><div class="card-b" style="font-size:.85rem;line-height:1.7">
      <p style="margin-top:0"><b>Router:</b> for each real Mysuru grievance we give the router the service and village recorded in iPGRS and check whether it picks the same named officer iPGRS actually used.</p>
      <p><b>End-to-end AI:</b> the model reads only the citizen's masked text, chooses the service from the official master, and the router picks the officer. The result is compared with the real assignment.</p>
      <p style="margin-bottom:0"><b>Offline fallback model</b> (used only if the AI service is unreachable): department ${pct(m.dept_acc)}, service ${pct(m.service_acc)} on ${n0(m.n_test_service)} held-out records.</p></div></div>`; };
  $('#content').innerHTML = head('Chief Secretary · trust','Accuracy proof','Measured on real Karnataka data, not claimed', `<button class="btn primary" id="accRun">${svg('star')}Run live test (40 real complaints)</button>`)+`<div id="accBody">${LOAD}</div>`;
  API('/api/insights/accuracy').then(show);
  $('#accRun').onclick = async ()=>{ $('#accRun').disabled=true; $('#accRun').innerHTML='Testing 40 real complaints…'; try { show(await API('/api/insights/accuracy?run=1&n=40')); toast('Accuracy test','Finished on 40 real complaints'); } finally { $('#accRun').disabled=false; $('#accRun').innerHTML=`${svg('star')}Run live test again`; } };
}

async function renderSakalaTracker(){
  $('#content').innerHTML = head('Chief Secretary · Sakala','Sakala district tracker · 2025','Real monthly district performance reports · all notified services')+`<div id="skBody">${LOAD}</div>`;
  const [t, w] = await Promise.all([API('/api/sakala/tracker'), API('/api/sakala/early_warning')]);
  const mx = Math.max(...t.monthly.map(m=>m.overdue));
  $('#skBody').innerHTML = `<div class="kpis">
     <div class="kpi hero"><div class="l">Applications received</div><div class="v">${(t.state.receipts/1e7).toFixed(2)} Cr</div><div class="d">${t.state.districts} districts · ${t.state.months} months</div></div>
     <div class="kpi"><div class="l">Delivered late</div><div class="v">${t.state.late_pct}%</div><div class="d">of disposals</div></div>
     <div class="kpi"><div class="l">Rejected</div><div class="v">${t.state.rej_pct}%</div><div class="d">of disposals</div></div>
     <div class="kpi"><div class="l">Overdue backlog</div><div class="v">${Math.round((t.state.overdue_last/t.state.overdue_first-1)*100)}%</div><div class="d">${n0(t.state.overdue_first)} → ${n0(t.state.overdue_last)}</div></div></div>
   <div class="grid2"><div class="card"><div class="card-h"><h3>Overdue applications, month by month</h3><span class="r">state total</span></div><div class="card-b"><div class="spark" style="height:120px">${t.monthly.map(m=>`<i title="${m.month}: ${n0(m.overdue)}" style="height:${m.overdue/mx*100}%"></i>`).join('')}</div><div class="tiny" style="display:flex;justify-content:space-between;margin-top:6px"><span>Jan</span><span>Dec</span></div>
     <h4 style="margin:18px 0 8px;font-size:.66rem;letter-spacing:1.2px;color:var(--mute-2)">HIGHEST LATE-DELIVERY RATE</h4>${bars(t.districts.slice(0,6).map(d=>[d.district,d.late_pct]),'var(--bad)')}</div></div>
   <div class="card"><div class="card-h"><h3>Early warning</h3><span class="r">last 3 months vs the 3 before</span></div><div class="card-b">${w.flagged.length?w.flagged.slice(0,7).map(f=>`<div class="flag-li"><b>${esc(f.district)}</b> · ${f.flags.map(esc).join(' · ')}</div>`).join(''):'<p class="tiny">No district is deteriorating.</p>'}
     <div class="ai-note"><div class="tag">Fairer scorecard</div>Today's official scores only span <b>${w.official_spread?w.official_spread.join('–'):'—'}</b> and depend almost entirely on in-time %. The proposed score weighs timeliness, rejections, backlog per lakh people and the trend equally, so districts that are slipping show up early.</div></div></div></div>
   <div class="card" style="margin-top:16px"><div class="card-h"><h3>District scorecard · proposed vs official</h3><span class="r">${esc(t.source)}</span></div><div style="overflow:auto;max-height:420px"><table><thead><tr><th>Fair rank</th><th>District</th><th>Late % (3 mo)</th><th>Rejected % (3 mo)</th><th>Overdue now</th><th>Official rank</th><th>Fair score</th></tr></thead><tbody>
   ${w.districts.map(d=>`<tr><td><b>${d.fair_rank}</b></td><td>${esc(d.district)}${d.flags.length?' <span class="badge b-s">watch</span>':''}</td><td>${d.late_now}%</td><td>${d.rej_now}%</td><td>${n0(d.overdue_now)}</td><td>${d.official_rank??'—'}</td><td><b>${d.fair_score}</b></td></tr>`).join('')}</tbody></table></div></div>
   <p class="tiny" style="margin-top:10px">The "RDPR" and "Revenue" report files shared are identical to this all-department file; department-wise exports requested from Sakala. Upload a new month on the Data upload screen.</p>`;
}

async function wednesdayPack(level){
  if (typeof level!=='string') level='cs';
  modal('Wednesday Review Pack · '+fmt(S.now), LOAD);
  const lv = {cs:['cs',''], dc:['dc','dc_mys'], ac:['ac','ac_hunsur'], eo:['eo','eo_piriyapatna']};
  const r = await API(`/api/review_pack?level=${lv[level][0]}&officer_id=${lv[level][1]}`); const f=r.facts;
  const e4 = await API('/api/e4');
  const tabs = `<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px">${[['cs','Chief Secretary'],['dc','DC Mysuru · 3–5 pm'],['ac','AC Hunsur · 11–1'],['eo','EO / Tahsildar · 9–11']].map(([k,t])=>`<button class="btn sm ${k===level?'primary':''}" data-wl="${k}">${t}</button>`).join('')}</div>`;
  const facts = `<p><b>1. Position.</b> ${f.open} requests pending; <b>${f.overdue}</b> overdue; ${f.vulnerable_waiting} from vulnerable citizens; ${f.auto_escalated} auto-escalated so far.</p>
    <p><b>2. Top issues.</b> ${f.top_issues.map(([k,v])=>`${esc(k)} (${v})`).join(', ')}.</p>
    <p><b>3. Where it is stuck.</b> ${f.stuck_examples.map(([id,s,o,d])=>`${id} · ${esc(s)} with ${esc(o)} (${d} days overdue)`).join('; ')||'No overdue cases.'}</p>
    ${f.sakala_deadlines_missed.length?`<p><b>Sakala deadlines missed:</b> ${f.sakala_deadlines_missed.map(([id,s])=>`${id} (${esc(s)})`).join(', ')} · compensation and Form C due.</p>`:''}
    ${e4.length?`<p><b>Form E-4 show-cause (more than 7 defaults):</b> ${e4.map(x=>`${esc(x.officer)} (${x.defaults})`).join(', ')}</p>`:''}
    ${f.sakala_2025?`<p class="tiny">Sakala 2025: Mysuru delivered ${f.sakala_2025.mysuru_late_pct}% late vs ${f.sakala_2025.state_late_pct}% statewide.</p>`:''}`;
  $('#modalRoot .modal-b').innerHTML = tabs + (r.html ? aiNote(r.html, 'AI-written pack') + (r.kn ? `<div class="ai-note kn"><div class="tag">ಕನ್ನಡ ಆವೃತ್ತಿ</div>${r.kn}</div>` : '') + `<details style="margin-top:12px"><summary class="tiny">Facts the pack was written from</summary>${facts}</details>` : facts);
  document.querySelectorAll('[data-wl]').forEach(b=>b.onclick=()=>wednesdayPack(b.dataset.wl));
}

function renderUpload(){
  $('#content').innerHTML = head('Chief Secretary · integration','Data upload','Connect any department today: Excel / CSV in, routed requests and dashboards out')+
   `<div class="grid2"><div class="card"><div class="card-h"><h3>Upload a file</h3><span class="r">.xlsx · .xls · .csv · max 5 MB</span></div><div class="card-b">
     <label class="drop" id="drop"><input type="file" id="upF" accept=".xlsx,.xls,.csv" hidden><div style="font-size:2rem">⇪</div><b>Drop a file or click to choose</b><p class="tiny">1) A Sakala monthly performance workbook: loads straight into the district tracker.<br>2) A sheet of complaints (a Description column, optional Village / Taluk): every row runs through the AI pipeline and is routed to an officer.</p></label>
     <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap"><a class="btn sm" href="/samples/sample_complaints.csv" download>${svg('doc')}Sample complaints file</a></div>
     <div id="upOut" style="margin-top:14px"></div></div></div>
   <div class="card"><div class="card-h"><h3>Every digital level</h3></div><div class="card-b">
     <div class="stat-row"><span><b>Full API</b><small>iPGRS, Sakala, Seva Sindhu push / pull</small></span><span class="prodtag">PRODUCTION</span></div>
     <div class="stat-row"><span><b>Excel / CSV upload</b><small>departments with spreadsheets (this screen)</small></span><span class="badge b-g">LIVE</span></div>
     <div class="stat-row"><span><b>Paper scan</b><small>photo of a petition read by the vision model (WhatsApp 📎)</small></span><span class="badge b-g">LIVE</span></div>
     <div class="stat-row"><span><b>Officer web console</b><small>departments with no system: the Officer profile</small></span><span class="badge b-g">LIVE</span></div></div></div></div>`;
  const go = async f => { if(!f) return; $('#upOut').innerHTML=LOAD; const fd=new FormData(); fd.append('file', f);
    try { const r = await fetch('/api/upload',{method:'POST',body:fd}); const j=await r.json(); if(!r.ok) throw new Error(j.detail||r.status);
      if (j.kind==='performance_report') $('#upOut').innerHTML = `<div class="banner info">${svg('doc')}<div><b>Performance report loaded:</b> ${j.rows} district-month rows, ${j.districts} districts, ${j.months} months. Open the Sakala tracker to see it.</div></div>`;
      else { $('#upOut').innerHTML = `<div class="banner info">${svg('send')}<div><b>${j.routed} of ${j.rows}</b> complaints routed to a named officer in one pass.</div></div><table><thead><tr><th>Complaint</th><th>Understood as</th><th>Sent to</th></tr></thead><tbody>${j.results.map(x=>`<tr><td><div class="ellip" style="max-width:260px">${esc(x.text)}</div></td><td class="tiny">${esc(x.service||x.intent)}${x.note?' · '+esc(x.note):''}</td><td><b>${esc(x.officer||'—')}</b>${x.case_id?`<div class="tiny">${x.case_id}${x.gp?' · '+esc(x.gp)+' GP':''}</div>`:''}</td></tr>`).join('')}</tbody></table>`; await loadState(); }
    } catch(e){ $('#upOut').innerHTML = `<div class="banner warn">${svg('shield')}<div>${esc(e.message)}</div></div>`; } };
  $('#upF').onchange = e => go(e.target.files[0]);
  const d=$('#drop'); d.ondragover=e=>{e.preventDefault();}; d.ondrop=e=>{e.preventDefault(); go(e.dataTransfer.files[0]);};
}

function renderRoadmap(){
  const items=[['AI callback to citizen','Kannada voice call after closure: “Was your problem solved?”'],['Namma Seva 5-star rating','A low rating means the officer must explain.'],
    ['Live integrations','iPGRS, Sakala, Seva Sindhu, HRMS, CPGRAMS (APIs).'],['SMS / WhatsApp sending','Reminders, notices and status updates actually sent.'],
    ['Learning loop · sovereign model','Officer corrections (Return · not my jurisdiction) retrain a government-hosted Kannada model.'],['Citizens-as-sensors alerts','A spike in one topic in one taluk raises an early warning to the DC.']];
  $('#content').innerHTML = head('Chief Secretary · next phase','Production roadmap','Shown for completeness · not part of this pilot')+`<div class="prod-grid">${items.map(([t,d])=>`<div class="prod-card"><span class="prodtag">PRODUCTION PHASE</span><b style="margin-top:8px">${t}</b>${d}</div>`).join('')}</div>`;
}

/* AI-mode microphone: record 6 s -> speech model -> ask */
async function askVoice(){
  const b=$('#askMic'); if(!b || b.classList.contains('rec')) return; b.classList.add('rec');
  try { const stream=await Promise.race([navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true}}), new Promise((_,rej)=>setTimeout(()=>rej(new Error('mic')),5000))]);
    const ctx=new (window.AudioContext||window.webkitAudioContext)(); const src=ctx.createMediaStreamSource(stream); const proc=ctx.createScriptProcessor(4096,1,1); const chunks=[]; proc.onaudioprocess=e=>chunks.push(new Float32Array(e.inputBuffer.getChannelData(0))); src.connect(proc); proc.connect(ctx.destination);
    toast('Listening','Speak your question; it stops after 6 seconds'); await sleep(6000); proc.disconnect(); src.disconnect(); stream.getTracks().forEach(t=>t.stop()); const rate=ctx.sampleRate; ctx.close();
    const r=await API('/api/transcribe',{audio_b64:b64(encodeWav(chunks,rate)), lang:'en'}); if(r.text){ $('#askI').value=r.text; $('#askF').requestSubmit(); } else toast('Voice','Could not hear that. Please type the question.');
  } catch(e){ toast('Microphone','Not available here. Please type the question.'); }
  b.classList.remove('rec');
}
