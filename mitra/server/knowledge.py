"""Mitra's knowledge base (22 Oct 2026): general questions ("what is Sakala?", "who is the Chief Secretary?", "how does
routing work?") are answered from mitra/knowledge.yaml and from nothing else. The matcher is deterministic (phrases and
keywords, no model), so the same question gets the same fact on the live voice, the cascade and the rules brain; the model
only puts the fact into conversational words. A question the file does not cover gets "not in my notes", never a guess."""
from __future__ import annotations

import re
import time
from pathlib import Path

import yaml

PATH = Path(__file__).resolve().parents[1] / "knowledge.yaml"
_ENTRIES: list[dict] = []
_BY_ID: dict[str, dict] = {}
_MTIME = 0.0

STOP = set("the a an of in on at to for is are was were be do does did what which who whom whose why how when where can could would "
           "should will shall may might i me my you your we our it its this that these those and or but if then than there here please "
           "tell about explain mitra hey hi hello so um uh like know mean means get got".split())
# a question about the live data (counts, lists, one case) or an instruction is never answered from the notes
DATA_RX = re.compile(r"\b(how many|count|number of|list|show me|open cases|overdue cases|pending cases|cases in|grievances in|complaints in|"
                     r"which officer has|most overdue|rank|compare|trend|this week|today|yesterday|gr-?\d|sk-?[a-z0-9]{6,}|grievance \d|case \d|\d{5,})\b")
DATA_OK_RX = re.compile(r"\b(2025|performance|how many (departments|services|districts|taluks|days|levels|times|stages|officers are mapped))\b")
ACTION_RX = re.compile(r"\b(take me|go back|back to|bring|open|show|nudge|remind|file it|register|send|read my|accept|reject|resolve|switch|upload|"
                       r"i want to|i need|i would like|i'd like|my request|my complaint|my case|status of|track|where is my|not working|no water|not coming|broken|is bad|since \d)\b")
QWORD_RX = re.compile(r"\b(what|what's|who|who's|whom|which|why|how|when|where|is|are|does|do|can|could|tell|explain|about|meaning|mean|difference|define)\b")


def _norm(s) -> str:
    """The question, lowered, without the wake word and the politeness around it."""
    s = str(s if s is not None else "").lower().replace("’", "'")
    s = re.sub(r"[^a-z0-9ಀ-೿' .-]+", " ", s)
    s = re.sub(r"\b(hey|hi|ok|okay)?\s*mitra[,!]?(?=\s|$)", " ", s)
    s = re.sub(r"\b(can|could|would) you (please )?(tell|explain|describe)( to)? (me|us)\b", " ", s)
    s = re.sub(r"\bplease\b", " ", s)
    s = re.sub(r"[.?!,]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _plain(s) -> str:
    """An `ask` phrase from the file: lowered, punctuation dropped, nothing else removed."""
    s = str(s if s is not None else "").lower().replace("’", "'")
    s = re.sub(r"[^a-z0-9ಀ-೿' .-]+", " ", s)
    s = re.sub(r"[.?!,]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9ಀ-೿'-]+", s):
        w = w[:-2] if w.endswith("'s") else w
        if w not in STOP and len(w) > 1:
            out.add(w)
            if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
                out.add(w[:-1])                       # appeals -> appeal, deadlines -> deadline
    return out


def load(force: bool = False) -> list[dict]:
    """Reads the YAML (again when the file changed), so the notes can be edited while Mitra runs."""
    global _ENTRIES, _BY_ID, _MTIME
    try:
        m = PATH.stat().st_mtime
    except OSError:
        return _ENTRIES
    if _ENTRIES and not force and m == _MTIME:
        return _ENTRIES
    raw = yaml.safe_load(PATH.read_text(encoding="utf-8")) or []
    out = []
    for e in raw:
        if not e.get("id") or not e.get("say"):
            continue
        asks = [a for a in (_plain(x) for x in (e.get("ask") or [])) if len(a) >= 3 and not (len(a.split()) == 1 and a in STOP)]
        keys = {_plain(k) for k in (e.get("keys") or []) if _plain(k)}
        out.append({**e, "_asks": asks, "_keys": keys, "_toks": set().union(*[_tokens(a) for a in asks]) | keys,
                    "say": " ".join(str(e["say"]).split()), "more": " ".join(str(e.get("more") or "").split())})
    _ENTRIES, _BY_ID, _MTIME = out, {e["id"]: e for e in out}, m
    return _ENTRIES


def score(entry: dict, q: str, toks: set[str]) -> float:
    s = 0.0
    for a in entry["_asks"]:
        if re.search(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", q):
            s += 2.0 + 1.5 * len(a.split())           # a known phrasing inside the question; longer phrases weigh more
    hit = toks & entry["_toks"]
    keyhits = hit & entry["_keys"]
    s += 2.0 * len(keyhits) + 0.5 * len(hit - entry["_keys"])
    if keyhits and QWORD_RX.search(q):
        s += 1.5                                      # a distinctive topic word inside a question
    return s


def match(text: str, last: str = "", strict: bool = True) -> tuple[dict | None, float]:
    """The best entry for a question. strict = the bar the rules brain uses before it claims the turn (a knowledge question
    must clearly be one); loose = what the catch-all uses when nothing else matched. A follow-up ("and compensation?") that
    ties between entries prefers those related to the last answer."""
    q = _norm(text)
    if not q:
        return None, 0.0
    if DATA_RX.search(q) and not DATA_OK_RX.search(q):
        return None, 0.0
    if ACTION_RX.search(q):
        return None, 0.0
    toks = _tokens(q)
    best, bs = None, 0.0
    rel = set((_BY_ID.get(last) or {}).get("related") or []) if last else set()
    for e in load():
        s = score(e, q, toks)
        if s and (e["id"] in rel or e["id"] == last):
            s += 0.75
        if s > bs:
            best, bs = e, s
    bar = 3.5 if strict else 2.0
    if best and bs >= bar:
        if strict and not (QWORD_RX.search(q) or len(toks) <= 3):      # a strict claim needs a question shape or a bare topic
            return None, 0.0
        return best, bs
    return None, 0.0


def answer(text: str, last: str = "", strict: bool = False) -> dict | None:
    e, s = match(text, last, strict=strict)
    if not e:
        return None
    related = [{"id": r, "topic": _BY_ID[r]["topic"]} for r in (e.get("related") or []) if r in _BY_ID]
    return {"id": e["id"], "topic": e["topic"], "say": e["say"], "more": e["more"], "source": e.get("source") or "", "related": related, "score": s}


def topics() -> list[str]:
    return [e["topic"] for e in load()]


def stamp() -> str:
    load()
    return time.strftime("%d %b %Y", time.localtime(_MTIME)) if _MTIME else ""
