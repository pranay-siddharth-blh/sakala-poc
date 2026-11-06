"""22 Oct 2026 (Pranay): Kannada stays Kannada on every path, and the language changes by voice, both ways, no button.
Found: the document reply (/api/document, /api/document/submit, /api/photo, /api/updates) came back in English on a Kannada
session (only /api/turn translated), and the live voice was told to read it "in these words", so Mitra spoke English in the
middle of a Kannada conversation. Also: a Kannada sentence said to an English session made the model call set_language + chat_text
in one turn, but the new Kannada session only heard the language acknowledgement and lost the question it had just asked.
- main._with_voice translates like /api/turn (one helper, casual code-mixed Kannada; ids, names, numbers kept).
- live.py: the announcement after a language change carries every reply of that turn (translated for Kannada); a harness at the
  end of a turn switches the language itself when the person asked for it (any wording, either language) or simply spoke Kannada
  to an English session and the model did not call set_language; the instruction asks the model to switch first and still act.
- brain.lang_asked / kn_share: one deterministic reading of 'switch to Kannada / English' in either language (rules + live harness).
- client: the live voice reads an HTTP reply in Kannada on a Kannada session; the reconfigure announcement is read in full;
  the EN / ಕನ್ನಡ toggle animates when the language changes by voice; phone has no toggle, voice is the way."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def patch(rel, pairs, py=True):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert old in s, f"{rel}: missing\n{old[:160]}"
        s = s.replace(old, new, 1)
    if py:
        ast.parse(s)
    assert "\x08" not in s
    p.write_text(s, encoding="utf-8")
    print("patched", rel)


# ---------------------------------------------------------------- brain: one reading of 'switch the language'
patch("mitra/server/brain.py", [
    ('''def _rules(ctx: dict, text: str) -> dict:
    t = text.strip()''',
     '''KN_RX = re.compile("[\\u0c80-\\u0cff]")
_KN_WORD = r"(kannada|ಕನ್ನಡ)"
_EN_WORD = r"(english|ಇಂಗ್ಲಿಷ್|ಇಂಗ್ಲೀಷ್|ಇಂಗ್ಲಿಶ್|ಇಂಗ್ಲೀಶ್|ಆಂಗ್ಲ)"
_LANG_VERB = (r"\\b(speak|talk|switch|shift|change|continue|go|reply|answer|respond|use|say|tell|carry on|move|put|do it|only|please|mode|language)\\b|"
              r"ಮಾತಾಡ|ಮಾತನಾಡ|ಬದಲಾಯಿಸ|ಬದಲಿಸ|ಹೇಳ|ಬೇಕು|ಸಾಕು|ಉತ್ತರ|ಭಾಷೆ|ಬನ್ನಿ|ಹೋಗ")


def lang_asked(text: str) -> str:
    """'switch to Kannada', 'ಕನ್ನಡದಲ್ಲಿ ಮಾತಾಡಿ', 'English please', 'ಇಂಗ್ಲಿಷ್ ಗೆ ಬದಲಾಯಿಸಿ' -> 'kn' / 'en'; anything else ''.
    A language named without any wish to change ('the Kannada teacher is absent') is not a switch."""
    low = (text or "").lower().strip()
    if not low:
        return ""
    found = []
    for code, word in (("kn", _KN_WORD), ("en", _EN_WORD)):
        m = None
        for m in re.finditer(word, low):
            pass
        if not m:
            continue
        tail = low[m.end():m.end() + 12]
        wish = (re.search(_LANG_VERB, low) or re.search(r"^\\s*(please|mode|language|only|now|ಅಲ್ಲಿ|ದಲ್ಲಿ|ಕ್ಕೆ|ಗೆ|ನಲ್ಲಿ|ಲ್ಲಿ|ಲಿ)", tail)
                or re.search(r"\\b(in|to|into)\\s+" + word, low) or len(low.split()) <= 2)
        if wish and not re.search(word + r"\\s*(teacher|school|medium|class|exam|paper|book|news|film|movie|song|subject)", low):
            found.append((m.end(), code))
    if not found:
        return ""
    if len(found) == 2:
        # 'from Kannada to English': the language after to / in / ಗೆ / ಕ್ಕೆ wins, else the last one named
        for code, word in (("kn", _KN_WORD), ("en", _EN_WORD)):
            if re.search(r"(\\b(to|into|in)\\s+|)" + word + r"\\s*(ಗೆ|ಕ್ಕೆ|ನಲ್ಲಿ|ದಲ್ಲಿ)", low) or re.search(r"\\b(to|into|in)\\s+" + word, low):
                return code
    return max(found)[1]


def kn_share(text: str) -> float:
    """Share of Kannada letters among the letters of a sentence (0 when it has no letters)."""
    kn = len(KN_RX.findall(text or ""))
    lat = len(re.findall(r"[A-Za-z]", text or ""))
    return kn / (kn + lat) if kn + lat else 0.0


def _rules(ctx: dict, text: str) -> dict:
    t = text.strip()'''),
    ('''    if re.search(r"[\\u0c80-\\u0cff]", t) and re.search(r"ವಾಪಸ್|ಹಿಂದೆ|ಹೋಗಿ|ಕರ್ಕೊಂಡು|ಕರೆದುಕೊಂಡು|ತೋರಿಸಿ|ತೆರೆಯಿರಿ|ಮುಚ್ಚಿ|switch|open|go|take", t, re.I):''',
     '''    la = lang_asked(t)
    if la:                                              # 'switch to Kannada' / 'English ನಲ್ಲಿ ಮಾತಾಡಿ', in either language, any wording
        return {"intent": "set_language", "language": la}
    if re.search(r"[\\u0c80-\\u0cff]", t) and re.search(r"ವಾಪಸ್|ಹಿಂದೆ|ಹೋಗಿ|ಕರ್ಕೊಂಡು|ಕರೆದುಕೊಂಡು|ತೋರಿಸಿ|ತೆರೆಯಿರಿ|ಮುಚ್ಚಿ|switch|open|go|take", t, re.I):'''),
    ('''    if has("kannada", "ಕನ್ನಡ") and has("speak", "switch", "in", "talk", "ಮಾತನಾಡು"):
        return {"intent": "set_language", "language": "kn"}
    if has("english") and has("speak", "switch", "in", "talk"):
        return {"intent": "set_language", "language": "en"}
''', ''),
])

# ---------------------------------------------------------------- tools: the acknowledgement fits the moment
patch("mitra/server/tools.py", [
    ('''async def t_set_language(sess, args):
    lang = (args.get("language") or "en").lower()
    lang = "kn" if lang.startswith("k") or "ಕನ್ನಡ" in lang else "en"
    sess["lang"] = lang
    store.save_session(sess)
    say = "ಸರಿ, ಇನ್ಮೇಲೆ ಕನ್ನಡದಲ್ಲೇ ಮಾತಾಡ್ತೀನಿ. ಹೇಳಿ, ಏನು ಮಾಡ್ಬೇಕು?" if lang == "kn" else "Okay, I will speak English now."
    return {"say": say, "ui": [{"op": "lang", "lang": lang}]}''',
     '''async def t_set_language(sess, args):
    """Switch the spoken language (by voice, in either language). A flow that is waiting for an answer is not interrupted:
    the acknowledgement is short and whatever Mitra just asked is repeated after it by the caller."""
    lang = (args.get("language") or "").lower()
    if not lang or lang in ("other", "the other", "switch"):
        lang = "en" if sess.get("lang") == "kn" else "kn"
    lang = "kn" if lang.startswith("k") or "ಕನ್ನಡ" in lang else "en"
    same = sess.get("lang") == lang
    sess["lang"] = lang
    store.save_session(sess)
    st = sess.get("state") or {}
    busy = (st.get("flow") or "") not in ("", "menu", "done") or bool(st.get("pending_action"))
    if same:
        say = "ಈಗಾಗಲೇ ಕನ್ನಡದಲ್ಲೇ ಮಾತಾಡ್ತಿದ್ದೀನಿ. ಹೇಳಿ." if lang == "kn" else "We are already in English. Go ahead."
    elif lang == "kn":
        say = "ಸರಿ, ಇನ್ಮೇಲೆ ಕನ್ನಡದಲ್ಲೇ ಮಾತಾಡ್ತೀನಿ." + ("" if busy else " ಹೇಳಿ, ಏನು ಮಾಡ್ಬೇಕು?")
    else:
        say = "Okay, English from here." + ("" if busy else " What would you like to do?")
    return {"say": say, "ui": [{"op": "lang", "lang": lang}]}'''),
])

# ---------------------------------------------------------------- main: every HTTP reply speaks Kannada on a Kannada session
patch("mitra/server/main.py", [
    ('''    res = await tools.execute(s, dec["intent"], dec["args"])
    say = guard.scrub(res.get("say") or "")
    kn_parts = None
    if s["lang"] == "kn" and say and not KN_RX.search(say):
        kn_parts = await translate_kn_parts(say)
        say = " ".join(kn_parts) or say
''',
     '''    res = await tools.execute(s, dec["intent"], dec["args"])
    say, kn_parts = await kn_say(s, guard.scrub(res.get("say") or ""))
'''),
    ('''    t0 = time.time()
    heard, stt_prov = req.text.strip(), "text"
    if not heard and req.audio_b64:
        heard, stt_prov = await speech.stt(req.audio_b64, s["lang"])
        s["state"]["last_audio"] = req.audio_b64[:4_000_000]
        store.save_session(s)
    # drop the wake phrase ("hey Mitra, ...") so only the request reaches the brain and the chat
    stripped = strip_wake(heard)''',
     '''    t0 = time.time()
    heard, stt_prov = req.text.strip(), "text"
    if not heard and req.audio_b64:
        heard, stt_prov = await speech.stt(req.audio_b64, s["lang"])
        s["state"]["last_audio"] = req.audio_b64[:4_000_000]
        store.save_session(s)
    if s["lang"] == "en" and heard and brain.kn_share(heard) >= 0.5 and not brain.lang_asked(heard):
        s["lang"] = "kn"                                  # spoken to in Kannada: Kannada from here (this reply is translated below)
        store.save_session(s)
    # drop the wake phrase ("hey Mitra, ...") so only the request reaches the brain and the chat
    stripped = strip_wake(heard)'''),
    ('''async def translate_kn_parts(say: str) -> list[str]:''',
     '''async def kn_say(s: dict, say: str) -> tuple[str, list[str] | None]:
    """What Mitra says on a Kannada session is Kannada: a tool's English reply is translated (casual, code-mixed; ids, names,
    places, numbers and dates kept), in two parts so the first voice clip is ready early. English session: unchanged."""
    if s.get("lang") == "kn" and say and not KN_RX.search(say):
        try:
            parts = await translate_kn_parts(say)
        except Exception:  # noqa: BLE001
            parts = []
        if parts:
            return " ".join(parts), parts
    return say, None


KN_PROMPT = ("Translate the message into casual, warm, spoken Kannada, the way people really talk every day in Bengaluru and Mysuru: "
             "short spoken sentences, code-mixed, keeping the English words people naturally use (complaint, officer, case, status, "
             "form, submit, upload, letter, Tahsildar, PDO, deadline, pending, dashboard, department and service names). Not formal or "
             "bookish Kannada. Keep case ids (GR-..., SK-...), iPGRS numbers, people's names, place names, dates and amounts exactly as "
             "they are. Output only the Kannada.")


async def translate_kn_parts(say: str) -> list[str]:'''),
    ('''            body = {"systemInstruction": {"parts": [{"text": "Translate the message into simple, polite, natural spoken Kannada, as a helpful government voice assistant would say it. Translate service and department names into Kannada too. Keep case ids (GR-..., SK-...), people's names, place names, dates and amounts exactly as they are. Output only the Kannada."}]},''',
     '''            body = {"systemInstruction": {"parts": [{"text": KN_PROMPT}]},'''),
    ('''                "messages": [{"role": "system", "content": "Translate the message into simple, polite, natural spoken Kannada, as a helpful government voice assistant would say it. Translate service and department names into Kannada too. Keep case ids (GR-..., SK-...), people's names, place names, dates and amounts exactly as they are. Output only the Kannada."},''',
     '''                "messages": [{"role": "system", "content": KN_PROMPT},'''),
    ('''async def _with_voice(s: dict, say: str, ui: list, intent: str = "", want_audio: bool = True) -> dict:
    say = guard.scrub(say)
    audio_b64, tts_prov, tid, parts = "", "browser", "", []
    if say and want_audio:
        parts = split_chunks(say)''',
     '''async def _with_voice(s: dict, say: str, ui: list, intent: str = "", want_audio: bool = True) -> dict:
    say, kn_parts = await kn_say(s, guard.scrub(say))   # a document read, a form submitted, a photo: Kannada on a Kannada session
    audio_b64, tts_prov, tid, parts = "", "browser", "", []
    if say and want_audio:
        parts = kn_parts or split_chunks(say)'''),
])

# ---------------------------------------------------------------- live: the switch turn keeps its answer; the harness switches itself
patch("mitra/server/live.py", [
    ('''def instruction(s: dict) -> str:''',
     '''async def kn_say(say: str, lang: str) -> str:
    """A reply announced on a Kannada session is Kannada (the same translation the HTTP replies use)."""
    if lang == "kn" and say and not brain.KN_RX.search(say):
        from . import main as M
        try:
            return (await M.kn_say({"lang": "kn"}, say))[0]
        except Exception:  # noqa: BLE001
            return say
    return say


def lang_switch_wanted(text: str, lang: str) -> str:
    """The harness reading of a turn: the language the person asked for (either wording), or Kannada when they simply spoke
    Kannada to an English session. '' when nothing should change."""
    want = brain.lang_asked(text)
    if not want and lang == "en" and brain.kn_share(text) >= 0.5:
        want = "kn"
    return want if want and want != lang else ""


def instruction(s: dict) -> str:'''),
    ('''        ("The conversation is already in Kannada: never call set_language with kn; call it with en only if they ask for English. "
         if s.get("lang") == "kn" else "If the person speaks Kannada or asks for Kannada, call set_language with language kn. ") +''',
     '''        ("The conversation is already in Kannada: never call set_language with kn; call it with en the moment they ask for English "
         "in any words (switch to English, English please, ಇಂಗ್ಲಿಷ್ ಗೆ ಬದಲಾಯಿಸಿ, English ನಲ್ಲಿ ಮಾತಾಡಿ); the next session speaks English. "
         if s.get("lang") == "kn" else
         "If the person speaks Kannada, or asks for Kannada in any words (switch to Kannada, ಕನ್ನಡದಲ್ಲಿ ಮಾತಾಡಿ, Kannada please), "
         "call set_language with language kn FIRST and in the same turn still do what they asked with the other functions "
         "(file the problem, answer the question); the next session speaks Kannada. ") +'''),
    ('''                    after = store.get_session(sid)
                    if (after["profile"], after["officer"], after["lang"]) != before:
                        pending["reconfig"] = True
                        pending["say"] = res.get("say", "")
''',
     '''                    after = store.get_session(sid)
                    if (after["profile"], after["officer"], after["lang"]) != before:
                        pending["reconfig"] = True
                        pending["say"] = res.get("say", "")
                    elif pending["reconfig"] and res.get("say"):
                        # the same turn also filed / answered something: the new session announces that too, in its language
                        pending["say"] = (pending.get("say", "") + " " + await kn_say(res["say"], after["lang"])).strip()
'''),
    ('''                if a and turn["intent"] != "identity":            # guardrails 21-22: numbers and ids must have a source''',
     '''                if u and not pending["reconfig"] and turn["intent"] != "set_language":
                    # the harness: the person asked for the other language (any wording) or spoke Kannada to an English session,
                    # and the model did not switch: the server switches, whatever the model did
                    try:
                        cur = store.get_session(sid)
                        want = lang_switch_wanted(u, cur["lang"]) if cur else ""
                        if want:
                            res = await tools.execute(cur, "set_language", {"language": want, "_text": u})
                            store.save_session(cur)
                            after = store.get_session(sid)
                            await ws.send_json({"type": "tool", "name": "set_language", "say": res.get("say", ""), "ui": res.get("ui", []),
                                                "profile": after["profile"], "officer": after["officer"], "lang": after["lang"], "auto": True})
                            pending["reconfig"] = True
                            pending["say"] = res.get("say", "")
                            pending["announce"] = True
                            turn["intent"] = (turn["intent"] + " + " if turn["intent"] else "") + "set_language (auto)"
                    except Exception as e:  # noqa: BLE001
                        STATS["last_error"] = f"auto language: {str(e)[:120]}"
                if a and turn["intent"] != "identity":            # guardrails 21-22: numbers and ids must have a source'''),
    ('''                if pending["reconfig"]:
                    await ws.send_json({"type": "reconfigure", "say": ""})     # the result was already spoken
                    return''',
     '''                if pending["reconfig"]:
                    # the result was already spoken, unless the harness switched the language after the model's answer
                    await ws.send_json({"type": "reconfigure", "say": pending.get("say", "") if pending.get("announce") else ""})
                    return'''),
])

# ---------------------------------------------------------------- client
patch("mitra/web/mitra.js", [
    ('''function lvRead(text) {
  if (!LV.ws || LV.ws.readyState !== 1 || !LV.ready) { LV.q.push({ read: text }); return; }
  lvCut(); LV.ws.send(JSON.stringify({ type: 'text', text: `(Say this to the person now, in these words, then stop. Call no function.) ${text}`, system: true }));''',
     '''function lvRead(text) {
  if (!LV.ws || LV.ws.readyState !== 1 || !LV.ready) { LV.q.push({ read: text }); return; }
  // a Kannada session reads it in Kannada even if an English line slipped through (the server translates first; this is the net)
  const how = J.lang === 'kn' ? 'in casual spoken Kannada, keeping every id, name, place, number and date exactly' : 'in these words';
  lvCut(); LV.ws.send(JSON.stringify({ type: 'text', text: `(Say this to the person now, ${how}, then stop. Call no function.) ${text}`, system: true }));'''),
    ('''      if (again) setTimeout(() => { liveOpen(); if (say) LV.q.push({ system: say }); }, 300);''',
     '''      if (again) setTimeout(() => { liveOpen(); if (say) LV.q.push({ read: say }); }, 300);   // read in full: the acknowledgement and any question it carries'''),
    ('''function renderLang() {
  document.querySelectorAll('#lang button').forEach(b => b.classList.toggle('on', b.dataset.l === J.lang));
  document.documentElement.lang = J.lang === 'kn' ? 'kn' : 'en';
}''',
     '''function renderLang() {
  document.querySelectorAll('#lang button').forEach(b => b.classList.toggle('on', b.dataset.l === J.lang));
  document.documentElement.lang = J.lang === 'kn' ? 'kn' : 'en';
  if (renderLang.last && renderLang.last !== J.lang) {               // changed by voice: the toggle answers, the orb pulses
    const l = $('#lang'); if (l) { l.classList.remove('switched'); void l.offsetWidth; l.classList.add('switched'); setTimeout(() => l.classList.remove('switched'), 1300); }
    if (document.querySelector('.orb-wrap')) { Orb.pulse(); flyLabel(J.lang === 'kn' ? 'ಕನ್ನಡ' : 'English'); }
    modePill();
  }
  renderLang.last = J.lang;
}'''),
], py=False)

patch("mitra/web/mitra.css", [
    ('''.lang button{padding:6px 11px;font-size:12px;font-weight:600;color:var(--mute)}
.lang button.on{background:var(--s2);color:var(--tx)}''',
     '''.lang button{padding:6px 11px;font-size:12px;font-weight:600;color:var(--mute);transition:background .35s,color .35s}
.lang button.on{background:var(--s2);color:var(--tx)}
.lang.switched{animation:langPop .9s cubic-bezier(.2,.8,.2,1)}
.lang.switched button.on{animation:langGlow 1.2s ease-out}
@keyframes langPop{0%{transform:scale(1)}35%{transform:scale(1.1)}100%{transform:scale(1)}}
@keyframes langGlow{0%{box-shadow:0 0 0 0 rgba(22,199,132,0)}30%{box-shadow:0 0 0 5px rgba(22,199,132,.35),0 0 26px rgba(22,199,132,.55)}100%{box-shadow:0 0 0 0 rgba(22,199,132,0)}}'''),
], py=False)

patch("mitra/web/index.html", [
    ('<link rel="stylesheet" href="/mitra.css?v=75">', '<link rel="stylesheet" href="/mitra.css?v=76">'),
    ('<script src="/mitra.js?v=76"></script>', '<script src="/mitra.js?v=77"></script>'),
], py=False)
print("done")
