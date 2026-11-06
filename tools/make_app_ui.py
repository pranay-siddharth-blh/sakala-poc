"""Wireframe → live app: same HTML/CSS, data + actions from the FastAPI backend."""
import os
import re
import sys

src, wa_js, out = sys.argv[1:4]
ins_js = sys.argv[4] if len(sys.argv) > 4 else None
s = open(src, encoding='utf-8').read()


def rep(old, new, count=1):
    global s
    assert old in s, 'missing: ' + old[:90]
    s = s.replace(old, new, count)


def cut(start, end, new, keep_end=True):
    global s
    a = s.index(start)
    b = s.index(end, a)
    s = s[:a] + new + (s[b:] if keep_end else s[b + len(end):])


rep('<span class="wf-tag">WIREFRAME · SIMULATED AI</span>', '<span class="wf-tag" id="engineTag">AI ENGINE</span>')
rep('<title>Sakala AI · Citizen Request Intelligence</title>', '<title>Sakala AI · Citizen Request Intelligence · POC</title>')
rep('</style>', '.pl-basis{font-size:.7rem;color:rgba(255,255,255,.72);margin:0 0 10px;line-height:1.45}\n.wf-tag.live{border-style:solid;border-color:rgba(251,183,86,.8);background:rgba(251,183,86,.18)}\n</style>')

# masters come from the API
cut('const OFF = {', 'const SLA = {', 'const OFF = {};\nconst GEO = { Mysuru:{} };\n')
rep("const SLA = { L1:7, L2:5, L3:3 };", "let SLA = { L1:7, L2:5, L3:3 };")
rep("const SOURCES = [\n", "const SOURCES = [\n  {k:'whatsapp-voice', n:'WhatsApp · voice note', kn:'ವಾಟ್ಸಾಪ್ ಧ್ವನಿ', g:'Self-service', d:'Voice note on WhatsApp', share:'new'},\n  {k:'whatsapp-photo', n:'WhatsApp · petition photo', kn:'ವಾಟ್ಸಾಪ್ ಫೋಟೋ', g:'Self-service', d:'Photo of a paper petition', share:'new'},\n")

# state: seed() → API
cut('function seed(){', 'const daysBetween', '''let BOOT = null;
const API = (p, body) => fetch(p, body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {}).then(async r=>{ if(!r.ok){ let m=r.status; try{ m=(await r.json()).detail||m; }catch(e){} throw new Error(m); } return r.json(); });
function freshState(){ S = { now:new Date(START), profile:'citizen', citizenSrc:'whatsapp', citizenView:'wa', officer:'tah_piriyapatna', officerView:'inbox', csView:'dash', cases:[], chat:[], notifs:[] }; }
function parseCase(c){ c.created=new Date(c.created); c.levelSince=new Date(c.levelSince); c.history=c.history.map(h=>({...h,t:new Date(h.t)})); if(c.sakala) c.sakala.complete=new Date(c.sakala.complete); return c; }
async function loadState(){ const st = await API('/api/state?session='+encodeURIComponent(WA.sid||'')+'&scope='+(S.profile==='citizen'?'citizen':'all')); S.now=new Date(st.now); S.cases=st.cases.map(parseCase); S.notifs=st.notifs.map(n=>({...n,t:new Date(n.t)})); setEngine(st.ai); return st; }
function setEngine(ai){ const t=$('#engineTag'); if(!t) return; t.classList.add('live'); t.textContent = ai.llm ? 'LIVE · '+ai.model : 'LIVE · LOCAL AI MODEL'; t.title = ai.llm ? 'Understanding, photo reading, ATR checks and AI mode use '+ai.model : (ai.reason||'')+' · running the local model trained on the 9,999 real iPGRS grievances'; }
async function boot(){
  BOOT = await API('/api/bootstrap');
  Object.assign(OFF, BOOT.officers); GEO.Mysuru = BOOT.geo.Mysuru; SLA = BOOT.sla;
  for (const k in BOOT.depts) DEPTS[k] = {...DEPTS[k], ...BOOT.depts[k]};
  freshState();
  const q=new URLSearchParams(location.search); if(q.get('p')) S.profile=q.get('p'); if(q.get('v')){ if(S.profile==='cs') S.csView=q.get('v'); else if(S.profile==='officer') S.officerView=q.get('v'); else S.citizenView=q.get('v'); } if(q.get('off') && OFF[q.get('off')]) S.officer=q.get('off');
  await loadState(); render();
  if(q.get('open')) setTimeout(()=>openCase(q.get('open')),300);
}
''')

# demo clock → server rules
cut('function tick(days){', 'const fmt = d =>', '''async function tick(days){
  const r = await API('/api/clock/tick', {days});
  await loadState();
  toast('Demo clock', `Moved to ${fmt(S.now)}.${r.escalated?` ${r.escalated} grievance${r.escalated>1?'s':''} auto-escalated.`:' Reminders updated.'}${r.breached?` ${r.breached} Sakala deadline${r.breached>1?'s':''} missed.`:''}`);
  render();
}
''')

# citizen module
cut('/* ================= CITIZEN · Sakala on WhatsApp ================= */', 'function renderTrack(){', open(wa_js, encoding='utf-8').read() + '\n')


# officer drawer: show why this officer + engine
rep('''<div class="kv"><div>Confidence</div><div>${Math.round((u.conf||0)*100)}%</div>''',
    '''${c.audit?`<details class="audit"><summary>Routing evidence · how this decision was made</summary><div class="kv" style="margin-top:8px"><div>Engine</div><div>${esc(({llm:'Sakala AI','llm+rules':'Sakala AI · rule check',local:'Sakala AI (offline model)'})[c.audit.engine]||c.audit.engine||'')}</div><div>Confidence</div><div>${c.audit.confidence!=null?Math.round(c.audit.confidence*100)+'%':'—'} · threshold ${c.audit.threshold!=null?Math.round(c.audit.threshold*100)+'%':'—'}</div>${c.audit.decision?`<div>Decision</div><div>${esc(c.audit.decision.service||'')}${c.audit.decision.grievance?' › '+esc(c.audit.decision.grievance):''}<div class="tiny">${esc(c.audit.decision.reason||'')}</div></div>`:''}${(c.audit.rules||[]).length?`<div>Rules applied</div><div>${c.audit.rules.map(esc).join('<br>')}</div>`:''}${c.audit.place?`<div>Location</div><div>${esc(c.audit.place.village||'')}${c.audit.place.gp?' → '+esc(c.audit.place.gp)+' GP':''} · ${esc(c.audit.place.how||'')}</div>`:''}${c.audit.route?`<div>Officer rule</div><div>${esc(c.audit.route.role||'')} · ${Math.round((c.audit.route.share||0)*100)}% of ${c.audit.route.support||0} real cases${c.audit.route.fallback?' · fallback':''}</div>`:''}${(c.audit.similar_real_cases||[]).length?`<div>Similar real cases</div><div class="tiny">${c.audit.similar_real_cases.map(x=>`#${x.gid} (${Math.round(x.score*100)}%)`).join(' · ')}</div>`:''}${c.audit.human_decision?`<div>Human decision</div><div>${esc(c.audit.human_decision.by)} → ${esc(c.audit.human_decision.to)} · ${esc(c.audit.human_decision.note||'')}</div>`:''}</div></details>`:''}
        <div class="kv"><div>Routed by</div><div>${esc(c.engine==='llm'?(BOOT.ai.model+' via AI gateway'):c.engine==='local'?'Local model (real-data trained)':c.engine==='iPGRS'?'iPGRS (real record)':c.engine||'')}</div><div>Why this officer</div><div style="font-weight:500">${esc(c.routeBasis||'')}</div><div>Confidence</div><div>${Math.round((u.conf||0)*100)}%</div>''')

# officer actions → API
cut("  const log=(what,col,note,status)=>", 'function closeDrawer(){', '''  const panel = html => { $('#actPanel').innerHTML = `<div class="card" style="padding:14px;border-color:var(--gold-line);background:var(--gold-soft)">${html}</div>`; $('#actPanel').scrollIntoView({behavior:'smooth'}); };
  const act = async (body, close) => { let r; try { r = await API(`/api/cases/${encodeURIComponent(c.id)}/action`, {officer: S.profile==='cs'?'':me, ...body}); } catch(err){ toast('Not allowed', err.message); return; } if(r.toast) toast(r.toast[0], r.toast[1]); await loadState(); if(close){ closeDrawer(); render(); } else { render(); openCase(c.id); } return r; };
  if ($('#aNudge')) $('#aNudge').onclick=()=>act({action:'nudge'});
  if ($('#aAccept')) $('#aAccept').onclick=()=>act({action:'accept'});
  if ($('#aInfo')) $('#aInfo').onclick=()=>{ panel(`<div class="field"><label>Question to the citizen (sent on WhatsApp in their language)</label><textarea id="infoQ">ದಯವಿಟ್ಟು ನಿಮ್ಮ ಜಮೀನಿನ ಸರ್ವೇ ನಂಬರ್ ಮತ್ತು ಪಹಣಿ ಪ್ರತಿಯನ್ನು ಕಳುಹಿಸಿ.</textarea></div><button class="btn primary sm" id="sendInfo">Send</button>`); $('#sendInfo').onclick=()=>act({action:'info', note:$('#infoQ').value}); };
  if ($('#aReturn')) $('#aReturn').onclick=()=>{ panel(`<div class="field"><label>Why is this not yours? (required)</label><select id="retR"><option>Location is outside my jurisdiction</option><option>Belongs to another department</option><option>Wrong service selected</option></select></div><div class="field"><label>Suggest the right officer (optional)</label><input id="retS" placeholder="e.g. PDO Attigodu, Tahsildar Hunsur"></div><div class="field"><label>Or where it belongs (optional)</label><input id="retP" placeholder="taluk, Gram Panchayat or village, e.g. Hunsur"></div><div class="tiny" id="retHint" style="margin:-4px 0 10px;opacity:.75">With an officer or a place it goes straight to that officer, who is notified. With neither, the scrutiny desk routes it.</div><button class="btn primary sm" id="doRet">Return to scrutiny desk</button>`); let _rt=0; const _rl=()=>{ const to=$('#retS').value.trim(), pl=$('#retP').value.trim(); clearTimeout(_rt); if(!to&&!pl){ $('#doRet').textContent='Return to scrutiny desk'; $('#retHint').textContent='With an officer or a place it goes straight to that officer, who is notified. With neither, the scrutiny desk routes it.'; return; } $('#doRet').textContent='Checking…'; _rt=setTimeout(async()=>{ try{ const q=new URLSearchParams({officer:me||'',to,place:pl}); const r=await (await fetch(`/api/cases/${encodeURIComponent(c.id)}/transfer_preview?${q}`)).json(); if(r.officer){ $('#doRet').textContent='Send to '+r.officer.short; $('#retHint').innerHTML='Goes straight to <b>'+esc(r.officer.short)+'</b> ('+esc(r.how||'')+'), who is notified; the clock restarts for them.'; } else { $('#doRet').textContent='Return to scrutiny desk'; $('#retHint').textContent='No officer matches that'+(/back to the returning/.test(r.how||'')?' (it is your own desk)':'')+', so the scrutiny desk will route it.'; } }catch(e){ $('#doRet').textContent='Send to the suggested officer'; } }, 350); }; $('#retS').oninput=_rl; $('#retP').oninput=_rl; $('#doRet').onclick=()=>act({action:'return', reason:$('#retR').value, to:$('#retS').value.trim(), place:$('#retP').value.trim()}, true); };
  if ($('#aReject')) $('#aReject').onclick=()=>{ panel(`<div class="field"><label>Reason for rejection (mandatory, shown to the citizen)</label><select id="rejR"><option>Applicant not eligible under scheme rules</option><option>Required document missing after 2 requests</option><option>Duplicate of an existing request</option><option>Matter is sub-judice (court case)</option></select></div><div class="field"><label>Details</label><textarea id="rejD">Eligibility checked against the scheme guidelines.</textarea></div><p class="tiny">The citizen is told the reason and ${c.sakala?'their right to appeal to the Competent Officer within 30 days.':'can escalate if not satisfied.'}</p><button class="btn danger sm" id="doRej">Reject</button>`); $('#doRej').onclick=()=>act({action:'reject', reason:$('#rejR').value, note:$('#rejD').value}, true); };
  if ($('#aResolve')) $('#aResolve').onclick=()=>{ panel(`<div class="field"><label>Action Taken Report</label><textarea id="atrT" placeholder="What was inspected, what was done, the outcome and the date. Tap “AI draft” for a first version."></textarea></div><div class="inputbar"><span class="tool">${svg('doc')}Attach photo / order</span><button class="tool" id="atrDraft">${svg('star')}AI draft</button></div><button class="btn primary sm" id="doRes">Submit ATR · AI checks it</button><div id="atrChk"></div>`);
    $('#atrDraft').onclick=async ()=>{ $('#atrDraft').innerHTML='Drafting…'; const r=await API(`/api/cases/${encodeURIComponent(c.id)}/draft_atr`,{}); $('#atrT').value=r.text; $('#atrDraft').innerHTML=`${svg('star')}AI draft · edit before submitting`; };
    $('#doRes').onclick=async ()=>{ $('#atrChk').innerHTML='<div class="tiny" style="margin-top:8px"><span class="typing"><i></i><i></i><i></i></span> AI is comparing the ATR with the complaint…</div>';
      let r; try { r = await API(`/api/cases/${encodeURIComponent(c.id)}/action`, {action:'resolve', officer:me, atr:$('#atrT').value}); } catch(err){ r={detail:err.message}; }
      if (r.detail){ $('#atrChk').innerHTML=`<div class="banner warn" style="margin-top:10px">${esc(r.detail)}</div>`; return; }
      $('#atrChk').innerHTML=`<div class="banner ${r.score>=4?'info':'warn'}" style="margin-top:10px">${svg('star')}<div><b>AI resolution check: ${r.score}/5 · ${['','Incorrect / irrelevant','Not resolved','Partially resolved','Substantially resolved','Fully resolved'][r.score]}</b> <span class="tiny">(${esc(r.engine)})</span><br>${esc(r.reason)}</div></div>`;
      if (r.score>=4){ toast(r.toast[0], r.toast[1]); await loadState(); setTimeout(()=>{closeDrawer();render();},1300); } }; };
  if ($('#cOrder')) $('#cOrder').onclick=()=>act({action:'comp_order'});
  if ($('#cNotice')) $('#cNotice').onclick=()=>modal('Form C · Notice for recovery of compensatory cost', `<p><b>To:</b> ${esc(OFF[c.sakala.DO].n)}</p><p>You have delayed the service <b>${esc(c.sakala.service)}</b> under the Karnataka Sakala Services Act, 2011, for the applicant with acknowledgement no. <b>${c.id}</b>. Rs. 20/- per day has been paid to the applicant for <b>${-s.left}</b> days of delay as compensatory cost (Rs. ${comp}). This amount will be recovered from your salary.</p><p>You are instructed to give your explanation with justification <b>within 7 days</b>.</p><p style="text-align:right"><b>Competent Officer</b><br>${esc(OFF[c.sakala.CO].n)}</p><p class="tiny">Drafted by Sakala AI from the case record · officer reviews before signing.</p>`);
  if ($('#cHrms')) $('#cHrms').onclick=()=>act({action:'comp_hrms'});
}
''')

# AI mode: Claude when available, otherwise answers computed from the live data in the browser
rep('''    setTimeout(()=>{ const r=answer(q); S.chat.push({a:r.a}); $('#typing').outerHTML=`<div class="msg a">${r.a}</div>`; scrollLog(); },850); };''',
    '''    API('/api/ask',{q}).catch(()=>({engine:'local'})).then(res=>{ let a, chart=null;
      if (res.engine && res.engine!=='local'){ a=safeHtml(res.html); chart=res.chart||null; }
      else { a=answer(q).a; chart=chartFromHbar(a, q); if(chart) a=a.replace(/<div class="hbar"[\s\S]*$/,''); }
      S.chat.push({a, chart}); const i=S.chat.length-1; $('#typing').outerHTML=`<div class="msg a${chart?' has-chart':''}" data-ci="${i}">${a}</div>`;
      if (chart) renderChart(document.querySelector(`.msg.a[data-ci="${i}"]`), chart); scrollLog(); }); };
  $('#askMic').onclick=()=>askVoice();''')
rep("if (t.includes('pension')){ const r=open.filter(c=>(c.u.svc||'').toLowerCase().includes('pension')&&",
    "if (t.includes('pension')){ const r=open.filter(c=>/pension|old-age|sandhya/i.test((c.u.svc||'')+' '+(c.u.gr||''))&&")
rep("const r=open.filter(c=>(c.u.svc||'').includes('Water')&&c.taluk==='Piriyapatna');", "const r=open.filter(c=>/water/i.test(c.u.svc||'')&&c.taluk==='Piriyapatna');")

# AI-mode charts: Chart.js (local copy), history keeps its charts
rep('</head>', '<script src="assets/vendor/chart.umd.min.js"></script>\n</head>')
rep("""    <div class="chatlog" id="chatlog">${S.chat.map(m=>m.q?`<div class="msg q">${esc(m.q)}</div>`:`<div class="msg a">${m.a}</div>`).join('')}</div>""",
    """    <div class="chatlog" id="chatlog">${S.chat.map((m,i)=>m.q?`<div class="msg q">${esc(m.q)}</div>`:`<div class="msg a${m.chart?' has-chart':''}" data-ci="${i}">${m.a}</div>`).join('')}</div>""")
rep("  if (has) setTimeout(()=>{ const log=$('#chatlog'); if(log) log.scrollTop=log.scrollHeight; },30);",
    "  S.chat.forEach((m,i)=>{ if(m.chart){ const el=document.querySelector(`.msg.a[data-ci=\"${i}\"]`); if(el) renderChart(el, m.chart); } });\n  if (has) setTimeout(()=>{ const log=$('#chatlog'); if(log) log.scrollTop=log.scrollHeight; },30);")

# CS dashboard: show the real-data routing proof
rep('''<div class="kpi" style="--c:var(--saffron)"><div class="l">Time to route</div><div class="v">~3 s</div><div class="d">vs 39% of app complaints stuck in manual scrutiny today</div></div>''',
    '''<div class="kpi" style="--c:var(--saffron)"><div class="l">Exact-officer agreement</div><div class="v">${(BOOT.evals.routing.rate*100).toFixed(1)}%</div><div class="d">${BOOT.evals.routing.n} real Mysuru cases: router picks the same officer iPGRS used</div></div>''')

# Wednesday pack: top issues computed
rep('''<p><b>2. Top issues.</b> Pensions not received, khata/RTC delays, drinking water in Piriyapatna GPs, ration-card delays.</p>''',
    '''<p><b>2. Top issues.</b> ${Object.entries(open.reduce((m,c)=>{const k=c.u.svc||'Scrutiny';m[k]=(m[k]||0)+1;return m;},{})).sort((a,b)=>b[1]-a[1]).slice(0,5).map(([k,v])=>`${esc(k)} (${v})`).join(', ')}.</p>''')

# boot instead of seed + wireframe hooks
rep('''    <button data-cs="all" class="${S.csView==='all'?'on':''}"><span class="ic">${svg('inbox')}</span><span>All cases<small>Every request, every officer</small></span></button>''',
    '''    <button data-cs="all" class="${S.csView==='all'?'on':''}"><span class="ic">${svg('inbox')}</span><span>All cases<small>Every request, every officer</small></span></button>
    <button data-cs="insights" class="${S.csView==='insights'?'on':''}"><span class="ic">${svg('map')}</span><span>Insights<small>Hotspots · history · misrouting</small></span></button>
    <button data-cs="accuracy" class="${S.csView==='accuracy'?'on':''}"><span class="ic">${svg('shield')}</span><span>Accuracy proof<small>Measured on real data</small></span></button>
    <button data-cs="upload" class="${S.csView==='upload'?'on':''}"><span class="ic">${svg('doc')}</span><span>Data upload<small>Excel / CSV from any department</small></span></button>
    <button data-cs="roadmap" class="${S.csView==='roadmap'?'on':''}"><span class="ic">${svg('star')}</span><span>Production roadmap<small>Next phase</small></span></button>''')
rep("  if (S.csView==='all') return renderAll();", """  if (S.csView==='all') return renderAll();
  if (S.csView==='insights') return renderInsights();
  if (S.csView==='accuracy') return renderAccuracy();
  if (S.csView==='upload') return renderUpload();
  if (S.csView==='roadmap') return renderRoadmap();""")
cut("$('#plus1').onclick=()=>tick(1);", '</script>', (open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_charts.js'), encoding='utf-8').read() + '\n' + open(ins_js, encoding='utf-8').read() + '\n' if ins_js else '') + '''$('#plus1').onclick=()=>tick(1); $('#plus7').onclick=()=>tick(7);
$('#clockReset').onclick=async ()=>{ await API('/api/reset',{}); WA.history=[]; WA.sid=''; WA.stage={}; WA.result=null; WA.chips=null; WA.started=false; persistWA(); S.chat=[]; await loadState(); render(); toast('Demo reset','Back to 14 Oct 2026 with the real case data.'); };
$('#lKn').onclick=()=>toast('ಕನ್ನಡ','Choose ಕನ್ನಡ inside the WhatsApp chat; the full Kannada interface follows in production.');
if(location.search) $('#overlay').style.display='none'; else setTimeout(()=>$('#overlay').classList.add('off'),1300);
boot().catch(e=>{ document.body.insertAdjacentHTML('beforeend', `<div class="toast" style="position:fixed;left:50%;top:40%;transform:translateX(-50%);z-index:99999">Cannot reach the Sakala AI server (${esc(e.message)}). Start it with run.bat</div>`); });
''')
rep("S.profile=b.dataset.prof; goHome(); profMenuOpen=false; closeDrawer(); render(); $('#main').scrollTop=0;", "S.profile=b.dataset.prof; goHome(); profMenuOpen=false; closeDrawer(); render(); $('#main').scrollTop=0; loadState().then(render);")
assert 'seed();' not in s, 'seed call still present'
s = s.replace("c.status!=='Resolved'", "!['Resolved','Rejected'].includes(c.status)")
open(out, 'w', encoding='utf-8').write(s)
print('app UI written', len(s))
