from __future__ import annotations

from typing import Any, TypedDict
from uuid import uuid4

from support_agent.classifier import classify_intent, should_escalate
from support_agent.config import Settings, get_settings
from support_agent.knowledge import KnowledgeBase
from support_agent.memory import MemoryStore, create_memory_store
from support_agent.models import ChatRequest, ChatResponse, Intent, KnowledgeOut, MemoryOut
from support_agent.safety import contains_sensitive_data, redacted_for_prompt


class SupportState(TypedDict, total=False):
    user_id: str
    message: str
    conversation_id: str
    channel: str
    account_metadata: dict[str, Any]
    force_escalation: bool
    memories: list[MemoryOut]
    knowledge_sources: list[KnowledgeOut]
    intent: Intent
    escalation_required: bool
    reply: str
    saved_memory_count: int
    memory_write_skipped_reason: str | None
    memory_error: str | None


class SupportAgent:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        memory_store: MemoryStore | None = None,
        knowledge_base: KnowledgeBase | None = None,
    ):
        self.settings = settings or get_settings()
        self.memory_store = memory_store or create_memory_store(self.settings)
        self.knowledge_base = knowledge_base or KnowledgeBase()
        self.llm = self._build_llm()
        self.graph = self._build_graph()

    def chat(self, request: ChatRequest) -> ChatResponse:
        initial_state: SupportState = {
            "user_id": request.user_id,
            "message": request.message,
            "conversation_id": request.conversation_id or "",
            "channel": request.channel,
            "account_metadata": request.account_metadata,
            "force_escalation": request.force_escalation,
            "saved_memory_count": 0,
            "memory_write_skipped_reason": None,
        }
        result = self.graph.invoke(initial_state)
        return ChatResponse(
            reply=result["reply"],
            intent=result["intent"],
            used_memories=result.get("memories", []),
            knowledge_sources=result.get("knowledge_sources", []),
            escalation_required=result["escalation_required"],
            conversation_id=result["conversation_id"],
            saved_memory_count=result.get("saved_memory_count", 0),
            memory_write_skipped_reason=result.get("memory_write_skipped_reason"),
        )

    def _build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            return _SequentialGraph(
                [
                    self._identify_user,
                    self._retrieve_memory,
                    self._classify,
                    self._fetch_knowledge,
                    self._respond_or_escalate,
                    self._save_memory,
                ]
            )

        workflow = StateGraph(SupportState)
        workflow.add_node("identify_user", self._identify_user)
        workflow.add_node("retrieve_memory", self._retrieve_memory)
        workflow.add_node("classify_intent", self._classify)
        workflow.add_node("fetch_knowledge", self._fetch_knowledge)
        workflow.add_node("respond_or_escalate", self._respond_or_escalate)
        workflow.add_node("save_memory", self._save_memory)

        workflow.add_edge(START, "identify_user")
        workflow.add_edge("identify_user", "retrieve_memory")
        workflow.add_edge("retrieve_memory", "classify_intent")
        workflow.add_edge("classify_intent", "fetch_knowledge")
        workflow.add_edge("fetch_knowledge", "respond_or_escalate")
        workflow.add_edge("respond_or_escalate", "save_memory")
        workflow.add_edge("save_memory", END)
        return workflow.compile()

    def _identify_user(self, state: SupportState) -> SupportState:
        conversation_id = state.get("conversation_id") or f"support-{uuid4()}"
        return {"conversation_id": conversation_id}

    def _retrieve_memory(self, state: SupportState) -> SupportState:
        try:
            memories = self.memory_store.search(
                redacted_for_prompt(state["message"]),
                user_id=state["user_id"],
                top_k=5,
            )
            return {"memories": memories, "memory_error": None}
        except Exception as exc:
            return {"memories": [], "memory_error": str(exc)}

    def _classify(self, state: SupportState) -> SupportState:
        intent = classify_intent(state["message"])
        escalation_required = should_escalate(
            state["message"],
            intent,
            force=state.get("force_escalation", False),
        )
        return {"intent": intent, "escalation_required": escalation_required}

    def _fetch_knowledge(self, state: SupportState) -> SupportState:
        query = f"{state['intent']} {state['message']}"
        return {"knowledge_sources": self.knowledge_base.search(query)}

    def _respond_or_escalate(self, state: SupportState) -> SupportState:
        if self.llm:
            try:
                reply = self._llm_reply(state)
                return {"reply": reply}
            except Exception:
                pass
        return {"reply": self._fallback_reply(state)}

    def _save_memory(self, state: SupportState) -> SupportState:
        if contains_sensitive_data(state["message"]):
            return {
                "saved_memory_count": 0,
                "memory_write_skipped_reason": "Sensitive data was detected and not stored.",
            }

        try:
            saved_count = self.memory_store.add_interaction(
                user_id=state["user_id"],
                conversation_id=state["conversation_id"],
                user_message=state["message"],
                assistant_reply=state["reply"],
                metadata={
                    "intent": state["intent"],
                    "channel": state["channel"],
                    "escalation_required": state["escalation_required"],
                    "app_id": self.settings.app_id,
                    "agent_id": self.settings.agent_id,
                },
            )
            return {"saved_memory_count": saved_count, "memory_write_skipped_reason": None}
        except Exception as exc:
            return {"saved_memory_count": 0, "memory_write_skipped_reason": str(exc)}

    def _build_llm(self):
        if not self.settings.use_live_llm:
            return None
        try:
            from langchain_openrouter import ChatOpenRouter

            return ChatOpenRouter(
                model=self.settings.openrouter_model,
                temperature=0.2,
                max_retries=2,
            )
        except Exception:
            if self.settings.offline_mode.lower() == "false":
                raise
            return None

    def _llm_reply(self, state: SupportState) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        memories = "\n".join(f"- {memory.memory}" for memory in state.get("memories", []))
        knowledge = "\n".join(
            f"- {source.title}: {source.content}" for source in state.get("knowledge_sources", [])
        )
        escalation = "yes" if state["escalation_required"] else "no"
        system = f"""You are a memory-first customer support assistant.
Use retrieved memory for continuity, but do not expose raw private memory unless the user directly asks.
Ask before assuming facts. Save-worthy facts are handled after the reply, so focus on helping.
Escalation required: {escalation}.
Detected intent: {state['intent']}.

Relevant customer memory:
{memories or "- none"}

Support knowledge:
{knowledge or "- none"}
"""
        message = redacted_for_prompt(state["message"])
        result = self.llm.invoke([SystemMessage(content=system), HumanMessage(content=message)])
        return str(result.content)

    def _fallback_reply(self, state: SupportState) -> str:
        memories = state.get("memories", [])
        knowledge_sources = state.get("knowledge_sources", [])
        intent = state["intent"]
        concise = _prefers_concise(memories)
        context_sentence = _memory_context_sentence(memories, state["message"])
        knowledge_sentence = _knowledge_sentence(knowledge_sources)

        if contains_sensitive_data(state["message"]):
            return (
                "For your safety, please do not share passwords, card numbers, API keys, "
                "or one-time codes here. I will not store that information, and I am routing "
                "this to secure support."
            )

        if state["escalation_required"]:
            base = "I am going to route this to a human support teammate."
            if intent == "billing":
                detail = "Please share the invoice ID and charge date, but not card details."
            elif intent == "bug":
                detail = "Please send the affected feature, expected behavior, actual behavior, and app version."
            elif intent == "account":
                detail = "Please use the secure account portal for verification details."
            else:
                detail = "Please add any ticket ID or recent error message that helps them continue quickly."
            parts = [base, context_sentence, detail]
            return _join_reply(parts, concise)

        intent_guidance = {
            "bug": "Let us collect the affected feature, expected behavior, actual behavior, and version so we can narrow it down.",
            "onboarding": "Start by connecting the workspace, inviting teammates, and completing one successful workflow.",
            "cancellation": "I can help capture the reason, preserve data export options, and route billing changes if needed.",
            "feature_request": "I will capture the workflow, business impact, urgency, and current workaround for product review.",
            "account": "For account questions, avoid sharing secrets here and use the secure portal for verification.",
            "billing": "Billing requests should be reviewed by a specialist, so I can collect invoice context and route it.",
            "general": "I can help. Tell me what you expected, what happened, and any relevant account or product context.",
        }
        parts = [context_sentence, knowledge_sentence, intent_guidance[intent]]
        return _join_reply(parts, concise)


class _SequentialGraph:
    def __init__(self, nodes):
        self.nodes = nodes

    def invoke(self, initial_state: SupportState) -> SupportState:
        state = dict(initial_state)
        for node in self.nodes:
            state.update(node(state))
        return state


def _prefers_concise(memories: list[MemoryOut]) -> bool:
    return any("concise" in memory.memory.lower() or "short" in memory.memory.lower() for memory in memories)


def _memory_context_sentence(memories: list[MemoryOut], message: str) -> str:
    if not memories:
        return ""
    lowered_message = message.lower()
    for memory in memories:
        lowered_memory = memory.memory.lower()
        if "plan is" in lowered_memory and "plan" in lowered_message:
            plan = lowered_memory.split("plan is", 1)[1].strip(" .")
            return f"I see saved account context that your plan is {plan.title()}."
        if "support issue" in lowered_memory:
            return "I found a previous support issue that may be related, so I will keep that context attached."
    return "I found relevant customer context and will use it for continuity."


def _knowledge_sentence(knowledge_sources: list[KnowledgeOut]) -> str:
    if not knowledge_sources:
        return ""
    source = knowledge_sources[0]
    return source.content


def _join_reply(parts: list[str], concise: bool) -> str:
    clean_parts = [part for part in parts if part]
    if concise and len(clean_parts) > 2:
        clean_parts = clean_parts[:2]
    return " ".join(clean_parts)
