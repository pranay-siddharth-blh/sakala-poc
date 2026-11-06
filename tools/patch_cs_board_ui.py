"""22 Oct 2026: the CS command board (8 KPI tiles, the 7-day clock, levels, departments, busiest districts; every tile a question)
and the scope chip, on web and phone; the server sends the board with the CS home panel."""
import ast
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BK = ROOT / "tools" / "backups" / "res22b"
BK.mkdir(parents=True, exist_ok=True)


def patch(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    shutil.copy(p, BK / (p.name + ".ui.bak"))
    for old, new in pairs:
        assert old in s, f"{rel}: missing\n{old[:140]}"
        s = s.replace(old, new, 1)
    if rel.endswith(".py"):
        ast.parse(s)
    p.write_text(s, encoding="utf-8")
    print("patched", rel)


patch("mitra/server/tools.py", [
    ('''    return {"op": "kpi", "now": st["now"], "pending": len(opened), "overdue": len(overdue), "vulnerable": len(vul),''',
     '''    board = {}
    try:
        b = await sakala._post("/api/query", {"tool": "dashboard", "args": {}})
        if not b.get("http"):
            board = {"kpis": b["kpis"], "days_left": b["days_left"], "by_level": b["by_level"], "departments": b.get("departments") or [],
                     "places": (b.get("places") or [])[:6], "officers": (b.get("officers") or [])[:5]}
    except Exception:
        board = {}
    return {"op": "kpi", "board": board, "now": st["now"], "pending": len(opened), "overdue": len(overdue), "vulnerable": len(vul),'''),
])

patch("mitra/web/mitra.js", [
    ('''  kpi(op) {
    const dept = Object.entries(op.byDept).sort((a, b) => b[1] - a[1]); const max = Math.max(1, ...dept.map(d => d[1]));''',
     '''  kpi(op) {
    if (op.board && op.board.kpis) return UI.board(op);
    const dept = Object.entries(op.byDept).sort((a, b) => b[1] - a[1]); const max = Math.max(1, ...dept.map(d => d[1]));'''),
    ('''  filter(op) {
    const rows = op.cases || [];''',
     '''  // the Chief Secretary's command board: every tile, bar and row is a question she can also ask by voice
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
      <div class="clock" data-say="show me the 7 day timeline">${dl.map((x, i) => `<div class="cb ${i === 0 ? 'od' : i === 1 ? 'dt' : ''}" title="${esc(x.name)}: ${x.count}"><b>${x.count}</b><i style="height:${Math.max(3, Math.round(Math.sqrt(x.count / mx) * 52))}px"></i><span>${esc(x.name.replace(' days left', 'd').replace(' day left', 'd').replace('Due today', 'today').replace('Overdue', 'late').replace('8+ d', '8+'))}</span></div>`).join('')}</div>
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
    const rows = op.cases || [];'''),
    # the chip leaves with the CS desk
    ('''  profile(op) { if (op.profile !== J.profile && !Portal.busy) Portal.flash(op.profile, { from: J.profile });''',
     '''  profile(op) { const sc = $('#scopeChip'); if (sc && op.profile !== 'cs') sc.classList.remove('on'); if (op.profile !== J.profile && !Portal.busy) Portal.flash(op.profile, { from: J.profile });'''),
])
print("done")
