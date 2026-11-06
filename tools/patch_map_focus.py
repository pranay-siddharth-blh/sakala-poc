"""22 Oct 2026 (Pranay): a map question gets the MAP, not the six-card board. 'Show all grievances across Karnataka', 'on the
map', 'district-wise', 'across the state' -> one big Karnataka map in the centre (every district from SQL) with a small KPI
column and the level split beside it ('mapfocus' layout). 'Show it on the map' while a board is up switches to that layout
instead of turning every card into a little map. Everything else is unchanged."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def patch(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert old in s, f"{rel}: missing\n{old[:140]}"
        s = s.replace(old, new, 1)
    if rel.endswith(".py"):
        ast.parse(s)
    p.write_text(s, encoding="utf-8")
    print("patched", rel)


patch("mitra/server/board.py", [
    ('''def dashboard_view(r: dict) -> tuple[str, list]:''',
     '''MAP_RX = re.compile(r"\\b(on (?:a |the )?(?:single |big |one )?map|map|maps|across (?:the )?(?:state|karnataka)|state of karnataka|all over (?:the )?(?:state|karnataka)|"
                    r"district[- ]?wise|which parts|where (?:are|is) (?:the|most|all))\\b|ನಕ್ಷೆ|map", re.I)


def map_view(r: dict) -> tuple[str, list]:
    """The map question: one big Karnataka map (every district, from SQL) + a small KPI column + the level split."""
    k = r["kpis"]
    title = r.get("title") or "Karnataka"
    geo = sorted((r.get("geo") or {}).items(), key=lambda kv: -kv[1])
    ipgrs = r["source"] == "ipgrs"
    what = "grievances in process" if ipgrs else "open grievances"
    top = ", ".join(f"{d} {n:,}" for d, n in geo[:3])
    say = (f"Here are the {k['open']:,} {what} {'in ' + title if title != 'Karnataka' else 'across Karnataka'} on the map."
           + (f" The most are in {top}." if top else "") + (" From the iPGRS sample week." if ipgrs else ""))
    cards = [_card(f"{what.capitalize()} · {title}", [{"name": d, "value": n, "district": d, "aliases": [d.lower()]} for d, n in geo], "map",
                   f"{len(geo)} districts · {r.get('period') or ''}", by="district"),
             tiles([("Open" if not ipgrs else "In process", k["open"], ""), ("Overdue" if not ipgrs else "Closed", k["overdue"] if not ipgrs else k["closed"], "bad" if not ipgrs else "ok"),
                    ("Escalated" if not ipgrs else "At scrutiny", k["escalated_open"] if not ipgrs else k["scrutiny"], "vio"), ("Due soon" if not ipgrs else "Total", k["due_3"] if not ipgrs else k["total"], "warn")],
                   subtitle="at a glance"),
             _card("By level", [{"name": x["name"], "value": x["count"], "aliases": LEVEL_ALIAS[x["name"]]} for x in r["by_level"]], "bars", "open")]
    return say, [{"op": "viz", "title": f"{title} · on the map", "insight": f"{geo[0][0]} has the most, {geo[0][1]:,}" if geo else "", "cards": cards, "mapfocus": True}]


def dashboard_view(r: dict) -> tuple[str, list]:'''),
])

patch("mitra/server/query.py", [
    ('''    if name == "find_cases" and (args.get("level") or str(args.get("group_by") or "").lower() == "level") and not args.get("status") \\''',
     '''    wants_map = s.get("profile") == "cs" and (chart == "map" or bool(board.MAP_RX.search(said)))
    if wants_map and (name in ("dashboard", "statewide_stats") or (name in ("find_cases", "ipgrs_records") and str(args.get("status") or "").lower() in ("", "open", "pending")
                                                                 and str(args.get("group_by") or "").lower() in ("", "district") and not args.get("level") and not args.get("days_left"))):
        name = "dashboard"                                # a map question: the big map + a small KPI column, not the six-card board
        args = {k: v for k, v in args.items() if k in ("department", "district", "taluk", "gp", "level", "officer")}
    if name == "find_cases" and (args.get("level") or str(args.get("group_by") or "").lower() == "level") and not args.get("status") \\'''),
    ('''    if name == "dashboard":
        say, ui = board.dashboard_view(r)''',
     '''    if name == "dashboard":
        say, ui = board.map_view(r) if wants_map and r.get("geo") else board.dashboard_view(r)'''),
])

patch("mitra/web/stage.js", [
    ("host_.classList.toggle('board', !!op.board || op.cards.length > 3); document.body.classList.toggle('board-on', !!op.board || op.cards.length > 3);",
     "host_.classList.toggle('board', !op.mapfocus && (!!op.board || op.cards.length > 3)); document.body.classList.toggle('board-on', !op.mapfocus && (!!op.board || op.cards.length > 3)); host_.classList.toggle('mapfocus', !!op.mapfocus); document.body.classList.toggle('mapfocus-on', !!op.mapfocus);"),
    ('''    const op = JSON.parse(JSON.stringify(S.current)); op.cards.forEach(c => { if (!['kpi', 'tiles'].includes(c.type)) c.type = kind; });''',
     '''    const op = JSON.parse(JSON.stringify(S.current));
    if (kind === 'map' && (op.board || op.cards.length > 3)) {        // a board on the map: ONE big map + the KPIs beside it, not six little maps
      const place = op.cards.find(c => ['district', 'taluk'].includes(c.by)) || op.cards.find(c => c.items.some(i => i.district || (i.geo && Object.keys(i.geo).length)));
      const tilesC = op.cards.find(c => c.type === 'tiles'), lvl = op.cards.find(c => /level/i.test(c.title));
      if (place) {
        place.type = 'map';
        op.cards = [place, tilesC, lvl].filter(Boolean); op.board = false; op.mapfocus = true;
        show(op, { replay: true, morph: true });
        return { kind, ok: true, by: place.by || '' };
      }
    }
    op.cards.forEach(c => { if (!['kpi', 'tiles'].includes(c.type)) c.type = kind; });'''),
])

css = '''
/* v75 (22 Oct): a map question = one big map in the centre, a small KPI column and the level split beside it */
@media (min-width:601px){
  .stage-cards.mapfocus{grid-template-columns:minmax(0,2.3fr) minmax(0,1fr)!important;grid-template-rows:minmax(0,1.15fr) minmax(0,1fr);align-content:stretch;top:96px!important;bottom:86px!important;gap:14px}
  .stage-cards.mapfocus .vcard{display:flex;flex-direction:column;min-height:0}
  .stage-cards.mapfocus .vb{flex:1 1 auto;height:auto!important;min-height:0}
  .stage-cards.mapfocus .vcard.k-map{grid-row:1 / span 2}
  body.stage-in.mapfocus-on .composer{bottom:80px!important;max-width:440px}
  body.mapfocus-on .stage-insight{display:none!important}
}
'''
p = ROOT / "mitra/web/mitra.css"
p.write_text(p.read_text(encoding="utf-8") + css, encoding="utf-8")
p = ROOT / "mitra/web/index.html"
s = p.read_text(encoding="utf-8")
import re
s = re.sub(r"mitra\.css\?v=\d+", "mitra.css?v=75", s)
s = re.sub(r"stage\.js\?v=\d+", "stage.js?v=65", s)
p.write_text(s, encoding="utf-8")
print("done")
