from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from support_agent.config import Settings
from support_agent.models import Intent, MemoryOut, MemoryRelation
from support_agent.safety import contains_sensitive_data


INTENT_CATEGORY_HINTS: dict[Intent, tuple[str, ...]] = {
    "billing": ("billing_context", "billing", "finance"),
    "bug": ("open_support_issue", "support_issue", "bug"),
    "onboarding": ("user_preferences", "onboarding", "preference"),
    "cancellation": ("billing_context", "cancellation"),
    "feature_request": ("feature_request", "product_feedback"),
    "account": ("account", "personal_information", "security"),
    "general": (),
}

EXPLICIT_MEMORY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:my|our)\s+plan\s+(?:is|=)\s+", re.IGNORECASE),
    re.compile(r"\b(?:ticket|invoice|case)\s*(?:#|id)?\s*:?\s*\w+", re.IGNORECASE),
    re.compile(r"\b(?:short|concise|brief)\b", re.IGNORECASE),
    re.compile(r"\bprefer(?:ence|s)?\b", re.IGNORECASE),
)


@dataclass
class MemoryContextResult:
    memories: list[MemoryOut] = field(default_factory=list)
    relations: list[MemoryRelation] = field(default_factory=list)


class MemoryStore(Protocol):
    def search(self, query: str, user_id: str, top_k: int = 5) -> list[MemoryOut]:
        ...

    def search_for_context(
        self,
        *,
        query: str,
        user_id: str,
        conversation_id: str,
        intent: Intent,
        top_k: int = 5,
    ) -> MemoryContextResult:
        ...

    def add_interaction(
        self,
        *,
        user_id: str,
        conversation_id: str,
        user_message: str,
        assistant_reply: str,
        metadata: dict[str, Any],
    ) -> int:
        ...

    def list_user_memories(self, user_id: str) -> list[MemoryOut]:
        ...

    def delete_user_memories(self, user_id: str) -> None:
        ...

    def delete_memory(self, user_id: str, memory_id: str) -> None:
        ...

    def mark_memory_outdated(self, user_id: str, memory_id: str, reason: str) -> MemoryOut:
        ...

    def correct_memory(
        self,
        user_id: str,
        memory_id: str,
        corrected_text: str,
        reason: str,
    ) -> MemoryOut:
        ...


def create_memory_store(settings: Settings) -> MemoryStore:
    if settings.use_live_mem0:
        try:
            return Mem0MemoryStore(settings)
        except Exception:
            if settings.offline_mode.lower() == "false":
                raise
    return LocalMemoryStore()


class Mem0MemoryStore:
    def __init__(self, settings: Settings):
        from mem0 import MemoryClient

        self.settings = settings
        self.client = MemoryClient(api_key=settings.mem0_api_key)

    def search(self, query: str, user_id: str, top_k: int = 5) -> list[MemoryOut]:
        response = self._mem0_search(query=query, user_id=user_id, top_k=top_k)
        return _filter_outdated(_normalize_memories(response))[:top_k]

    def search_for_context(
        self,
        *,
        query: str,
        user_id: str,
        conversation_id: str,
        intent: Intent,
        top_k: int = 5,
    ) -> MemoryContextResult:
        intent_query = _intent_aware_query(intent, query)
        thread_response = self._mem0_search(
            query=intent_query,
            user_id=user_id,
            conversation_id=conversation_id,
            top_k=self.settings.mem0_thread_top_k,
            category_hints=INTENT_CATEGORY_HINTS.get(intent, ()),
        )
        profile_response = self._mem0_search(
            query=intent_query,
            user_id=user_id,
            top_k=self.settings.mem0_profile_top_k,
            category_hints=INTENT_CATEGORY_HINTS.get(intent, ()),
        )

        thread_memories = [
            memory.model_copy(update={"scope": "thread"})
            for memory in _filter_outdated(_normalize_memories(thread_response))
        ]
        profile_memories = [
            memory.model_copy(update={"scope": "profile"})
            for memory in _filter_outdated(_normalize_memories(profile_response))
        ]
        relations = _normalize_relations(thread_response) + _normalize_relations(profile_response)
        merged = _dedupe_memories(thread_memories + profile_memories)[:top_k]
        return MemoryContextResult(memories=merged, relations=_dedupe_relations(relations))

    def add_interaction(
        self,
        *,
        user_id: str,
        conversation_id: str,
        user_message: str,
        assistant_reply: str,
        metadata: dict[str, Any],
    ) -> int:
        category = _infer_local_category(user_message)
        if category == "plan":
            _delete_memories_by_category(self, user_id, "plan")

        infer = not should_use_explicit_memory(user_message)
        add_kwargs: dict[str, Any] = {
            "messages": [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_reply},
            ],
            "user_id": user_id,
            "run_id": conversation_id,
            "agent_id": self.settings.agent_id,
            "app_id": self.settings.app_id,
            "metadata": {**metadata, "category": category, "status": "active"},
            "infer": infer,
        }
        if self.settings.mem0_enable_graph:
            add_kwargs["enable_graph"] = True

        response = self._mem0_add(add_kwargs)
        if isinstance(response, dict) and "results" in response:
            return len(response["results"])
        return 1

    def list_user_memories(self, user_id: str) -> list[MemoryOut]:
        response = self.client.get_all(filters={"user_id": user_id}, page=1, page_size=100)
        return _normalize_memories(response)

    def delete_user_memories(self, user_id: str) -> None:
        self.client.delete_all(user_id=user_id)

    def delete_memory(self, user_id: str, memory_id: str) -> None:
        self._assert_user_memory(user_id, memory_id)
        self.client.delete(memory_id=memory_id)

    def mark_memory_outdated(self, user_id: str, memory_id: str, reason: str) -> MemoryOut:
        memory = self._assert_user_memory(user_id, memory_id)
        metadata = dict(memory.metadata)
        metadata.update({"status": "outdated", "outdated_reason": reason})
        text = f"[OUTDATED] {memory.memory}"
        response = self.client.update(memory_id=memory_id, text=text, metadata=metadata)
        normalized = _normalize_memories(response)
        if normalized:
            return normalized[0]
        return MemoryOut(id=memory.id, memory=text, metadata=metadata, categories=memory.categories)

    def correct_memory(
        self,
        user_id: str,
        memory_id: str,
        corrected_text: str,
        reason: str,
    ) -> MemoryOut:
        old_memory = self._assert_user_memory(user_id, memory_id)
        self.delete_memory(user_id, memory_id)

        add_kwargs: dict[str, Any] = {
            "messages": [{"role": "user", "content": corrected_text}],
            "user_id": user_id,
            "infer": False,
            "metadata": {
                "status": "active",
                "corrects": memory_id,
                "correction_reason": reason,
                "category": old_memory.metadata.get("category"),
            },
            "agent_id": self.settings.agent_id,
            "app_id": self.settings.app_id,
        }
        if self.settings.mem0_enable_graph:
            add_kwargs["enable_graph"] = True

        response = self._mem0_add(add_kwargs)
        normalized = _normalize_memories(response)
        if normalized:
            return normalized[0]
        return MemoryOut(
            id=str(uuid4()),
            memory=corrected_text,
            metadata=add_kwargs["metadata"],
            categories=old_memory.categories,
        )

    def _mem0_search(
        self,
        *,
        query: str,
        user_id: str,
        top_k: int,
        conversation_id: str | None = None,
        category_hints: tuple[str, ...] = (),
    ) -> Any:
        attempts: list[dict[str, Any]] = []

        base_filters: list[dict[str, Any]] = [{"user_id": user_id}]
        if conversation_id:
            base_filters.append({"run_id": conversation_id})
        if category_hints:
            base_filters.append({"categories": {"contains": category_hints[0]}})

        attempts.append(
            {
                "filters": {"AND": base_filters},
                "top_k": top_k,
                "rerank": self.settings.mem0_search_rerank,
                "keyword_search": self.settings.mem0_search_keyword,
                "threshold": self.settings.mem0_search_threshold,
                "enable_graph": self.settings.mem0_enable_graph,
            }
        )
        attempts.append({"user_id": user_id, "top_k": top_k, "run_id": conversation_id})
        attempts.append({"user_id": user_id, "top_k": top_k})
        attempts.append({"filters": {"user_id": user_id}, "top_k": top_k})

        last_error: Exception | None = None
        for kwargs in attempts:
            clean_kwargs = {key: value for key, value in kwargs.items() if value is not None}
            try:
                return self.client.search(query, **clean_kwargs)
            except TypeError as exc:
                last_error = exc
                continue
            except Exception as exc:
                last_error = exc
                continue

        if last_error:
            raise last_error
        return {"results": []}

    def _mem0_add(self, kwargs: dict[str, Any]) -> Any:
        try:
            return self.client.add(**kwargs)
        except TypeError:
            fallback = dict(kwargs)
            fallback.pop("enable_graph", None)
            return self.client.add(**fallback)

    def _assert_user_memory(self, user_id: str, memory_id: str) -> MemoryOut:
        for memory in self.list_user_memories(user_id):
            if memory.id == memory_id:
                return memory
        raise KeyError(f"Memory {memory_id} was not found for user {user_id}.")


class LocalMemoryStore:
    def __init__(self):
        self._memories: dict[str, list[MemoryOut]] = {}

    def search(self, query: str, user_id: str, top_k: int = 5) -> list[MemoryOut]:
        return self._rank_memories(
            query=query,
            user_id=user_id,
            top_k=top_k,
            conversation_id=None,
            scope="profile",
        )

    def search_for_context(
        self,
        *,
        query: str,
        user_id: str,
        conversation_id: str,
        intent: Intent,
        top_k: int = 5,
    ) -> MemoryContextResult:
        intent_query = _intent_aware_query(intent, query)
        thread_memories = self._rank_memories(
            query=intent_query,
            user_id=user_id,
            top_k=3,
            conversation_id=conversation_id,
            scope="thread",
            category_hints=INTENT_CATEGORY_HINTS.get(intent, ()),
        )
        profile_memories = self._rank_memories(
            query=intent_query,
            user_id=user_id,
            top_k=5,
            conversation_id=None,
            scope="profile",
            category_hints=INTENT_CATEGORY_HINTS.get(intent, ()),
        )
        merged = _dedupe_memories(thread_memories + profile_memories)[:top_k]
        relations = _local_relations(merged)
        return MemoryContextResult(memories=merged, relations=relations)

    def add_interaction(
        self,
        *,
        user_id: str,
        conversation_id: str,
        user_message: str,
        assistant_reply: str,
        metadata: dict[str, Any],
    ) -> int:
        if contains_sensitive_data(user_message):
            return 0

        summary, category = _summarize_user_message(user_message)
        created_at = datetime.now(UTC).isoformat()
        memory_metadata = {
            **metadata,
            "conversation_id": conversation_id,
            "created_at": created_at,
            "status": "active",
            "local_demo": True,
            "explicit_memory": should_use_explicit_memory(user_message),
        }

        if category == "plan":
            self._memories[user_id] = [
                memory
                for memory in self._memories.get(user_id, [])
                if memory.metadata.get("category") != "plan"
            ]

        memory = MemoryOut(
            id=str(uuid4()),
            memory=summary,
            metadata={**memory_metadata, "category": category},
            categories=[category],
            score=None,
        )
        self._memories.setdefault(user_id, []).append(memory)
        return 1

    def list_user_memories(self, user_id: str) -> list[MemoryOut]:
        return list(reversed(self._memories.get(user_id, [])))

    def delete_user_memories(self, user_id: str) -> None:
        self._memories[user_id] = []

    def delete_memory(self, user_id: str, memory_id: str) -> None:
        before = len(self._memories.get(user_id, []))
        self._memories[user_id] = [
            memory for memory in self._memories.get(user_id, []) if memory.id != memory_id
        ]
        if len(self._memories[user_id]) == before:
            raise KeyError(f"Memory {memory_id} was not found for user {user_id}.")

    def mark_memory_outdated(self, user_id: str, memory_id: str, reason: str) -> MemoryOut:
        for index, memory in enumerate(self._memories.get(user_id, [])):
            if memory.id != memory_id:
                continue
            updated = memory.model_copy(
                update={
                    "memory": f"[OUTDATED] {memory.memory}",
                    "metadata": {
                        **memory.metadata,
                        "status": "outdated",
                        "outdated_reason": reason,
                    },
                }
            )
            self._memories[user_id][index] = updated
            return updated
        raise KeyError(f"Memory {memory_id} was not found for user {user_id}.")

    def correct_memory(
        self,
        user_id: str,
        memory_id: str,
        corrected_text: str,
        reason: str,
    ) -> MemoryOut:
        old_memory = self._assert_user_memory(user_id, memory_id)
        self.delete_memory(user_id, memory_id)
        memory = MemoryOut(
            id=str(uuid4()),
            memory=corrected_text,
            metadata={
                "status": "active",
                "corrects": memory_id,
                "correction_reason": reason,
                "category": old_memory.metadata.get("category"),
                "created_at": datetime.now(UTC).isoformat(),
                "local_demo": True,
            },
            categories=old_memory.categories,
            score=None,
        )
        self._memories.setdefault(user_id, []).append(memory)
        return memory

    def _rank_memories(
        self,
        *,
        query: str,
        user_id: str,
        top_k: int,
        conversation_id: str | None,
        scope: str,
        category_hints: tuple[str, ...] = (),
    ) -> list[MemoryOut]:
        query_terms = _terms(query)
        ranked: list[MemoryOut] = []
        for memory in self._memories.get(user_id, []):
            if memory.metadata.get("status") == "outdated":
                continue
            if conversation_id is not None:
                if memory.metadata.get("conversation_id") != conversation_id:
                    continue
            elif conversation_id is None and scope == "profile":
                pass

            memory_terms = _terms(memory.memory)
            score = len(query_terms & memory_terms)
            category = str(memory.metadata.get("category") or "")
            if category in category_hints:
                score += 1
            if memory.metadata.get("category") == "preference":
                score = max(score, 0.5)
            if scope == "thread":
                score = max(score, 0.1)
            if score > 0:
                ranked.append(
                    memory.model_copy(
                        update={
                            "score": float(score),
                            "scope": "thread" if scope == "thread" else "profile",
                        }
                    )
                )

        ranked.sort(
            key=lambda item: (
                item.score or 0.0,
                1 if item.scope == "thread" else 0,
                item.metadata.get("created_at", ""),
            ),
            reverse=True,
        )
        return ranked[:top_k]

    def _assert_user_memory(self, user_id: str, memory_id: str) -> MemoryOut:
        for memory in self._memories.get(user_id, []):
            if memory.id == memory_id:
                return memory
        raise KeyError(f"Memory {memory_id} was not found for user {user_id}.")


def should_use_explicit_memory(message: str) -> bool:
    return any(pattern.search(message) for pattern in EXPLICIT_MEMORY_PATTERNS)


def _intent_aware_query(intent: Intent, query: str) -> str:
    return f"{intent}: {query}"


def _filter_outdated(memories: list[MemoryOut]) -> list[MemoryOut]:
    filtered: list[MemoryOut] = []
    for memory in memories:
        if memory.metadata.get("status") == "outdated":
            continue
        if memory.memory.startswith("[OUTDATED]"):
            continue
        filtered.append(memory)
    return filtered


def _dedupe_memories(memories: list[MemoryOut]) -> list[MemoryOut]:
    seen: set[str] = set()
    deduped: list[MemoryOut] = []
    for memory in memories:
        if memory.id in seen:
            continue
        seen.add(memory.id)
        deduped.append(memory)
    return deduped


def _dedupe_relations(relations: list[MemoryRelation]) -> list[MemoryRelation]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[MemoryRelation] = []
    for relation in relations:
        key = (relation.source, relation.relationship, relation.target)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(relation)
    return deduped


def _delete_memories_by_category(store: Mem0MemoryStore, user_id: str, category: str) -> None:
    for memory in store.list_user_memories(user_id):
        if memory.metadata.get("category") == category or category in memory.categories:
            store.delete_memory(user_id, memory.id)


def _infer_local_category(message: str) -> str:
    _, category = _summarize_user_message(message)
    return category


def _normalize_memories(response: Any) -> list[MemoryOut]:
    if isinstance(response, dict):
        raw_items = response.get("results")
        if raw_items is None:
            raw_items = [response]
    elif isinstance(response, list):
        raw_items = response
    else:
        raw_items = []

    memories: list[MemoryOut] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        text = item.get("memory") or item.get("text") or item.get("content") or ""
        if not text:
            continue
        memories.append(
            MemoryOut(
                id=str(item.get("id") or item.get("memory_id") or uuid4()),
                memory=str(text),
                metadata=dict(item.get("metadata") or {}),
                categories=list(item.get("categories") or []),
                score=item.get("score"),
            )
        )
    return memories


def _normalize_relations(response: Any) -> list[MemoryRelation]:
    if not isinstance(response, dict):
        return []

    raw_relations = response.get("relations")
    if not isinstance(raw_relations, list):
        return []

    relations: list[MemoryRelation] = []
    for item in raw_relations:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or item.get("from") or "")
        relationship = str(item.get("relationship") or item.get("relation") or item.get("type") or "")
        target = str(item.get("target") or item.get("to") or "")
        if not source or not relationship or not target:
            continue
        relations.append(
            MemoryRelation(source=source, relationship=relationship, target=target)
        )
    return relations


def _local_relations(memories: list[MemoryOut]) -> list[MemoryRelation]:
    relations: list[MemoryRelation] = []
    for memory in memories:
        category = str(memory.metadata.get("category") or "")
        if category == "support_issue":
            relations.append(
                MemoryRelation(
                    source=memory.memory[:80],
                    relationship="related_to",
                    target="open_support_issue",
                )
            )
        if category == "plan":
            relations.append(
                MemoryRelation(
                    source=memory.memory[:80],
                    relationship="has_plan",
                    target=memory.memory,
                )
            )
    return relations


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _summarize_user_message(message: str) -> tuple[str, str]:
    lowered = message.lower()
    plan_match = re.search(r"\b(?:my|our)\s+plan\s+(?:is|=)\s+([a-z][a-z0-9_-]*)", lowered)
    if plan_match:
        plan = plan_match.group(1).split(".")[0].strip().title()
        return f"User says their subscription plan is {plan}.", "plan"

    if "short" in lowered or "concise" in lowered or "brief" in lowered:
        return "User prefers concise support replies.", "preference"

    if "prefer" in lowered or "preference" in lowered:
        return f"User preference: {_trim(message)}", "preference"

    if any(term in lowered for term in ("bug", "error", "broken", "not working", "issue")):
        return f"User reported a support issue: {_trim(message)}", "support_issue"

    return f"Recent support interaction: {_trim(message)}", "conversation"


def _trim(text: str, limit: int = 180) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 3]}..."
