"""Karnataka map v3: no black outline (white rim + floating shadow), Karnataka-flag heat scale (butter → flag yellow →
amber → flag red), RDPR-style hover (district lifts to the front with a glow), tooltip with rank. Pilot Mysuru stays emerald."""
import re

W = r"D:\Sakala POC\wireframe\index.html"
CSS = r"D:\Sakala POC\tools\future2.css"
s = open(W, encoding="utf-8").read()


def rep(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)


s = re.sub(r"const CHORO = \[.*?\];",
           "const CHORO = [[1.9,[255,246,214]],[2.6,[255,226,128]],[3.4,[255,205,0]],[4.4,[255,159,67]],[5.6,[240,85,58]],[9.2,[200,16,46]]];",
           s, count=1)
rep("if(v==null) return '#eef0f3';", "if(v==null) return '#f3f1ea';")
# hover: bring the district under the pointer to the front (RDPR style) + ranked tooltip
rep("    else if (di){ const lt=KA_LATE[di.dataset.n]; tip.innerHTML=`<b>${esc(di.dataset.n)}</b><span>Sakala 2025 late delivery: ${lt!=null?lt+'%':'n/a'}</span><span>${di.dataset.n==='Mysuru'?'Pilot district · click to zoom in':'Outside the pilot'}</span>`; }",
    "    else if (di){ if (MAP.hot!==di && !di.classList.contains('kd-hl')){ MAP.hot?.classList.remove('hot'); di.classList.add('hot'); di.parentNode.appendChild(di); const hl=di.parentNode.querySelector('.kd-hl'); if(hl) di.parentNode.appendChild(hl); MAP.hot=di; }\n"
    "      const lt=KA_LATE[di.dataset.n], all=Object.values(KA_LATE), rk=lt!=null?all.filter(v=>v>lt).length+1:null;\n"
    "      tip.innerHTML=`<b>${esc(di.dataset.n)}</b><span class=\"tip-big\">${lt!=null?lt+'%':'n/a'} <small>delivered late · Sakala 2025</small></span><span>${rk?`#${rk} of ${all.length} districts (1 = most late)`:''}</span><span>${di.dataset.n==='Mysuru'?'Pilot district · click to zoom in':'Outside the pilot'}</span>`; }")
rep("  svg.addEventListener('pointerleave', ()=>tip.classList.remove('on'));",
    "  svg.addEventListener('pointerleave', ()=>{ tip.classList.remove('on'); MAP.hot?.classList.remove('hot'); MAP.hot=null; });")
rep('<radialGradient id="kGlow"><stop offset="0" stop-color="#16c784" stop-opacity=".55"/>', '<radialGradient id="kGlow"><stop offset="0" stop-color="#16c784" stop-opacity=".6"/>')
rep('flood-color="#0b0b0c" flood-opacity=".22"', 'flood-color="#7a1d12" flood-opacity=".22"')
open(W, "w", encoding="utf-8").write(s)

css = open(CSS, encoding="utf-8").read()
if "/* ===== MAP v3" not in css:
    css += """
/* ===== MAP v3: Karnataka-flag heat scale, no black outline, floating white rim, RDPR-style hover lift ===== */
.ko{fill:#ffffff;stroke:#ffffff;stroke-width:calc(var(--sw) * 7);stroke-linejoin:round}
#kOut{filter:url(#kLift)}
.kd{stroke:rgba(255,255,255,.95);stroke-width:calc(var(--sw) * 1.35);stroke-linejoin:round;cursor:pointer;transition:fill .35s ease,filter .2s ease,stroke-width .2s ease}
.kd:hover,.kd.hot{filter:brightness(1.06) saturate(1.15) drop-shadow(0 calc(var(--sw) * 5) calc(var(--sw) * 7) rgba(150,20,30,.38));stroke:#fff;stroke-width:calc(var(--sw) * 2.6)}
.kd-hl{fill:#dff7ec!important;stroke:#0e9f6e;stroke-width:calc(var(--sw) * 2.4);filter:drop-shadow(0 0 calc(var(--sw) * 8) rgba(22,199,132,.6))}
.kd-hl:hover{fill:#cdf2e1!important}
.kmap.moving .kd,.kmap.moving .kd:hover,.kmap.moving .kd.hot,.kmap.moving .kd-hl{filter:none}
.kdl{fill:#3b2a1a;font-weight:600;opacity:.85}
.kscale b{background:linear-gradient(90deg,rgb(255,246,214),rgb(255,226,128),rgb(255,205,0),rgb(255,159,67),rgb(240,85,58),rgb(200,16,46))}
.kmap-tip .tip-big{font-size:1.05rem;font-weight:700;color:#fff;letter-spacing:-.01em;margin:2px 0}
.kmap-tip .tip-big small{font-size:.66rem;font-weight:500;color:rgba(255,255,255,.65)}
.kmap-tip b{color:#ffd84d}
"""
    open(CSS, "w", encoding="utf-8").write(css)
w = open(W, encoding="utf-8").read()
a = w.index("/* ===================== FUTURE 2"); b = w.index("</style>", a)
open(W, "w", encoding="utf-8").write(w[:a] + css + "\n" + w[b:])
print("map v3 applied")
