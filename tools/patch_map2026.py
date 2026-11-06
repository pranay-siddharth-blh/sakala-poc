"""2026 restyle of the Karnataka live map: single-hue saffron choropleth on a cool-neutral canvas, emerald pilot glow,
vivid translucent taluks, ink/glass controls. Keeps the black state outline."""
import re

W = r"D:\Sakala POC\wireframe\index.html"
CSS = r"D:\Sakala POC\tools\future2.css"
s = open(W, encoding="utf-8").read()


def rep(old, new):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, 1)


rep("const CHORO = [[1.9,[191,227,198]],[3.0,[226,236,181]],[4.0,[253,224,166]],[5.5,[248,191,134]],[9.2,[239,143,116]]];",
    "const CHORO = [[1.9,[246,244,241]],[3.0,[252,234,216]],[4.2,[250,204,163]],[5.5,[246,162,108]],[9.2,[229,102,42]]];")
rep("if(v==null) return '#e6efe7';", "if(v==null) return '#eef0f3';")
s = re.sub(r"const TALUK_STYLE = \{.*?\};",
           "const TALUK_STYLE = { Piriyapatna:{fill:'#16c784', stroke:'#0e9f6e', kn:'ಪಿರಿಯಾಪಟ್ಟಣ'}, Hunsur:{fill:'#3b9bff', stroke:'#0a6fe0', kn:'ಹುಣಸೂರು'}, Mysuru:{fill:'#9b7bff', stroke:'#6d4ce6', kn:'ಮೈಸೂರು'} };",
           s, count=1, flags=re.S)
rep('<radialGradient id="kGlow"><stop offset="0" stop-color="#fbb756" stop-opacity=".6"/><stop offset="1" stop-color="#fbb756" stop-opacity="0"/></radialGradient>',
    '<radialGradient id="kGlow"><stop offset="0" stop-color="#16c784" stop-opacity=".55"/><stop offset="1" stop-color="#16c784" stop-opacity="0"/></radialGradient>')
rep('flood-color="#14421a" flood-opacity=".18"', 'flood-color="#0b0b0c" flood-opacity=".14"')
rep('flood-color="#0f3416" flood-opacity=".28"', 'flood-color="#0b0b0c" flood-opacity=".22"')
rep("const col=slaInfo(c).left<0?'#db4a38':c.vulnerable?'#c2185b':'#26732f';", "const col=slaInfo(c).left<0?'#e5484d':c.vulnerable?'#d6409f':'#0e9f6e';")
rep('<span><i style="background:#26732f"></i>On time</span><span><i style="background:#db4a38"></i>Overdue</span><span><i style="background:#c2185b"></i>Vulnerable</span>',
    '<span><i style="background:#0e9f6e"></i>On time</span><span><i style="background:#e5484d"></i>Overdue</span><span><i style="background:#d6409f"></i>Vulnerable</span>')
rep('<h6>Sakala 2025 · late delivery</h6>', '<h6>Sakala 2025 · late delivery %</h6>')
open(W, "w", encoding="utf-8").write(s)

css = open(CSS, encoding="utf-8").read()
if "/* ===== MAP 2026" not in css:
    css += """
/* ===== MAP 2026: single-hue saffron choropleth, emerald pilot, glass controls ===== */
.kmap{border-radius:22px;border:1px solid var(--line);background:
  radial-gradient(55% 65% at 58% 42%,#ffffff,rgba(255,255,255,0) 70%),
  radial-gradient(circle at 1px 1px,rgba(15,23,42,.07) 1px,transparent 1.5px) 0 0/16px 16px,
  linear-gradient(180deg,#f8f9fb,#eef1f5)}
.ko{fill:#0b0b0c;stroke:#0b0b0c}
.kd{stroke:#ffffff;stroke-width:calc(var(--sw) * 1.25);stroke-opacity:1;transition:fill .3s,filter .25s}
.kd:hover{filter:brightness(.96) saturate(1.25)}
.kd-hl{fill:#e3f8ee!important;stroke:#0e9f6e;stroke-width:calc(var(--sw) * 2.2);filter:drop-shadow(0 0 calc(var(--sw) * 7) rgba(22,199,132,.55))}
.kd-hl:hover{fill:#d3f4e4!important}
.kmap.moving .kd-hl{filter:none}
.kdl{fill:#64748b;font-weight:600;letter-spacing:.01em}
.kdl-hl{fill:#065f46;font-weight:700}
.kt{fill-opacity:.3;stroke-width:calc(var(--sw) * 1.8)}
.kt:hover{fill-opacity:.45}
.kt.on{fill-opacity:.16;stroke-width:calc(var(--sw) * 2.6)}
.ktl{fill:#0b0b0c;font-weight:700;stroke:rgba(255,255,255,.95)}
.km-dot{stroke:#fff;stroke-width:calc(var(--sw) * 2.4)}
.km-n{font-weight:700}
.kdot{stroke:#fff}
.kdot:hover{stroke:#0b0b0c}
.kmap-side{background:rgba(255,255,255,.76);backdrop-filter:blur(18px) saturate(1.6);-webkit-backdrop-filter:blur(18px) saturate(1.6);
  border:1px solid rgba(0,0,0,.06);border-radius:20px;box-shadow:0 24px 48px -28px rgba(0,0,0,.35);padding:12px}
.kmap-side h6{color:var(--mute-2);font-weight:600;letter-spacing:1.3px}
.ktk{border-radius:14px;border:1px solid rgba(0,0,0,.06);background:rgba(255,255,255,.9)}
.ktk:hover{box-shadow:0 8px 20px -10px rgba(0,0,0,.25);border-color:var(--s)}
.ktk.on{border-color:var(--s);box-shadow:0 0 0 3px color-mix(in srgb,var(--f) 25%,transparent)}
.ktk i{width:10px;height:10px;border-radius:50%;background:var(--f);box-shadow:0 0 0 3px color-mix(in srgb,var(--f) 22%,transparent)}
.ktk b,.ktk em{color:var(--ink)}
.kleg{color:var(--mute)}
.kscale b{height:8px;background:linear-gradient(90deg,rgb(246,244,241),rgb(252,234,216),rgb(250,204,163),rgb(246,162,108),rgb(229,102,42));box-shadow:inset 0 0 0 1px rgba(0,0,0,.05)}
.crumbs,.kmap-btns{background:rgba(255,255,255,.76);backdrop-filter:blur(18px);border:1px solid rgba(0,0,0,.06);border-radius:14px}
.crumbs b{color:var(--em)}
.kmap-btns button{color:var(--ink);font-weight:600;border-radius:10px}
.kmap-btns button:hover{background:rgba(0,0,0,.05)}
.kmap-tip{background:rgba(11,11,12,.86);backdrop-filter:blur(12px);border-radius:14px;border:1px solid rgba(255,255,255,.08)}
.kmap-tip b{color:var(--em-2)}
.kmap-attr{background:rgba(255,255,255,.6);color:var(--mute-2);border-radius:999px;padding:2px 9px}
"""
    open(CSS, "w", encoding="utf-8").write(css)
w = open(W, encoding="utf-8").read()
a = w.index("/* ===================== FUTURE 2"); b = w.index("</style>", a)
open(W, "w", encoding="utf-8").write(w[:a] + css + "\n" + w[b:])
print("map 2026 applied")
