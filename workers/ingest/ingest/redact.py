"""PII redaction runs BEFORE embedding (arch §4.3). Keep fast + deterministic."""

import re

EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")
TOKEN = re.compile(r"\b(sk-[A-Za-z0-9\-_]{8,}|ghp_[A-Za-z0-9]{8,}|xox[bap]-[A-Za-z0-9\-_]+)\b")


def redact(text: str) -> str:
    text = EMAIL.sub("[REDACTED_EMAIL]", text)
    text = TOKEN.sub("[REDACTED_TOKEN]", text)
    # phones last (most false-positive prone); require 8+ digits
    def _phone(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        return "[REDACTED_PHONE]" if len(digits) >= 8 else m.group(0)

    return PHONE.sub(_phone, text)
