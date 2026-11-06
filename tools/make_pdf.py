import pymupdf, sys

BOTH = ("Both", "#1f7a4d", "#e3f4ea")
CS = ("Chief Secretary", "#1d4f91", "#e2ebf7")
OURS = ("Ours", "#a35a00", "#fdf0dc")
PROD = ("Production phase", "#555555", "#ececec")
REAL, SYN, UI = "Real data", "Synthetic data", "Front-end only"

sections = [
 ("A", "Intake: getting a complete, clean request in", [
  (1, "AI application-completion agent", "Voice or text, Kannada/English. Keeps asking for missing details and documents until the application is complete, then confirms with the citizen. 3 services: caste/income certificate, old-age pension, ration card.", CS, SYN),
  (2, "Photo / scanned application intake", "Upload a form or handwritten petition; AI reads it, extracts the fields and loads them into the database. Unreadable parts flagged for a human.", BOTH, SYN),
  (3, "Data validation &amp; standardisation", "Live checks at intake (mobile, Aadhaar format, pin code to district, village in master, documents, duplicates) plus a data-quality report on the 9,999 historical rows.", BOTH, REAL),
  (4, "Privacy shield", "Phone, Aadhaar and ration-card numbers masked before the AI or the screen sees them. Sakala RD/GSC numbers extracted first.", OURS, REAL),
  (5, "Wrong-door detector", "Flags non-grievances (RTI, court/sub-judice, suggestions, employee service matters) and says where they should go.", OURS, REAL),
 ]),
 ("B", "Routing: right department, exact officer", [
  (6, "AI understanding", "Complaint/request &#8594; Department &#8594; Line Department &#8594; Service &#8594; Grievance type + Sakala tag. Confidence, top-3 alternatives, reason in Kannada &amp; English. Picks only from the official master.", OURS, REAL),
  (7, "Exact-officer routing to village / GP", "Location &#8594; named first-level officer (LMF / Designated Officer) &#8594; L2 &#8594; L3, with a map pin. Jurisdiction master; taluk fallback flagged amber.", OURS, REAL),
  (8, "Misrouting detector + human scrutiny desk", "Flags wrong historical labels (KRIDL 'General' desk, 'General' rows). Low-confidence cases go to a person with the top-3 options.", OURS, REAL),
  (9, "Vulnerability fast-lane", "Elderly, widow, disabled, pension and ration cases prioritised.", OURS, REAL),
  (10, "Accuracy proof", "Held-out test: department, exact-officer and end-to-end accuracy.", OURS, REAL),
 ]),
 ("C", "After routing: officer action &amp; accountability", [
  (11, "Automatic three-level escalation", "Sakala applications: legal deadlines (clock starts when complete, holidays excluded), Designated &#8594; Competent &#8594; Appellate officer. Grievances: configurable deadlines, LMF &#8594; L2 &#8594; L3. Live 'move time forward' simulation. Synthetic applications calibrated to each district's real 2025 late, rejection and overdue rates.", BOTH, SYN),
  (12, "Officer reminder board, notices &amp; audit trail", "Each officer's open cases with days open, days left, green/amber/red. Daily digest, pre-escalation warning, notice to senior. AI-drafted Form C / E-4 notices. Full audit log.", BOTH, SYN),
  (13, "HRMS salary-linked accountability", "Delay &#8594; Rs 20/day (max Rs 500) &#8594; notice &#8594; 7-day reply &#8594; Competent Officer approval &#8594; debit note posted to a mock HRMS. A human always approves.", BOTH, SYN),
  (14, "Grievance &#8594; Sakala bridge", "Complaints quoting an RD/GSC number linked to the application; AI decides whether Sakala rights apply (delayed certificate vs pension payment issue).", OURS, SYN),
  (15, "ATR Quality Auditor", "Complaint + synthetic Action Taken Report (PDF) &#8594; summary, issue-by-issue comparison, 1-5 rating or 'insufficient evidence', re-open flag; officer copilot drafts a better reply.", OURS, SYN),
 ]),
 ("D", "Leadership &amp; intelligence", [
  (16, "Leadership dashboard", "Total pending, ageing buckets, department and district status, cases at each escalation level, overdue officers, offices with 7+ defaults. Sakala side uses the real 2025 district performance reports (see #21).", BOTH, REAL),
  (17, "Praja Seva historical intelligence", "Camp patterns, top issues by taluk, scrutiny bottleneck, vulnerable citizens waiting, repeat complainants (masked), AI-written summary.", BOTH, REAL),
  (18, "Wednesday Review Pack", "One-pagers for Tahsildar/EO &#8594; AC &#8594; DC &#8594; Chief Secretary in Kannada &amp; English, matching the government's Wednesday review rhythm. Includes the district's Sakala performance and month-on-month change.", OURS, REAL),
  (19, "Hotspot clusters &amp; root cause", "Repeated or similar complaints grouped by place, with an AI-inferred fix.", OURS, REAL),
  (20, "Ask the data", "Plain-language question &#8594; chart and one-line answer, across both grievances and Sakala performance data.", OURS, REAL),
  (21, "Sakala District Performance Tracker (NEW)", "Real 2025 monthly reports for 31 districts (35.2M applications): receipts, in-time %, late %, rejection %, overdue, rank on a Karnataka map, month by month. Highlights e.g. Bengaluru Urban holding a third of state overdue, rejection rate rising from ~6% to ~8.5%, overdue down 63% (51,172 &#8594; 19,129).", BOTH, REAL),
  (22, "Early warning &amp; improved district scorecard (NEW)", "Flags districts whose rejection or overdue is rising before they slip. Shows that today's ranking barely separates districts (scores 61-79, driven almost only by in-time %) and proposes a fairer AI-assisted score.", OURS, REAL),
 ]),
 ("E", "Integration", [
  (23, "Connect departments at every digital level", "API connector (mocked), Excel/CSV upload (real, demonstrated with the Sakala monthly performance reports), paper scan (real, via #2), officer web console for departments with no system.", BOTH, REAL),
 ]),
 ("F", "Production-phase screens (shown in the UI, labelled)", [
  (24, "AI callback to citizen", "Kannada voice call after closure: 'Was your problem solved?'", PROD, UI),
  (25, "Namma Seva 5-star rating", "Citizen rates the service; a low rating means the officer must explain.", PROD, UI),
  (26, "Live integrations", "iPGRS, Sakala, Seva Sindhu, real HRMS, CPGRAMS.", PROD, UI),
  (27, "SMS / WhatsApp / email sending", "Reminders and notices actually sent.", PROD, UI),
  (28, "Learning loop &amp; sovereign model", "Officer corrections retrain a government-hosted Kannada model.", PROD, UI),
  (29, "Citizens-as-sensors alerts", "A spike in a topic and taluk raises an early warning to the DC.", PROD, UI),
 ]),
]

def tag(t):
    name, fg, bg = t
    return f'<span style="color:{fg};background-color:{bg};font-weight:bold;font-size:7.5pt;">&#160;{name}&#160;</span>'

css = """
@font-face {font-family: seg; src: url(segoeui.ttf);}
@font-face {font-family: seg; src: url(segoeuib.ttf); font-weight: bold;}
body {font-family: seg; font-size: 8.8pt; color: #1e2430;}
h1 {font-size: 21pt; color: #12305c; margin: 0;}
.sub {font-size: 10pt; color: #5b6575; margin-top: 2pt;}
.bar {background-color: #12305c; height: 3pt; margin: 8pt 0 10pt 0;}
h2 {font-size: 11pt; color: #ffffff; background-color: #12305c; padding: 4pt 7pt; margin: 12pt 0 4pt 0;}
table {width: 100%; border-collapse: collapse;}
td {padding: 4pt 5pt; vertical-align: top; border-bottom: 0.6pt solid #d9dee6;}
th {font-size: 7.5pt; color: #5b6575; text-align: left; padding: 3pt 5pt; border-bottom: 1pt solid #12305c;}
.num {color: #12305c; font-weight: bold; width: 16pt;}
.name {font-weight: bold; width: 120pt;}
.desc {color: #333b48;}
.data {font-size: 7.8pt; color: #5b6575; width: 58pt;}
.src {width: 80pt;}
.note {font-size: 8.3pt; color: #5b6575;}
.box {background-color: #f3f6fa; padding: 6pt 8pt; margin-top: 6pt;}
"""

rows_html = ""
for letter, title, items in sections:
    brk = ' style="page-break-before:always;"' if letter in ('C',) else ''
    rows_html += f'<h2{brk}>{letter}.&#160;&#160;{title}</h2><table><tr><th>#</th><th>Use case</th><th>What it does</th><th>Source</th><th>Data</th></tr>'
    for n, name, desc, src, data in items:
        rows_html += f'<tr><td class="num">{n}</td><td class="name">{name}</td><td class="desc">{desc}</td><td class="src">{tag(src)}</td><td class="data">{data}</td></tr>'
    rows_html += "</table>"

counts = {"Both": 0, "Chief Secretary": 0, "Ours": 0, "Production phase": 0}
for _, _, items in sections:
    for it in items:
        counts[it[3][0]] += 1

html = f"""
<h1>Sakala AI: Proof of Concept</h1>
<div class="sub">Final use-case list &#183; Government of Karnataka &#183; 13 October 2026</div>
<div class="bar"></div>
<div class="box"><b>Core goal.</b> A citizen files one request or complaint, from any source and in Kannada or English. It is completed, validated and routed straight to the correct department and the <b>exact field officer for that village / GP</b>. The system then makes sure that officer acts, escalating automatically, with full accountability and a leadership view.</div>
<p class="note" style="margin-top:8pt;"><b>Source key:</b>&#160; {tag(BOTH)} asked by the Chief Secretary and already in our plan &#160; {tag(CS)} new from the Chief Secretary meeting &#160; {tag(OURS)} from our analysis, the scope document and the client use-case PDF &#160; {tag(PROD)} shown in the UI only</p>
{rows_html}
<div class="box" style="margin-top:12pt;">
<b>Summary.</b> {counts['Both']} items wanted by both the Chief Secretary and us &#183; {counts['Chief Secretary']} new from the Chief Secretary &#183; {counts['Ours']} from our analysis &#183; {counts['Production phase']} production-phase screens.<br/>
<b>Skipped for this POC:</b> WhatsApp voice entry (CS-1) and the Meghalaya reference (CS-11).<br/>
<b>Real data used:</b> 9,999 iPGRS / Praja Seva grievances (3-9 Oct 2026, masked) and Sakala monthly district performance reports, Jan-Dec 2025 (31 districts + BBMP row).<br/>
<b>Open data issues to raise with Sakala:</b> the "RDPR" and "Revenue" report files are identical to the combined all-department file in all 12 months, so we need the real department-wise exports; the BBMP row uses Bengaluru Urban's population, so its per-lakh figures are invalid; district names still use Ramanagara.<br/>
<b>Data honesty:</b> every synthetic record and screen carries a visible "Synthetic data" badge; every front-end-only feature carries a "Production phase" badge.<br/>
<b>Guardrails:</b> AI picks only from official masters; every decision shows its reason; low confidence goes to a human; personal data masked before AI; Sakala compensation applies only to Sakala applications; the grievance ladder (LMF &#8594; L2 &#8594; L3) is never mixed with the Sakala appeal ladder (Designated &#8594; Competent &#8594; Appellate); salary action always needs human approval.
</div>
"""

arch = pymupdf.Archive("C:/Windows/Fonts")
story = pymupdf.Story(html=html, user_css=css, archive=arch)
out = sys.argv[1]
writer = pymupdf.DocumentWriter(out)
mediabox = pymupdf.paper_rect("a4")
where = mediabox + (36, 40, -36, -46)
more = True
while more:
    dev = writer.begin_page(mediabox)
    more, _ = story.place(where)
    story.draw(dev)
    writer.end_page()
writer.close()

doc = pymupdf.open(out)
n = len(doc)
for i, p in enumerate(doc):
    p.insert_text((36, mediabox.height - 22), "Sakala AI POC: Final use-case list", fontsize=7.5, color=(0.45, 0.5, 0.58))
    p.insert_text((mediabox.width - 82, mediabox.height - 22), f"Page {i+1} of {n}", fontsize=7.5, color=(0.45, 0.5, 0.58))
doc.saveIncr()
print("pages:", n)
for i, p in enumerate(doc):
    p.get_pixmap(dpi=80).save(out.replace(".pdf", f"_p{i+1}.png"))
