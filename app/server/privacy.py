"""Stage 2 · Privacy shield: personal numbers are masked before any AI model reads the text."""
import re

_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    (re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)"), "[AADHAAR]"),                 # 12-digit Aadhaar
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"), "[PHONE]"),              # Indian mobile
    (re.compile(r"\b[A-Z]{2,3}\d{8,13}\b"), "[ID-MASKED]"),                           # ration card / application numbers
]


def mask(text: str) -> tuple[str, int]:
    """Return (masked_text, number_of_items_masked)."""
    n = 0
    out = text or ""
    for rx, tag in _PATTERNS:
        out, k = rx.subn(tag, out)
        n += k
    return out, n
