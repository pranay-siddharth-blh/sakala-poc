"""Mitra performance pass 3 (19 Oct 2026): main-thread cost per frame, measured with the GPU on (tests/perf_probe.py gpu): the orb's
frame 27 %, the stage particles 14 %, garbage-collection pauses (worst frame 55 ms).
- orb: the 1,700 particles were drawn one by one, each with a new rgba() string and a fillStyle switch -> drawn in 16 batches
  (2 colours x 8 alpha steps), one path and one fill per batch, no strings built per particle; while a chart is on stage (the orb
  is the small icon in the corner) it draws at 30 fps;
- orb: it wrote --lvl on <html> every frame, which dirtied the style of the whole page -> only when it changes visibly;
- stage particles: read clientHeight every frame (a forced style + layout after the write above) -> the size is cached and
  refreshed on resize."""
import io

ROOT = r"D:\Sakala POC\mitra\web"


def edit(path, pairs):
    p = ROOT + "\\" + path
    s = io.open(p, encoding="utf-8").read()
    for a, b in pairs:
        assert s.count(a) == 1, (path, a[:90], s.count(a))
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("patched", path)


edit("orb.js", [
    ("  function rgba(c, a) { return `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`; }",
     """  function rgba(c, a) { return `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`; }
  // particle batches: 2 colours x 8 alpha steps, each drawn as one path with one fill (no per-particle strings or state changes)
  const NB_A = 8, batch = Array.from({ length: 2 * NB_A }, () => []);
  let lastLvl = -1, skip = 0;"""),
    ("""    if (document.hidden || de.classList.contains('phone-on') || (de.dataset.started !== '1' && document.querySelector('#splash:not(.off)'))) { requestAnimationFrame(frame); return; }""",
     """    if (document.hidden || de.classList.contains('phone-on') || (de.dataset.started !== '1' && document.querySelector('#splash:not(.off)'))) { requestAnimationFrame(frame); return; }
    if (document.body.classList.contains('stage-on') && !P.down && (skip ^= 1)) { requestAnimationFrame(frame); return; }   // small corner icon: 30 fps"""),
    ("""    const f = 2.6, hovR = R * .5;
    for (const p of pts) {""",
     """    const f = 2.6, hovR = R * .5;
    for (const b of batch) b.length = 0;
    for (const p of pts) {"""),
    ("""      const c = deep(depth > .55 ? col[0] : col[1]);
      const sz = (.7 + depth * 1.9 + p.s * .6 + lift * 1.4) * dpr * (LIGHT ? 1.08 : 1);
      ctx.fillStyle = rgba(c, Math.min(1, LIGHT ? a * 1.05 + .05 : a));
      ctx.fillRect(px - sz / 2, py - sz / 2, sz, sz);
    }""",
     """      const sz = (.7 + depth * 1.9 + p.s * .6 + lift * 1.4) * dpr * (LIGHT ? 1.08 : 1);
      const al = Math.min(1, LIGHT ? a * 1.05 + .05 : a);
      batch[(depth > .55 ? 0 : NB_A) + Math.min(NB_A - 1, (al * NB_A) | 0)].push(px - sz / 2, py - sz / 2, sz);
    }
    for (let bi = 0; bi < batch.length; bi++) {
      const b = batch[bi]; if (!b.length) continue;
      ctx.fillStyle = rgba(deep(bi < NB_A ? col[0] : col[1]), ((bi % NB_A) + .5) / NB_A);
      ctx.beginPath();
      for (let i = 0; i < b.length; i += 3) ctx.rect(b[i], b[i + 1], b[i + 2], b[i + 2]);
      ctx.fill();
    }"""),
    ("    document.documentElement.style.setProperty('--lvl', smooth.toFixed(3));",
     "    if (Math.abs(smooth - lastLvl) > .006) { lastLvl = smooth; document.documentElement.style.setProperty('--lvl', smooth.toFixed(3)); }   // only a visible change dirties the page"),
])

edit("stage.js", [
    ("""    const w = innerWidth, h = cv.clientHeight || innerHeight;""",
     """    if (!FX.h || FX.vw !== innerWidth || FX.vh !== innerHeight) { FX.vw = innerWidth; FX.vh = innerHeight; FX.h = cv.clientHeight || innerHeight; }   // read the size once, not every frame
    const w = innerWidth, h = FX.h;"""),
])

import re
h = io.open(ROOT + r"\index.html", encoding="utf-8").read()
for name in ("orb.js", "stage.js"):
    h = re.sub(rf"/{re.escape(name)}\?v=(\d+)", lambda m: f"/{name}?v={int(m.group(1)) + 1}", h)
io.open(ROOT + r"\index.html", "w", encoding="utf-8", newline="").write(h)
print("bumped orb.js / stage.js")
