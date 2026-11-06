"""Probe every AI engine named in app/.env and report what works. Never prints keys or base URLs."""
import base64
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mitra"))
from server import config  # noqa: E402  (reads mitra/.env then app/.env)

WAV = (Path(__file__).resolve().parent / "tests" / "asr_test.wav").read_bytes()
G = config.GEMINI_BASE
K = config.GEMINI_API_KEY
c = httpx.Client(timeout=httpx.Timeout(40, connect=5), verify=False)
out = []


def rec(name, ok, detail=""):
    out.append((name, ok, detail))
    print(("  OK   " if ok else "  FAIL ") + name + (f"  ·  {detail}" if detail else ""), flush=True)


def t(fn):
    t0 = time.time()
    try:
        d = fn()
        return True, f"{time.time() - t0:.2f}s" + (f" · {d}" if d else "")
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:160]}"


print("[H200 gateway]")
def qwen_chat():
    r = c.post(f"{config.QWEN_BASE}/chat/completions", headers={"Authorization": f"Bearer {config.QWEN_KEY}"},
               json={"model": config.QWEN_MODEL, "messages": [{"role": "user", "content": "Say OK"}], "max_tokens": 5,
                     "chat_template_kwargs": {"enable_thinking": False}})
    r.raise_for_status(); return r.json()["choices"][0]["message"]["content"][:20]
rec(f"LLM {config.QWEN_MODEL}", *t(qwen_chat))

def qwen_asr():
    r = c.post(f"{config.get('ASR_BASE_URL')}/audio/transcriptions", headers={"Authorization": f"Bearer {config.get('ASR_API_KEY')}"},
               files={"file": ("a.wav", WAV, "audio/wav")}, data={"model": config.get("ASR_MODEL", "qwen3-asr"), "language": "en"})
    r.raise_for_status(); return repr(r.json().get("text", "")[:40])
rec("ASR qwen3-asr", *t(qwen_asr))

def qwen_tts():
    r = c.post(f"{config.QWEN_TTS_BASE}/audio/speech", headers={"Authorization": f"Bearer {config.QWEN_TTS_KEY}"},
               json={"model": config.QWEN_TTS_MODEL, "input": "Hello from Sakala.", "voice": config.QWEN_TTS_VOICE, "response_format": "wav"})
    r.raise_for_status(); return f"{len(r.content)} bytes {r.headers.get('content-type')}"
rec("TTS qwen3-tts", *t(qwen_tts))

print("[Gemini]")
if not K:
    rec("GEMINI_API_KEY present", False, "missing")
else:
    rec("GEMINI_API_KEY present", True)
    models = []
    def list_models():
        r = c.get(f"{G}/models", headers={"x-goog-api-key": K}, params={"pageSize": 200})
        r.raise_for_status()
        models.extend(m["name"].split("/")[-1] for m in r.json().get("models", []))
        return f"{len(models)} models"
    rec("list models", *t(list_models))
    interesting = [m for m in models if any(s in m for s in ("3.8", "3.5", "live", "tts", "transcribe", "flash"))]
    print("     available (subset):", ", ".join(sorted(interesting)[:40]))

    def gen(model):
        def f():
            r = c.post(f"{G}/models/{model}:generateContent", headers={"x-goog-api-key": K},
                       json={"contents": [{"parts": [{"text": "Reply with exactly: OK"}]}]})
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code} {r.text[:120]}")
            return repr(r.json()["candidates"][0]["content"]["parts"][0]["text"][:20])
        return f
    for m in (config.get("GEMINI_MODEL", "gemini-3.5-flash-lite"), "gemini-3.8-flash"):
        rec(f"generateContent {m}", *t(gen(m)))

    def interactions(model):
        def f():
            r = c.post(f"{G}/interactions", headers={"x-goog-api-key": K},
                       json={"model": model, "input": "Reply with exactly: OK"})
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code} {r.text[:140]}")
            j = r.json()
            return "keys=" + ",".join(list(j.keys())[:8])
        return f
    rec("Interactions API gemini-3.8-flash", *t(interactions("gemini-3.8-flash")))

    def tts_gc(model):
        def f():
            r = c.post(f"{G}/models/{model}:generateContent", headers={"x-goog-api-key": K},
                       json={"contents": [{"parts": [{"text": "Namaskara. I am Mitra, the voice of Sakala."}]}],
                             "generationConfig": {"responseModalities": ["AUDIO"],
                                                  "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Kore"}}}}})
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code} {r.text[:140]}")
            p = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
            return f"{len(base64.b64decode(p['data']))} bytes {p.get('mimeType')}"
        return f
    for m in ("gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"):
        rec(f"TTS generateContent {m}", *t(tts_gc(m)))

    def stt_gc():
        r = c.post(f"{G}/models/{config.get('GEMINI_MODEL', 'gemini-3.5-flash-lite')}:generateContent", headers={"x-goog-api-key": K},
                   json={"contents": [{"parts": [{"text": "Transcribe this speech exactly. Return only the words."},
                                                 {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(WAV).decode()}}]}]})
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code} {r.text[:140]}")
        return repr(r.json()["candidates"][0]["content"]["parts"][0]["text"][:60])
    rec("STT via generateContent (audio in)", *t(stt_gc))

print("[Sarvam]")
rec("SARVAM_API_KEY present", bool(config.SARVAM_API_KEY), "" if config.SARVAM_API_KEY else "not in any env file")
Path(__file__).with_name("probe_result.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
