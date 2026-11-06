"""Mitra settings.

Reads mitra/.env first, then the Sakala app's .env (read-only) for the H200 gateway, so the
Mitra works today on the gateway and switches to Gemini / Sarvam the moment keys are added.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

MITRA = Path(__file__).resolve().parents[1]            # D:\Sakala POC\mitra
PROJECT = MITRA.parent                                  # D:\Sakala POC
SAKALA_APP = PROJECT / "app"                             # the existing POC (never modified)
WEB = MITRA / "web"
DATA = MITRA / "data"
DB_PATH = DATA / "mitra.db"

SAKALA_URL = os.environ.get("SAKALA_URL", "http://127.0.0.1:8020")
if "://" not in SAKALA_URL:                    # Render gives "host:port" for a service on its private network
    SAKALA_URL = "http://" + SAKALA_URL
SAKALA_LOCAL = any(h in SAKALA_URL for h in ("127.0.0.1", "localhost"))   # only then may Mitra start the POC itself
if os.environ.get("MITRA_START_POC", "").lower() in ("0", "false", "no"):    # a server runs the POC as its own service
    SAKALA_LOCAL = False
# the browser opens the live voice / event stream here when the pages are served from elsewhere (Vercel); empty = same host
PUBLIC_BACKEND = os.environ.get("MITRA_PUBLIC_BACKEND", "").rstrip("/")
CORS_ORIGINS = [o.strip() for o in os.environ.get("MITRA_CORS_ORIGINS", "").split(",") if o.strip()]
PORT = int(os.environ.get("MITRA_PORT", "8030"))


def _read_env(path: Path) -> dict:
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
        if not m:
            continue
        v = re.sub(r"\s+#.*$", "", m.group(2)).strip().strip('"').strip("'")
        out[m.group(1)] = v
    return out


_sakala_env = _read_env(SAKALA_APP / ".env")
_mitra_env = _read_env(MITRA / ".env")


def get(key: str, default: str = "") -> str:
    """mitra/.env > process env > app/.env > default."""
    if key in _mitra_env and _mitra_env[key] != "":
        return _mitra_env[key]
    if key in os.environ and os.environ[key] != "":
        return os.environ[key]
    return _sakala_env.get(key, default) or default


# Provider keys (bought later; everything degrades gracefully without them)
GEMINI_API_KEY = get("GEMINI_API_KEY")
GEMINI_BASE = get("GEMINI_BASE", "https://generativelanguage.googleapis.com/v1beta")
GEMINI_BRAIN_MODEL = get("GEMINI_BRAIN_MODEL") or get("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_FALLBACK_MODEL = get("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")   # used when the main one returns 503 "high demand"
GEMINI_TTS_MODEL = get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
GEMINI_VOICE = get("GEMINI_VOICE", "Kore")
GEMINI_LIVE_MODEL = get("GEMINI_LIVE_MODEL", "gemini-3.8-live")            # real-time voice (WebSocket); next step


def _chain(*names: str) -> tuple[str, ...]:
    seen, out = set(), []
    for n in names:
        for m in (n or "").split(","):
            m = m.strip()
            if m and m not in seen:
                seen.add(m)
                out.append(m)
    return tuple(out)


# Every Gemini model has its own daily quota on the free tier, so each job rotates through a chain and skips a
# model for a while after a 429 (quota) or 503 (busy). When the whole chain is exhausted the H200 gateway answers.
GEMINI_BRAIN_CHAIN = _chain(get("GEMINI_BRAIN_CHAIN"), GEMINI_BRAIN_MODEL, GEMINI_FALLBACK_MODEL,
                            "gemini-3.5-flash-lite", "gemini-3.1-flash-lite")
GEMINI_STT_CHAIN = _chain(get("GEMINI_STT_CHAIN"), "gemini-3.1-flash-lite", "gemini-3.5-flash-lite", GEMINI_BRAIN_MODEL)
GEMINI_TTS_CHAIN = _chain(get("GEMINI_TTS_CHAIN"), GEMINI_TTS_MODEL, "gemini-3.8-flash-lite-tts", "gemini-3.1-flash-tts-preview")

SARVAM_API_KEY = get("SARVAM_API_KEY")
SARVAM_BASE = get("SARVAM_BASE", "https://api.sarvam.ai")
SARVAM_STT_MODEL = get("SARVAM_STT_MODEL", "saaras:v4")
SARVAM_TTS_MODEL = get("SARVAM_TTS_MODEL", "bulbul:v4-flash")
SARVAM_VOICE_KN = get("SARVAM_VOICE_KN", "chaitra_kn_conversation")
SARVAM_VOICE_EN = get("SARVAM_VOICE_EN", "shubh_enhi_ads")

# Every model call is Gemini (23 Oct 2026). "auto" = Gemini when the key is set, else the rules brain / the browser voice.
BRAIN = get("MITRA_BRAIN", "auto")          # gemini | rules
STT = get("MITRA_STT", "auto")              # gemini | browser
TTS = get("MITRA_TTS", "auto")              # gemini | browser

# Guardrail 5: debug / test pages and engine details only when MITRA_DEBUG=1 (test instances); never in the demo.
DEBUG = get("MITRA_DEBUG", "").lower() in ("1", "true", "yes")
# Guardrail 8: conversation turns are kept this many days, then deleted ("forget this conversation" deletes at once).
RETAIN_DAYS = int(get("MITRA_RETAIN_DAYS", "7") or 7)

# The assistant's name and wake words ("Hey Mitra"). Change both here or in mitra/.env when it is renamed.
NAME = get("MITRA_NAME", "Mitra")
WAKE_WORDS = [w.strip().lower() for w in get("MITRA_WAKE_WORDS", NAME).split(",") if w.strip()]

PROFILES = {
    "citizen": {"title": "Citizen", "sub": "Sakala on WhatsApp"},
    "officer": {"title": "Officer", "sub": "Inbox and actions"},
    "cs": {"title": "Chief Secretary", "sub": "Command view"},
}
DEFAULT_OFFICER = "tah_piriyapatna"
