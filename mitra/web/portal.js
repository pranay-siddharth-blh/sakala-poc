/* Portal: the transition between profiles (Citizen ⇄ Officer ⇄ Chief Secretary, and logging in as another officer).
   Like the sister POCs' "Opening …" overlay, in Mitra's palette and more cinematic: an iris opens from where you clicked,
   warp streaks rush outward, two counter-rotating rings circle the Sakala mark and the destination's icon, a route beam
   runs from the old profile to the new one, the new screen is built underneath, then the iris closes on the centre and
   the new screen rises into place. Portal.run(to, work) waits for `work` (the screen swap) and never shows for less than
   ~1.2 s; Portal.flash(to) covers a swap that has already happened (a voice switch). */
const Portal = (() => {
  const META = {
    citizen: { icon: '👤', name: 'Citizen', title: 'Opening the Citizen desk', sub: 'Speak a complaint · track your requests', rgb: '121,227,255' },
    officer: { icon: '🧑‍💼', name: 'Officer', title: 'Opening the Officer desk', sub: 'Inbox · reports · decisions', rgb: '22,199,132' },
    cs:      { icon: '🏛️', name: 'Chief Secretary', title: 'Opening the Chief Secretary desk', sub: 'The state at a glance', rgb: '255,154,60' },
  };
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const MIN = reduced ? 300 : 1250;
  let el = null, busy = 0, endT = null;

  function build() {
    if (el) return el;
    el = document.createElement('div'); el.id = 'portal'; el.className = 'portal'; el.setAttribute('aria-hidden', 'true');
    const streaks = Array.from({ length: 48 }, (_, i) => `<i style="--a:${(i * 7.5 + Math.random() * 4).toFixed(1)}deg;--d:${(Math.random() * .6).toFixed(2)}s;--l:${(30 + Math.random() * 40).toFixed(0)}vmax"></i>`).join('');
    el.innerHTML = `<div class="pt-grid"></div><div class="pt-warp">${streaks}</div>
      <div class="pt-core">
        <div class="pt-marks"><div class="pt-rings"><span class="r1"></span><span class="r2"></span><span class="r3"></span></div><span class="pt-halo"><img src="/assets/sakala-logo.svg" alt=""></span><span class="pt-halo pt-to"><b id="ptIcon"></b></span></div>
        <div class="pt-text"><b id="ptTitle"></b><small id="ptSub"></small></div>
        <div class="pt-route"><span id="ptFrom"></span><i><em></em></i><span id="ptTo"></span></div>
        <div class="pt-bar"><i></i></div>
      </div>`;
    document.body.appendChild(el);
    return el;
  }
  function whoosh(rgb) {
    try {
      const ac = window.ensureAudio ? ensureAudio() : null; if (!ac) return;
      const t = ac.currentTime, o = ac.createOscillator(), g = ac.createGain(), f = ac.createBiquadFilter();
      o.type = 'sawtooth'; o.frequency.setValueAtTime(110, t); o.frequency.exponentialRampToValueAtTime(660, t + .55);
      f.type = 'lowpass'; f.frequency.setValueAtTime(400, t); f.frequency.exponentialRampToValueAtTime(2400, t + .5);
      g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(.045, t + .12); g.gain.exponentialRampToValueAtTime(.0001, t + .8);
      o.connect(f); f.connect(g); g.connect(ac.destination); o.start(t); o.stop(t + .85);
      const o2 = ac.createOscillator(), g2 = ac.createGain(); o2.type = 'sine'; o2.frequency.setValueAtTime(880, t + .5); o2.frequency.exponentialRampToValueAtTime(1320, t + .7);
      g2.gain.setValueAtTime(0, t + .5); g2.gain.linearRampToValueAtTime(.05, t + .53); g2.gain.exponentialRampToValueAtTime(.0001, t + 1); o2.connect(g2); g2.connect(ac.destination); o2.start(t + .5); o2.stop(t + 1.05);
    } catch (_) { }
  }
  function origin() {
    const b = document.querySelector('#profBtn');
    if (!b) return [innerWidth / 2, innerHeight / 2];
    const r = b.getBoundingClientRect(); return [r.left + 24, r.top + r.height / 2];
  }
  function cover(to, { from = null, title = null, sub = null } = {}) {
    const m = META[to] || META.citizen, f = META[from] || null, p = build();
    clearTimeout(endT); busy++;
    p.style.setProperty('--prgb', m.rgb); p.style.setProperty('--frgb', f ? f.rgb : m.rgb);
    const [ox, oy] = origin(); p.style.setProperty('--ox', ox + 'px'); p.style.setProperty('--oy', oy + 'px');
    p.querySelector('#ptIcon').textContent = m.icon;
    p.querySelector('#ptTitle').textContent = title || m.title;
    p.querySelector('#ptSub').textContent = sub || m.sub;
    p.querySelector('#ptFrom').textContent = f ? f.name : 'Mitra';
    p.querySelector('#ptTo').textContent = m.name;
    p.classList.remove('out', 'in'); void p.offsetWidth; p.classList.add('in');
    document.body.classList.remove('portal-in'); document.body.classList.add('portal-out');
    whoosh(m.rgb);
    return performance.now();
  }
  function reveal() {
    if (--busy > 0) return;
    const p = build();
    document.body.classList.remove('portal-out'); document.body.classList.add('portal-in');
    p.classList.add('out');
    endT = setTimeout(() => { p.classList.remove('in', 'out'); document.body.classList.remove('portal-in'); }, reduced ? 200 : 900);
  }
  // swap the screen behind the portal; `work` builds the new profile
  async function run(to, work, opts = {}) {
    const t0 = cover(to, opts);
    try { await work(); } catch (e) { console.error('portal work', e); }
    const left = MIN - (performance.now() - t0); if (left > 0) await new Promise(r => setTimeout(r, left));
    reveal();
  }
  // the swap has already happened (a voice switch): cover it briefly, then reveal
  function flash(to, opts = {}) { cover(to, opts); setTimeout(reveal, MIN); }
  return { run, flash, META, get busy() { return busy > 0; } };
})();
