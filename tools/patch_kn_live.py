"""22 Oct 2026 (Pranay): Kannada in FULL DUPLEX. The same live session, the same functions, the same guardrails; Kannada is a
persona switch, not a different pipeline. Proven by tests/kn_live_probe.py: the live model hears spoken Kannada, calls the right
function and answers in spoken Kannada (first audio ~0.5 s after the question ends). The persona speaks the casual, code-mixed
Kannada people use every day in Bengaluru (English words where people use them), not formal written Kannada. Function
arguments go in English (the server also normalises any Kannada that slips through: query_board.normalise_args)."""
import ast
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BK = ROOT / "tools" / "backups" / "res22b"
BK.mkdir(parents=True, exist_ok=True)


def patch(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    shutil.copy(p, BK / (p.name + ".kn.bak"))
    for old, new in pairs:
        assert old in s, f"{rel}: missing\n{old[:140]}"
        s = s.replace(old, new, 1)
    if rel.endswith(".py"):
        ast.parse(s)
    p.write_text(s, encoding="utf-8")
    print("patched", rel)


KN_BLOCK = '''KANNADA = (
    "LANGUAGE: KANNADA. Speak Kannada, the way people really talk every day in Bengaluru and Mysuru: casual, warm, simple, "
    "code-mixed. Use English words wherever people naturally use them (complaint, officer, case, status, update, Tahsildar, PDO, "
    "deadline, pending, map, dashboard, department names, numbers if easier), and Kannada for the rest. Not formal or bookish "
    "Kannada, not a translation of English; short spoken sentences, like a helpful person at the taluk office or a friend. "
    "Examples of the tone: 'ಸರಿ, ನಿಮ್ಮ complaint register ಆಯ್ತು.', 'ಈಗ Hunsur taluk ನಲ್ಲಿ 10 cases pending ಇವೆ.', "
    "'ಒಂದು ನಿಮಿಷ, ನೋಡ್ತೀನಿ.', 'Chief Secretary Madam, ನಮಸ್ಕಾರ.' "
    "The person may speak Kannada, English or a mix: understand all of it and always answer in this casual Kannada (switch to "
    "English only if they ask for English: then call set_language with en). "
    "FUNCTION ARGUMENTS ARE ALWAYS IN ENGLISH / LATIN LETTERS: place names transliterated (ಹುಣಸೂರು -> Hunsur, ಪಿರಿಯಾಪಟ್ಟಣ -> "
    "Piriyapatna, ಮೈಸೂರು -> Mysuru), status in English (open, overdue, resolved), departments in English (Revenue, RDPR, Food, "
    "Education...), levels as L1 / L2 / L3. The only exception: chat_text, reply and voice notes carry the person's own words exactly "
    "as said (Kannada stays Kannada). Function results come back in English: say them in this casual Kannada, keeping every id, "
    "name, place, number, date and decision exactly; read case ids digit by digit (G R ಐದು ಸೊನ್ನೆ ನಾಲ್ಕು...) or in English digits, "
    "and numbers the way people say them (12 -> 'ಹನ್ನೆರಡು' or 'twelve' are both fine)."
)


'''

patch("mitra/server/live.py", [
    ('''def instruction(s: dict) -> str:''', KN_BLOCK + '''def instruction(s: dict) -> str:'''),
    ('''    if s["lang"] == "kn":
        await ws.send_json({"type": "fallback", "reason": "kannada uses the cascade"}); await ws.close(); return
''', ''''''),
    ('''        "generationConfig": {"responseModalities": ["TEXT" if text_mode else "AUDIO"], "temperature": 0.6,
                             "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": config.get("GEMINI_VOICE") or "Kore"}}}},''',
     '''        "generationConfig": {"responseModalities": ["TEXT" if text_mode else "AUDIO"], "temperature": 0.6,
                             "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": config.get("GEMINI_VOICE") or "Kore"}},
                                              **({"languageCode": "kn-IN"} if s.get("lang") == "kn" else {})}},'''),
])

# the language block goes FIRST in the instruction when the session is Kannada
s = (ROOT / "mitra/server/live.py").read_text(encoding="utf-8")
i = s.index("def instruction(s: dict) -> str:")
j = s.index("    lines = [", i)
k = s.index("    ]\n", j)
s = s[:k + 6] + '''    if s.get("lang") == "kn":
        lines.insert(0, KANNADA)
''' + s[k + 6:]
ast.parse(s)
(ROOT / "mitra/server/live.py").write_text(s, encoding="utf-8")
print("kannada block placed")

patch("mitra/web/mitra.js", [
    ("  if (!wakeOnly && text && !silentEcho && J.lang !== 'kn' && liveOpen(text)) return;",
     "  if (!wakeOnly && text && !silentEcho && liveOpen(text)) return;"),
    ("function liveWanted() { return J.lang !== 'kn' && Date.now() > LV.fallbackUntil && (!!J.mic || J.liveTest) && !J.muted; }",
     "function liveWanted() { return Date.now() > LV.fallbackUntil && (!!J.mic || J.liveTest) && !J.muted; }"),
    ("  const m = LV.open ? (LV.ready ? 'live' : 'connecting') : (J.lang === 'kn' ? 'kannada' : Date.now() < LV.fallbackUntil ? 'cascade' : 'standby');",
     "  const m = LV.open ? (LV.ready ? (J.lang === 'kn' ? 'kannada' : 'live') : 'connecting') : (Date.now() < LV.fallbackUntil ? 'cascade' : 'standby');"),
    ("kannada: 'ಕನ್ನಡ · voice'", "kannada: 'ಕನ್ನಡ · full duplex'"),
    ("      const again = J.lang !== 'kn', say = e.say || '';", "      const again = true, say = e.say || '';"),
])
print("done")
