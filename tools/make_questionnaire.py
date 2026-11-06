"""Builds the test questionnaire (English + Kannada) for manual testing of Mitra from the automated banks
(mitra/tests/cs_bank.py, mitra/tests/kn_bank.py), with the expected answer of each question computed from the database NOW.
Writes Mitra_Test_Questionnaire.md and .pdf in the project folder.
Run from the project root: PYTHONIOENCODING=utf-8 python tools/make_questionnaire.py"""
import asyncio
import base64
import html
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mitra" / "tests"))
import cs_bank as C  # noqa: E402
import kn_bank as K  # noqa: E402

# what each group checks, in plain words, and what should appear on screen
DESC = {
    "level": ("Open cases sitting with that level of officer", "KPI tiles + bars by level"),
    "level-overdue": ("Overdue cases still with L1 field officers", "KPI tiles + bars by level"),
    "level-split": ("Open cases split across L1, L2 and L3", "Bars: L1 / L2 / L3"),
    "escalated": ("Cases escalated up the ladder (auto, re-opened or appealed)", "KPI tiles + breakdown"),
    "not-escalated": ("Open cases never escalated", "KPI tiles + breakdown"),
    "escalation-split": ("Escalated vs not escalated, open cases", "Donut: escalated / not"),
    "days": ("Open cases with exactly that many days left on the clock", "KPI tiles + the 7-day clock"),
    "due-today": ("Open cases due today", "KPI tiles + the 7-day clock"),
    "due-tomorrow": ("Open cases due tomorrow (1 day left)", "KPI tiles + the 7-day clock"),
    "timeline": ("The 7-day clock: overdue, due today, 1..7 days, 8+ (the number shown is '3 days left')", "Bars: the 7-day clock"),
    "pending": ("Open cases in that taluk / district", "KPI tiles + breakdown by service / taluk"),
    "alias": ("Old place name (Mysore, Bangalore) understood", "KPI tiles + breakdown"),
    "dash": ("'How is X doing' = the full dashboard (number shown = open cases; for departments outside the pilot = all grievances in the iPGRS sample week)", "Board of 6 cards + scope chip"),
    "count": ("Open cases / grievances of a department", "KPI tiles + breakdown"),
    "compare": ("Side-by-side comparison (number shown = Piriyapatna open)", "Bars"),
    "ranking": ("Which district has the most open cases", "Ranked bars / map"),
    "edge": ("Nonsense or out-of-range question: must not crash or invent a number", "A polite answer, no made-up figure"),
    "knowledge": ("General question answered from Mitra's notes", "Answer card"),
}


def describe(group: str):
    for k in sorted(DESC, key=len, reverse=True):
        if group.startswith(k):
            return DESC[k]
    return ("", "")


def expected(chk: dict) -> str:
    if "num" in chk:
        return f"{chk['num']:,}"
    if chk.get("knowledge"):
        return "fact from the notes"
    return "—"


def rows(bank):
    out, n = [], 0
    for g, q, chk in bank:
        n += 1
        what, screen = describe(g)
        if chk.get("board"):
            screen = "Board of 6 cards + scope chip"
        out.append((n, g, q, what, expected(chk), screen))
    return out


EN_EXTRA = [  # citizen, officer and general checks that are not in the data bank
    ("Citizen", "There is no drinking water in Gorahalli for a week", "Understood as drinking water (RDPR) · place Gorahalli → Chapparadahalli GP · officer preview · asks to confirm", "Request card + 8-stage rail"),
    ("Citizen", "yes, file it", "Registered with a GR number, assigned to the AE RDWS Piriyapatna, 7 days", "Routed card"),
    ("Citizen", "I want to upload a letter", "Opens / lights the upload box and asks you to tap it", "Drop zone lit (paperclip on phone)"),
    ("Citizen", "What is Sakala?", "Sakala Act 2011, in force 2 April 2012, 1,446 services, compensation", "Answer card"),
    ("Citizen", "Who is the Chief Secretary?", "Shalini Rajneesh", "Answer card"),
    ("Citizen", "What is the capital of France?", "Not in my notes, no guess (no 'Paris')", "—"),
    ("Officer", "Read my inbox", "The officer's open cases, most urgent first", "Inbox card"),
    ("Officer", "Open the first case", "The case card with history and deadline", "Case card"),
    ("CS", "Give me the position", "Statewide briefing: open, overdue, vulnerable, escalated", "Charts + command board"),
    ("CS", "Show it on the Karnataka map", "The same numbers redrawn on the map", "Karnataka map"),
    ("CS", "Nudge the Tahsildar of Piriyapatna", "Asks 'Shall I go ahead?' first; after 'yes' the reminder is sent and logged", "Read-back bar"),
    ("CS", "Take me back to the dashboard", "Closes the chart, back to the command board", "Dashboard"),
    ("Any", "Switch to the phone app", "The phone view opens with the same desk", "Phone frame"),
    ("Any", "Switch to Kannada", "Mitra answers in casual Kannada from now on, full duplex", "Mode pill: ಕನ್ನಡ · full duplex"),
]
KN_MEANING = {
    "L1 ಹಂತದಲ್ಲಿ ಎಷ್ಟು ಕೇಸ್ ಇವೆ?": "How many cases are at L1?",
    "field officers ಹತ್ರ ಎಷ್ಟು cases pending ಇದೆ?": "How many cases are pending with field officers?",
    "ಮೊದಲ ಹಂತದಲ್ಲಿ ಎಷ್ಟು ದೂರುಗಳು ಬಾಕಿ ಇವೆ?": "How many complaints are pending at the first level?",
    "L2 ನಲ್ಲಿ ಎಷ್ಟು cases ಇವೆ?": "How many cases are at L2?",
    "ಎರಡನೇ ಹಂತದ ಅಧಿಕಾರಿಗಳ ಹತ್ರ ಎಷ್ಟು ದೂರುಗಳು ಬಾಕಿ ಇವೆ?": "How many complaints are pending with second-level officers?",
    "L3 officers ಹತ್ರ ಎಷ್ಟು cases ಇವೆ?": "How many cases are with L3 officers?",
    "ಮೂರನೇ ಹಂತದಲ್ಲಿ ಎಷ್ಟು ಕೇಸ್ ಇವೆ?": "How many cases are at the third level?",
    "ಹಂತವಾರು breakup ತೋರಿಸಿ": "Show the level-wise breakup",
    "L1, L2, L3 ಪ್ರಕಾರ cases ತೋರಿಸಿ": "Show cases by L1, L2, L3",
    "ಎಷ್ಟು ಕೇಸ್ escalate ಆಗಿವೆ?": "How many cases have been escalated?",
    "ಇಲ್ಲಿವರೆಗೆ ಎಷ್ಟು ದೂರುಗಳು ಮೇಲಕ್ಕೆ ಹೋದವು?": "How many complaints have gone up so far?",
    "ಎಷ್ಟು ಕೇಸ್ escalate ಆಗಿಲ್ಲ?": "How many cases have not been escalated?",
    "ಎಷ್ಟು ಕೇಸ್‌ಗಳಿಗೆ 3 ದಿನ ಉಳಿದಿವೆ?": "How many cases have 3 days left?",
    "ಮೂರು ದಿನ ಬಾಕಿ ಇರೋ cases ಎಷ್ಟು?": "How many cases have three days remaining?",
    "1 ದಿನ ಉಳಿದಿರೋ ಕೇಸ್ ಎಷ್ಟು?": "How many cases have 1 day left?",
    "5 ದಿನ ಉಳಿದಿರೋ cases ಎಷ್ಟು?": "How many cases have 5 days left?",
    "ಇವತ್ತೇ due ಇರೋ ಕೇಸ್ ಎಷ್ಟು?": "How many cases are due today?",
    "ನಾಳೆ due ಇರೋ ಕೇಸ್ ಎಷ್ಟು?": "How many cases are due tomorrow?",
    "7 day timeline ತೋರಿಸಿ": "Show the 7-day timeline",
    "deadline ಪ್ರಕಾರ cases ತೋರಿಸಿ": "Show cases by deadline",
    "RDPR ಹೇಗೆ perform ಮಾಡ್ತಿದೆ?": "How is RDPR performing?",
    "ಗ್ರಾಮೀಣಾಭಿವೃದ್ಧಿ ಇಲಾಖೆ ಹೇಗಿದೆ?": "How is the Rural Development department doing?",
    "ಕಂದಾಯ ಇಲಾಖೆ ಹೇಗಿದೆ?": "How is the Revenue department doing?",
    "ಆಹಾರ ಇಲಾಖೆ ಹೇಗಿದೆ?": "How is the Food department doing?",
    "ಶಿಕ್ಷಣ ಇಲಾಖೆ ಹೇಗಿದೆ?": "How is the Education department doing?",
    "ಆರೋಗ್ಯ ಇಲಾಖೆ ಹೇಗಿದೆ?": "How is the Health department doing?",
    "ನಗರಾಭಿವೃದ್ಧಿ ಇಲಾಖೆ ಹೇಗಿದೆ?": "How is Urban Development doing?",
    "ವಿದ್ಯುತ್ ಇಲಾಖೆ ಹೇಗಿದೆ?": "How is the Power department doing?",
    "ಪೊಲೀಸ್ ಇಲಾಖೆ ಹೇಗಿದೆ?": "How is the Police department doing?",
    "ಸಾರಿಗೆ ಇಲಾಖೆ ಹೇಗಿದೆ?": "How is the Transport department doing?",
    "ವಸತಿ ಇಲಾಖೆ ಹೇಗಿದೆ?": "How is the Housing department doing?",
    "ಕೃಷಿ ಇಲಾಖೆ ಹೇಗಿದೆ?": "How is the Agriculture department doing?",
    "ಆರೋಗ್ಯ ಇಲಾಖೆಯಲ್ಲಿ ಎಷ್ಟು ದೂರು ಬಾಕಿ ಇವೆ?": "How many complaints are pending in Health?",
    "RDPR ನಲ್ಲಿ ಎಷ್ಟು overdue ಇದೆ?": "How many are overdue in RDPR?",
    "ಹುಣಸೂರು ಹೇಗಿದೆ?": "How is Hunsur doing?",
    "ಹುಣಸೂರು ತಾಲ್ಲೂಕಿನ ಎಲ್ಲಾ ವಿವರ ತೋರಿಸಿ": "Show everything about Hunsur taluk",
    "ಪಿರಿಯಾಪಟ್ಟಣ ಹೇಗಿದೆ?": "How is Piriyapatna doing?",
    "ಮೈಸೂರು ಜಿಲ್ಲೆ ಹೇಗಿದೆ?": "How is Mysuru district doing?",
    "ಒಟ್ಟಾರೆ ರಾಜ್ಯದ dashboard ತೋರಿಸಿ": "Show the overall state dashboard",
    "ಸಕಾಲ ಅಂದ್ರೆ ಏನು?": "What is Sakala?",
    "Chief Secretary ಯಾರು?": "Who is the Chief Secretary?",
    "ತಡವಾದರೆ ಎಷ್ಟು compensation ಸಿಗುತ್ತೆ?": "How much compensation if it is late?",
    "RDPR ಹೇಗಿದೆ?": "How is RDPR doing?",
    "ಮತ್ತೆ ಹುಣಸೂರು?": "And Hunsur? (stays inside RDPR)",
    "ಒಟ್ಟಾರೆ L1 ನಲ್ಲಿ ಎಷ್ಟು ಕೇಸ್ ಇವೆ?": "Overall, how many cases are at L1? (scope cleared)",
    "ನಮ್ಮ ಊರು ಗೊರಹಳ್ಳಿಯಲ್ಲಿ ಒಂದು ವಾರದಿಂದ ಕುಡಿಯುವ ನೀರು ಬರ್ತಿಲ್ಲ": "No drinking water in our village Gorahalli for a week",
    "ನಮ್ಮ ಬೀದಿಯಲ್ಲಿ street light ಕೆಟ್ಟು ಹೋಗಿದೆ, ಪಿರಿಯಾಪಟ್ಟಣ ತಾಲ್ಲೂಕು": "The street light on our street is broken, Piriyapatna taluk",
    "ನನ್ನ ration card ಇನ್ನೂ ಬಂದಿಲ್ಲ, ಹುಣಸೂರು": "My ration card has not come yet, Hunsur",
}


def km(q: str) -> str:
    if q in KN_MEANING:
        return KN_MEANING[q]
    for kn, en in (("ತಾಲ್ಲೂಕಿನಲ್ಲಿ ಎಷ್ಟು ಕೇಸ್ ಬಾಕಿ ಇದೆ?", "How many cases are pending in this taluk?"), ("ಜಿಲ್ಲೆಯಲ್ಲಿ ಎಷ್ಟು ಕೇಸ್ ಬಾಕಿ ಇವೆ?", "How many cases are pending in this district?")):
        if kn in q:
            return en
    return ""


def build():
    stamp = time.strftime("%d %b %Y, %H:%M")
    en, kn = rows(C.BANK), rows(K.BANK)
    md = [f"# Mitra · test questionnaire (English and Kannada)", "",
          f"For manual testing of Mitra on web and phone. Expected numbers were read from the live database on **{stamp}**; they move by a few as new cases are filed, so a small difference is fine. "
          "Every data answer must come with a picture on screen; 'how is X doing' must open the full board of six cards with a scope chip. "
          "Use the Chief Secretary profile for sections 1, 2 and 4; the profile is named in section 3.", "",
          "## 1 · English: Chief Secretary data questions", "", "| # | Question | What it checks | Expected now | On screen |", "|---|---|---|---|---|"]
    for n, g, q, what, exp, scr in en:
        md.append(f"| {n} | {q} | {what} | {exp} | {scr} |")
    md += ["", "**Follow-up sequence (ask in this order, one conversation):**", ""]
    for i, (q, chk) in enumerate(C.SEQ, 1):
        md.append(f"{i}. {q} → expected {expected(chk)}" + (f" · scope chip: {chk.get('scope') or 'cleared'}" if "scope" in chk else ""))
    md += ["", "## 2 · Kannada: Chief Secretary data questions (switch to ಕನ್ನಡ first)", "", "| # | Question (Kannada) | Meaning | Expected now | On screen |", "|---|---|---|---|---|"]
    for n, g, q, what, exp, scr in kn:
        md.append(f"| {n} | {q} | {km(q)} | {exp} | {scr} |")
    md += ["", "**Kannada follow-up sequence (one conversation):**", ""]
    for i, (q, chk) in enumerate(K.SEQ, 1):
        md.append(f"{i}. {q} ({km(q)}) → expected {expected(chk)}")
    md += ["", "**Kannada citizen complaints (Citizen profile, Kannada):**", ""]
    for i, (q, chk) in enumerate(K.CITIZEN, 1):
        md.append(f"{i}. {q} ({km(q)}) → the request card with the category and place; answer spoken in Kannada")
    md += ["", "## 3 · General flows (English)", "", "| Profile | Say | Expected | On screen |", "|---|---|---|---|"]
    for p, q, exp, scr in EN_EXTRA:
        md.append(f"| {p} | {q} | {exp} | {scr} |")
    md += ["", "## 4 · What counts as a pass", "",
           "- The number spoken or drawn matches the expected one (within a few, as cases get filed).",
           "- A data answer always shows a picture; 'how is X doing' shows the board of six cards.",
           "- Departments outside Revenue, RDPR and Food are answered from the iPGRS sample week, and Mitra says so.",
           "- Follow-ups stay inside the department / place on the scope chip; 'overall' or the chip's ✕ clears it.",
           "- In Kannada, Mitra answers in casual Kannada and you can interrupt it any time.",
           "- Nothing invented: unknown places, departments or general questions get an honest 'not found' / 'not in my notes'.",
           "- Before the demo, connect the office VPN (complaint understanding is weaker on the offline model without it)."]
    return "\n".join(md), en, kn, stamp


def to_html(en, kn, stamp):
    e = html.escape
    css = """
    @page { size: A4; margin: 14mm 12mm; }
    body { font-family: "Segoe UI","Nirmala UI",sans-serif; color:#1e2633; font-size:10.5px; }
    h1 { font-size:20px; color:#12305c; margin:0 0 4px; } h2 { font-size:14px; color:#12305c; margin:18px 0 6px; border-bottom:2px solid #16c784; padding-bottom:3px; }
    p.lead { color:#5d6878; margin:0 0 10px; line-height:1.45; }
    table { width:100%; border-collapse:collapse; margin:4px 0 8px; page-break-inside:auto; } tr { page-break-inside:avoid; }
    th { background:#12305c; color:#fff; text-align:left; padding:5px 6px; font-size:10px; }
    td { padding:4px 6px; border-bottom:1px solid #e3e8ef; vertical-align:top; line-height:1.35; }
    tr:nth-child(even) td { background:#f6f8fb; }
    td.n { color:#8a95a5; width:22px; } td.x { font-weight:700; color:#0f766e; white-space:nowrap; } td.q { font-weight:600; }
    td.kn { font-family:"Nirmala UI","Noto Sans Kannada",sans-serif; font-size:11.5px; }
    ol li { margin:3px 0; } .tag { display:inline-block; background:#e8f7ee; color:#166534; border-radius:10px; padding:0 6px; font-size:9.5px; }
    ul li { margin:3px 0; }"""
    h = [f"<!doctype html><html><head><meta charset='utf-8'><title>Mitra test questionnaire</title><style>{css}</style></head><body>",
         "<h1>Mitra · test questionnaire <span style='color:#16c784'>English + ಕನ್ನಡ</span></h1>",
         f"<p class='lead'>For manual testing on web and phone. Expected numbers were read from the live database on <b>{e(stamp)}</b>; they move by a few as new cases are filed, so a small difference is fine. Every data answer must come with a picture; 'how is X doing' must open the full board of six cards with a scope chip. Use the Chief Secretary profile for sections 1, 2 and 4.</p>",
         "<h2>1 · English · Chief Secretary data questions</h2><table><tr><th>#</th><th>Question</th><th>What it checks</th><th>Expected now</th><th>On screen</th></tr>"]
    for n, g, q, what, exp, scr in en:
        h.append(f"<tr><td class='n'>{n}</td><td class='q'>{e(q)}</td><td>{e(what)}</td><td class='x'>{e(exp)}</td><td>{e(scr)}</td></tr>")
    h.append("</table><p><b>Follow-up sequence</b> (one conversation, in this order):</p><ol>")
    for q, chk in C.SEQ:
        h.append(f"<li>{e(q)} → expected <b>{e(expected(chk))}</b>" + (f" · scope chip: <span class='tag'>{e(chk.get('scope') or 'cleared')}</span>" if "scope" in chk else "") + "</li>")
    h.append("</ol><h2>2 · ಕನ್ನಡ · Chief Secretary data questions (switch to ಕನ್ನಡ first)</h2><table><tr><th>#</th><th>Question (Kannada)</th><th>Meaning</th><th>Expected now</th><th>On screen</th></tr>")
    for n, g, q, what, exp, scr in kn:
        h.append(f"<tr><td class='n'>{n}</td><td class='q kn'>{e(q)}</td><td>{e(km(q))}</td><td class='x'>{e(exp)}</td><td>{e(scr)}</td></tr>")
    h.append("</table><p><b>Kannada follow-up sequence</b> (one conversation):</p><ol>")
    for q, chk in K.SEQ:
        h.append(f"<li><span class='kn'>{e(q)}</span> ({e(km(q))}) → expected <b>{e(expected(chk))}</b></li>")
    h.append("</ol><p><b>Kannada citizen complaints</b> (Citizen profile, Kannada):</p><ol>")
    for q, chk in K.CITIZEN:
        h.append(f"<li><span class='kn'>{e(q)}</span> ({e(km(q))}) → the request card with the category and place; the answer spoken in Kannada</li>")
    h.append("</ol><h2>3 · General flows (English)</h2><table><tr><th>Profile</th><th>Say</th><th>Expected</th><th>On screen</th></tr>")
    for p, q, exp, scr in EN_EXTRA:
        h.append(f"<tr><td>{e(p)}</td><td class='q'>{e(q)}</td><td>{e(exp)}</td><td>{e(scr)}</td></tr>")
    h.append("""</table><h2>4 · What counts as a pass</h2><ul>
    <li>The number spoken or drawn matches the expected one (within a few, as cases get filed).</li>
    <li>A data answer always shows a picture; 'how is X doing' shows the board of six cards.</li>
    <li>Departments outside Revenue, RDPR and Food are answered from the iPGRS sample week, and Mitra says so.</li>
    <li>Follow-ups stay inside the department / place on the scope chip; 'overall' or the chip's ✕ clears it.</li>
    <li>In Kannada, Mitra answers in casual Kannada and you can interrupt it any time.</li>
    <li>Nothing invented: unknown places, departments or general questions get an honest 'not found' / 'not in my notes'.</li>
    <li>Before the demo, connect the office VPN (complaint understanding is weaker on the offline model without it).</li></ul></body></html>""")
    return "".join(h)


async def pdf(html_path: Path, out: Path):
    from cdp import Browser
    async with Browser(port=9499, size=(1240, 1754)) as b:
        await b.goto(html_path.resolve().as_uri(), 2)
        r = await b.cmd("Page.printToPDF", printBackground=True, preferCSSPageSize=True)
        out.write_bytes(base64.b64decode(r["data"]))


def main():
    md, en, kn, stamp = build()
    (ROOT / "Mitra_Test_Questionnaire.md").write_text(md, encoding="utf-8")
    hp = ROOT / "tools" / "questionnaire.html"
    hp.write_text(to_html(en, kn, stamp), encoding="utf-8")
    asyncio.run(pdf(hp, ROOT / "Mitra_Test_Questionnaire.pdf"))
    print(f"English {len(en)} + {len(C.SEQ)} follow-ups · Kannada {len(kn)} + {len(K.SEQ)} follow-ups + {len(K.CITIZEN)} citizen · general {len(EN_EXTRA)}")


if __name__ == "__main__":
    main()
