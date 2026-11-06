"""Statewide map + labels for the CS dashboard (15 Oct 2026). Patches wireframe/index.html in place (backup kept);
run make_app_ui.py afterwards to regenerate app/web/index.html."""
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / "wireframe" / "index.html"
s = WF.read_text(encoding="utf-8")
if "distPoly(" in s:
    print("already patched"); sys.exit(0)
shutil.copy2(WF, ROOT / "tools" / "backups" / f"index.before_statewide_{datetime.now():%Y%m%d_%H%M}.html")


def rep(old, new, count=1):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, count)


# 1. district polygons + name matching + dots anywhere in the state
rep("function hashRand(str){",
    """const DIST_ALIAS={'Bagalkote':'Bagalkot','Bengaluru South':'Bengaluru South (Ramanagara)','Chamarajanagara':'Chamarajanagar','Davangere':'Davanagere','Vijayanagar':'Vijayanagara','Ramanagara':'Bengaluru South (Ramanagara)'};
const _dn=s=>String(s||'').toLowerCase().replace(/[^a-z]/g,'');
function distRec(name){ if(!name) return null; const a=DIST_ALIAS[name]||name; let d=KA_DIST.find(x=>x.n===a); if(d) return d; const n=_dn(a); return KA_DIST.find(x=>_dn(x.n)===n)||KA_DIST.find(x=>_dn(x.n).slice(0,6)===n.slice(0,6))||null; }
function distPoly(d){ if(d._poly) return d._poly; const nums=d.d.match(/-?\\d+\\.?\\d*/g).map(Number); const poly=[]; for(let i=0;i+1<nums.length;i+=2) poly.push([nums[i],nums[i+1]]); const xs=poly.map(p=>p[0]), ys=poly.map(p=>p[1]); d._poly=poly; d._bbox=[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)]; return poly; }
function distBox(name){ const d=typeof name==='string'?distRec(name):name; if(!d) return mysuruBox(); distPoly(d); return d._bbox; }
function distAt(x,y){ return KA_DIST.find(d=>inPoly(x,y,distPoly(d)))||null; }
function hashRand(str){""")
rep("function dotFor(c){ if(MAP.dots[c.id]) return MAP.dots[c.id]; const t=KA_TALUK[c.taluk]; if(!t) return null; const r=hashRand(c.id); const [x0,y0,x1,y1]=t.bbox;\n  for(let k=0;k<400;k++){ const x=x0+(x1-x0)*r(), y=y0+(y1-y0)*r(); if(inPoly(x,y,t.poly)) return MAP.dots[c.id]=[x,y]; } return MAP.dots[c.id]=t.c; }",
    """function dotFor(c){ if(MAP.dots[c.id]) return MAP.dots[c.id]; const r=hashRand(c.id); const t=KA_TALUK[c.taluk];
  if(t){ const [x0,y0,x1,y1]=t.bbox; for(let k=0;k<400;k++){ const x=x0+(x1-x0)*r(), y=y0+(y1-y0)*r(); if(inPoly(x,y,t.poly)) return MAP.dots[c.id]=[x,y]; } return MAP.dots[c.id]=t.c; }
  const d=distRec(c.district); if(!d) return null; const poly=distPoly(d), [x0,y0,x1,y1]=d._bbox;
  for(let k=0;k<300;k++){ const x=x0+(x1-x0)*r(), y=y0+(y1-y0)*r(); if(inPoly(x,y,poly)) return MAP.dots[c.id]=[x,y]; } return MAP.dots[c.id]=d.c; }""")

# 2. district level follows the district under the view, not always Mysuru
rep("  if (tk && w < boxToVb(mysuruBox(),.08)[2]*0.72) return {lv:'taluk', tk}; return {lv:'district'}; }",
    "  const dn=distAt(cx,cy); if (tk && dn && dn.n==='Mysuru' && w < boxToVb(mysuruBox(),.08)[2]*0.72) return {lv:'taluk', tk}; return {lv:'district', dn:dn?dn.n:'Mysuru'}; }")
rep("if(L.lv!=='state') parts.push(`<b data-k=\"district\">Mysuru district</b>`);",
    "if(L.lv!=='state') parts.push(`<b data-k=\"${L.dn||'Mysuru'}\">${esc(L.dn||'Mysuru')} district</b>`);")
rep("  if (k==='district') return glideTo(boxToVb(mysuruBox(),.08), 760);",
    "  if (k==='district') return glideTo(boxToVb(mysuruBox(),.08), 760);\n  if (distRec(k)) return glideTo(boxToVb(distBox(k),.08), 760);")

# 3. markers with open counts for every district, district tooltip with its open count, click any district to zoom
rep("  const counts={}, over={}; open.forEach(c=>{ counts[c.taluk]=(counts[c.taluk]||0)+1; if(slaInfo(c).left<0) over[c.taluk]=(over[c.taluk]||0)+1; });",
    "  const counts={}, over={}, dcount={}, dover={}; open.forEach(c=>{ counts[c.taluk]=(counts[c.taluk]||0)+1; if(slaInfo(c).left<0) over[c.taluk]=(over[c.taluk]||0)+1; const dr=distRec(c.district); const dn=dr?dr.n:c.district; dcount[dn]=(dcount[dn]||0)+1; if(slaInfo(c).left<0) dover[dn]=(dover[dn]||0)+1; }); MAP.dcount=dcount; MAP.dover=dover;")
rep("      <g id=\"kMark\">",
    "      <g id=\"kDMark\">${KA_DIST.filter(d=>d.n!=='Mysuru'&&dcount[d.n]).map(d=>`<g class=\"km kmd\" data-dn=\"${esc(d.n)}\" transform=\"translate(${d.c[0]},${d.c[1]-9})\"><circle class=\"km-glow\" r=\"1\" style=\"fill:${dover[d.n]?'#e5484d':'#0e9f6e'}\"/><circle class=\"km-dot\" r=\"1\" style=\"fill:${dover[d.n]?'#e5484d':'#0e9f6e'}\"/><text class=\"km-n\" y=\"0\">${dcount[d.n]}</text></g>`).join('')}</g>\n      <g id=\"kMark\">")
rep("    else if (m||p){ const k=(m||p).dataset.tk;",
    "    else if ((m||p) && (m||p).dataset.dn){ const k=(m||p).dataset.dn; tip.innerHTML=`<b>${esc(k)}</b><span>${MAP.dcount?.[k]||0} open requests${MAP.dover?.[k]?' · '+MAP.dover[k]+' overdue':''} · click to zoom in</span>`; }\n    else if (m||p){ const k=(m||p).dataset.tk;")
rep("tip.innerHTML=`<b>${esc(di.dataset.n)}</b><span class=\"tip-big\">${lt!=null?lt+'%':'n/a'} <small>delivered late · Sakala 2025</small></span><span>${rk?`#${rk} of ${all.length} districts (1 = most late)`:''}</span><span>${di.dataset.n==='Mysuru'?'Pilot district · click to zoom in':'Outside the pilot'}</span>`; }",
    "tip.innerHTML=`<b>${esc(di.dataset.n)}</b><span class=\"tip-big\">${lt!=null?lt+'%':'n/a'} <small>delivered late · Sakala 2025</small></span><span>${rk?`#${rk} of ${all.length} districts (1 = most late)`:''}</span><span>${(MAP.dcount?.[di.dataset.n]||0)} open requests${MAP.dover?.[di.dataset.n]?' · '+MAP.dover[di.dataset.n]+' overdue':''} · ${di.dataset.n==='Mysuru'?'pilot district · ':''}click to zoom in</span>`; }")
rep("    const t=e.target.closest('.km,.kt'); if(t){ hint.classList.add('off'); return mapGo(t.dataset.tk); }\n    const di=e.target.closest('.kd'); if(di && di.dataset.n==='Mysuru'){ hint.classList.add('off'); return mapGo('district'); } };",
    "    const t=e.target.closest('.km,.kt'); if(t){ hint.classList.add('off'); return mapGo(t.dataset.dn||t.dataset.tk); }\n    const di=e.target.closest('.kd'); if(di){ hint.classList.add('off'); return mapGo(di.dataset.n==='Mysuru'?'district':di.dataset.n); } };")
# category fly-to: never closer than a third of the Mysuru box, but allow the state when dots are spread
rep("  const mb=mysuruBox(), minW=(mb[2]-mb[0])*.34, minH=(mb[3]-mb[1])*.34, cx=(box[0]+box[2])/2, cy=(box[1]+box[3])/2;",
    "  const mb=mysuruBox(), minW=(mb[2]-mb[0])*.34, minH=(mb[3]-mb[1])*.34, cx=(box[0]+box[2])/2, cy=(box[1]+box[3])/2; MAP.catBox=box;")

# 4. labels
rep("<p class=\"sub\">Revenue · RDPR · Food & Civil Supplies · Mysuru district (pilot) · as of <b>${fmt(S.now)}</b></p>",
    "<p class=\"sub\">Revenue · RDPR · Food & Civil Supplies · all 31 districts of Karnataka · Mysuru pilot in depth · as of <b>${fmt(S.now)}</b></p>")
rep("<span class=\"badge b-s\" style=\"margin-left:6px\">Pilot · Mysuru district</span><span class=\"r\">${open.length} open requests · districts shaded by real Sakala 2025 late-delivery %</span>",
    "<span class=\"badge b-s\" style=\"margin-left:6px\">31 districts · 235 taluks</span><span class=\"r\">${open.length} open requests statewide · districts shaded by real Sakala 2025 late-delivery %</span>")
rep("<button data-k=\"district\" title=\"Mysuru district\">Mysuru</button>", "<button data-k=\"district\" title=\"Mysuru district (pilot, taluk detail)\">Mysuru</button>")
rep("      <h6>Pilot taluks</h6>", "      <h6>Mysuru pilot · taluk detail</h6>")
rep("<div class=\"kmap-hint\" id=\"kHint\">Scroll to zoom · drag to pan · click a taluk</div>", "<div class=\"kmap-hint\" id=\"kHint\">Scroll to zoom · drag to pan · click a district or taluk</div>")

WF.write_text(s, encoding="utf-8")
print("patched", WF)
