"""Map panel: On time / Overdue / Vulnerable as clickable KPI tiles that filter the dots, fly to them and list the cases."""
W = r"D:\Sakala POC\wireframe\index.html"
CSS = r"D:\Sakala POC\tools\future2.css"
s = open(W, encoding="utf-8").read()


def rep(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)


rep("  const counts={}, over={}; open.forEach(c=>{ counts[c.taluk]=(counts[c.taluk]||0)+1; if(slaInfo(c).left<0) over[c.taluk]=(over[c.taluk]||0)+1; });",
    "  const counts={}, over={}; open.forEach(c=>{ counts[c.taluk]=(counts[c.taluk]||0)+1; if(slaInfo(c).left<0) over[c.taluk]=(over[c.taluk]||0)+1; });\n"
    "  const isOver=c=>slaInfo(c).left<0, nOver=open.filter(isOver).length, nVul=open.filter(c=>c.vulnerable).length, nOn=open.length-nOver;\n"
    "  MAP.open=open;")
rep('''      <h6>Grievances</h6>
      <div class="kleg"><span><i style="background:#0e9f6e"></i>On time</span><span><i style="background:#e5484d"></i>Overdue</span><span><i style="background:#d6409f"></i>Vulnerable</span></div>''',
    '''      <h6>Grievances · tap to find</h6>
      <div class="kcats">
        <button class="kc" data-cat="ontime" style="--c:#0e9f6e" title="Show the grievances that are within their deadline"><b>${nOn}</b><small>On time</small></button>
        <button class="kc" data-cat="overdue" style="--c:#e5484d" title="Show the grievances past their deadline"><b>${nOver}</b><small>Overdue</small></button>
        <button class="kc" data-cat="vulnerable" style="--c:#d6409f" title="Show grievances from elderly, widows, disabled, pension- or ration-dependent citizens"><b>${nVul}</b><small>Vulnerable</small></button>
      </div>
      <div class="kc-list" id="kcList"></div>''')
# dots: tag each with its categories; draw overdue / vulnerable last so they sit on top of the green ones
rep('''      <g id="kDots">${open.map(c=>{const p=dotFor(c); if(!p) return ''; const col=slaInfo(c).left<0?'#e5484d':c.vulnerable?'#d6409f':'#0e9f6e'; return `<circle class="kdot" data-id="${c.id}" cx="${p[0].toFixed(2)}" cy="${p[1].toFixed(2)}" r="1" style="fill:${col}"/>`;}).join('')}</g>''',
    '''      <g id="kDots">${open.slice().sort((a,b)=>(isOver(a)*2+!!a.vulnerable)-(isOver(b)*2+!!b.vulnerable)).map(c=>{const p=dotFor(c); if(!p) return ''; const o=isOver(c), col=o?'#e5484d':c.vulnerable?'#d6409f':'#0e9f6e'; return `<circle class="kdot" data-id="${c.id}" ${o?'data-o="1"':'data-t="1"'} ${c.vulnerable?'data-v="1"':''} cx="${p[0].toFixed(2)}" cy="${p[1].toFixed(2)}" r="1" style="fill:${col}"/>`;}).join('')}</g>''')
# wire the tiles inside initMap; filter function at top level
rep("function initMap(){\n", '''/* filter the dots by category, fly to them and list the cases (click the tile again to clear) */
function setCat(cat){
  const m=$('#kmap'); if(!m) return; MAP.cat=cat||null;
  m.classList.remove('f-ontime','f-overdue','f-vulnerable'); if(cat) m.classList.add('f-'+cat);
  document.querySelectorAll('.kc').forEach(b=>b.classList.toggle('on', b.dataset.cat===cat));
  const list=$('#kcList'); if(!cat){ list.innerHTML=''; list.classList.remove('on'); return; }
  const pick={ontime:c=>slaInfo(c).left>=0, overdue:c=>slaInfo(c).left<0, vulnerable:c=>c.vulnerable}[cat];
  const rows=(MAP.open||[]).filter(pick).sort((a,b)=>slaInfo(a).left-slaInfo(b).left);
  list.innerHTML = rows.length ? rows.slice(0,40).map(c=>{ const s=slaInfo(c); return `<button data-id="${c.id}"><span><b>${c.id}</b><small>${esc(c.u.svc||'Scrutiny desk')} · ${esc(OFF[c.owner]?.short||'')}</small></span><em class="${s.left<0?'bad':''}">${s.left<0?(-s.left)+'d late':s.left+'d left'}</em></button>`; }).join('')
    + (rows.length>40?`<div class="kc-more">+${rows.length-40} more in All cases</div>`:'') : '<div class="kc-more">None right now</div>';
  list.classList.add('on');
  list.querySelectorAll('button[data-id]').forEach(b=>b.onclick=()=>openCase(b.dataset.id));
  // fly to the matching dots (bounding box with padding; never closer than a third of the district)
  const pts=rows.map(dotFor).filter(Boolean); if(!pts.length) return;
  const xs=pts.map(p=>p[0]), ys=pts.map(p=>p[1]); let box=[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)];
  const mb=mysuruBox(), minW=(mb[2]-mb[0])*.34, minH=(mb[3]-mb[1])*.34, cx=(box[0]+box[2])/2, cy=(box[1]+box[3])/2;
  box=[Math.min(box[0],cx-minW/2),Math.min(box[1],cy-minH/2),Math.max(box[2],cx+minW/2),Math.max(box[3],cy+minH/2)];
  $('#kHint')?.classList.add('off'); glideTo(clampVb(boxToVb(box,.18)), 820);
}
function initMap(){
''')
rep("  document.querySelectorAll('.ktk').forEach(b=>b.onclick=()=>{ hint.classList.add('off'); mapGo(b.dataset.tk); });",
    "  document.querySelectorAll('.ktk').forEach(b=>b.onclick=()=>{ hint.classList.add('off'); mapGo(b.dataset.tk); });\n"
    "  document.querySelectorAll('.kc').forEach(b=>b.onclick=()=>setCat(MAP.cat===b.dataset.cat?null:b.dataset.cat)); MAP.cat=null;")
open(W, "w", encoding="utf-8").write(s)

css = open(CSS, encoding="utf-8").read()
if "/* ===== MAP category tiles" not in css:
    css += """
/* ===== MAP category tiles: On time / Overdue / Vulnerable (filter + fly + list) ===== */
.kmap-side{width:236px;max-height:calc(100% - 76px);overflow-y:auto;scrollbar-width:none}
.kmap-side::-webkit-scrollbar{display:none}
.kcats{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.kc{position:relative;display:flex;flex-direction:column;align-items:flex-start;gap:1px;padding:9px 9px 8px;border-radius:14px;cursor:pointer;
  border:1px solid rgba(0,0,0,.06);background:#fff;text-align:left;transition:transform .18s,box-shadow .2s,border-color .2s,background .2s;overflow:hidden}
.kc::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--c)}
.kc b{font-size:1.15rem;font-weight:700;letter-spacing:-.02em;color:var(--ink);line-height:1.1;font-variant-numeric:tabular-nums}
.kc small{font-size:.62rem;font-weight:600;color:var(--mute);letter-spacing:.2px}
.kc:hover{transform:translateY(-2px);box-shadow:0 10px 22px -12px rgba(0,0,0,.3);border-color:color-mix(in srgb,var(--c) 45%,transparent)}
.kc.on{background:var(--c);border-color:var(--c);box-shadow:0 12px 26px -10px color-mix(in srgb,var(--c) 70%,transparent)}
.kc.on b,.kc.on small{color:#fff}
.kc.on::before{background:rgba(255,255,255,.5)}
.kc-list{display:none;flex-direction:column;gap:4px;margin-top:2px;max-height:210px;overflow-y:auto;scrollbar-width:thin;animation:rise .3s ease-out}
.kc-list.on{display:flex}
.kc-list button{display:flex;align-items:center;gap:8px;width:100%;text-align:left;padding:7px 9px;border-radius:11px;border:1px solid rgba(0,0,0,.05);background:rgba(255,255,255,.85);cursor:pointer;transition:background .15s,transform .15s}
.kc-list button:hover{background:#fff;transform:translateX(2px)}
.kc-list span{flex:1;min-width:0}
.kc-list b{display:block;font-size:.74rem;color:var(--ink)}
.kc-list small{display:block;font-size:.62rem;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kc-list em{font-style:normal;font-size:.64rem;font-weight:700;color:#0b7a3d;white-space:nowrap}
.kc-list em.bad{color:#c62f34}
.kc-more{font-size:.66rem;color:var(--mute);padding:4px 2px}
/* filtering: the other dots step back, the chosen ones grow and pulse */
.kmap.f-ontime .kdot:not([data-t]),.kmap.f-overdue .kdot:not([data-o]),.kmap.f-vulnerable .kdot:not([data-v]){opacity:.07;pointer-events:none}
.kmap.f-ontime .kdot[data-t],.kmap.f-overdue .kdot[data-o],.kmap.f-vulnerable .kdot[data-v]{r:calc(var(--dotr) * 1.55px);stroke-width:calc(var(--sw) * 2.2);animation:kdotPulse 1.6s ease-in-out infinite}
.kmap.f-vulnerable .kdot[data-v]{fill:#d6409f!important}
@keyframes kdotPulse{0%,100%{stroke-opacity:1}50%{stroke-opacity:.35}}
.kmap.moving .kdot{animation:none}
"""
    open(CSS, "w", encoding="utf-8").write(css)
w = open(W, encoding="utf-8").read()
a = w.index("/* ===================== FUTURE 2"); b = w.index("</style>", a)
open(W, "w", encoding="utf-8").write(w[:a] + css + "\n" + w[b:])
print("map category tiles applied")
