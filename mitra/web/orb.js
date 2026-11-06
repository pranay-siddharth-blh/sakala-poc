/* The Mitra core: a 3D particle sphere (fibonacci lattice, perspective projection) that breathes when idle,
   swells with your voice, swirls while thinking and pulses with its own voice; a frequency halo around it is
   driven by the live microphone or by Mitra's audio. Canvas 2D, additive light, 60 fps.
   It is also something you can touch: hover and the particles lean towards the pointer; press and drag and the
   sphere spins with you (with momentum); press and pull and it stretches like jelly and springs back; a tap
   wakes Mitra (or silences it while it is talking). */
const Orb = (() => {
  const cv = document.getElementById('orb');
  const ctx = cv.getContext('2d');
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  let state = 'idle', level = 0, smooth = 0, an = null, fbuf = null, t0 = performance.now();
  let rotY = 0, rotX = .35, spin = .12, wake = 0;
  const PAL = {
    idle:      [[22, 199, 132], [59, 155, 255]],
    muted:     [[118, 122, 136], [72, 76, 90]],
    hearing:   [[90, 210, 230], [40, 170, 150]],
    listening: [[121, 227, 255], [22, 199, 132]],
    thinking:  [[255, 154, 60], [255, 205, 0]],
    speaking:  [[22, 199, 132], [255, 154, 60]],
    off:       [[80, 84, 96], [50, 52, 60]]
  };
  let col = PAL.idle.map(c => c.slice());
  const N = 1700, pts = [];
  for (let i = 0; i < N; i++) {
    const y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(1 - y * y), th = Math.PI * (3 - Math.sqrt(5)) * i;
    pts.push({ x: Math.cos(th) * r, y, z: Math.sin(th) * r, s: Math.random(), k: Math.random() * 6.28 });
  }
  const sparks = Array.from({ length: 70 }, () => ({ a: Math.random() * 6.28, r: 1.25 + Math.random() * .9, v: .1 + Math.random() * .4, y: (Math.random() - .5) * .8, s: Math.random() }));
  const bursts = [];                                     // short-lived particles fired outwards on a big moment (a case routed)

  function size() { const r = cv.getBoundingClientRect(); cv.width = Math.max(10, r.width * dpr); cv.height = Math.max(10, r.height * dpr); }
  window.addEventListener('resize', size); size();

  const lerp = (a, b, k) => a + (b - a) * k;
  function rgba(c, a) { return `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`; }
  // particle batches: 2 colours x 8 alpha steps, each drawn as one path with one fill (no per-particle strings or state changes)
  const NB_A = 8, batch = Array.from({ length: 2 * NB_A }, () => []);
  let lastLvl = -1, skip = 0;

  // ---- pointer: hover lean, drag-to-spin with momentum, pull-and-release spring, tap
  const P = { over: false, down: false, drag: false, x: 0, y: 0, lx: 0, ly: 0, dx: 0, dy: 0, vy: 0, vx: 0, t: 0,
              pullX: 0, pullY: 0, pvx: 0, pvy: 0, tx: 0, ty: 0, squash: 0, grab: 0 };
  let onTap = null;
  function pos(e) { const r = cv.getBoundingClientRect(); P.x = (e.clientX - r.left) * dpr; P.y = (e.clientY - r.top) * dpr; }
  cv.addEventListener('pointerenter', e => { P.over = true; pos(e); });
  cv.addEventListener('pointerleave', () => { P.over = false; if (!P.down) { P.tx = P.ty = 0; } });
  cv.addEventListener('pointerdown', e => {
    e.preventDefault(); try { cv.setPointerCapture(e.pointerId); } catch (_) { } pos(e);
    P.down = true; P.drag = false; P.lx = P.x; P.ly = P.y; P.t = performance.now(); P.vx = P.vy = 0; P.dx = P.dy = 0; P.grab = 1;
  });
  cv.addEventListener('pointermove', e => {
    pos(e); if (!P.down) return;
    const mx = P.x - P.lx, my = P.y - P.ly; P.lx = P.x; P.ly = P.y;
    P.dx += mx; P.dy += my;
    if (!P.drag && Math.hypot(P.dx, P.dy) > 6 * dpr) P.drag = true;
    if (P.drag) {
      const W = cv.width, R = Math.min(W, cv.height) * .25;
      // horizontal motion spins it, vertical motion tilts it; the sphere also stretches toward the pointer
      P.vy = lerp(P.vy, (mx / R) * 2.2, .5); P.vx = lerp(P.vx, (my / R) * 1.4, .5);
      rotY += P.vy / 6; rotX = Math.max(-1.2, Math.min(1.2, rotX + P.vx / 6));
      const cx = W / 2, cy = cv.height / 2;
      P.tx = Math.max(-.6, Math.min(.6, (P.x - cx) / R * .32)); P.ty = Math.max(-.6, Math.min(.6, (P.y - cy) / R * .32));
    }
  });
  function release(e) {
    if (!P.down) return; P.down = false; P.grab = 0;
    try { cv.releasePointerCapture(e.pointerId); } catch (_) { }
    if (!P.drag && performance.now() - P.t < 450) { wake = Math.max(wake, .8); if (onTap) onTap(); }
    P.drag = false; P.tx = P.ty = 0;                      // the spring takes it home
  }
  cv.addEventListener('pointerup', release); cv.addEventListener('pointercancel', release);

  function frame() {
    const de = document.documentElement;                     // hidden (start screen up, phone open over it, tab in the background): skip
    if (de.classList.contains('phone-on') && !document.getElementById('phoneStage')) de.classList.remove('phone-on');   // never frozen without a phone on top
    if (document.hidden || de.classList.contains('phone-on') || (de.dataset.started !== '1' && document.querySelector('#splash:not(.off)'))) { requestAnimationFrame(frame); return; }
    if (document.body.classList.contains('stage-on') && !P.down && (skip ^= 1)) { requestAnimationFrame(frame); return; }   // small corner icon: 30 fps
    const now = performance.now(), t = (now - t0) / 1000;
    const W = cv.width, H = cv.height, cx = W / 2, cy = H / 2, R = Math.min(W, H) * .25;
    // live audio level and spectrum
    let bands = null;
    if (an) {
      if (!fbuf || fbuf.length !== an.frequencyBinCount) fbuf = new Uint8Array(an.frequencyBinCount);
      an.getByteFrequencyData(fbuf); bands = fbuf;
      let s = 0; for (let i = 2; i < 64; i++) s += fbuf[i]; level = Math.max(level * .9, s / 62 / 255 * 1.6);
    }
    smooth += (level - smooth) * (level > smooth ? .3 : .06);
    wake *= .94;
    const target = PAL[state] || PAL.idle;
    for (let j = 0; j < 2; j++) for (let k = 0; k < 3; k++) col[j][k] = lerp(col[j][k], target[j][k], .06);
    // rotation: its own slow spin, plus whatever momentum the hand left behind
    const spinT = state === 'thinking' ? .9 : state === 'speaking' ? .35 : state === 'listening' ? .22 : state === 'muted' ? .04 : .1;
    spin = lerp(spin, spinT, .03);
    if (!P.drag) {
      rotY += spin / 60 + P.vy / 6; rotX = lerp(rotX, .35 + Math.sin(t * .3) * .12, .02) + P.vx / 6;
      P.vy *= .955; P.vx *= .955;
    }
    // pull: a damped spring towards the pointer while pressed, back to centre once released (it overshoots)
    const kx = P.tx - P.pullX, ky = P.ty - P.pullY;
    P.pvx = (P.pvx + kx * .16) * .78; P.pvy = (P.pvy + ky * .16) * .78;
    P.pullX += P.pvx; P.pullY += P.pvy;
    const pullLen = Math.hypot(P.pullX, P.pullY), ux = pullLen > 1e-4 ? P.pullX / pullLen : 0, uy = pullLen > 1e-4 ? P.pullY / pullLen : 0;
    P.squash = lerp(P.squash, P.grab * .08, .12);
    // hover: how close the pointer is to the sphere, 0..1
    const hov = P.over && !P.down ? Math.max(0, 1 - Math.hypot(P.x - cx, P.y - cy) / (R * 1.6)) : 0;

    ctx.clearRect(0, 0, W, H);
    const LIGHT = document.documentElement.dataset.theme === 'light';
    const deep = c => LIGHT ? [c[0] * .74, c[1] * .74, c[2] * .74] : c;     // on a light page the particles are inked, not lit
    // ambient glow (follows the pull)
    const gx = cx + P.pullX * R * .6, gy = cy + P.pullY * R * .6;
    const gl = ctx.createRadialGradient(gx, gy, R * .2, gx, gy, R * (2.4 + smooth * 1.2 + wake + hov * .3));
    const gk = LIGHT ? .55 : 1;
    gl.addColorStop(0, rgba(col[0], (.30 + smooth * .3 + wake * .3 + hov * .08) * gk)); gl.addColorStop(.5, rgba(col[1], (.08 + smooth * .08) * gk)); gl.addColorStop(1, LIGHT ? 'rgba(255,255,255,0)' : 'rgba(0,0,0,0)');
    ctx.fillStyle = gl; ctx.fillRect(0, 0, W, H);

    ctx.globalCompositeOperation = LIGHT ? 'source-over' : 'lighter';
    const amp = state === 'idle' ? .035 + Math.sin(t * 1.3) * .015 : state === 'thinking' ? .08 : .05 + smooth * .42;
    const sy = Math.sin(rotY), cyy = Math.cos(rotY), sx = Math.sin(rotX), cxx = Math.cos(rotX);
    const f = 2.6, hovR = R * .5;
    for (const b of batch) b.length = 0;
    for (const p of pts) {
      // organic displacement
      const n = Math.sin(p.x * 3.1 + t * 1.4 + p.k) * .5 + Math.sin(p.y * 4.3 - t * 1.1) * .3 + Math.sin(p.z * 5.7 + t * 2.3) * .2;
      let d = 1 + n * amp + (state === 'thinking' ? Math.sin(p.y * 10 + t * 6) * .025 : 0);
      if (bands && (state === 'speaking' || state === 'listening' || state === 'hearing')) d += (bands[4 + ((p.s * 60) | 0)] / 255) * .22 * (.5 + p.s);
      let x = p.x * d, y = p.y * d, z = p.z * d;
      const x1 = x * cyy - z * sy, z1 = x * sy + z * cyy;
      let y1 = y * cxx - z1 * sx; const z2 = y * sx + z1 * cxx;
      let xx = x1;
      // jelly: the side facing the pull stretches most, the far side follows a little; squash across the pull
      if (pullLen > 1e-3) {
        const side = xx * ux + y1 * uy;                   // -1 far side .. +1 pull side
        const w = .35 + .65 * (side + 1) / 2;
        xx += P.pullX * w * 1.1; y1 += P.pullY * w * 1.1;
        const perp = -xx * uy + y1 * ux;                   // component across the pull
        xx -= -uy * perp * pullLen * .35; y1 -= ux * perp * pullLen * .35;
      }
      if (P.squash > 1e-3) { xx *= 1 + P.squash; y1 *= 1 - P.squash * .6; }
      const sc = f / (f + z2);
      let px = cx + xx * R * sc, py = cy + y1 * R * sc;
      const depth = (1 - z2) / 2;                         // 0 back .. 1 front
      let a = (.10 + depth * .75) * (.6 + smooth * .6), lift = 0;
      // hover: particles under the pointer lean out towards it and brighten
      if (hov > 0 && depth > .4) {
        const ddx = P.x - px, ddy = P.y - py, dd = Math.hypot(ddx, ddy);
        if (dd < hovR) { lift = (1 - dd / hovR) * hov; px += ddx / (dd + 1) * lift * R * .18; py += ddy / (dd + 1) * lift * R * .18; a += lift * .5; }
      }
      const sz = (.7 + depth * 1.9 + p.s * .6 + lift * 1.4) * dpr * (LIGHT ? 1.08 : 1);
      const al = Math.min(1, LIGHT ? a * 1.05 + .05 : a);
      batch[(depth > .55 ? 0 : NB_A) + Math.min(NB_A - 1, (al * NB_A) | 0)].push(px - sz / 2, py - sz / 2, sz);
    }
    for (let bi = 0; bi < batch.length; bi++) {
      const b = batch[bi]; if (!b.length) continue;
      ctx.fillStyle = rgba(deep(bi < NB_A ? col[0] : col[1]), ((bi % NB_A) + .5) / NB_A);
      ctx.beginPath();
      for (let i = 0; i < b.length; i += 3) ctx.rect(b[i], b[i + 1], b[i + 2], b[i + 2]);
      ctx.fill();
    }
    // core light
    const ccx = cx + P.pullX * R * .9, ccy = cy + P.pullY * R * .9;
    const core = ctx.createRadialGradient(ccx - R * .2, ccy - R * .25, 0, ccx, ccy, R * (.95 + smooth * .25 + hov * .1));
    core.addColorStop(0, LIGHT ? rgba(col[0], .10 + smooth * .16 + hov * .05) : rgba([255, 255, 255], .16 + smooth * .25 + hov * .06)); core.addColorStop(.35, rgba(col[0], (.10 + smooth * .12) * (LIGHT ? .7 : 1))); core.addColorStop(1, LIGHT ? 'rgba(255,255,255,0)' : 'rgba(0,0,0,0)');
    ctx.fillStyle = core; ctx.beginPath(); ctx.arc(ccx, ccy, R * 1.25, 0, 6.29); ctx.fill();

    // frequency halo
    const NB = 120, r0 = R * 1.42;
    for (let i = 0; i < NB; i++) {
      const ang = (i / NB) * 6.283 - 1.5708 + rotY * .15;
      let v = bands ? bands[3 + ((i < NB / 2 ? i : NB - i) * 1.2 | 0)] / 255 : 0;
      v = Math.max(v, (state === 'idle' ? .03 + (Math.sin(t * 2 + i * .3) + 1) * .015 : state === 'thinking' ? (Math.sin(t * 8 - i * .4) + 1) * .06 : .02));
      const len = R * (.04 + v * .55);
      ctx.strokeStyle = rgba(deep(i % 2 ? col[0] : col[1]), .25 + v * .7); ctx.lineWidth = 1.6 * dpr;
      ctx.beginPath(); ctx.moveTo(cx + Math.cos(ang) * r0, cy + Math.sin(ang) * r0);
      ctx.lineTo(cx + Math.cos(ang) * (r0 + len), cy + Math.sin(ang) * (r0 + len)); ctx.stroke();
    }
    // orbit rings
    for (let k = 0; k < 3; k++) {
      ctx.strokeStyle = rgba(deep(col[k % 2]), (LIGHT ? .16 : .10) + (state === 'thinking' ? .2 : 0) + smooth * .1 + hov * .06); ctx.lineWidth = 1 * dpr;
      ctx.beginPath(); ctx.ellipse(cx, cy, R * (1.75 + k * .22), R * (.42 + k * .1), rotY * (k % 2 ? -1 : 1) * .4 + k, 0, 6.29); ctx.stroke();
    }
    // thinking arcs
    if (state === 'thinking') {
      for (let k = 0; k < 3; k++) {
        const a0 = t * (2 + k * .7) + k * 2.1;
        ctx.strokeStyle = rgba(col[k % 2], .85); ctx.lineWidth = 2.2 * dpr;
        ctx.beginPath(); ctx.arc(cx, cy, R * (1.3 + k * .06), a0, a0 + 1.1); ctx.stroke();
      }
    }
    // sparks
    for (const s of sparks) {
      s.a += s.v * (state === 'thinking' ? 2.4 : 1) / 60;
      const rr = R * s.r * (1 + smooth * .2), x = cx + Math.cos(s.a) * rr, y = cy + Math.sin(s.a) * rr * .45 + s.y * R;
      ctx.fillStyle = rgba(deep(col[s.s > .5 ? 0 : 1]), .35 + s.s * .4); ctx.fillRect(x, y, 1.6 * dpr, 1.6 * dpr);
    }
    // bursts
    for (let i = bursts.length - 1; i >= 0; i--) {
      const b = bursts[i]; b.life -= .016; if (b.life <= 0) { bursts.splice(i, 1); continue; }
      b.r += b.v; const x = cx + Math.cos(b.a) * b.r * R, y = cy + Math.sin(b.a) * b.r * R * .7;
      ctx.fillStyle = rgba(b.c, b.life * .9); const z = (1 + b.life * 2) * dpr; ctx.fillRect(x, y, z, z);
    }
    // wake flash
    if (wake > .02) { ctx.strokeStyle = LIGHT ? rgba(deep(col[0]), wake * .7) : rgba([255, 255, 255], wake * .6); ctx.lineWidth = 3 * dpr; ctx.beginPath(); ctx.arc(cx, cy, R * (1.1 + (1 - wake) * 1.3), 0, 6.29); ctx.stroke(); }
    ctx.globalCompositeOperation = 'source-over';

    if (Math.abs(smooth - lastLvl) > .006) { lastLvl = smooth; document.documentElement.style.setProperty('--lvl', smooth.toFixed(3)); }   // only a visible change dirties the page
    cv.style.cursor = P.down ? 'grabbing' : hov > .05 ? 'grab' : 'default';
    if (!an) level *= .92;
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  return {
    setState(s) { state = s; document.body.dataset.state = s; },
    setLevel(v) { level = Math.max(0, Math.min(1, v)); },
    setSource(analyser) { an = analyser || null; },
    pulse() { wake = 1; },
    burst(n = 90) { wake = Math.max(wake, .9); for (let i = 0; i < n; i++) bursts.push({ a: Math.random() * 6.283, r: 1 + Math.random() * .2, v: .012 + Math.random() * .03, life: .6 + Math.random() * .7, c: Math.random() < .7 ? [22, 199, 132] : [255, 154, 60] }); },
    set onTap(fn) { onTap = fn; },
    get state() { return state; }
  };
})();
