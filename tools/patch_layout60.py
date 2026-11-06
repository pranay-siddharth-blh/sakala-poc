"""Stage + phone layout polish (19 Oct 2026, Pranay: "the top and bottom of the boxes do not look right, titles get covered,
the place names at the bottom of the graphs are crammed together", web and phone).
Seen in the screenshots:
- web: the "you said" line of the caption was cut off under the header; the insight chip sat on the composer (its ✦ on the mic);
- phone: the orb (150 px) parked over the card's top-right corner; the map panel repeated its legend under the chips in 9 px type
  and cut chip names ("Rural Development & P…"); the sheet pulled to full covered the app header; row pills were cut on the right;
- every size: bar labels drawn at full width however narrow the slot (names ran into each other), every month label drawn on a
  narrow line chart.
Fixes: one definitive layout layer (v60) with fixed zones (title, caption, cards, insight, composer, dock) that never overlap; the
orb parks as a 40 px badge in the title row on a phone; labels fitted to their slot (short names for long departments, ellipsis,
thinned month labels); the map chips use short names and the duplicate legend is gone on a phone; the full sheet stops under
the header; rows keep their pill."""
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
    # helpers: short names for long labels, text fitted to a width (cached)
    ("""  function label(ctx, text, x, y, { size = 12, weight = 600, color = null, align = 'center', glow = null } = {}) {""",
     """  const SHORT = { 'rural development & panchayat raj': 'RDPR', 'rural development and panchayat raj': 'RDPR', 'food & civil supplies': 'Food & Civil Supplies',
                  'food and civil supplies': 'Food & Civil Supplies', 'dakshina kannada': 'Dakshina Kannada', 'uttara kannada': 'Uttara Kannada' };
  const SHORTER = { 'food & civil supplies': 'Food', 'dakshina kannada': 'D. Kannada', 'uttara kannada': 'U. Kannada', 'bengaluru urban': 'Bengaluru U.',
                    'bengaluru rural': 'Bengaluru R.', 'chikkamagaluru': 'Chikkamagaluru', 'chamarajanagara': 'Chamarajanagar' };
  function shortLabel(t) { const k = String(t || '').toLowerCase(); return SHORT[k] || t; }
  const FT = new Map();
  function fitText(ctx, text, maxW, size = 12, weight = 600) {   // the label as it fits the slot: short name, then a shorter one, then an ellipsis
    const key = `${text}|${maxW | 0}|${size}|${weight}`; if (FT.has(key)) return FT.get(key);
    ctx.save(); ctx.font = `${weight} ${size}px Inter, system-ui, sans-serif`;
    let t = shortLabel(text);
    if (ctx.measureText(t).width > maxW) t = SHORTER[String(t).toLowerCase()] || SHORTER[String(text).toLowerCase()] || t;
    if (ctx.measureText(t).width > maxW) { let s = t; while (s.length > 2 && ctx.measureText(s + '…').width > maxW) s = s.slice(0, -1); t = s.trimEnd() + '…'; }
    ctx.restore(); if (FT.size > 800) FT.clear(); FT.set(key, t); return t;
  }
  function label(ctx, text, x, y, { size = 12, weight = 600, color = null, align = 'center', glow = null } = {}) {"""),
    # bars: the place name fitted to its slot; a smaller face when slots are narrow
    ("""        if (!it.on) { ctx.save(); ctx.setLineDash([4, 5]); ctx.strokeStyle = TK().line; ctx.strokeRect(x, base - 6, bw, 6); ctx.restore(); label(ctx, it.label, x + bw / 2, base + 20, { color: TK().mute2 }); return; }""",
     """        const ls = gw < 90 ? 11 : 12, lt = fitText(ctx, it.label, gw - 10, ls, 700);
        if (!it.on) { ctx.save(); ctx.setLineDash([4, 5]); ctx.strokeStyle = TK().line; ctx.strokeRect(x, base - 6, bw, 6); ctx.restore(); label(ctx, lt, x + bw / 2, base + 20, { color: TK().mute2, size: ls }); return; }"""),
    ("""        label(ctx, it.label, x + bw / 2, base + 20, { color: TK().ink, weight: 700 });""",
     """        label(ctx, lt, x + bw / 2, base + 20, { color: TK().ink, weight: 700, size: ls });"""),
    # line: only as many month labels as fit (every k-th, always the last)
    ("""      const peak = vals.indexOf(Math.max(...vals)), low = vals.indexOf(Math.min(...vals));
      items.forEach((it, i) => {
        const shown = i <= upto + 1e-6, col = i === peak ? '#ff9a3c' : i === low ? '#79e3ff' : '#16c784';
        label(ctx, it.label, X(i), H - pad.b + 18, { color: shown ? TK().ink : TK().mute2, weight: shown ? 700 : 600, size: 11 });""",
     """      const peak = vals.indexOf(Math.max(...vals)), low = vals.indexOf(Math.min(...vals));
      if (!card.lblW || card.lblN !== n) { ctx.save(); ctx.font = '700 11px Inter, system-ui, sans-serif'; card.lblW = Math.max(...items.map(it => ctx.measureText(it.label).width)); card.lblN = n; ctx.restore(); }
      const gap = (W - pad.l - pad.r) / Math.max(1, n - 1), every = Math.max(1, Math.ceil((card.lblW + 10) / Math.max(1, gap)));
      items.forEach((it, i) => {
        const shown = i <= upto + 1e-6, col = i === peak ? '#ff9a3c' : i === low ? '#79e3ff' : '#16c784';
        if (i % every === 0 || i === n - 1 && (n - 1) % every >= every / 2) label(ctx, it.label, X(i), H - pad.b + 18, { color: shown ? TK().ink : TK().mute2, weight: shown ? 700 : 600, size: 11 });"""),
    # map panel: short chip names; the category legend only where there is room
    ("""${esc(it.label.length > 22 ? it.label.slice(0, 21) + '…' : it.label)}<b>${it.on ? fmt(it.value) : ''}</b></button>`).join('')}</div>` : '';""",
     """${esc(shortLabel(it.label).length > 22 ? shortLabel(it.label).slice(0, 21) + '…' : shortLabel(it.label))}<b>${it.on ? fmt(it.value) : ''}</b></button>`).join('')}</div>` : '';"""),
    ("""${esc(it.label.length > 18 ? it.label.slice(0, 17) + '…' : it.label)}</span>`).join('')}</div>`""",
     """${esc(shortLabel(it.label).length > 18 ? shortLabel(it.label).slice(0, 17) + '…' : shortLabel(it.label))}</span>`).join('')}</div>`"""),
    # the orb: on a phone it parks as a small badge in the title row, never over a card
    ("""      const r = ow.getBoundingClientRect(), size = 150, tx = (innerWidth - 24 - size / 2) - (r.left + r.width / 2), ty = (84 + size / 2) - (r.top + r.height / 2);""",
     """      const phone = innerWidth < 600, hostTop = ($('#stageHost') || $('.stage-host') || { getBoundingClientRect: () => ({ top: 68 }) }).getBoundingClientRect().top || 68;
      const r = ow.getBoundingClientRect(), size = phone ? 40 : 132;
      const tx = (innerWidth - (phone ? 14 : 28) - size / 2) - (r.left + r.width / 2), ty = (phone ? hostTop + 4 + size / 2 : 84 + size / 2) - (r.top + r.height / 2);"""),
])

css = io.open(ROOT + r"\mitra.css", encoding="utf-8").read()
assert "/* v60 · layout" not in css
css += '''
/* v60 · layout: fixed zones on the stage that never overlap (title · caption · cards · insight · composer · dock), web and phone */
@media (min-width:601px){
  body.stage-in .captions{top:86px!important;max-height:52px!important;width:min(680px,52vw)!important;
    -webkit-mask-image:linear-gradient(180deg,transparent 0,#000 12px);mask-image:linear-gradient(180deg,transparent 0,#000 12px)}
  body.stage-in .captions .you{display:none!important}
  body.stage-in .composer{bottom:136px!important}
  .stage-insight{bottom:142px!important}
  .stage-cards{top:96px!important;bottom:206px!important}
}
@media (min-width:601px) and (max-height:760px){
  body.stage-in .composer{bottom:132px!important}
  .stage-insight{display:none!important}
  .stage-cards{bottom:150px!important}
}
.vh{min-height:22px;padding-right:2px}
.vh b{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.vh small,.vh span{flex:none;white-space:nowrap}
/* rows keep their pill: ring · text (ellipsis) · pill */
.row:has(.ring){grid-template-columns:auto minmax(0,1fr) auto}
.row>div{min-width:0}
.row .pill{white-space:nowrap;flex:none}
@media (max-width:600px){
  /* the stage on a phone: title row (orb badge on its right), two caption lines, then the cards */
  .stage-title{top:12px!important;left:14px!important;right:64px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  body.stage-in .captions{top:calc(56px + var(--safe-top,0px) + 34px)!important;left:14px!important;right:14px!important;transform:none!important;
    width:auto!important;max-height:36px!important;text-align:left!important;
    -webkit-mask-image:linear-gradient(180deg,transparent 0,#000 9px);mask-image:linear-gradient(180deg,transparent 0,#000 9px)}
  body.stage-in .captions .jv{font-size:12.5px!important;line-height:1.4!important}
  .stage-cards{top:80px!important;bottom:178px!important;padding-top:2px}
  .vcard{padding:12px 12px 10px}
  .vh{margin-bottom:6px}.vh b{font-size:13.5px}
  /* the map: chips (short names) + the top two; no second legend */
  .vcard.k-map .mp-leg-cat{display:none!important}
  .vcard.k-map .mp-chips{-webkit-mask-image:linear-gradient(90deg,#000 85%,transparent);mask-image:linear-gradient(90deg,#000 85%,transparent);padding-right:18px}
  .vcard.k-map .mp-chips button{font-size:11px;padding:5px 9px}
  .vcard.k-map .mp-r{font-size:11.5px}
  /* the sheet pulled up stops under the header */
  .msheet[data-s=full]{height:calc(100% - 56px - var(--safe-top,0px) - 8px)!important}
}
'''
io.open(ROOT + r"\mitra.css", "w", encoding="utf-8", newline="").write(css)
print("patched mitra.css")

h = io.open(ROOT + r"\index.html", encoding="utf-8").read()
h = re.sub(r"/mitra\.css\?v=\d+", "/mitra.css?v=60", h)
h = re.sub(r"/stage\.js\?v=(\d+)", lambda m: f"/stage.js?v={int(m.group(1)) + 1}", h)
io.open(ROOT + r"\index.html", "w", encoding="utf-8", newline="").write(h)
print("bumped mitra.css / stage.js")
