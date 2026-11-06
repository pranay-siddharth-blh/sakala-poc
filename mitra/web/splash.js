/* Splash: the first second of Mitra. A breathing particle orb sits behind the title and leans towards Start; behind it the
   31 districts of Karnataka turn slowly as an emerald wireframe floor, with signals pulsing in from district after district.
   A short cinematic intro (logo traced in light, halo spins up, the title blurs in letter by letter, Start rises) plays on a
   fresh visit (skipped on a reload in the same tab, with reduced motion, or when ?intro=0). Pressing Start plays a rising
   chord while the orb rushes forward and lands exactly where the live orb is, so the splash hands over without a cut. */
const Splash = (() => {
  const $ = s => document.querySelector(s);
  const root = $('#splash'); if (!root) return { launch: () => { } };
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const q = new URLSearchParams(location.search);
  const dpr = Math.min(2, devicePixelRatio || 1);
  let raf = 0, alive = true, t0 = performance.now(), launching = 0;

  // ------------------------------------------------------------------ greeting (by the hour; "Madam" on the CS screen)
  (function greet() {
    const h = new Date().getHours(), prof = q.get('p') || (() => { try { return localStorage.getItem('jv_profile'); } catch (e) { return ''; } })();
    const [en, kn] = h >= 5 && h < 12 ? ['Good morning', 'ಶುಭೋದಯ'] : h >= 12 && h < 17 ? ['Good afternoon', 'ಶುಭ ಮಧ್ಯಾಹ್ನ'] : h >= 17 && h < 22 ? ['Good evening', 'ಶುಭ ಸಂಜೆ'] : ['Namaskara', 'ನಮಸ್ಕಾರ'];
    const el = $('#spGreet'); if (el) el.innerHTML = `<b>${en}${prof === 'cs' ? ', Chief Secretary Madam' : ''}</b><span class="kn">${kn}</span>`;
  })();

  // ------------------------------------------------------------------ title, letter by letter (gradient kept across "Mitra")
  (function letters() {
    const h1 = $('#spTitle'); if (!h1) return;
    const wrap = (node, cls) => [...node.textContent].map(ch => ch === ' ' ? ' ' : `<i class="ch${cls ? ' ' + cls : ''}">${ch}</i>`).join('');
    const g = h1.querySelector('.grad'), word = g ? g.textContent : '';
    const lead = h1.childNodes[0] && h1.childNodes[0].nodeType === 3 ? h1.childNodes[0].textContent : '';
    h1.innerHTML = wrap({ textContent: lead }) + (g ? `<span class="grad-l">${wrap({ textContent: word }, 'gl')}</span>` : '');
    h1.querySelectorAll('.ch').forEach((c, i) => c.style.setProperty('--i', i));
    const fit = () => {                                   // one gradient spread over the whole word, each letter showing its slice
      const gl = [...h1.querySelectorAll('.gl')]; if (!gl.length) return;
      const x0 = gl[0].offsetLeft, w = gl[gl.length - 1].offsetLeft + gl[gl.length - 1].offsetWidth - x0;
      gl.forEach(c => { c.style.backgroundSize = `${w}px 100%`; c.style.backgroundPosition = `${x0 - c.offsetLeft}px 0`; });
    };
    (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(fit); setTimeout(fit, 300); addEventListener('resize', fit);
  })();

  // ------------------------------------------------------------------ intro (fresh visit) or straight in
  const intro = document.documentElement.dataset.intro === '1';          // decided in <head>, before the first paint
  root.classList.add(intro ? 'intro' : 'nointro');

  // ------------------------------------------------------------------ the map floor
  const mapCv = $('#spMap'), mctx = mapCv && mapCv.getContext('2d');
  const D = (typeof KA_DIST !== 'undefined' ? KA_DIST : []).map(d => {
    const nums = d.d.match(/-?\d+(\.\d+)?/g).map(Number); let sx = 0, sy = 0, n = 0;
    for (let i = 0; i + 1 < nums.length; i += 2) { sx += nums[i]; sy += nums[i + 1]; n++; }
    return { n: d.n, p: new Path2D(d.d), cx: sx / n, cy: sy / n, lit: 0, col: '22,199,132' };
  });
  const W0 = typeof KA_WORLD !== 'undefined' ? KA_WORLD : [0, 0, 1000, 1560];
  const pulses = [];
  let nextPulse = 0;
  function sizeMap() {
    if (!mapCv) return;
    const r = mapCv.getBoundingClientRect();
    mapCv.width = Math.round(r.width * dpr); mapCv.height = Math.round(r.height * dpr);
  }
  function drawMap(now) {
    if (!mctx || !D.length) return;
    const W = mapCv.width / dpr, H = mapCv.height / dpr;
    const light = document.documentElement.dataset.theme === 'light';
    mctx.setTransform(dpr, 0, 0, dpr, 0, 0); mctx.clearRect(0, 0, W, H);
    const ww = W0[2] - W0[0], wh = W0[3] - W0[1], k = Math.min(W / ww, H / wh) * .94;
    mctx.save(); mctx.translate((W - ww * k) / 2 - W0[0] * k, (H - wh * k) / 2 - W0[1] * k); mctx.scale(k, k);
    if (now > nextPulse && D.length) {                      // a signal arrives somewhere in the state
      const d = D[Math.floor(Math.random() * D.length)], r = Math.random();
      d.col = r < .72 ? '22,199,132' : r < .9 ? '121,227,255' : '255,154,60'; d.lit = 1;
      pulses.push({ x: d.cx, y: d.cy, t: now, col: d.col });
      nextPulse = now + 260 + Math.random() * 520;
    }
    const base = light ? 'rgba(14,159,110,.32)' : 'rgba(22,199,132,.26)';
    mctx.lineJoin = 'round';
    for (const d of D) {
      d.lit *= .975;
      if (d.lit > .02) { mctx.fillStyle = `rgba(${d.col},${(d.lit * (light ? .16 : .12)).toFixed(3)})`; mctx.fill(d.p); }
      mctx.strokeStyle = d.lit > .02 ? `rgba(${d.col},${(.3 + d.lit * .6).toFixed(3)})` : base;
      mctx.lineWidth = (d.lit > .02 ? 1.6 + d.lit * 1.6 : 1.1) / k * 1.4; mctx.stroke(d.p);
    }
    for (let i = pulses.length - 1; i >= 0; i--) {
      const p = pulses[i], a = (now - p.t) / 1700; if (a >= 1) { pulses.splice(i, 1); continue; }
      const r = (6 + a * 70) / k * 1.6;
      mctx.beginPath(); mctx.arc(p.x, p.y, r, 0, 6.283); mctx.strokeStyle = `rgba(${p.col},${(1 - a) * .8})`; mctx.lineWidth = 2 / k * 1.4; mctx.stroke();
      mctx.beginPath(); mctx.arc(p.x, p.y, 3.2 / k * 1.6, 0, 6.283); mctx.fillStyle = `rgba(${p.col},${1 - a})`; mctx.fill();
    }
    mctx.restore();
  }

  // ------------------------------------------------------------------ the orb (same idea as the live core: a fibonacci sphere of light)
  const orbCv = $('#spOrb'), octx = orbCv && orbCv.getContext('2d');
  const N = 820, P = [];
  for (let i = 0; i < N; i++) { const y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(1 - y * y), th = i * 2.399963; P.push([Math.cos(th) * r, y, Math.sin(th) * r]); }
  const lean = { x: 0, y: 0, tx: 0, ty: 0, k: 0, tk: 0 };
  function sizeOrb() { if (!orbCv) return; const r = orbCv.getBoundingClientRect(); orbCv.width = Math.round(r.width * dpr); orbCv.height = Math.round(r.height * dpr); }
  function drawOrb(now) {
    if (!octx) return;
    const W = orbCv.width / dpr, H = orbCv.height / dpr, t = (now - t0) / 1000;
    octx.setTransform(dpr, 0, 0, dpr, 0, 0); octx.clearRect(0, 0, W, H);
    lean.x += (lean.tx - lean.x) * .06; lean.y += (lean.ty - lean.y) * .06; lean.k += (lean.tk - lean.k) * .05;
    const boost = launching ? Math.min(1, (now - launching) / 700) : 0;
    const R = Math.min(W, H) * .30 * (1 + Math.sin(t * 1.1) * .025 + lean.k * .05 + boost * .12);
    const cx = W / 2 + lean.x * R * .22, cy = H / 2 + lean.y * R * .22;
    const ry = t * .22, rx = .38 + lean.y * .25, cyr = Math.cos(ry), syr = Math.sin(ry), cxr = Math.cos(rx), sxr = Math.sin(rx);
    const g = octx.createRadialGradient(cx, cy, 0, cx, cy, R * 1.6);
    g.addColorStop(0, `rgba(22,199,132,${.16 + lean.k * .08 + boost * .2})`); g.addColorStop(.5, 'rgba(121,227,255,.05)'); g.addColorStop(1, 'rgba(0,0,0,0)');
    octx.fillStyle = g; octx.fillRect(0, 0, W, H);
    const LT = document.documentElement.dataset.theme === 'light';
    octx.globalCompositeOperation = LT ? 'source-over' : 'lighter';
    for (let i = 0; i < N; i++) {
      let [x, y, z] = P[i];
      const x1 = x * cyr + z * syr, z1 = -x * syr + z * cyr, y1 = y * cxr - z1 * sxr, z2 = y * sxr + z1 * cxr;
      const wob = 1 + Math.sin(t * 2 + i * .37) * .015 + (lean.k * .08) * Math.max(0, x1 * lean.x + y1 * lean.y);
      const s = 1.9 / (2.6 - z2), px = cx + x1 * R * wob * s, py = cy + y1 * R * wob * s;
      const a = .26 + (z2 + 1) * .4, sz = (.8 + (z2 + 1) * .95) * (1 + boost * .6);
      octx.fillStyle = LT ? (i % 9 === 0 ? `rgba(43,127,217,${a})` : i % 23 === 0 ? `rgba(234,106,34,${a * .9})` : `rgba(14,150,104,${a})`)
                         : (i % 9 === 0 ? `rgba(121,227,255,${a})` : i % 23 === 0 ? `rgba(255,154,60,${a * .9})` : `rgba(22,199,132,${a})`);
      octx.fillRect(px - sz / 2, py - sz / 2, sz, sz);
    }
    octx.globalCompositeOperation = 'source-over';
    octx.strokeStyle = `rgba(22,199,132,${.18 + lean.k * .2})`; octx.lineWidth = 1;
    octx.beginPath(); octx.arc(cx, cy, R * 1.18, 0, 6.283); octx.stroke();
    octx.setLineDash([2, 7]); octx.strokeStyle = 'rgba(121,227,255,.22)';
    octx.beginPath(); octx.arc(cx, cy, R * 1.34, t * .3, t * .3 + 6.283); octx.stroke(); octx.setLineDash([]);
  }

  function frame(now) {
    if (!alive) return;
    raf = requestAnimationFrame(frame);
    if (document.hidden || document.documentElement.classList.contains('phone-on')) return;   // frozen behind the phone
    drawMap(now); drawOrb(now);
  }
  sizeMap(); sizeOrb(); addEventListener('resize', () => { sizeMap(); sizeOrb(); });
  raf = requestAnimationFrame(frame);

  // the orb leans towards the pointer, and towards Start when you are about to press it
  root.addEventListener('pointermove', e => {
    if (!orbCv) return;
    const r = orbCv.getBoundingClientRect();
    lean.tx = Math.max(-1, Math.min(1, (e.clientX - (r.left + r.width / 2)) / (r.width / 2)));
    lean.ty = Math.max(-1, Math.min(1, (e.clientY - (r.top + r.height / 2)) / (r.height / 2)));
    root.style.setProperty('--mx', (e.clientX / innerWidth - .5).toFixed(3)); root.style.setProperty('--my', (e.clientY / innerHeight - .5).toFixed(3));
  }, { passive: true });
  const btn = $('#start');
  if (btn) { btn.addEventListener('pointerenter', () => { lean.tk = 1; root.classList.add('ready'); }); btn.addEventListener('pointerleave', () => { lean.tk = 0; root.classList.remove('ready'); }); }

  // ------------------------------------------------------------------ the chord: switching something on
  function chord() {
    try {
      const ac = window.ensureAudio ? ensureAudio() : null; if (!ac) return;
      const t = ac.currentTime, out = ac.createGain(), lp = ac.createBiquadFilter();
      lp.type = 'lowpass'; lp.frequency.setValueAtTime(500, t); lp.frequency.exponentialRampToValueAtTime(5200, t + 1.1);
      out.gain.setValueAtTime(0, t); out.gain.linearRampToValueAtTime(.07, t + .25); out.gain.exponentialRampToValueAtTime(.0001, t + 2.1);
      lp.connect(out); out.connect(ac.destination);
      [[261.63, 392], [329.63, 493.88], [392, 587.33], [523.25, 783.99]].forEach(([a, b], i) => {   // C major rising to G major, softly
        const o = ac.createOscillator(); o.type = i === 3 ? 'sine' : 'triangle';
        o.frequency.setValueAtTime(a, t + i * .06); o.frequency.exponentialRampToValueAtTime(b, t + .9 + i * .05);
        const g = ac.createGain(); g.gain.value = i === 3 ? .5 : .32; o.connect(g); g.connect(lp); o.start(t + i * .06); o.stop(t + 2.2);
      });
      const s = ac.createOscillator(), sg = ac.createGain(); s.type = 'sine'; s.frequency.setValueAtTime(1567.98, t + .55);
      sg.gain.setValueAtTime(0, t + .55); sg.gain.linearRampToValueAtTime(.025, t + .62); sg.gain.exponentialRampToValueAtTime(.0001, t + 1.8);
      s.connect(sg); sg.connect(ac.destination); s.start(t + .55); s.stop(t + 1.85);
    } catch (e) { }
  }

  // ------------------------------------------------------------------ Start: the orb rushes forward and becomes the live one
  function launch({ instant = false } = {}) {
    if (instant || reduced || !orbCv) { finish(); return Promise.resolve(); }
    launching = performance.now(); chord();
    root.classList.add('launch');
    const from = orbCv.getBoundingClientRect(), live = document.querySelector('#orb'), to = live ? live.getBoundingClientRect() : from;
    const sc = (to.width || from.width) / from.width;
    const dx = (to.left + to.width / 2) - (from.left + from.width / 2), dy = (to.top + to.height / 2) - (from.top + from.height / 2);
    orbCv.animate([
      { transform: 'translate(0,0) scale(1)', filter: 'brightness(1)' },
      { transform: `translate(${dx * .15}px,${dy * .15}px) scale(1.35)`, filter: 'brightness(1.8)', offset: .35 },
      { transform: `translate(${dx}px,${dy}px) scale(${sc})`, filter: 'brightness(1)' },
    ], { duration: 1150, easing: 'cubic-bezier(.65,0,.25,1)', fill: 'forwards' });
    return new Promise(res => setTimeout(() => { finish(); res(); }, 1050));
  }
  function finish() {
    root.classList.add('off');
    setTimeout(() => { alive = false; cancelAnimationFrame(raf); root.classList.add('gone'); }, 900);   // gone: no layer, no animation left running
  }
  return { launch };
})();
