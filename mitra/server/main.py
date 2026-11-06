"""Mitra: one voice agent for the Citizen, the Officer and the Chief Secretary.

Runs beside the Sakala POC (port 8020) on port 8030. Start with mitra/run.bat."""
from __future__ import annotations

import asyncio
import base64
import difflib
import json
import os
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import brain, config, guard, notify, sakala, speech, store, tools
from .sync import broker, poller, sse

KN_RX = re.compile("[ಀ-೿]")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.conn()
    ok = await sakala.ensure_running()
    if ok:
        try:
            await tools.boot()
        except Exception:
            pass
    # a second (test) instance must not tail the change feed too, or every notification would be logged twice
    task = None if os.environ.get("MITRA_NO_SYNC") else asyncio.create_task(poller())
    keeper = asyncio.create_task(_retention())
    yield
    keeper.cancel()
    if task:
        task.cancel()


async def _retention():
    """Guardrail 8: old conversation turns are deleted on start-up and every hour."""
    while True:
        try:
            store.purge_turns(config.RETAIN_DAYS)
        except Exception:
            pass
        await asyncio.sleep(3600)


app = FastAPI(title="Mitra", lifespan=lifespan)
if config.CORS_ORIGINS:                          # pages on Vercel open the event stream on this host directly
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"])
app.mount("/assets", StaticFiles(directory=str(config.WEB / "assets")), name="assets")


@app.middleware("http")
async def headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["x-content-type-options"] = "nosniff"
    resp.headers["referrer-policy"] = "no-referrer"
    resp.headers["permissions-policy"] = "camera=(), microphone=(self), geolocation=()"
    path = request.url.path
    if path == "/" or path.endswith((".js", ".css", ".html")):          # the page and its scripts: always revalidated, never a stale splash.js on new markup
        resp.headers["cache-control"] = "no-cache"
    return resp


@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(config.WEB / "index.html")


@app.get("/mitra.css")
async def css():
    return FileResponse(config.WEB / "mitra.css", media_type="text/css")


@app.get("/mitra.js")
async def js():
    return FileResponse(config.WEB / "mitra.js", media_type="application/javascript")


@app.get("/orb.js")
async def orbjs():
    return FileResponse(config.WEB / "orb.js", media_type="application/javascript")


@app.get("/config.js")
async def configjs():
    """Where the browser opens the live voice and the event stream (empty = this host). On Vercel a static config.js is built instead."""
    return Response(f"window.MITRA_BACKEND={json.dumps(config.PUBLIC_BACKEND)};", media_type="application/javascript",
                    headers={"Cache-Control": "no-store"})


@app.get("/app.js")
async def appjs():
    return FileResponse(config.WEB / "app.js", media_type="application/javascript")


@app.get("/phone.js")
async def phonejs():
    return FileResponse(config.WEB / "phone.js", media_type="application/javascript")


@app.get("/splash.js")
async def splashjs():
    return FileResponse(config.WEB / "splash.js", media_type="application/javascript")


@app.get("/portal.js")
async def portaljs():
    return FileResponse(config.WEB / "portal.js", media_type="application/javascript")


@app.get("/stage.js")
async def stagejs():
    return FileResponse(config.WEB / "stage.js", media_type="application/javascript")


@app.get("/shot.html", response_class=HTMLResponse)
async def shot_page():
    p = config.WEB / "shot.html"
    if not config.DEBUG or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/dbg.html", response_class=HTMLResponse)
async def dbg_page():
    """Served only while tests/dbg_ui.py has written it (the file is deleted after each run)."""
    p = config.WEB / "dbg.html"
    if not config.DEBUG or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket, session: str = "", text: int = 0):
    """Full-duplex voice (English): browser <-> Gemini Live relay. Kannada and any failure use the cascade."""
    from . import live
    await live.handle(ws, session, bool(text))


@app.get("/api/deviations")
async def deviations_log(limit: int = 50):
    """Guardrails 21-22: numbers / case ids Mitra spoke without a source (debug instance only)."""
    if not config.DEBUG:
        raise HTTPException(404)
    return {"deviations": store.deviations(limit)}


@app.get("/api/live_stats")
async def live_stats():
    if not config.DEBUG:
        raise HTTPException(404)
    from . import live
    return live.STATS


@app.get("/api/notifs")
async def notifs(session: str, justin: int = 1):
    """What this screen missed (pending, oldest first), its recent history for the bell, and, for an officer,
    the "Just in" shelf: arrivals in the last hour that are still open with them."""
    s = store.get_session(session)
    if not s:
        raise HTTPException(404, "unknown session")
    out = {"pending": notify.pending(s), "history": notify.history(s), "viewer": notify.viewer(s), "just_in": []}
    if justin and s["profile"] == "officer":
        rows = notify.just_in_rows(s["officer"])
        if rows:
            # still with this officer and still open (a case may have moved on since it arrived)
            got = await asyncio.gather(*[sakala.case(r["case_id"]) for r in rows], return_exceptions=True)
            keep = []
            for r, c in zip(rows, got):
                if not isinstance(c, dict):
                    continue
                c = c.get("case", c)
                if c.get("owner") == s["officer"] and c.get("status") not in ("Resolved", "Rejected", "Closed"):
                    r["level"], r["left"], r["leftText"] = c.get("level"), c.get("left"), c.get("leftText")
                    keep.append(r)
            out["just_in"] = keep
    return out


class SeenReq(BaseModel):
    session: str
    upto: int | None = None


@app.post("/api/notifs/seen")
async def notifs_seen(req: SeenReq):
    s = store.get_session(req.session)
    if not s:
        raise HTTPException(404, "unknown session")
    notify.mark_seen(s, req.upto)
    return {"ok": True}


@app.get("/api/tracker")
async def tracker_proxy():
    """Sakala 2025 district tracker from the POC (real report data) for the Chief Secretary's pulse strip."""
    try:
        return await sakala.tracker()
    except Exception as e:  # the POC is down: the strip simply does not render
        raise HTTPException(503, str(e))


@app.get("/api/health")
async def health():
    cooling = {k: round(v - time.time()) for k, v in brain._down.items() if v > time.time()}
    out = {"ok": True, "sakala": bool(await sakala.health())}
    if config.DEBUG:                                  # engine details only on a debug (test) instance
        out.update({"providers": speech.providers(), "brain": brain.pick(), "engine_recent": brain.GEMINI_LOG[-8:], "cooling_down_s": cooling})
    return out


@app.get("/api/boot")
async def boot():
    sak = await sakala.ensure_running()
    b = await tools.boot() if sak else {}
    p = speech.providers()
    pub = {"server_stt": bool(p.get("gemini") or p.get("sarvam")), "stt": guard.public_engine(p.get("stt")),
           "stt_kn": guard.public_engine(p.get("stt_kn")), "tts": guard.public_engine(p.get("tts")), "tts_kn": guard.public_engine(p.get("tts_kn"))}
    return {"sakala": sak, "providers": pub, "brain": guard.public_engine(brain.pick()), "name": config.NAME, "wake": config.WAKE_WORDS, "learned": learned_variants(),
            "profiles": config.PROFILES, "officers": b.get("officers", {}), "now": b.get("now"),
            "evals": guard.strip_engines(b.get("evals")), "defaultOfficer": config.DEFAULT_OFFICER}


class SessionReq(BaseModel):
    profile: str = "citizen"
    officer: str = config.DEFAULT_OFFICER
    lang: str = "en"
    session: str = ""


@app.post("/api/session")
async def session(req: SessionReq):
    await tools.boot()
    s = store.get_session(req.session) if req.session else None
    if not s:
        s = store.new_session(req.profile, req.officer, req.lang)
    changed = s["profile"] != req.profile or s["officer"] != req.officer or s["lang"] != req.lang
    s["profile"], s["officer"], s["lang"] = req.profile, req.officer, req.lang
    if changed:
        s["state"]["case_id"] = None
    store.save_session(s)
    ui = await tools._profile_ui(s)
    store.save_session(s)
    return {"session": s["id"], "profile": s["profile"], "officer": s["officer"], "officerName": tools.off_name(s["officer"], False),
            "lang": s["lang"], "ui": ui}


def build_ctx(s: dict) -> dict:
    st = s.get("state") or {}
    ctx = {"profile": s["profile"], "lang": s["lang"], "history": store.history(s["id"], 6), "context": {},
           "options": st.get("options") or [], "offer_open": st.get("offer_open")}
    c = ctx["context"]
    c["language"] = "Kannada" if s["lang"] == "kn" else "English"
    pend = st.get("pending_action")
    if pend and time.time() - pend.get("t", 0) < 120:
        ctx["pending"] = pend["intent"]
        c["pending_action"] = f"Mitra asked: {pend.get('question', '')} A yes is confirm_action, a no is cancel_action."
    if st.get("scope"):
        c["scope"] = st["scope"]                     # the department / place the Chief Secretary is looking at: follow-ups stay inside it
    if st.get("kb_last"):
        c["kb_last"] = st["kb_last"]                 # the last knowledge topic answered: a follow-up stays on it
    if s["profile"] == "citizen":
        c["chat_flow"] = st.get("flow") or st.get("chat_flow") or "menu"
        if st.get("reply_case"):
            c["reply_case"] = st["reply_case"]
        if st.get("draft", {}).get("service"):
            c["draft"] = f"{st['draft'].get('service')} ({st['draft'].get('conf')}%)"
        opts = st.get("options") or []
        if opts:
            c["options"] = ", ".join(lab for lab, _ in opts[:12])
        if st.get("awaiting_feedback"):
            c["awaiting_feedback"] = f"Mitra asked whether {st['awaiting_feedback']} was solved; yes/no is feedback"
        if st.get("case_id"):
            c["last_case"] = st["case_id"]
    else:
        c["officer"] = tools.off_name(s["officer"], False)
        if st.get("case_id"):
            c["open_case"] = st["case_id"]
        if st.get("list"):
            c["list"] = ", ".join(st["list"][:8])
        if st.get("offer_open"):
            c["offered"] = f"Mitra just offered to open {st['offer_open']}; a yes means open it"
    ctx["context"] = c
    return ctx


class TurnReq(BaseModel):
    session: str
    text: str = ""
    audio_b64: str = ""
    lang: str = ""
    want_audio: bool = True
    wake_only: bool = False      # hands-free scan: act only if the clip starts with the wake word, else ignore
    detect_only: bool = False    # with wake_only: just report the wake (and any command said with it); the live session acts


# how speech models tend to hear "Mitra" (the configured wake words are added at runtime)
WAKE_LIKE = r"mitra+h?|mithra+h?|mitrah|meetra+|mytra|mithraa?|mitr|mi\s*tra|mee\s*tra|me\s*tra|mithura|nitra|mitre|mittra|mitthra"
LEARNED = config.DATA / "wake_variants.json"      # spellings learned from the user's own voice ("teach Mitra your name")


def learned_variants() -> list[str]:
    try:
        return [v for v in json.loads(LEARNED.read_text(encoding="utf-8")) if isinstance(v, str) and v]
    except Exception:
        return []


def wake_rx() -> re.Pattern:
    wake = "|".join([re.escape(w) for w in config.WAKE_WORDS + learned_variants()] + [WAKE_LIKE])
    return re.compile(rf"^\W*(?:(?:hey|hi|hello|ok|okay|o\.k\.|a|hay|hei)\W+)?(?:{wake})\b\W*", re.I)


# Kannada: Gemini writes the name in Kannada script (ಹೇ ಮಿತ್ರ) when the screen is in Kannada, even if it was said
# the English way. Kannada vowel signs are not "word" characters for \b / \W, so separators are spelled out.
_KN_SEP = r"[\s,.!?।]"
KN_WAKE = re.compile(rf"^{_KN_SEP}*(?:(?:ಹೇ|ಹೆ|ಹಾಯ್|ಹಲೋ|ಓಕೆ|ಏ|hey|hi|ok|okay){_KN_SEP}+)?(?:ಮಿತ್ರ(?:ಾ|ರೇ|ರೆ|ನೇ)?|ಮೀತ್ರ|ಮಿತ್ರಾ)(?={_KN_SEP}|$){_KN_SEP}*", re.I)


def strip_wake(text: str) -> str:
    """The request without its wake phrase; unchanged if it did not start with one (Latin or Kannada script)."""
    out = wake_rx().sub("", text, count=1)
    if out == text:
        out = KN_WAKE.sub("", text, count=1)
    return out.strip() if out != text else text


class LearnReq(BaseModel):
    audio_b64: str
    lang: str = "en"


_STOP = {"the", "this", "that", "meter", "metro", "mister", "miss", "matter", "mother", "my", "me", "media", "mantra", "metre", "mitral"}


@app.post("/api/wake_learn")
async def wake_learn(req: LearnReq):
    """One-off 'training': the user says the name a few times; whatever the speech model writes for it becomes an
    accepted wake spelling (if it is close enough to the name and not an ordinary word)."""
    heard, prov = await speech.stt(req.audio_b64, req.lang)
    text = (heard or "").strip()
    if not text:
        return {"heard": "", "learned": False, "matched": False, "reason": "nothing heard"}
    if strip_wake(text) != text:
        return {"heard": text, "learned": False, "matched": True}
    words = re.findall(r"[a-z]+", re.sub(r"^\W*(?:hey|hi|hello|ok|okay)\W+", "", text.lower(), count=1))
    cand = " ".join(words[:2]) if words and len(words[0]) <= 3 and len(words) > 1 else (words[0] if words else "")
    name = config.NAME.lower()
    sim = difflib.SequenceMatcher(None, cand.replace(" ", ""), name).ratio() if cand else 0
    if not cand or cand in _STOP or len(cand) < 3 or len(cand) > 12 or sim < 0.5:
        return {"heard": text, "learned": False, "matched": False, "reason": f"'{cand or text}' is too far from {config.NAME}", "sim": round(sim, 2)}
    cur = learned_variants()
    if cand not in cur:
        cur.append(cand)
        LEARNED.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"heard": text, "learned": True, "matched": False, "variant": cand, "sim": round(sim, 2), "all": cur}


@app.post("/api/turn")
async def turn(req: TurnReq):
    s = store.get_session(req.session)
    if not s:
        raise HTTPException(404, "unknown session")
    if req.lang in ("en", "kn") and req.lang != s["lang"]:
        s["lang"] = req.lang
        store.save_session(s)
    t0 = time.time()
    heard, stt_prov = req.text.strip(), "text"
    if not heard and req.audio_b64:
        heard, stt_prov = await speech.stt(req.audio_b64, s["lang"])
        s["state"]["last_audio"] = req.audio_b64[:4_000_000]
        store.save_session(s)
    if s["lang"] == "en" and heard and brain.kn_share(heard) >= 0.5 and not brain.lang_asked(heard):
        s["lang"] = "kn"                                  # spoken to in Kannada: Kannada from here (this reply is translated below)
        store.save_session(s)
    # drop the wake phrase ("hey Mitra, ...") so only the request reaches the brain and the chat
    stripped = strip_wake(heard)
    if req.wake_only and (not heard or stripped == heard):
        # room talk that did not start with the wake word: never acted on, never logged
        return {"heard": heard, "say": "", "intent": "ignored", "ui": [], "stt": guard.public_engine(stt_prov), "tts": "browser", "lang": s["lang"], "parts": [],
                "timing": {"stt": round(time.time() - t0, 2), "total": round(time.time() - t0, 2)}}
    if req.wake_only and req.detect_only and stripped != heard:
        return {"heard": heard, "command": stripped, "say": "", "intent": "wake", "ui": [], "stt": guard.public_engine(stt_prov), "tts": "browser",
                "lang": s["lang"], "parts": []}
    if stripped != heard:
        heard = stripped
        if not heard:
            return {"heard": "", "say": "Yes?", "intent": "wake", "ui": [], "stt": guard.public_engine(stt_prov), "tts": "browser", "lang": s["lang"], "parts": []}
    if not heard:
        say = "I could not hear that clearly. Please say it again." if s["lang"] != "kn" else "ಸರಿಯಾಗಿ ಕೇಳಿಸಲಿಲ್ಲ, ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ."
        return {"heard": "", "say": say, "intent": "none", "ui": [], "stt": guard.public_engine(stt_prov), "tts": "browser", "lang": s["lang"]}
    t_stt = time.time() - t0
    ctx = build_ctx(s)
    dec = await brain.decide(ctx, heard)
    t_brain = time.time() - t0 - t_stt
    store.log_turn(s["id"], "user", heard, dec["intent"], {"args": dec["args"], "provider": dec["provider"]})
    s = store.get_session(s["id"])
    # a yes right after "shall I open it?"
    if s["profile"] == "officer" and dec["intent"] in ("smalltalk", "confirm", "help", "confirm_action") and s["state"].get("offer_open") and not s["state"].get("pending_action") and brain.YES.search(heard.lower()):
        dec = {"intent": "open_case", "args": {"case_id": s["state"]["offer_open"]}, "provider": dec["provider"]}
    dec["args"]["_text"] = heard                     # the exact words, for tools that may need to fall back to them
    res = await tools.execute(s, dec["intent"], dec["args"])
    say, kn_parts = await kn_say(s, guard.scrub(res.get("say") or ""))
    audio_b64, tts_prov, tid, parts = "", "browser", "", []
    t_act = time.time() - t0
    if say and req.want_audio:
        # sentence-by-sentence: synthesise every chunk in parallel, answer with the first one, the client
        # fetches the rest (already in flight) while the first plays
        parts = kn_parts or split_chunks(say)
        tasks = [asyncio.create_task(speech.tts(p, s["lang"])) for p in parts]
        tid = uuid.uuid4().hex[:10]
        TTS_JOBS[tid] = (time.time(), tasks)
        _gc_jobs()
        wav, tts_prov = await tasks[0]
        if wav:
            audio_b64 = base64.b64encode(wav).decode()
    store.log_turn(s["id"], "mitra", say, dec["intent"])
    if dec["intent"] == "forget_conversation":
        store.forget(s["id"])
    return {"heard": heard, "intent": res.get("intent") or dec["intent"], "args": {k: v for k, v in dec["args"].items() if not k.startswith("_")},
            "say": say, "audio_b64": audio_b64, "stt": guard.public_engine(stt_prov), "tts": guard.public_engine(tts_prov), "ui": res.get("ui", []),
            "tts_id": tid, "parts": parts, "lang": s["lang"], "profile": s["profile"], "officer": s["officer"],
            "timing": {"stt": round(t_stt, 2), "brain": round(t_brain, 2), "act": round(t_act - t_stt - t_brain, 2),
                       "first_audio": round(time.time() - t0 - t_act, 2), "total": round(time.time() - t0, 2)}}


TTS_JOBS: dict[str, tuple[float, list]] = {}
_SENT = re.compile(r"(?<=[.!?।])\s+")


def split_chunks(text: str, first_max: int = 140, max_len: int = 260) -> list[str]:
    """Short first chunk (fast first audio), then sentence groups up to max_len characters."""
    sents = [x.strip() for x in _SENT.split(text.strip()) if x.strip()]
    out: list[str] = []
    for snt in sents:
        limit = first_max if not out else max_len
        if out and len(out[-1]) + 1 + len(snt) <= limit and (len(out) > 1 or len(out[-1]) < 25):
            out[-1] += " " + snt
        else:
            out.append(snt)
    return out or [text]


def _gc_jobs():
    now = time.time()
    for k in [k for k, (t, _) in TTS_JOBS.items() if now - t > 300]:
        for task in TTS_JOBS[k][1]:
            task.cancel()
        TTS_JOBS.pop(k, None)


@app.get("/api/tts_part")
async def tts_part(tid: str, i: int):
    job = TTS_JOBS.get(tid)
    if not job or i < 0 or i >= len(job[1]):
        raise HTTPException(404, "unknown chunk")
    wav, prov = await job[1][i]
    return {"audio_b64": base64.b64encode(wav).decode() if wav else "", "tts": guard.public_engine(prov)}


async def kn_say(s: dict, say: str) -> tuple[str, list[str] | None]:
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


async def translate_kn_parts(say: str) -> list[str]:
    """Kannada reply, fast to first word: the first sentence is translated on its own and in parallel with the rest, so its
    (short) voice clip can start while the rest is still being prepared."""
    sents = [x.strip() for x in _SENT.split(say.strip()) if x.strip()]
    if not sents:
        return []
    first, rest = sents[0], " ".join(sents[1:])
    src = [first] + ([rest] if rest else [])
    out = await asyncio.gather(*[translate_kn(x) for x in src])
    out = [o or e for o, e in zip(out, src)]
    lead, tail = _lead(out[0])
    rest = " ".join(x for x in (tail, out[1] if len(out) > 1 else "") if x)
    # two voice clips per reply at most: the TTS quota is ~10 requests a minute on this key
    return [lead] + ([rest] if rest else [])


def _lead(text: str, cap: int = 60) -> tuple[str, str]:
    """A short opening phrase (its voice clip is ready in ~2 s) and the rest, split at a comma or a word boundary."""
    if len(text) <= cap + 15:
        return text, ""
    m = None
    for m in re.finditer(r"[,،।:;]\s", text[: cap + 25]):
        pass
    cut = m.end() if m and m.end() >= 18 else (text.rfind(" ", 0, cap) + 1 or cap)
    return text[:cut].strip(), text[cut:].strip()


async def translate_kn(text: str) -> str:
    if config.GEMINI_API_KEY:
        try:
            body = {"systemInstruction": {"parts": [{"text": KN_PROMPT}]},
                    "contents": [{"role": "user", "parts": [{"text": text[:1200]}]}],
                    "generationConfig": {"temperature": 0.1, "thinkingConfig": {"thinkingLevel": "low"}}}
            out = brain.gemini_text(await brain.gemini_generate(body)).strip()
            if KN_RX.search(out):
                return out
        except Exception:
            pass
    return ""                                       # Gemini only: no second translation engine


class TtsReq(BaseModel):
    text: str
    lang: str = "en"


@app.post("/api/tts")
async def tts_ep(req: TtsReq):
    wav, prov = await speech.tts(guard.scrub(req.text), req.lang)
    return {"audio_b64": base64.b64encode(wav).decode() if wav else "", "tts": guard.public_engine(prov)}


class ClipReq(BaseModel):
    session: str
    to_role: str
    case_id: str = ""
    officer: str = ""
    audio_b64: str = ""
    transcript: str = ""


@app.post("/api/clip")
async def clip(req: ClipReq):
    s = store.get_session(req.session)
    if not s:
        raise HTTPException(404, "unknown session")
    text = req.transcript.strip()
    if not text and req.audio_b64:
        text, _ = await speech.stt(req.audio_b64, s["lang"])
    if not text:
        return {"ok": False, "say": "I could not hear the note. Please record it again."}
    s["state"]["last_audio"] = req.audio_b64[:4_000_000]
    if req.case_id:
        s["state"]["case_id"] = req.case_id
    store.save_session(s)
    intent = {"officer": "voice_note_officer" if s["profile"] == "citizen" else "voice_note_officer_cs",
              "cs": "voice_note_cs", "citizen": "voice_note_citizen"}.get(req.to_role, "voice_note_officer")
    res = await tools.execute(s, intent, {"text": text, "officer": req.officer, "case_id": req.case_id})
    return {"ok": True, "transcript": text, "say": res.get("say"), "ui": res.get("ui", [])}


@app.get("/api/notes")
async def notes(session: str):
    s = store.get_session(session)
    if not s:
        raise HTTPException(404, "unknown session")
    return {"notes": store.notes_for(s["profile"], s["officer"], s["chat_session"])}


@app.get("/api/note/{nid}/audio")
async def note_audio(nid: int):
    b64 = store.note_audio(nid)
    if not b64:
        raise HTTPException(404, "no audio")
    return Response(base64.b64decode(b64), media_type="audio/wav")


class PhotoReq(BaseModel):
    session: str
    image_b64: str
    media_type: str = "image/png"


class DocReq(BaseModel):
    session: str
    file_b64: str
    media_type: str = "application/pdf"
    filename: str = ""
    want_audio: bool = True       # False while the live voice is open: Mitra reads the reply through Live, no TTS spent


class DocSubmit(BaseModel):
    session: str
    fields: dict = {}
    want_audio: bool = True


@app.post("/api/document")
async def document(req: DocReq):
    """The document door: a written complaint (PDF / photo) read into the official form, then the usual pipeline."""
    s = store.get_session(req.session)
    if not s:
        raise HTTPException(404, "unknown session")
    await tools.boot()
    res = await tools.t_citizen_document(s, req.file_b64, req.media_type, req.filename)
    store.save_session(s)
    say = res.get("say") or ""
    store.log_turn(s["id"], "user", f"(document: {guard.mask(req.filename or 'file')})", "document")
    store.log_turn(s["id"], "mitra", guard.mask(say), "document")
    return await _with_voice(s, say, res.get("ui", []), intent="document", want_audio=req.want_audio)


@app.post("/api/document/submit")
async def document_submit(req: DocSubmit):
    """Submit the reviewed form (typed edits applied; NA / empty accepted), then the same create step as 'yes, file it'."""
    s = store.get_session(req.session)
    if not s:
        raise HTTPException(404, "unknown session")
    await tools.boot()
    st = s["state"]; d = st.get("draft") or {}
    if not d.get("doc"):
        raise HTTPException(409, "no document form is open")
    f = d["doc"].setdefault("fields", {})
    for k, v in (req.fields or {}).items():
        v = "" if tools.NA_RX.match(str(v or "")) else str(v or "").strip()
        f[k] = v
    # a changed place is resolved again through the shared completion step
    p = d.get("place") or {}
    want = (req.fields or {}).get("gp") or (req.fields or {}).get("village") or ""
    if d.get("scrutiny"):
        d["taluk_hint"] = (req.fields or {}).get("taluk") or d.get("taluk_hint") or ""
        want = ""
    if want and want.lower() not in ((p.get("gp") or "").lower(), (p.get("village") or "").lower()):
        r = await tools.intake(s, step="place", text=want, u=d.get("u") or {}, taluk=(req.fields or {}).get("taluk") or "")
        if r.get("place"):
            d["place"] = r["place"]; d["preview"] = r.get("preview"); d["duplicate"] = r.get("duplicate")
        elif r.get("need") == "gp":
            res = await tools._apply_place(s, r, [tools.stage(3, "Location changed on the form", "run")], "Which Gram Panchayat?")
            store.save_session(s)
            return await _with_voice(s, res.get("say") or "", res.get("ui", []), intent="document")
    if d.get("scrutiny"):
        st["flow"] = "scrutiny_confirm"
        res = await tools.execute(s, "confirm", {"_text": "submit", "_confirmed": True})
    elif not d.get("place"):
        res = {"say": "I still need the place: which village, Gram Panchayat or taluk is this in?", "ui": tools._draft_ui(s, [tools.stage(3, "Asking for the place", "run")])}
    else:
        st["flow"] = "confirm"
        res = await tools.execute(s, "confirm", {"_text": "submit", "_confirmed": True})
    store.save_session(s)
    say = res.get("say") or ""
    store.log_turn(s["id"], "user", "(form submitted)", "confirm")
    store.log_turn(s["id"], "mitra", guard.mask(say), res.get("intent", "confirm"))
    return await _with_voice(s, say, res.get("ui", []), intent=res.get("intent", "confirm"), want_audio=req.want_audio)


@app.post("/api/photo")
async def photo(req: PhotoReq):
    """A photo of a petition or document: read by the vision model and run through the pipeline."""
    s = store.get_session(req.session)
    if not s:
        raise HTTPException(404, "unknown session")
    await tools.boot()
    res = await tools.t_citizen_photo(s, req.image_b64, req.media_type)
    store.save_session(s)
    say = res.get("say") or ""
    store.log_turn(s["id"], "user", "(photo)", "photo")
    store.log_turn(s["id"], "mitra", guard.mask(say), "photo")
    return await _with_voice(s, say, res.get("ui", []), intent="photo")


class ForgetReq(BaseModel):
    session: str


@app.post("/api/forget")
async def forget(req: ForgetReq):
    """Guardrail 8: delete this screen's conversation (turns, last clip) on request."""
    s = store.get_session(req.session)
    if not s:
        raise HTTPException(404, "unknown session")
    return {"ok": True, "deleted": store.forget(s["id"])}


@app.get("/api/updates")
async def updates(session: str):
    """Officer -> citizen messages that this screen has not heard yet (called when the live feed says so)."""
    s = store.get_session(session)
    if not s:
        raise HTTPException(404, "unknown session")
    await tools.boot()
    res = await tools.t_updates(s, {})
    store.save_session(s)
    say = res.get("say") or ""
    if say:
        store.log_turn(s["id"], "mitra", say, "updates")
    return await _with_voice(s, say, res.get("ui", []), intent="updates")


async def _with_voice(s: dict, say: str, ui: list, intent: str = "", want_audio: bool = True) -> dict:
    say, kn_parts = await kn_say(s, guard.scrub(say))   # a document read, a form submitted, a photo: Kannada on a Kannada session
    audio_b64, tts_prov, tid, parts = "", "browser", "", []
    if say and want_audio:
        parts = kn_parts or split_chunks(say)
        tasks = [asyncio.create_task(speech.tts(p, s["lang"])) for p in parts]
        tid = uuid.uuid4().hex[:10]
        TTS_JOBS[tid] = (time.time(), tasks)
        _gc_jobs()
        wav, tts_prov = await tasks[0]
        if wav:
            audio_b64 = base64.b64encode(wav).decode()
    return {"heard": "", "intent": intent, "say": say, "audio_b64": audio_b64, "tts": guard.public_engine(tts_prov), "ui": ui, "tts_id": tid, "parts": parts,
            "lang": s["lang"], "profile": s["profile"], "officer": s["officer"]}


@app.get("/api/events")
async def events(request: Request, session: str = ""):
    s = store.get_session(session) if session else None
    q = broker.subscribe(s["id"] if s else "")

    async def gen():
        try:
            yield sse({"type": "hello", "now": None})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield sse(ev)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            broker.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"cache-control": "no-cache", "x-accel-buffering": "no"})


@app.get("/api/state")
async def state(session: str = ""):
    s = store.get_session(session) if session else None
    if not s:
        raise HTTPException(404, "unknown session")
    ui = await tools._profile_ui(s)
    store.save_session(s)
    return {"ui": ui, "profile": s["profile"], "officer": s["officer"], "lang": s["lang"]}
