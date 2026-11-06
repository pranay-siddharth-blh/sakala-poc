"""Replace every placeholder clock mark with the official Sakala logo (vector redraw of sakala.kar.nic.in/img/Sakala_logo.jpg)."""
import os
import re
import shutil

ROOT = r"D:\Sakala POC"
svgp = os.path.join(ROOT, "tools", "sakala-logo.svg")
s = open(svgp, encoding="utf-8").read()
s = s.replace('<path id="sakArcTop" d="M 55.6 52.2 A 52.5 52.5 0 0 1 139.4 30.4"/>',
              '<path id="sakArcTop" d="M 55.6 52.2 A 52.5 52.5 0 0 1 145.2 36.3"/>')
open(svgp, "w", encoding="utf-8").write(s)
for d in (os.path.join(ROOT, "wireframe", "assets"), os.path.join(ROOT, "app", "web", "assets")):
    shutil.copyfile(svgp, os.path.join(d, "sakala-logo.svg"))

IMG = '<img src="assets/sakala-logo.svg" alt="Sakala" class="sk-logo">'
rx = re.compile(r'<svg[^>]*viewBox="0 0 64 64"[^>]*>(?:(?!</svg>).)*?#da6823(?:(?!</svg>).)*?</svg>', re.S)

css_path = os.path.join(ROOT, "tools", "future2.css")
css = open(css_path, encoding="utf-8").read()
if ".sk-logo{" not in css:
    css += """
/* official Sakala logo (vector redraw of sakala.kar.nic.in/img/Sakala_logo.jpg) */
.sk-logo{display:block;object-fit:contain;background:#fff}
.halo .sk-logo{position:relative;z-index:1;width:84px;height:84px;border-radius:50%;padding:9px;animation:popIn .7s ease-out .12s both}
.logo-halo .sk-logo{height:40px;width:40px;border-radius:50%;padding:3px;box-shadow:0 0 0 1px var(--line)}
.wa-av .sk-logo{width:100%;height:100%;border-radius:50%;padding:2px}
"""
    open(css_path, "w", encoding="utf-8").write(css)

p = os.path.join(ROOT, "wireframe", "index.html")
w = open(p, encoding="utf-8").read()
w, n = rx.subn(IMG, w)
print("wireframe clock marks replaced:", n)
if 'rel="icon"' not in w:
    w = w.replace("<title>", '<link rel="icon" type="image/svg+xml" href="assets/sakala-logo.svg">\n<title>', 1)
a = w.index("/* ===================== FUTURE 2")
b = w.index("</style>", a)
w = w[:a] + css + "\n" + w[b:]
open(p, "w", encoding="utf-8").write(w)
print("remaining clock marks in wireframe:", len(rx.findall(w)))

for name in ("app_wa_client.js", "wa_module.js"):
    f = os.path.join(ROOT, "tools", name)
    t = open(f, encoding="utf-8").read()
    t, n = rx.subn(IMG, t)
    open(f, "w", encoding="utf-8").write(t)
    print(name, "replaced:", n)
