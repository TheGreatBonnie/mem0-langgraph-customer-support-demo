from __future__ import annotations

from dataclasses import dataclass
from re import findall

from support_agent.models import KnowledgeOut


@dataclass(frozen=True)
class KnowledgeEntry:
    title: str
    content: str
    source: str
    keywords: tuple[str, ...]


PRODUCT_KNOWLEDGE: tuple[KnowledgeEntry, ...] = (
    KnowledgeEntry(
        title="Billing Review Policy",
        content=(
            "Billing disputes, duplicate charges, failed payments, refunds, and invoice "
            "exceptions should be routed to a human billing specialist after collecting the "
            "invoice ID and the date of the charge."
        ),
        source="policy://billing-review",
        keywords=("billing", "invoice", "refund", "charge", "payment", "receipt", "duplicate"),
    ),
    KnowledgeEntry(
        title="Account Security Policy",
        content=(
            "Agents must not accept passwords, card numbers, API keys, or one-time codes. "
            "For account recovery, verify ownership through the secure account portal."
        ),
        source="policy://account-security",
        keywords=("password", "security", "account", "login", "2fa", "token", "api key"),
    ),
    KnowledgeEntry(
        title="Bug Triage Playbook",
        content=(
            "For product defects, collect the affected feature, expected behavior, actual "
            "behavior, browser or app version, and a screenshot or log snippet when available."
        ),
        source="playbook://bug-triage",
        keywords=("bug", "error", "broken", "crash", "not working", "issue", "still happening"),
    ),
    KnowledgeEntry(
        title="Onboarding Checklist",
        content=(
            "For new customers, help them connect their workspace, invite teammates, configure "
            "roles, import data, and complete a first successful workflow."
        ),
        source="guide://onboarding",
        keywords=("onboard", "setup", "start", "invite", "workspace", "import", "configure"),
    ),
    KnowledgeEntry(
        title="Cancellation Save Flow",
        content=(
            "When a customer asks to cancel, acknowledge the request, ask the main reason, "
            "offer to preserve data export options, and escalate if billing changes are needed."
        ),
        source="policy://cancellation",
        keywords=("cancel", "cancellation", "terminate", "downgrade", "close account"),
    ),
    KnowledgeEntry(
        title="Feature Request Intake",
        content=(
            "For feature requests, capture the workflow, business impact, urgency, and any "
            "current workaround before tagging the request for product review."
        ),
        source="playbook://feature-request",
        keywords=("feature", "request", "enhancement", "roadmap", "wishlist", "could you add"),
    ),
)


def _tokens(text: str) -> set[str]:
    return set(findall(r"[a-z0-9]+", text.lower()))


class KnowledgeBase:
    def __init__(self, entries: tuple[KnowledgeEntry, ...] = PRODUCT_KNOWLEDGE):
        self.entries = entries

    def search(self, query: str, limit: int = 3) -> list[KnowledgeOut]:
        query_tokens = _tokens(query)
        ranked: list[KnowledgeOut] = []

        for entry in self.entries:
            keyword_tokens = set()
            for keyword in entry.keywords:
                keyword_tokens |= _tokens(keyword)
            content_tokens = _tokens(f"{entry.title} {entry.content}")
            score = len(query_tokens & (keyword_tokens | content_tokens))
            if score == 0:
                continue
            ranked.append(
                KnowledgeOut(
                    title=entry.title,
                    content=entry.content,
                    source=entry.source,
                    score=float(score),
                )
            )

        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:limit]
