/* Stage mode, canvas edition. When an answer deserves a picture the dashboard sinks into a dock, the orb glides to the
   corner and chart cards arc in from the bottom-left. Charts are drawn on canvas with depth (extruded bars, a ribbon line,
   a thick ring, a raised Karnataka map) and a camera that leans with the pointer. Each bar / slice / point / district starts
   growing the moment Mitra says its name (Stage.hear gets her running transcript) and keeps growing for a couple of
   seconds, so the picture builds while she talks; Stage.flush() at the end of her turn brings in anything she did not
   name. "Show it as a line graph / donut / map" re-draws the same numbers (Stage.morph). Numbers are never computed here. */
// an entrance animation that has finished leaves filter:blur(0) behind (fill-mode both) and keeps the element a filtered layer:
// mark it settled so the animation (and the filter) is dropped. Ghost, exit and morph animations are more specific and still run.
document.addEventListener('animationend', e => {
  if (/^(vcardIn|vcardMorph|mpIn|insightIn)$/.test(e.animationName) && e.target.classList) { e.target.classList.add('settled'); e.target.classList.remove('morphing'); }
}, true);
const Stage = (() => {
  const S = { open: false, cards: [], last: null, current: null, flushT: null, raf: 0, exitT: null, cam: { x: 0, y: 0, tx: 0, ty: 0 } };
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const norm = s => ' ' + String(s || '').toLowerCase().replace(/[^a-z0-9ಀ-೿%]+/g, ' ').replace(/\s+/g, ' ').trim() + ' ';
  const fmt = v => (Math.abs(v) >= 1000 ? Math.round(v).toLocaleString('en-IN') : (Number.isInteger(v) ? String(v) : (+v).toFixed(2)));
  const grow = (v, p) => (Number.isInteger(v) ? Math.round(v * p) : +(v * p).toFixed(2));     // a count-up of a whole number shows whole numbers
  const PAL = ['#16c784', '#79e3ff', '#ff9a3c', '#9b7dff', '#ff5c6a', '#ffd166', '#3b9bff', '#d6409f', '#4ade80', '#f472b6'];
  const ease = k => 1 - Math.pow(1 - Math.max(0, Math.min(1, k)), 3);
  const GROW = { bars: 2000, race: 1600, line: 1300, donut: 1500, map: 1400, kpi: 1500, tiles: 1100 };     // ms per reveal: slow enough to watch
  const dpr = Math.min(2, devicePixelRatio || 1);
  function nice(max, ticks = 4) {
    if (max <= 0) return { top: ticks, step: 1 };
    const raw = max / ticks, p = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * p).find(s => s * ticks >= max) || 10 * p;
    return { top: step * ticks, step };
  }
  const hex = (h, a = 1) => { const n = parseInt(h.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };
  const mix = (h, k) => { const n = parseInt(h.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255; const f = v => Math.round(k < 0 ? v * (1 + k) : v + (255 - v) * k); return `rgb(${f(r)},${f(g)},${f(b)})`; };

  // ------------------------------------------------------------------ chrome
  function host() {
    let h = $('#stageHost');
    if (h) return h;
    h = document.createElement('div'); h.id = 'stageHost'; h.className = 'stage-host';
    h.innerHTML = `<canvas class="stage-fx" id="stageFx"></canvas><div class="stage-veil"></div><div class="stage-beam"></div><div class="stage-title" id="stageTitle"></div><div class="stage-cards" id="stageCards"></div>
      <div class="stage-insight" id="stageInsight"></div>
      <div class="stage-kinds" id="stageKinds"><span>Show as</span>${['bars', 'line', 'donut', 'map'].map(k => `<button data-k="${k}">${k}</button>`).join('')}</div>
      <div class="stage-dock" id="stageDock"><div class="dock-chips" id="dockChips"></div><button class="dock-close" id="dockClose"><i>⌃</i> Dashboard</button></div>`;
    document.body.appendChild(h);
    $('#dockClose').onclick = () => exit();
    h.querySelectorAll('#stageKinds button').forEach(b => b.onclick = () => { const r = morph(b.dataset.k); if (r && window.morphSpoken) window.morphSpoken(r); });
    window.addEventListener('pointermove', e => { S.cam.tx = (e.clientX / innerWidth - .5) * 2; S.cam.ty = (e.clientY / innerHeight - .5) * 2; }, { passive: true });
    return h;
  }
  // the composer leaves the dashboard's stacking context while the stage is up (`.stage` has its own z-index, so the fixed
  // composer could never rise above the stage host and its dock covered the mic and stop buttons); it goes back on exit
  function liftComposer() {
    const comp = $('.composer');
    if (!comp || S.compHome || comp.parentNode === document.body) return;
    S.compHome = document.createComment('composer'); comp.parentNode.insertBefore(S.compHome, comp); document.body.appendChild(comp);
  }
  function homeComposer() {
    if (!S.compHome) return;
    const comp = $('.composer');
    if (comp && S.compHome.parentNode) S.compHome.parentNode.insertBefore(comp, S.compHome);
    S.compHome.remove(); S.compHome = null;
  }
  function enter() {
    if (S.open) return;
    host(); S.open = true; liftComposer();
    if (S.exitT) { clearTimeout(S.exitT); S.exitT = null; if (S.exitDone) S.exitDone(); }     // a close still fading out is finished first
    const ow = $('.orb-wrap');
    if (ow) {
      const phone = innerWidth < 600, hostTop = ($('#stageHost') || $('.stage-host') || { getBoundingClientRect: () => ({ top: 68 }) }).getBoundingClientRect().top || 68;
      const r = ow.getBoundingClientRect(), size = phone ? 40 : 132;
      const tx = (innerWidth - (phone ? 14 : 28) - size / 2) - (r.left + r.width / 2), ty = (phone ? hostTop + 4 + size / 2 : 84 + size / 2) - (r.top + r.height / 2);
      ow.style.setProperty('--sx', tx + 'px'); ow.style.setProperty('--sy', ty + 'px'); ow.style.setProperty('--ss', (size / r.width).toFixed(3));
    }
    dockChips();
    document.body.classList.add('stage-on');
    requestAnimationFrame(() => document.body.classList.add('stage-in'));
    if (!S.raf) S.raf = requestAnimationFrame(frame);
  }
  function exit(immediate = false) {
    if (!S.open) return;
    S.open = false; clearTimeout(S.flushT); clearTimeout(S.autoT);
    const h = host(); h.classList.add('stage-out'); document.body.classList.remove('stage-in');
    const done = () => { S.exitT = null; S.exitDone = null; homeComposer(); document.body.classList.remove('stage-on', 'board-on'); h.classList.remove('stage-out'); $('#stageCards').innerHTML = ''; $('#stageInsight').innerHTML = ''; $('#stageTitle').textContent = ''; S.cards.forEach(c => c.ro && c.ro.disconnect()); S.cards = []; cancelAnimationFrame(S.raf); S.raf = 0; };
    S.exitDone = done;
    if (immediate) done(); else S.exitT = setTimeout(done, 750);
  }
  function dockChips() {
    const chips = $('#dockChips'); chips.innerHTML = '';
    const seen = new Set();
    for (const el of document.querySelectorAll('#left .card, #right .card')) {
      const h3 = el.querySelector('h3'); if (!h3) continue;
      const title = (h3.childNodes[0]?.textContent || h3.textContent).trim().replace(/\s+/g, ' ').slice(0, 26);
      if (!title || seen.has(title)) continue; seen.add(title);
      const num = el.querySelector('.kpi .v, .n, small')?.textContent?.trim().slice(0, 14) || '';
      const b = document.createElement('button'); b.className = 'dock-chip'; b.innerHTML = `<b>${esc(title)}</b>${num ? `<span>${esc(num)}</span>` : ''}`;
      b.onclick = () => exitTo(title); chips.appendChild(b);
    }
    if (S.last && S.last !== S.current) {
      const b = document.createElement('button'); b.className = 'dock-chip last'; b.innerHTML = `<b>Last chart</b><span>${esc(S.last.title || '')}</span>`;
      b.onclick = () => show(S.last, { replay: false }); chips.appendChild(b);
    }
  }

  // ------------------------------------------------------------------ cards
  function show(op, { replay = true, kind = null, morph = false, crossfade = false } = {}) {
    if (!op || !(op.cards || []).length) return;
    enter();
    if (morph || crossfade) ghost();                  // crossfade: a new picture replaces one already up, in place; the reveal still follows her words
    S.current = op; S.last = op; clearTimeout(S.flushT); S.cards.forEach(c => c.ro && c.ro.disconnect()); S.cards = [];
    $('#stageTitle').textContent = op.title || '';
    const host_ = $('#stageCards'); host_.innerHTML = ''; host_.dataset.n = Math.min(3, op.cards.length); host_.classList.toggle('board', !op.mapfocus && (!!op.board || op.cards.length > 3)); document.body.classList.toggle('board-on', !op.mapfocus && (!!op.board || op.cards.length > 3)); host_.classList.toggle('mapfocus', !!op.mapfocus); document.body.classList.toggle('mapfocus-on', !!op.mapfocus);
    $('#stageInsight').innerHTML = op.insight ? `<span>✦</span>${esc(op.insight)}` : ''; $('#stageInsight').classList.remove('on');
    op.cards.slice(0, 6).forEach((c, ci) => {
      const k = ['kpi', 'tiles'].includes(c.type) ? c.type : (kind || c.type);
      const el = document.createElement('div'); el.className = `vcard k-${k}${(morph || crossfade) ? ' morphing' : ''}`; el.style.animationDelay = `${ci * ((morph || crossfade) ? 140 : 420)}ms`;
      el.innerHTML = `<div class="vh"><b>${esc(c.title)}</b>${c.subtitle ? `<span>${esc(c.subtitle)}</span>` : ''}</div><div class="vb"><canvas class="vcv"></canvas><div class="vov"></div></div>`;
      host_.appendChild(el);
      S.cards.push(makeCard(k, c, el, ci));
    });
    $('#stageKinds').classList.toggle('on', canMorph());
    $('#stageKinds').querySelectorAll('button').forEach(b => b.classList.toggle('on', S.cards[0] && S.cards[0].kind === b.dataset.k));
    clearTimeout(S.autoT);
    if (!replay) { flush(0); return; }
    S.flushT = setTimeout(() => flush(), 16000);
    const n = S.cards.reduce((a, cd) => a + cd.items.length, 0);
    const revealed = () => S.cards.some(cd => cd.items.some(i => i.on));
    const race = S.cards.every(cd => cd.kind === 'race');               // a ranking slides in by itself; lit = named, so it waits for her words
    if (race && !morph) S.autoT = null;
    else if (morph || n > 5) S.autoT = setTimeout(() => flush(90), morph ? 200 : 450);
    else S.autoT = setTimeout(() => { if (!revealed()) flush(260); else S.autoT = setTimeout(() => flush(260), 3200); }, 3000);
  }
  function makeCard(kind, c, el, ci) {
    const cv = el.querySelector('.vcv'), ov = el.querySelector('.vov');
    const items = c.items.map(it => ({ label: it.label, value: +it.value || 0, aliases: it.aliases || [], district: it.district || '', geo: it.geo || {}, tone: it.tone || '', on: false, t0: 0, p: 0,
                                       pats: [it.label, ...(it.aliases || [])].map(norm).filter(p => p.trim().length >= 2) }));
    const card = { kind, c, el, cv, ov, items, ctx: cv.getContext('2d'), born: performance.now(), h: 0, hx: 0, hy: 0, hover: 0 };
    el.insertAdjacentHTML('beforeend', '<div class="glint"></div>');
    el.onpointermove = e => { const r = el.getBoundingClientRect(); card.hx = (e.clientX - r.left) / r.width * 2 - 1; card.hy = (e.clientY - r.top) / r.height * 2 - 1; card.hover = 1;
      el.style.setProperty('--mx', ((card.hx + 1) * 50).toFixed(1) + '%'); el.style.setProperty('--my', ((card.hy + 1) * 50).toFixed(1) + '%'); };
    el.onpointerleave = () => { card.hover = 0; };
    card.reveal = i => { const it = items[i]; if (it.on) return; it.on = true; it.t0 = performance.now(); el.classList.add('live'); };
    card.r = ({ bars: Bars, race: Race, line: Line, donut: Donut, map: KaMap, kpi: Kpi, tiles: Tiles }[kind] || Bars)(card);
    sizeCard(card);
    card.needSize = false;
    if (window.ResizeObserver) { card.ro = new ResizeObserver(() => { card.needSize = true; }); card.ro.observe(cv); card.ro.observe(el); }
    else card.needSize = true;
    return card;
  }
  // the canvas follows its LAYOUT size (clientWidth/Height: not the tilted / flying-in transformed box, which changes every frame and
  // used to resize, and so wipe, the canvas again and again), and only when that size really changes (ResizeObserver)
  function sizeCard(card) {
    const w = Math.max(10, card.cv.clientWidth), h = Math.max(10, card.cv.clientHeight);
    if (card.cv.width !== Math.round(w * dpr) || card.cv.height !== Math.round(h * dpr)) { card.cv.width = Math.round(w * dpr); card.cv.height = Math.round(h * dpr); }
    card.W = w; card.H = h;
    const ch = card.el.offsetHeight;
    if (ch !== card.ch) { card.ch = ch; card.el.style.setProperty('--ch', ch + 'px'); }   // the scan line travels this far (transform, not top)
  }
  function frame() {
    S.raf = requestAnimationFrame(frame);
    if (!S.open) return;
    const now = performance.now();
    _T = mkT();
    S.cam.x += (S.cam.tx - S.cam.x) * .04; S.cam.y += (S.cam.ty - S.cam.y) * .04;
    if (!document.hidden) fx(now);
    for (const card of S.cards) {
      card.h += (card.hover - card.h) * .08;
      if (card.needSize || !card.ro) { card.needSize = false; sizeCard(card); }
      for (const it of card.items) if (it.on) it.p = ease((now - it.t0) / (GROW[card.kind] || 2000));
      const ctx = card.ctx; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, card.W, card.H);
      try { card.r.draw(ctx, card, now); } catch (e) { console.error('stage draw', e); }
      card.el.style.transform = `perspective(1400px) rotateY(${(S.cam.x * 5 + card.hx * card.h * 7).toFixed(2)}deg) rotateX(${(-S.cam.y * 4 - card.hy * card.h * 6).toFixed(2)}deg) scale(${(1 + card.h * .025).toFixed(3)})`;
    }
  }

  // ambient light: drifting glow particles behind the cards (pre-rendered sprites, one draw each; parallax with the camera)
  const FX = { ps: [], sprites: null };
  function sprite(col) { const c = document.createElement('canvas'); c.width = c.height = 64; const x = c.getContext('2d'); const g = x.createRadialGradient(32, 32, 0, 32, 32, 32); g.addColorStop(0, hex(col, .9)); g.addColorStop(.35, hex(col, .25)); g.addColorStop(1, hex(col, 0)); x.fillStyle = g; x.fillRect(0, 0, 64, 64); return c; }
  function fx(now) {
    const cv = $('#stageFx'); if (!cv) return;
    if (!FX.sprites) FX.sprites = ['#16c784', '#79e3ff', '#ff9a3c'].map(sprite);
    if (!FX.h || FX.vw !== innerWidth || FX.vh !== innerHeight) { FX.vw = innerWidth; FX.vh = innerHeight; FX.h = cv.clientHeight || innerHeight; }   // read the size once, not every frame
    const w = innerWidth, h = FX.h;
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
    if (!FX.ps.length) for (let i = 0; i < 70; i++) FX.ps.push({ x: Math.random() * w, y: Math.random() * h, z: .3 + Math.random() * .7, s: i % 3, vy: -(.08 + Math.random() * .25), vx: (Math.random() - .5) * .12, ph: Math.random() * 6.28 });
    const ctx = cv.getContext('2d'); ctx.clearRect(0, 0, w, h); ctx.globalCompositeOperation = TK().light ? 'source-over' : 'lighter';
    for (const p of FX.ps) {
      p.y += p.vy * p.z; p.x += p.vx + Math.sin(now / 1800 + p.ph) * .08;
      if (p.y < -20) { p.y = h + 10; p.x = Math.random() * w; } if (p.x < -20) p.x = w + 10; if (p.x > w + 20) p.x = -10;
      const a = (.35 + .35 * Math.sin(now / 900 + p.ph)) * p.z, sz = 8 + 22 * p.z;
      ctx.globalAlpha = TK().light ? a * .55 : a; ctx.drawImage(FX.sprites[p.s], p.x + S.cam.x * 30 * p.z - sz / 2, p.y + S.cam.y * 20 * p.z - sz / 2, sz, sz);
    }
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  }
  // a morph crossfades: the old cards stay as a fading ghost (their canvases frozen as images) while the new ones turn in
  function ghost() {
    const host_ = $('#stageCards'); if (!host_ || !host_.children.length) return;
    const g = document.createElement('div'); g.className = 'stage-cards ghost'; g.dataset.n = host_.dataset.n;
    for (const el of host_.children) {
      const c = el.cloneNode(true), cv = el.querySelector('.vcv'), im = c.querySelector('.vcv');
      if (cv && im) { const img = new Image(); try { img.src = cv.toDataURL(); } catch (e) { } img.className = 'vcv'; img.style.width = cv.clientWidth + 'px'; img.style.height = cv.clientHeight + 'px'; im.replaceWith(img); }
      c.style.transform = el.style.transform; g.appendChild(c);
    }
    host_.parentNode.insertBefore(g, host_); setTimeout(() => g.remove(), 750);
  }
  // a further function is running while a picture is up: the title shimmers until the next picture settles
  function refine(on) { const h = $('#stageHost'); if (h) h.classList.toggle('refining', !!on && S.open); }
  // leaving through a dock chip glides back and lights the card it named
  function exitTo(title) { exit(); setTimeout(() => focusCard(title), 650); }
  function focusCard(title) {
    const t = (title || '').toLowerCase();
    const el = [...document.querySelectorAll('#left .card, #right .card')].find(e => { const h3 = e.querySelector('h3'); const tt = h3 ? (h3.childNodes[0]?.textContent || h3.textContent).trim().toLowerCase() : ''; return (e.dataset.id || '') === t || tt.startsWith(t); });
    if (!el) return false;
    el.scrollIntoView({ behavior: 'smooth', block: 'center' }); el.classList.remove('focus'); void el.offsetWidth; el.classList.add('focus'); setTimeout(() => el.classList.remove('focus'), 1700);
    return true;
  }

  // ------------------------------------------------------------------ renderers (canvas, with depth)
  // colours for the current theme, refreshed once a frame (light is the default look; dark keeps the original)
  let _T = null;
  function mkT() {
    return document.documentElement.dataset.theme === 'light'
      ? { light: true, ink: '#0b0d14', ink2: '#1f2433', mute: '#4a5060', mute2: '#7d8394', faint: 'rgba(12,16,28,.05)', grid: 'rgba(12,16,28,.08)',
          line: 'rgba(12,16,28,.2)', rim: 'rgba(255,255,255,.4)', hole: '#ffffff', chip: 'rgba(255,255,255,.96)', land: '#e9eef5', border: 'rgba(255,255,255,.95)', shadow: 'rgba(30,45,80,.10)' }
      : { light: false, ink: '#ffffff', ink2: '#dfe3ea', mute: '#8a8d99', mute2: '#6b6e7a', faint: 'rgba(255,255,255,.05)', grid: 'rgba(255,255,255,.07)',
          line: 'rgba(255,255,255,.18)', rim: 'rgba(255,255,255,.12)', hole: '#0b0b0f', chip: 'rgba(5,5,7,.82)', land: 'rgba(255,255,255,.035)', border: 'rgba(255,255,255,.15)', shadow: 'rgba(0,0,0,.35)' };
  }
  function TK() { return _T || (_T = mkT()); }
  function floor(ctx, W, H, cam, y0) {
    ctx.save(); ctx.strokeStyle = TK().faint; ctx.lineWidth = 1;
    const vx = W / 2 + cam.x * 120;
    for (let i = 0; i <= 10; i++) { const x = (W * i) / 10; ctx.beginPath(); ctx.moveTo(x, H); ctx.lineTo(vx + (x - vx) * .55, y0); ctx.stroke(); }
    for (let j = 0; j < 4; j++) { const k = j / 4, y = y0 + (H - y0) * (k * k); ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
    ctx.restore();
  }
  const SHORT = { 'rural development & panchayat raj': 'RDPR', 'rural development and panchayat raj': 'RDPR', 'food & civil supplies': 'Food & Civil Supplies',
                  'food and civil supplies': 'Food & Civil Supplies', 'dakshina kannada': 'Dakshina Kannada', 'uttara kannada': 'Uttara Kannada' };
  const SHORTER = { 'food & civil supplies': 'Food', 'dakshina kannada': 'D. Kannada', 'uttara kannada': 'U. Kannada', 'bengaluru urban': 'Bengaluru U.',
                    'bengaluru rural': 'Bengaluru R.', 'chikkamagaluru': 'Chikkamagaluru', 'chamarajanagara': 'Chamarajanagar' };
  function shortLabel(t) { const k = String(t || '').toLowerCase(); return SHORT[k] || t; }
  const FT = new Map();
  function fitText(ctx, text, maxW, size = 12, weight = 600) {   // the label as it fits the slot: short name, then a shorter one, then an ellipsis
    const key = `${text}|${maxW | 0}|${size}|${weight}`; if (FT.has(key)) return FT.get(key);
    ctx.save(); ctx.font = `${weight} ${size}px Inter, system-ui, sans-serif`;
    let t = shortLabel(text);
    if (ctx.measureText(t).width > maxW) t = SHORTER[String(t).toLowerCase()] || SHORTER[String(text).toLowerCase()] || t;
    if (ctx.measureText(t).width > maxW) { let s = t; while (s.length > 2 && ctx.measureText(s + '…').width > maxW) s = s.slice(0, -1); t = s.trimEnd() + '…'; }
    ctx.restore(); if (FT.size > 800) FT.clear(); FT.set(key, t); return t;
  }
  function label(ctx, text, x, y, { size = 12, weight = 600, color = null, align = 'center', glow = null } = {}) {
    ctx.save(); ctx.font = `${weight} ${size}px Inter, system-ui, sans-serif`; ctx.fillStyle = color || TK().mute; ctx.textAlign = align; ctx.textBaseline = 'middle';
    if (glow && !TK().light) { ctx.shadowColor = glow; ctx.shadowBlur = 14; }
    ctx.fillText(text, x, y); ctx.restore();
  }
  function sparks(ctx, x, y, col, t, seed) {
    for (let i = 0; i < 10; i++) { const a = (seed * 7 + i * 1.7) % 6.28, k = Math.min(1, t / 1100), r = 10 + k * 46; ctx.fillStyle = hex(col, (1 - k) * .9); ctx.beginPath(); ctx.arc(x + Math.cos(a) * r, y - 8 - Math.sin(a) * r - k * 30, 1.6, 0, 6.29); ctx.fill(); }
  }

  function Bars(card) {
    return { draw(ctx, card, now) {
      const { W, H, items, c } = card, cam = S.cam, n = items.length;
      const tilt = (W - 72) / n < 66;                         // narrow slots: the names are tilted, not cut
      const pad = { l: 54, r: 18, t: 34, b: tilt ? 62 : 44 }, ax = nice(Math.max(...items.map(i => i.value), 1) * 1.08), max = ax.top;
      const base = H - pad.b, gw = (W - pad.l - pad.r) / n, bw = Math.min(84, gw * .5), depth = 22, dx = -depth * (.45 + cam.x * .5), dy = -depth * .55;
      floor(ctx, W, H, cam, base);
      for (let g = 0; g <= 4; g++) { const y = pad.t + (base - pad.t) * (1 - g / 4); ctx.strokeStyle = TK().grid; ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(W - pad.r, y); ctx.stroke(); label(ctx, fmt(ax.step * g), pad.l - 10, y, { size: 10, color: TK().mute2, align: 'right' }); }
      items.forEach((it, i) => {
        const col = PAL[i % PAL.length], x = pad.l + gw * i + (gw - bw) / 2, h = Math.max(3, (base - pad.t) * it.value / max * it.p), y = base - h;
        const ls = tilt ? 10.5 : gw < 90 ? 11 : 12, lt = tilt ? fitText(ctx, it.label, 96, ls, 700) : fitText(ctx, it.label, gw - 10, ls, 700);
        const name = (txt, col, wt) => { if (!tilt) return label(ctx, txt, x + bw / 2, base + 20, { color: col, weight: wt, size: ls });
          ctx.save(); ctx.translate(x + bw / 2 + 4, base + 12); ctx.rotate(-0.62); ctx.font = `${wt} ${ls}px Inter, system-ui, sans-serif`; ctx.fillStyle = col; ctx.textAlign = 'right'; ctx.textBaseline = 'middle'; ctx.fillText(txt, 0, 0); ctx.restore(); };
        if (!it.on) { ctx.save(); ctx.setLineDash([4, 5]); ctx.strokeStyle = TK().line; ctx.strokeRect(x, base - 6, bw, 6); ctx.restore(); name(lt, TK().mute2, 600); return; }
        ctx.fillStyle = mix(col, -.45); ctx.beginPath(); ctx.moveTo(x + bw, y); ctx.lineTo(x + bw - dx, y + dy); ctx.lineTo(x + bw - dx, base + dy); ctx.lineTo(x + bw, base); ctx.closePath(); ctx.fill();   // side face
        ctx.fillStyle = mix(col, .35); ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - dx, y + dy); ctx.lineTo(x + bw - dx, y + dy); ctx.lineTo(x + bw, y); ctx.closePath(); ctx.fill();                     // top face
        const g = ctx.createLinearGradient(0, y, 0, base); g.addColorStop(0, mix(col, .1)); g.addColorStop(1, mix(col, -.35));
        ctx.save(); if (it.p > .2) { ctx.shadowColor = hex(col, .55); ctx.shadowBlur = 18 + it.p * 14; } ctx.fillStyle = g; ctx.fillRect(x, y, bw, h); ctx.restore();                                     // front face
        ctx.fillStyle = TK().rim; ctx.fillRect(x, y, 3, h);
        const rg = ctx.createRadialGradient(x + bw / 2, base + 6, 2, x + bw / 2, base + 6, bw); rg.addColorStop(0, hex(col, .35 * it.p)); rg.addColorStop(1, hex(col, 0)); ctx.fillStyle = rg; ctx.fillRect(x - bw / 2, base - 8, bw * 2, 30);
        name(lt, TK().ink, 700);
        label(ctx, fmt(grow(it.value, it.p)) + (c.unit === '%' ? '%' : ''), x + bw / 2 - dx / 2, y + dy - 16, { size: 15, weight: 800, color: TK().ink, glow: hex(col, .9) });
        const age = now - it.t0; if (age > GROW.bars - 300 && age < GROW.bars + 900) sparks(ctx, x + bw / 2, y, col, age - (GROW.bars - 300), i);
      });
    } };
  }

  function Race(card) {
    card.items.forEach((it, i) => { it.wave = performance.now() + 250 + i * 140; });
    return { draw(ctx, card, now) {
      const { W, H, items, c } = card, n = items.length, max = Math.max(...items.map(i => i.value), 1);
      const rowH = Math.min(40, (H - 16) / n), lw = Math.min(150, W * .26), x0 = lw + 12, x1 = W - 70, depth = 8;
      items.forEach((it, i) => {
        const y = 10 + rowH * i + rowH / 2, col = PAL[i % PAL.length];
        const wave = ease((now - it.wave) / GROW.race), w = (x1 - x0) * it.value / max * wave, lit = it.on ? Math.min(1, it.p * 1.5) : 0;
        ctx.globalAlpha = Math.min(1, wave * 3);
        ctx.fillStyle = TK().faint; ctx.fillRect(x0, y - 7, x1 - x0, 14);
        ctx.fillStyle = mix(col, -.5); ctx.fillRect(x0 + depth * .6, y - 7 + depth * .6, w, 14);
        const g = ctx.createLinearGradient(x0, 0, x0 + Math.max(1, w), 0); g.addColorStop(0, mix(col, -.15)); g.addColorStop(1, mix(col, .35));
        ctx.save(); if (lit) { ctx.shadowColor = hex(col, .8 * lit); ctx.shadowBlur = 22 * lit; } ctx.fillStyle = g; ctx.fillRect(x0, y - 7, w, 14); ctx.restore();
        ctx.fillStyle = TK().rim; ctx.fillRect(x0, y - 7, w, 2);
        label(ctx, fitText(ctx, it.label, lw - 4, 12, lit ? 800 : 600), x0 - 12, y, { align: 'right', color: lit ? TK().ink : TK().mute, weight: lit ? 800 : 600, glow: lit ? hex(col, .6) : null });   // the name fits its column, never cut at the card's edge
        label(ctx, fmt(grow(it.value, wave)) + (c.unit === '%' ? '%' : ''), x1 + 12, y, { align: 'left', color: TK().ink2, weight: 800, size: 13 });
        ctx.globalAlpha = 1;
      });
    } };
  }

  function Line(card) {
    card.prog = 0; card.target = 0;
    return { draw(ctx, card, now) {
      const { W, H, items, c } = card, cam = S.cam, n = items.length, vals = items.map(i => i.value);
      const pad = { l: 56, r: 24, t: 30, b: 42 }, top = nice(Math.max(...vals) * 1.05, 3), max = top.top, min = Math.max(0, Math.floor(Math.min(...vals) * .9 / top.step) * top.step);
      const X = i => pad.l + (W - pad.l - pad.r) * (n > 1 ? i / (n - 1) : .5), Y = v => H - pad.b - (H - pad.t - pad.b) * ((v - min) / Math.max(1e-9, max - min));
      const want = Math.max(0, ...items.map((it, i) => it.on ? i : -1)) / Math.max(1, n - 1);
      card.target = Math.max(card.target, want); card.prog += (card.target - card.prog) * .035;
      floor(ctx, W, H, cam, H - pad.b);
      for (let g = 0; g <= 3; g++) { const y = pad.t + (H - pad.t - pad.b) * (1 - g / 3); ctx.strokeStyle = TK().grid; ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(W - pad.r, y); ctx.stroke(); label(ctx, fmt(Math.round(min + (max - min) * g / 3)), pad.l - 10, y, { size: 10, color: TK().mute2, align: 'right' }); }
      const pts = vals.map((v, i) => [X(i), Y(v)]), depth = 14 + cam.y * 6, px = -8 - cam.x * 10;
      const upto = card.prog * (n - 1), k = Math.floor(upto), f = upto - k;
      const path = pts.slice(0, k + 1); if (k < n - 1) path.push([pts[k][0] + (pts[k + 1][0] - pts[k][0]) * f, pts[k][1] + (pts[k + 1][1] - pts[k][1]) * f]);
      if (path.length > 1) {
        ctx.beginPath(); ctx.moveTo(path[0][0], path[0][1]); path.forEach(p => ctx.lineTo(p[0], p[1])); for (let i = path.length - 1; i >= 0; i--) ctx.lineTo(path[i][0] + px, path[i][1] + depth); ctx.closePath();
        ctx.fillStyle = 'rgba(14,159,110,.28)'; ctx.fill();
        ctx.beginPath(); ctx.moveTo(path[0][0], H - pad.b); path.forEach(p => ctx.lineTo(p[0], p[1])); ctx.lineTo(path[path.length - 1][0], H - pad.b); ctx.closePath();
        const ag = ctx.createLinearGradient(0, pad.t, 0, H - pad.b); ag.addColorStop(0, 'rgba(22,199,132,.22)'); ag.addColorStop(1, 'rgba(22,199,132,0)'); ctx.fillStyle = ag; ctx.fill();
        ctx.save(); ctx.shadowColor = 'rgba(22,199,132,.9)'; ctx.shadowBlur = 16; ctx.strokeStyle = '#16c784'; ctx.lineWidth = 3; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
        ctx.beginPath(); ctx.moveTo(path[0][0], path[0][1]); path.forEach(p => ctx.lineTo(p[0], p[1])); ctx.stroke(); ctx.restore();
        const head = path[path.length - 1], hg = ctx.createRadialGradient(head[0], head[1], 0, head[0], head[1], 16); hg.addColorStop(0, 'rgba(255,255,255,.95)'); hg.addColorStop(.3, 'rgba(22,199,132,.8)'); hg.addColorStop(1, 'rgba(22,199,132,0)'); ctx.fillStyle = hg; ctx.beginPath(); ctx.arc(head[0], head[1], 16, 0, 6.29); ctx.fill();
      }
      const peak = vals.indexOf(Math.max(...vals)), low = vals.indexOf(Math.min(...vals));
      if (!card.lblW || card.lblN !== n) { ctx.save(); ctx.font = '700 11px Inter, system-ui, sans-serif'; card.lblW = Math.max(...items.map(it => ctx.measureText(it.label).width)); card.lblN = n; ctx.restore(); }
      const gap = (W - pad.l - pad.r) / Math.max(1, n - 1), every = Math.max(1, Math.ceil((card.lblW + 10) / Math.max(1, gap)));
      items.forEach((it, i) => {
        const shown = i <= upto + 1e-6, col = i === peak ? '#ff9a3c' : i === low ? '#79e3ff' : '#16c784';
        if (i % every === 0 || i === n - 1 && (n - 1) % every >= every / 2) label(ctx, it.label, X(i), H - pad.b + 18, { color: shown ? TK().ink : TK().mute2, weight: shown ? 700 : 600, size: 11 });
        if (shown) { ctx.fillStyle = TK().hole; ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(X(i), Y(it.value), (i === peak || i === low) ? 5.5 : 4, 0, 6.29); ctx.fill(); ctx.stroke(); }
        if (shown && (i === peak || i === low) && card.prog > .999) label(ctx, fmt(it.value), X(i), Y(it.value) + (i === low ? 20 : -16), { color: col, weight: 800, size: 13, glow: hex(col, .8) });
      });
    } };
  }

  function Donut(card) {
    const legend = document.createElement('div'); legend.className = 'dleg'; card.ov.appendChild(legend);
    card.items.forEach((it, i) => { const li = document.createElement('div'); li.className = 'dli'; li.innerHTML = `<i style="background:${PAL[i % PAL.length]}"></i><span>${esc(it.label)}</span><b></b>`; legend.appendChild(li); it.li = li; });
    return { draw(ctx, card, now) {
      const { W, H, items, c } = card, cam = S.cam, tot = items.reduce((a, b) => a + b.value, 0) || 1;
      const narrow = W < 520, cx = narrow ? W / 2 : Math.min(W * .34, 150), cy = narrow ? Math.min(H * .36, 120) : H / 2 + 6;
      const R = narrow ? Math.max(40, Math.min(W * .3, cy - 26)) : Math.max(40, Math.min(cx - 28, H / 2 - 30)), th = narrow ? 22 : 26, tilt = .62 + cam.y * .06, depth = narrow ? 14 : 18;
      card.el.classList.toggle('narrow', narrow);
      let a0 = -Math.PI / 2, shown = 0;
      ctx.beginPath(); ctx.ellipse(cx, cy, R, R * tilt, 0, 0, 6.29); ctx.strokeStyle = TK().faint; ctx.lineWidth = th; ctx.stroke();
      items.forEach((it, i) => {
        const col = PAL[i % PAL.length], full = 2 * Math.PI * it.value / tot, span = full * it.p;
        if (it.on && span > 0) {
          for (let d = depth; d > 0; d -= 2) { ctx.beginPath(); ctx.ellipse(cx, cy + d, R, R * tilt, 0, a0, a0 + span); ctx.strokeStyle = mix(col, -.6 + d / depth * .2); ctx.lineWidth = th; ctx.stroke(); }
          ctx.save(); ctx.shadowColor = hex(col, .7); ctx.shadowBlur = 16; ctx.beginPath(); ctx.ellipse(cx, cy, R, R * tilt, 0, a0, a0 + span); ctx.strokeStyle = col; ctx.lineWidth = th; ctx.stroke(); ctx.restore();
          shown += it.value * it.p;
          it.li.classList.add('on'); it.li.querySelector('b').textContent = `${fmt(it.value)} · ${Math.round(100 * it.value / tot)}%`;
        }
        a0 += full;
      });
      label(ctx, fmt(Number.isInteger(tot) ? Math.round(shown) : +shown.toFixed(2)) + (c.unit === '%' ? '%' : ''), cx, cy - 4, { size: 28, weight: 800, color: TK().ink, glow: 'rgba(22,199,132,.5)' });
      label(ctx, c.unit === '%' ? '' : 'total', cx, cy + 20, { size: 10, color: TK().mute2, weight: 700 });
    } };
  }

  // KPI tiles: a grid of numbers that count up as Mitra names them (the board's first card, or the count behind a single question)
  const TONE = { bad: '#ff5c6a', warn: '#ff9a3c', ok: '#16c784', vio: '#9b7dff', l1: '#3b9bff', l2: '#79a8ff', l3: '#b8c8ff', '': '#16c784' };
  function Tiles(card) {
    return { draw(ctx, card, now) {
      const { W, H, items } = card, n = items.length;
      const cols = n <= 2 ? n : n <= 4 ? (W > 520 ? n : 2) : n <= 6 ? 3 : 4, rows = Math.ceil(n / cols), gap = 10;
      const tw = (W - gap * (cols - 1)) / cols, th = Math.min(118, (H - gap * (rows - 1)) / rows);
      const y0 = Math.max(0, (H - (th * rows + gap * (rows - 1))) / 2);
      items.forEach((it, i) => {
        const cx = (i % cols) * (tw + gap), cy = y0 + Math.floor(i / cols) * (th + gap), col = TONE[it.tone] || TONE[''], p = it.on ? it.p : 0;
        ctx.save();
        ctx.fillStyle = TK().light ? hex(col, .07 + .05 * p) : hex(col, .08 + .08 * p);
        ctx.strokeStyle = hex(col, .25 + .45 * p); ctx.lineWidth = 1.2;
        const r = 14; ctx.beginPath(); ctx.moveTo(cx + r, cy); ctx.arcTo(cx + tw, cy, cx + tw, cy + th, r); ctx.arcTo(cx + tw, cy + th, cx, cy + th, r); ctx.arcTo(cx, cy + th, cx, cy, r); ctx.arcTo(cx, cy, cx + tw, cy, r); ctx.closePath(); ctx.fill(); ctx.stroke();
        ctx.fillStyle = hex(col, .9); ctx.fillRect(cx + 12, cy + 12, 3, Math.max(10, th * .28));
        ctx.restore();
        const vs = Math.max(18, Math.min(38, th * .36, tw * .22));
        label(ctx, it.on ? fmt(grow(it.value, p)) : '—', cx + 22, cy + th * .44, { size: vs, weight: 800, color: it.on ? TK().ink : TK().mute2, align: 'left', glow: hex(col, .7) });
        label(ctx, fitText(ctx, it.label, tw - 30, 11.5, 600), cx + 22, cy + th * .78, { size: 11.5, color: TK().mute, align: 'left' });
      });
    } };
  }
  function Kpi(card) {
    return { draw(ctx, card, now) {
      const { W, H, items, c } = card, it = items[0] || { label: c.title, value: 0, p: 0 };
      label(ctx, fmt(grow(it.value, it.p)) + (c.unit === '%' ? '%' : ''), W / 2, H / 2 - 10, { size: 64, weight: 800, color: TK().ink, glow: 'rgba(22,199,132,.6)' });
      label(ctx, it.label, W / 2, H / 2 + 38, { size: 13, color: TK().mute });
    } };
  }

  // ------------------------------------------------------------------ the Karnataka map
  // Every chart can be the map. Districts take a colour ramp from their value and rise a little out of the state; a side panel
  // ranks the top districts, a legend gives the scale, hovering a district shows its numbers and its rank.
  //  - items that ARE districts (a ranking or breakdown by district): a choropleth of those values;
  //  - items spread across the state (departments, services, channels, statuses...): each item's footprint across the 31
  //    districts (from SQL). The map follows Mitra's voice: when she names an item its footprint washes over the state from its
  //    busiest district; once everything is named it settles on "All": each district coloured by the item that leads there;
  //  - taluks, Gram Panchayats and officers: their district (or the taluk outline, where we have it) rises in the item's colour.
  // Wheel to zoom, drag to pan, double-click for the whole state.
  const MAPALIAS = { 'bagalkot': 'bagalkote', 'bengaluru south (ramanagara)': 'ramanagara', 'chikkaballapura': 'chikkaballapur', 'vijayanagara': 'vijayanagar' };
  const key = s => (s || '').toLowerCase().replace(/[^a-z]/g, '');
  const dkeyOf = s => key(MAPALIAS[(s || '').toLowerCase()] || s);
  const hitCtx = document.createElement('canvas').getContext('2d');
  const METRIC_COL = { overdue: '#ff5c6a', late_pct: '#ff9a3c', rejected: '#ff9a3c', vulnerable: '#d6409f', escalated: '#9b7dff', resolved: '#16c784' };
  const LW = new Map();                                    // label widths, measured once
  function KaMap(card) {
    const DIST = typeof KA_DIST !== 'undefined' ? KA_DIST : (window.KA_DIST || []), WORLD = typeof KA_WORLD !== 'undefined' ? KA_WORLD : (window.KA_WORLD || [0, 0, 1000, 1550]);
    const TAL = typeof KA_TALUK !== 'undefined' ? KA_TALUK : (window.KA_TALUK || {});
    const paths = DIST.map(d => { const b = bbox(d.d); return { n: d.n, k: dkeyOf(d.n), p2: new Path2D(d.d), b, cx: (b[0] + b[2]) / 2, cy: (b[1] + b[3]) / 2, f: 0, hov: 0 }; })
      .sort((a, b) => a.cy - b.cy);                                       // north first, so the south's extrusions overlap correctly
    const taluks = Object.entries(TAL).map(([n, v]) => ({ n, k: key(n), p2: new Path2D(v.d), b: bbox(v.d) }));
    const by = (card.c.by || '').toLowerCase(), unit = card.c.unit === '%' ? '%' : '';
    card.items.forEach(it => {
      it.gk = new Map(Object.entries(it.geo || {}).map(([d, v]) => [dkeyOf(d), +v || 0]));
      it.dkey = dkeyOf(by === 'district' ? it.label : it.district);
      it.tkey = by === 'taluk' ? key(it.label) : '';
      it.tal = it.tkey ? taluks.find(t => t.k === it.tkey || (it.aliases || []).some(a => key(a) === t.k)) : null;
    });
    const heatD = by === 'district' || (!by && card.items.length > 6 && card.items.every(it => it.dkey && paths.some(p => p.k === it.dkey)));
    const geoMode = !heatD && !card.items.some(it => it.tal) && card.items.some(it => it.gk.size);
    const placeMode = !heatD && !geoMode;
    const M = { focus: -2, user: false, lastOn: 0, allT: 0, wave0: 0, wfx: 0, wfy: 0, hover: null, panelKey: '', tipKey: '' };
    const cam = { cx: WORLD[0] + WORLD[2] / 2, cy: WORLD[1] + WORLD[3] / 2, z: 1, tcx: 0, tcy: 0, tz: 1, user: false };
    cam.tcx = cam.cx; cam.tcy = cam.cy;
    // the side panel, the tooltip
    const panel = document.createElement('div'); panel.className = 'mpanel'; card.ov.appendChild(panel);
    const tip = document.createElement('div'); tip.className = 'mtip'; card.ov.appendChild(tip);
    panel.addEventListener('click', e => {
      const b = e.target.closest('[data-f]'); if (!b) return;
      M.focus = +b.dataset.f; M.user = true; startWave();
    });
    const cv = card.cv; let drag = null, moved = false;
    cv.style.pointerEvents = 'auto'; cv.style.cursor = 'grab';
    cv.addEventListener('wheel', e => { e.preventDefault(); cam.user = true; cam.tz = Math.max(1, Math.min(9, cam.tz * (e.deltaY < 0 ? 1.2 : 1 / 1.2))); }, { passive: false });
    cv.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY, cx: cam.tcx, cy: cam.tcy }; moved = false; cv.style.cursor = 'grabbing'; try { cv.setPointerCapture(e.pointerId); } catch (_) { } });
    cv.addEventListener('pointermove', e => {
      const r = cv.getBoundingClientRect(); M.mx = e.clientX - r.left; M.my = e.clientY - r.top;
      if (drag) { const sc = base() * cam.z; if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) > 4) { moved = true; cam.user = true; } cam.tcx = drag.cx - (e.clientX - drag.x) / sc; cam.tcy = drag.cy - (e.clientY - drag.y) / sc; }
      M.hover = pick(M.mx, M.my);
    });
    cv.addEventListener('pointerleave', () => { M.hover = null; tip.classList.remove('on'); });
    const up = () => { drag = null; cv.style.cursor = 'grab'; };
    cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
    cv.addEventListener('dblclick', () => { cam.user = false; fit(); });
    let view = { ox: 0, oy: 0, sc: 1, mapW: 0 };
    function mapW() { return card.W >= 640 ? card.W - 232 : card.W; }
    let panelH = -1;                                         // the panel's height, read when it changes, not on every frame
    if (window.ResizeObserver) new ResizeObserver(() => { panelH = panel.offsetHeight || 0; }).observe(panel);
    function mapH() { if (panelH < 0) panelH = panel.offsetHeight || 0; return card.W >= 640 ? card.H : Math.max(150, card.H - panelH - 12); }   // phone: above the panel
    function base() { return Math.min((mapW() - 30) / WORLD[2], (mapH() - 24) / WORLD[3]); }
    function pick(x, y) {
      const wx = (x - view.ox) / view.sc, wy = (y - view.oy) / view.sc;
      for (let i = paths.length - 1; i >= 0; i--) if (hitCtx.isPointInPath(paths[i].p2, wx, wy)) return paths[i];
      return null;
    }
    function fit() {
      if (!placeMode) { cam.tcx = WORLD[0] + WORLD[2] / 2; cam.tcy = WORLD[1] + WORLD[3] / 2; cam.tz = 1; return; }
      const shapes = card.items.filter(it => it.on && (it.tal || it.dkey)).map(it => it.tal ? it.tal.b : (paths.find(p => p.k === it.dkey) || {}).b).filter(Boolean);
      if (!shapes.length) { cam.tcx = WORLD[0] + WORLD[2] / 2; cam.tcy = WORLD[1] + WORLD[3] / 2; cam.tz = 1; return; }
      const x0 = Math.min(...shapes.map(b => b[0])), y0 = Math.min(...shapes.map(b => b[1])), x1 = Math.max(...shapes.map(b => b[2])), y1 = Math.max(...shapes.map(b => b[3]));
      const w = Math.max(x1 - x0, WORLD[2] * .18), h = Math.max(y1 - y0, WORLD[3] * .18);
      cam.tcx = (x0 + x1) / 2; cam.tcy = (y0 + y1) / 2; cam.tz = Math.max(1, Math.min(5, .75 * Math.min(WORLD[2] / w, WORLD[3] / h)));
    }
    // what each district shows right now: { value, col, lead } and the scale
    function layer() {
      const items = card.items, out = new Map();
      if (heatD) {
        const col = METRIC_COL[card.c.metric] || '#16c784';
        items.forEach(it => { if (it.on && it.dkey) out.set(it.dkey, { v: it.value * it.p, col, raw: it.value }); });
        return { vals: out, col, title: card.c.title, sub: `${items.filter(i => i.on).length} of ${items.length} districts` };
      }
      if (geoMode) {
        if (M.focus >= 0) {
          const it = items[M.focus], col = PAL[M.focus % PAL.length];
          it.gk.forEach((v, k) => out.set(k, { v: v * (it.on ? it.p : 0), col, raw: v }));
          return { vals: out, col, title: it.label, sub: `${fmt(it.value)}${unit} ${card.c.metric && card.c.metric !== 'count' ? card.c.metric : 'cases'} · ${it.gk.size} districts` };
        }
        if (M.focus === -1) {                                       // all: the item that leads in each district
          paths.forEach(p => {
            let tot = 0, best = -1, bv = -1;
            items.forEach((it, j) => { if (!it.on) return; const v = (it.gk.get(p.k) || 0) * it.p; tot += v; if (v > bv) { bv = v; best = j; } });
            if (tot > 0) out.set(p.k, { v: tot, col: PAL[best % PAL.length], lead: best, share: bv / tot, raw: tot });
          });
          return { vals: out, col: PAL[0], title: 'All together', sub: 'each district in the colour of what leads there' };
        }
      }
      return { vals: out, col: PAL[0], title: card.c.title, sub: '' };
    }
    function startWave() {
      const L = layer(); let top = null, tv = -1;
      L.vals.forEach((x, k) => { if (x.raw > tv) { tv = x.raw; top = k; } });
      const p = paths.find(q => q.k === top) || { cx: WORLD[0] + WORLD[2] / 2, cy: WORLD[1] + WORLD[3] / 2 };
      M.wave0 = performance.now(); M.wfx = p.cx; M.wfy = p.cy;
    }
    function buildPanel(L, ranked, total) {
      const pk = `${M.focus}|${ranked.slice(0, 6).map(r => r[0] + ':' + Math.round(r[1].raw)).join(',')}|${card.items.map(i => i.on ? 1 : 0).join('')}`;
      if (pk === M.panelKey) return; M.panelKey = pk;
      const chips = geoMode ? `<div class="mp-chips">${card.items.length > 1 ? `<button data-f="-1" class="${M.focus === -1 ? 'on' : ''}"><i class="all"></i>All</button>` : ''}${card.items.map((it, j) =>
        `<button data-f="${j}" class="${M.focus === j ? 'on' : ''}${it.on ? '' : ' off'}"><i style="background:${PAL[j % PAL.length]}"></i>${esc(shortLabel(it.label).length > 22 ? shortLabel(it.label).slice(0, 21) + '…' : shortLabel(it.label))}<b>${it.on ? fmt(it.value) : ''}</b></button>`).join('')}</div>` : '';
      const max = ranked.length ? ranked[0][1].raw : 1, name = k => (paths.find(p => p.k === k) || { n: k }).n;
      const rows = ranked.slice(0, 6).map(([k, x], i) => `<div class="mp-r" style="--d:${i * 60}ms"><span class="mp-i">${i + 1}</span><span class="mp-n">${esc(name(k))}</span>` +
        `<i class="mp-b"><em style="width:${Math.max(4, 100 * x.raw / max).toFixed(1)}%;background:${x.col}"></em></i><b>${fmt(Math.round(x.raw * 100) / 100)}${unit}</b></div>`).join('');
      const legend = M.focus === -1 && geoMode ? `<div class="mp-leg mp-leg-cat">${card.items.filter(i => i.on).map(it => `<span><i style="background:${PAL[card.items.indexOf(it) % PAL.length]}"></i>${esc(shortLabel(it.label).length > 18 ? shortLabel(it.label).slice(0, 17) + '…' : shortLabel(it.label))}</span>`).join('')}</div>`
        : ranked.length ? `<div class="mp-leg"><span>${fmt(Math.round(Math.min(...ranked.map(r => r[1].raw))))}</span><i style="background:linear-gradient(90deg,${hex(L.col, .12)},${L.col})"></i><span>${fmt(Math.round(max))}${unit}</span></div>` : '';
      panel.innerHTML = `${chips}<div class="mp-h"><b>${esc(L.title || '')}</b><span>${esc(L.sub || '')}</span></div>` +
        (ranked.length ? `<div class="mp-t">Top districts</div><div class="mp-list">${rows}</div>${legend}` : `<div class="mp-empty">${placeMode ? 'The places Mitra names rise on the map.' : 'Lights up as Mitra speaks…'}</div>`) +
        (total ? `<div class="mp-tot">${fmt(Math.round(total))}${unit} across ${ranked.length} district${ranked.length === 1 ? '' : 's'}</div>` : '');
    }
    function showTip(L, ranked) {
      const p = M.hover;
      if (!p) { tip.classList.remove('on'); return; }
      const x = L.vals.get(p.k), rank = x ? ranked.findIndex(r => r[0] === p.k) + 1 : 0;
      let body = '';
      if (geoMode) {
        body = card.items.map((it, j) => it.on ? `<div><i style="background:${PAL[j % PAL.length]}"></i>${esc(it.label.length > 20 ? it.label.slice(0, 19) + '…' : it.label)}<b>${fmt(it.gk.get(p.k) || 0)}</b></div>` : '').join('');
      } else if (x) body = `<div><i style="background:${x.col}"></i>${esc(card.c.title || 'Value')}<b>${fmt(Math.round(x.raw * 100) / 100)}${unit}</b></div>`;
      const tk = `${p.k}|${body}|${rank}`;
      if (tk !== M.tipKey) { M.tipKey = tk; tip.innerHTML = `<h4>${esc(p.n)}</h4>${body || '<div class="mt-none">No cases here</div>'}${rank ? `<small>#${rank} of ${ranked.length} districts${M.focus === -1 ? ' by total' : ''}</small>` : ''}`; }
      const tw = tip.offsetWidth || 160, th = tip.offsetHeight || 60;
      tip.style.left = Math.min(M.mx + 16, card.W - tw - 8) + 'px'; tip.style.top = Math.max(8, Math.min(M.my - th - 10, card.H - th - 8)) + 'px';
      tip.classList.add('on');
    }
    return { draw(ctx, card, now) {
      const { W, H, items } = card, lean = S.cam, T = TK();
      if (!paths.length) { label(ctx, 'map data not loaded', W / 2, H / 2, { color: T.mute2 }); return; }
      // follow the voice: the item just named takes the map; when all are named, "All"
      if (geoMode && !M.user) {
        const on = items.filter(i => i.on);
        if (on.length !== M.lastOn) {
          M.lastOn = on.length;
          const last = on.reduce((a, b) => (b.t0 > (a ? a.t0 : -1) ? b : a), null);
          if (last) { M.focus = items.indexOf(last); startWave(); }
          M.allT = on.length === items.length && items.length > 1 ? now + 2600 : 0;
        }
        if (M.allT && now > M.allT && M.focus !== -1) { M.focus = -1; M.allT = 0; startWave(); }
      }
      if (heatD && M.lastOn !== items.filter(i => i.on).length) { M.lastOn = items.filter(i => i.on).length; if (M.lastOn === 1) startWave(); }
      if (!cam.user) fit();
      cam.cx += (cam.tcx - cam.cx) * .05; cam.cy += (cam.tcy - cam.cy) * .05; cam.z += (cam.tz - cam.z) * .05;
      const mw = mapW(), mh = mapH(), sc = base() * cam.z, ox = mw / 2 - cam.cx * sc + lean.x * 6, oy = mh / 2 - cam.cy * sc + lean.y * 4;
      view = { ox, oy, sc, mapW: mw };
      const L = layer();
      let max = 0, total = 0; L.vals.forEach(x => { max = Math.max(max, x.raw); total += x.v; });
      const ranked = [...L.vals.entries()].filter(([, x]) => x.raw > 0).sort((a, b) => b[1].raw - a[1].raw);
      const maxD = Math.hypot(WORLD[2], WORLD[3]);
      ctx.save(); ctx.translate(ox, oy); ctx.scale(sc, sc);
      // the state floats: a soft shadow under it
      ctx.save(); ctx.translate(6 / sc, 14 / sc); ctx.fillStyle = T.shadow; paths.forEach(p => ctx.fill(p.p2)); ctx.restore();
      for (const p of paths) {
        const x = L.vals.get(p.k), tgt = x && max ? Math.sqrt(Math.max(0, x.v) / max) : 0;
        const delay = M.wave0 ? Math.hypot(p.cx - M.wfx, p.cy - M.wfy) / maxD * 900 : 0;
        if (now - M.wave0 >= delay) p.f += (tgt - p.f) * .09;
        p.hov += ((M.hover === p ? 1 : 0) - p.hov) * .2;
        const col = x ? x.col : L.col, rise = (p.f * 16 + p.hov * 5) / sc;
        if (rise > .3 / sc) { ctx.save(); ctx.fillStyle = mix(col, T.light ? -.25 : -.6); ctx.globalAlpha = Math.min(1, p.f * 1.6 + p.hov); ctx.fill(p.p2); ctx.restore(); }   // the side
        ctx.save(); ctx.translate(0, -rise);
        ctx.fillStyle = T.land; ctx.fill(p.p2);
        if (p.f > .004) { ctx.fillStyle = hex(col, (T.light ? .14 : .1) + .82 * Math.min(1, p.f) * (x && x.share != null ? .45 + .55 * x.share : 1)); ctx.fill(p.p2); }
        if (p.hov > .02) { ctx.fillStyle = T.light ? `rgba(12,16,28,${.08 * p.hov})` : `rgba(255,255,255,${.08 * p.hov})`; ctx.fill(p.p2); }
        ctx.strokeStyle = p.hov > .3 ? T.ink : T.border; ctx.lineWidth = (p.hov > .3 ? 2 : 1) / sc; ctx.stroke(p.p2);
        ctx.restore();
      }
      if (cam.z > 1.6) for (const t of taluks) { ctx.fillStyle = 'rgba(121,227,255,.05)'; ctx.fill(t.p2); ctx.strokeStyle = 'rgba(121,227,255,.45)'; ctx.setLineDash([3 / sc, 3 / sc]); ctx.lineWidth = 1 / sc; ctx.stroke(t.p2); ctx.setLineDash([]); }
      // taluks / GPs / officers: their place rises in the item's colour
      const raise = (p2, col, rise, pr) => {
        for (let z = rise; z > 0; z -= 2 / sc) { ctx.save(); ctx.translate(0, -z); ctx.fillStyle = mix(col, T.light ? -.3 : -.55); ctx.fill(p2); ctx.restore(); }
        ctx.save(); ctx.translate(0, -rise); ctx.shadowColor = hex(col, .6); ctx.shadowBlur = 18; ctx.fillStyle = hex(col, .55 + .4 * pr); ctx.fill(p2); ctx.strokeStyle = T.light ? '#fff' : 'rgba(255,255,255,.7)'; ctx.lineWidth = 1.2 / sc; ctx.stroke(p2); ctx.restore();
      };
      const pmax = Math.max(1, ...items.map(i => i.value));
      if (placeMode) items.forEach((it, i) => {
        if (!it.on) return;
        const shape = it.tal ? it.tal : paths.find(p => p.k === it.dkey);
        if (shape) raise(shape.p2, PAL[i % PAL.length], (8 + 24 * it.value / pmax) / sc * it.p, it.p);
      });
      // the busiest district breathes
      if (ranked.length) {
        const top = paths.find(p => p.k === ranked[0][0]);
        if (top) { const ph = (now / 1600) % 1, r = (14 + ph * 46) / sc, col = ranked[0][1].col; ctx.beginPath(); ctx.arc(top.cx, top.cy - top.f * 16 / sc, r, 0, 6.283); ctx.strokeStyle = hex(col, .7 * (1 - ph)); ctx.lineWidth = 2 / sc; ctx.stroke(); }
      }
      ctx.restore();
      // labels: the top five (or the named places), never on top of each other
      const placed = [], put = (x, y, text, col) => {
        let w = LW.get(text); if (w === undefined) { ctx.save(); ctx.font = '800 11px Inter, system-ui, sans-serif'; w = ctx.measureText(text).width + 20; ctx.restore(); if (LW.size > 400) LW.clear(); LW.set(text, w); }
        const h = 22;
        for (let tries = 0; tries < 8; tries++) { if (!placed.some(p => Math.abs(p.x - x) < (p.w + w) / 2 + 4 && Math.abs(p.y - y) < (p.h + h) / 2 + 3)) break; y -= h + 4; }
        placed.push({ x, y, w, h });
        ctx.fillStyle = T.light ? 'rgba(20,30,60,.10)' : 'rgba(0,0,0,.35)'; ctx.beginPath(); ctx.roundRect(x - w / 2 - 1, y - h / 2 + 2, w + 2, h + 1, 12); ctx.fill();   // a cheap soft shadow (no shadowBlur)
        ctx.fillStyle = T.chip; ctx.beginPath(); ctx.roundRect(x - w / 2, y - h / 2, w, h, 11); ctx.fill();
        ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x - w / 2 + 9, y, 3.2, 0, 6.283); ctx.fill();
        label(ctx, text, x + 4, y + .5, { size: 11, weight: 800, color: T.ink });
      };
      if (placeMode) items.forEach((it, i) => {
        if (!it.on) return; const shape = it.tal ? it.tal : paths.find(p => p.k === it.dkey); if (!shape) return;
        const b = shape.b; put(ox + (b[0] + b[2]) / 2 * sc, oy + (b[1] + b[3]) / 2 * sc - (8 + 24 * it.value / pmax) * it.p - 8, `${it.label}  ${fmt(grow(it.value, it.p))}${unit}`, PAL[i % PAL.length]);
      });
      else ranked.slice(0, 5).forEach(([k, x]) => {
        const p = paths.find(q => q.k === k); if (!p || p.f < .25) return;
        put(ox + p.cx * sc, oy + p.cy * sc - p.f * 16 - 6, `${p.n}  ${fmt(Math.round(x.raw * 100) / 100)}${unit}`, x.col);
      });
      if (placeMode) { const missing = items.filter(it => it.on && !it.dkey && !it.tal).map(it => it.label); if (missing.length) label(ctx, `not on the map: ${missing.join(', ')}`, mw / 2, mh - 10, { size: 10, color: T.mute2 }); }
      if (card.W >= 640) label(ctx, cam.z > 1.6 ? 'scroll to zoom · drag to pan · double-click for the state' : 'scroll to zoom · drag to pan · hover a district', mw / 2, H - 10, { size: 9, color: T.mute2 });
      buildPanel(L, ranked, total);
      showTip(L, ranked);
    } };
  }
  const bboxCache = {};
  function bbox(d) {
    if (bboxCache[d]) return bboxCache[d];
    const nums = (d.match(/-?\d+(\.\d+)?/g) || []).map(Number), xs = [], ys = [];
    for (let i = 0; i + 1 < nums.length; i += 2) { xs.push(nums[i]); ys.push(nums[i + 1]); }
    return (bboxCache[d] = xs.length ? [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)] : [0, 0, 0, 0]);
  }

  // ------------------------------------------------------------------ speech sync, morphing
  function hear(text) {
    if (!S.open || !S.cards.length) return;
    const heard = norm(text), flat = heard.replace(/ /g, '');
    for (const card of S.cards) card.items.forEach((it, i) => {
      if (it.on) return;
      if (it.pats.some(p => heard.includes(p) || (p.trim().length >= 6 && flat.includes(p.trim().replace(/ /g, ''))))) card.reveal(i);
    });
    if (S.cards.every(cd => cd.items.every(i => i.on))) setTimeout(insight, 1800);
  }
  function flush(stagger = 260) {
    if (!S.open) return;
    clearTimeout(S.flushT); clearTimeout(S.autoT);
    const left = S.cards.reduce((a, cd) => a + cd.items.filter(i => !i.on).length, 0);
    const st = Math.min(stagger, 1600 / Math.max(1, left));           // however many items, the rest arrive within ~1.6 s
    let k = 0;
    for (const card of S.cards) card.items.forEach((it, i) => { if (!it.on) { setTimeout(() => card.reveal(i), k * st); k++; } });
    setTimeout(insight, k * st + 1200);
  }
  function insight() { const el = $('#stageInsight'); if (el && el.innerHTML) el.classList.add('on'); }
  function canMorph() { return !!(S.current && !S.current.board && S.current.cards.some(c => !['kpi', 'tiles'].includes(c.type))); }
  const KINDS = { bar: 'bars', bars: 'bars', column: 'bars', line: 'line', trend: 'line', donut: 'donut', pie: 'donut', ring: 'donut', map: 'map', karnataka: 'map', race: 'race', ranking: 'race' };
  function morph(kindWord) {
    const kind = KINDS[(kindWord || '').toLowerCase()]; if (!kind || !S.current) return null;
    const op = JSON.parse(JSON.stringify(S.current));
    if (kind === 'map' && op.mapfocus) return { kind, ok: true, by: 'district' };     // already the map
    if (kind === 'map' && (op.board || op.cards.length > 3)) {        // a board on the map: ONE big map + the KPIs beside it, not six little maps
      const place = op.cards.find(c => ['district', 'taluk'].includes(c.by)) || op.cards.find(c => c.items.some(i => i.district || (i.geo && Object.keys(i.geo).length)));
      const tilesC = op.cards.find(c => c.type === 'tiles'), lvl = op.cards.find(c => /level/i.test(c.title));
      if (place) {
        place.type = 'map';
        op.cards = [place, tilesC, lvl].filter(Boolean); op.board = false; op.mapfocus = true;
        show(op, { replay: true, morph: true });
        return { kind, ok: true, by: place.by || '' };
      }
    }
    op.cards.forEach(c => { if (!['kpi', 'tiles'].includes(c.type)) c.type = kind; });
    show(op, { replay: true, kind, morph: true });
    const first = op.cards.find(c => !['kpi', 'tiles'].includes(c.type)) || op.cards[0], placeOk = kind !== 'map' || (first.by === 'district' || first.by === 'taluk' || first.items.some(i => i.district || (i.geo && Object.keys(i.geo).length)));
    return { kind, ok: placeOk, by: first.by || '' };
  }
  function debug() { return { open: S.open, cards: S.cards.map(cd => ({ kind: cd.kind, items: cd.items.map(it => ({ label: it.label, on: it.on, p: +it.p.toFixed(2) })) })) }; }

  return { show, hear, flush, exit, exitTo, focusCard, morph, refine, debug, get open() { return S.open; }, get last() { return S.last; }, get current() { return S.current; } };
})();
