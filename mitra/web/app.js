/* Mitra on a phone. Under 600 px wide (a real phone, or the phone frame of "Start app") the three-column desk becomes an app:
   a compact header with the profile switcher, the orb and the captions in the middle, the composer at the thumb, and the two
   side columns in a bottom sheet with tabs (peek / half / full; drag the handle or tap a tab). New cards light a dot on their
   tab; the important ones (an opened case, your request, the inbox) raise the sheet by themselves. When it runs inside the
   phone frame (?app=1) it reports what it is doing to the page around it ("Behind the app"). */
const Mobile = (() => {
  const $ = s => document.querySelector(s);
  const mq = matchMedia('(max-width: 600px)');
  const inApp = new URLSearchParams(location.search).has('app');
  let sheet = null;
  const post = m => { if (inApp && window.parent !== window) { try { window.parent.postMessage({ mitra: 1, ...m }, location.origin); } catch (e) { } } };
  const LABELS = { citizen: ['My request', 'Updates'], officer: ['Inbox', 'Case'], cs: ['State', 'Activity'] };
  const AUTO = { upload: 'left', answer: 'right', case: 'right', request: 'left', inbox: 'left', mycases: 'left', kpi: 'left', filter: 'left', routed: 'left', atr: 'right', pack: 'right', resolution: 'right', verdict: 'right' };

  function setS(s) { if (!sheet) return; sheet.dataset.s = s; document.body.dataset.sheet = s; }
  function tab(t) {
    if (!sheet) return;
    sheet.dataset.t = t;
    sheet.querySelectorAll('.ms-tabs button').forEach(b => { b.classList.toggle('on', b.dataset.t === t); if (b.dataset.t === t) b.classList.remove('new'); });
  }
  function labels() {
    if (!sheet) return;
    const p = (typeof J !== 'undefined' && J.profile) || 'citizen', [a, b] = LABELS[p] || LABELS.citizen;
    sheet.querySelector('[data-t=left] .ms-l').textContent = a; sheet.querySelector('[data-t=right] .ms-l').textContent = b;
  }
  function setup() {
    if (!mq.matches || sheet) return;
    document.body.classList.add('m');
    const prof = $('#prof'), hr = $('.hdr-right');
    if (prof && hr && prof.parentElement !== hr) hr.prepend(prof);          // the profile switcher sits in the header on a phone
    sheet = document.createElement('div'); sheet.className = 'msheet';
    sheet.innerHTML = `<div class="ms-grab" aria-label="Drag up for more"><i></i></div>
      <div class="ms-tabs"><button data-t="left"><span class="ms-l"></span><em></em></button><button data-t="right"><span class="ms-l"></span><em></em></button></div>
      <div class="ms-body"></div>`;
    document.body.appendChild(sheet);
    const body = sheet.querySelector('.ms-body');
    body.appendChild($('#left')); body.appendChild($('#right'));
    tab('left'); setS('peek'); labels();
    // drag the handle; a tap steps peek -> half -> full -> peek
    const grab = sheet.querySelector('.ms-grab'); let y0 = null, h0 = 0;
    grab.addEventListener('pointerdown', e => { y0 = e.clientY; h0 = sheet.getBoundingClientRect().height; sheet.classList.add('drag'); try { grab.setPointerCapture(e.pointerId); } catch (_) { } });
    grab.addEventListener('pointermove', e => { if (y0 == null) return; sheet.style.height = Math.max(72, Math.min(innerHeight * .9, h0 + (y0 - e.clientY))) + 'px'; });
    const end = e => {
      if (y0 == null) return;
      const moved = Math.abs(e.clientY - y0), h = sheet.getBoundingClientRect().height;
      sheet.classList.remove('drag'); sheet.style.height = ''; y0 = null;
      if (moved < 6) { setS(sheet.dataset.s === 'peek' ? 'half' : sheet.dataset.s === 'half' ? 'full' : 'peek'); return; }
      setS(h > innerHeight * .7 ? 'full' : h > innerHeight * .3 ? 'half' : 'peek');
    };
    grab.addEventListener('pointerup', end); grab.addEventListener('pointercancel', end);
    sheet.querySelectorAll('.ms-tabs button').forEach(b => b.onclick = () => {
      if (sheet.dataset.t === b.dataset.t && sheet.dataset.s !== 'peek') { setS('peek'); return; }
      tab(b.dataset.t); if (sheet.dataset.s === 'peek') setS('half');
    });
    // new cards: a dot on their tab; important ones raise the sheet
    for (const side of ['left', 'right']) {
      new MutationObserver(ms => {
        for (const m of ms) for (const n of m.addedNodes) {
          if (n.nodeType !== 1 || !n.classList.contains('card')) continue;
          const id = n.dataset.id || '';
          if (AUTO[id] === side && !document.body.classList.contains('stage-on')) { tab(side); if (sheet.dataset.s === 'peek') setS('half'); }
          else if (sheet.dataset.t !== side) sheet.querySelector(`[data-t="${side}"]`).classList.add('new');
        }
      }).observe($('#' + side), { childList: true });
    }
    // the profile changed: new tab names, back to the first tab
    const pn = $('#profName');
    if (pn) new MutationObserver(() => { labels(); tab('left'); setS('peek'); post({ type: 'profile', name: pn.textContent, sub: ($('#profSub') || {}).textContent || '' }); }).observe(pn, { childList: true, characterData: true, subtree: true });
  }

  // ------------------------------------------------------------------ "Behind the app": what Mitra is doing, for the page around the phone
  function bridge() {
    if (!inApp) return;
    document.documentElement.classList.add('inapp');
    const watch = (sel, fn, opts) => { const el = $(sel); if (el) new MutationObserver(() => fn(el)).observe(el, opts || { childList: true, characterData: true, subtree: true }); };
    watch('#trace', el => post({ type: 'trace', steps: [...el.querySelectorAll('span')].map(s => ({ k: s.dataset.k, st: s.className, note: (s.querySelector('b') || {}).textContent || '' })) }),
      { attributes: true, subtree: true, childList: true });
    watch('#capYou', el => post({ type: 'you', text: el.textContent }));
    watch('#capJv', el => post({ type: 'jv', text: [...el.querySelectorAll('.w')].map(w => w.textContent.trim()).join(' ') || el.textContent }));
    watch('#stateText', el => post({ type: 'state', state: document.body.dataset.state || '', text: el.textContent }));
    watch('#modePill', el => post({ type: 'mode', m: el.dataset.m, text: el.textContent }), { attributes: true, childList: true, subtree: true });
    new MutationObserver(() => post({ type: 'stage', on: document.body.classList.contains('stage-on') })).observe(document.body, { attributes: true, attributeFilter: ['class'] });
    post({ type: 'ready' });
  }
  // what Mitra just did for the person (not a background refresh) raises the sheet on the right tab
  let lastAsk = 0;
  function hookUi() {
    const you = $('#capYou');
    if (you) new MutationObserver(() => { if (you.textContent.trim()) lastAsk = performance.now(); }).observe(you, { childList: true, characterData: true, subtree: true });
    if (typeof window.applyUi !== 'function' || window.applyUi.__m) return;
    const orig = window.applyUi;
    window.applyUi = function (ops) {
      const r = orig.apply(this, arguments);
      try {
        if (sheet && performance.now() - lastAsk < 15000 && !document.body.classList.contains('stage-on')) {
          const op = (ops || []).map(o => o.op).find(o => AUTO[o]);
          if (op) { tab(AUTO[op]); if (sheet.dataset.s === 'peek') setS('half'); }
        }
      } catch (e) { }
      return r;
    };
    window.applyUi.__m = true;
  }
  setup(); bridge(); hookUi();
  mq.addEventListener?.('change', () => setup());
  return { setup, labels, open: t => { tab(t); setS('half'); }, post };
})();
