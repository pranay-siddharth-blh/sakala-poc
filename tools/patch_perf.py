"""Mitra performance pass (19 Oct 2026, Pranay: "very laggy, the map sometimes does not come, out of the layout").
Measured with tests/perf_ablate.py while the department map is open on the CS desk: 18 fps as shipped; 31 without backdrop blur,
31 without the looping CSS animations, 32 without the animated aurora; 60 with all of them off. Inside the phone frame: 6 fps.
Causes and fixes (same look):
- the start screen kept animating after Start (revolving map, sheen, halo; its canvas loop); in the phone view it kept drawing
  behind the phone, under a full-screen backdrop blur that was recomputed every frame -> stopped after Start, frozen behind the phone;
- the aurora (three ~1M px blurred blobs) drifted forever and changed filter on stage entry -> GPU layer, paused while a chart is up;
- the map card's scan line animated `top` and the stage beam `left` (layout + repaint every frame) -> transform;
- backdrop-filter on every panel over an already 90px-blurred aurora (no visible effect, full cost) -> removed there, kept on menus;
- the dashboard columns blurred (filter) while sinking -> opacity + transform only;
- the live orb kept drawing while hidden under the start screen / behind the phone -> skipped."""
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


edit("splash.js", [
    ('''  function frame(now) {
    if (!alive) return;
    raf = requestAnimationFrame(frame);
    if (document.hidden) return;
    drawMap(now); drawOrb(now);
  }''',
     '''  function frame(now) {
    if (!alive) return;
    raf = requestAnimationFrame(frame);
    if (document.hidden || document.documentElement.classList.contains('phone-on')) return;   // frozen behind the phone
    drawMap(now); drawOrb(now);
  }'''),
    ('''  function finish() {
    root.classList.add('off');
    setTimeout(() => { alive = false; cancelAnimationFrame(raf); }, 900);
  }''',
     '''  function finish() {
    root.classList.add('off');
    setTimeout(() => { alive = false; cancelAnimationFrame(raf); root.classList.add('gone'); }, 900);   // gone: no layer, no animation left running
  }'''),
])

edit("phone.js", [
    ('''    opts = o || {};
    root = document.createElement('div'); root.id = 'phoneStage'; root.className = 'phone-stage';''',
     '''    opts = o || {};
    document.documentElement.classList.add('phone-on');          // the page behind the phone stands still (it is only a backdrop)
    root = document.createElement('div'); root.id = 'phoneStage'; root.className = 'phone-stage';'''),
    ('''    const r = root; root = null;
    document.body.classList.remove('app-over');''',
     '''    const r = root; root = null;
    document.documentElement.classList.remove('phone-on');
    document.body.classList.remove('app-over');'''),
])

edit("orb.js", [
    ('''  function frame() {
    const now = performance.now(), t = (now - t0) / 1000;''',
     '''  function frame() {
    const de = document.documentElement;                     // hidden (start screen up, phone open over it, tab in the background): skip
    if (document.hidden || de.classList.contains('phone-on') || (de.dataset.started !== '1' && document.querySelector('#splash:not(.off)'))) { requestAnimationFrame(frame); return; }
    const now = performance.now(), t = (now - t0) / 1000;'''),
])

edit("stage.js", [
    ('''    card.W = w; card.H = h;
  }''',
     '''    card.W = w; card.H = h;
    card.el.style.setProperty('--ch', Math.round(card.el.offsetHeight) + 'px');   // the scan line travels this far (transform, not top)
  }'''),
])

css = io.open(ROOT + r"\mitra.css", encoding="utf-8").read()
assert "/* v58 · performance" not in css
css += '''
/* v58 · performance: the same look, a fraction of the paint (19 Oct). See tools/patch_perf.py for the measurements. */
#splash.gone{display:none!important}
html.phone-on #splash,html.phone-on #splash *,html.phone-on body>:not(#phoneStage),html.phone-on body>:not(#phoneStage) *{animation-play-state:paused!important}
.aurora{will-change:transform;contain:strict}
body.stage-on .aurora{animation-play-state:paused}
body.stage-in .bg .aurora,html[data-theme=light] body.stage-in .bg .aurora{filter:blur(90px)}
html[data-theme=light] body.stage-in .bg .aurora{filter:blur(90px) saturate(1.25)}
body.stage-in .col.left,body.stage-in .col.right{filter:none!important}
body.stage-on .col.left,body.stage-on .col.right{will-change:transform,opacity}
.vcard::after{top:0!important;animation:scanT 3.6s linear infinite!important;will-change:transform}
@keyframes scanT{from{transform:translateY(0)}to{transform:translateY(var(--ch,320px))}}
.stage-beam{left:0!important;will-change:transform;transform:translateX(-40vw) skewX(-14deg)}
body.stage-in .stage-beam{animation:beamSweepT 2.2s cubic-bezier(.2,.8,.2,1) .2s both!important}
@keyframes beamSweepT{from{transform:translateX(-40vw) skewX(-14deg)}to{transform:translateX(130vw) skewX(-14deg)}}
.card,.top,.feed,.orb-state,.mode-pill,.dock-chip,.stage-kinds button,.mpanel,.vcard,.msheet{backdrop-filter:none!important;-webkit-backdrop-filter:none!important}
.vcard{background:linear-gradient(160deg,rgba(28,30,38,.94),rgba(10,11,15,.94))}
html[data-theme=light] .vcard{background:linear-gradient(160deg,rgba(255,255,255,.98),rgba(248,250,253,.96))}
.top{background:rgba(8,8,11,.86)}html[data-theme=light] .top{background:rgba(255,255,255,.9)}
.feed{background:rgba(8,8,11,.86)}html[data-theme=light] .feed{background:rgba(255,255,255,.9)}
.phone-stage.solo{backdrop-filter:blur(18px)}
html.phone-on .phone-stage.solo{backdrop-filter:none;background:radial-gradient(1000px 700px at 50% 45%,rgba(22,199,132,.14),transparent 62%),rgba(5,5,7,.94)}
html[data-theme=light].phone-on .phone-stage.solo{background:radial-gradient(1000px 700px at 50% 45%,rgba(14,159,110,.10),transparent 62%),rgba(243,245,249,.95)}
'''
io.open(ROOT + r"\mitra.css", "w", encoding="utf-8", newline="").write(css)
print("patched mitra.css")

h = io.open(ROOT + r"\index.html", encoding="utf-8").read()
for name, v in (("mitra.css", 58), ("stage.js", None), ("orb.js", None), ("splash.js", None), ("phone.js", None)):
    m = re.search(rf"/{re.escape(name)}\?v=(\d+)", h)
    if m:
        h = h.replace(m.group(0), f"/{name}?v={v or int(m.group(1)) + 1}")
io.open(ROOT + r"\index.html", "w", encoding="utf-8", newline="").write(h)
print("bumped asset versions")
