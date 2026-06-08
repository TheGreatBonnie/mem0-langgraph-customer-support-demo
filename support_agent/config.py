from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is declared for the app runtime
    load_dotenv = None


if load_dotenv:
    load_dotenv()


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str | None
    mem0_api_key: str | None
    openrouter_model: str = "anthropic/claude-sonnet-4.5"
    app_id: str = "memory-first-support-demo"
    agent_id: str = "memory-first-support-agent"
    offline_mode: str = "auto"

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
    )
