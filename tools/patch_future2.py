"""Apple / OpenAI-grade restyle of the wireframe + remove the ticker and trim the profile bar."""
import sys
p, css = sys.argv[1:3]
s = open(p, encoding='utf-8').read()
def rep(old, new):
    global s
    assert old in s, 'missing: ' + old[:80]
    s = s.replace(old, new, 1)
if '/* ===================== FUTURE 2' not in s:
    rep('</style>', open(css, encoding='utf-8').read() + '\n</style>')
rep("citizen:'<b>Citizen</b> · Sakala AI on WhatsApp · no app to install · every channel feeds the same AI pipeline'", "citizen:'<b>Citizen</b> · Sakala AI on WhatsApp'")
rep("officer:`<b>Officer</b> · logged in as ${esc(OFF[S.officer].n)} (${OFF[S.officer].lv})`", "officer:`<b>Officer</b> · ${esc(OFF[S.officer].n)}`")
rep("cs:'<b>Chief Secretary</b> · master view of all 3 pilot departments · Mysuru district'", "cs:'<b>Chief Secretary</b> · Mysuru pilot'")
rep('<div class="eyebrow">Citizen · no app to install</div>\n        ', '')
open(p, 'w', encoding='utf-8').write(s)
print('future2 applied')
