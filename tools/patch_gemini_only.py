"""23 Oct 2026 (Pranay): Mitra uses Gemini only. Qwen (the office H200 gateway) is removed from the brain, the Kannada
translation, speech to text and text to speech; Sarvam is no longer picked automatically (it had no key and was never used).
The chains become Gemini, then the deterministic rules (brain) or the browser (speech). Nothing else changes: the intents,
tools, router, SQL, guardrails and the live voice are untouched. The POC side is in app/server/ai.py (edited separately)."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def patch(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert old in s, f"{rel}: missing\n{old[:200]}"
        s = s.replace(old, new, 1)
    ast.parse(s)
    assert "\x08" not in s
    p.write_text(s, encoding="utf-8")
    print("patched", rel)


patch("mitra/server/config.py", [
    ('''# H200 gateway (from app/.env)
QWEN_BASE = get("SQL_VERIFY_BASE_URL")
QWEN_KEY = get("SQL_VERIFY_API_KEY")
QWEN_MODEL = get("SQL_VERIFY_MODEL", "qwen4-deploy")
QWEN_TTS_BASE = get("TTS_BASE_URL") or QWEN_BASE
QWEN_TTS_KEY = get("TTS_API_KEY") or QWEN_KEY
QWEN_TTS_MODEL = get("TTS_MODEL", "qwen3-tts")
QWEN_TTS_VOICE = get("TTS_VOICE", "serena")
CA_BUNDLE = get("AI_MODEL_CA_BUNDLE_PATH")

# Provider preference: "auto" = best available by key, else an explicit name
BRAIN = get("MITRA_BRAIN", "auto")          # gemini | qwen | rules
STT = get("MITRA_STT", "auto")              # sarvam | gemini | qwen | browser
TTS = get("MITRA_TTS", "auto")              # sarvam | gemini | qwen | browser''',
     '''# Every model call is Gemini (23 Oct 2026). "auto" = Gemini when the key is set, else the rules brain / the browser voice.
BRAIN = get("MITRA_BRAIN", "auto")          # gemini | rules
STT = get("MITRA_STT", "auto")              # gemini | browser
TTS = get("MITRA_TTS", "auto")              # gemini | browser'''),
])

patch("mitra/server/brain.py", [
    ('''Providers, best available first: gemini (Interactions API, JSON schema) > qwen (H200 gateway,
guided JSON) > rules (regex; always available).''',
     '''Providers: gemini (JSON schema) > rules (regex; always available). Gemini only (23 Oct 2026).'''),
    ('''        verify = config.CA_BUNDLE if config.CA_BUNDLE else False
        _http = httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=1.5), verify=verify)''',
     '''        _http = httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=1.5))'''),
    ('''    if config.GEMINI_API_KEY and up("gemini"):
        return "gemini"
    if config.QWEN_BASE and config.QWEN_KEY and up("qwen"):
        return "qwen"
    return "rules"''',
     '''    if config.GEMINI_API_KEY and up("gemini"):
        return "gemini"
    return "rules"'''),
    ('''    order = [prov] + [p for p in ("gemini", "qwen") if p != prov] + ["rules"]''',
     '''    order = [prov] + [p for p in ("gemini",) if p != prov] + ["rules"]'''),
    ('''            elif p == "qwen" and config.QWEN_BASE and config.QWEN_KEY and up("qwen"):
                out = await _qwen(ctx, text)
''', ''),
    ('''async def _qwen(ctx: dict, text: str) -> dict:
    body = {"model": config.QWEN_MODEL, "temperature": 0.0, "max_tokens": 300,
            "messages": [{"role": "system", "content": system_prompt(ctx)},
                         {"role": "user", "content": f"They said: {text}"}],
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema", "json_schema": {"name": "mitra_intent", "schema": schema_for(ctx['profile'])}}}
    r = await http().post(f"{config.QWEN_BASE}/chat/completions", json=body,
                          headers={"Authorization": f"Bearer {config.QWEN_KEY}"})
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    content = re.sub(r"^.*?</think>", "", content, flags=re.S).strip()
    content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
    if not content.startswith("{"):
        content = re.search(r"\\{.*\\}", content, re.S).group(0)
    return json.loads(content, strict=False)


''', ''),
])

patch("mitra/server/main.py", [
    ('''    if not (config.QWEN_BASE and config.QWEN_KEY) or not brain.up("qwen"):
        return ""
    try:
        body = {"model": config.QWEN_MODEL, "temperature": 0.1, "max_tokens": 400,
                "messages": [{"role": "system", "content": KN_PROMPT},
                             {"role": "user", "content": text[:1200]}],
                "chat_template_kwargs": {"enable_thinking": False}}
        r = await brain.http().post(f"{config.QWEN_BASE}/chat/completions", json=body,
                                    headers={"Authorization": f"Bearer {config.QWEN_KEY}"}, timeout=20.0)
        r.raise_for_status()
        out = r.json()["choices"][0]["message"]["content"]
        out = re.sub(r"^.*?</think>", "", out, flags=re.S).strip()
        return out if KN_RX.search(out) else ""
    except Exception:
        return ""''',
     '''    return ""                                       # Gemini only: no second translation engine'''),
])

patch("mitra/server/speech.py", [
    ('''STT:  sarvam (Saaras v4, Kannada + English) > gemini (Interactions API, audio in)
      > qwen (the H200 gateway through the Sakala /api/transcribe) > browser (client-side Web Speech)
TTS:  sarvam (Bulbul v4-flash) > gemini (3.8 Flash TTS) > qwen (qwen3-tts) > browser (speechSynthesis)''',
     '''STT:  gemini (audio in) > browser (client-side Web Speech)
TTS:  gemini (Flash TTS) > browser (speechSynthesis)
Gemini only (23 Oct 2026). The Sarvam adapters stay dormant: used only if MITRA_STT / MITRA_TTS is set to sarvam explicitly.'''),
    ('''        verify = config.CA_BUNDLE if config.CA_BUNDLE else False
        _http = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0), verify=verify)''',
     '''        _http = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0))'''),
    ('''        "sarvam": bool(config.SARVAM_API_KEY),
        "qwen": bool(config.QWEN_BASE and config.QWEN_KEY),
''', ''),
    ('''    if config.SARVAM_API_KEY:
        return "sarvam"
    if config.GEMINI_API_KEY:
        return "gemini"
    if lang == "kn":                      # qwen3-asr has no Kannada: the browser engine does
        return "browser"
    from . import brain
    if config.QWEN_BASE and config.QWEN_KEY and brain.up("qwen"):
        return "qwen"
    return "browser"''',
     '''    if config.GEMINI_API_KEY:
        return "gemini"
    return "browser"'''),
    ('''    if config.SARVAM_API_KEY:
        return "sarvam"
    if config.GEMINI_API_KEY:
        return "gemini"
    if lang == "kn":                      # qwen3-tts has no Kannada
        return "browser"
    from . import brain
    if config.QWEN_TTS_BASE and config.QWEN_TTS_KEY and brain.up("qwen"):
        return "qwen"
    return "browser"''',
     '''    if config.GEMINI_API_KEY:
        return "gemini"
    return "browser"'''),
    ('''    order = [prov] + [p for p in ("sarvam", "gemini", "qwen") if p != prov]
    for p in order:
        try:''',
     '''    order = [prov] + [p for p in ("gemini",) if p != prov]
    for p in order:
        try:'''),
    ('''            if p == "qwen" and config.QWEN_BASE:
                r = await sakala.transcribe(audio_b64, lang)
                return (r.get("text") or "").strip(), "qwen"
''', ''),
    ('''    order = [prov] + [p for p in ("sarvam", "gemini", "qwen") if p != prov]
    from . import brain''',
     '''    order = [prov] + [p for p in ("gemini",) if p != prov]
    from . import brain'''),
    ('''            if p == "qwen" and config.QWEN_TTS_BASE and lang != "kn":
                wav = await _tts_qwen(text)
                if wav and len(wav) > 1000:
                    return wav, "qwen"
''', ''),
    ('''async def _tts_qwen(text: str) -> bytes:
    body = {"model": config.QWEN_TTS_MODEL, "input": text[:3000], "voice": config.QWEN_TTS_VOICE,
            "response_format": "wav"}
    r = await http().post(f"{config.QWEN_TTS_BASE}/audio/speech", json=body,
                          headers={"Authorization": f"Bearer {config.QWEN_TTS_KEY}"}, timeout=40.0)
    r.raise_for_status()
    ct = r.headers.get("content-type", "")
    if "json" in ct:
        j = r.json()
        data = j.get("audio") or (j.get("data") or [{}])[0].get("b64_json") or j.get("b64_json")
        return base64.b64decode(data) if data else b""
    return r.content


''', ''),
])
print("done")
