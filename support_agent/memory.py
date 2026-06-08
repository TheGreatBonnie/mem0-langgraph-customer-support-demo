from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from support_agent.config import Settings
from support_agent.models import MemoryOut
from support_agent.safety import contains_sensitive_data


class MemoryStore(Protocol):
    def search(self, query: str, user_id: str, top_k: int = 5) -> list[MemoryOut]:
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
        response = self.client.search(query, filters={"user_id": user_id}, top_k=top_k)
        return _normalize_memories(response)[:top_k]

    def add_interaction(
        self,
        *,
        user_id: str,
        conversation_id: str,
        user_message: str,
        assistant_reply: str,
        metadata: dict[str, Any],
    ) -> int:
        response = self.client.add(
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_reply},
            ],
            user_id=user_id,
            run_id=conversation_id,
            agent_id=self.settings.agent_id,
            app_id=self.settings.app_id,
            metadata=metadata,
        )
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

    def _assert_user_memory(self, user_id: str, memory_id: str) -> MemoryOut:
        for memory in self.list_user_memories(user_id):
            if memory.id == memory_id:
                return memory
        raise KeyError(f"Memory {memory_id} was not found for user {user_id}.")


class LocalMemoryStore:
    def __init__(self):
        self._memories: dict[str, list[MemoryOut]] = {}

    def search(self, query: str, user_id: str, top_k: int = 5) -> list[MemoryOut]:
        query_terms = _terms(query)
        ranked: list[MemoryOut] = []
        for memory in self._memories.get(user_id, []):
            if memory.metadata.get("status") == "outdated":
                continue
            memory_terms = _terms(memory.memory)
            score = len(query_terms & memory_terms)
            if memory.metadata.get("category") == "preference":
                score = max(score, 0.5)
            if score > 0:
                ranked.append(memory.model_copy(update={"score": float(score)}))
        ranked.sort(
            key=lambda item: (item.score or 0.0, item.metadata.get("created_at", "")),
            reverse=True,
        )
        return ranked[:top_k]

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
