/* ================= AI-mode charts (ported from the RDPR POC renderer, Sakala palette) =================
   Chart data is always built from the query result (server-side or from the live case data), never by the model.
   Bar ↔ line morph in place; doughnut crossfades in with a sweep; a sliding toggle; SVG fallback without Chart.js. */
const SK_PALETTE = ['#0e9f6e','#f26b1d','#3b82f6','#8b5cf6','#16c784','#ff9a3c','#0ea5e9','#d6409f','#64748b','#14b8a6','#f59e0b','#6366f1'];
const fmtNum = v => v == null ? 'no data' : Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 });

function renderChart(host, c){
  if (!c || !Array.isArray(c.values) || c.values.length < 2) return;
  const card = document.createElement('div'); card.className = 'chart-card';
  const head = document.createElement('div'); head.className = 'chart-head';
  const title = document.createElement('div'); title.className = 'chart-title';
  title.innerHTML = `<span class="chart-dot"></span>${esc(c.title || c.series_label || '')}${c.unit && !(c.title||'').includes(c.unit) ? ` <small>(${esc(c.unit)})</small>` : ''}`;
  const tog = document.createElement('div'); tog.className = 'chart-toggle'; tog.setAttribute('role', 'group');
  const canvasWrap = document.createElement('div'); canvasWrap.className = 'chart-canvas';
  const foot = document.createElement('div'); foot.className = 'chart-foot'; foot.textContent = c.source || '';
  head.append(title, tog); card.append(head, canvasWrap); if (c.source) card.append(foot); host.appendChild(card);

  const allPos = c.values.every(v => v == null || v >= 0);
  const ratio = /%|rate|ratio|average|avg|pct|per /i.test((c.unit || '') + ' ' + (c.series_label || ''));
  // a doughnut only for parts of a whole: additive counts, not rates and not a time series
  const types = ['bar', 'line'].concat(allPos && !ratio && c.type !== 'line' && c.values.length <= 12 ? ['doughnut'] : []);
  const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const ink = '#6e6e73', font = { family: 'Inter, "Noto Sans Kannada", sans-serif', size: 11 };
  const unitTxt = c.unit ? ' ' + c.unit : '';
  const total = c.values.reduce((a, v) => a + (v || 0), 0);
  const full = c.full || c.labels;
  let inst = null, kind = null;
  const stagger = (ctx, step) => reduced || ctx.type !== 'data' ? 0 : ctx.dataIndex * step;
  const tooltip = dough => ({ backgroundColor: 'rgba(11,11,12,.92)', padding: 11, cornerRadius: 12, caretSize: 6, displayColors: dough,
    titleFont: { family: 'Inter', weight: '600' }, bodyFont: { family: 'Inter' },
    callbacks: { title: x => full[x[0].dataIndex] || x[0].label,
      label: x => ' ' + (dough ? '' : (c.series_label ? c.series_label + ': ' : '')) + fmtNum(x.raw) + unitTxt + (dough && total ? '  (' + (x.raw / total * 100).toFixed(1) + '%)' : '') } });
  const guide = { id: 'guide', afterDatasetsDraw(ch){
    const a = ch.tooltip && ch.tooltip.getActiveElements(); if (!a || !a.length) return;
    const x = a[0].element.x, { top, bottom } = ch.chartArea, g = ch.ctx;
    g.save(); g.strokeStyle = 'rgba(14,159,110,.35)'; g.setLineDash([4, 4]); g.lineWidth = 1;
    g.beginPath(); g.moveTo(x, top); g.lineTo(x, bottom); g.stroke(); g.restore(); } };
  const centre = { id: 'centre', afterDraw(ch){
    const a = ch.getActiveElements(), g = ch.ctx, arc = ch.getDatasetMeta(0).data[0]; if (!arc) return;
    const i = a.length ? a[0].index : -1;
    const big = i >= 0 ? (total ? (c.values[i] / total * 100).toFixed(1) + '%' : fmtNum(c.values[i])) : fmtNum(total);
    const small = i >= 0 ? String(c.labels[i]).slice(0, 20) : 'Total' + unitTxt;
    g.save(); g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillStyle = '#0b0b0c'; g.font = '700 19px Inter, sans-serif'; g.fillText(big, arc.x, arc.y - 8);
    g.fillStyle = ink; g.font = '500 11px Inter, sans-serif'; g.fillText(small, arc.x, arc.y + 12);
    g.restore(); } };
  const layer = () => { const l = document.createElement('div'); l.className = 'chart-layer'; const cv = document.createElement('canvas');
    l.appendChild(cv); canvasWrap.appendChild(l); return [l, cv]; };
  const seriesLook = (ch, on, animate) => {
    const [bar, line] = ch.data.datasets;
    bar.data = on === 0 ? c.values.slice() : c.values.map(() => 0);
    line.data = on === 1 ? c.values.slice() : c.values.map(() => 0);
    bar.minBarLength = on === 0 ? 3 : 0;
    line.borderColor = on === 1 ? '#0e9f6e' : 'rgba(14,159,110,0)';
    line.pointRadius = on === 1 ? 4 : 0; line.pointBorderWidth = on === 1 ? 2 : 0;
    line.pointHoverRadius = on === 1 ? 7 : 0; line.pointHoverBorderWidth = on === 1 ? 2 : 0;
    line.fill = on === 1; ch.$on = on;
    if (animate) ch.update();
  };
  const buildCartesian = (cv, type) => {
    const ctx = cv.getContext('2d'), h = canvasWrap.clientHeight || 260;
    const barGrad = ctx.createLinearGradient(0, 0, 0, h); barGrad.addColorStop(0, '#16c784'); barGrad.addColorStop(1, '#0e9f6e');
    const barHover = ctx.createLinearGradient(0, 0, 0, h); barHover.addColorStop(0, '#ff9a3c'); barHover.addColorStop(1, '#f26b1d');
    const areaGrad = ctx.createLinearGradient(0, 0, 0, h); areaGrad.addColorStop(0, 'rgba(22,199,132,.28)'); areaGrad.addColorStop(1, 'rgba(22,199,132,0)');
    const cfg = { type: 'bar',
      data: { labels: c.labels, datasets: [
        { type: 'bar', label: c.series_label || '', data: c.values.slice(), order: 2, backgroundColor: c.values.map(v => v == null ? '#e5e7eb' : barGrad),
          hoverBackgroundColor: barHover, borderWidth: 0, borderRadius: 8, borderSkipped: 'bottom', maxBarThickness: 46, minBarLength: 3 },
        { type: 'line', label: c.series_label || '', data: c.values.slice(), order: 1, borderColor: '#0e9f6e', backgroundColor: areaGrad,
          borderWidth: 2.6, fill: true, tension: .38, spanGaps: true, pointBackgroundColor: '#f26b1d', pointBorderColor: '#fff',
          pointBorderWidth: 2, pointRadius: 4, pointHoverRadius: 7, pointHoverBackgroundColor: '#0e9f6e', pointHoverBorderWidth: 2 } ] },
      options: { responsive: true, maintainAspectRatio: false,
        animation: { duration: reduced ? 0 : 800, easing: 'easeOutQuart', delay: ctx => ctx.mode === 'default' ? stagger(ctx, 32) : 0 },
        transitions: { active: { animation: { duration: reduced ? 0 : 180 } } },
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { display: false }, tooltip: { ...tooltip(false), filter: item => item.datasetIndex === ch.$on } },
        scales: {
          x: { ticks: { color: ink, maxRotation: 40, autoSkip: true, font }, grid: { display: false }, border: { color: 'rgba(0,0,0,.08)' } },
          y: { beginAtZero: true, ticks: { color: ink, font, callback: v => Number(v).toLocaleString('en-IN') + (c.unit === '%' ? '%' : '') },
               border: { display: false }, grid: { color: 'rgba(0,0,0,.05)' } } } },
      plugins: [guide] };
    const on = type === 'line' ? 1 : 0;
    seriesLook(cfg, on, false);
    const ch = new Chart(ctx, cfg); ch.$on = on; return ch;
  };
  const buildDoughnut = cv => new Chart(cv.getContext('2d'), { type: 'doughnut',
    data: { labels: c.labels, datasets: [{ data: c.values, backgroundColor: c.labels.map((_, i) => SK_PALETTE[i % SK_PALETTE.length]),
      borderColor: '#fff', borderWidth: 3, hoverOffset: 12, hoverBorderColor: '#fff', borderRadius: 6, spacing: 2 }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: '66%', layout: { padding: 8 },
      animation: { duration: reduced ? 0 : 950, easing: 'easeOutQuart', animateRotate: true, animateScale: true },
      interaction: { mode: 'nearest', intersect: true },
      plugins: { legend: { display: true, position: 'right', labels: { color: '#1d1d1f', boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle', padding: 12, font } },
                 tooltip: tooltip(true) } },
    plugins: [centre] });
  const crossfade = build => {
    const old = canvasWrap.querySelector('.chart-layer.on'), oldInst = inst;
    const [l, cv] = layer(); inst = build(cv);
    requestAnimationFrame(() => l.classList.add('on'));
    if (old){ old.classList.remove('on'); old.classList.add('off'); setTimeout(() => { if (oldInst) oldInst.destroy(); old.remove(); }, reduced ? 0 : 420); }
  };
  const draw = type => {
    if (!window.Chart){ canvasWrap.innerHTML = svgChart(c, type === 'line' ? 'line' : 'bar'); return; }
    const want = type === 'doughnut' ? 'doughnut' : 'cartesian';
    if (inst && kind === 'cartesian' && want === 'cartesian'){ const on = type === 'line' ? 1 : 0; if (inst.$on !== on) seriesLook(inst, on, true); return; }
    kind = want; crossfade(cv => want === 'doughnut' ? buildDoughnut(cv) : buildCartesian(cv, type));
  };
  const thumb = document.createElement('span'); thumb.className = 'thumb'; tog.appendChild(thumb);
  const place = b => { thumb.style.width = b.offsetWidth + 'px'; thumb.style.transform = `translateX(${b.offsetLeft}px)`; };
  const initial = types.includes(c.type) ? c.type : 'bar';
  const NAMES = { bar: 'Bar', line: 'Line', doughnut: 'Donut' };
  types.forEach(ty => { const b = document.createElement('button'); b.type = 'button'; b.textContent = NAMES[ty];
    b.setAttribute('aria-pressed', ty === initial ? 'true' : 'false');
    b.onclick = () => { if (b.getAttribute('aria-pressed') === 'true') return;
      tog.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', 'false')); b.setAttribute('aria-pressed', 'true'); place(b); draw(ty); };
    tog.appendChild(b); });
  requestAnimationFrame(() => { const on = tog.querySelector('button[aria-pressed="true"]'); if (on){ tog.classList.add('no-anim'); place(on); requestAnimationFrame(() => tog.classList.remove('no-anim')); } });
  draw(initial);
}

function svgChart(c, type){
  const n = c.labels.length, W = 820, H = 260, L = 56, B = 56, T = 12, R = 10, pw = W - L - R, ph = H - T - B;
  const vals = c.values.map(v => v == null ? 0 : v), mx = Math.max(...vals, 0) || 1;
  const y = v => T + ph - v / mx * ph, step = pw / n;
  let s = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`;
  for (let i = 0; i <= 4; i++){ const v = mx * i / 4; s += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="#000" opacity=".05"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${fmtNum(v)}</text>`; }
  if (type === 'line') s += `<polyline fill="none" stroke="#0e9f6e" stroke-width="2.4" points="${vals.map((v, i) => (L + step * i + step / 2) + ',' + y(v)).join(' ')}"/>`;
  else vals.forEach((v, i) => { const bw = Math.min(46, step * .66); s += `<rect x="${L + step * i + (step - bw) / 2}" y="${y(v)}" width="${bw}" height="${y(0) - y(v)}" rx="6" fill="#0e9f6e"><title>${esc(c.labels[i])}: ${fmtNum(c.values[i])}</title></rect>`; });
  c.labels.forEach((l, i) => { if (i % Math.ceil(n / 12)) return; s += `<text transform="translate(${L + step * i + step / 2},${T + ph + 12}) rotate(30)">${esc(String(l).slice(0, 16))}</text>`; });
  return s + '</svg>';
}

/* chart data for the offline answers (local engine): built from the same rows the answer used */
let LASTCHART = null;
function chartFromHbar(html, q){
  const d=document.createElement('div'); d.innerHTML=html; const rows=[...d.querySelectorAll('.hb')].map(h=>[h.children[0].textContent.trim(), parseFloat((h.querySelector('.n')||{}).textContent.replace(/[^\d.]/g,''))]).filter(r=>!isNaN(r[1]));
  if (rows.length<2) return null; const pctQ=/late|rate|%/i.test(q);
  return {type:'bar', labels:rows.map(r=>r[0].length>27?r[0].slice(0,26)+'…':r[0]), full:rows.map(r=>r[0]), values:rows.map(r=>r[1]), series_label:pctQ?'Delivered late':'Cases', unit:pctQ?'%':'', title:q, source:''};
}
