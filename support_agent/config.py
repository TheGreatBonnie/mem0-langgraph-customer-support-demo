from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is declared for the app runtime
    load_dotenv = None


if load_dotenv:
    load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str | None
    mem0_api_key: str | None
    openrouter_model: str = "anthropic/claude-sonnet-4.5"
    app_id: str = "memory-first-support-demo"
    agent_id: str = "memory-first-support-agent"
    offline_mode: str = "auto"
    mem0_enable_graph: bool = False
    mem0_search_rerank: bool = True
    mem0_search_keyword: bool = True
    mem0_search_threshold: float = 0.3
    mem0_thread_top_k: int = 3
    mem0_profile_top_k: int = 5

    @property
    def use_live_mem0(self) -> bool:
        if self.offline_mode.lower() == "true":
            return False
        if self.offline_mode.lower() == "false":
            return True
        return bool(self.mem0_api_key)

    @property
    def use_live_llm(self) -> bool:
        if self.offline_mode.lower() == "true":
            return False
        if self.offline_mode.lower() == "false":
            return True
        return bool(self.openrouter_api_key)


def get_settings() -> Settings:
    return Settings(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY") or None,
        mem0_api_key=os.getenv("MEM0_API_KEY") or None,
        openrouter_model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5"),
        app_id=os.getenv("SUPPORT_AGENT_APP_ID", "memory-first-support-demo"),
        agent_id=os.getenv("SUPPORT_AGENT_ID", "memory-first-support-agent"),
        offline_mode=os.getenv("SUPPORT_AGENT_OFFLINE_MODE", "auto"),
        mem0_enable_graph=_env_bool("MEM0_ENABLE_GRAPH", False),
        mem0_search_rerank=_env_bool("MEM0_SEARCH_RERANK", True),
        mem0_search_keyword=_env_bool("MEM0_SEARCH_KEYWORD", True),
        mem0_search_threshold=_env_float("MEM0_SEARCH_THRESHOLD", 0.3),
        mem0_thread_top_k=_env_int("MEM0_THREAD_TOP_K", 3),
        mem0_profile_top_k=_env_int("MEM0_PROFILE_TOP_K", 5),
    )
