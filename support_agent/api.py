from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from support_agent.graph import SupportAgent
from support_agent.models import (
    ChatRequest,
    ChatResponse,
    DeleteResponse,
    MarkMemoryRequest,
    MarkMemoryResponse,
    MemoriesResponse,
)


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"


def create_app(agent: SupportAgent | None = None) -> FastAPI:
    support_agent = agent or SupportAgent()
    app = FastAPI(
        title="Memory-First Customer Support Agent",
        version="0.1.0",
        description="Customer support agent demo using Mem0 memory and LangGraph orchestration.",
    )
    app.state.agent = support_agent

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    def health():
        settings = app.state.agent.settings
        return {
            "status": "ok",
            "live_mem0": settings.use_live_mem0,
            "live_llm": settings.use_live_llm,
            "offline_mode": settings.offline_mode,
        }

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest):
        return app.state.agent.chat(request)

    @app.get("/memories/{user_id}", response_model=MemoriesResponse)
    def get_memories(user_id: str):
        try:
            memories = app.state.agent.memory_store.list_user_memories(user_id)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Memory lookup failed: {exc}") from exc
        return MemoriesResponse(user_id=user_id, memories=memories)

    @app.delete("/memories/{user_id}", response_model=DeleteResponse)
    def delete_user_memories(user_id: str):
        try:
            app.state.agent.memory_store.delete_user_memories(user_id)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Memory deletion failed: {exc}") from exc
        return DeleteResponse(message=f"Deleted memories for user {user_id}.")

    @app.delete("/memories/{user_id}/{memory_id}", response_model=DeleteResponse)
    def delete_memory(user_id: str, memory_id: str):
        try:
            app.state.agent.memory_store.delete_memory(user_id, memory_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Memory deletion failed: {exc}") from exc
        return DeleteResponse(message=f"Deleted memory {memory_id}.")

    @app.patch("/memories/{user_id}/{memory_id}/mark-outdated", response_model=MarkMemoryResponse)
    def mark_memory_outdated(user_id: str, memory_id: str, request: MarkMemoryRequest):
        try:
            memory = app.state.agent.memory_store.mark_memory_outdated(
                user_id=user_id,
                memory_id=memory_id,
                reason=request.reason,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Memory update failed: {exc}") from exc
        return MarkMemoryResponse(memory=memory, message=f"Marked memory {memory_id} outdated.")

    return app


app = create_app()
