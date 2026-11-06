"""Speech adapters. Every provider is optional; `pick_*` chooses the best one that has a key.

STT:  gemini (audio in) > browser (client-side Web Speech)
TTS:  gemini (Flash TTS) > browser (speechSynthesis)
Gemini only (23 Oct 2026). The Sarvam adapters stay dormant: used only if MITRA_STT / MITRA_TTS is set to sarvam explicitly.
"""
from __future__ import annotations

import base64
import re

import httpx

from . import config, sakala

_http: httpx.AsyncClient | None = None


def http() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0))
    return _http


def providers() -> dict:
    """What is available right now, for the boot screen."""
    return {
        "gemini": bool(config.GEMINI_API_KEY),
        "stt": pick_stt("en"), "stt_kn": pick_stt("kn"),
        "tts": pick_tts("en"), "tts_kn": pick_tts("kn"),
    }


def pick_stt(lang: str) -> str:
    want = config.STT
    if want != "auto":
        return want
    if config.GEMINI_API_KEY:
        return "gemini"
    return "browser"


def pick_tts(lang: str) -> str:
    want = config.TTS
    if want != "auto":
        return want
    if config.GEMINI_API_KEY:
        return "gemini"
    return "browser"


# ---------------------------------------------------------------------------- STT
async def stt(audio_b64: str, lang: str = "en") -> tuple[str, str]:
    prov = pick_stt(lang)
    order = [prov] + [p for p in ("gemini",) if p != prov]
    for p in order:
        try:
            if p == "sarvam" and config.SARVAM_API_KEY:
                return await _stt_sarvam(audio_b64, lang), "sarvam"
            if p == "gemini" and config.GEMINI_API_KEY:
                return await _stt_gemini(audio_b64, lang), "gemini"
        except Exception as e:  # try the next provider
            last = str(e)[:160]
            continue
    return "", "none"


async def _stt_sarvam(audio_b64: str, lang: str) -> str:
    files = {"file": ("voice.wav", base64.b64decode(audio_b64), "audio/wav")}
    data = {"model": config.SARVAM_STT_MODEL, "language_code": "kn-IN" if lang == "kn" else "en-IN"}
    r = await http().post(f"{config.SARVAM_BASE}/speech-to-text", files=files, data=data,
                          headers={"api-subscription-key": config.SARVAM_API_KEY})
    r.raise_for_status()
    return (r.json().get("transcript") or "").strip()


async def _stt_gemini(audio_b64: str, lang: str) -> str:
    from . import brain
    want = "Kannada script" if lang == "kn" else "English"
    body = {"contents": [{"role": "user", "parts": [
                {"text": f"Transcribe this speech exactly, in {want}. Return only the words spoken, nothing else. "
                         "If there is no speech, return an empty string."},
                {"inlineData": {"mimeType": "audio/wav", "data": audio_b64}}]}],
            "generationConfig": {"temperature": 0, "thinkingConfig": {"thinkingLevel": "low"}}}
    j = await brain.gemini_generate(body, models=config.GEMINI_STT_CHAIN)
    text = brain.gemini_text(j).strip().strip('"').strip()
    # guardrail 7 (same as the Sakala POC): noise or a non-speech clip must not become a request
    if len(re.findall(r"[A-Za-zಀ-೿]", text)) < 4 or re.fullmatch(r"[\W\d_]+", text or "x"):
        return ""
    return text


def _gemini_text(j: dict) -> str:
    if isinstance(j.get("output_text"), str):
        return j["output_text"]
    out = []
    for step in j.get("steps", []) or j.get("output", []) or []:
        for c in step.get("content", []) if isinstance(step, dict) else []:
            if c.get("type") == "text" and c.get("text"):
                out.append(c["text"])
    return "\n".join(out)


# ---------------------------------------------------------------------------- TTS
async def tts(text: str, lang: str = "en") -> tuple[bytes | None, str]:
    """Returns (wav_bytes, provider). None bytes with provider 'browser' means: speak client-side."""
    text = clean_for_speech(text)
    if not text:
        return None, "browser"
    prov = pick_tts(lang)
    order = [prov] + [p for p in ("gemini",) if p != prov]
    from . import brain
    for p in order:
        if not brain.up(p):
            continue
        try:
            if p == "sarvam" and config.SARVAM_API_KEY:
                return await _tts_sarvam(text, lang), "sarvam"
            if p == "gemini" and config.GEMINI_API_KEY:
                return await _tts_gemini(text, lang), "gemini"
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            brain.mark_down(p)
            continue
        except Exception as e:
            print(f"[tts] {p} failed: {type(e).__name__}: {str(e)[:160]}", flush=True)
            continue
    return None, "browser"


async def _tts_sarvam(text: str, lang: str) -> bytes:
    body = {"text": text[:2400], "language_code": "kn-IN" if lang == "kn" else "en-IN",
            "model": config.SARVAM_TTS_MODEL,
            "speaker": config.SARVAM_VOICE_KN if lang == "kn" else config.SARVAM_VOICE_EN,
            "pace": 1.0, "speech_sample_rate": 24000, "output_audio_codec": "wav"}
    r = await http().post(f"{config.SARVAM_BASE}/text-to-speech", json=body,
                          headers={"api-subscription-key": config.SARVAM_API_KEY})
    r.raise_for_status()
    audios = r.json().get("audios") or []
    return b"".join(base64.b64decode(a) for a in audios)


async def _tts_gemini(text: str, lang: str) -> bytes:
    from . import brain
    # Only the words to be spoken go to the voice model: any style instruction in the text gets read aloud.
    body = {"contents": [{"role": "user", "parts": [{"text": text[:3000]}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": config.GEMINI_VOICE}}}}}
    j = await brain.gemini_generate(body, models=config.GEMINI_TTS_CHAIN, timeout=40.0)
    parts = ((j.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    inline = next((p["inlineData"] for p in parts if p.get("inlineData")), None)
    if not inline:
        return b""
    raw = base64.b64decode(inline["data"])
    if raw[:4] == b"RIFF":
        return raw
    rate = 24000
    m = re.search(r"rate=(\d+)", inline.get("mimeType", ""))
    if m:
        rate = int(m.group(1))
    return pcm_to_wav(raw, rate)


def pcm_to_wav(pcm: bytes, rate: int = 24000) -> bytes:
    import struct
    return (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", len(pcm)) + pcm)


TAG_RX = re.compile(r"<[^>]+>")
EMOJI_RX = re.compile("[\U0001F300-\U0001FAFF☀-➿⬀-⯿️]")


def clean_for_speech(html: str) -> str:
    """HTML from the Sakala chat engine -> plain spoken text."""
    t = TAG_RX.sub(" ", (html or "").replace("<br>", ". ").replace("<br/>", ". "))
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    t = EMOJI_RX.sub("", t)
    t = t.replace("·", ",").replace("→", " to ").replace("→", " to ").replace("…", "...")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s([,.;:!?])", r"\1", t)
    return t
