import sys, shutil, os
p, js, css, bak = sys.argv[1:5]
shutil.copyfile(p, bak)
s = open(p, encoding='utf-8').read()

def rep(old, new, count=1):
    global s
    assert old in s, 'missing: ' + old[:80]
    s = s.replace(old, new, count)

# 1. CSS layer
rep('</style>', open(css, encoding='utf-8').read() + '\n</style>')

# 2. splash with two halos (emblem + Sakala mark)
MARK = '<svg class="mark" viewBox="0 0 64 64"><circle cx="32" cy="32" r="31" fill="#fff"/><circle cx="32" cy="32" r="24" fill="none" stroke="#26732f" stroke-width="4"/><path d="M32 14v18l11 7" stroke="#da6823" stroke-width="4.5" fill="none" stroke-linecap="round"/><circle cx="32" cy="32" r="3.5" fill="#14421a"/></svg>'
a = s.index('<div class="overlay" id="overlay">'); b = s.index('<header class="gov-header">')
s = s[:a] + f'''<div class="overlay" id="overlay">
  <div class="splash-logos"><span class="halo"><img src="assets/karnataka-emblem.png" alt=""></span><span class="halo">{MARK}</span></div>
  <div class="overlay-text"><b>ಸಕಾಲ · Sakala AI</b><small>Right officer · First time · On time</small></div>
</div>
<div class="go-overlay" id="goOverlay">
  <div class="splash-logos"><span class="halo"><img src="assets/karnataka-emblem.png" alt=""></span><span class="halo">{MARK}</span></div>
  <div class="overlay-text"><b>Sakala AI · Chief Secretary</b><small>Entering AI mode</small></div>
</div>

''' + s[b:]

# 3. header brand: emblem + Sakala mark in halos, live pill
a = s.index('<div class="gov-brand">'); b = s.index('<span class="brand-divider"></span>')
s = s[:a] + f'''<div class="gov-brand" id="govBrand">
      <span class="logos"><span class="logo-halo"><img src="assets/karnataka-emblem.png" alt="Emblem of Karnataka"></span><span class="logo-halo">{MARK.replace('class="mark" ', '')}</span></span>
      ''' + s[b:]
rep('<div class="clock" title=', '<span class="live-pill"><i></i>LIVE · MYSURU PILOT</span>\n    <div class="clock" title=')

# 4. citizen module replaces the old 9-channel form + pipeline
a = s.index('/* ================= CITIZEN ================= */'); b = s.index('function renderTrack(){')
s = s[:a] + open(js, encoding='utf-8').read() + '\n' + s[b:]

# 5. WhatsApp as a source
rep("const SOURCES = [\n", "const SOURCES = [\n  {k:'whatsapp', n:'WhatsApp · Sakala AI', kn:'ವಾಟ್ಸಾಪ್', g:'Self-service', d:'Citizen chats with Sakala AI on WhatsApp', share:'new'},\n")
rep("  map:'<path d=\"M9 3L3 6v15l6-3 6 3 6-3V3l-6 3z\"/>", "  whatsapp:'<path d=\"M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2z\"/>',\n  map:'<path d=\"M9 3L3 6v15l6-3 6 3 6-3V3l-6 3z\"/>")
rep("'ಬೈಲಕುಪ್ಪೆ':'Bylakuppe'}", "'ಬೈಲಕುಪ್ಪೆ':'Bylakuppe','ಬಿಳಿಕೆರೆ':'Bilikere','ಜಯಪುರ':'Jayapura'}")

# 6. app bar text + wide content for the WhatsApp stage
rep("citizen:'<b>Citizen</b> · file a request from any of the 9 channels and see exactly which officer it reached'",
    "citizen:'<b>Citizen</b> · Sakala AI on WhatsApp · no app to install · every channel feeds the same AI pipeline'")
rep("  if (S.profile==='citizen') renderCitizen();", "  $('#content').className = 'content' + (S.profile==='citizen' && S.citizenView!=='track' ? ' wa-mode' : '');\n  if (S.profile==='citizen') renderCitizen();")
rep("s:'File & track requests · 9 channels'", "s:'Sakala on WhatsApp · my requests'")

# 7. CS: AI-mode launch card + 'Entering AI mode' transition
rep('''    <button data-cs="ai" class="${S.csView==='ai'?'on':''}"><span class="ic">${svg('star')}</span><span>AI mode<small>Ask anything, get the facts</small></span><span class="cnt">AI</span></button>\n''', '')
rep('''$('#sidebar').innerHTML = `<div><div class="side-h">Master access</div><div class="nav">''',
    '''$('#sidebar').innerHTML = `<button class="dash-link ${S.csView==='ai'?'on':''}" data-cs="ai"><span class="dash-ico"><i></i><i></i><i></i><i></i></span><span class="dash-txt"><b>AI mode</b><small>Ask anything · answers from live data</small></span><span class="dash-go"><svg viewBox="0 0 24 24"><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></svg></span></button>
  <div><div class="side-h">Master access</div><div class="nav">''')
rep("document.querySelectorAll('[data-cs]').forEach(b=>b.onclick=()=>{S.csView=b.dataset.cs;render()});",
    "document.querySelectorAll('[data-cs]').forEach(b=>b.onclick=()=>{ if(b.dataset.cs==='ai' && S.csView!=='ai') return goAI(); S.csView=b.dataset.cs;render()});")
rep("$('#toAI').onclick=()=>{S.csView='ai';render()};", "$('#toAI').onclick=goAI;")
rep("$('#aiBadge').onclick=()=>{ S.profile='cs'; S.csView='ai'; render(); };",
    "function goAI(){ const o=$('#goOverlay'); $('#govBrand').classList.add('thinking'); o.classList.add('on'); setTimeout(()=>{ S.profile='cs'; S.csView='ai'; profMenuOpen=false; closeDrawer(); render(); },420); setTimeout(()=>{ o.classList.remove('on'); $('#govBrand').classList.remove('thinking'); },1250); }\n$('#aiBadge').onclick=goAI;")

# 8. test hooks: ?wa=N sends WhatsApp sample N, ?wa=voice / photo / apply
old_hook = s[s.index("{ const q=new URLSearchParams(location.search); if(q.get('auto'))"):s.index('</script>')]
s = s.replace(old_hook, """{ const q=new URLSearchParams(location.search); const w=q.get('wa');
  if(w){ setTimeout(()=>{ WA.lang='en'; if(w==='voice') $('#waSend').click(); else if(w==='photo') $('#waAttach').click(); else if(w==='apply') applyStart(SERVICES[0]); else if(w==='track') waTrack(); else handleFree(WA_SAMPLES[+w-1][1]); }, 1400); }
  if(q.get('open')) setTimeout(()=>openCase(q.get('open')),300); if(q.get('tick')) setTimeout(()=>tick(+q.get('tick')),200); }
""")
open(p, 'w', encoding='utf-8').write(s)
print('patched OK', len(s))
