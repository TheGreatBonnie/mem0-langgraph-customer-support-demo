# Memory-First Customer Support Agent

Runnable customer support agent demo using Mem0 for persistent memory and LangGraph for workflow orchestration.

The app works in two modes:

- Live mode when `MEM0_API_KEY` and `OPENROUTER_API_KEY` are present.
- Local demo mode when keys are absent, using an in-memory store and deterministic support replies.

## What It Builds

- `POST /chat` support endpoint with intent, escalation, memory hits, and knowledge sources.
- `GET /memories/{user_id}` admin/debug memory view.
- `DELETE /memories/{user_id}` privacy delete endpoint.
- `DELETE /memories/{user_id}/{memory_id}` single-memory delete endpoint.
- `PATCH /memories/{user_id}/{memory_id}/mark-outdated` memory correction endpoint.
- Browser console at `/` with chat, memory inspection, delete, mark-outdated, and force escalation controls.

## Setup

```bash
cp .env.example .env
```

Fill in real keys in `.env` for live service calls:

```bash
OPENROUTER_API_KEY=...
MEM0_API_KEY=...
OPENROUTER_MODEL=anthropic/claude-sonnet-4.5
```

Run the app:

```bash
uv run uvicorn support_agent.api:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

Run tests:

```bash
uv run pytest
```

## Demo Prompts

Try these as the same `user_id`:

```text
The invoice export is broken in Chrome.
My issue is still happening.
Please keep answers short.
I need onboarding help.
Actually, my plan is Pro now.
What plan am I on?
My password is hunter2.
```

## Architecture

The LangGraph flow is:

```text
identify_user -> retrieve_memory -> classify_intent -> fetch_knowledge -> respond_or_escalate -> save_memory
```

Mem0 is isolated in `support_agent/memory.py`, so the rest of the app only depends on a small `MemoryStore` interface. That keeps tests fast and lets the app fall back locally when credentials are not configured.

## Notes

- Sensitive data such as passwords, card numbers, API keys, and SSNs is not stored.
- Billing, security, angry/high-risk messages, and recurring bugs are escalated.
- The local demo store keeps memory only while the app process is running.
