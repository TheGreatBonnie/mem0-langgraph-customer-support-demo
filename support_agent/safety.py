from __future__ import annotations

import re


CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
SECRET_RE = re.compile(
    r"\b(password|passcode|secret|api[_ -]?key|token|cvv|credit card|card number)\b",
    re.IGNORECASE,
)


def contains_sensitive_data(text: str) -> bool:
    return bool(CARD_RE.search(text) or SSN_RE.search(text) or SECRET_RE.search(text))


def redacted_for_prompt(text: str) -> str:
    text = CARD_RE.sub("[redacted-card-number]", text)
    text = SSN_RE.sub("[redacted-ssn]", text)
    return text


def is_angry_or_high_risk(text: str) -> bool:
    angry_terms = (
        "angry",
        "furious",
        "lawsuit",
        "legal action",
        "terrible",
        "unacceptable",
        "cancel everything",
        "never works",
    )
    lowered = text.lower()
    return any(term in lowered for term in angry_terms)
