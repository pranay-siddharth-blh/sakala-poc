"""Mitra's own small SQLite store: sessions, spoken turns and voice notes between roles."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, profile TEXT, officer TEXT, lang TEXT, chat_session TEXT,
  state TEXT, created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS deviations (id INTEGER PRIMARY KEY, session TEXT, t TEXT, said TEXT, unsupported TEXT);
CREATE TABLE IF NOT EXISTS turns (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT, t TEXT, role TEXT, text TEXT,
  intent TEXT, meta TEXT);
CREATE TABLE IF NOT EXISTS voice_notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, t TEXT, case_id TEXT, from_role TEXT, to_role TEXT,
  from_officer TEXT, to_officer TEXT, session TEXT, transcript TEXT, audio_b64 TEXT,
  heard INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_turns_session ON turns(session);
CREATE INDEX IF NOT EXISTS ix_notes_to ON voice_notes(to_role, to_officer);
"""

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.DATA.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False, isolation_level=None)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(SCHEMA)
    return _conn


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def q(sql: str, *args) -> list[dict]:
    with _lock:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]


def q1(sql: str, *args) -> dict | None:
    rows = q(sql, *args)
    return rows[0] if rows else None


def run(sql: str, *args) -> int:
    with _lock:
        cur = conn().execute(sql, args)
        return cur.lastrowid


# sessions -------------------------------------------------------------------------------
def new_session(profile: str, officer: str, lang: str) -> dict:
    sid = uuid.uuid4().hex[:12]
    chat_sid = "jv" + uuid.uuid4().hex[:10]
    run("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)",
        sid, profile, officer, lang, chat_sid, "{}", now(), now())
    return get_session(sid)


def get_session(sid: str) -> dict | None:
    s = q1("SELECT * FROM sessions WHERE id=?", sid)
    if s:
        s["state"] = json.loads(s.get("state") or "{}")
    return s


def save_session(s: dict):
    run("UPDATE sessions SET profile=?, officer=?, lang=?, chat_session=?, state=?, updated=? WHERE id=?",
        s["profile"], s["officer"], s["lang"], s["chat_session"], json.dumps(s.get("state") or {}),
        now(), s["id"])


def log_turn(sid: str, role: str, text: str, intent: str = "", meta: dict | None = None):
    run("INSERT INTO turns(session,t,role,text,intent,meta) VALUES (?,?,?,?,?,?)",
        sid, now(), role, text, intent, json.dumps(meta or {}))


def purge_turns(days: int) -> int:
    """Guardrail 8: delete conversation turns older than `days` (and the last recorded clip of idle sessions)."""
    cut = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    n = len(q("SELECT id FROM turns WHERE t < ?", cut))
    run("DELETE FROM turns WHERE t < ?", cut)
    for r in q("SELECT id, state FROM sessions WHERE updated < ?", cut):
        st = json.loads(r["state"] or "{}")
        if st.pop("last_audio", None) is not None:
            run("UPDATE sessions SET state=? WHERE id=?", json.dumps(st), r["id"])
    return n


def forget(sid: str) -> int:
    """Guardrail 8: "forget this conversation" deletes every turn of this screen's session and what it heard last."""
    n = len(q("SELECT id FROM turns WHERE session=?", sid))
    run("DELETE FROM turns WHERE session=?", sid)
    s = get_session(sid)
    if s:
        for k in ("last_audio", "last_say", "last_heard"):
            s["state"].pop(k, None)
        save_session(s)
    return n


def log_deviation(sid: str, said: str, unsupported: list[str]):
    """Guardrails 21-22: a number or case id Mitra spoke that no function result, screen or user words supported."""
    run("INSERT INTO deviations(session,t,said,unsupported) VALUES (?,?,?,?)", sid, now(), said[:600], ", ".join(unsupported))


def deviations(limit: int = 50) -> list[dict]:
    return q("SELECT * FROM deviations ORDER BY id DESC LIMIT ?", limit)


def history(sid: str, n: int = 8) -> list[dict]:
    rows = q("SELECT role,text,intent FROM turns WHERE session=? ORDER BY id DESC LIMIT ?", sid, n)
    return list(reversed(rows))


# voice notes ---------------------------------------------------------------------------
def add_note(**f) -> int:
    nid = run("INSERT INTO voice_notes(t,case_id,from_role,to_role,from_officer,to_officer,session,transcript,audio_b64) "
              "VALUES (?,?,?,?,?,?,?,?,?)",
              now(), f.get("case_id", ""), f["from_role"], f["to_role"], f.get("from_officer", ""),
              f.get("to_officer", ""), f.get("session", ""), f.get("transcript", ""), f.get("audio_b64", ""))
    return nid


def notes_for(role: str, officer: str = "", session: str = "", limit: int = 20) -> list[dict]:
    if role == "citizen":
        rows = q("SELECT id,t,case_id,from_role,to_role,from_officer,to_officer,transcript,heard,length(audio_b64) audio "
                 "FROM voice_notes WHERE to_role='citizen' AND session=? ORDER BY id DESC LIMIT ?", session, limit)
    elif role == "officer":
        rows = q("SELECT id,t,case_id,from_role,to_role,from_officer,to_officer,transcript,heard,length(audio_b64) audio "
                 "FROM voice_notes WHERE to_role='officer' AND (to_officer=? OR to_officer='') ORDER BY id DESC LIMIT ?",
                 officer, limit)
    else:
        rows = q("SELECT id,t,case_id,from_role,to_role,from_officer,to_officer,transcript,heard,length(audio_b64) audio "
                 "FROM voice_notes WHERE to_role='cs' ORDER BY id DESC LIMIT ?", limit)
    return rows


def note_audio(nid: int) -> str:
    r = q1("SELECT audio_b64 FROM voice_notes WHERE id=?", nid)
    run("UPDATE voice_notes SET heard=1 WHERE id=?", nid)
    return (r or {}).get("audio_b64") or ""
