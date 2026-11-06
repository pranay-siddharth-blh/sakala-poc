"""Bring the architecture diagram (tools/arch.html → Sakala_AI_POC_Architecture.png/.pdf) up to the built POC."""
P = r"D:\Sakala POC\tools\arch.html"
s = open(P, encoding="utf-8").read()


def rep(old, new):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, 1)


rep("Proof-of-concept architecture: understand every citizen request, route it to the exact field officer of the right department, and make sure it is acted upon, with full accountability and a leadership view.",
    "Built and running (14 Oct 2026): a citizen writes, speaks or sends a photo on WhatsApp; Sakala AI understands it, routes it to the exact field officer of the right department down to the Gram Panchayat, keeps the officer on the clock, and gives the Chief Secretary a live view with charts and a Karnataka map.")
rep("Praja Seva Department · Sakala Mission<br>POC · 14 October 2026", "Praja Seva Department · Sakala Mission<br>Live POC · Mysuru pilot · 14 October 2026")
rep("<div class=\"flowtitle\">How it works · 8 stages, one pipeline for every channel</div>", "<div class=\"flowtitle\">How it works · 8 stages, one pipeline for every channel (as built)</div>")
# stage 1
rep('''        <li>Voice or text chat in <b>Kannada / English</b></li>
        <li>Photo or scan of a paper form / petition</li>
        <li>App-style form: District → Taluk → GP</li>
        <li>Excel/CSV upload &amp; officer console for low-digital departments</li>''',
    '''        <li><b>WhatsApp</b> (no app to install): text, voice note, photo of a petition, live location, in Kannada / English</li>
        <li>Two-way: officer questions, decisions and resolutions arrive back in the same chat; the citizen replies, confirms 👍/👎 or appeals</li>
        <li>Same pipeline for the 1902 call centre, Praja Seva camps, Grama One / CSC counters and the app</li>
        <li>Excel / CSV upload for departments with spreadsheets; officer web console</li>''')
# stage 2
rep('''        <li>Speech-to-text (Kannada / English)</li>
        <li>AI reads scanned &amp; handwritten forms into fields</li>
        <li>Language detection + English summary</li>
        <li><b>Masks</b> phone, Aadhaar, ration-card numbers</li>
        <li>Pulls out Sakala RD / GSC numbers</li>''',
    '''        <li>Speech-to-text (Kannada / English) on the government's own model gateway</li>
        <li>Vision model reads the petition photo; unreadable or unrelated images are refused, never guessed</li>
        <li>Language detection + one-line English summary</li>
        <li><b>Masks</b> phone, Aadhaar, email and card numbers before any AI step</li>
        <li>Pulls out Sakala GSC numbers and links them to the application</li>''')
# stage 3
rep('''        <li>Checks: mobile, Aadhaar format, pin ↔ district, village exists, duplicates</li>
        <li>Per-service checklist of required details &amp; documents</li>
        <li>Wrong-door check: RTI, court cases, suggestions</li>''',
    '''        <li>Village / GP resolved from the message (Kannada names transliterated), GPS, or a pick-list; taluk-level services skip the village question</li>
        <li>Duplicate check: same service, same GP → linked, not re-filed</li>
        <li>Per-service checklist for Sakala applications (name, village, document photo)</li>
        <li>Wrong-door check: RTI, other departments → told where to go</li>''')
# stage 4
rep('''        <li>Finds similar past cases + official categories</li>
        <li>Claude picks <b>Department → Line Dept → Service → Grievance</b> from the master only</li>
        <li>Sakala / Non-Sakala tag</li>
        <li>Confidence, top-3 options, reason in Kannada + English</li>
        <li>Vulnerability flag: elderly, widow, disabled, pension</li>''',
    '''        <li>Finds the 5 most similar real grievances (9,999 from 3–9 Oct 2026)</li>
        <li>The AI model picks <b>Department → Line Dept → Service → Grievance</b> from the official master only (enum-constrained)</li>
        <li>A second, offline model trained on the real data must agree; keyword rules override for RTI / other departments / new applications</li>
        <li>Confidence below a threshold tuned from measured accuracy → scrutiny desk with the top-3 options</li>
        <li>Vulnerability flag: elderly, widow, disabled, pension, ration</li>''')
# stage 5
rep('''        <li>Jurisdiction master: <b>District → Taluk → Village / GP</b></li>
        <li>Names the field officer (LMF / Designated Officer), e.g. PDO of that GP, Tahsildar of that taluk</li>
        <li>Escalation chain above: L2 → L3</li>
        <li>Rural vs town; electricity company by district</li>''',
    '''        <li>Service → officer role learned from the real assignments (Khata → Tahsildar 100%, water → AE RDWS 100%, street light → PDO 97%)</li>
        <li>Role + taluk + GP → one named officer: PDO of that GP, Tahsildar / ADLR / Food Inspector / AEE of that taluk</li>
        <li><b>97.6%</b> agreement with the real iPGRS officer on 673 Mysuru cases; 92.5% end to end from text alone</li>
        <li>Every decision stores its evidence: confidence, threshold, rules, similar cases, location source, officer rule</li>''')
rep("⚑ Unsure, or village unknown? → Human scrutiny desk with top-3 options. Never a silent guess.",
    "⚑ Unsure, outside the master, or village unknown? → Scrutiny desk (L2/L3) decides and re-routes; the citizen is told. Never a silent guess.")
# stage 6
rep('''        <li>Sakala legal clock (holidays excluded) + grievance deadlines</li>
        <li><b>Automatic 3-level escalation</b> when time runs out</li>
        <li>Officer board: open cases, days left, reminders, notices, audit trail</li>
        <li>₹20/day (max ₹500) → notice → approval → <b>HRMS debit</b></li>
        <li>Does Sakala apply to this complaint?</li>''',
    '''        <li>Grievance deadlines per level (7 / 5 / 3 days, assumed) + the Sakala legal clock for applications</li>
        <li>Due-tomorrow reminders, then <b>automatic 3-level escalation</b>; the citizen is told each time</li>
        <li>Officer inbox: open cases, days left, vulnerable first, accept / ask info / return / reject (reason mandatory) / resolve</li>
        <li>₹20/day (max ₹500) ordered by the Competent Officer → Form C notice → <b>HRMS debit</b> (mock)</li>
        <li>Officer messages translated to Kannada for Kannada chats</li>''')
# stage 7
rep('''        <li>Reads complaint + officer's Action Taken Report (PDF)</li>
        <li>Issue-by-issue comparison with evidence</li>
        <li>Rating: 5 Fully … 1 Irrelevant, or "insufficient evidence"</li>
        <li>Copilot drafts a better reply for the officer</li>''',
    '''        <li>AI compares the complaint with the officer's Action Taken Report</li>
        <li>Score 5 Fully resolved … 1 Irrelevant; below 4 the case stays open and is flagged</li>
        <li>AI drafts a first ATR the officer edits</li>
        <li>Citizen asked on WhatsApp "was it solved?" · 👎 re-opens the case and informs the senior</li>''')
rep("↺ Not resolved? → case re-opens and goes back to stage 6.", "↺ Not resolved, or the citizen says no? → re-opened, back to stage 6 with the senior officer informed.")
# stage 8
rep('''        <li>Dashboard: pending, ageing, department, district, cases at each level</li>
        <li><b>Sakala district tracker</b>: real 2025 receipts, in-time %, late %, rejection %, overdue, rank</li>
        <li>Praja Seva insights: camps, top issues, repeat complainants</li>
        <li>Wednesday Review Pack: Tahsildar → AC → DC → CS</li>
        <li>Hotspots, ask the data</li>''',
    '''        <li>Command dashboard with a live <b>Karnataka map</b>: districts shaded by real 2025 late delivery; zoom to taluk; on-time / overdue / vulnerable filters</li>
        <li><b>Sakala district tracker</b>: real 2025 reports, early warning for slipping districts, fairer scorecard</li>
        <li>Insights: hotspots with AI-suggested fixes, Praja Seva history, misrouting detector, data quality</li>
        <li>Wednesday Review Pack (EN + ಕನ್ನಡ) for Tahsildar/EO → AC → DC → CS; Form E-4 list</li>
        <li><b>AI mode</b>: ask anything, answered only from data tools, with bar / line / donut charts</li>''')
rep("⚠ Early warning: districts with rising rejections or overdue flagged before they slip; fairer district scorecard.",
    "⚠ Accuracy proof screen: live test on real complaints (dept 97.5% · service 95% · officer 92.5% on 40 cases).")
# panel A example: update to a WhatsApp example that the demo actually runs
rep('''<div class="ph">A · One real complaint, end to end (case 503060 from the sample)</div>''', '''<div class="ph">A · One complaint, end to end (as the demo runs it)</div>''')
rep('''          <div class="kn">"ಸಬ್ಬನಹಳ್ಳಿ ಗ್ರಾಮ ಸರ್ವೇ ನಂಬರ್ 53 … ಪೌತಿ ಖಾತಾ ಮಾಡಲು ವಿಳಂಬ"</div>
          <div class="en">"Sabbanahalli village, survey no. 53: delay in transferring the land khata after the owner's death."</div>
          <div class="meta">Source: Mobile App · Mysuru › Hunsur › Halebeedu GP</div>
          <div class="bad">Today: "Registered &amp; Sent for Scrutiny"; waiting for a person to check the category.</div>''',
    '''          <div class="kn">"ನಮ್ಮ ಗೊರಹಳ್ಳಿ ಗ್ರಾಮದಲ್ಲಿ ಕಳೆದ ಒಂದು ವಾರದಿಂದ ಕುಡಿಯುವ ನೀರು ಬರುತ್ತಿಲ್ಲ"</div>
          <div class="en">"No drinking water in our Gorahalli village for the last one week."</div>
          <div class="meta">Source: WhatsApp (text) · village read from the Kannada message → Chapparadahalli GP, Piriyapatna</div>
          <div class="bad">Today: 6 dropdowns picked by an operator; 39% of app complaints wait in manual scrutiny.</div>''')
rep('''          <div class="rrow"><span>Department</span><span>Revenue</span></div>
          <div class="rrow"><span>Line Dept</span><span>Revenue (Land-related issues)</span></div>
          <div class="rrow"><span>Service</span><span>Khata</span></div>
          <div class="rrow"><span>Grievance</span><span>Delay in processing application</span></div>
          <div class="rrow"><span>Type</span><span>Non-Sakala grievance</span></div>
          <div class="rrow"><span>Location</span><span>Mysuru › Hunsur › Halebeedu</span></div>
          <div class="rrow hl"><span>Officer (LMF)</span><span>Tahsildar Grade-1, Hunsur</span></div>
          <div class="rrow"><span>Escalates to</span><span>AC Hunsur → DC Mysuru*</span></div>
          <div class="ok">With AI: routed in seconds, with confidence + reason.</div>''',
    '''          <div class="rrow"><span>Department</span><span>RDPR</span></div>
          <div class="rrow"><span>Line Dept</span><span>Rural Drinking Water &amp; Sanitation</span></div>
          <div class="rrow"><span>Service</span><span>Provision of Drinking Water</span></div>
          <div class="rrow"><span>Confidence</span><span>95% · offline model agrees · 4 of 5 similar real cases</span></div>
          <div class="rrow"><span>Location</span><span>Gorahalli → Chapparadahalli GP → Piriyapatna</span></div>
          <div class="rrow hl"><span>Officer (L1)</span><span>AE/JE Rural Drinking Water, Piriyapatna (100% of 229 real cases)</span></div>
          <div class="rrow"><span>Escalates to</span><span>EO TP Piriyapatna → ZP CEO Mysuru</span></div>
          <div class="ok">Routed in about 3 s; the citizen gets the officer's name and deadline on WhatsApp.</div>''')
rep("*Escalation officers illustrative; to be confirmed from the official jurisdiction master.", "Grievance timelines (7 / 5 / 3 days) and Sakala service timelines are assumed until confirmed by the department.")
# panel C
rep('''<span class="chip">Sakala service timelines</span><span class="chip">Holiday calendar</span><span class="chip">LGD location codes</span>''',
    '''<span class="chip">Sakala service timelines (assumed)</span><span class="chip mock">Holiday calendar</span><span class="chip mock">Full LGD village master</span>''')
rep('''<span class="chip syn">Synthetic Sakala applications</span><span class="chip syn">Synthetic ATR PDFs</span>''', '''<span class="chip real">701 real Mysuru cases with their real officers</span><span class="chip syn">2 Sakala applications + 10 grievances for the demo</span>''')
rep("Stack: Python · database · Claude (AI) · Kannada speech-to-text · web app with map.",
    "Stack: Python (FastAPI) · SQLite · government model gateway (text + vision model, Kannada speech-to-text) inside the network · offline fallback model trained on the real data · single-page web app with Chart.js and a KGIS/OSM map.")
# panel D guardrails: the ones implemented
rep('''        <li>AI chooses <b>only from official masters</b></li>
        <li>Every decision shows its <b>reason</b> and is logged</li>
        <li>Low confidence → <b>a human decides</b></li>
        <li>Personal data masked before AI sees it</li>
        <li>Salary action needs <b>human approval</b> and a hearing</li>
        <li>Synthetic data clearly badged on screen</li>''',
    '''        <li>AI chooses <b>only from official masters</b>; anything else goes to a person</li>
        <li>Auto-route threshold <b>tuned from measured accuracy</b>; below it a human decides with top-3 options</li>
        <li>Every routing decision keeps its <b>evidence</b> (confidence, rules, similar cases, officer rule) for audit</li>
        <li>AI mode answers <b>only from data tools</b>; instruction-override and off-data prompts are refused and logged</li>
        <li>Unreadable photos / silent audio are refused, never guessed; every AI call is logged for weekly review</li>
        <li>A chat sees only its own cases; only the owner acts, only the Competent Officer compensates; ladders never mix</li>
        <li>Rejection needs a reason and the citizen is told the appeal officer (reply APPEAL); 👎 re-opens</li>
        <li>Per-client rate limits and size caps, as in the sister POCs; all rendered text sanitised</li>''')
open(P, "w", encoding="utf-8").write(s)
print("arch updated")
