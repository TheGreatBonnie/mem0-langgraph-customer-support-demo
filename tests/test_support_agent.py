from __future__ import annotations

from fastapi.testclient import TestClient

from support_agent.api import create_app
from support_agent.config import Settings
from support_agent.graph import SupportAgent
from support_agent.memory import LocalMemoryStore
from support_agent.models import ChatRequest


def make_agent() -> SupportAgent:
    settings = Settings(
        openrouter_api_key=None,
        mem0_api_key=None,
        offline_mode="true",
    )
    return SupportAgent(settings=settings, memory_store=LocalMemoryStore())


def test_returning_customer_issue_uses_memory_and_escalates():
    agent = make_agent()

    first = agent.chat(
        ChatRequest(
            user_id="alice",
            message="The invoice export is broken in Chrome.",
            conversation_id="ticket-1",
        )
    )
    assert first.intent == "bug"
    assert first.saved_memory_count == 1

    second = agent.chat(
        ChatRequest(
            user_id="alice",
            message="My issue is still happening.",
            conversation_id="ticket-2",
        )
    )
    assert second.intent == "bug"
    assert second.escalation_required is True
    assert second.used_memories
    assert "previous support issue" in second.reply


def test_sensitive_data_is_not_stored():
    agent = make_agent()

    response = agent.chat(
        ChatRequest(
            user_id="alice",
            message="My password is hunter2 and my card number is 4242 4242 4242 4242.",
        )
    )

    assert response.escalation_required is True
    assert response.saved_memory_count == 0
    assert response.memory_write_skipped_reason == "Sensitive data was detected and not stored."
    assert agent.memory_store.list_user_memories("alice") == []


def test_plan_updates_replace_older_local_plan_memory():
    agent = make_agent()

    agent.chat(ChatRequest(user_id="alice", message="My plan is Basic."))
    agent.chat(ChatRequest(user_id="alice", message="Actually, my plan is Pro now."))

    memories = agent.memory_store.list_user_memories("alice")
    plan_memories = [memory for memory in memories if memory.metadata.get("category") == "plan"]
    assert len(plan_memories) == 1
    assert "Pro" in plan_memories[0].memory
    assert "Basic" not in plan_memories[0].memory


def test_preference_memory_affects_future_replies():
    agent = make_agent()

    agent.chat(ChatRequest(user_id="alice", message="Please keep answers short."))
    response = agent.chat(ChatRequest(user_id="alice", message="I need onboarding help."))

    assert response.used_memories
    assert any("concise" in memory.memory for memory in response.used_memories)
    assert response.reply.count(".") <= 2


def test_chat_api_and_memory_admin_controls():
    agent = make_agent()
    client = TestClient(create_app(agent))

    chat_response = client.post(
        "/chat",
        json={
            "user_id": "alice",
            "message": "The dashboard has an error on export.",
            "conversation_id": "api-ticket",
        },
    )
    assert chat_response.status_code == 200
    payload = chat_response.json()
    assert payload["intent"] == "bug"
    assert payload["conversation_id"] == "api-ticket"

    memories = client.get("/memories/alice")
    assert memories.status_code == 200
    memory_id = memories.json()["memories"][0]["id"]

    outdated = client.patch(
        f"/memories/alice/{memory_id}/mark-outdated",
        json={"reason": "Test correction"},
    )
    assert outdated.status_code == 200
    assert outdated.json()["memory"]["metadata"]["status"] == "outdated"

    deleted = client.delete("/memories/alice")
    assert deleted.status_code == 200
    assert client.get("/memories/alice").json()["memories"] == []


def test_thread_scoped_memory_is_returned_in_same_conversation():
    agent = make_agent()

    first = agent.chat(
        ChatRequest(
            user_id="alice",
            message="The export button fails in Safari.",
            conversation_id="ticket-thread",
        )
    )
    second = agent.chat(
        ChatRequest(
            user_id="alice",
            message="It still fails after refresh.",
            conversation_id="ticket-thread",
        )
    )

    assert first.saved_memory_count == 1
    assert second.used_memories
    assert any(memory.scope == "thread" for memory in second.used_memories)


def test_outdated_memory_is_excluded_from_retrieval():
    agent = make_agent()

    first = agent.chat(
        ChatRequest(
            user_id="alice",
            message="The dashboard export is broken.",
            conversation_id="ticket-a",
        )
    )
    memory_id = agent.memory_store.list_user_memories("alice")[0].id
    agent.memory_store.mark_memory_outdated("alice", memory_id, "No longer relevant")

    second = agent.chat(
        ChatRequest(
            user_id="alice",
            message="The dashboard export is broken again.",
            conversation_id="ticket-b",
        )
    )

    assert not any(memory.id == memory_id for memory in second.used_memories)


def test_correct_memory_replaces_stored_fact():
    agent = make_agent()
    client = TestClient(create_app(agent))

    agent.chat(ChatRequest(user_id="alice", message="My plan is Basic."))
    memory_id = agent.memory_store.list_user_memories("alice")[0].id

    corrected = client.post(
        f"/memories/alice/{memory_id}/correct",
        json={
            "corrected_text": "User says their subscription plan is Pro.",
            "reason": "Customer upgraded",
        },
    )
    assert corrected.status_code == 200
    payload = corrected.json()
    assert payload["replaced_memory_id"] == memory_id
    assert "Pro" in payload["memory"]["memory"]

    memories = client.get("/memories/alice").json()["memories"]
    assert len(memories) == 1
    assert "Basic" not in memories[0]["memory"]
