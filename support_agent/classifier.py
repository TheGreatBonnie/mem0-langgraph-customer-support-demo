from __future__ import annotations

from support_agent.models import Intent
from support_agent.safety import contains_sensitive_data, is_angry_or_high_risk


INTENT_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    "billing": ("billing", "invoice", "refund", "charge", "payment", "receipt", "paid"),
    "bug": ("bug", "error", "broken", "crash", "not working", "issue", "still happening"),
    "onboarding": ("onboard", "setup", "start", "invite", "workspace", "configure", "import"),
    "cancellation": ("cancel", "cancellation", "downgrade", "terminate", "close account"),
    "feature_request": ("feature", "request", "roadmap", "wishlist", "could you add"),
    "account": ("account", "login", "password", "security", "2fa", "email", "access"),
    "general": (),
}


def classify_intent(message: str) -> Intent:
    lowered = message.lower()
    scores: dict[Intent, int] = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        scores[intent] = sum(1 for keyword in keywords if keyword in lowered)
    if scores["bug"] > 0 and any(
        term in lowered for term in ("broken", "error", "crash", "not working", "still happening")
    ):
        return "bug"
    winner = max(scores, key=scores.get)
    return winner if scores[winner] > 0 else "general"


def should_escalate(message: str, intent: Intent, force: bool = False) -> bool:
    lowered = message.lower()
    if force:
        return True
    if contains_sensitive_data(message) or is_angry_or_high_risk(message):
        return True
    if intent == "billing":
        return True
    if intent == "account" and any(term in lowered for term in ("locked", "password", "2fa", "security")):
        return True
    if intent == "cancellation" and any(term in lowered for term in ("refund", "billing", "charge")):
        return True
    if intent == "bug" and any(term in lowered for term in ("still", "again", "keeps", "production")):
        return True
    return False
