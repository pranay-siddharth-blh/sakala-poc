/* The document door on the WhatsApp POC (19 Oct 2026): "Upload a written complaint" beside the phone. The letter (PDF / photo,
   Kannada / English / both) is read into the official iPGRS form by the server (the same reader Mitra uses), shown for review
   with every field editable and "not provided" accepted, then ONE Submit files it through the same pipeline as a chat message:
   the 8 stages light up in "Behind the chat" and the Registered card lands in the chat. Nothing in the chat engine changes. */
(function () {
  if (typeof API !== 'function' || typeof WA === 'undefined') return;        // the wireframe (no server) has no document door
  const STYLE = `
.du-tile{display:flex;gap:12px;align-items:center;margin-top:12px;padding:12px 14px;border-radius:16px;border:1px dashed rgba(37,211,102,.55);background:linear-gradient(135deg,rgba(37,211,102,.12),rgba(251,183,86,.06));cursor:pointer;transition:transform .2s,box-shadow .25s,border-color .2s;position:relative;overflow:hidden;color:#fff}
.du-tile::before{content:"";position:absolute;inset:0;background:linear-gradient(100deg,transparent 30%,rgba(255,255,255,.1) 50%,transparent 70%);transform:translateX(-120%);transition:transform .9s}
.du-tile:hover{transform:translateY(-2px);border-color:#25d366;box-shadow:0 12px 34px rgba(37,211,102,.18)}.du-tile:hover::before{transform:translateX(120%)}
.du-tile .ic{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;background:rgba(37,211,102,.18);flex:none;font-size:20px}
.du-tile b{display:block;font-size:.95rem}.du-tile small{display:block;color:rgba(255,255,255,.7);font-size:.78rem;line-height:1.3}
.du-tile .k{margin-left:auto;font-size:.72rem;font-weight:700;padding:6px 10px;border-radius:999px;background:#25d366;color:#06110c;flex:none}
.du-ov{position:fixed;inset:0;z-index:400;background:rgba(5,8,12,.72);backdrop-filter:blur(10px);display:grid;place-items:center;animation:duIn .25s both}
@keyframes duIn{from{opacity:0}to{opacity:1}}
.du-m{width:min(1080px,94vw);max-height:92vh;overflow:auto;border-radius:22px;background:#fff;color:#0b0b0c;box-shadow:0 40px 120px rgba(0,0,0,.5);padding:22px 24px 18px;position:relative;animation:duUp .35s cubic-bezier(.2,.8,.2,1) both}
@keyframes duUp{from{opacity:0;transform:translateY(16px) scale(.98)}to{opacity:1;transform:none}}
.du-m h2{margin:0 0 4px;font-size:1.35rem;letter-spacing:-.02em}.du-m .sub{color:#667781;font-size:.85rem;margin-bottom:14px}
.du-x{position:absolute;top:14px;right:16px;width:34px;height:34px;border-radius:50%;border:1px solid #e5e7eb;background:#fff;cursor:pointer;font-size:16px}
.du-drop{border:2px dashed #9fe3a9;border-radius:18px;padding:34px 20px;text-align:center;background:linear-gradient(180deg,#f3fbf6,#fff);cursor:pointer;transition:border-color .2s,background .2s}
.du-drop.over,.du-drop:hover{border-color:#0e9f6e;background:#eafaf0}.du-drop .big{font-size:1.05rem;font-weight:700}.du-drop small{display:block;color:#667781;margin-top:6px}
.du-drop input{display:none}
.du-prog{display:flex;align-items:center;gap:12px;padding:14px 16px;border-radius:14px;background:#f6f8fa;margin-top:14px}
.du-prog i{width:18px;height:18px;border:2px solid #cfd8dc;border-top-color:#0e9f6e;border-radius:50%;animation:duSpin 1s linear infinite;flex:none}
@keyframes duSpin{to{transform:rotate(360deg)}}
.du-grid{display:grid;grid-template-columns:minmax(260px,1fr) minmax(0,1.5fr);gap:18px;margin-top:8px}
.du-pages img{width:100%;border-radius:12px;border:1px solid #e5e7eb;margin-bottom:10px;box-shadow:0 4px 14px rgba(0,0,0,.06)}
.du-sec{border:1px solid #e5e7eb;border-radius:14px;padding:12px 14px;margin-bottom:12px;background:#fafbfc}
.du-sec h4{margin:0 0 8px;font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:#0e9f6e}
.du-f{display:flex;flex-direction:column;gap:4px;margin-bottom:8px}
.du-f span{font-size:.74rem;color:#667781;display:flex;gap:6px;align-items:center}
.du-f input,.du-f textarea{width:100%;box-sizing:border-box;padding:9px 11px;border-radius:10px;border:1px solid #d9dee3;font:inherit;font-size:.9rem;background:#fff}
.du-f.miss input,.du-f.miss textarea{border-style:dashed}
.du-f input:focus,.du-f textarea:focus{outline:none;border-color:#0e9f6e;box-shadow:0 0 0 3px rgba(14,159,110,.15)}
.du-f em{font-size:.74rem;color:#da6823;font-style:normal}
.du-dot{width:8px;height:8px;border-radius:50%;display:inline-block}.du-dot.ok{background:#0e9f6e}.du-dot.amber{background:#fbb756}.du-dot.red{background:#e5484d}
.du-cls{display:flex;flex-direction:column;gap:4px}.du-cls b{font-size:1rem}.du-cls .p{color:#667781;font-size:.85rem}
.du-who{display:flex;gap:10px;align-items:center;padding:8px 10px;border-radius:12px;background:#eafaf0;margin-top:6px;font-size:.85rem}
.du-who .av{width:32px;height:32px;border-radius:50%;background:#0e9f6e;color:#fff;font-weight:800;display:grid;place-items:center;font-size:.75rem}
.du-note{font-size:.82rem;color:#7a5200;background:#fff7e6;border:1px solid #ffe2a8;border-radius:10px;padding:8px 10px;margin:4px 0 10px}
.du-bar{display:flex;gap:10px;align-items:center;justify-content:flex-end;margin-top:6px}
.du-go{padding:12px 22px;border-radius:999px;border:0;background:#0b0b0c;color:#fff;font-weight:700;font-size:.95rem;cursor:pointer;box-shadow:0 10px 26px rgba(0,0,0,.18)}
.du-go:disabled{opacity:.6;cursor:progress}
.du-sec2{padding:12px 14px;border-radius:14px;background:#f6f8fa;color:#667781;font-size:.82rem}
.du-rec{display:flex;gap:9px;align-items:flex-start;margin-top:10px;padding:9px 11px;border-radius:12px;background:linear-gradient(135deg,#eafaf0,#e8f6ff);border:1px solid #9fe3a9;color:#0b0b0c}
.du-rec i{flex:none;width:24px;height:24px;border-radius:50%;display:grid;place-items:center;font-style:normal;font-size:12px;background:#0e9f6e;color:#fff}
.du-rec b{display:block;font-size:.84rem}.du-rec div div{font-size:.76rem;color:#667781;margin-top:2px;line-height:1.35}
.du-done{text-align:center;padding:18px}.du-done .ok{width:64px;height:64px;border-radius:50%;background:#25d366;color:#fff;font-size:30px;display:grid;place-items:center;margin:0 auto 10px}
@media(max-width:860px){.du-grid{grid-template-columns:1fr}.du-pages{display:flex;gap:8px;overflow:auto}.du-pages img{width:120px;margin:0}}`;
  const st = document.createElement('style'); st.textContent = STYLE; document.head.appendChild(st);
  const E = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const S1 = [['description', 'Grievance, in the citizen\'s words', 'area'], ['address', 'Exact place (street, landmark, door)'], ['village', 'Village'], ['gp', 'Gram Panchayat'], ['taluk', 'Taluk'], ['district', 'District'], ['pincode', 'Pincode'], ['since', 'Since when']];
  const S3 = [['name', 'Name'], ['phone', 'Mobile number'], ['complainant_address', 'Address'], ['letter_date', 'Date of the letter'], ['addressed_to', 'Addressed to'], ['asked_for', 'What is asked for'], ['grievance_id', 'iPGRS number quoted in the letter']];

  function tile() {
    const left = document.querySelector('.wa-left'); if (!left || left.querySelector('.du-tile')) return;
    const t = document.createElement('div'); t.className = 'du-tile'; t.tabIndex = 0;
    t.innerHTML = '<div class="ic">📄</div><div><b>Upload a written complaint</b><small>A paper letter, PDF or photo · Kannada, English or both · read into the official form, then filed the same way</small></div><span class="k">Upload</span>';
    t.onclick = open; t.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } };
    const feats = left.querySelector('.wa-feats'); (feats || left).insertAdjacentElement('afterend', t);
  }
  let ov = null, draft = null;
  function close() { if (ov) { ov.remove(); ov = null; } }
  function open() {
    close(); ov = document.createElement('div'); ov.className = 'du-ov';
    ov.innerHTML = `<div class="du-m"><button class="du-x" title="Close">✕</button><h2>Upload a written complaint</h2><div class="sub">The letter is read into the official iPGRS grievance form. Check it, add anything the letter left out, then submit: it goes to the exact officer like any other request.</div>
      <div class="du-drop" id="duDrop"><input type="file" id="duFile" accept="application/pdf,image/*"><div class="big">Drop the letter here, or tap to choose</div><small>PDF, PNG or JPG · up to 30 MB · handwritten or typed · Kannada, English or mixed</small></div><div id="duBody"></div></div>`;
    document.body.appendChild(ov);
    ov.querySelector('.du-x').onclick = close; ov.onclick = e => { if (e.target === ov) close(); };
    const dz = ov.querySelector('#duDrop'), inp = ov.querySelector('#duFile');
    dz.onclick = e => { if (e.target !== inp) inp.click(); }; inp.onchange = () => read(inp.files[0]);
    ['dragenter', 'dragover'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('over'); }));
    ['dragleave', 'drop'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove('over'); }));
    dz.addEventListener('drop', e => { const f = e.dataTransfer.files && e.dataTransfer.files[0]; if (f) read(f); });
  }
  async function read(file) {
    if (!file) return; if (file.size > 30 * 1024 * 1024) return alert('The file is larger than 30 MB.');
    const body = ov.querySelector('#duBody'), dz = ov.querySelector('#duDrop'); dz.style.display = 'none';
    body.innerHTML = `<div class="du-prog"><i></i><div><b>Reading ${E(file.name)}…</b><div style="font-size:.8rem;color:#667781">Transcribing every page · masking personal numbers · filling the form · checking against the official masters</div></div></div>`;
    if (typeof resetStages === 'function') resetStages();
    if (typeof stage === 'function') { stage(0, 'Written complaint received · ' + file.name); stage(1, 'Reading the letter · personal numbers masked before AI', 'run'); }
    const b64 = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1]); fr.readAsDataURL(file); });
    let r;
    try { r = await API('/api/intake', { session: WA.sid || 'doc-' + Math.random().toString(36).slice(2, 10), step: 'document', file_b64: b64, media_type: file.type || (file.name.toLowerCase().endsWith('.pdf') ? 'application/pdf' : 'image/jpeg'), filename: file.name, channel: 'document' }); }
    catch (e) { body.innerHTML = `<div class="du-note">Could not read the file: ${E(e.message || e)}</div>`; dz.style.display = ''; return; }
    if (!r.ok) { body.innerHTML = `<div class="du-note">${r.reason === 'unreadable' ? 'No complaint could be read in that file, so nothing was guessed.' : 'Could not read the file (' + E(r.reason) + ').'}</div>`; dz.style.display = ''; return; }
    if (!WA.sid) WA.sid = r.session || WA.sid;
    draft = r;
    if (typeof stage === 'function') {
      stage(1, (r.masked_items ? r.masked_items + ' personal number(s) masked before AI' : 'Nothing personal to mask'));
      const u = r.u || {}; stage(2, u.intent === 'GRIEVANCE' ? `${u.dept || ''} › ${u.service || ''} · ${Math.round((u.conf || 0) * 100)}% · ${r.engine || ''}` : (u.intent === 'OUT_OF_SCOPE' ? `${u.dept || 'Another department'} · outside the pilot → scrutiny desk` : u.intent === 'UNCLEAR' ? 'Unclear · no category matches well → scrutiny desk' : (u.intent || 'read')), u.intent === 'GRIEVANCE' ? 'done' : 'warn');
      stage(3, r.place ? `From the letter: ${r.place.village || r.place.gp} → ${r.place.gp} GP, ${r.place.taluk}` : (r.taluk ? (u.intent === 'GRIEVANCE' ? `Taluk ${r.taluk} read · Gram Panchayat needed` : `Taluk ${r.taluk} read from the letter · its scrutiny desk`) : 'The letter does not name the place'), r.place || u.intent !== 'GRIEVANCE' ? 'done' : 'run');
      stage(4, 'Form shown for review · waiting for submit', 'run');
    }
    form(r);
  }
  function form(r) {
    const f = r.fields || {}, cf = r.confidence || {}, flags = Object.fromEntries((r.flags || []).map(x => [x.field, x])), u = r.u || {}, pv = r.preview || {}, o = pv.officer;
    const dot = k => { const c = cf[k]; if (!(k in cf) || !f[k]) return ''; const cls = flags[k] ? 'red' : c >= .9 ? 'ok' : c >= .6 ? 'amber' : 'red'; return `<i class="du-dot ${cls}" title="${flags[k] ? E(flags[k].why) : 'confidence ' + Math.round(c * 100) + '%'}"></i>`; };
    const fld = ([k, label, kind]) => { const v = f[k] || '', miss = !v, ph = miss ? 'Not in the letter · leave blank or type NA' : '';
      return `<label class="du-f ${miss ? 'miss' : ''}"><span>${label}${dot(k)}</span>${kind === 'area' ? `<textarea data-k="${k}" rows="5" placeholder="${ph}">${E(v)}</textarea>` : `<input data-k="${k}" value="${E(v)}" placeholder="${ph}">`}${flags[k] ? `<em>Two readings differ: “${E(flags[k].read)}” / “${E(flags[k].second || '')}”. Check it.</em>` : ''}</label>`; };
    const gaps = (r.missing || []).filter(k => ['name', 'phone', 'address'].includes(k));
    const cls = u.intent === 'GRIEVANCE' ? `<div class="du-cls"><b>${E(u.service || '')}</b><div class="p">${E(u.dept || '')}${u.grievance ? ' › ' + E(u.grievance) : ''} · ${Math.round((u.conf || 0) * 100)}% · from the official master</div>${o ? `<div class="du-who"><div class="av">${E((o.short || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase())}</div><div><b>${E(o.name)}</b><div style="font-size:.78rem;color:#667781">${E((pv.chain || []).map(c => c.short).join(' → '))} · ${pv.days} days</div></div></div>` : ''}</div>`
      : `<div class="du-note">${u.intent === 'UNCLEAR' ? 'No official category matches well; on submit the letter goes to the scrutiny desk, where a person routes it.' : u.intent === 'OUT_OF_SCOPE' ? 'This belongs to ' + E(u.dept || 'another department') + ', outside the three pilot departments; on submit the letter goes to the scrutiny desk, where a person routes it to that department.' : E(u.reason || u.intent || '')}</div>`;
    const rec = r.record, recRow = rec ? `<div class="du-rec"><i>⌘</i><div><b>Matches iPGRS record ${E(rec.gid)}</b><div>${E(rec.service || rec.grievance || '')} · ${E([rec.gp, rec.taluk, rec.district].filter(Boolean).join(', '))} · filed ${E((rec.created || '').slice(0, 10))} via ${E(rec.source || 'iPGRS')} · ${E(rec.status || '')}</div></div></div>` : '';
    ov.querySelector('#duBody').innerHTML = `<div class="du-grid"><div class="du-pages">${(r.thumbs || []).map((t, i) => `<img src="${t}" alt="page ${i + 1}">`).join('')}<div class="du-sec2"><b>${E(r.filename || 'Letter')}</b> · ${r.pages} page${r.pages > 1 ? 's' : ''} · read by Sakala AI in ${((r.ms || 0) / 1000).toFixed(0)} s${r.rotation ? ' · photo turned upright' : ''}${recRow}${r.english && r.english !== f.description ? `<details style="margin-top:8px"><summary style="cursor:pointer;color:#0e9f6e;font-weight:600">English rendering</summary><p style="margin:6px 0 0;color:#0b0b0c;line-height:1.45">${E(r.english)}</p></details>` : ''}</div></div>
      <div><div class="du-sec"><h4>1 · Grievance &amp; location${r.place ? ` <span style="color:#667781;letter-spacing:0;text-transform:none;font-weight:600"> 📍 ${E(r.place.gp ? r.place.gp + ' GP, ' : '')}${E(r.place.taluk)}</span>` : ''}</h4>${S1.map(fld).join('')}</div>
      <div class="du-sec"><h4>2 · Classification</h4>${cls}</div>
      <div class="du-sec"><h4>3 · Complainant</h4>${S3.map(fld).join('')}</div>
      ${gaps.length ? `<div class="du-note">The letter does not give ${gaps.map(k => ({ name: 'the complainant\'s name', phone: 'a phone number', address: 'the exact place' })[k]).join(' or ')}. Add it if you have it; otherwise it is filed as “not provided”.</div>` : ''}
      ${!r.place && !r.taluk ? '<div class="du-note">The letter does not name the village or taluk. Type the village or Gram Panchayat above (it is checked against the official list on submit).</div>' : ''}
      <div class="du-bar"><button class="du-go" id="duGo">${u.intent === 'GRIEVANCE' ? 'Submit the grievance' : 'Submit to the scrutiny desk'}</button></div></div></div>`;
    ov.querySelector('#duGo').onclick = submit;
  }
  const NA = /^\s*(na|n\/?a|nil|none|not available|not provided|-+|skip|no)\s*$/i;
  async function submit() {
    const go = ov.querySelector('#duGo'); go.disabled = true; go.textContent = 'Filing…';
    const fields = {}; ov.querySelectorAll('[data-k]').forEach(e => { fields[e.dataset.k] = NA.test(e.value) ? '' : e.value.trim(); });
    const r = draft, u = r.u || {}, rec = r.record;
    let place = r.place;
    const want = fields.gp || fields.village || '';
    if (want && (!place || ![place.gp, place.village].some(x => (x || '').toLowerCase() === want.toLowerCase()))) {
      try { const p = await API('/api/intake', { session: WA.sid, step: 'place', text: want, u, taluk: fields.taluk || '' }); if (p.place) place = p.place; else if (p.need === 'gp') { alert(`Which Gram Panchayat in ${p.taluk}? For example ${(p.gp_options || []).slice(0, 4).join(', ')}.`); go.disabled = false; go.textContent = 'Submit the grievance'; return; } } catch (e) { }
    }
    try {
      let res;
      if (u.intent !== 'GRIEVANCE') {
        res = await API('/api/intake', { session: WA.sid, step: 'scrutiny', text: fields.description || r.text, u, channel: 'document', taluk: fields.taluk || '',
          doc: Object.assign({}, fields, { filename: r.filename, pages: r.pages, reader: r.reader, evidence: r.evidence, flags: r.flags, english: r.english, confidence: r.confidence, transcript: (r.transcript || '').slice(0, 4000), record: rec && rec.gid }) });
        res.scrutiny = res.case_id;
      } else {
        if (!place) { alert('The place is needed to route it: please type the village or Gram Panchayat.'); go.disabled = false; go.textContent = 'Submit the grievance'; return; }
        res = await API('/api/intake', { session: WA.sid, step: 'create', text: fields.description || r.text, u, taluk: place.taluk, gp: place.gp || '', village: place.village || '', how: 'read from the letter', channel: 'document',
          doc: Object.assign({}, fields, { filename: r.filename, pages: r.pages, reader: r.reader, evidence: r.evidence, flags: r.flags, english: r.english, confidence: r.confidence, transcript: (r.transcript || '').slice(0, 4000), record: rec && rec.gid }) });
      }
      done(res, place);
    } catch (e) { alert('Could not file it: ' + (e.message || e)); go.disabled = false; go.textContent = 'Submit the grievance'; }
  }
  function done(res, place) {
    const id = res.id || res.scrutiny, o = res.officer;
    if (typeof stage === 'function') {
      stage(4, 'Submitted from the form · location valid');
      if (o) { stage(5, o.short + (res.fallback ? ' (fallback)' : '')); stage(6, `${res.days} days · then ${res.next}`); stage(7, 'Visible to officer & Chief Secretary now'); }
      else stage(5, 'Scrutiny desk · a person routes it', 'warn');
    }
    if (o && typeof showResult === 'function') showResult({ caseId: id, officer: o, chain: res.chain || [], basis: res.basis || '', title: 'Routed to' });
    if (typeof waPush === 'function') waPush({ me: false, type: 'card', t: new Date().toTimeString().slice(0, 5), html: `<div class="wa-ok"><span class="wa-okic">✓</span><b>Registered · ${E(id)}</b><p>Filed from your written complaint${o ? `. Assigned to <b>${E(o.name)}</b>` : ' · the scrutiny desk will route it'}.</p>${o ? `<p>⏱ Action due in <b>${res.days} days</b>. If not acted on, it moves automatically to <b>${E(res.next)}</b>.</p>` : ''}<p class="wa-muted">You will get every update here. Reply <b>TRACK</b> anytime.</p></div>` });
    ov.querySelector('#duBody').innerHTML = `<div class="du-done"><div class="ok">✓</div><h3 style="margin:0 0 4px">Registered · ${E(id)}</h3><div style="color:#667781">${o ? `Assigned to <b>${E(o.name)}</b> · ${res.days} days` : 'Sent to the scrutiny desk; a person will route it'}</div><div class="du-bar" style="justify-content:center;margin-top:16px"><button class="du-go" id="duClose">Done</button></div></div>`;
    ov.querySelector('#duClose').onclick = close;
    if (typeof loadState === 'function') { try { loadState(); } catch (e) { } }
  }
  const mo = new MutationObserver(() => tile()); mo.observe(document.body, { childList: true, subtree: true }); tile();
})();
