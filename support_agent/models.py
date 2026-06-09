from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Intent = Literal[
    "billing",
    "bug",
    "onboarding",
    "cancellation",
    "feature_request",
    "account",
    "general",
]


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    conversation_id: str | None = None
    channel: str = Field(default="web", min_length=1)
    account_metadata: dict[str, Any] = Field(default_factory=dict)
    force_escalation: bool = False


class MemoryRelation(BaseModel):
    source: str
    relationship: str
    target: str


class MemoryOut(BaseModel):
    id: str
    memory: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    categories: list[str] = Field(default_factory=list)
    score: float | None = None
    scope: Literal["thread", "profile"] | None = None


class KnowledgeOut(BaseModel):
    title: str
    content: str
    source: str
    score: float


class ChatResponse(BaseModel):
    reply: str
    intent: Intent
    used_memories: list[MemoryOut]
    memory_relations: list[MemoryRelation] = Field(default_factory=list)
    knowledge_sources: list[KnowledgeOut]
    escalation_required: bool
    conversation_id: str
    saved_memory_count: int = 0
    memory_write_skipped_reason: str | None = None


class MemoriesResponse(BaseModel):
    user_id: str
    memories: list[MemoryOut]


class DeleteResponse(BaseModel):
    message: str
    deleted: bool = True


class MarkMemoryRequest(BaseModel):
    reason: str = Field(default="Marked outdated by support admin")


class MarkMemoryResponse(BaseModel):
    memory: MemoryOut
    message: str


class CorrectMemoryRequest(BaseModel):
    corrected_text: str = Field(..., min_length=1)
    reason: str = Field(default="Corrected by support admin")


class CorrectMemoryResponse(BaseModel):
    memory: MemoryOut
    message: str
    replaced_memory_id: str
