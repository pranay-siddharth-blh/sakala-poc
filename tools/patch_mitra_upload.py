"""22 Oct 2026 (Pranay): (1) the document door reachable in the PHONE app and by voice on both: a paperclip "Upload" button in the
composer (citizen), a new intent `upload_document` ("I want to upload a letter / attach my complaint") that raises the request card,
lights the drop zone and tells the person to tap it (a browser never opens the file picker without a tap), declared to Live;
(2) the product is called plain "Mitra" everywhere (web, phone, splash, pills, stage notes, audit strings); Sakala / iPGRS stay
only as the services. Backups in tools/backups/res22/."""
import ast
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BK = ROOT / "tools" / "backups" / "res22"
BK.mkdir(parents=True, exist_ok=True)


def patch(rel, pairs, subs=()):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    shutil.copy(p, BK / (p.name + ".bak"))
    for old, new in pairs:
        assert old in s, f"{rel}: missing\n{old[:160]}"
        s = s.replace(old, new, 1)
    for old, new in subs:
        s = s.replace(old, new)
    if rel.endswith(".py"):
        ast.parse(s)
    p.write_text(s, encoding="utf-8")
    print("patched", rel)


# ------------------------------------------------------------------ brain: the intent, deterministic
patch("mitra/server/brain.py", [
    ('''    "identity":       (("*",),''',
     '''    "upload_document": (("citizen",), "The person wants to upload / attach / scan / send a written complaint, letter, petition, PDF or photo of a document "
                      "('I want to upload a letter', 'can I attach my complaint', 'I have a written petition', 'upload'). Opens the upload box on screen; files nothing by itself.", ()),
    "identity":       (("*",),'''),
    ('''    if pre["intent"] in ("go_to", "show_chart_as", "set_theme", "identity", "forget_conversation", "confirm_action", "cancel_action", "view_as_officer") \\''',
     '''    if pre["intent"] in ("go_to", "show_chart_as", "set_theme", "identity", "forget_conversation", "confirm_action", "cancel_action", "view_as_officer", "upload_document") \\'''),
    ('''    if re.match(r"^\\s*(stop|cancel|never mind|nevermind|quiet|shut up|enough)\\b", low):
        return {"intent": "stop"}''',
     '''    if re.match(r"^\\s*(stop|cancel|never mind|nevermind|quiet|shut up|enough)\\b", low):
        return {"intent": "stop"}
    # the document door by voice: "I want to upload a letter", "can I attach my written complaint", "upload"
    if ctx.get("profile") == "citizen" and (UPLOAD_RX.search(low) or re.fullmatch(r"\\s*(upload|attach|attachment|upload (a )?(file|document|letter|pdf|photo))\\s*[.!]?\\s*", low)):
        return {"intent": "upload_document"}'''),
    ('''def rules(ctx''',
     '''UPLOAD_RX = re.compile(r"\\b(upload|attach|scan|send (you|in)?)\\s*(a |my |the |this |an )?(written |handwritten |signed |scanned )?(complaint|letter|petition|document|pdf|file|photo|application|form)s?\\b"
                       r"|\\b(i (have|got|am holding)|there is|here is) (a |my |the )?(written|handwritten|signed|scanned|paper) (complaint|letter|petition|application)\\b"
                       r"|\\b(how|where) (do|can) i (upload|attach|send) (a |my |the )?(letter|complaint|petition|document|pdf|photo|file)\\b"
                       r"|\\bupload(ing)? (a |my |the )?(written )?(complaint|letter|petition|document|pdf|photo|file)\\b", re.I)


def rules(ctx'''),
])

# ------------------------------------------------------------------ Live instruction
patch("mitra/server/live.py", [
    ('''uploaded shows as a form on screen: 'submit' / 'file it' -> confirm; 'the phone number is …' / 'my name is …' / "
                     "'the village is …' -> chat_text with those words.")''',
     '''uploaded shows as a form on screen: 'submit' / 'file it' -> confirm; 'the phone number is …' / 'my name is …' / "
                     "'the village is …' -> chat_text with those words. 'I want to upload a letter' / 'attach my written complaint' / "
                     "'upload' -> upload_document (it opens the upload box; the person then taps it).")'''),
])

# ------------------------------------------------------------------ tools: the function + the name
patch("mitra/server/tools.py", [
    ('''async def t_go_to(sess, args):''',
     '''async def t_upload_document(sess, args):
    """The document door by voice: the request card with its drop zone is raised and lit; the person taps it (a browser never
    opens the file picker without a tap). Nothing is filed by this call."""
    st = sess["state"]
    if st.get("flow") not in (None, "", "menu", "done") and (st.get("draft") or {}).get("doc"):
        return {"say": "Your letter is already on the form. Check it and say submit, or change anything.", "ui": [{"op": "upload", "lit": True}]}
    return {"say": "Tap Upload a written complaint and choose the letter, a PDF or a photo, or take a photo of it. I will read it into the "
                   "official form and send it to the right officer.",
            "ui": _draft_ui(sess, [stage(0, "Waiting for the letter · tap Upload a written complaint", "run")]) + [{"op": "upload"}]}


async def t_go_to(sess, args):'''),
    ('''    "switch_profile": t_switch_profile, "go_to": t_go_to,''',
     '''    "switch_profile": t_switch_profile, "go_to": t_go_to, "upload_document": t_upload_document,'''),
], subs=[
    ("Spoken request received by Sakala Mitra", "Spoken request received by Mitra"),
    ("Photo of the petition read by Sakala Mitra", "Photo of the petition read by Mitra"),
    ('via="Sakala Mitra (voice)"', 'via="Mitra (voice)"'),
    ('via="Sakala Mitra (voice note)"', 'via="Mitra (voice note)"'),
])
patch("mitra/server/main.py", [('app = FastAPI(title="Sakala Mitra", lifespan=lifespan)', 'app = FastAPI(title="Mitra", lifespan=lifespan)')], subs=[("Sakala Mitra:", "Mitra:")])
patch("mitra/server/config.py", [], subs=[('"""Sakala Mitra settings.', '"""Mitra settings.')])
patch("mitra/server/notify.py", [], subs=[('replace("Citizen (Sakala Mitra)", "The citizen")', 'replace("Citizen (Mitra)", "The citizen").replace("Citizen (Sakala Mitra)", "The citizen")')])
patch("mitra/server/guard.py", [
    ('''IDENTITY_SAY = ("I'm Mitra, the voice assistant of Sakala, Government of Karnataka.''',
     '''IDENTITY_SAY = ("I'm Mitra, the voice assistant for the Sakala and iPGRS services of the Government of Karnataka.'''),
])
patch("mitra/server/brain.py", [
    ('''f"You are {config.NAME}, the voice assistant of the Sakala AI system of the Government of Karnataka.",''',
     '''f"You are {config.NAME}, the voice assistant for the Sakala and iPGRS grievance services of the Government of Karnataka.",'''),
])

# ------------------------------------------------------------------ POC audit strings
patch("app/server/api.py", [], subs=[
    ('"mitra": "Sakala Mitra (voice)"', '"mitra": "Mitra (voice)"'),
    ('doc_note="filed by voice through Sakala Mitra"', 'doc_note="filed by voice through Mitra"'),
    ('"Citizen (Sakala Mitra)"', '"Citizen (Mitra)"'),
    ('"Sakala Mitra (voice)")', '"Mitra (voice)")'),
])

# ------------------------------------------------------------------ web: markup
patch("mitra/web/index.html", [
    ("<title>Sakala Mitra</title>", "<title>Mitra</title>"),
    ('<div class="brand-t"><b>Sakala <span class="grad">Mitra</span></b>', '<div class="brand-t"><b><span class="grad">Mitra</span></b>'),
    ('<span id="profSub">Sakala Mitra</span>', '<span id="profSub">Mitra</span>'),
    ('<span data-k="act"><i></i>Act on Sakala</span>', '<span data-k="act"><i></i>Act on iPGRS</span>'),
    ('<h1 id="spTitle">Sakala <span class="grad">Mitra</span></h1>', '<h1 id="spTitle"><span class="grad">Mitra</span></h1>'),
    ('''      <button class="stop" id="stop" title="Stop (Esc, or say “stop”)">''',
     '''      <button class="attach" id="attach" title="Upload a written complaint (PDF or photo)" aria-label="Upload a written complaint" hidden><svg viewBox="0 0 24 24"><path d="M21.4 11.6 12.3 20.7a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.1a2 2 0 0 1-2.8-2.8l8.5-8.5"/></svg></button>
      <button class="stop" id="stop" title="Stop (Esc, or say “stop”)">'''),
], subs=[("mitra.css?v=63", "mitra.css?v=64"), ("mitra.js?v=65", "mitra.js?v=66")])

# the splash title is one word now: the letter animation must not read the span as a leading text node
patch("mitra/web/splash.js", [
    ('''    h1.innerHTML = wrap({ textContent: h1.childNodes[0].textContent }) + (g ? `<span class="grad-l">${wrap({ textContent: word }, 'gl')}</span>` : '');''',
     '''    const lead = h1.childNodes[0] && h1.childNodes[0].nodeType === 3 ? h1.childNodes[0].textContent : '';
    h1.innerHTML = wrap({ textContent: lead }) + (g ? `<span class="grad-l">${wrap({ textContent: word }, 'gl')}</span>` : '');'''),
])

# ------------------------------------------------------------------ web: client
patch("mitra/web/mitra.js", [
    ("const STAGES = [['Entry', 'Sakala Mitra · you just say it'],", "const STAGES = [['Entry', 'Mitra · you just say it'],"),
    ("$('#statusText').textContent = !b.sakala ? 'Sakala offline' : b.brain === 'rules' ? 'Sakala AI · offline mode' : 'Sakala AI · online';",
     "$('#statusText').textContent = !b.sakala ? 'iPGRS offline' : b.brain === 'rules' ? 'Mitra · offline mode' : 'Mitra · online';"),
    ("const PROF = { citizen: ['👤', 'Citizen', 'Sakala Mitra · Karnataka'],", "const PROF = { citizen: ['👤', 'Citizen', 'Mitra · Karnataka'],"),
    ("<small>Sakala AI</small></h3>", "<small>Mitra</small></h3>"),
    ("<small>Sakala AI pipeline · live</small></h3>", "<small>Mitra pipeline · live</small></h3>"),
    (" · read by Sakala AI${doc.ms ?", " · read by Mitra${doc.ms ?"),
    # the attach button follows the profile (citizen only) and opens the picker; by voice the drop zone is raised and lit
    ('''  $('#hints').innerHTML = (HINTS[J.profile] || []).map(h => `<button>${esc(h)}</button>`).join('');''',
     '''  document.body.dataset.profile = J.profile; const at = $('#attach'); if (at) at.hidden = J.profile !== 'citizen';
  $('#hints').innerHTML = (HINTS[J.profile] || []).map(h => `<button>${esc(h)}</button>`).join('');'''),
    ('''  routed(op) { renderRouted(op); Orb.burst();''',
     '''  upload(op) {                       // "I want to upload a letter": the request card with its drop zone, lit; the person taps it
    if (J.profile !== 'citizen') return;
    if (!panels.left.get('request')) UI.request({ draft: {}, flow: 'menu', options: [] });
    const dz = $('#dropz'); if (!dz) return;
    dz.classList.remove('pulse'); void dz.offsetWidth; dz.classList.add('pulse');
    setTimeout(() => dz.scrollIntoView({ behavior: 'smooth', block: 'center' }), 350);
    try { dz.focus({ preventScroll: true }); } catch (e) { }
    setTimeout(() => dz.classList.remove('pulse'), 6000);
  },
  routed(op) { renderRouted(op); Orb.burst();'''),
    ('''function bindDrop() {
  const dz = $('#dropz'), inp = $('#reqFile'); if (!dz || !inp) return;''',
     '''function bindAttach() {
  const at = $('#attach'); if (!at || at.__b) return; at.__b = true;
  at.onclick = () => {
    if (J.profile !== 'citizen') return;
    if (!panels.left.get('request') || !$('#reqFile')) UI.request({ draft: {}, flow: 'menu', options: [] });
    const inp = $('#reqFile'), dz = $('#dropz');
    if (inp) inp.click();                                              // a real tap: the picker (camera on a phone) opens
    else if (dz) UI.upload({});
  };
}
function bindDrop() {
  bindAttach();
  const dz = $('#dropz'), inp = $('#reqFile'); if (!dz || !inp) return;'''),
], subs=[("/* Sakala Mitra client:", "/* Mitra client:")])

patch("mitra/web/phone.js", [], subs=[
    ('Sakala Mitra · App', 'Mitra · App'), ('title="Sakala Mitra app"', 'title="Mitra app"'),
    ('<small>Sakala Mitra</small>', '<small>Mitra</small>'), ('the real Sakala Mitra, on the same server', 'the real Mitra, on the same server'),
])
patch("mitra/web/portal.js", [], subs=[("'Sakala Mitra'", "'Mitra'")])
patch("mitra/web/app.js", [
    ("const AUTO = { case: 'right', request: 'left',", "const AUTO = { upload: 'left', case: 'right', request: 'left',"),
])

# ------------------------------------------------------------------ styles: the attach button, the lit drop zone, the phone
patch("mitra/web/mitra.css", [
    ('''.mic svg{width:24px;height:24px;fill:currentColor}''',
     '''.mic svg{width:24px;height:24px;fill:currentColor}
/* v64: the document door from the composer (citizen): a paperclip that opens the picker / camera */
.attach{width:46px;height:46px;border-radius:50%;display:grid;place-items:center;flex:none;background:rgba(22,199,132,.12);border:1px solid rgba(22,199,132,.45);color:var(--em);cursor:pointer;transition:transform .2s,box-shadow .3s,background .2s}
.attach svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.attach:hover,.attach:focus-visible{transform:translateY(-1px) scale(1.04);background:rgba(22,199,132,.22);box-shadow:0 8px 24px rgba(22,199,132,.25);outline:none}
.attach[hidden]{display:none}
.dropz.pulse{border-style:solid;border-color:var(--em);animation:dzPulse 1.1s ease-out 4}
@keyframes dzPulse{0%{box-shadow:0 0 0 0 rgba(22,199,132,.55)}100%{box-shadow:0 0 0 18px rgba(22,199,132,0)}}'''),
    ('''  .composer .stop{width:40px;height:40px}''',
     '''  .composer .stop{width:40px;height:40px}
  .composer .attach{width:44px;height:44px;order:0}'''),
], subs=[('"Sakala Mitra" in the header', '"Mitra" in the header')])

# ------------------------------------------------------------------ tests that assert the old strings
patch("mitra/tests/test_guardrails.py", [], subs=[('"via Sakala Mitra (voice)"', '"via Mitra (voice)"'), ("through Sakala Mitra", "through Mitra")])
patch("mitra/tests/ui_splash.py", [
    ('''check("after the intro: 'Sakala Mitra' letter by letter (gradient letters), greeting, Start visible", r["letters"] == 11 and r["gl"] == 5''',
     '''check("after the intro: 'Mitra' letter by letter (gradient letters), greeting, Start visible", r["letters"] == 5 and r["gl"] == 5'''),
])
print("done")
