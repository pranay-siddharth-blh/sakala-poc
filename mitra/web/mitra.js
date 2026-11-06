/* Mitra client: voice in, voice out, three profile stages, live sync. */
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const J = {
  sid: localStorage.getItem('jv_sid') || '', profile: localStorage.getItem('jv_profile') || 'citizen',
  officer: localStorage.getItem('jv_officer') || 'tah_piriyapatna', lang: localStorage.getItem('jv_lang') || 'en',
  boot: null, busy: false, speaking: false, handsfree: false, options: [], caseId: null, charts: {}, stages: {},
  audio: null, mic: null, analyser: null, proc: null, chunks: [], rec: false, inRate: 48000, recog: null, hfActive: false,
  lastSay: '', started: false, levelTimer: null,
  wakeOn: true, wakeRec: null, wakeHit: false, ring: [], ringLen: 0, abort: false, followUntil: 0, capturing: false, name: 'Mitra', wakeWords: ['mitra']
};
const PROFILE_NAMES = { citizen: 'Citizen', officer: 'Officer', cs: 'Chief Secretary' };
const STAGES = [['Entry', 'Mitra · you just say it'], ['Privacy shield', 'Phone, Aadhaar, ration-card numbers masked'],
  ['AI understanding', 'Department → Line dept → Service → Grievance'], ['Completion agent', 'Asks only for what is missing'],
  ['Validate & confirm', 'Location, duplicates, citizen confirms'], ['Exact-officer routing', 'Village / GP → named field officer'],
  ['Deadlines & reminders', 'Clock starts · escalation chain armed'], ['Leadership view', 'Live on the officer & Chief Secretary screens']];
const HINTS = {
  citizen: ['There is no drinking water in Gorahalli', 'Street light near the bus stand in Piriyapatna is not working', 'Track my request', 'Any update from the officer?', 'Apply for a caste certificate'],
  officer: ['Read my inbox', 'Open the first one', 'Accept', 'Draft the report', 'Resolve: inspected the site, pipeline repaired, supply restored', 'Ask the citizen which street', 'Next case'],
  cs: ['Give me the position', 'Show the overdue cases', 'Which officer has the most overdue cases?', 'Nudge the Tahsildar of Piriyapatna', 'Read the Wednesday pack', 'Sakala 2025 district performance', 'Move time forward by 7 days']
};

// ------------------------------------------------------------------ api
async function api(path, body, method = 'POST') {
  const r = await fetch(path, { method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
function toast(h, m) {
  const el = document.createElement('div'); el.className = 'toast'; el.innerHTML = `<b>${esc(h)}</b>${esc(m)}`;
  $('#toasts').appendChild(el); setTimeout(() => el.remove(), 4200);
}

// ------------------------------------------------------------------ boot
async function boot() {
  const b = await api('/api/boot', null, 'GET'); J.boot = b;
  const p = b.providers;
  const st = $('#status'); st.classList.toggle('ok', b.sakala);
  $('#statusText').textContent = !b.sakala ? 'iPGRS offline' : b.brain === 'rules' ? 'Mitra · offline mode' : 'Mitra · online';
  const sel = $('#officerSel'); sel.innerHTML = '';
  const offs = Object.entries(b.officers).sort((a, c) => (a[1].lv + a[1].short).localeCompare(c[1].lv + c[1].short));
  for (const [id, o] of offs) { const op = document.createElement('option'); op.value = id; op.textContent = `${o.lv} · ${o.short}`; sel.appendChild(op); }
  sel.value = J.officer; sel.onchange = () => { const o = J.boot?.officers?.[sel.value]; switchTo('officer', { officer: sel.value, title: o ? `Opening ${o.short}'s desk` : null, sub: o ? `${o.lv} · logged in` : null }); };
  if (b.now) $('#clock').textContent = fmtDate(b.now);
  J.name = b.name || 'Mitra'; J.wakeWords = (b.wake && b.wake.length) ? b.wake : [J.name.toLowerCase()];
  $('#wakeLabel').textContent = `“Hey ${J.name}”`;
  document.querySelector('.brand-t b').innerHTML = `<span class="grad">${esc(J.name)}</span>`;
  renderLang();
}
function fmtDate(iso) { const d = new Date(iso); return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }); }

async function greet() {
  if (liveWanted() && liveOpen()) LV.q.push({ greet: true });       // greet in the live voice; the conversation is already open
  else await turn({ text: 'help', silentEcho: true });
}
// every switch of profile (or of the officer logged in) goes through the portal: swap behind it, greet after it
async function switchTo(profile, { officer = null, title = null, sub = null, then = null } = {}) {
  const from = J.profile;
  $('#prof').classList.remove('open'); stopAll();
  await Portal.run(profile, async () => {
    if (officer) { J.officer = officer; localStorage.setItem('jv_officer', officer); }
    J.profile = profile; localStorage.setItem('jv_profile', profile);
    await session(false);
  }, { from, title, sub });
  if (then) then(); else greet();
}
async function session(speakHello = false) {
  if (LV.open) liveClose('profile');
  const s = await api('/api/session', { session: J.sid, profile: J.profile, officer: J.officer, lang: J.lang });
  J.sid = s.session; localStorage.setItem('jv_sid', J.sid); J.profile = s.profile; localStorage.setItem('jv_profile', J.profile);
  J.officer = s.officer; J.caseId = null;
  renderProfile(); clearPanels(); applyUi(s.ui || []); renderConvo();
  if (J.profile === 'citizen' && !panels.left.get('request')) UI.request({ draft: {}, flow: 'menu', options: [] });
  if (J.started) connectEvents();
  loadNotifs();
  if (speakHello) await greet();
}

// ------------------------------------------------------------------ profile chrome
const PROF = { citizen: ['👤', 'Citizen', 'Mitra · Karnataka'], officer: ['🧑‍💼', 'Officer', ''], cs: ['🏛️', 'Chief Secretary', 'Government of Karnataka'] };
function renderProfile() {
  document.querySelectorAll('#profiles button').forEach(b => b.classList.toggle('on', b.dataset.p === J.profile));
  $('#officerPick').hidden = J.profile !== 'officer';
  if ($('#officerSel').value !== J.officer) $('#officerSel').value = J.officer;
  const [av, nm, sub] = PROF[J.profile] || PROF.citizen, o = J.boot?.officers?.[J.officer];
  $('#profAv').textContent = av; $('#profName').textContent = nm;
  $('#profSub').textContent = J.profile === 'officer' ? (o ? `${o.short} · ${o.lv}` : 'logged in') : sub;
  document.body.dataset.profile = J.profile; const at = $('#attach'); if (at) at.hidden = J.profile !== 'citizen';
  $('#hints').innerHTML = (HINTS[J.profile] || []).map(h => `<button>${esc(h)}</button>`).join('');
  document.querySelectorAll('#hints button').forEach(b => b.onclick = () => turn({ text: b.textContent }));
  setState('idle', J.profile === 'citizen' ? 'Tell me what is wrong' : J.profile === 'officer' ? 'Say "read my inbox"' : 'Say "give me the position"');
}
// Light / dark. Every fresh open starts light (start page and all three profiles); a switch to dark holds for this tab: html[data-theme] + sessionStorage.
// The change sweeps in from the bottom-left as an expanding circle (View Transitions) with a glowing wave on its edge.
const Theme = (() => {
  const KEY = 'jv_theme';
  const cur = () => document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';      // light is the default
  function apply(t) {
    document.documentElement.dataset.theme = t; try { sessionStorage.setItem(KEY, t); } catch (e) { }      // this tab only: every fresh open starts light
    const b = $('#theme'); if (b) b.title = t === 'light' ? 'Switch to dark mode' : 'Switch to light mode';
  }
  function wave(ox, oy, t) { const w = document.createElement('div'); w.className = 'theme-wave ' + t; w.style.left = ox + 'px'; w.style.top = oy + 'px'; document.body.appendChild(w); setTimeout(() => w.remove(), 1500); }
  function set(t) {
    t = t === 'light' ? 'light' : 'dark'; if (t === cur()) return false;
    const ox = 28, oy = innerHeight - 30;                                   // from the bottom-left corner, up and across
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!document.startViewTransition || reduced) { apply(t); return true; }
    const maxR = Math.hypot(innerWidth - ox, oy) + 40;
    try {
      const vt = document.startViewTransition(() => apply(t));
      vt.ready.then(() => { wave(ox, oy, t); document.documentElement.animate({ clipPath: [`circle(0px at ${ox}px ${oy}px)`, `circle(${maxR}px at ${ox}px ${oy}px)`] }, { duration: 1150, easing: 'cubic-bezier(.7,0,.2,1)', pseudoElement: '::view-transition-new(root)' }); }).catch(() => { });
    } catch (e) { apply(t); }
    return true;
  }
  const toggle = () => set(cur() === 'light' ? 'dark' : 'light');
  try { apply(sessionStorage.getItem(KEY) || 'light'); } catch (e) { apply('light'); }
  return { set, toggle, cur };
})();
$('#theme').onclick = () => Theme.toggle();
function renderLang() {
  document.querySelectorAll('#lang button').forEach(b => b.classList.toggle('on', b.dataset.l === J.lang));
  document.documentElement.lang = J.lang === 'kn' ? 'kn' : 'en';
  if (renderLang.last && renderLang.last !== J.lang) {               // changed by voice: the toggle answers, the orb pulses
    const l = $('#lang'); if (l) { l.classList.remove('switched'); void l.offsetWidth; l.classList.add('switched'); setTimeout(() => l.classList.remove('switched'), 1300); }
    if (document.querySelector('.orb-wrap')) { Orb.pulse(); flyLabel(J.lang === 'kn' ? 'ಕನ್ನಡ' : 'English'); }
    modePill();
  }
  renderLang.last = J.lang;
}
document.querySelectorAll('#profiles button').forEach(b => b.onclick = async () => {
  if (b.dataset.p === J.profile) { $('#prof').classList.remove('open'); return; }
  await switchTo(b.dataset.p);
});
// the profile switcher (bottom left) opens upward; any click elsewhere, or Escape, closes it
$('#profBtn').onclick = e => { e.stopPropagation(); $('#prof').classList.toggle('open'); };
// "Teach Mitra how you say its name": records the name three times and lets the server learn the spelling it hears
async function teachName() {
  $('#prof').classList.remove('open');
  if (!J.mic) { toast('Teach', 'The microphone is needed; press Start first.'); return; }
  if (J.muted) setMuted(false, { quiet: true });
  if (LV.open) liveClose('teach');
  stopAll(); J.teaching = true;
  const results = [];
  for (let i = 1; i <= 3; i++) {
    setState('listening', `Say “${J.name}” · ${i} of 3`); chime(true);
    await new Promise(r => setTimeout(r, 350));
    J.chunks = []; J.rec = true; Orb.setSource(J.analyser);
    await new Promise(r => setTimeout(r, 1700));
    J.rec = false; Orb.setSource(null);
    const b64 = encodeWav(J.chunks, J.inRate, 16000); J.chunks = [];
    setState('thinking', 'Learning…');
    try { const r = await api('/api/wake_learn', { audio_b64: b64, lang: J.lang }); results.push(r); toast(`Heard “${r.heard || '…'}”`, r.matched ? 'already understood' : r.learned ? `learned “${r.variant}”` : (r.reason || 'not learned')); }
    catch (e) { toast('Teach', e.message); }
  }
  J.teaching = false;
  try { J.boot = await api('/api/boot', null, 'GET'); } catch (e) { }
  const n = results.filter(r => r.learned).length, m = results.filter(r => r.matched).length;
  setState('idle', `Say “Hey ${J.name}”`); chime(false);
  toast(J.name, n ? `Learned ${n} new way${n > 1 ? 's' : ''} you say my name.` : m ? 'I already understand you perfectly.' : 'Could not learn from that; try again a little closer to the mic.');
}
$('#teach').onclick = e => { e.stopPropagation(); teachName(); };
$('#forgetBtn').onclick = async e => { e.stopPropagation(); $('#prof').classList.remove('open');
  try { await api('/api/forget', { session: J.sid }); UI.forget(); } catch (x) { toast('Not deleted', 'Please try again.'); } };
// guardrail 17: an action that cannot be undone waits here for a spoken (or tapped) yes
function confirmBar(q) {
  let bar = $('#confirmBar');
  if (!q) { if (bar) { bar.classList.remove('on'); setTimeout(() => bar && !bar.classList.contains('on') && bar.remove(), 400); } return; }
  if (!bar) { bar = document.createElement('div'); bar.id = 'confirmBar'; bar.className = 'confirm-bar'; document.body.appendChild(bar); }
  bar.innerHTML = `<i class="cb-ic">!</i><span class="cb-q">${esc(q)}</span><button class="cb-yes">Yes, do it</button><button class="cb-no">No</button><i class="cb-t"></i>`;
  bar.querySelector('.cb-yes').onclick = () => { confirmBar(null); turn({ text: 'yes' }); };
  bar.querySelector('.cb-no').onclick = () => { confirmBar(null); turn({ text: 'no' }); };
  requestAnimationFrame(() => bar.classList.add('on'));
  clearTimeout(J.cbT); J.cbT = setTimeout(() => confirmBar(null), 120000);
}
$('#profiles').addEventListener('click', e => e.stopPropagation());
document.addEventListener('click', () => $('#prof').classList.remove('open'));
document.querySelectorAll('#lang button').forEach(b => b.onclick = () => turn({ text: b.dataset.l === 'kn' ? 'speak in kannada' : 'speak in english' }));

// ------------------------------------------------------------------ state / captions
function setState(s, text) {
  if (J.muted && s === 'idle') { s = 'muted'; text = 'Tap the mic to unmute'; }
  Orb.setState(s); const el = $('#state'); el.className = 'orb-state ' + s; $('.k', el).textContent = s;
  if (text != null) $('#stateText').textContent = text;
  parkPill(s);
}
// while a chart or board is up the orb parks small in the corner: a live pill under it keeps saying what Mitra is doing
// (listening / speaking / thinking), its dot breathing with the voice level, and a tap on it talks or stops, like the orb
function parkPill(s) {
  let p = $('#parkPill');
  if (!p) {
    p = document.createElement('button'); p.id = 'parkPill'; p.className = 'park-pill'; p.innerHTML = '<i></i><span></span>';
    p.onclick = () => { if (typeof Orb !== 'undefined' && Orb.onTap) Orb.onTap(); };
    document.body.appendChild(p);
  }
  const lab = { listening: 'Listening', speaking: 'Speaking', thinking: 'Thinking', hearing: 'Hearing you', idle: LV && LV.open ? 'Live · listening' : 'Tap to talk', muted: 'Muted' }[s || 'idle'] || s;
  p.dataset.s = s || 'idle'; p.querySelector('span').textContent = lab;
  placePill();
}
function placePill() {
  const p = $('#parkPill'), w = $('.orb-wrap'); if (!p || !w) return;
  if (!document.body.classList.contains('stage-in')) { p.classList.remove('on'); return; }
  const r = w.getBoundingClientRect(); p.style.left = (r.left + r.width / 2) + 'px'; p.style.top = (r.bottom + 4) + 'px'; p.classList.add('on');
}
new MutationObserver(() => { placePill(); setTimeout(placePill, 900); setTimeout(placePill, 1500); }).observe(document.body, { attributes: true, attributeFilter: ['class'] });
addEventListener('resize', () => placePill());
function captionYou(t) { $('#capYou').textContent = t || ''; }
let capTimer = null;
function captionMitra(text, duration) {
  const el = $('#capJv'); clearTimeout(capTimer); el.innerHTML = '';
  if (!text) return;
  const words = text.split(/\s+/); const per = Math.max(60, Math.min(260, ((duration || words.length * .3) * 1000) / words.length));
  words.forEach((w, i) => { const s = document.createElement('span'); s.className = 'w'; s.style.animationDelay = `${i * per}ms`; s.textContent = w; el.appendChild(s); });
  // a long reply: keep the words being spoken in view (the caption box scrolls inside itself)
  const box = el.parentElement; box.scrollTop = 0; clearInterval(J._capScroll);
  const end = performance.now() + words.length * per + 600;
  J._capScroll = setInterval(() => {
    if (performance.now() > end) { clearInterval(J._capScroll); return; }
    const spoken = Math.min(words.length - 1, Math.floor((performance.now() - (end - words.length * per - 600)) / per));
    Stage.hear(words.slice(0, spoken + 1).join(' '));
    const w = el.children[spoken]; if (!w) return;
    const want = w.offsetTop + w.offsetHeight - box.clientHeight + 24;
    if (want > box.scrollTop) box.scrollTop += Math.min(want - box.scrollTop, 4);
  }, 40);
}

// ------------------------------------------------------------------ live step trace
function trace(k, st, note) {
  const el = document.querySelector(`#trace span[data-k="${k}"]`); if (!el) return;
  el.className = st || ''; const b = el.querySelector('b'); if (b) b.remove();
  if (note) { const n = document.createElement('b'); n.textContent = note; el.appendChild(n); }
}
function traceReset() { document.querySelectorAll('#trace span').forEach(s => { s.className = ''; const b = s.querySelector('b'); if (b) b.remove(); }); }

// ------------------------------------------------------------------ the turn
// wakeOnly: a hands-free scan clip; the server acts only if it starts with the wake word, otherwise it is ignored
// Every turn gets a sequence number. A wake-word clip that arrives while an older turn is still in flight or
// still talking takes over: the older turn is silenced and its late result is dropped, like Siri does.
J.turnSeq = 0;
async function turn({ text = '', audio_b64 = '', silentEcho = false, wakeOnly = false, clip = null } = {}) {
  let my = null;
  if (text && !wakeOnly && navByVoice(text)) return;
  if (Stage.open && text && !wakeOnly && morphByVoice(text)) return;
  if (!wakeOnly && text && !silentEcho && liveOpen(text)) return;     // typed text / chips go to the live conversation
  if (wakeOnly) { if (J.scanBusy) return; J.scanBusy = true; if (!J.speaking && !J.busy) setState('hearing', '…'); }
  else {
    if (J.busy) return; J.busy = true; J.abort = false; my = ++J.turnSeq;
    stopSpeaking();
    if (text && !silentEcho) captionYou(text);
    setState('thinking', `${J.name} is working…`); $('#capJv').innerHTML = '';
    traceReset(); trace('listen', 'done'); trace('hear', audio_b64 ? 'run' : 'done'); if (!audio_b64) trace('think', 'run');
  }
  try {
    const r = await api('/api/turn', { session: J.sid, text, audio_b64, lang: J.lang, want_audio: true, wake_only: wakeOnly, detect_only: wakeOnly && liveWanted() });
    if (wakeOnly) {
      J.scanBusy = false;
      if (r.intent === 'ignored') { duck(false); if (!J.speaking && !J.busy && !J.capturing && !J.rec) setState('idle', `Say “Hey ${J.name}”`); return; }
      // it was for Mitra: take over from whatever it was doing and run this as an ordinary turn
      my = ++J.turnSeq; J.busy = true; J.abort = false; duck(false);
      stopSpeaking(); cancelCapture(); $('#capJv').innerHTML = ''; traceReset(); trace('listen', 'done');
      if (r.intent !== 'wake') setState('thinking', `${J.name} is working…`);
    }
    if (my !== J.turnSeq) return;                                   // superseded by a newer wake
    if (J.abort) { applyUi(r.ui || []); setState('idle', 'Stopped'); traceReset(); return; }
    const tm = r.timing || {};
    trace('hear', 'done', audio_b64 ? `${tm.stt ?? ''}s` : ''); trace('think', 'done', r.intent ? `${r.intent.replace(/_/g, ' ')} · ${tm.brain ?? ''}s` : '');
    trace('act', 'done', tm.act != null ? `${tm.act}s` : ''); trace('speak', 'run');
    if (r.intent === 'wake' && wakeOnly && liveWanted()) { J.busy = false; captionYou(r.command || ''); Orb.pulse(); liveOpen(r.command || ''); return; }
    if (r.intent === 'wake') { captionYou(''); setState('idle', 'Listening'); Orb.pulse(); chime(); J.busy = false; J.wakeHasCommand = false; startCapture(false, .4); return; }
    if (r.heard && !text) captionYou(r.heard);
    if (r.lang && r.lang !== J.lang) { J.lang = r.lang; localStorage.setItem('jv_lang', J.lang); renderLang(); }
    if (r.profile && r.profile !== J.profile) { Portal.flash(r.profile, { from: J.profile }); J.profile = r.profile; localStorage.setItem('jv_profile', J.profile); renderProfile(); clearPanels(); }
    if (r.officer && r.officer !== J.officer) { J.officer = r.officer; localStorage.setItem('jv_officer', J.officer); renderProfile(); }
    applyUi(r.ui || []);
    J.lastSay = r.say || '';
    const ex = convoAdd({ you: r.heard || text, clip: audio_b64 ? (clip || J.lastClip) : null, say: r.say || '', intent: r.intent, t: Date.now() }); J.lastBufs = [];
    if (r.intent && r.intent !== 'none') $('#stateText').textContent = r.intent.replace(/_/g, ' ') + (r.timing ? ` · ${r.timing.total}s` : '');
    J.busy = false;
    if (r.tts_id && (r.parts || []).length > 1) await speakParts(r);
    else await speak(r.say, r.audio_b64, r.tts);
    if (ex && J.lastBufs.length) { ex.bufs = J.lastBufs.slice(); renderConvo(); }
    Stage.flush();
    if (my !== J.turnSeq) return;
    trace('speak', 'done');
    // continued conversation: listen for a follow-up for a few seconds without the wake word
    // the conversation continues in full duplex (English); the old follow-up listener only where Live is not available
    if (J.wakeOn && !J.abort && r.say) { if (liveWanted()) liveOpen(); else startCapture(true); }
  } catch (e) {
    J.scanBusy = false; duck(false);
    if (my === J.turnSeq) { toast(J.name, e.message || 'something went wrong'); setState('idle', 'Try again'); traceReset(); }
  } finally { if (my != null && my === J.turnSeq) J.busy = false; }
}
// while a wake-word clip is being checked during speech, Mitra lowers its own voice; it comes back if the clip was not for it
function duck(on) {
  if (!J.outGain || J.ducked === on) return; J.ducked = on;
  const t = J.audio.currentTime; J.outGain.gain.cancelScheduledValues(t); J.outGain.gain.setTargetAtTime(on ? .18 : 1, t, .06);
}
$('#send').onclick = () => { const v = $('#text').value.trim(); if (v) { $('#text').value = ''; turn({ text: v }); } };
$('#text').addEventListener('keydown', e => { if (e.key === 'Enter') $('#send').click(); e.stopPropagation(); });

// ------------------------------------------------------------------ speech out
function ensureAudio() {
  if (!J.audio) { J.audio = new (window.AudioContext || window.webkitAudioContext)(); J.outGain = J.audio.createGain(); J.outGain.connect(J.audio.destination); }
  if (J.audio.state === 'suspended') J.audio.resume();
  return J.audio;
}
let outSrc = null, outAn = null, outRaf = null;
async function speak(text, b64, prov) {
  if (!text) { setState('idle', 'Ready'); return; }
  J.speaking = true; setState('speaking', 'Mitra');
  try {
    if (b64) {
      const ac = ensureAudio(); const buf = await ac.decodeAudioData(b64ToArr(b64).buffer); J.lastBufs = [buf];
      captionMitra(text, buf.duration);
      await new Promise(res => {
        outSrc = ac.createBufferSource(); outSrc.buffer = buf; outAn = ac.createAnalyser(); outAn.fftSize = 512;
        outSrc.connect(outAn); outAn.connect(J.outGain); duck(false);
        const data = new Uint8Array(outAn.frequencyBinCount);
        const tick = () => { if (!J.speaking) return; outAn.getByteTimeDomainData(data); let s = 0; for (const v of data) s += Math.abs(v - 128); Orb.setLevel((s / data.length) / 40); outRaf = requestAnimationFrame(tick); };
        Orb.setSource(outAn); tick(); outSrc.onended = res; outSrc.start();
      });
    } else if ('speechSynthesis' in window) {
      captionMitra(text, text.split(/\s+/).length * (J.lang === 'kn' ? .42 : .33));
      await new Promise(res => {
        const u = new SpeechSynthesisUtterance(text); u.lang = J.lang === 'kn' ? 'kn-IN' : 'en-IN'; u.rate = 1.02; u.pitch = 1;
        const voices = speechSynthesis.getVoices();
        const v = voices.find(v => v.lang.toLowerCase().startsWith(J.lang === 'kn' ? 'kn' : 'en-in') && /neural|natural|online/i.test(v.name)) || voices.find(v => v.lang.toLowerCase().startsWith(J.lang === 'kn' ? 'kn' : 'en-in')) || voices.find(v => /en-(gb|us)/i.test(v.lang) && /neural|natural|online/i.test(v.name));
        if (v) u.voice = v;
        let fake = 0; J.levelTimer = setInterval(() => { fake = .25 + Math.random() * .45; Orb.setLevel(fake); }, 90);
        u.onboundary = () => Orb.setLevel(.5 + Math.random() * .4);
        u.onend = u.onerror = () => { clearInterval(J.levelTimer); res(); };
        speechSynthesis.cancel(); speechSynthesis.speak(u);
      });
    } else { captionMitra(text, 3); await new Promise(r => setTimeout(r, 2500)); }
  } catch (e) { captionMitra(text, 3); }
  J.speaking = false; Orb.setSource(null); Orb.setLevel(0); cancelAnimationFrame(outRaf); setState('idle', 'Ready');
}
// sentence-by-sentence playback: part 0 arrives with the turn, the others are already being synthesised
// on the server; each is fetched while the previous one plays, so speech is continuous.
// a reply that came back over HTTP (a document read, the form submitted, a photo) while the live voice is open is read by
// Mitra's live voice, like a notification; the cascade voice (server TTS, browser as the last resort) only when Live is closed
async function sayBack(r) {
  if (!r || !r.say) { setState('idle', 'Ready'); return; }
  if (LV.open && LV.ready) { lvRead(r.say); return; }
  if (liveWanted() && liveOpen()) { lvRead(r.say); return; }          // Standby: the live voice opens and reads it (queued until ready)
  if (r.tts_id && (r.parts || []).length > 1) await speakParts(r); else await speak(r.say, r.audio_b64, r.tts);
}
function liveVoiceOn() { return !!(LV.open && LV.ready); }
async function speakParts(r) {
  const parts = r.parts, ac = ensureAudio(); J.lastBufs = [];
  J.speaking = true; setState('speaking', 'Mitra');
  captionMitra(r.say, r.say.split(/\s+/).length * 0.36);
  const fetchPart = i => i === 0 ? Promise.resolve({ audio_b64: r.audio_b64 }) : api(`/api/tts_part?tid=${r.tts_id}&i=${i}`, null, 'GET').catch(() => ({}));
  let next = fetchPart(0);
  for (let i = 0; i < parts.length && J.speaking; i++) {
    const cur = await next;
    if (i + 1 < parts.length) next = fetchPart(i + 1);
    if (!J.speaking) break;
    try {
      if (cur.audio_b64) {
        const buf = await ac.decodeAudioData(b64ToArr(cur.audio_b64).buffer); J.lastBufs.push(buf);
        await new Promise(res => {
          outSrc = ac.createBufferSource(); outSrc.buffer = buf; outAn = ac.createAnalyser(); outAn.fftSize = 512;
          outSrc.connect(outAn); outAn.connect(J.outGain); duck(false);
          const data = new Uint8Array(outAn.frequencyBinCount);
          const tick = () => { if (!J.speaking) return res(); outAn.getByteTimeDomainData(data); let s = 0; for (const v of data) s += Math.abs(v - 128); Orb.setLevel((s / data.length) / 40); outRaf = requestAnimationFrame(tick); };
          Orb.setSource(outAn); tick(); outSrc.onended = res; outSrc.start();
        });
      } else if ('speechSynthesis' in window) {
        await new Promise(res => { const u = new SpeechSynthesisUtterance(parts[i]); u.lang = 'en-IN'; u.onend = u.onerror = res; speechSynthesis.speak(u); });
      }
    } catch (e) { }
  }
  J.speaking = false; Orb.setSource(null); Orb.setLevel(0); cancelAnimationFrame(outRaf); setState('idle', 'Ready');
}
function stopSpeaking() {
  if ('speechSynthesis' in window) { try { speechSynthesis.pause(); speechSynthesis.cancel(); setTimeout(() => speechSynthesis.cancel(), 120); } catch (e) { } }   // Edge's online voices need the pause + a second cancel
  if (!J.speaking) return; J.speaking = false; clearInterval(J.levelTimer);
  try { outSrc && outSrc.stop(); } catch (e) { }
  Orb.setSource(null); Orb.setLevel(0); setState('idle', 'Ready');
}
// the Stop control: silence Mitra, drop a reply still being prepared, cancel a recording in progress
function stopAll() {
  if (LV.open) { LV.cutTurn = true; lvCut(); captionMitra(''); }
  const was = J.speaking || J.busy || J.capturing;
  stopSpeaking(); J.abort = true; cancelCapture(); duck(false);
  if (was) { captionMitra(''); setState('idle', 'Stopped'); traceReset(); }
}
$('#stop').onclick = stopAll;
function chime(up = true) {
  try {
    const ac = ensureAudio(), o = ac.createOscillator(), g = ac.createGain(), t = ac.currentTime;
    o.type = 'sine'; o.frequency.setValueAtTime(up ? 660 : 880, t); o.frequency.exponentialRampToValueAtTime(up ? 1320 : 520, t + .14);
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(.12, t + .02); g.gain.exponentialRampToValueAtTime(.0001, t + .32);
    o.connect(g); g.connect(ac.destination); o.start(t); o.stop(t + .34);
  } catch (e) { }
}
function b64ToArr(b64) { const bin = atob(b64); const a = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i); return a; }

// ------------------------------------------------------------------ speech in
// The server's speech engine hears when it is available. Without it the browser's own recogniser is
// faster and streams captions, so it is preferred whenever it exists; the server is the last resort.
function sttProvider() {
  const p = J.boot?.providers || {};
  if (p.server_stt) return 'server';
  if (hasRecog()) return 'browser';
  return (J.lang === 'kn' ? p.stt_kn : p.stt) === 'browser' ? 'browser' : 'server';
}
function hasRecog() { return !!(window.SpeechRecognition || window.webkitSpeechRecognition); }
async function initMic() {
  if (J.mic) return true;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    const ac = ensureAudio(); J.inRate = ac.sampleRate; const src = ac.createMediaStreamSource(stream);
    J.analyser = ac.createAnalyser(); J.analyser.fftSize = 512; J.analyser.smoothingTimeConstant = .6; src.connect(J.analyser);
    J.proc = ac.createScriptProcessor(4096, 1, 1); src.connect(J.proc);
    const mute = ac.createGain(); mute.gain.value = 0; J.proc.connect(mute); mute.connect(ac.destination);
    J.proc.onaudioprocess = e => {
      const buf = new Float32Array(e.inputBuffer.getChannelData(0));
      // rolling 4 s pre-roll, so "Hey Mitra, read my inbox" said in one breath is captured whole
      J.ring.push(buf); J.ringLen += buf.length;
      while (J.ringLen > J.inRate * 4 && J.ring.length > 1) J.ringLen -= J.ring.shift().length;
      if (J.rec) J.chunks.push(buf);
      if (LV.open && !J.muted) lvSend(buf);
    };
    J.mic = stream; return true;
  } catch (e) { toast('Microphone', 'Not available; type instead, or allow the microphone and reload.'); return false; }
}
function micLevel() {
  if (!J.analyser) return 0; const d = J._td || (J._td = new Uint8Array(J.analyser.fftSize));
  J.analyser.getByteTimeDomainData(d); let s = 0; for (const v of d) s += (v - 128) * (v - 128); return Math.sqrt(s / d.length) / 128;
}

// ---- push-to-talk (hold the mic button or Space)
function startRec(preSec = 0) {
  if (LV.open) return;                     // already heard through the live stream
  if (SC.on) { SC.on = false; SC.loudMs = 0; J.rec = false; J.chunks = []; }  // push-to-talk beats the scanner
  if (J.rec || J.busy) return; stopSpeaking(); cancelCapture();
  if (sttProvider() === 'browser' && hasRecog()) { recogOnce(); return; }
  if (!J.mic) return;
  J.chunks = preSec && J.inRate ? J.ring.slice(-Math.ceil(J.inRate * preSec / 4096)) : []; J.rec = true; $('#mic').classList.add('rec'); setState('listening', 'Listening…'); Orb.setSource(J.analyser); traceReset(); trace('listen', 'run');
}
async function stopRec() {
  if (LV.open) { J.rec = false; return; }
  if (!J.rec) return; J.rec = false; $('#mic').classList.remove('rec'); Orb.setSource(null);
  const n = J.chunks.reduce((a, c) => a + c.length, 0);
  if (n / J.inRate < 0.5) { setState('idle', 'Too short'); traceReset(); return; }
  const b64 = encodeWav(J.chunks, J.inRate, 16000); J.lastClip = clipBars(J.chunks, J.inRate); J.chunks = [];
  await turn({ audio_b64: b64, clip: J.lastClip });
}
function encodeWav(chunks, inRate, outRate) {
  let n = 0; for (const c of chunks) n += c.length; const all = new Float32Array(n); let o = 0; for (const c of chunks) { all.set(c, o); o += c.length; }
  const ratio = inRate / outRate, len = Math.floor(n / ratio), out = new Int16Array(len);
  for (let i = 0; i < len; i++) { const s = Math.floor(i * ratio), e = Math.min(n, Math.floor((i + 1) * ratio)); let sum = 0; for (let k = s; k < e; k++) sum += all[k]; const v = Math.max(-1, Math.min(1, sum / Math.max(1, e - s))); out[i] = v < 0 ? v * 32768 : v * 32767; }
  const buf = new ArrayBuffer(44 + out.length * 2), dv = new DataView(buf);
  const w = (p, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(p + i, s.charCodeAt(i)); };
  w(0, 'RIFF'); dv.setUint32(4, 36 + out.length * 2, true); w(8, 'WAVE'); w(12, 'fmt '); dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true);
  dv.setUint32(24, outRate, true); dv.setUint32(28, outRate * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true); w(36, 'data'); dv.setUint32(40, out.length * 2, true);
  new Int16Array(buf, 44).set(out);
  let bin = ''; const u8 = new Uint8Array(buf); for (let i = 0; i < u8.length; i += 0x8000) bin += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
  return btoa(bin);
}
function makeRecog(continuous) {
  const R = window.SpeechRecognition || window.webkitSpeechRecognition; const r = new R();
  r.lang = J.lang === 'kn' ? 'kn-IN' : 'en-IN'; r.interimResults = true; r.continuous = continuous; r.maxAlternatives = 3; return r;
}
function recogOnce() {
  const r = makeRecog(false); let final = '';
  setState('listening', 'Listening…'); $('#mic').classList.add('rec');
  r.onresult = e => { let t = ''; for (const res of e.results) { t += res[0].transcript; if (res.isFinal) final = t; } captionYou(t); };
  r.onend = () => { $('#mic').classList.remove('rec'); if (final.trim()) turn({ text: final.trim() }); else setState('idle', 'Did not catch that'); };
  r.onerror = () => { $('#mic').classList.remove('rec'); setState('idle', 'Mic error'); };
  r.start();
}

// ---- capture: record one utterance, end it on silence, send the audio to the server.
// After a wake word it keeps the pre-roll (the wake phrase and anything said with it); after Mitra answers it
// opens a short follow-up window so the conversation can continue without repeating the wake word.
function startCapture(followUp, preSec = 2.5) {
  if (!J.mic || J.busy || J.speaking || J.capturing || J.muted || LV.open) return;
  SC.on = false; SC.loudMs = 0;                                        // the scanner hands over to the capture
  J.capturing = true; document.body.classList.add('capturing');
  const pre = followUp ? [] : J.ring.slice(-Math.ceil(J.inRate * preSec / 4096));
  J.chunks = pre.slice(); J.rec = true; Orb.setSource(J.analyser);
  if (!followUp) { setState('listening', 'Listening…'); traceReset(); trace('listen', 'run'); }
  const t0 = performance.now(); let spoke = !followUp && J.wakeHasCommand, lastLoud = performance.now(), noise = .015, spokeMs = 0;
  J._cap = setInterval(() => {
    if (!J.capturing) return;
    const lv = micLevel(), now = performance.now(); levelPush(lv);
    if (lv < noise * 1.6) noise = noise * .97 + lv * .03;              // adapt to the room
    const loud = lv > Math.max(.035, noise * 3.2);
    if (loud) { lastLoud = now; spokeMs += 50; if (!spoke && now - t0 > 120) { spoke = true; if (followUp) { setState('listening', 'Listening…'); traceReset(); trace('listen', 'run'); } } }
    const wait = followUp ? 6000 : 8000;
    if (!spoke && now - t0 > wait) { cancelCapture(); if (!followUp) setState('idle', `Say “Hey ${J.name}”`); return; }
    // end of the sentence: a real pause, not an "uh" or a breath. The pause allowed grows with how much was said.
    const pause = spokeMs < 1500 ? 1300 : spokeMs < 5000 ? 1600 : 1900;
    if (spoke && now - lastLoud > pause) { finishCapture(); return; }
    if (now - t0 > 25000) finishCapture();
  }, 50);
}
function finishCapture() {
  clearInterval(J._cap); J.capturing = false; J.rec = false; document.body.classList.remove('capturing'); Orb.setSource(null);
  const b64 = encodeWav(J.chunks, J.inRate, 16000); J.lastClip = clipBars(J.chunks, J.inRate); J.chunks = [];
  turn({ audio_b64: b64, clip: J.lastClip });
}
function cancelCapture() {
  if (!J.capturing) return; clearInterval(J._cap); J.capturing = false; J.rec = false; J.chunks = [];
  document.body.classList.remove('capturing'); Orb.setSource(null); if (!J.busy && !J.speaking) setState('idle', 'Ready');
}

// ---- hands-free scanner: the reliable wake path. Whenever someone speaks while Mitra is idle, the utterance
// is cut on silence and sent to the server with wake_only; the server transcribes it and the server acts only if it
// began with "Hey Mitra" (the command said in the same breath is carried out at once). Room talk is ignored.
// This does not depend on the browser's recogniser, which is blocked on many networks (VPNs, proxies).
// The scanner runs in EVERY state except while another recording already has the microphone (push-to-talk,
// or the follow-up capture that opens after a reply): idle, while Mitra is thinking, while it is talking, after
// Stop. While Mitra talks the bar is higher (so its own voice through the speakers, a cough or people nearby do
// not trip it) and its voice is ducked while the clip is checked; only a clip that begins with the wake word
// interrupts it, anything else lets it carry on.
const SC = { on: false, t0: 0, lastLoud: 0, noise: .012, loudMs: 0, duck: false };
const SCAN_SILENCE_MS = 1100, SCAN_MAX_MS = 12000;
function startScan() { if (J._scan) return; J._scan = setInterval(scanTick, 40); }
function stopScan() { clearInterval(J._scan); J._scan = null; scanDrop(); }
function scanDrop() {
  if (!SC.on) return; SC.on = false; SC.loudMs = 0; J.rec = false; J.chunks = []; duck(false);
  document.body.classList.remove('scanning');
  if (!J.speaking) Orb.setSource(null);
  if (!J.busy && !J.speaking && !J.capturing) setState('idle', `Say “Hey ${J.name}”`);
}
function scanTick() {
  if (!J.wakeOn || !J.mic || J.teaching || J.muted) return;
  if (LV.open || J.capturing || J.scanBusy || J.wakeLatched || (J.rec && !SC.on)) { scanDrop(); return; }
  const lv = micLevel(), now = performance.now(), talking = J.speaking;
  levelPush(lv);
  if (!talking && lv < SC.noise * 1.6) SC.noise = SC.noise * .97 + lv * .03;      // adapt to the room (never to its own voice)
  const loud = lv > (talking ? Math.max(.07, SC.noise * 4.5) : Math.max(.03, SC.noise * 3.2));
  if (!SC.on) {
    if (!loud) { SC.loudMs = 0; return; }
    SC.loudMs += 40; if (SC.loudMs < (talking ? 280 : 160)) return;       // a click or a cough is not speech
    SC.on = true; SC.t0 = now; SC.lastLoud = now; document.body.classList.add('scanning');
    J.chunks = J.ring.slice(-Math.ceil(J.inRate * 1.0 / 4096)); J.rec = true;
    if (talking) duck(true); else { Orb.setSource(J.analyser); if (!J.busy) setState('hearing', '…'); }
    return;
  }
  if (loud) SC.lastLoud = now;
  const dur = now - SC.t0;
  if ((!loud && now - SC.lastLoud > SCAN_SILENCE_MS) || dur > SCAN_MAX_MS) {
    SC.on = false; SC.loudMs = 0; J.rec = false; document.body.classList.remove('scanning');
    if (!J.speaking) Orb.setSource(null);
    if (dur < 350) { J.chunks = []; duck(false); if (!J.busy && !J.speaking) setState('idle', `Say “Hey ${J.name}”`); return; }
    const b64 = encodeWav(J.chunks, J.inRate, 16000); J.lastClip = clipBars(J.chunks, J.inRate); J.chunks = [];
    turn({ audio_b64: b64, wakeOnly: true, clip: J.lastClip });
  }
}
// a small waveform of a recorded clip (40 bars) kept for the conversation strip, plus the audio itself
function clipBars(chunks, rate) {
  let n = 0; for (const c of chunks) n += c.length; const bars = 40, per = Math.max(1, Math.floor(n / bars)), out = [];
  let i = 0, ci = 0, off = 0;
  for (let b = 0; b < bars; b++) { let s = 0, k = 0; while (k < per && ci < chunks.length) { const v = chunks[ci][off]; s += v * v; k++; off++; if (off >= chunks[ci].length) { ci++; off = 0; } } out.push(Math.sqrt(s / Math.max(1, k))); }
  const mx = Math.max(.02, ...out); return { bars: out.map(v => v / mx), secs: n / rate, b64: encodeWav(chunks, rate, 16000) };
}
// live level history for the waveform strip (last ~3 s)
J.lv = new Float32Array(72); J.lvi = 0;
function levelPush(v) { J.lv[J.lvi] = v; J.lvi = (J.lvi + 1) % J.lv.length; }

// ---- wake word ("Hey Mitra"), fast path: the browser's recogniser spots the wake phrase and "stop" instantly
// when it works; the request itself is recorded and transcribed by the server. If the recogniser cannot reach its
// service it is switched off and the scanner above carries the wake word alone.
function wakeRegex() {
  const names = J.wakeWords.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  const learned = (J.boot?.learned || []).map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  return new RegExp(`\\b(?:(hey|hi|hello|ok|okay)\\s+)?(${[names, ...learned, 'mitra', 'mithra', 'meetra', 'mitrah'].join('|')})\\b`, 'i');
}
function startWake() {
  startScan();
  if (!hasRecog() || J.recogDead || J.muted) return;
  if (J.wakeRec) return;
  const r = makeRecog(true); r.lang = 'en-IN'; J.wakeRec = r; const rx = wakeRegex();
  r.onresult = e => {
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const res = e.results[i];
      const alts = Array.from(res).map(a => a.transcript.toLowerCase());
      const txt = alts[0] || '';
      if ((J.speaking || J.busy) && alts.some(a => /\b(stop|cancel|enough|quiet|shut up|be quiet|never mind)\b/.test(a))) { stopAll(); continue; }
      const hit = alts.map(a => a.match(rx)).find(Boolean);
      if (!hit) continue;
      const explicit = !!hit[1];                         // "hey/ok mitra" (required while it is talking: its own voice says "Mitra")
      if ((J.speaking || J.busy) && !explicit) continue;
      if (J.capturing || J.wakeLatched) continue;
      J.recogOk = true;
      J.wakeLatched = true; setTimeout(() => { J.wakeLatched = false; }, 2500);
      const after = txt.slice(txt.search(rx)).replace(rx, '').trim();
      J.wakeHasCommand = after.split(/\s+/).filter(Boolean).length >= 1;
      stopSpeaking(); if (J.busy) J.abort = true;
      Orb.pulse(); chime(true);
      startCapture(false);
    }
  };
  r.onend = () => { J.wakeRec = null; if (J.wakeOn && !J.recogDead) setTimeout(startWake, J.recogErrs > 2 ? 1500 : 300); };
  r.onerror = e => {
    if (['network', 'audio-capture', 'language-not-supported', 'service-not-allowed', 'not-allowed'].includes(e.error)) {
      // the recogniser cannot work here (its cloud service is unreachable, or it is denied): rely on the scanner
      J.recogDead = true; console.warn('browser recogniser off:', e.error, '- the server scanner carries the wake word');
    } else if (e.error !== 'no-speech' && e.error !== 'aborted') { J.recogErrs = (J.recogErrs || 0) + 1; }
  };
  try { r.start(); } catch (e) { J.wakeRec = null; }
}
function stopWake() { J.wakeOn = false; stopScan(); if (J.wakeRec) { try { J.wakeRec.onend = null; J.wakeRec.abort(); } catch (e) { } J.wakeRec = null; } }
function toggleWake() {
  if (J.wakeOn) { stopWake(); $('#handsfree').classList.remove('on'); toast('Wake word off', 'Hold the mic or Space to talk.'); }
  else { J.wakeOn = true; $('#handsfree').classList.add('on'); startWake(); toast('Wake word on', `Say “Hey ${J.name}” any time.`); }
}
$('#handsfree').onclick = toggleWake;
// tap the orb: wake Mitra (no need to say its name), or silence it while it is talking or working
Orb.onTap = () => {
  if (LV.open) { if (LV.playing) { LV.cutTurn = true; lvCut(); } else { chime(false); liveClose('tap'); } return; }
  if (J.speaking || J.busy || J.capturing) { stopAll(); return; }
  if (J.muted && J.mic) setMuted(false, { quiet: true });
  if (liveWanted()) { liveOpen(); return; }
  if (!J.mic) { $('#text').focus(); return; }
  if (J.muted) setMuted(false, { quiet: true });
  if (SC.on) { SC.on = false; SC.loudMs = 0; J.rec = false; J.chunks = []; }
  stopSpeaking(); chime(true); J.wakeHasCommand = false; startCapture(false, .3);
};
const mic = $('#mic');
// Tap the mic = mute / unmute. Hold it = talk (also while muted: the mic opens only for the hold).
// The hold starts after 220 ms; the ring buffer's last 0.3 s is kept so the first word is not clipped.
const MIC = { down: 0, held: false, timer: null };
mic.addEventListener('pointerdown', e => {
  e.preventDefault(); MIC.down = performance.now(); MIC.held = false; holdOpen(true);
  MIC.timer = setTimeout(() => { MIC.held = true; mic.classList.add('hold'); startRec(.3); }, 220);
});
function micUp(toggle) {
  if (!MIC.down) return; clearTimeout(MIC.timer); MIC.down = 0; mic.classList.remove('hold');
  if (MIC.held) { MIC.held = false; stopRec(); holdOpen(false); return; }
  holdOpen(false);
  if (toggle) setMuted(!J.muted);
}
mic.addEventListener('pointerup', () => micUp(true));
mic.addEventListener('pointerleave', () => micUp(false));
mic.addEventListener('pointercancel', () => micUp(false));
// ---- mute: the microphone track itself is switched off, so nothing reaches the wake-word scanner, the
// talk-over check or the follow-up listening. Mitra can still speak; only its ears are closed.
J.muted = false; J.holdOpen = false;
function micTracks() { return J.mic && J.mic.getAudioTracks ? J.mic.getAudioTracks() : []; }
function applyTrack() { const on = !J.muted || J.holdOpen; micTracks().forEach(t => { t.enabled = on; }); }
function holdOpen(on) { J.holdOpen = !!on; applyTrack(); }
// mute is the microphone only: the track is switched off, the live session stays open, an answer in progress keeps
// playing and typed text still goes to Live. Only Stop cuts her off.
const MUTED_TEXT = 'Muted · the answer still plays';
function setMuted(on, { quiet = false } = {}) {
  J.muted = !!on; applyTrack();
  setTimeout(modePill, 0);
  document.body.classList.toggle('muted', J.muted);
  mic.classList.toggle('muted', J.muted);
  mic.dataset.tip = J.muted ? 'Muted · tap to unmute · hold to talk anyway' : 'Tap to mute · hold to talk (or hold Space)';
  $('#wakeLabel').textContent = J.muted ? 'Muted' : `“Hey ${J.name}”`;
  if (J.muted) {
    cancelCapture(); scanDrop();
    if (J.wakeRec) { try { J.wakeRec.onend = null; J.wakeRec.abort(); } catch (e) { } J.wakeRec = null; }
    if (!J.speaking && !J.busy && !LV.playing) setState('muted', LV.open ? MUTED_TEXT : 'Tap the mic to unmute');
  } else {
    if (J.wakeOn && !LV.open) startWake();
    if (!J.speaking && !J.busy && !LV.playing) setState(LV.open ? 'listening' : 'idle', LV.open ? 'Listening…' : `Say “Hey ${J.name}”`);
  }
  if (!quiet) { chime(!J.muted); toast(J.muted ? 'Microphone muted' : 'Listening again', J.muted ? `${J.name} cannot hear you until you unmute; her answer still plays. Hold the mic to talk anyway.` : `Say “Hey ${J.name}” any time.`); }
}
window.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') { if (e.key === 'Escape') stopAll(); return; }
  if (e.code === 'Space' && !e.repeat) { e.preventDefault(); holdOpen(true); startRec(.3); }
  if ((e.key === 'm' || e.key === 'M') && !e.repeat) setMuted(!J.muted);
  if (e.key === 'Escape') { stopAll(); $('#prof').classList.remove('open'); }
  if (e.key === 'h' || e.key === 'H') toggleWake();
  if (e.key === '/') { e.preventDefault(); $('#text').focus(); }
});
window.addEventListener('keyup', e => { if (e.code === 'Space' && e.target.tagName !== 'INPUT') { e.preventDefault(); stopRec(); holdOpen(false); } });

// ------------------------------------------------------------------ panels
const panels = { left: new Map(), right: new Map() };
function clearPanels() {
  Stage.exit(true); $('#left').innerHTML = ''; $('#right').innerHTML = ''; panels.left.clear(); panels.right.clear(); J.stages = {}; for (const c of Object.values(J.charts)) c.destroy?.(); J.charts = {}; }
function panel(id, side, html, { top = false, cls = '' } = {}) {
  const host = $('#' + side); let el = panels[side].get(id);
  if (!el) { el = document.createElement('div'); el.className = 'card ' + cls; el.dataset.id = id; panels[side].set(id, el); top ? host.prepend(el) : host.appendChild(el); }
  else { el.className = 'card ' + cls; }
  el.innerHTML = html; return el;
}
function dropPanel(id, side) { const el = panels[side].get(id); if (el) { panels[side].delete(id); el.classList.add('out'); setTimeout(() => el.remove(), 320); } }
function leftPill(b) { return b.left < 0 ? `<span class="pill bad">${esc(b.leftText)}</span>` : b.left <= 1 ? `<span class="pill warn">${esc(b.leftText)}</span>` : `<span class="pill ok">${esc(b.leftText)}</span>`; }

const STAGE_DOWN = new Set(['case', 'inbox', 'kpi', 'filter', 'officers', 'pack', 'e4', 'request', 'atr', 'mycases']);
function applyUi(ops, keepStage = false) {
  // an answer that needs the dashboard (a case, the inbox, a list) brings it back; charts keep the stage
  if (Stage.open && !keepStage && !ops.some(o => o.op === 'viz') && ops.some(o => STAGE_DOWN.has(o.op))) Stage.exit();
  for (const op of ops) {
    try { (UI[op.op] || (() => { }))(op); } catch (e) { console.error(op.op, e); }
  }
}
// a small clock ring for a case row: how much of its time is used, red once overdue
function ring(b) {
  const total = b.legal ? (b.dueDays || 21) : ({ L1: 7, L2: 5, L3: 3 }[b.level] || 7);
  const left = typeof b.left === 'number' ? b.left : total, pct = Math.max(0, Math.min(1, (total - left) / total));
  const r = 8, c = 2 * Math.PI * r, cls = left < 0 ? 'bad' : left <= 1 ? 'warn' : 'ok';
  return `<svg class="ring ${cls}" viewBox="0 0 20 20"><circle cx="10" cy="10" r="${r}"/><circle cx="10" cy="10" r="${r}" style="stroke-dasharray:${c};stroke-dashoffset:${c * (1 - (left < 0 ? 1 : pct))}"/></svg>`;
}
// numbers that count up to their new value instead of jumping
function countUp(el, to) {
  const from = Number(el.dataset.v || 0); el.dataset.v = to; if (from === to) { el.textContent = to; return; }
  const t0 = performance.now(), dur = 700;
  const step = () => { const k = Math.min(1, (performance.now() - t0) / dur), e = 1 - Math.pow(1 - k, 3); el.textContent = Math.round(from + (to - from) * e); if (k < 1) requestAnimationFrame(step); };
  step();
}
const UI = {
  upload(op) {                       // "I want to upload a letter": the request card with its drop zone, lit; the person taps it
    if (J.profile !== 'citizen') return;
    if (!panels.left.get('request')) UI.request({ draft: {}, flow: 'menu', options: [] });
    const dz = $('#dropz'); if (!dz) return;
    dz.classList.remove('lit'); void dz.offsetWidth; dz.classList.add('lit');
    setTimeout(() => dz.scrollIntoView({ behavior: 'smooth', block: 'center' }), 350);
    try { dz.focus({ preventScroll: true }); } catch (e) { }
    setTimeout(() => dz.classList.remove('lit'), 6000);
  },
  routed(op) { renderRouted(op); Orb.burst(); const o = op.officer || {}; flyLabel(`${op.caseId} → ${o.short || o.name || 'officer'}`); },
  viz(op) { Stage.show(op); },
  nav(op) {
    if (op.target === 'chart') { if (Stage.last) Stage.show(Stage.last, { replay: false }); return; }
    const was = Stage.open; Stage.exit();
    if (op.target === 'inbox') { setTimeout(() => Stage.focusCard('inbox'), was ? 700 : 0); return; }
    document.body.classList.remove('nav-home'); void document.body.offsetWidth; document.body.classList.add('nav-home');
    setTimeout(() => document.body.classList.remove('nav-home'), 1800);
  },
  morph(op) { if (Stage.open || Stage.last) { if (!Stage.open && Stage.last) Stage.show(Stage.last, { replay: false }); Stage.morph(op.kind); } },
  profile(op) { const sc = $('#scopeChip'); if (sc && op.profile !== 'cs') sc.classList.remove('on'); if (op.profile !== J.profile && !Portal.busy) Portal.flash(op.profile, { from: J.profile }); J.profile = op.profile; localStorage.setItem('jv_profile', J.profile); renderProfile(); clearPanels(); },
  login(op) { J.officer = op.officer; localStorage.setItem('jv_officer', J.officer); renderProfile(); toast('Logged in', op.officerName); },
  lang(op) { J.lang = op.lang; localStorage.setItem('jv_lang', J.lang); renderLang(); },
  confirm(op) { confirmBar(op.clear ? null : op.question); },
  view_officer(op) { setTimeout(() => viewAsOfficer(op.officer, op.case_id), 1100); },     // after the spoken line
  view(op) { setTimeout(() => switchView(op.view, op.profile || J.profile, op.officer || J.officer), 1300); },   // after the spoken line
  forget() { J.convo = []; renderConvo(); $('#capYou').textContent = ''; $('#capJv').innerHTML = ''; confirmBar(null); toast('Forgotten', 'This conversation was deleted from this screen.'); },
  theme(op) { Theme.set(op.theme); },
  clock(op) { $('#clock').textContent = fmtDate(op.now); },
  toast(op) { toast(op.h, op.m); },
  stop() { stopSpeaking(); },
  reload() { setTimeout(() => session(), 300); },
  hint() { },
  facts() { },
  notes(op) {
    const n = op.notes || [];
    panel('notes', 'right', `<h3>Voice notes <small>${n.length ? n.length + ' for you' : 'none yet'}</small></h3>` +
      (n.length ? n.map(x => `<div class="note ${x.heard ? '' : 'new'}"><button class="play ${x.audio ? '' : 'off'}" data-n="${x.id}" ${x.audio ? '' : 'disabled'}>▶</button><div><div class="fr">${esc(x.from_role === 'cs' ? 'Chief Secretary' : x.from_role === 'officer' ? (x.from_officer || 'Officer') : 'Citizen')}${x.case_id ? ' · ' + esc(x.case_id) : ''}</div><div class="tx">${esc(x.transcript)}</div></div><div class="t">${esc(x.t.slice(11, 16))}</div></div>`).join('')
        : `<div class="empty">Say "send a voice note to the officer" (citizen), "tell the Chief Secretary …" (officer) or "send the Tahsildar a note …" (CS).</div>`));
    document.querySelectorAll('.note .play[data-n]').forEach(b => b.onclick = () => playNote(b.dataset.n));
  },
  // ---------------- citizen: Mitra is the input channel
  stages(op) {
    J.stages = {};
    for (const s of op.items || []) J.stages[s.i] = { state: s.state || 'done', note: s.note };
    if (!(op.items || []).length) { dropPanel('routed', 'right'); }
    renderPipe();
  },
  request(op) {
    const d = op.draft || {}, flow = op.flow || 'menu', opts = op.options || [];
    let body = '';
    if (d.service) {
      const p = d.place, pv = d.preview, o = pv && pv.officer;
      body += `<div class="big">${esc(d.service)}</div><div class="path">${esc(d.dept || '')}${d.grievance ? ' › ' + esc(d.grievance) : ''}${d.vulnerable ? ' · <span class="pill vio">♥ priority</span>' : ''}</div>`;
      if (d.conf != null && d.conf !== '') body += `<div class="conf"><span>AI confidence</span><span class="m"><i style="width:${d.conf}%"></i></span><b>${d.conf}%</b> <span>· ${esc(d.engine || '')}</span></div>`;
      if (d.masked) body += `<div class="quote">${esc(d.masked)}</div>`;
      if (p) body += `<div class="loc"><span class="pin">📍</span><div>${esc(p.village && p.village !== p.gp ? p.village + ' village, ' : '')}${esc(p.gp ? p.gp + ' GP, ' : '')}${esc(p.taluk)} taluk<div class="meta" style="font-size:11px;color:var(--mute2)">${esc(p.how || '')}</div></div></div>`;
      else if (flow === 'ask_gp') body += `<div class="waiting">Which Gram Panchayat? Say it, or pick below.</div>`;
      else if (flow === 'ask_place') body += `<div class="waiting">Which village or taluk? Say it, share your location, or pick a taluk.</div>`;
      if (d.duplicate) body += `<div class="ev">A similar open request exists (<b>${esc(d.duplicate)}</b>); yours will be linked to it.</div>`;
      if (o) body += `<div class="who"><div class="av">${esc((o.short || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase())}</div><div><div class="n">${esc(o.name)}</div><div class="c">${esc((pv.chain || []).map(c => c.short).join(' → '))} · ${pv.days} days</div></div></div>`;
      if (flow === 'confirm') body += `<div class="waiting">Say <b>“yes, file it”</b> to confirm, or <b>“change”</b>.</div>`;
    } else if (flow === 'apply_name' || flow === 'apply_village' || flow === 'apply_confirm' || flow === 'apply') {
      body += `<div class="big">Sakala service application</div><div class="waiting">${flow === 'apply_name' ? 'Say the applicant’s name.' : flow === 'apply_village' ? 'Say the village.' : flow === 'apply' ? 'Which service?' : 'Say “apply now” to start.'}</div>`;
    } else {
      body += `<div class="big" style="color:var(--mute)">Tell ${esc(J.name)} what is wrong.</div><div class="waiting">Speak in your own words. It reads it, masks personal numbers, finds the category and the exact officer, and files it. A photo of a petition or document is optional.</div>`;
    }
    if (d.doc) body = docReview(d, flow) + body.replace(/<div class="big">[\s\S]*?<\/div><div class="path">[\s\S]*?<\/div>/, '').replace(/<div class="quote">[\s\S]*?<\/div>/, '').replace(/<div class="waiting">Say <b>“yes, file it”<\/b>[\s\S]*?<\/div>/, '');
    if (opts.length && !d.doc) body += `<div class="opts">${opts.map(([l, a]) => `<button data-a="${esc(a)}">${esc(l)}</button>`).join('')}</div>`;
    if (!d.doc) body += `<div class="dropz" id="dropz" tabindex="0"><input type="file" accept="application/pdf,image/*" id="reqFile" capture="environment"><div class="dz-ic"><i></i><svg viewBox="0 0 24 24"><path d="M12 16V4m0 0 4 4m-4-4-4 4" /><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" /></svg></div><div class="dz-t"><b>Upload a written complaint</b><span>PDF or photo · Kannada, English or both · the letter is read into the official form</span></div><span class="dz-k">Browse</span></div>`;
    panel('request', 'left', `<h3>${d.doc ? 'Your written complaint' : 'Your request'} <small><span class="live-pill"><i></i>${esc(J.name)} · ${d.doc ? 'document' : 'voice'}</span></small></h3><div class="req ${d.doc ? 'docmode' : ''}">${body}</div>`, { top: true });
    document.querySelectorAll('#left .req .opts button').forEach(b => b.onclick = () => turn({ text: b.textContent }));
    bindDrop();
    if (d.doc) bindDocReview(d);
  },
  mycases(op) {
    const rows = op.cases || [];
    panel('mycases', 'left', `<h3>My requests <small>${rows.length ? rows.length + ' filed' : 'none yet'}</small></h3>` +
      (rows.length ? `<div class="rows">${rows.slice(0, 8).map(c => { const st = c.status === 'Resolved' ? '<span class="pill ok">Resolved</span>' : c.status === 'Rejected' ? '<span class="pill bad">Rejected · appeal</span>' : c.status === 'Info requested' ? '<span class="pill warn">Officer asked</span>' : c.left < 0 ? `<span class="pill bad">${-c.left}d overdue</span>` : `<span class="pill ok">${c.left}d left</span>`; return `<div class="row" data-id="${esc(c.id)}"><div><div class="id">${esc(c.id)}</div><div class="svc">${esc(c.service)} · ${esc(c.ownerShort)}</div><div class="meta">${esc(c.last || '')}</div></div>${st}</div>`; }).join('')}</div>` : `<div class="empty">Your filed requests appear here with their officer and days left.</div>`));
  },
  updates(op) {
    const ms = op.messages || [];
    let host = panels.right.get('updates');
    const html = ms.map(m => `<div class="upd ${esc(m.kind)}"><div class="ic">${m.kind === 'resolved' ? '✓' : m.kind === 'rejected' ? '✕' : m.kind === 'info' ? '?' : m.kind === 'escalated' ? '⏫' : '●'}</div><div><div class="fr">${esc(m.officer)} · ${esc(m.case_id)}</div><div class="tx">${esc(spokenUpdate(m))}</div><div class="t">${esc((m.t || '').slice(11, 16))}</div></div></div>`).join('');
    if (!host) panel('updates', 'right', `<h3>From the officer <small><span class="live-pill"><i></i>live</span></small></h3><div id="updList">${html}</div>`, { top: true });
    else { const l = $('#updList'); l.insertAdjacentHTML('afterbegin', html); }
  },
  // the officer's resolution: a report the citizen judges with one word (or a tap); shown on the web and in the phone
  resolution(op) {
    const cid = op.case_id || '', ini = (op.officer || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
    panel('resolution', 'right', `<h3>Resolution <small>${esc(cid)}</small></h3>
      <div class="resv" data-cid="${esc(cid)}">
        <div class="ring"><svg viewBox="0 0 64 64"><circle class="trk" cx="32" cy="32" r="28"/><circle class="arc" cx="32" cy="32" r="28"/><path class="tick" d="M20 33l8 8 16-17"/></svg></div>
        <div class="rtx"><div class="who"><span class="av">${ini}</span><div><b>${esc(op.officerFull || op.officer || 'The officer')}</b><small>${esc(op.officer || '')} · marked it resolved</small></div></div>
          ${op.service ? `<div class="svc">${esc(op.service)}</div>` : ''}
          <div class="atr">“${esc(op.atr || 'Action taken report filed')}”</div>
          <div class="q">Was your problem actually solved?</div>
          <div class="yn"><button class="yes" data-say="yes, it is solved">👍 Yes, it’s solved</button><button class="no" data-say="no, it is not solved">👎 No, not solved</button></div>
          <div class="hint">Say it, or tap. A “no” re-opens it and moves it up to the senior officer.</div></div></div>`, { top: true });
    document.querySelectorAll('#right .resv .yn button').forEach(b => b.onclick = () => turn({ text: b.dataset.say }));
    flyLabel(`${cid} · solved?`);
  },
  // the verdict: closed with thanks, or the ladder climbing one rung with a fresh clock
  verdict(op) {
    const cid = op.case_id || '', host = document.querySelector('#right .resv');
    let html;
    if (op.accepted) {
      html = `<div class="resv closed"><div class="ring ok"><svg viewBox="0 0 64 64"><circle class="trk" cx="32" cy="32" r="28"/><circle class="arc" cx="32" cy="32" r="28"/><path class="tick" d="M20 33l8 8 16-17"/></svg></div>
        <div class="rtx"><b class="ttl">Closed · thank you</b><div class="sub">${esc(cid)} is solved. Your confirmation sits on ${esc(op.officer || 'the officer')}’s report.</div></div></div>`;
    } else {
      const chain = op.chain || [];
      const rungs = (op.escalated === false ? [] : [{ lv: op.from_level || '', short: op.from || '', st: 'passed' }])
        .concat(chain.map((c, i) => ({ lv: c.lv, short: c.short, st: i ? 'next' : 'cur' })));
      html = `<div class="resv reopened"><div class="rtx"><b class="ttl">${op.escalated === false ? 'Re-opened · top of the ladder' : 'Re-opened · moved up the ladder'}</b>
        <div class="ladder">${rungs.map((r, i) => `<div class="rung ${r.st}" style="--i:${i}"><span class="lv">${esc(r.lv)}</span><span class="nm">${esc(r.short)}</span>${r.st === 'cur' ? '<span class="now">holds it now</span>' : r.st === 'passed' ? '<span class="now">rejected</span>' : ''}</div>`).join('<i class="up"></i>')}</div>
        <div class="clock"><span class="dot"></span>Clock restarted · <b>${op.days || 7} days</b> for ${esc(op.to_name || op.to || '')}</div>
        <div class="sub">The Chief Secretary can see it. You will hear every update here.</div></div></div>`;
    }
    if (host) host.outerHTML = html; else panel('resolution', 'right', `<h3>Resolution <small>${esc(cid)}</small></h3>${html}`, { top: true });
    if (op.accepted) { Orb.burst(); flyLabel(`${cid} · closed ✓`); } else flyLabel(`${cid} ↑ ${op.to || 're-opened'}`);
  },
  // ---------------- officer
  inbox(op) {
    const rows = op.cases || [];
    panel('inbox', 'left', `<h3>Inbox · ${esc(op.officerName)} <small>${op.total} open</small></h3>` +
      (rows.length ? `<div class="rows">${rows.map(b => `<div class="row ${b.id === J.caseId ? 'sel' : ''}" data-id="${esc(b.id)}">${ring(b)}<div><div class="id">${esc(b.id)} ${b.vulnerable ? '<span class="pill vio">♥ priority</span>' : ''}</div><div class="svc">${esc(b.service)}</div><div class="meta">${esc(b.gp || b.taluk)} · ${esc(b.level)} · ${esc(b.src || '')}</div></div>${leftPill(b)}</div>`).join('')}</div>` : `<div class="empty">Inbox clear 🎉</div>`), { top: true });
    document.querySelectorAll('#left .row[data-id]').forEach(r => r.onclick = () => turn({ text: `open ${r.dataset.id}` }));
    { const j = panels.left.get('justin'); if (j) $('#left').prepend(j); } markInboxNew();
  },
  case(op) {
    const b = op.case; J.caseId = b.id;
    document.querySelectorAll('.row[data-id]').forEach(r => r.classList.toggle('sel', r.dataset.id === b.id));
    const total = b.legal ? (b.sakala?.dueDays || 7) : ({ L1: 7, L2: 5, L3: 3 }[b.level] || 7);
    const used = Math.max(0, total - b.left); const pct = Math.min(100, Math.round(used / total * 100));
    const au = b.audit || {}, rt = au.route || {}, pl = au.place || {};
    const isOfficer = J.profile === 'officer';
    panel('case', 'right', `
      <div class="case">
        <div class="top-l"><div class="cid">${esc(b.id)}</div><div class="badges"><span class="pill n">${esc(b.status)}</span><span class="pill n">${esc(b.level)} · ${esc(b.ownerShort)}</span>${b.vulnerable ? '<span class="pill vio">♥ vulnerable</span>' : ''}${b.legal ? '<span class="pill warn">Sakala · legal clock</span>' : ''}</div></div>
        <div class="svc">${esc(b.service)}</div>
        <div class="path">${esc(b.dept || '')} › ${esc(b.grievance || '')} · ${esc(b.gp ? b.gp + ' GP, ' : '')}${esc(b.taluk || '')} · via ${esc(b.src || '')}</div>
        <div class="quote">${esc(b.masked)}</div>
        <div class="clockbar ${b.left < 0 ? 'bad' : ''}"><i style="width:${pct}%"></i></div>
        <div class="kv"><dt>Time</dt><dd>${esc(b.leftText)} of ${total} days${b.legal ? ' (Sakala Act)' : ''}</dd>
        ${b.conf ? `<dt>AI confidence</dt><dd>${Math.round(b.conf * 100)}%${au.threshold ? ` · threshold ${Math.round(au.threshold * 100)}%` : ''}</dd>` : ''}
        ${b.why ? `<dt>Reason</dt><dd>${esc(b.why)}</dd>` : ''}
        ${rt.role ? `<dt>Officer rule</dt><dd>${esc(rt.role)} · ${Math.round((rt.share || 0) * 100)}% of ${rt.support || 0} real cases${rt.fallback ? ' · fallback' : ''}</dd>` : ''}
        ${pl.how ? `<dt>Location</dt><dd>${esc(pl.village || '')} → ${esc(pl.gp || '')} · ${esc(pl.how)}</dd>` : ''}
        ${b.sakala ? `<dt>Sakala</dt><dd>DO ${esc(b.sakala.DO)} · CO ${esc(b.sakala.CO)} · AA ${esc(b.sakala.AA)}</dd>` : ''}</div>
        ${b.atr ? `<div class="ev"><b>ATR</b> · ${esc(b.atr)} <span class="pill ${b.atrScore >= 4 ? 'ok' : 'warn'}">${b.atrScore}/5</span></div>` : ''}
        <ul class="timeline">${(b.history || []).slice(-5).map(h => `<li><div><b>${esc(h.what)}</b> · ${esc(h.who)}${h.note ? `<br>${esc(h.note)}` : ''}</div></li>`).join('')}</ul>
        ${isOfficer ? `<div class="actions"><button class="primary" data-say="accept">Accept</button><button data-say="draft the report">AI draft ATR</button><button data-say="ask the citizen which street the problem is on">Ask citizen</button><button data-say="return it, not my jurisdiction">Return</button><button class="danger" data-say="reject it as a duplicate of an existing request">Reject</button><button data-say="next case">Next</button></div>`
        : `<div class="actions"><button class="primary" data-say="nudge this officer">Nudge</button><button data-say="read the details">Read evidence</button></div>`}
      </div>`, { top: true });
    document.querySelectorAll('#right .actions button[data-say]').forEach(b => b.onclick = () => turn({ text: b.dataset.say }));
  },
  atr(op) {
    const s = op.score;
    panel('atr', 'right', `<h3>Action Taken Report <small>${esc(op.engine || '')}</small></h3><div class="atr"><textarea id="atrText">${esc(op.text || '')}</textarea>
      ${s != null ? `<div class="score"><div class="n ${s >= 4 ? 'good' : 'bad'}">${s}/5</div><div class="meter"><i style="width:${s * 20}%"></i></div><div class="r">${esc(op.reason || '')}</div></div>` : ''}
      <div class="actions"><button class="primary" id="atrFile">Resolve with this ATR</button></div></div>`, { top: true });
    $('#atrFile').onclick = () => { const t = $('#atrText').value.trim(); if (t) turn({ text: 'resolve: ' + t }); };
  },
  // ---------------- chief secretary
  kpi(op) {
    if (op.board && op.board.kpis) return UI.board(op);
    const dept = Object.entries(op.byDept).sort((a, b) => b[1] - a[1]); const max = Math.max(1, ...dept.map(d => d[1]));
    const names = { REV: 'Revenue', RDPR: 'RDPR', FOOD: 'Food & Civil Supplies' };
    panel('kpi', 'left', `<h3>Command view <small>Karnataka · 31 districts · ${fmtDate(op.now)}</small></h3>
      <div class="kpis"><div class="kpi hero" data-say="show all cases"><div class="v">${op.pending}</div><div class="l">Pending now</div></div>
      <div class="kpi bad" data-say="show the overdue cases"><div class="v">${op.overdue}</div><div class="l">Overdue</div></div>
      <div class="kpi vio" data-say="show the vulnerable cases"><div class="v">${op.vulnerable}</div><div class="l">Vulnerable waiting</div></div>
      <div class="kpi saf" data-say="how many cases were auto-escalated"><div class="v">${op.escalated}</div><div class="l">Auto-escalated</div></div></div>
      <div class="bars" style="margin-top:12px">${['L1', 'L2', 'L3'].map(l => `<div class="bar"><span class="t">${l} · ${l === 'L1' ? 'field officer' : l === 'L2' ? 'EO / AC / DD' : 'DC / ZP CEO'}</span><span class="b"><i style="width:${Math.round(op.byLevel[l] / Math.max(1, op.pending) * 100)}%"></i></span><span class="n">${op.byLevel[l]}</span></div>`).join('')}</div>
      <div class="bars" style="margin-top:10px">${dept.map(([d, n]) => `<div class="bar"><span class="t">${esc(names[d] || d)}</span><span class="b"><i style="width:${Math.round(n / max * 100)}%"></i></span><span class="n">${n}</span></div>`).join('')}</div>
      <div class="pstrip" id="pulse"></div>`, { top: true });
    document.querySelectorAll('#left .kpi[data-say]').forEach(k => k.onclick = () => turn({ text: k.dataset.say }));
    document.querySelectorAll('#left .kpi .v').forEach(v => { const to = Number(v.textContent); const prev = J.kpiPrev?.[v.parentElement.className] ?? 0; v.dataset.v = prev; countUp(v, to); (J.kpiPrev ||= {})[v.parentElement.className] = to; });
    pulseStrip();
    if (!panels.left.get('filter')) UI.filter({ category: 'urgent', cases: op.cases.slice(0, 8), total: op.cases.length, quiet: true });
  },
  // the Chief Secretary's command board: every tile, bar and row is a question she can also ask by voice
  board(op) {
    const b = op.board, k = b.kpis, dl = b.days_left || [], mx = Math.max(1, ...dl.map(x => x.count));
    const tile = (cls, v, l, say) => `<div class="kpi ${cls}" data-say="${esc(say)}"><div class="v">${v}</div><div class="l">${esc(l)}</div></div>`;
    const lvMax = Math.max(1, ...(b.by_level || []).map(x => x.count)), dMax = Math.max(1, ...(b.departments || []).map(x => x.count));
    panel('kpi', 'left', `<h3>Command view <small>Karnataka · live · ${fmtDate(op.now)}</small></h3>
      <div class="kpis k8">${tile('hero', k.open, 'Open now', 'show me the dashboard for Karnataka')}${tile('bad', k.overdue, 'Overdue', 'show the overdue cases')}
        ${tile('vio', k.escalated_open, 'Escalated', 'how many cases have been escalated')}${tile('saf', k.due_3, 'Due ≤ 3 days', 'show me the 7 day timeline')}
        ${tile('l1', k.l1, 'At L1 · field', 'how many cases are with L1')}${tile('l2', k.l2, 'At L2', 'how many cases are with L2')}
        ${tile('l3', k.l3, 'At L3', 'how many cases are with L3')}${tile('ok', k.resolved, 'Resolved', 'how many cases are resolved')}</div>
      <div class="boardh"><span>The 7-day clock</span><span>${k.due_today} due today</span></div>
      <div class="dclock" data-say="show me the 7 day timeline">${dl.map((x, i) => `<div class="cb ${i === 0 ? 'od' : i === 1 ? 'dt' : ''}" title="${esc(x.name)}: ${x.count}"><b>${x.count}</b><i style="height:${Math.max(3, Math.round(Math.sqrt(x.count / mx) * 52))}px"></i><span>${esc(x.name.replace(' days left', 'd').replace(' day left', 'd').replace('Due today', 'today').replace('Overdue', 'late').replace('8+ d', '8+'))}</span></div>`).join('')}</div>
      <div class="boardh"><span>By level</span><span>open</span></div>
      <div class="bars">${(b.by_level || []).map(x => `<div class="bar" data-say="how many cases are with ${x.name}"><span class="t">${x.name} · ${x.name === 'L1' ? 'field officer' : x.name === 'L2' ? 'EO / AC / DD' : 'DC / ZP CEO'}</span><span class="b"><i style="width:${Math.round(x.count / lvMax * 100)}%"></i></span><span class="n">${x.count}</span></div>`).join('')}</div>
      <div class="boardh"><span>Departments</span><span>tap for the dashboard</span></div>
      <div class="bars">${(b.departments || []).map(x => `<div class="bar" data-say="how is ${esc(x.name === 'Rural Development & Panchayat Raj' ? 'RDPR' : x.name)} doing"><span class="t">${esc(x.name === 'Rural Development & Panchayat Raj' ? 'RDPR' : x.name)}</span><span class="b"><i style="width:${Math.round(x.count / dMax * 100)}%"></i></span><span class="n">${x.count}</span></div>`).join('')}</div>
      <div class="boardh"><span>Busiest districts</span><span>open · overdue</span></div>
      ${(b.places || []).map(x => `<div class="minirow" data-say="how is ${esc(x.name)} district doing"><span>${esc(x.name)}</span><span><b>${x.count}</b> · ${x.overdue}</span></div>`).join('')}
      <div class="pstrip" id="pulse"></div>`, { top: true });
    document.querySelectorAll('#left [data-say]').forEach(el => el.onclick = () => turn({ text: el.dataset.say }));
    document.querySelectorAll('#left .kpis .kpi .v').forEach(v => { const to = Number(v.textContent); const key = v.parentElement.className; const prev = J.kpiPrev?.[key] ?? 0; v.dataset.v = prev; countUp(v, to); (J.kpiPrev ||= {})[key] = to; });
    pulseStrip();
    if (!panels.left.get('filter')) UI.filter({ category: 'urgent', cases: op.cases.slice(0, 8), total: op.cases.length, quiet: true });
  },
  // the department / place the numbers are about, kept for follow-ups; ✕ goes back to the whole state
  scope(op) {
    let el = $('#scopeChip');
    if (!el) { el = document.createElement('div'); el.id = 'scopeChip'; el.className = 'scope-chip'; document.body.appendChild(el); }
    if (!op.label || J.profile !== 'cs') { el.classList.remove('on'); return; }
    el.innerHTML = `<i>Scope</i><span>${esc(op.label)}</span><button title="Back to the whole state" aria-label="Clear the scope">✕</button>`;
    el.classList.remove('on'); void el.offsetWidth; el.classList.add('on');
    el.querySelector('button').onclick = () => { el.classList.remove('on'); turn({ text: 'show me the overall dashboard statewide' }); };
  },
  filter(op) {
    const rows = op.cases || []; const label = { overdue: 'Overdue', vulnerable: 'Vulnerable citizens', on_time: 'On time', all: 'All open', urgent: 'Most urgent' }[op.category] || op.category;
    panel('filter', 'left', `<h3>${esc(label)} <small>${op.total} case${op.total === 1 ? '' : 's'}</small></h3>` +
      (rows.length ? `<div class="rows">${rows.slice(0, 14).map(b => `<div class="row" data-id="${esc(b.id)}">${ring(b)}<div><div class="id">${esc(b.id)} ${b.vulnerable ? '<span class="pill vio">♥</span>' : ''}</div><div class="svc">${esc(b.service)} · ${esc(b.ownerShort)}</div><div class="meta">${esc(b.gp || b.taluk)} · ${esc(b.level)}</div></div>${leftPill(b)}</div>`).join('')}</div>` : '<div class="empty">None right now.</div>'));
    document.querySelectorAll('#left .row[data-id]').forEach(r => r.onclick = () => turn({ text: `open ${r.dataset.id}` }));
  },
  officers(op) {
    const max = Math.max(1, ...op.rows.map(r => r.open));
    panel('officers', 'left', `<h3>Officers needing attention <small>sorted by overdue</small></h3><div class="bars">${op.rows.map(r => `<div class="bar" style="grid-template-columns:150px 1fr 60px"><span class="t">${esc(r.name)}</span><span class="b"><i style="width:${Math.round(r.open / max * 100)}%;${r.overdue ? 'background:linear-gradient(90deg,#f26b1d,#ff5c6a)' : ''}"></i></span><span class="n">${r.overdue}/${r.open}</span></div>`).join('')}</div>
      <div class="actions">${op.rows.slice(0, 3).map(r => `<button data-say="nudge ${esc(r.name)}">Nudge ${esc(r.name)}</button>`).join('')}</div>`, { top: true });
    document.querySelectorAll('#left .actions button[data-say]').forEach(b => b.onclick = () => turn({ text: b.dataset.say }));
  },
  answer(op) {
    const id = 'ans' + Math.random().toString(36).slice(2, 7);
    const el = panel(id, 'right', `<h3>${esc(op.q || 'Answer')} <small>Mitra</small></h3>${op.html ? `<div class="answer">${op.html}</div>` : ''}${op.chart ? `<div class="chartbox"><canvas id="c_${id}"></canvas></div><div class="src">${esc(op.chart.source || '')}</div>` : ''}`, { top: true });
    if (op.chart) renderChart('c_' + id, op.chart);
    while (panels.right.size > 5) { const [k, v] = [...panels.right.entries()].filter(([k]) => k.startsWith('ans')).pop() || []; if (!k) break; v.remove(); panels.right.delete(k); }
  },
  pack(op) {
    const f = op.facts || {};
    panel('pack', 'right', `<h3>Wednesday Review Pack <small>${esc((op.level || 'cs').toUpperCase())}</small></h3>${op.html ? `<div class="answer">${op.html}</div>` : `<div class="kv"><dt>Open</dt><dd>${f.open}</dd><dt>Overdue</dt><dd>${f.overdue}</dd><dt>Vulnerable</dt><dd>${f.vulnerable_waiting}</dd><dt>Auto-escalated</dt><dd>${f.auto_escalated}</dd></div>`}${op.kn ? `<div class="answer kn" style="margin-top:10px">${op.kn}</div>` : ''}`, { top: true });
  },
  e4(op) {
    panel('e4', 'right', `<h3>Form E-4 show-cause <small>more than 7 defaults</small></h3>${op.rows.length ? `<div class="rows">${op.rows.map(r => `<div class="row"><div><div class="id">${esc(r.officer)}</div></div><span class="pill bad">${r.defaults} defaults</span></div>`).join('')}</div>` : '<div class="empty">No officer crosses the threshold.</div>'}`, { top: true });
  }
};
function renderPipe() {
  const html = `<h3>Behind your words <small>Mitra pipeline · live</small></h3><div class="pipe">${STAGES.map(([t, d], i) => { const s = J.stages[i]; return `<div class="step ${s ? s.state : ''}"><div class="n">${s && s.state === 'done' ? '✓' : i + 1}</div><div><div class="t">${t}</div><div class="d">${esc(s?.note || d)}</div></div></div>`; }).join('')}</div>`;
  panel('pipe', 'right', html, { top: true });
}
// Sakala 2025 pulse strip for the Chief Secretary: 31 districts by late delivery (real report data) + the
// month-by-month overdue line; hover a cell for the number, click it to ask about that district
async function pulseStrip() {
  const host = $('#pulse'); if (!host) return;
  try { J.tracker ||= await api('/api/tracker', null, 'GET'); } catch (e) { host.remove(); return; }
  if (!document.body.contains(host)) return;
  const d = [...(J.tracker.districts || [])].sort((a, b) => b.late_pct - a.late_pct), mx = Math.max(...d.map(x => x.late_pct), 1);
  const m = J.tracker.monthly || [], ov = m.map(x => x.overdue), omx = Math.max(...ov, 1), omn = Math.min(...ov);
  const pts = ov.map((v, i) => `${(i / Math.max(1, ov.length - 1) * 100).toFixed(1)},${(28 - (v - omn) / Math.max(1, omx - omn) * 24).toFixed(1)}`).join(' ');
  host.innerHTML = `<div class="ph"><span>Sakala 2025 · late delivery by district</span><span>${J.tracker.state?.late_pct}% late · ${J.tracker.state?.rej_pct}% rejected</span></div>
    <div class="cells">${d.map(x => `<i title="${esc(x.district)} · ${x.late_pct}% late · rank ${x.rank_last | 0}" data-say="tell me about Sakala performance in ${esc(x.district)}" class="${/mysuru/i.test(x.district) ? 'pilot' : ''}" style="--h:${(x.late_pct / mx).toFixed(2)}"></i>`).join('')}</div>
    <div class="ph"><span>overdue applications, Jan → Dec</span><span>${ov[0]?.toLocaleString('en-IN')} → ${ov[ov.length - 1]?.toLocaleString('en-IN')}</span></div>
    <svg class="spark" viewBox="0 0 100 30" preserveAspectRatio="none"><polyline points="${pts}"/><polyline class="fill" points="0,30 ${pts} 100,30"/></svg>`;
  host.querySelectorAll('.cells i').forEach(c => c.onclick = () => turn({ text: c.dataset.say }));
}
// a label that floats up from the orb on a big moment ("GR-504211 → PDO Chapparadahalli")
function flyLabel(text) {
  const el = document.createElement('div'); el.className = 'fly'; el.textContent = text;
  document.querySelector('.orb-wrap').appendChild(el); setTimeout(() => el.remove(), 2600);
}
// ---- conversation strip: what you said (with the actual recording) and what Mitra answered (replayable)
J.convo = [];
function convoAdd(e) { if (!e.you && !e.say) return; J.convo.push(e); while (J.convo.length > 6) J.convo.shift(); renderConvo(); return e; }
function renderConvo() {
  if (!J.convo.length) { dropPanel('convo', 'right'); return; }
  const bars = c => c && c.bars ? `<span class="clip" data-i="${c._i}"><b class="pl">▶</b>${c.bars.map(v => `<i style="--v:${Math.max(.08, v).toFixed(2)}"></i>`).join('')}<small>${c.secs.toFixed(1)}s</small></span>` : '';
  J.convo.forEach((e, i) => { if (e.clip) e.clip._i = i; });
  panel('convo', 'right', `<h3>Conversation <small>${J.convo.length} exchange${J.convo.length === 1 ? '' : 's'}</small></h3><div class="convo">${J.convo.map((e, i) => `
    <div class="ex"><div class="you">${bars(e.clip)}<span>${esc(e.you || '')}</span></div>
    <div class="jv"><button class="pl ${e.bufs && e.bufs.length ? '' : 'off'}" data-j="${i}" ${e.bufs && e.bufs.length ? '' : 'disabled'}>▶</button><span>${esc(e.say)}</span></div></div>`).join('')}</div>`);
  document.querySelectorAll('#right .convo .clip[data-i]').forEach(c => c.onclick = () => playB64(J.convo[+c.dataset.i]?.clip?.b64));
  document.querySelectorAll('#right .convo .jv .pl[data-j]').forEach(b => b.onclick = () => playBufs(J.convo[+b.dataset.j]?.bufs));
  const box = document.querySelector('#right .convo'); if (box) box.scrollTop = box.scrollHeight;
}
async function playB64(b64) { if (!b64) return; const ac = ensureAudio(); const buf = await ac.decodeAudioData(b64ToArr(b64).buffer); playBufs([buf]); }
function playBufs(bufs) {
  if (!bufs || !bufs.length) return; stopSpeaking(); const ac = ensureAudio(); let t = ac.currentTime;
  for (const b of bufs) { const s = ac.createBufferSource(); s.buffer = b; s.connect(J.outGain); s.start(t); t += b.duration; }
}
// ---- live waveform under the captions while the microphone is open
(function waveLoop() {
  const cv = $('#wave'); if (!cv) return; const ctx = cv.getContext('2d');
  const draw = () => {
    const on = J.capturing || J.rec || SC.on || document.body.dataset.state === 'listening';
    cv.classList.toggle('on', !!on);
    if (on) {
      const W = cv.width, H = cv.height, n = J.lv.length, bw = W / n; ctx.clearRect(0, 0, W, H);
      for (let i = 0; i < n; i++) { const v = J.lv[(J.lvi + i) % n], h = Math.max(2, Math.min(H, v * H * 4.5)); const a = .25 + (i / n) * .75; ctx.fillStyle = `rgba(121,227,255,${a})`; ctx.fillRect(i * bw + 1, (H - h) / 2, bw - 2, h); }
    }
    requestAnimationFrame(draw);
  };
  draw();
})();
// ---- the background leans with the pointer
window.addEventListener('pointermove', e => { const x = (e.clientX / innerWidth - .5), y = (e.clientY / innerHeight - .5); document.documentElement.style.setProperty('--px', x.toFixed(3)); document.documentElement.style.setProperty('--py', y.toFixed(3)); }, { passive: true });
function renderRouted(e) {
  const o = e.officer || {}; const ini = (o.short || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  const chain = (e.chain || []).map((c, i) => `${i ? ' → ' : ''}${esc(c.lv)} · ${esc(c.short)}`).join('');
  panel('routed', 'right', `<h3>${esc(e.title || 'Routed to')} <small>${esc(e.caseId)}</small></h3><div class="routed"><div class="av">${ini}</div><div><div class="nm">${esc(o.name || o.short)}</div><div class="ch">${chain}</div></div></div><div class="ev">${esc(e.basis || '')}</div>`);
}
function renderChart(id, c) {
  const el = document.getElementById(id); if (!el || !window.Chart) return;
  const grad = el.getContext('2d').createLinearGradient(0, 0, 0, 220); grad.addColorStop(0, '#16c784'); grad.addColorStop(1, 'rgba(14,159,110,.35)');
  const line = c.type === 'line';
  const chart = new Chart(el, {
    type: line ? 'line' : 'bar',
    data: { labels: c.labels, datasets: [{ label: c.series_label || '', data: c.values, backgroundColor: line ? 'rgba(22,199,132,.18)' : grad, borderColor: '#16c784', borderWidth: line ? 2 : 0, borderRadius: 8, fill: line, tension: .4, pointBackgroundColor: '#ff9a3c', pointRadius: line ? 3 : 0 }] },
    options: { responsive: true, maintainAspectRatio: false, animation: { duration: 900, easing: 'easeOutQuart' }, plugins: { legend: { display: false }, tooltip: { backgroundColor: 'rgba(11,11,12,.92)', cornerRadius: 12, callbacks: { label: x => ` ${x.formattedValue}${c.unit || ''}` } } },
      scales: { x: { ticks: { color: '#9a9ca6', font: { size: 10 }, maxRotation: 0, callback(v) { const l = this.getLabelForValue(v); return l.length > 12 ? l.slice(0, 11) + '…' : l; } }, grid: { display: false } }, y: { ticks: { color: '#6b6e7a', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,.06)' }, border: { display: false } } } }
  });
  J.charts[id] = chart;
}
async function playNote(id) {
  const ac = ensureAudio(); const r = await fetch(`/api/note/${id}/audio`); if (!r.ok) return toast('Voice note', 'No audio recorded for this note');
  const buf = await ac.decodeAudioData(await r.arrayBuffer()); const s = ac.createBufferSource(); s.buffer = buf; s.connect(ac.destination); s.start();
}

function spokenUpdate(m) {
  const t = m.text || '';
  switch (m.kind) {
    case 'accepted': return `${m.officer} accepted your request and started working on it.`;
    case 'info': return `${m.officer} asks: “${t}”`;
    case 'resolved': return `Resolved. Action taken: “${t.replace(/[.\s]+$/, '')}”. Was it actually solved?`;
    case 'rejected': return `Could not accept. Reason: ${t}. You may appeal to ${m.up}.`;
    case 'returned': return `Being re-checked by the scrutiny desk to find the right office.`;
    case 'escalated': return `Not acted on in time; moved up to ${m.officer}.`;
    case 'routed': return `Checked by the scrutiny desk; now with ${m.officer}.`;
    case 'compensation': return `Sakala compensation of ₹${t} ordered for the delay.`;
    default: return `${m.officer}: ${t}`;
  }
}
// ---- the document door: a written complaint read into the official iPGRS form
const DOC_STEPS = [
  { title: '1 · Grievance & location', keys: [['description', 'Grievance, in the citizen\'s words', 'area'], ['address', 'Exact place (street, landmark, door)'], ['village', 'Village'], ['gp', 'Gram Panchayat'], ['taluk', 'Taluk'], ['district', 'District'], ['pincode', 'Pincode'], ['since', 'Since when']] },
  { title: '2 · Classification', keys: [] },
  { title: '3 · Complainant', keys: [['name', 'Name'], ['phone', 'Mobile number'], ['complainant_address', 'Address'], ['letter_date', 'Date of the letter'], ['addressed_to', 'Addressed to'], ['asked_for', 'What is asked for'], ['grievance_id', 'iPGRS number quoted in the letter']] },
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
  const rec = doc.record;
  const recRow = rec ? `<div class="drec"><i>⌘</i><div><b>Matches iPGRS record ${esc(rec.gid)}</b><span>${esc(rec.service || rec.grievance || '')} · ${esc([rec.gp, rec.taluk, rec.district].filter(Boolean).join(', '))} · filed ${esc((rec.created || '').slice(0, 10))} via ${esc(rec.source || 'iPGRS')} · ${esc(rec.status || '')}</span></div></div>` : '';
  const head = `<div class="dhead"><div class="dthumbs">${thumbs}</div><div class="dmeta"><b>${esc(doc.filename || 'Written complaint')}</b><span>${doc.pages || 1} page${(doc.pages || 1) > 1 ? 's' : ''} · read by Mitra${doc.ms ? ' in ' + (doc.ms / 1000).toFixed(0) + ' s' : ''}${doc.rotation ? ' · photo turned upright' : ''}${doc.language ? ' · ' + esc({ kn: 'Kannada', en: 'English', mixed: 'Kannada + English', te: 'Telugu', hi: 'Hindi', ta: 'Tamil' }[doc.language] || doc.language) : ''}</span>${doc.several ? '<span class="pill warn">The letter seems to hold more than one complaint</span>' : ''}${recRow}${doc.english && doc.english !== f.description ? `<details class="deng"><summary>English rendering</summary><p>${esc(doc.english)}</p></details>` : ''}</div></div>`;
  const cls = `<div class="dsec"><h4>${DOC_STEPS[1].title}</h4><div class="dclass"><div class="big">${esc(d.service || '—')}</div><div class="path">${esc(d.dept || '')}${d.grievance ? ' › ' + esc(d.grievance) : ''}${d.vulnerable ? ' · <span class="pill vio">♥ priority</span>' : ''}</div>${d.conf != null ? `<div class="conf"><span>AI confidence</span><span class="m"><i style="width:${d.conf}%"></i></span><b>${d.conf}%</b> <span>· from the official master</span></div>` : ''}${o ? `<div class="who"><div class="av">${esc((o.short || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase())}</div><div><div class="n">${esc(o.name)}</div><div class="c">${esc((pv.chain || []).map(c => c.short).join(' → '))} · ${pv.days} days</div></div></div>` : ''}</div></div>`;
  const s1 = `<div class="dsec"><h4>${DOC_STEPS[0].title}${p.taluk ? ` <small>📍 ${esc(p.gp ? p.gp + ' GP, ' : '')}${esc(p.taluk)} · ${esc(p.how || '')}</small>` : ''}</h4>${DOC_STEPS[0].keys.map(field).join('')}</div>`;
  const s3 = `<div class="dsec"><h4>${DOC_STEPS[2].title}</h4>${DOC_STEPS[2].keys.map(field).join('')}</div>`;
  const gaps = (doc.missing || []).filter(k => ['name', 'phone', 'address'].includes(k));
  const note = gaps.length ? `<div class="dnote">The letter does not give ${gaps.map(k => ({ name: 'the complainant\'s name', phone: 'a phone number', address: 'the exact place' })[k]).join(' or ')}. Add it if you have it; otherwise it is filed as “not provided”.</div>` : '';
  const bar = flow === 'confirm' ? `<div class="dsubmit"><button class="dgo" id="docSubmit"><span>Submit</span><small>files it to ${o ? esc(o.short) : 'the officer'}</small></button><button class="dchg" id="docChange">Change</button></div>`
    : flow === 'scrutiny_confirm' ? `<div class="dnote">${esc(d.why || 'No official category matches with certainty.')} On submit the letter goes to the scrutiny desk, where a person routes it to the right officer.</div><div class="dsubmit"><button class="dgo" id="docSubmit"><span>Submit</span><small>to the scrutiny desk, with the letter</small></button><button class="dchg" id="docChange">Change</button></div>`
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
      const r = await api('/api/document/submit', { session: J.sid, fields: collect(), want_audio: !liveVoiceOn() });
      trace('think', 'done'); trace('act', 'done'); trace('speak', 'run'); applyUi(r.ui || []); captionYou('Submit'); convoAdd({ you: 'Submit', say: r.say || '', intent: r.intent || 'confirm', t: Date.now() });
      await sayBack(r);
      trace('speak', 'done');
    } catch (e) { toast('Submit', e.message || 'could not file it'); setState('idle', 'Ready'); go.disabled = false; go.querySelector('span').textContent = 'Submit'; }
  };
  const ch = $('#docChange'); if (ch) ch.onclick = () => turn({ text: 'change' });
  // typed edits live in the draft until Submit; a changed place is resolved on Submit
}
function bindAttach() {
  const at = $('#attach'); if (!at || at.__b) return; at.__b = true;
  at.onclick = () => {
    if (J.profile !== 'citizen') return;
    if (!panels.left.get('request') || !$('#reqFile')) UI.request({ draft: {}, flow: 'menu', options: [] });
    const inp = $('#reqFile'), dz = $('#dropz');
    if (inp) inp.click();                                              // a real tap: the picker (camera on a phone) opens
    else if (dz) UI.upload({});
  };
}
function bindDrop() {
  bindAttach();
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
    const r = await api('/api/document', { session: J.sid, file_b64: b64, media_type: file.type || (file.name.toLowerCase().endsWith('.pdf') ? 'application/pdf' : 'image/jpeg'), filename: file.name, want_audio: !liveVoiceOn() });
    trace('think', 'done'); trace('act', 'done'); trace('speak', 'run');
    applyUi(r.ui || []); captionYou('📄 ' + file.name); Orb.burst(); flyLabel('letter read → form'); convoAdd({ you: '📄 ' + file.name, say: r.say || '', intent: 'document', t: Date.now() });
    await sayBack(r);
    trace('speak', 'done');
  } catch (e) { toast('Document', e.message || 'could not read it'); setState('idle', 'Ready'); if (dz) { dz.classList.remove('busy'); dz.querySelector('.dz-t b').textContent = 'Upload a written complaint'; } }
}
async function sendPhoto(file) {
  if (!file) return;
  const b64 = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1]); fr.readAsDataURL(file); });
  stopSpeaking(); setState('thinking', 'Reading the photo…'); traceReset(); trace('listen', 'done'); trace('think', 'run');
  try {
    const r = await api('/api/photo', { session: J.sid, image_b64: b64, media_type: file.type || 'image/png' });
    trace('think', 'done'); trace('act', 'done'); trace('speak', 'run');
    applyUi(r.ui || []); captionYou('📷 photo of the petition');
    await sayBack(r);
    trace('speak', 'done');
  } catch (e) { toast('Photo', e.message || 'could not read it'); setState('idle', 'Ready'); }
}
// something arrived for this screen while it was idle: show it, and let Mitra say it
let announceQueue = Promise.resolve();
function announce(fn) { announceQueue = announceQueue.then(async () => { while (J.busy || J.speaking || J.capturing) await new Promise(r => setTimeout(r, 300)); await fn(); }).catch(() => { }); }
async function citizenUpdates() {
  const r = await api(`/api/updates?session=${J.sid}`, null, 'GET');
  if (!r.say) { applyUi(r.ui || []); return; }
  applyUi(r.ui || []); traceReset();
  if (LV.open) { lvText(r.say, true); return; }
  if (r.tts_id && (r.parts || []).length > 1) await speakParts(r); else await speak(r.say, r.audio_b64, r.tts);
  if (J.wakeOn) { if (liveWanted()) liveOpen(); else startCapture(true); }
}
async function officerAnnounce(text) {
  if (LV.open) { lvText(text, true); return; }
  const r = await api('/api/tts', { text, lang: J.lang });
  await speak(text, r.audio_b64, r.tts);
}

// ------------------------------------------------------------------ notifications
// Cards slide in from the right and settle at the top centre; the bell keeps this screen's history; the officer
// gets a "Just in" shelf. The server keeps a seen-cursor per screen, so switching to a profile pops exactly what it
// missed while it was not on screen, once.
const NT = { shown: new Set(), live: [], queue: [], unread: 0, hist: [], maxId: 0, viewer: '' };
const NT_MAX = 3;
function ntAgo(ts) {
  const s = (Date.now() - new Date(ts).getTime()) / 1000;
  return !isFinite(s) ? '' : s < 45 ? 'just now' : s < 3600 ? `${Math.max(1, Math.floor(s / 60))} min ago` : s < 86400 ? `${Math.floor(s / 3600)} h ago` : `${Math.floor(s / 86400)} d ago`;
}
setInterval(() => document.querySelectorAll('[data-ts]').forEach(el => { el.textContent = ntAgo(el.dataset.ts); }), 15000);
function ping(tone) {
  try {
    const ac = ensureAudio(), t = ac.currentTime;
    const notes = tone === 'bad' ? [587, 440] : tone === 'warn' ? [698, 587] : tone === 'sent' ? [988] : tone === 'voice' ? [659, 880, 1047] : [784, 1175];
    notes.forEach((f, i) => {
      const o = ac.createOscillator(), g = ac.createGain(), at = t + i * .11;
      o.type = 'sine'; o.frequency.value = f; g.gain.setValueAtTime(0, at); g.gain.linearRampToValueAtTime(tone === 'sent' ? .05 : .085, at + .015);
      g.gain.exponentialRampToValueAtTime(.0001, at + .38); o.connect(g); g.connect(ac.destination); o.start(at); o.stop(at + .42);
    });
  } catch (e) { }
}
let seenTimer = null;
function seenSoon() { clearTimeout(seenTimer); seenTimer = setTimeout(() => { if (J.sid && NT.maxId) api('/api/notifs/seen', { session: J.sid, upto: NT.maxId }).catch(() => { }); }, 600); }
function ntSpeak(c) {
  if (!c.speak || c.tone === 'sent' || J.profile !== 'officer') return;
  if (!J.announced) J.announced = new Set();
  if (J.announced.has(c.id)) return; J.announced.add(c.id);
  announce(() => officerAnnounce(c.speak));
}
// a live card from the server (SSE)
function onNotify(c) {
  if (!c) return; const k = NT.viewer + ':' + c.id;
  if (NT.shown.has(k)) return; NT.shown.add(k);
  NT.maxId = Math.max(NT.maxId, c.id); seenSoon();
  ncAdd(c); ntEnqueue(c); ntSpeak(c);
  if (J.profile === 'officer' && ['new', 'rerouted', 'escalated', 'appeal', 'reopened'].includes(c.change)) { clearTimeout(J.jiTimer); J.jiTimer = setTimeout(() => loadNotifs({ replay: false }), 500); }
}
function ntEnqueue(c, delay = 0) {
  if (NT.live.length >= NT_MAX) { NT.queue.push(c); return; }
  delay ? setTimeout(() => ntShow(c), delay) : ntShow(c);
}
function ntShow(c) {
  while (NT.live.filter(x => !x.classList.contains('out')).length >= NT_MAX) ntClose(NT.live.find(x => !x.classList.contains('out')));
  const el = document.createElement('div'); el.className = `nt t-${c.tone || 'info'}`; el.dataset.id = c.id;
  const dur = c.sticky ? 16000 : c.tone === 'sent' ? 5000 : 9000; el.style.setProperty('--dur', dur + 'ms');
  const acts = (c.actions || []).filter(a => !(a.say && /^open /.test(a.say) && J.profile === 'citizen'));
  el.innerHTML = `<div class="nt-ic"><span>${esc(c.icon || '•')}</span></div><div class="nt-b"><div class="nt-h"><b>${esc(c.title)}</b><span class="nt-t" data-ts="${esc(c.ts)}">${esc(ntAgo(c.ts) || c.ago || '')}</span></div>${c.body ? `<div class="nt-m">${esc(c.body)}</div>` : ''}${acts.length ? `<div class="nt-a">${acts.map((a, i) => `<button data-i="${i}">${esc(a.label)}</button>`).join('')}</div>` : ''}</div><button class="nt-x" title="Dismiss">×</button><i class="nt-bar"></i>`;
  $('#notifs').prepend(el); NT.live.push(el); requestAnimationFrame(restack);
  ping(c.tone); Orb.pulse();
  let left = dur, t0 = performance.now(), timer = setTimeout(() => ntClose(el), dur);
  el.addEventListener('pointerenter', () => { clearTimeout(timer); left -= performance.now() - t0; });
  el.addEventListener('pointerleave', () => { t0 = performance.now(); timer = setTimeout(() => ntClose(el), Math.max(1200, left)); });
  el.querySelector('.nt-x').onclick = ev => { ev.stopPropagation(); ntClose(el); };
  el.querySelectorAll('.nt-a button').forEach(b => b.onclick = ev => { ev.stopPropagation(); ntAction(acts[+b.dataset.i]); ntClose(el); });
  el.onclick = () => { const a = acts.find(x => x.say || x.play || x.as_officer); if (a) ntAction(a); ntClose(el); };
  // swipe it away
  let sx = null;
  el.addEventListener('pointerdown', ev => { if (ev.target.closest('button')) return; sx = ev.clientX; el.setPointerCapture(ev.pointerId); });
  el.addEventListener('pointermove', ev => { if (sx == null) return; const dx = ev.clientX - sx; el.style.transform = `translateX(${dx}px)`; el.style.opacity = String(1 - Math.min(.8, Math.abs(dx) / 260)); });
  el.addEventListener('pointerup', ev => { if (sx == null) return; const dx = ev.clientX - sx; sx = null; if (Math.abs(dx) > 90) { ev.stopPropagation(); el.onclick = null; ntClose(el, dx > 0 ? 'r' : 'l'); } else { el.style.transform = ''; el.style.opacity = ''; } });
}
function ntClose(el, dir) {
  if (el.classList.contains('out')) return;
  el.classList.add('out'); if (dir) el.classList.add('out-' + dir);
  setTimeout(() => { el.remove(); NT.live = NT.live.filter(x => x !== el); restack(); const n = NT.queue.shift(); if (n) ntShow(n); }, 380);
}
// older cards tuck behind the newest so only a sliver of each shows (hovering the stack fans them out)
function restack() { [...$('#notifs').children].forEach((el, i) => el.style.setProperty('--tuck', i ? `${-(el.offsetHeight - 12)}px` : '0px')); }
function ntClear() { NT.queue = []; for (const el of [...NT.live]) ntClose(el); }
async function ntAction(a) {
  if (!a) return;
  if (a.play) return playNote(a.play);
  if (a.as_officer) return viewAsOfficer(a.as_officer, a.case_id);
  if (a.say) turn({ text: a.say });
}
// jump straight into the inbox of the officer a request was routed to
async function viewAsOfficer(oid, cid = '') {
  const o = J.boot?.officers?.[oid];
  if (J.profile === 'officer' && J.officer === oid) { if (cid) turn({ text: `open ${cid}` }); return; }
  if (cid) J.quietArrival = true;
  await switchTo('officer', { officer: oid, title: o ? `Opening ${o.short}'s desk` : null, sub: cid ? `${cid} · as the officer sees it` : null,
                              then: cid ? () => whenIdle(() => { turn({ text: `open ${cid}` }); setTimeout(() => { J.quietArrival = false; }, 4000); }) : null });
}
// run once Mitra has finished the turn in hand (a request made while she is busy would be dropped)
function whenIdle(fn, waited = 0) {
  if ((J.busy || J.speaking) && waited < 12000) { setTimeout(() => whenIdle(fn, waited + 150), 150); return; }
  fn();
}
// ---- the bell
function ncRow(c) { return `<div class="nc-row t-${c.tone || 'info'}" data-c="${esc(c.case_id || '')}"><div class="nt-ic"><span>${esc(c.icon || '•')}</span></div><div class="nc-b"><b>${esc(c.title)}</b>${c.body ? `<div class="m">${esc(c.body)}</div>` : ''}</div><span class="nt-t" data-ts="${esc(c.ts)}">${esc(ntAgo(c.ts))}</span></div>`; }
function renderNc() {
  $('#ncList').innerHTML = NT.hist.length ? NT.hist.map(ncRow).join('') : '<div class="empty">Nothing yet. Everything that happens to your cases appears here.</div>';
  document.querySelectorAll('#ncList .nc-row').forEach(r => r.onclick = () => { $('#ncenter').classList.remove('open'); const id = r.dataset.c; if (id && J.profile !== 'citizen') turn({ text: `open ${id}` }); else if (id) turn({ text: 'track my request' }); });
  badge();
}
function ncAdd(c) { NT.hist = [c, ...NT.hist.filter(x => x.id !== c.id)].slice(0, 40); NT.unread++; renderNc(); const b = $('#bell'); b.classList.remove('ring'); void b.offsetWidth; b.classList.add('ring'); }
function badge() { const n = $('#bellN'); n.hidden = !NT.unread; n.textContent = NT.unread > 9 ? '9+' : NT.unread; }
$('#bell').onclick = e => { e.stopPropagation(); $('#ncenter').classList.toggle('open'); NT.unread = 0; badge(); };
$('#ncenter').addEventListener('click', e => e.stopPropagation());
document.addEventListener('click', () => $('#ncenter').classList.remove('open'));
$('#ncClear').onclick = () => { NT.unread = 0; badge(); $('#ncenter').classList.remove('open'); };
// ---- load what this screen missed (on every profile switch / officer login / reload)
async function loadNotifs({ replay = true } = {}) {
  if (!J.sid) return;
  let r; try { r = await api(`/api/notifs?session=${J.sid}`, null, 'GET'); } catch (e) { return; }
  if (r.viewer !== NT.viewer) { NT.viewer = r.viewer; NT.shown = new Set(); NT.maxId = 0; NT.unread = 0; ntClear(); }
  NT.hist = r.history || []; renderNc();
  J.justIn = r.just_in || []; renderJustIn();
  if (!replay) return;
  const pend = (r.pending || []).filter(c => !NT.shown.has(NT.viewer + ':' + c.id));
  if (!pend.length) return;
  pend.forEach(c => { NT.shown.add(NT.viewer + ':' + c.id); NT.maxId = Math.max(NT.maxId, c.id); });
  seenSoon(); NT.unread += pend.length; badge();
  const show = pend.slice(-NT_MAX).reverse();               // newest first
  show.forEach((c, i) => ntEnqueue(c, 350 + i * 420));
  if (pend.length > NT_MAX) setTimeout(() => ntEnqueue({ id: -1, ts: new Date().toISOString(), tone: 'info', icon: '🔔', title: `${pend.length - NT_MAX} more while you were away`, body: 'They are all in the bell, top right.', actions: [] }), 350 + NT_MAX * 420);
  if (J.profile === 'officer' && !J.quietArrival) {               // (not when the person asked to open a case here: it opens at once)
    const lead = pend[pend.length - 1], said = lead.speak || lead.title;
    pend.forEach(c => { (J.announced ||= new Set()).add(c.id); });
    announce(() => officerAnnounce(pend.length === 1 ? said : `${pend.length} updates while you were away. The latest: ${said}`));
  }
}
// ---- the officer's "Just in" shelf: what reached this inbox in the last hour (real time), newest first
function renderJustIn() {
  const rows = J.profile === 'officer' ? (J.justIn || []) : [];
  if (!rows.length) { dropPanel('justin', 'left'); markInboxNew(); return; }
  const icon = { new: '⚡', rerouted: '↪', escalated: '⏫', appeal: '⚖', reopened: '↩' }, label = { new: 'new', rerouted: 'assigned', escalated: 'escalated', appeal: 'appeal', reopened: 're-opened' };
  const fresh = ts => (Date.now() - new Date(ts).getTime()) < 10 * 60 * 1000;
  const el = panel('justin', 'left', `<h3><span class="ji-h"><i></i>Just in</span><small>arrived in the last hour · live</small></h3><div class="ji">${rows.map(r => `<div class="ji-row ${fresh(r.ts) ? 'fresh' : ''}" data-id="${esc(r.case_id)}"><div class="ji-ic">${icon[r.change] || '⚡'}</div><div class="ji-b"><div class="id">${esc(r.case_id)} <span class="ji-k k-${esc(r.change)}">${label[r.change] || r.change}</span></div><div class="svc">${esc(r.service || '')}${r.place ? ' · ' + esc(r.place) : ''}</div>${r.via ? `<div class="meta">${esc(r.via)}</div>` : ''}</div><div class="ji-t" data-ts="${esc(r.ts)}">${esc(ntAgo(r.ts))}</div></div>`).join('')}</div>`, { top: true, cls: 'justin' });
  $('#left').prepend(el);
  el.querySelectorAll('.ji-row').forEach(x => x.onclick = () => turn({ text: `open ${x.dataset.id}` }));
  markInboxNew();
}
function markInboxNew() {
  const ids = new Set((J.justIn || []).map(r => r.case_id));
  document.querySelectorAll('#left .card:not(.justin) .row[data-id]').forEach(r => {
    const t = r.querySelector('.newtag'), on = ids.has(r.dataset.id);
    if (on && !t) r.querySelector('.id')?.insertAdjacentHTML('beforeend', ' <span class="newtag">NEW</span>');
    else if (!on && t) t.remove();
  });
}


// ------------------------------------------------------------------ full duplex (English): the live voice engine through /ws/live
// Standby: the wake scanner listens for "Hey Mitra" (nothing is streamed). The wake word, a tap on the orb or typing opens a
// live conversation: the mic streams continuously (16 kHz PCM), Mitra's voice streams back (24 kHz PCM) and is cut the
// instant the person talks over it. ~20 s of quiet closes it again (and stops the per-minute cost). Kannada, or any
// failure, uses the cascade.
const LV = { ws: null, open: false, ready: false, q: [], nextT: 0, srcs: [], an: null, idleT: null, fallbackUntil: 0,
             inTx: '', outTx: '', bufs: [], pcm: [], lastVoice: 0, playing: false, turnT0: 0, firstAudio: 0, cutTurn: false,
             viz: null, vizT: null, vizShown: false, vizN: 0 };
// one picture per turn: the model may call several functions before it speaks (and sometimes the same one again), so a
// picture waits for the turn to settle (a newer one replaces it, the same one is ignored), is shown the moment Mitra starts
// speaking, enters once, and anything later in the same turn crossfades in place instead of flying in again
const VIZ_SETTLE_MS = 900;
function vizHold(op, e) {
  LV.viz = op; clearTimeout(LV.vizT); LV.vizT = null;
  if (LV.outTx || LV.firstAudio || (e && e.auto)) { vizFlush('now'); return; }
  LV.vizT = setTimeout(() => vizFlush('settled'), VIZ_SETTLE_MS);
}
function vizFlush(why) {
  clearTimeout(LV.vizT); LV.vizT = null;
  const op = LV.viz; LV.viz = null; Stage.refine(false);
  if (!op) return;
  const same = Stage.open && Stage.current && JSON.stringify(Stage.current) === JSON.stringify(op);
  if (same) { LV.vizShown = true; return; }
  Stage.show(op, { crossfade: Stage.open });          // a picture already up crossfades in place; the first one makes the entrance
  LV.vizShown = true; LV.vizN++;
  if (window.__vizLog) window.__vizLog.push({ why, title: op.title, t: Math.round(performance.now()) });
}
function vizDrop() { clearTimeout(LV.vizT); LV.vizT = null; LV.viz = null; Stage.refine(false); }
const LV_IDLE_MS = 20000;
J.liveTest = new URLSearchParams(location.search).has('livetest');      // headless tests: no microphone, drive by typing
function liveWanted() { return Date.now() > LV.fallbackUntil && (!!J.mic || J.liveTest); }     // muted = the track is off; the session may still open for typed text
function modePill() {
  const p = $('#modePill'); if (!p) return;
  const m = LV.open ? (LV.ready ? (J.lang === 'kn' ? 'kannada' : 'live') : 'connecting') : (Date.now() < LV.fallbackUntil ? 'cascade' : 'standby');
  p.dataset.m = m;
  p.querySelector('b').textContent = { live: 'Live · full duplex', connecting: 'Connecting…', kannada: 'ಕನ್ನಡ · full duplex', cascade: 'Voice · cascade', standby: `Standby · “Hey ${J.name}”` }[m];
}
function liveOpen(firstText = '') {
  if (LV.open) { if (firstText) lvText(firstText); return true; }
  if (!liveWanted()) return false;
  stopSpeaking(); cancelCapture(); scanDrop();
  LV.open = true; LV.ready = false; LV.inTx = LV.outTx = ''; LV.q = firstText ? [firstText] : []; LV.cutTurn = false;
  const BK = window.MITRA_BACKEND || '';                             // pages on Vercel: the live voice goes straight to the server
  const ws = new WebSocket(BK ? `${BK.replace(/^http/, 'ws')}/ws/live?session=${J.sid}` : `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/live?session=${J.sid}`);
  ws.binaryType = 'arraybuffer'; LV.ws = ws;
  document.body.classList.add('live'); setState('listening', 'Connecting…'); modePill(); Orb.pulse();
  ws.onmessage = ev => { if (LV.ws !== ws) return;                 // a socket closed by a profile switch says nothing more (no stale fallback)
    typeof ev.data === 'string' ? lvEvent(JSON.parse(ev.data)) : lvAudio(ev.data); };
  ws.onclose = () => { if (LV.ws === ws) liveClose('closed'); };
  ws.onerror = () => { };
  return true;
}
function liveClose(why = '') {
  const ws = LV.ws; LV.ws = null;
  if (ws) { try { ws.readyState === 1 && ws.send(JSON.stringify({ type: 'bye' })); ws.close(); } catch (e) { } }
  const was = LV.open;
  LV.open = LV.ready = false; clearTimeout(LV.idleT); lvCut(true);
  document.body.classList.remove('live', 'user-talking');
  if (was) { Orb.setSource(null); if (!J.busy && !J.speaking) setState(J.muted ? 'muted' : 'idle', J.muted ? 'Tap the mic to unmute' : `Say “Hey ${J.name}”`); }
  modePill();
}
function lvIdle() {
  clearTimeout(LV.idleT);
  LV.idleT = setTimeout(() => { if (LV.open && !LV.playing && performance.now() - LV.lastVoice > LV_IDLE_MS - 500) { chime(false); liveClose('idle'); } else lvIdle(); }, LV_IDLE_MS);
}
// Mitra's live voice reads a reply that arrived over HTTP (a document read, the form submitted): word for word, no function
function lvRead(text) {
  if (!LV.ws || LV.ws.readyState !== 1 || !LV.ready) { LV.q.push({ read: text }); return; }
  // a Kannada session reads it in Kannada even if an English line slipped through (the server translates first; this is the net)
  const how = J.lang === 'kn' ? 'in casual spoken Kannada, keeping every id, name, place, number and date exactly' : 'in these words';
  lvCut(); LV.ws.send(JSON.stringify({ type: 'text', text: `(Say this to the person now, ${how}, then stop. Call no function.) ${text}`, system: true }));
  LV.lastVoice = performance.now(); lvIdle();
}
function lvText(text, system = false) {
  if (!system && navByVoice(text)) return;
  if (!system && Stage.open && morphByVoice(text)) return;
  if (!LV.ws || LV.ws.readyState !== 1 || !LV.ready) { LV.q.push(system ? { system: text } : text); return; }
  if (!system) { captionYou(text); LV.inTx = text; }
  lvCut(); LV.ws.send(JSON.stringify({ type: 'text', text: system ? `(Sakala notification for the person on this screen. Tell them in one short sentence, then stop.) ${text}` : text, system }));
  LV.lastVoice = performance.now(); lvIdle();
}
// 48 kHz Float32 from the mic -> 16 kHz Int16 frames to the server
function outLevel() {
  if (!LV.an || !LV.playing) return 0;
  const d = LV.ob || (LV.ob = new Uint8Array(LV.an.fftSize)); LV.an.getByteTimeDomainData(d);
  let s = 0; for (const v of d) s += (v - 128) * (v - 128); return Math.sqrt(s / d.length) / 128;
}
function lvSend(buf) {
  if (!LV.ws || LV.ws.readyState !== 1 || !LV.ready) return;
  // echo guard: while Mitra speaks through laptop speakers, frames quieter than its own echo go as silence, so it never
  // interrupts itself; a real voice near the microphone is louder and still cuts in
  const ml = micLevel(), echo = LV.playing && ml < Math.max(.05, outLevel() * .7);
  // local barge-in: a voice clearly louder than Mitra's own echo ducks her at once (the model's 'interrupted' then cuts her);
  // two frames (~250 ms) so a cough or a click does not
  if (LV.playing && ml > Math.max(.09, outLevel() * 1.8)) { LV.loud = (LV.loud || 0) + 1; if (LV.loud === 2) { duck(true); document.body.classList.add('user-talking'); } }
  else LV.loud = 0;
  const ratio = J.inRate / 16000, n = Math.floor(buf.length / ratio), out = new Int16Array(n);
  if (echo) { LV.ws.send(out.buffer); return; }
  for (let i = 0; i < n; i++) { const s = Math.floor(i * ratio), e = Math.min(buf.length, Math.floor((i + 1) * ratio)); let sum = 0; for (let k = s; k < e; k++) sum += buf[k]; const v = Math.max(-1, Math.min(1, sum / Math.max(1, e - s))); out[i] = v < 0 ? v * 32768 : v * 32767; }
  LV.ws.send(out.buffer);
  if (LV.pcm.length < 400) LV.pcm.push(buf);
  const lv = ml; levelPush(lv);
  if (lv > .04) { LV.lastVoice = performance.now(); if (LV.playing && lv > .09) duck(true); }
}
function lvAudio(ab) {
  if (LV.cutTurn) return;                                       // the rest of an interrupted / stopped answer
  const ac = ensureAudio(), i16 = new Int16Array(ab), f = new Float32Array(i16.length);
  for (let i = 0; i < i16.length; i++) f[i] = i16[i] / 32768;
  const b = ac.createBuffer(1, f.length, 24000); b.copyToChannel(f, 0);
  if (!LV.an) { LV.an = ac.createAnalyser(); LV.an.fftSize = 512; LV.an.connect(J.outGain); }
  const src = ac.createBufferSource(); src.buffer = b; src.connect(LV.an);
  const t = Math.max(ac.currentTime + .03, LV.nextT); src.start(t); LV.nextT = t + b.duration;
  LV.srcs.push(src); LV.bufs.push(b);
  src.onended = () => { LV.srcs = LV.srcs.filter(x => x !== src); if (!LV.srcs.length) { LV.playing = false; J.speaking = false; Orb.setSource(J.analyser); duck(false); if (LV.open) setState(J.muted ? 'muted' : 'listening', J.muted ? MUTED_TEXT : 'Listening…'); lvIdle(); } };
  if (!LV.playing) { LV.playing = true; J.speaking = true; Orb.setSource(LV.an); setState('speaking', J.name); trace('speak', 'run'); if (!LV.firstAudio) { LV.firstAudio = performance.now(); const ms = LV.firstAudio - LV.turnT0; if (LV.turnT0 && ms > 0 && ms < 20000) latency(ms); vizFlush('audio'); } }
}
function lvCut(silent) {
  for (const s of LV.srcs) { try { s.stop(); } catch (e) { } }
  LV.srcs = []; LV.nextT = 0; LV.playing = false; J.speaking = false; duck(false);
  if (!silent && LV.open) { setState(J.muted ? 'muted' : 'listening', J.muted ? MUTED_TEXT : 'Listening…'); Orb.setSource(J.analyser); }
}
function latency(ms) { const el = $('#latency'); if (el) { el.textContent = `${(ms / 1000).toFixed(1)} s`; el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash'); } }
function lvEvent(e) {
  switch (e.type) {
    case 'ready':
      LV.ready = true; modePill(); chime(true); setState(J.muted ? 'muted' : 'listening', J.muted ? MUTED_TEXT : 'Listening…'); Orb.setSource(J.analyser); traceReset(); trace('listen', 'run');
      LV.lastVoice = performance.now(); lvIdle();
      for (const x of LV.q.splice(0)) {
        if (x.greet) LV.ws.send(JSON.stringify({ type: 'text', system: true, text: `(The person has just opened the ${J.profile === 'cs' ? 'Chief Secretary' : J.profile} screen. Greet them warmly in one or two short spoken sentences as ${J.name} and say what you can do for them here.${J.profile === 'cs' ? ' Begin with exactly: Hello, Chief Secretary Madam.' : ''} Do not call any function.)` }));
        else if (x.read) lvRead(x.read);
        else typeof x === 'string' ? lvText(x) : lvText(x.system, true);
      }
      break;
    case 'vad':
      if (/START/.test(e.state)) { LV.turnT0 = 0; document.body.classList.add('user-talking'); LV.lastVoice = performance.now(); if (LV.playing) duck(true); }
      else { document.body.classList.remove('user-talking'); LV.turnT0 = performance.now(); LV.firstAudio = 0; }
      break;
    case 'in':
      if (!LV.inTx) { traceReset(); trace('listen', 'done'); trace('hear', 'run'); LV.cutTurn = false; }
      LV.inTx += e.text; captionYou(LV.inTx.trim()); LV.lastVoice = performance.now();
      break;
    case 'tool_start':
      trace('hear', 'done'); trace('think', 'done', e.name.replace(/_/g, ' ')); trace('act', 'run'); setState('thinking', 'Working on it…'); Orb.pulse();
      if ((e.n || 1) > 1 && (Stage.open || LV.viz)) Stage.refine(true);
      break;
    case 'tool': {
      trace('act', 'done');
      if (e.lang && e.lang !== J.lang) { J.lang = e.lang; localStorage.setItem('jv_lang', J.lang); renderLang(); }
      if (e.profile && e.profile !== J.profile) { Portal.flash(e.profile, { from: J.profile }); J.profile = e.profile; localStorage.setItem('jv_profile', J.profile); renderProfile(); clearPanels(); }
      if (e.officer && e.officer !== J.officer) { J.officer = e.officer; localStorage.setItem('jv_officer', J.officer); renderProfile(); }
      const ops = e.ui || [], viz = ops.filter(o => o.op === 'viz');
      applyUi(ops.filter(o => o.op !== 'viz'), viz.length > 0);
      if (viz.length) vizHold(viz[viz.length - 1], e);
      break;
    }
    case 'out':
      if (!LV.outTx) { $('#capJv').innerHTML = ''; LV.firstAudio = LV.firstAudio || 0; }
      vizFlush('speech');
      LV.outTx += e.text; captionLive(e.text); Stage.hear(LV.outTx);
      break;
    case 'interrupted':
      vizDrop(); lvCut(); LV.cutTurn = false; ripple();
      break;
    case 'turn_complete': {
      trace('speak', 'done');
      const clip = LV.pcm.length ? clipBars(LV.pcm, J.inRate) : null; LV.pcm = [];
      vizFlush('turn'); LV.vizShown = false;
      Stage.flush();
      const ex = convoAdd({ you: e.user || LV.inTx, clip: e.user ? clip : null, say: e.mitra || LV.outTx, intent: e.intent, t: Date.now() });
      if (ex) { ex.bufs = LV.bufs.slice(); renderConvo(); }
      LV.bufs = []; LV.inTx = LV.outTx = ''; LV.cutTurn = false; LV.firstAudio = 0; lvIdle();
      break;
    }
    case 'reconfigure': {
      // the profile / officer / language changed: reopen for the new screen; it announces what just happened
      const again = true, say = e.say || '';
      liveClose('reconfigure');
      if (again) setTimeout(() => { liveOpen(); if (say) LV.q.push({ read: say }); }, 300);   // read in full: the acknowledgement and any question it carries
      else if (say) api('/api/tts', { text: say, lang: J.lang }).then(r => speak(say, r.audio_b64, r.tts)).catch(() => { });
      break;
    }
    case 'goaway': liveClose('goaway'); setTimeout(() => liveOpen(), 300); break;
    case 'fallback': {
      // try Live again after 20 s, not 5 min: the server decides how long Live is really off (15 s for a network blip)
      if (!/kannada/i.test(e.reason || '')) { LV.fallbackUntil = Date.now() + 20 * 1000; toast(J.name, 'Live voice is unavailable; using the standard voice for now.'); }
      const pending = LV.q.filter(x => typeof x === 'string');
      liveClose('fallback');
      if (pending.length) turn({ text: pending[pending.length - 1] }); else if (J.mic && !J.muted) startCapture(false, .3);
      break;
    }
  }
}
// live caption: words arrive as they are spoken
function captionLive(text) {
  const el = $('#capJv');
  for (const w of text.split(/\s+/).filter(Boolean)) { const s = document.createElement('span'); s.className = 'w'; s.textContent = w; el.appendChild(s); }
  const box = el.parentElement; box.scrollTop = box.scrollHeight;
}
function ripple() { const r = document.createElement('i'); r.className = 'ripple'; document.querySelector('.orb-wrap').appendChild(r); setTimeout(() => r.remove(), 900); }
setInterval(modePill, 5000);
// duplex meters: your voice and Mitra's voice, both live at the same time
(function dmeters() {
  const you = document.querySelector('.dmeter.you'), me = document.querySelector('.dmeter.me');
  let a = 0, b = 0, buf = null;
  const loop = () => {
    if (LV.open && you && me) {
      a += (Math.min(1, micLevel() * 7) - a) * .3;
      let lv = 0;
      if (LV.an && LV.playing) { buf = buf || new Uint8Array(LV.an.fftSize); LV.an.getByteTimeDomainData(buf); let s2 = 0; for (const v of buf) s2 += (v - 128) * (v - 128); lv = Math.min(1, Math.sqrt(s2 / buf.length) / 128 * 5); }
      b += (lv - b) * .3;
      you.style.setProperty('--l', a.toFixed(3)); me.style.setProperty('--l', b.toFixed(3));
    }
    requestAnimationFrame(loop);
  };
  loop();
})();

// "can you show it as a line graph / donut / bar chart / on the Karnataka map": redraw the last chart, then let Mitra say so
// navigation said in full: 'take me back to the dashboard', 'close the chart', 'bring the chart back' (instant, client-side;
// anything else goes to Mitra, where go_to is a real function)
const NAV_BACK_RX = /^\W*(?:(?:can|could|would|will)\s+you\s+)?(?:please\s+)?(?:just\s+)?(?:(?:close|dismiss|hide|exit|clear)(?:\s+(?:the|this|that))?(?:\s+(?:chart|graph|visual|stage|picture|it))?|(?:take\s+me|take\s+us|go|bring\s+me|get\s+me|return|come)\s+back(?:\s+to)?(?:\s+the)?(?:\s+(?:dashboard|main\s+screen|main\s+view|home(?:\s+screen)?|inbox))?|(?:take\s+me|go|return)\s+to\s+the\s+(?:dashboard|main\s+screen|home\s+screen))(?:\s+please)?\W*$/i;
const NAV_CHART_RX = /^\W*(?:(?:can|could|would|will)\s+you\s+)?(?:please\s+)?(?:(?:bring|show|put|get)\s+(?:the|that|my|me\s+the)?\s*(?:last\s+)?(?:chart|graph|visual|picture)\s+(?:back|again)(?:\s+(?:up|please))?|(?:back\s+to|go\s+back\s+to|return\s+to|take\s+me\s+to)\s+the\s+(?:last\s+)?(?:chart|graph|visual))\W*$/i;
function navByVoice(text) {
  if (Stage.open && NAV_BACK_RX.test(text || '')) { captionYou(text); UI.nav({ target: 'dashboard' }); return true; }
  if (!Stage.open && Stage.last && NAV_CHART_RX.test(text || '')) { captionYou(text); UI.nav({ target: 'chart' }); return true; }
  return false;
}
// a redraw of what is on screen only: 'show IT / THIS / THAT ... as a donut / on the map'; 'show me RDPR on the map' is a new question
const MORPH_RX = /\b(show|switch|change|turn|make|convert|display|see|view|put|draw|render|give)\b\s+(?:me\s+)?(?:it|this|that|them|these|those|the same|the (?:chart|graph|data|numbers|results|picture|board)|everything|all of (?:it|this|that))\b[^.?!]*\b(as|to|into|in|on|like)\b[^.?!]*\b(line|bar|bars|column|donut|pie|ring|map|karnataka)\b|^\W*(line|bar|donut|pie|map|karnataka)\s*(graph|chart|view)?\W*$/i;
function morphByVoice(text) {
  const m = MORPH_RX.exec(text || ''); if (!m) return false;
  const word = (m[3] || m[4] || '').toLowerCase();
  captionYou(text);
  const r = Stage.morph(word); if (!r) return false;
  morphSpoken(r);
  return true;
}
function morphSpoken(r) {
  const name = { bars: 'a bar chart', line: 'a line graph', donut: 'a donut', map: 'the Karnataka map', race: 'a ranking' }[r.kind] || r.kind;
  const line = r.kind === 'map' && !r.ok ? `Here is the Karnataka map. This comparison is by ${r.by || 'category'}, so no single place lights up.` : `Here it is as ${name}.`;
  if (LV.open) lvText(`(The chart on screen was just redrawn as ${name}${r.kind === 'map' && !r.ok ? ', a state view since this comparison is not by place' : ''}. Say one short natural sentence about that, mention the highest value, and do not call any function.)`, true);
  else api('/api/tts', { text: line, lang: J.lang }).then(x => speak(line, x.audio_b64, x.tts)).catch(() => { });
}
window.morphSpoken = morphSpoken;

// ------------------------------------------------------------------ live feed (SSE)
let refreshTimer = null;
function feed(html, cls = '') { const l = $('#feedList'); const el = document.createElement('div'); el.className = 'fi ' + cls; el.innerHTML = html; l.prepend(el); while (l.children.length > 8) l.lastChild.remove(); }
function flashRow(id) { const r = document.querySelector(`.row[data-id="${CSS.escape(id)}"]`); if (r) { r.classList.remove('flash'); void r.offsetWidth; r.classList.add('flash'); } }
function connectEvents() {
  if (new URLSearchParams(location.search).get('noevents')) return;
  if (J.es) { try { J.es.close(); } catch (e) { } }
  const es = new EventSource(`${window.MITRA_BACKEND || ''}/api/events?session=${J.sid}`); J.es = es;
  es.onmessage = ev => {
    const e = JSON.parse(ev.data);
    if (e.type === 'case') {
      const cls = /escalated|rejected|reopened/.test(e.change) ? 'bad' : /nudge|info|atr_flagged|returned/.test(e.change) ? 'warn' : '';
      feed(`<b>${esc(e.id)}</b> ${esc(e.what)}${e.who ? ' · ' + esc(e.who) : ''}`, cls);
      clearTimeout(refreshTimer); refreshTimer = setTimeout(() => { refreshPanels().then(() => flashRow(e.id)); }, 400);
      if (J.profile === 'citizen' && e.mine && !['citizen_reply', 'feedback_yes', 'reopened', 'appeal', 'new'].includes(e.change)) {
        clearTimeout(J.updTimer); J.updTimer = setTimeout(() => announce(citizenUpdates), 500);
      }
    } else if (e.type === 'notif') {
      feed(`<b>${esc(e.to)}</b> ${esc(e.m)}`, 'warn');
    } else if (e.type === 'clock') { $('#clock').textContent = fmtDate(e.now); feed(`<b>clock</b> ${fmtDate(e.now)}`); clearTimeout(refreshTimer); refreshTimer = setTimeout(refreshPanels, 400); }
    else if (e.type === 'notify') { onNotify(e.card); }
    else if (e.type === 'voice_note') {
      const mine = (e.to_role === J.profile) && (e.to_role !== 'officer' || !e.to_officer || e.to_officer === J.officer);
      feed(`<b>voice note</b> ${esc(e.from_role)} → ${esc(e.to_role)}${e.case_id ? ' · ' + esc(e.case_id) : ''}`);
      if (mine) refreshPanels();
    }
  };
  es.onerror = () => { setTimeout(() => { try { es.close(); } catch (x) { } if (J.es === es) connectEvents(); }, 3000); };
}
async function refreshPanels() {
  if (!J.sid || J.busy) return;
  try { const s = await api(`/api/state?session=${J.sid}`, null, 'GET'); applyUi(s.ui || []); } catch (e) { }
}

// ------------------------------------------------------------------ start
async function start() {
  if (J.started) return; J.started = true;
  ensureAudio();
  const auto0 = new URLSearchParams(location.search).get('auto');
  const handover = typeof Splash !== 'undefined' ? Splash.launch({ instant: !!auto0 }) : ($('#splash').classList.add('off'), null); if ('speechSynthesis' in window) { speechSynthesis.getVoices(); speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices(); }
  const auto = new URLSearchParams(location.search).get('auto');
  if (!auto) await initMic();
  if (handover) await handover;                                       // the orb lands, then Mitra greets
  await session(!auto);
  if (!J.es) connectEvents();
  if (!auto && J.wakeOn && J.mic) startWake();
}
$('#start').onclick = start;
// ------------------------------------------------------------------ the web desk <-> the phone app (by voice or by a button)
const INAPP = document.documentElement.classList.contains('inapp');
function pauseEars() { J.paused = true; stopAll(); if (LV.open) liveClose('view'); stopScan(); if (J.wakeRec) { try { J.wakeRec.onend = null; J.wakeRec.abort(); } catch (e) { } J.wakeRec = null; } }
function resumeEars() { J.paused = false; if (J.started && J.wakeOn && J.mic) startWake(); }
function switchView(view, profile, officer) {
  if (view === 'app') {
    if (INAPP) { if (profile !== J.profile) switchTo(profile); return; }              // already the app
    if (typeof Phone === 'undefined') return;
    pauseEars();
    Phone.open({ profile, officer, go: true, onClose: resumeEars });
    return;
  }
  if (INAPP && window.parent !== window) {                                            // the phone hands over to the web desk
    try { stopAll(); if (LV.open) liveClose('view'); } catch (e) { }
    window.parent.postMessage({ mitra: 1, type: 'goto', view: 'web', profile, officer }, location.origin);
    return;
  }
  if (profile !== J.profile) switchTo(profile);                                       // already the web desk
}
window.addEventListener('message', e => {                                             // (parent) the app asked for the web desk
  if (e.origin !== location.origin || !e.data || !e.data.mitra || e.data.type !== 'goto' || INAPP) return;
  const { profile, officer } = e.data;
  Phone.expand(async () => {
    if (officer) { J.officer = officer; localStorage.setItem('jv_officer', officer); }
    if (!J.started) { J.profile = profile; localStorage.setItem('jv_profile', profile); await start(); }
    else { resumeEars(); if (profile !== J.profile) await switchTo(profile); }
  });
});
(async () => {
  try { await boot(); } catch (e) { $('#statusText').textContent = 'Mitra server unreachable'; }
  const q = new URLSearchParams(location.search);
  if (q.get('p')) { J.profile = q.get('p'); }
  if (q.get('off')) { J.officer = q.get('off'); }
  if (q.get('auto') || q.get('go')) start();
})();
