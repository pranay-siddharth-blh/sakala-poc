"""Mitra performance pass 2 (19 Oct 2026). The real costs, found by reading every element's computed style while the department map
is open (not by guessing): the three aurora blobs (about 2.8M px of layer, each re-filtered with blur(90px) every frame), and the map
card + its side panel keeping filter:blur(0px) after their entrance animation (fill-mode both), which makes a 330k px card a filtered
layer for ever. Fixes, same look:
- aurora: no filter; the radial gradients get the soft falloff the blur used to give (they were already soft gradients);
- a card / panel / insight chip that has finished its entrance is marked .settled and drops the animation (and with it the zero blur);
  later animations (morph ghost, exit) are more specific and still run;
- the stage beam: no blur filter, a softer gradient instead."""
import io
import re

ROOT = r"D:\Sakala POC\mitra\web"


def edit(path, pairs):
    p = ROOT + "\\" + path
    s = io.open(p, encoding="utf-8").read()
    for a, b in pairs:
        assert s.count(a) == 1, (path, a[:90], s.count(a))
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("patched", path)


edit("stage.js", [
    ("const Stage = (() => {",
     """// an entrance animation that has finished leaves filter:blur(0) behind (fill-mode both) and keeps the element a filtered layer:
// mark it settled so the animation (and the filter) is dropped. Ghost, exit and morph animations are more specific and still run.
document.addEventListener('animationend', e => {
  if (/^(vcardIn|vcardMorph|mpIn|insightIn)$/.test(e.animationName) && e.target.classList) { e.target.classList.add('settled'); e.target.classList.remove('morphing'); }
}, true);
const Stage = (() => {"""),
])

css = io.open(ROOT + r"\mitra.css", encoding="utf-8").read()
assert "/* v59 · performance 2" not in css
css += '''
/* v59 · performance 2: no full-screen filters, no settled card left as a filtered layer (19 Oct) */
.aurora,html[data-theme=light] .aurora,body.stage-in .bg .aurora,html[data-theme=light] body.stage-in .bg .aurora{filter:none!important}
.a1{background:radial-gradient(circle closest-side,rgba(22,199,132,.40) 0%,rgba(22,199,132,.24) 30%,rgba(22,199,132,.09) 58%,rgba(22,199,132,0) 100%)}
.a2{background:radial-gradient(circle closest-side,rgba(255,154,60,.28) 0%,rgba(255,154,60,.16) 30%,rgba(255,154,60,.06) 58%,rgba(255,154,60,0) 100%)}
.a3{background:radial-gradient(circle closest-side,rgba(59,155,255,.26) 0%,rgba(59,155,255,.15) 30%,rgba(59,155,255,.05) 58%,rgba(59,155,255,0) 100%)}
html[data-theme=light] .aurora{opacity:.62}
.vcard:where(.settled),.mpanel:where(.settled),.insight:where(.settled){animation:none}
.stage-beam{filter:none!important;background:linear-gradient(90deg,transparent,rgba(121,227,255,.05) 30%,rgba(22,199,132,.10) 50%,rgba(121,227,255,.05) 70%,transparent)!important}
html[data-theme=light] .stage-beam{background:linear-gradient(90deg,transparent,rgba(14,159,110,.06) 30%,rgba(43,127,217,.08) 50%,rgba(14,159,110,.06) 70%,transparent)!important}
'''
io.open(ROOT + r"\mitra.css", "w", encoding="utf-8", newline="").write(css)
print("patched mitra.css")

h = io.open(ROOT + r"\index.html", encoding="utf-8").read()
h = re.sub(r"/mitra\.css\?v=\d+", "/mitra.css?v=59", h)
h = re.sub(r"/stage\.js\?v=(\d+)", lambda m: f"/stage.js?v={int(m.group(1)) + 1}", h)
io.open(ROOT + r"\index.html", "w", encoding="utf-8", newline="").write(h)
print("bumped asset versions")
