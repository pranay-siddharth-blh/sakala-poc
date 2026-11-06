"""Guardrails for Sakala Mitra (17 Oct 2026 list, items 1-4, 14, 21-22, 25).

- Identity and disclosure: no engine or vendor name ever reaches the screen or the voice (`scrub`, `public_engine`); a fixed,
  honest answer to "are you a person / which AI are you / who made you" (`IDENTITY_RX`, `IDENTITY_SAY`).
- Privacy: the same number masking as the Sakala pipeline's privacy shield (`mask`), used for text Mitra logs itself.
- Prompt injection: text that came from citizens, officers or records is data, never instructions; lines that try to give the
  model orders are cut out before such text enters a prompt or a function result (`sanitize`).
- Facts: every number and case id Mitra speaks in a live conversation should come from a Sakala function result, the screen or
  the person's own words; anything else is logged as a deviation (`spoken_numbers`, `facts_from`, `deviations`).
"""
from __future__ import annotations

import re

# ------------------------------------------------------------------ 1-3. vendor / engine names
VENDOR_RX = re.compile(r"\b((?:google\s+)?gemini(?:[\s-]*(?:live|flash|pro|lite|tts|\d[\w.]*))*|google(?:\s+deepmind)?|deepmind|"
                       r"qwen[\w.-]*|open\s?ai|chat\s?gpt|gpt[\s-]?\d[\w.-]*|claude|anthropic|sarvam(?:\s+ai)?|bulbul|saaras|"
                       r"h200|vllm|llama|mistral)\b", re.I)
MODEL_TALK_RX = re.compile(r"\b(large\s+language\s+model|language\s+model|llm)\b", re.I)


def scrub(text: str) -> str:
    """Remove engine / vendor names from anything shown or spoken."""
    if not text:
        return text or ""
    out = VENDOR_RX.sub("Sakala AI", text)
    out = re.sub(r"\b(a)\s+(?=(large\s+language\s+model|language\s+model|llm)\b)", "an ", out, flags=re.I)
    out = MODEL_TALK_RX.sub("AI assistant", out)
    return re.sub(r"(Sakala AI)(\s*(,|and|/|·)?\s*Sakala AI)+", r"\1", out)


def strip_engines(obj, depth: int = 0):
    """Drop engine / model fields from data passed through to the browser (e.g. the accuracy record's "model")."""
    if depth > 8:
        return obj
    if isinstance(obj, dict):
        return {k: strip_engines(v, depth + 1) for k, v in obj.items() if k not in ("model", "engine", "provider", "asr_model")}
    if isinstance(obj, list):
        return [strip_engines(v, depth + 1) for v in obj]
    return obj


def has_vendor(text: str) -> bool:
    return bool(VENDOR_RX.search(text or ""))


def public_engine(name: str) -> str:
    """What the browser may know about an engine: only whether it is the server's AI, the browser's own voice, or typed text."""
    n = (name or "").lower()
    if n in ("browser", "text", ""):
        return n or "browser"
    if n == "rules":
        return "rules"
    return "ai"


# ------------------------------------------------------------------ 4. who Mitra is
IDENTITY_RX = re.compile(
    r"\b(are\s+you\s+(a\s+|an\s+|the\s+)?(human|person|real|man|woman|lady|robot|bot|machine|ai|computer|officer|government\s+officer|"
    r"tahsildar|chief\s+secretary|alive|chat\s?gpt|gemini|google|siri|alexa)|"
    r"which\s+(ai|model|llm|engine|company)|what\s+(ai|model|llm|engine)\s+(are|is)|what\s+are\s+you(\s+exactly|\s+really)?\s*[?.!]*$|"
    r"who\s+are\s+you(\s+exactly|\s+really)?\s*[?.!]*$|"
    r"who\s+(made|built|created|developed|trained|programmed)\s+you|what\s+(model|language\s+model)\s+(powers|runs)|"
    r"(are|is)\s+(this|it)\s+(a\s+)?(human|person|real\s+person|recording|bot)|am\s+i\s+(talking|speaking)\s+to\s+(a\s+)?(human|person|real|bot|machine|computer|ai))",
    re.I)
IDENTITY_SAY = ("I'm Mitra, the voice assistant for the Sakala and iPGRS services of the Government of Karnataka. I'm an AI assistant, not a person and not a "
                "government officer. Officers take the decisions; I help you reach the right one and keep track of it.")
IDENTITY_MAKER = ("I was built for the Praja Seva Department to help citizens, officers and the Chief Secretary with Sakala. "
                  "I'm an AI assistant, not a person and not an officer.")


def identity_answer(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"who\s+(made|built|created|developed|trained|programmed)|which\s+company", t):
        return IDENTITY_MAKER
    return IDENTITY_SAY


# ------------------------------------------------------------------ 14. masking (same patterns as app/server/privacy.py)
_MASKS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    (re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)"), "[AADHAAR]"),
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"), "[PHONE]"),
    (re.compile(r"\b[A-Z]{2,3}\d{8,13}\b"), "[ID-MASKED]"),
]


def mask(text: str) -> str:
    out = text or ""
    for rx, tag in _MASKS:
        out = rx.sub(tag, out)
    return out


# ------------------------------------------------------------------ 25. prompt injection
INJECTION_RX = re.compile(
    r"(ignore|disregard|forget|override|bypass)\s+(all\s+|any\s+|the\s+|your\s+|these\s+|those\s+|previous\s+|prior\s+|above\s+|earlier\s+)*"
    r"(instructions?|rules?|prompts?|guidelines?|guardrails?|system\s+message|restrictions?)|"
    r"(system|developer|hidden)\s+(prompt|message|instructions?)|"
    r"you\s+are\s+now\b|from\s+now\s+on\s+you\s+(are|will|must)|act\s+as\s+(an?\s+)?(unrestricted|different|new)|"
    r"(developer|god|admin|jailbreak|dan)\s+mode|jailbreak|do\s+anything\s+now|"
    r"reveal\s+(your|the)\s+(prompt|instructions?|rules?|system)|print\s+(your|the)\s+(prompt|instructions?)|"
    r"(new|updated)\s+instructions?\s*:|^\s*(system|assistant|developer)\s*:", re.I | re.M)


def injection(text: str) -> bool:
    return bool(INJECTION_RX.search(text or ""))


def sanitize(obj, depth: int = 0):
    """Cut instruction-like sentences out of data (complaint texts, notes, histories) before a model reads it."""
    if depth > 8:
        return obj
    if isinstance(obj, str):
        if not INJECTION_RX.search(obj):
            return obj
        parts = re.split(r"(?<=[.!?\n])\s+", obj)
        kept = [p for p in parts if not INJECTION_RX.search(p)]
        return (" ".join(kept) + " [instruction-like text removed]").strip()
    if isinstance(obj, dict):
        return {k: sanitize(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v, depth + 1) for v in obj]
    return obj


# ------------------------------------------------------------------ 21-22. numbers and ids Mitra speaks
_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
                                     "sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
_SCALES = {"hundred": 100, "thousand": 1_000, "lakh": 100_000, "lakhs": 100_000, "lac": 100_000, "million": 1_000_000,
           "crore": 10_000_000, "crores": 10_000_000, "billion": 1_000_000_000}
_DIGIT_WORDS = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
                "eight": "8", "nine": "9"}


def _words_to_numbers(text: str) -> list[float]:
    """Spoken numbers in English words -> values ("three thousand fifty-six" -> 3056; "five zero four two" -> 5042)."""
    toks = re.findall(r"[a-z]+|\d+(?:\.\d+)?", (text or "").lower().replace("-", " "))
    out: list[float] = []
    i = 0
    while i < len(toks):
        # a run of single digits said one by one (ids): "five zero four two two seven"
        j, digits = i, ""
        while j < len(toks) and (toks[j] in _DIGIT_WORDS or (toks[j].isdigit() and len(toks[j]) == 1)):
            digits += _DIGIT_WORDS.get(toks[j], toks[j]); j += 1
        if len(digits) >= 3:
            out.append(float(digits)); i = j; continue
        # a cardinal: "three thousand and fifty six", "one point five"
        if toks[i] in _UNITS or toks[i] in _TENS:
            total, cur, j, seen = 0, 0, i, False
            while j < len(toks):
                w = toks[j]
                if w in _UNITS:
                    cur += _UNITS[w]; seen = True
                elif w in _TENS:
                    cur += _TENS[w]; seen = True
                elif w == "hundred" and seen:
                    cur = (cur or 1) * 100
                elif w in _SCALES and seen:
                    total += (cur or 1) * _SCALES[w]; cur = 0
                elif w == "and" and seen and j + 1 < len(toks) and (toks[j + 1] in _UNITS or toks[j + 1] in _TENS):
                    pass
                else:
                    break
                j += 1
            val = float(total + cur)
            if j < len(toks) and toks[j] == "point" and j + 1 < len(toks) and toks[j + 1] in _DIGIT_WORDS:
                dec, k = "", j + 1
                while k < len(toks) and toks[k] in _DIGIT_WORDS:
                    dec += _DIGIT_WORDS[toks[k]]; k += 1
                val = float(f"{int(val)}.{dec}"); j = k
            out.append(val); i = max(j, i + 1); continue
        i += 1
    return out


def spoken_numbers(text: str) -> list[float]:
    """Every number in a spoken transcript, written as digits or as words."""
    t = (text or "").replace(",", "")
    t = re.sub(r"\b(G\s*R|S\s*K)[\s.-]*", "", t, flags=re.I)              # "G R 5 0 4 2 2 7" -> the digits
    t = re.sub(r"(?<=\d)\s+(?=\d\b)", "", t)                              # "5 0 4 2 2 7" -> "504227"
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]
    words = re.sub(r"\d+(?:\.\d+)?", " ", t)
    return nums + _words_to_numbers(words)


def spoken_ids(text: str) -> list[str]:
    t = " ".join(_DIGIT_WORDS.get(w.lower(), w) for w in re.split(r"\s+", text or ""))
    t = re.sub(r"(?<=\d)\s+(?=\d)", "", t.upper())
    return [f"GR-{m}" for m in re.findall(r"G\s*\.?\s*R[\s-]*(\d{5,})", t)] + re.findall(r"\bSK-[A-Z0-9]{6,}\b", t)


# numbers that need no source: small counts, the year, the Sakala Act's fixed figures, the clock
TRIVIAL = {float(x) for x in list(range(0, 13)) + [15, 20, 21, 24, 30, 45, 48, 60, 90, 100, 500, 2012, 2014, 2025, 2026, 1902]}


def facts_from(obj, acc: set | None = None, depth: int = 0) -> set:
    """Numbers (and their usual spoken roundings) found anywhere in a function result or screen context."""
    acc = acc if acc is not None else set()
    if depth > 10:
        return acc
    if isinstance(obj, bool):
        return acc
    if isinstance(obj, (int, float)):
        v = float(obj)
        for x in (v, round(v), round(v, 1), round(v, 2), round(v * 100, 1), round(v * 100, 2), round(v * 100),
                  round(v / 1e7, 1), round(v / 1e7, 2), round(v / 1e5, 1), round(v / 1e6, 1), round(v / 1000, 1), round(v / 1000)):
            acc.add(float(x))
        return acc
    if isinstance(obj, str):
        for x in spoken_numbers(obj):
            facts_from(x, acc, depth + 1)
        for m in re.findall(r"\d{5,}", obj):
            acc.add(float(m))
        return acc
    if isinstance(obj, dict):
        for v in obj.values():
            facts_from(v, acc, depth + 1)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            facts_from(v, acc, depth + 1)
    return acc


def deviations(said: str, facts: set) -> list[str]:
    """Numbers / ids in what Mitra said that no source supports."""
    bad = []
    for v in spoken_numbers(said):
        if v in TRIVIAL or v in facts or round(v, 1) in facts or round(v) in facts:
            continue
        if any(abs(v - f) <= max(0.051, abs(f) * 0.006) for f in facts if f):   # spoken roundings ("about 3,056" for 3,056.4)
            continue
        bad.append(str(int(v)) if v.is_integer() else str(v))
    return bad


# ------------------------------------------------------------------ long Sakala application numbers, read aloud
def speakable_ids(text: str) -> str:
    """SK-RD855S260004811 -> "the application ending in 4811" (cards on screen keep the full number)."""
    return re.sub(r"\bSK-?[A-Z0-9]{8,}\b", lambda m: f"the application ending in {m.group(0)[-4:]}", text or "")
