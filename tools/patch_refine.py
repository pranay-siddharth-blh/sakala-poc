"""Pipeline refinements + AI-mode UI refresh + model names out of the UI.

Backend: low-confidence → scrutiny with alternatives · scrutiny re-route action · pre-deadline reminders ·
officer messages translated to the citizen's language · /api/transcribe for the AI-mode mic · neutral engine labels.
UI: Sakala logo instead of the orb · bigger suggestion cards · ask bar pinned to the bottom · chat scrolls inside ·
subtle Sakala gradient + watermark · no "answered from data tools" line · no model names anywhere.
"""
import os

ROOT = r"D:\Sakala POC"
A = os.path.join(ROOT, "app", "server")
T = os.path.join(ROOT, "tools")


def edit(p, old, new, count=1):
    s = open(p, encoding="utf-8").read()
    assert old in s, (os.path.basename(p), old[:70])
    open(p, "w", encoding="utf-8").write(s.replace(old, new, count))


# ---------------------------------------------------------------- backend
P = os.path.join(A, "pipeline.py")
edit(P, '''            if lu["intent"] in ("WRONG_DOOR", "OUT_OF_SCOPE", "SERVICE_REQUEST") and u["intent"] != lu["intent"]:
                lu.update(engine="llm+rules", summary=u.get("summary", ""))
                u = lu''', '''            if lu["intent"] in ("WRONG_DOOR", "OUT_OF_SCOPE", "SERVICE_REQUEST") and u["intent"] != lu["intent"]:
                lu.update(engine="llm+rules", summary=u.get("summary", ""))
                u = lu
            # low confidence never routes silently: a person at the scrutiny desk sees the top-3 options
            if u["intent"] == "GRIEVANCE" and u.get("conf", 1) < LOW_CONF:
                alts = [u["service"]] + [a for a in local_ai.alternatives(masked, 3) if a != u["service"]]
                u = {"intent": "UNCLEAR", "engine": u["engine"], "conf": u["conf"], "summary": u.get("summary", ""),
                     "alternatives": alts[:3], "similar": u.get("similar", []),
                     "reason": f"Confidence only {round(u['conf'] * 100)}%. Possible services: " + " / ".join(alts[:3])}''')
edit(P, 'DEPT_SHORT = {"REV": "Revenue", "RDPR": "RDPR", "FOOD": "Food & Civil Supplies"}',
     'DEPT_SHORT = {"REV": "Revenue", "RDPR": "RDPR", "FOOD": "Food & Civil Supplies"}\nLOW_CONF = 0.55                      # below this the AI does not route on its own')
edit(P, '''def engine_label(u):
    return {"llm": f"{ai.status()['model']} (AI gateway)", "llm+rules": f"{ai.status()['model']} + rule check",
            "local": "local model"}.get(u.get("engine"), u.get("engine", ""))''', '''def engine_label(u):
    return {"llm": "Sakala AI", "llm+rules": "Sakala AI · rule check", "local": "Sakala AI (offline model)"}.get(u.get("engine"), u.get("engine", ""))''')
edit(P, '''    event(cid, "Sakala AI", "Sent to scrutiny desk", "#c98a00", f"Low confidence ({round(u.get('conf', 0) * 100)}%) · never a silent guess")''',
     '''    event(cid, "Sakala AI", "Sent to scrutiny desk", "#c98a00", (u.get("reason") or "Low confidence") + " · never a silent guess")
    notify("eo_piriyapatna", f"{cid} needs a human decision at the scrutiny desk")''')

L = os.path.join(A, "local_ai.py")
edit(L, "# ---------------- high-precision keyword rules ----------------", '''def alternatives(text, k=3):
    """Top-k service names for the scrutiny desk."""
    names = {s["id"]: s["name"] for s in db.q("SELECT id, name FROM services")}
    return [names.get(sid, "") for sid, _ in predict(text)["services"][:k] if names.get(sid)]


# ---------------- high-precision keyword rules ----------------''')

S = os.path.join(A, "sla.py")
edit(S, '''    breached = 0
    for c in db.q("SELECT * FROM cases WHERE kind='APPLICATION' AND status NOT IN ('Resolved','Rejected')"):''', '''    # pre-deadline reminders: due tomorrow / due today (stage 7)
    for c in db.q(f"SELECT * FROM cases WHERE status IN ({','.join('?' * len(OPEN))})", OPEN):
        left = sla_info(c)["left"]
        if left in (0, 1):
            notify(c["owner"], f"{c['id']} is due {'today' if left == 0 else 'tomorrow'}" + (" (Sakala legal deadline)" if c["kind"] == "APPLICATION" else " · will escalate if not acted on"))
    breached = 0
    for c in db.q("SELECT * FROM cases WHERE kind='APPLICATION' AND status NOT IN ('Resolved','Rejected')"):''')

AI = os.path.join(A, "ai.py")
edit(AI, "# ---------------- 6. written briefs (UC 17, 18, 19) ----------------", '''# ---------------- translation for citizen-facing officer text ----------------
def to_kannada(text):
    """Officer wrote in English; the citizen chose Kannada. Keeps numbers, ids and names as they are."""
    if not text or any("\\u0c80" <= ch <= "\\u0cff" for ch in text):
        return text
    return chat("translate", [{"role": "system", "content": "Translate the officer's message into simple, polite Kannada for a citizen. "
                                                            "Keep case numbers, names, dates and amounts unchanged. Output only the Kannada text."},
                              {"role": "user", "content": text}], max_tokens=300, temperature=0.1)


# ---------------- 6. written briefs (UC 17, 18, 19) ----------------''')

C = os.path.join(A, "chat.py")
edit(C, '''        en, kn = KIND_TEXT.get(m["kind"], ("{off}: {text}", "{off}: {text}"))
        html = o.t(en, kn).format(off=E(off["short"]), cid=m["case_id"], text=E(m["text"] or ""))''', '''        en, kn = KIND_TEXT.get(m["kind"], ("{off}: {text}", "{off}: {text}"))
        text = m["text"] or ""
        if o.st.get("lang") == "kn" and m["kind"] in ("info", "rejected", "resolved") and text and ai.status()["llm"]:
            try:
                text = ai.to_kannada(text)
            except Exception:  # noqa: BLE001 - keep the English text
                pass
        html = o.t(en, kn).format(off=E(off["short"]), cid=m["case_id"], text=E(text))''')
edit(C, '''    "compensation": (''', '''    "routed": ("📍 <b>{cid}</b> has been checked by the scrutiny desk and is now with <b>{off}</b>. {text}",
               "📍 <b>{cid}</b> ಪರಿಶೀಲನಾ ಡೆಸ್ಕ್ ಪರಿಶೀಲಿಸಿ ಈಗ <b>{off}</b> ಅವರಿಗೆ ವಹಿಸಲಾಗಿದೆ. {text}"),
    "compensation": (''')

API = os.path.join(A, "api.py")
edit(API, '''class Action(BaseModel):
    action: str
    officer: str = ""
    note: str = ""
    reason: str = ""
    atr: str = ""''', '''class Action(BaseModel):
    action: str
    officer: str = ""
    note: str = ""
    reason: str = ""
    atr: str = ""
    to: str = ""''')
edit(API, '''    elif a.action == "nudge":''', '''    elif a.action == "reroute":
        if c["status"] != "Scrutiny":
            raise HTTPException(409, "only scrutiny-desk cases can be re-routed")
        if me and me["level"] == "L1":
            raise HTTPException(403, "the scrutiny desk is the taluk / district level (L2, L3) or the Chief Secretary's office")
        target = officer(a.to)
        if not target:
            raise HTTPException(400, "choose the officer to send it to")
        db.run("UPDATE cases SET owner=?, level=?, level_since=?, status='Pending', route_basis=? WHERE id=?",
               (target["id"], target["level"], now().isoformat(), f"Scrutiny desk decision by {who}" + (f": {a.note}" if a.note else ""), cid))
        event(cid, who, f"Scrutiny desk: routed to {target['short']}", "#0e9f6e", a.note or "Human decision recorded as a routing correction")
        notify(target["id"], f"{cid} assigned to you by the scrutiny desk")
        message_citizen(cid, target["id"], "routed", "")
        out["toast"] = ["Re-routed", f"{cid} → {target['short']}"]
    elif a.action == "nudge":''')
edit(API, '''                score, reason = ai.check_atr(c["masked"], a.atr)
                engine = ai.status()["model"]''', '''                score, reason = ai.check_atr(c["masked"], a.atr)
                engine = "Sakala AI"''')
edit(API, '''        return {"text": ai.draft_atr({"officer": officer(c["owner"])["name"], "service": c["service"], "masked": c["masked"]}), "engine": ai.status()["model"]}''',
     '''        return {"text": ai.draft_atr({"officer": officer(c["owner"])["name"], "service": c["service"], "masked": c["masked"]}), "engine": "Sakala AI"}''')
edit(API, '''        return {"engine": ai.status()["model"], "html": r["html"], "tools": r["tools"]}''', '''        return {"engine": "ai", "html": r["html"], "tools": r["tools"]}''')
edit(API, '''@app.get("/api/health")''', '''class Audio(BaseModel):
    audio_b64: str
    lang: str = "en"


@app.post("/api/transcribe")
def transcribe(a: Audio):
    """Speech to text for the AI-mode microphone (same model as WhatsApp voice notes)."""
    import base64
    try:
        return {"text": ai.transcribe(base64.b64decode(a.audio_b64), "kn" if a.lang == "kn" else "en")}
    except Exception as e:  # noqa: BLE001
        return {"text": "", "error": str(e)[:120]}


@app.get("/api/health")''')

ASKVOICE = r"""
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
"""

# ---------------------------------------------------------------- UI (wireframe source + generator + client)
W = os.path.join(ROOT, "wireframe", "index.html")
edit(W, '''  $('#content').innerHTML = `<div class="ai-wrap"><div class="ai-hero"><div class="orb"></div><h2>Sakala AI · ask anything</h2><p>Answers come only from the case database and the Sakala 2025 reports. If the data doesn’t exist, it says so.</p></div>
    <div class="suggest">${QS.map(q=>`<span class="chip" data-q="${esc(q)}">${esc(q)}</span>`).join('')}</div>
    <div class="chatlog" id="chatlog">${S.chat.map(m=>m.q?`<div class="msg q">${esc(m.q)}</div>`:`<div class="msg a">${m.a}<div class="src">${m.src}</div></div>`).join('')}</div>
    <div class="askbar"><form id="askF"><input id="askI" placeholder="Ask in English or ಕನ್ನಡ… e.g. Which officer has the most overdue cases?" autocomplete="off"><button class="btn tool" type="button" title="Voice">${svg('mic')}</button><button class="btn primary">${svg('send')}Ask</button></form></div></div>`;
  const ask = q => { if(!q.trim())return; S.chat.push({q}); const log=$('#chatlog'); log.insertAdjacentHTML('beforeend',`<div class="msg q">${esc(q)}</div><div class="msg a" id="typing"><span class="typing"><i></i><i></i><i></i></span> Querying the data…</div>`); $('#main').scrollTop=1e9;
    setTimeout(()=>{ const r=answer(q); const src = r.none?'No matching records.':`Based on ${r.n} record${r.n===1?'':'s'} · computed from the live database, not generated · ${fmt(S.now)}`; S.chat.push({a:r.a,src}); $('#typing').outerHTML=`<div class="msg a">${r.a}<div class="src">${src}</div></div>`; $('#main').scrollTop=1e9; },850); };
  $('#askF').onsubmit=e=>{e.preventDefault(); const q=$('#askI').value; $('#askI').value=''; ask(q);};
  document.querySelectorAll('[data-q]').forEach(c=>c.onclick=()=>ask(c.dataset.q));''',
     '''  const has = S.chat.length>0;
  $('#content').innerHTML = `<div class="ai-wrap ${has?'has-chat':''}">
    <div class="ai-hero"><div class="ai-logo"><img class="sk-logo" src="assets/sakala-logo.svg" alt="Sakala"></div><h2>Sakala AI · ask anything</h2><p>Answers come only from the case database and the Sakala 2025 reports. If the data doesn’t exist, it says so.</p></div>
    <div class="suggest">${QS.map(q=>`<button class="sq" data-q="${esc(q)}"><span class="sq-ic">✦</span><span>${esc(q)}</span></button>`).join('')}</div>
    <div class="chatlog" id="chatlog">${S.chat.map(m=>m.q?`<div class="msg q">${esc(m.q)}</div>`:`<div class="msg a">${m.a}</div>`).join('')}</div>
    <div class="askbar"><div class="suggest-mini">${QS.slice(0,4).map(q=>`<button class="chip" data-q="${esc(q)}">${esc(q)}</button>`).join('')}</div>
      <form id="askF"><input id="askI" placeholder="Ask in English or ಕನ್ನಡ… e.g. Which officer has the most overdue cases?" autocomplete="off"><button class="btn tool" type="button" id="askMic" title="Speak your question">${svg('mic')}</button><button class="btn primary">${svg('send')}Ask</button></form></div></div>`;
  const scrollLog = () => { const log=$('#chatlog'); if(log) log.scrollTo({top:log.scrollHeight, behavior:'smooth'}); };
  const ask = q => { if(!q.trim())return; S.chat.push({q}); $('.ai-wrap')?.classList.add('has-chat'); const log=$('#chatlog'); log.insertAdjacentHTML('beforeend',`<div class="msg q">${esc(q)}</div><div class="msg a" id="typing"><span class="typing"><i></i><i></i><i></i></span> Querying the data…</div>`); scrollLog();
    setTimeout(()=>{ const r=answer(q); S.chat.push({a:r.a}); $('#typing').outerHTML=`<div class="msg a">${r.a}</div>`; scrollLog(); },850); };
  $('#askF').onsubmit=e=>{e.preventDefault(); const q=$('#askI').value; $('#askI').value=''; ask(q);};
  document.querySelectorAll('[data-q]').forEach(c=>c.onclick=()=>ask(c.dataset.q));
  if (has) setTimeout(()=>{ const log=$('#chatlog'); if(log) log.scrollTop=log.scrollHeight; },30);''')
edit(W, "  if (S.profile==='citizen') renderCitizen(); else if (S.profile==='officer') renderOfficer(); else renderCS();",
     "  const isAI = S.profile==='cs' && S.csView==='ai'; $('#main').classList.toggle('ai-bg', isAI); $('#content').classList.toggle('ai-mode', isAI);\n  if (S.profile==='citizen') renderCitizen(); else if (S.profile==='officer') renderOfficer(); else renderCS();")
# scrutiny re-route panel in the case drawer (wireframe shows the control; the app wires it to the API)
edit(W, '''      <div id="actPanel"></div>''', '''      ${c.status==='Scrutiny' && (S.profile==='cs' || (OFF[S.officer]||{}).lv!=='L1') ? `<div class="sec reroute"><h4>Scrutiny desk · decide the route</h4>
        <p class="tiny" style="margin:0 0 8px">${esc(u.why||'')}</p>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center"><select id="rrTo" style="flex:1;min-width:220px;padding:9px 12px;border-radius:12px;border:1px solid var(--line-2)">${Object.keys(DEPTS).map(d=>`<optgroup label="${DEPTS[d].name}">${Object.entries(OFF).filter(([k,o])=>o.d===d).map(([k,o])=>`<option value="${k}">${o.lv} · ${esc(o.short)}</option>`).join('')}</optgroup>`).join('')}</select>
        <input id="rrNote" placeholder="Why (optional)" style="flex:1;min-width:160px;padding:9px 12px;border-radius:12px;border:1px solid var(--line-2)"><button class="btn primary sm" id="rrGo">Route it</button></div></div>` : ''}
      <div id="actPanel"></div>''')

M = os.path.join(T, "make_app_ui.py")
edit(M, '''    API('/api/ask',{q}).catch(()=>({engine:'local'})).then(res=>{ let a, src;
      if (res.engine && res.engine!=='local'){ a=safeHtml(res.html); src=`${res.engine} · answered only from data tools (${[...new Set(res.tools)].join(', ')||'no tools'}) · ${fmt(S.now)}`; }
      else { const r=answer(q); a=r.a; src = r.none?'No matching records.':`Based on ${r.n} record${r.n===1?'':'s'} · computed from the live database, not generated · ${fmt(S.now)}`; }
      S.chat.push({a,src}); $('#typing').outerHTML=`<div class="msg a">${a}<div class="src">${esc(src)}</div></div>`; $('#main').scrollTop=1e9; }); };''',
     '''    API('/api/ask',{q}).catch(()=>({engine:'local'})).then(res=>{ const a = (res.engine && res.engine!=='local') ? safeHtml(res.html) : answer(q).a;
      S.chat.push({a}); $('#typing').outerHTML=`<div class="msg a">${a}</div>`; scrollLog(); }); };
  $('#askMic').onclick=()=>askVoice();''')
edit(M, '''    setTimeout(()=>{ const r=answer(q); S.chat.push({a:r.a}); $('#typing').outerHTML=`<div class="msg a">${r.a}</div>`; scrollLog(); },850); };''', '''''')
edit(M, "c.engine==='llm'?(BOOT.ai.model+' via AI gateway'):c.engine==='local'?'Local model (real-data trained)':c.engine==='iPGRS'?'iPGRS (real record)':c.engine||''",
     "({llm:'Sakala AI','llm+rules':'Sakala AI · rule check',local:'Sakala AI (offline model)',iPGRS:'iPGRS (real record)',Sakala:'Sakala application'})[c.engine]||c.engine||''")
edit(M, '''  if ($('#cOrder')) $('#cOrder').onclick=()=>act({action:'comp_order'});''', '''  if ($('#rrGo')) $('#rrGo').onclick=()=>act({action:'reroute', to:$('#rrTo').value, note:$('#rrNote').value}, true);
  if ($('#cOrder')) $('#cOrder').onclick=()=>act({action:'comp_order'});''')
I = os.path.join(T, "app_insights.js")
s = open(I, encoding="utf-8").read()
s = s.replace("${esc(label||'AI summary')} · ${esc(BOOT.ai.model||'AI')}", "${esc(label||'AI summary')} · Sakala AI")
s = s.replace("<div class=\"tag\">Likely root cause & fix · ${esc(BOOT.ai.model)}</div>", "<div class=\"tag\">Likely root cause & fix · Sakala AI</div>")
s = s.replace("${l?`${l.n} real complaints, text only → officer (${esc(l.model)})`:'run the live test'}", "${l?`${l.n} real complaints, text only → officer`:'run the live test'}")
s += ASKVOICE if "async function askVoice" not in s else ""
s = s.replace("<p style=\"margin-bottom:0\"><b>Local fallback model</b> (runs without the gateway): department", "<p style=\"margin-bottom:0\"><b>Offline fallback model</b> (used only if the AI service is unreachable): department")
open(I, "w", encoding="utf-8").write(s)

WA = os.path.join(T, "app_wa_client.js")
s = open(WA, encoding="utf-8").read()
s = s.replace("<small>Sakala AI pipeline · live · ${BOOT.ai.claude?'Claude Opus 5.5':'local model trained on real iPGRS data'}</small>", "<small>Sakala AI pipeline · live</small>")
open(WA, "w", encoding="utf-8").write(s)

CSS = os.path.join(T, "future2.css")
css = open(CSS, encoding="utf-8").read()
if "/* ===== AI MODE 2026" not in css:
    css += """
/* ===== AI MODE 2026: logo hero, big suggestion cards, chat scrolls inside, ask bar pinned to the bottom ===== */
.main.ai-bg{background:
  radial-gradient(900px 520px at 12% 0%,rgba(22,199,132,.13),transparent 60%),
  radial-gradient(760px 480px at 92% 8%,rgba(242,107,29,.11),transparent 62%),
  radial-gradient(900px 600px at 50% 110%,rgba(10,132,255,.07),transparent 60%),var(--canvas)}
.main.ai-bg::after{content:"";position:fixed;right:-40px;bottom:-60px;width:520px;height:420px;pointer-events:none;opacity:.055;
  background:url("assets/sakala-logo.svg") no-repeat center/contain;filter:grayscale(.2)}
.content.ai-mode{height:100%;min-height:0;display:flex;flex-direction:column;padding:16px 28px 18px;animation:none;max-width:none}
.ai-wrap{flex:1;min-height:0;display:flex;flex-direction:column;max-width:1040px;width:100%;margin:0 auto}
.ai-hero{padding:14px 10px 6px;flex:0 0 auto}
.ai-logo{width:92px;height:92px;margin:0 auto 12px;border-radius:50%;background:#fff;display:grid;place-items:center;
  box-shadow:0 0 0 1px var(--line),0 24px 48px -22px rgba(0,0,0,.35),0 0 80px -20px rgba(22,199,132,.45);animation:aiFloat 5s ease-in-out infinite}
.ai-logo .sk-logo{width:72px;height:72px;padding:4px}
@keyframes aiFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
.ai-hero h2{font-size:2.3rem}
.ai-hero p{font-size:.92rem;max-width:620px;margin:8px auto 0;color:var(--mute)}
.suggest{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin:18px 0 10px;flex:0 0 auto}
.sq{display:flex;align-items:center;gap:12px;text-align:left;padding:16px 18px;border-radius:18px;background:#fff;border:1px solid var(--line);
  font-size:1rem;font-weight:550;line-height:1.35;color:var(--ink);cursor:pointer;box-shadow:var(--sh);transition:transform .18s,box-shadow .18s,border-color .18s}
.sq:hover{transform:translateY(-2px);box-shadow:var(--sh-h);border-color:rgba(14,159,110,.45)}
.sq-ic{flex:0 0 auto;width:34px;height:34px;border-radius:11px;display:grid;place-items:center;background:linear-gradient(135deg,#e7f8f0,#fff2e8);color:var(--em);font-size:.95rem}
.chatlog{flex:1 1 auto;min-height:0;overflow-y:auto;overscroll-behavior:contain;gap:14px;margin:4px 0 0;padding:6px 4px 18px;scrollbar-width:thin}
.chatlog:empty{flex:1 1 auto}
.msg.a{font-size:.95rem;line-height:1.6;padding:16px 20px;width:auto;max-width:88%}
.msg.q{font-size:.95rem;padding:12px 18px}
.msg .src{display:none}
.askbar{position:static;flex:0 0 auto;padding:10px 0 0;background:none}
.askbar form{box-shadow:0 20px 50px -20px rgba(0,0,0,.35);padding:7px 7px 7px 18px}
.askbar input{font-size:1rem;padding:11px 8px}
.askbar .btn.tool{border:none;background:var(--canvas);color:var(--ink);border-radius:999px;width:42px;height:42px;padding:0;display:grid;place-items:center}
.askbar .btn.tool.rec{background:#e5484d;color:#fff;animation:pulse 1s infinite}
.askbar .btn.primary{height:42px}
.suggest-mini{display:none;gap:8px;flex-wrap:wrap;margin:0 0 10px;padding:0 6px}
.suggest-mini .chip{font-size:.78rem;padding:7px 13px}
.ai-wrap.has-chat .ai-hero{padding:6px 10px 0;display:flex;align-items:center;gap:14px;text-align:left}
.ai-wrap.has-chat .ai-logo{width:46px;height:46px;margin:0;animation:none;box-shadow:0 0 0 1px var(--line)}
.ai-wrap.has-chat .ai-logo .sk-logo{width:36px;height:36px;padding:2px}
.ai-wrap.has-chat .ai-hero h2{font-size:1.25rem;margin:0}
.ai-wrap.has-chat .ai-hero p{display:none}
.ai-wrap.has-chat .suggest{display:none}
.ai-wrap.has-chat .suggest-mini{display:flex}
@media (max-height:760px){ .ai-logo{width:72px;height:72px} .ai-logo .sk-logo{width:56px;height:56px} .ai-hero h2{font-size:1.9rem} .sq{padding:12px 14px;font-size:.92rem} }
"""
    open(CSS, "w", encoding="utf-8").write(css)
w = open(W, encoding="utf-8").read()
a = w.index("/* ===================== FUTURE 2"); b = w.index("</style>", a)
open(W, "w", encoding="utf-8").write(w[:a] + css + "\n" + w[b:])
print("refine patch applied")
