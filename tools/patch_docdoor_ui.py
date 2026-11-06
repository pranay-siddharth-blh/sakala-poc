"""The document door, Mitra UI (19 Oct 2026): a drop zone on the citizen's request card ("Upload a written complaint", PDF or photo,
drag & drop, camera on the phone), reading progress on the pipeline rail, then the official three-step form pre-filled from the
letter beside the page previews: every field editable, confidence dots, "not in the letter" accepted, flags explained, ONE Submit.
Works on the web desk and inside the phone sheet."""
import io
import re

ROOT = r"D:\Sakala POC\mitra\web"


def edit(path, pairs):
    p = ROOT + "\\" + path
    s = io.open(p, encoding="utf-8").read()
    for a, b in pairs:
        assert s.count(a) == 1, (path, a[:90], s.count(a))
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("patched", path)


edit("mitra.js", [
    # the request card: a document review when a letter was read; the drop zone otherwise
    ("""    if (opts.length) body += `<div class="opts">${opts.map(([l, a]) => `<button data-a="${esc(a)}">${esc(l)}</button>`).join('')}</div>`;
    body += `<div class="tools"><label class="photo">📎 Add a photo of a petition / document (optional)<input type="file" accept="image/*" id="reqPhoto"></label></div>`;
    panel('request', 'left', `<h3>Your request <small><span class="live-pill"><i></i>${esc(J.name)} · voice</span></small></h3><div class="req">${body}</div>`, { top: true });
    document.querySelectorAll('#left .req .opts button').forEach(b => b.onclick = () => turn({ text: b.textContent }));
    const f = $('#reqPhoto'); if (f) f.onchange = () => sendPhoto(f.files[0]);
  },""",
     """    if (d.doc) body = docReview(d, flow) + body.replace(/<div class="big">[\\s\\S]*?<\\/div><div class="path">[\\s\\S]*?<\\/div>/, '').replace(/<div class="quote">[\\s\\S]*?<\\/div>/, '').replace(/<div class="waiting">Say <b>“yes, file it”<\\/b>[\\s\\S]*?<\\/div>/, '');
    if (opts.length && !d.doc) body += `<div class="opts">${opts.map(([l, a]) => `<button data-a="${esc(a)}">${esc(l)}</button>`).join('')}</div>`;
    if (!d.doc) body += `<div class="dropz" id="dropz" tabindex="0"><input type="file" accept="application/pdf,image/*" id="reqFile" capture="environment"><div class="dz-ic"><i></i><svg viewBox="0 0 24 24"><path d="M12 16V4m0 0 4 4m-4-4-4 4" /><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" /></svg></div><div class="dz-t"><b>Upload a written complaint</b><span>PDF or photo · Kannada, English or both · the letter is read into the official form</span></div><span class="dz-k">Browse</span></div>`;
    panel('request', 'left', `<h3>${d.doc ? 'Your written complaint' : 'Your request'} <small><span class="live-pill"><i></i>${esc(J.name)} · ${d.doc ? 'document' : 'voice'}</span></small></h3><div class="req ${d.doc ? 'docmode' : ''}">${body}</div>`, { top: true });
    document.querySelectorAll('#left .req .opts button').forEach(b => b.onclick = () => turn({ text: b.textContent }));
    bindDrop();
    if (d.doc) bindDocReview(d);
  },""",
    ),
    # the document review form + the upload path
    ("""async function sendPhoto(file) {""",
     """// ---- the document door: a written complaint read into the official iPGRS form
const DOC_STEPS = [
  { title: '1 · Grievance & location', keys: [['description', 'Grievance, in the citizen\\'s words', 'area'], ['address', 'Exact place (street, landmark, door)'], ['village', 'Village'], ['gp', 'Gram Panchayat'], ['taluk', 'Taluk'], ['district', 'District'], ['pincode', 'Pincode'], ['since', 'Since when']] },
  { title: '2 · Classification', keys: [] },
  { title: '3 · Complainant', keys: [['name', 'Name'], ['phone', 'Mobile number'], ['complainant_address', 'Address'], ['letter_date', 'Date of the letter'], ['addressed_to', 'Addressed to'], ['asked_for', 'What is asked for']] },
];
function docReview(d, flow) {
  const doc = d.doc, f = doc.fields || {}, cf = doc.confidence || {}, ev = doc.evidence || {}, flags = Object.fromEntries((doc.flags || []).map(x => [x.field, x]));
  const p = d.place || {}, pv = d.preview || {}, o = pv.officer;
  const dot = k => { const c = cf[k]; if (!(k in cf) || !f[k]) return ''; const cls = flags[k] ? 'red' : c >= .9 ? 'ok' : c >= .6 ? 'amber' : 'red'; return `<i class="cdot ${cls}" title="${flags[k] ? esc(flags[k].why) : 'confidence ' + Math.round(c * 100) + '%'}"></i>`; };
  const field = ([k, label, kind]) => {
    const v = f[k] || '', miss = !v, ph = miss ? 'Not in the letter · leave blank or type NA' : '';
    const inp = kind === 'area' ? `<textarea data-k="${k}" rows="4" placeholder="${ph}">${esc(v)}</textarea>` : `<input data-k="${k}" value="${esc(v)}" placeholder="${ph}">`;
    return `<label class="dfield ${miss ? 'miss' : ''} ${flags[k] ? 'flag' : ''}"><span class="dl">${label}${dot(k)}</span>${inp}${flags[k] ? `<em class="dflag">Two readings differ: “${esc(flags[k].read)}” / “${esc(flags[k].second || '')}”. Check it.</em>` : ''}${ev[k] && !miss ? `<em class="dev">${esc(ev[k])}</em>` : ''}</label>`;
  };
  const thumbs = (doc.thumbs || []).map((t, i) => `<img src="${t}" alt="page ${i + 1}" data-i="${i}" title="Page ${i + 1} · tap to enlarge">`).join('');
  const head = `<div class="dhead"><div class="dthumbs">${thumbs}</div><div class="dmeta"><b>${esc(doc.filename || 'Written complaint')}</b><span>${doc.pages || 1} page${(doc.pages || 1) > 1 ? 's' : ''} · read by Sakala AI${doc.ms ? ' in ' + (doc.ms / 1000).toFixed(0) + ' s' : ''}</span>${doc.several ? '<span class="pill warn">The letter seems to hold more than one complaint</span>' : ''}${doc.english && doc.english !== f.description ? `<details class="deng"><summary>English rendering</summary><p>${esc(doc.english)}</p></details>` : ''}</div></div>`;
  const cls = `<div class="dsec"><h4>${DOC_STEPS[1].title}</h4><div class="dclass"><div class="big">${esc(d.service || '—')}</div><div class="path">${esc(d.dept || '')}${d.grievance ? ' › ' + esc(d.grievance) : ''}${d.vulnerable ? ' · <span class="pill vio">♥ priority</span>' : ''}</div>${d.conf != null ? `<div class="conf"><span>AI confidence</span><span class="m"><i style="width:${d.conf}%"></i></span><b>${d.conf}%</b> <span>· from the official master</span></div>` : ''}${o ? `<div class="who"><div class="av">${esc((o.short || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase())}</div><div><div class="n">${esc(o.name)}</div><div class="c">${esc((pv.chain || []).map(c => c.short).join(' → '))} · ${pv.days} days</div></div></div>` : ''}</div></div>`;
  const s1 = `<div class="dsec"><h4>${DOC_STEPS[0].title}${p.taluk ? ` <small>📍 ${esc(p.gp ? p.gp + ' GP, ' : '')}${esc(p.taluk)} · ${esc(p.how || '')}</small>` : ''}</h4>${DOC_STEPS[0].keys.map(field).join('')}</div>`;
  const s3 = `<div class="dsec"><h4>${DOC_STEPS[2].title}</h4>${DOC_STEPS[2].keys.map(field).join('')}</div>`;
  const gaps = (doc.missing || []).filter(k => ['name', 'phone', 'address'].includes(k));
  const note = gaps.length ? `<div class="dnote">The letter does not give ${gaps.map(k => ({ name: 'the complainant\\'s name', phone: 'a phone number', address: 'the exact place' })[k]).join(' or ')}. Add it if you have it; otherwise it is filed as “not provided”.</div>` : '';
  const bar = flow === 'confirm' ? `<div class="dsubmit"><button class="dgo" id="docSubmit"><span>Submit</span><small>files it to ${o ? esc(o.short) : 'the officer'}</small></button><button class="dchg" id="docChange">Change</button></div>`
    : `<div class="dnote">${flow === 'ask_gp' ? 'Which Gram Panchayat? Say it, or pick below.' : 'The letter does not name the village or taluk. Say it, share your location, or pick a taluk.'}</div>`;
  return `<div class="docrev">${head}${s1}${cls}${s3}${note}${bar}</div>`;
}
function bindDocReview(d) {
  const host = document.querySelector('#left .docrev'); if (!host) return;
  host.querySelectorAll('.dthumbs img').forEach(im => im.onclick = () => { const lb = document.createElement('div'); lb.className = 'dlight'; lb.innerHTML = `<img src="${im.src}" alt=""><span>tap to close</span>`; lb.onclick = () => lb.remove(); document.body.appendChild(lb); });
  const collect = () => { const o = {}; host.querySelectorAll('[data-k]').forEach(e => { o[e.dataset.k] = e.value; }); return o; };
  const go = $('#docSubmit'); if (go) go.onclick = async () => {
    go.disabled = true; go.querySelector('span').textContent = 'Filing…'; stopSpeaking(); setState('thinking', 'Filing your complaint…'); traceReset(); trace('listen', 'done'); trace('think', 'run');
    try {
      const r = await api('/api/document/submit', { session: J.sid, fields: collect() });
      trace('think', 'done'); trace('act', 'done'); trace('speak', 'run'); applyUi(r.ui || []); captionYou('Submit');
      if (r.tts_id && (r.parts || []).length > 1) await speakParts(r); else await speak(r.say, r.audio_b64, r.tts);
      trace('speak', 'done');
    } catch (e) { toast('Submit', e.message || 'could not file it'); setState('idle', 'Ready'); go.disabled = false; go.querySelector('span').textContent = 'Submit'; }
  };
  const ch = $('#docChange'); if (ch) ch.onclick = () => turn({ text: 'change' });
  // typed edits live in the draft until Submit; a changed place is resolved on Submit
}
function bindDrop() {
  const dz = $('#dropz'), inp = $('#reqFile'); if (!dz || !inp) return;
  dz.onclick = e => { if (e.target !== inp) inp.click(); };
  dz.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); inp.click(); } };
  inp.onchange = () => sendDocument(inp.files[0]);
  ['dragenter', 'dragover'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove('over'); }));
  dz.addEventListener('drop', e => { const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]; if (f) sendDocument(f); });
}
async function sendDocument(file) {
  if (!file) return;
  if (file.size > 30 * 1024 * 1024) return toast('Document', 'The file is larger than 30 MB');
  const b64 = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1]); fr.readAsDataURL(file); });
  const dz = $('#dropz'); if (dz) { dz.classList.add('busy'); dz.querySelector('.dz-t b').textContent = 'Reading the letter…'; dz.querySelector('.dz-t span').textContent = file.name + ' · transcribing, filling the form, checking against the masters'; }
  stopSpeaking(); setState('thinking', 'Reading the letter…'); traceReset(); trace('listen', 'done'); trace('think', 'run');
  applyUi([{ op: 'stages', items: [{ i: 0, state: 'done', note: `Written complaint received · ${file.name}` }, { i: 1, state: 'run', note: 'Reading every page · personal numbers masked before AI' }] }]);
  try {
    const r = await api('/api/document', { session: J.sid, file_b64: b64, media_type: file.type || (file.name.toLowerCase().endsWith('.pdf') ? 'application/pdf' : 'image/jpeg'), filename: file.name });
    trace('think', 'done'); trace('act', 'done'); trace('speak', 'run');
    applyUi(r.ui || []); captionYou('📄 ' + file.name); Orb.burst(); flyLabel('letter read → form');
    if (r.tts_id && (r.parts || []).length > 1) await speakParts(r); else await speak(r.say, r.audio_b64, r.tts);
    trace('speak', 'done');
  } catch (e) { toast('Document', e.message || 'could not read it'); setState('idle', 'Ready'); if (dz) { dz.classList.remove('busy'); dz.querySelector('.dz-t b').textContent = 'Upload a written complaint'; } }
}
async function sendPhoto(file) {"""),
])

css = io.open(ROOT + r"\mitra.css", encoding="utf-8").read()
assert "/* v62 · the document door" not in css
css += '''
/* v62 · the document door: drop zone + the official form read from a letter (web and phone) */
.dropz{position:relative;display:flex;align-items:center;gap:12px;margin-top:12px;padding:12px 14px;border-radius:16px;border:1px dashed rgba(22,199,132,.45);background:linear-gradient(135deg,rgba(22,199,132,.08),rgba(121,227,255,.04));cursor:pointer;transition:border-color .2s,transform .2s,box-shadow .3s;overflow:hidden}
.dropz input{display:none}
.dropz::before{content:"";position:absolute;inset:0;background:linear-gradient(100deg,transparent 30%,rgba(255,255,255,.08) 50%,transparent 70%);transform:translateX(-120%);transition:transform .9s ease}
.dropz:hover,.dropz:focus-visible{border-color:var(--em);transform:translateY(-1px);box-shadow:0 10px 30px rgba(22,199,132,.12);outline:none}
.dropz:hover::before{transform:translateX(120%)}
.dropz.over{border-style:solid;border-color:var(--em);background:rgba(22,199,132,.16);box-shadow:0 0 0 4px rgba(22,199,132,.15)}
.dropz .dz-ic{position:relative;width:40px;height:40px;border-radius:12px;display:grid;place-items:center;background:rgba(22,199,132,.14);flex:none}
.dropz .dz-ic svg{width:20px;height:20px;fill:none;stroke:var(--em);stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.dropz .dz-ic i{position:absolute;inset:-3px;border-radius:14px;border:1px solid rgba(22,199,132,.35);animation:blink 2.2s infinite}
.dropz .dz-t{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
.dropz .dz-t b{font-size:13px}.dropz .dz-t span{font-size:11px;color:var(--mute);line-height:1.35}
.dropz .dz-k{font-size:11px;font-weight:700;padding:6px 10px;border-radius:999px;background:var(--em);color:#06110c;flex:none}
.dropz.busy{cursor:progress;border-style:solid}
.dropz.busy .dz-ic{animation:dzspin 1.2s linear infinite}
@keyframes dzspin{to{transform:rotate(360deg)}}
.dropz.busy .dz-k{display:none}
.docrev{display:flex;flex-direction:column;gap:12px}
.dhead{display:flex;gap:12px;align-items:flex-start}
.dthumbs{display:flex;gap:6px;flex:none}
.dthumbs img{width:64px;height:84px;object-fit:cover;object-position:top;border-radius:8px;border:1px solid var(--line2);background:#fff;cursor:zoom-in;transition:transform .2s,box-shadow .2s}
.dthumbs img:hover{transform:translateY(-2px) scale(1.03);box-shadow:0 8px 24px rgba(0,0,0,.35)}
.dmeta{min-width:0;display:flex;flex-direction:column;gap:3px}
.dmeta b{font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dmeta>span{font-size:11px;color:var(--mute)}
.deng{font-size:12px;color:var(--mute);margin-top:4px}.deng summary{cursor:pointer;color:var(--em);font-weight:600}.deng p{margin:6px 0 0;line-height:1.45;color:var(--tx)}
.dsec{border:1px solid var(--line);border-radius:14px;padding:10px 12px;background:var(--s1)}
.dsec h4{font-size:10.5px;text-transform:uppercase;letter-spacing:.12em;color:var(--em);margin:0 0 8px;display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.dsec h4 small{text-transform:none;letter-spacing:0;color:var(--mute);font-weight:600;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dfield{display:flex;flex-direction:column;gap:4px;margin-bottom:8px}
.dfield .dl{font-size:11px;color:var(--mute);display:flex;align-items:center;gap:6px}
.dfield input,.dfield textarea{width:100%;box-sizing:border-box;padding:8px 10px;border-radius:10px;border:1px solid var(--line2);background:var(--s2);color:var(--tx);font:inherit;font-size:13px;line-height:1.4;transition:border-color .2s,box-shadow .2s}
.dfield textarea{resize:vertical;min-height:72px}
.dfield input:focus,.dfield textarea:focus{outline:none;border-color:var(--em);box-shadow:0 0 0 3px rgba(22,199,132,.15)}
.dfield.miss input,.dfield.miss textarea{border-style:dashed}
.dfield.flag input{border-color:rgba(255,154,60,.7)}
.dfield .dflag{font-size:11px;color:var(--saf);font-style:normal}
.dfield .dev{font-size:10.5px;color:var(--mute2);font-style:normal;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cdot{width:8px;height:8px;border-radius:50%;display:inline-block}.cdot.ok{background:var(--em);box-shadow:0 0 8px var(--em)}.cdot.amber{background:var(--saf)}.cdot.red{background:var(--bad)}
.dclass .big{font-size:16px}
.dnote{font-size:12px;color:var(--mute);padding:8px 10px;border-radius:10px;background:rgba(255,154,60,.08);border:1px solid rgba(255,154,60,.3)}
.dsubmit{display:flex;gap:8px;align-items:stretch}
.dgo{flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;padding:12px 14px;border-radius:14px;border:0;background:linear-gradient(135deg,var(--em),var(--em2));color:#06110c;font-weight:800;font-size:15px;cursor:pointer;box-shadow:0 10px 30px rgba(22,199,132,.3);transition:transform .15s,box-shadow .2s}
.dgo small{font-size:10.5px;font-weight:600;opacity:.8}
.dgo:hover{transform:translateY(-1px);box-shadow:0 14px 36px rgba(22,199,132,.4)}
.dgo:disabled{opacity:.6;cursor:progress;transform:none}
.dchg{padding:12px 16px;border-radius:14px;border:1px solid var(--line2);background:var(--s2);color:var(--tx);font-weight:700;cursor:pointer}
.dlight{position:fixed;inset:0;z-index:300;background:rgba(5,5,7,.86);display:grid;place-items:center;cursor:zoom-out;animation:up .25s both}
.dlight img{max-width:min(92vw,900px);max-height:88vh;border-radius:12px;box-shadow:0 30px 80px rgba(0,0,0,.6);background:#fff}
.dlight span{position:absolute;bottom:18px;left:50%;transform:translateX(-50%);font-size:12px;color:#fff;opacity:.7}
html[data-theme=light] .dropz{background:linear-gradient(135deg,rgba(14,159,110,.08),rgba(43,127,217,.04))}
html[data-theme=light] .dthumbs img:hover{box-shadow:0 8px 24px rgba(20,30,60,.18)}
html[data-theme=light] .dfield input,html[data-theme=light] .dfield textarea{background:#fff}
html[data-theme=light] .dgo{color:#fff}
@media (max-width:600px){.dhead{flex-direction:column}.dthumbs img{width:56px;height:74px}.dfield input,.dfield textarea{font-size:14px;padding:10px 12px}.dgo{padding:14px}}
'''
io.open(ROOT + r"\mitra.css", "w", encoding="utf-8", newline="").write(css)
print("patched mitra.css")

h = io.open(ROOT + r"\index.html", encoding="utf-8").read()
h = re.sub(r"/mitra\.css\?v=\d+", "/mitra.css?v=62", h)
h = re.sub(r"/mitra\.js\?v=(\d+)", lambda m: f"/mitra.js?v={int(m.group(1)) + 1}", h)
io.open(ROOT + r"\index.html", "w", encoding="utf-8", newline="").write(h)
print("bumped")
