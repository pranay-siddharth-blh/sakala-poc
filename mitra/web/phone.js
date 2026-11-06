/* "Start app": the whole of Mitra on a phone. The start page makes way, a titanium phone rises into the centre and runs the
   real Mitra inside (the same server, the same pipeline, the phone layout of app.js) at a true phone size (393 x 852, scaled
   to fit). Around it: what the app is, and "Behind the app", which follows what Mitra is doing inside the phone (the five
   pipeline steps, what it heard and said, the profile and the voice mode), like the WhatsApp POC's "Behind the chat". */
const Phone = (() => {
  const $ = s => document.querySelector(s);
  const SW = 393, SH = 852;                                       // the phone's screen in CSS pixels (iPhone 16 Pro)
  let root = null;
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const STEPS = [['listen', 'Listen'], ['hear', 'Hear'], ['think', 'Understand'], ['act', 'Act on iPGRS'], ['speak', 'Speak']];
  const ic = {
    signal: '<svg viewBox="0 0 18 12"><rect x="0" y="8" width="3" height="4" rx="1"/><rect x="5" y="5.5" width="3" height="6.5" rx="1"/><rect x="10" y="3" width="3" height="9" rx="1"/><rect x="15" y="0" width="3" height="12" rx="1"/></svg>',
    wifi: '<svg viewBox="0 0 16 12"><path d="M8 11.5l2.2-2.6a3.3 3.3 0 0 0-4.4 0zM3.4 6.4l1.5 1.7a4.8 4.8 0 0 1 6.2 0l1.5-1.7a7 7 0 0 0-9.2 0zM.6 3.4l1.5 1.7a9 9 0 0 1 11.8 0l1.5-1.7a11.2 11.2 0 0 0-14.8 0z"/></svg>',
    batt: '<svg viewBox="0 0 27 12"><rect x=".5" y=".5" width="23" height="11" rx="3.2" fill="none" stroke="currentColor" opacity=".45"/><rect x="2.2" y="2.2" width="18" height="7.6" rx="1.8"/><rect x="24.5" y="4" width="1.8" height="4" rx=".9" opacity=".45"/></svg>',
  };

  let opts = {};
  function open(o = {}) {
    if (root) return;
    opts = o || {};
    document.documentElement.classList.add('phone-on');          // the page behind the phone stands still (it is only a backdrop)
    root = document.createElement('div'); root.id = 'phoneStage'; root.className = 'phone-stage';
    root.innerHTML = `
      <aside class="ps-side ps-l">
        <div class="ps-k"><i></i>Mitra</div>
        <h2>The whole of Mitra,<br><span class="grad">in your hand.</span></h2>
        <p>The same voice, the same pipeline and the same three desks, built for a phone: speak a complaint as a citizen, clear an inbox as an officer, or brief the state as the Chief Secretary.</p>
        <ul class="ps-feats">
          <li><b>🎙</b><span><strong>Talk, don't type</strong>Hold the mic or say “Hey Mitra”.</span></li>
          <li><b>⇅</b><span><strong>Everything one swipe away</strong>Your request, the inbox or the state in a sheet.</span></li>
          <li><b>👤</b><span><strong>Three desks, one app</strong>Switch profile from the top bar.</span></li>
        </ul>
        <button class="ps-back" id="psBack"><span>←</span> Back to start</button>
      </aside>
      <div class="ps-phone" id="psPhone">
        <div class="iph" id="iph">
          <i class="iph-b iph-act"></i><i class="iph-b iph-vu"></i><i class="iph-b iph-vd"></i><i class="iph-b iph-pw"></i><i class="iph-b iph-cam"></i>
          <div class="iph-screen" id="iphScreen">
            <iframe id="iphFrame" title="Mitra app" src="/?app=1&intro=0${opts.profile ? '&p=' + opts.profile : ''}${opts.officer ? '&off=' + encodeURIComponent(opts.officer) : ''}${opts.go ? '&go=1' : ''}" allow="microphone; autoplay; clipboard-write"></iframe>
            <div class="iph-status"><b id="iphTime">9:41</b><span class="iph-ic">${ic.signal}${ic.wifi}${ic.batt}</span></div>
            <div class="iph-island" id="iphIsland"><i></i><span id="iphIslandT"></span></div>
            <div class="iph-home"></div>
          </div>
          <div class="iph-glare"></div>
        </div>
        <div class="ps-floor"></div>
      </div>
      <aside class="ps-side ps-r">
        <div class="ps-k"><i class="live"></i>Behind the app</div>
        <div class="ps-prof" id="psProf"><span class="ps-av">👤</span><span><b>Citizen</b><small>Mitra</small></span><em id="psMode">Standby</em></div>
        <div class="ps-steps" id="psSteps">${STEPS.map(([k, l], i) => `<div class="ps-st" data-k="${k}"><i>${i + 1}</i><span>${l}</span><b></b></div>`).join('')}</div>
        <div class="ps-said"><label>Heard</label><p id="psYou">…</p></div>
        <div class="ps-said"><label>Mitra</label><p id="psJv">Tap Start inside the phone.</p></div>
        <div class="ps-note">Live: the app inside the phone is the real Mitra, on the same server as the web.</div>
      </aside>`;
    const splashUp = !$('#splash').classList.contains('off');
    root.classList.toggle('solo', !splashUp);                          // over the running web desk: its own backdrop
    document.body.classList.add('app-over');
    document.body.appendChild(root);
    fit(); addEventListener('resize', fit);
    clock(); root._clock = setInterval(clock, 15000);
    $('#splash').classList.add('to-app');
    requestAnimationFrame(() => requestAnimationFrame(() => root.classList.add('on')));
    $('#psBack').onclick = close;
    addEventListener('message', onMsg);
    tilt();
  }
  function close() {
    if (!root) return;
    const r = root; root = null;
    document.documentElement.classList.remove('phone-on');
    document.body.classList.remove('app-over');
    const cb = opts.onClose; opts = {};
    if (cb) setTimeout(cb, 500);
    r.classList.remove('on'); r.classList.add('off');
    $('#splash').classList.remove('to-app');
    removeEventListener('message', onMsg); removeEventListener('resize', fit); clearInterval(r._clock);
    setTimeout(() => r.remove(), 900);
  }
  function fit() {
    if (!root) return;
    const sideW = innerWidth > 1180 ? 2 * 330 : 0, availH = innerHeight * .9, availW = innerWidth - sideW - 40;
    const bezel = 14, H = Math.min(availH, 900), s = Math.min((H - 2 * bezel) / SH, (availW - 2 * bezel) / SW, 1.1);
    root.style.setProperty('--s', s.toFixed(4)); root.style.setProperty('--sw', SW + 'px'); root.style.setProperty('--sh', SH + 'px');
  }
  function clock() { const d = new Date(); const t = $('#iphTime'); if (t) t.textContent = `${d.getHours() % 12 || 12}:${String(d.getMinutes()).padStart(2, '0')}`; }
  function tilt() {                                                  // the phone leans a little towards the pointer
    root.addEventListener('pointermove', e => {
      const ph = $('#iph'); if (!ph || e.target.closest('iframe')) return;
      const x = e.clientX / innerWidth - .5, y = e.clientY / innerHeight - .5;
      ph.style.setProperty('--rx', (-y * 6).toFixed(2) + 'deg'); ph.style.setProperty('--ry', (x * 8).toFixed(2) + 'deg');
    });
  }
  const PROF = { Citizen: '👤', Officer: '🧑‍💼', 'Chief Secretary': '🏛️' };
  function onMsg(e) {
    if (e.origin !== location.origin || !e.data || !e.data.mitra || !root) return;
    const m = e.data;
    if (m.type === 'trace') {
      for (const s of m.steps || []) {
        const el = root.querySelector(`.ps-st[data-k="${s.k}"]`); if (!el) continue;
        el.className = 'ps-st ' + (s.st || ''); el.querySelector('b').textContent = s.note || '';
      }
      const run = (m.steps || []).find(s => /run/.test(s.st || ''));
      island(run ? (STEPS.find(x => x[0] === run.k) || ['', ''])[1] : '');
    } else if (m.type === 'you') { $('#psYou').textContent = m.text || '…'; }
    else if (m.type === 'jv') { if (m.text) $('#psJv').textContent = m.text; }
    else if (m.type === 'profile') {
      root.querySelector('.ps-prof b').textContent = m.name; root.querySelector('.ps-prof small').textContent = m.sub || '';
      root.querySelector('.ps-av').textContent = PROF[m.name] || '👤';
    } else if (m.type === 'mode') { $('#psMode').textContent = (m.text || '').trim() || m.m; $('#psMode').dataset.m = m.m || ''; }
    else if (m.type === 'state') { const isl = $('#iphIsland'); if (isl) isl.dataset.state = m.state || ''; }
  }
  function island(text) {                                            // the Dynamic Island widens with what Mitra is doing
    const isl = $('#iphIsland'); if (!isl) return;
    isl.classList.toggle('wide', !!text); $('#iphIslandT').textContent = text || '';
  }
  // the phone grows into the web desk, then the desk takes over (voice: "switch me to the web view")
  function expand(then) {
    if (!root) { then && then(); return; }
    const r = root; root = null; opts = {};
    document.documentElement.classList.remove('phone-on');        // the desk behind wakes up: orb, cards, animations
    r.classList.add('expand');
    $('#splash').classList.remove('to-app');
    document.body.classList.remove('app-over');
    removeEventListener('message', onMsg); removeEventListener('resize', fit); clearInterval(r._clock);
    setTimeout(() => { then && then(); }, 650);
    setTimeout(() => r.remove(), 1300);
  }
  return { open, close, expand };
})();

document.getElementById('startApp')?.addEventListener('click', () => Phone.open());
