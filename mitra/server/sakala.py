"""Client for the existing Sakala POC API (port 8020). The POC is the system of record; the
Mitra never touches its database directly. Starts the POC server if it is not running."""
from __future__ import annotations

import asyncio
import subprocess
import sys
import time

import httpx

from . import config

_client: httpx.AsyncClient | None = None
_proc: subprocess.Popen | None = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=config.SAKALA_URL, timeout=httpx.Timeout(120.0, connect=3.0))
    return _client


async def health() -> dict | None:
    try:
        r = await client().get("/api/health")
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


async def ensure_running(wait: float = 60.0) -> bool:
    """Start the Sakala server if it is down (same command as app/run.bat)."""
    global _proc
    if await health():
        return True
    if not config.SAKALA_LOCAL:                       # a remote POC (Render): wait for it to wake, never start one here
        t0 = time.time()
        while time.time() - t0 < max(wait, 90):
            await asyncio.sleep(2.0)
            if await health():
                return True
        return False
    if _proc is None or _proc.poll() is not None:
        log = open(config.SAKALA_APP / "data" / "server.mitra.log", "ab")
        _proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server.api:app", "--port", "8020"],
            cwd=str(config.SAKALA_APP), stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    t0 = time.time()
    while time.time() - t0 < wait:
        await asyncio.sleep(1.0)
        if await health():
            return True
    return False


async def _get(path: str, **params):
    r = await client().get(path, params=params or None)
    r.raise_for_status()
    return r.json()


async def _post(path: str, body: dict):
    r = await client().post(path, json=body)
    try:
        data = r.json()
    except Exception:
        data = {}
    if r.status_code >= 400:
        data = {"http": r.status_code, "detail": data.get("detail") if isinstance(data, dict) else str(data)}
    return data


async def bootstrap():
    return await _get("/api/bootstrap")


async def state(session: str = "", scope: str = "all", **filters):
    """filters: owner, district, light (bool), id (comma-separated)."""
    params = {"session": session, "scope": scope}
    for k, v in filters.items():
        if v not in (None, "", False):
            params[k] = "true" if v is True else v
    return await _get("/api/state", **params)


async def case(cid: str):
    return await _get(f"/api/case/{cid}")


async def chat(session: str, **payload):
    return await _post("/api/chat", {"session": session, **payload})


async def action(cid: str, **payload):
    return await _post(f"/api/cases/{cid}/action", payload)


async def draft_atr(cid: str):
    return await _post(f"/api/cases/{cid}/draft_atr", {})


async def ask(q: str):
    return await _post("/api/ask", {"q": q})


async def tick(days: int):
    return await _post("/api/clock/tick", {"days": days})


async def reset():
    return await _post("/api/reset", {})


async def transcribe(audio_b64: str, lang: str = "en"):
    return await _post("/api/transcribe", {"audio_b64": audio_b64, "lang": lang})


async def review_pack(level: str = "cs", officer_id: str = ""):
    return await _get("/api/review_pack", level=level, officer_id=officer_id)


async def e4():
    return await _get("/api/e4")


async def tracker():
    return await _get("/api/sakala/tracker")


async def early_warning():
    return await _get("/api/sakala/early_warning")


async def insights(kind: str, **params):
    return await _get(f"/api/insights/{kind}", **params)
