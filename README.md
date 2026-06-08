# Memory-First Customer Support Agent

Runnable customer support agent demo that combines **Mem0** (persistent user memory), **LangGraph** (workflow orchestration), and **FastAPI** (HTTP API). A **Next.js** frontend provides a full support console; a simpler static HTML UI ships with the backend at `/`.

## How It Works

Every chat message flows through a linear six-step pipeline. The `SupportAgent` in `support_agent/graph.py` orchestrates this via LangGraph (or a sequential fallback when LangGraph is unavailable):

```text
identify_user -> retrieve_memory -> classify_intent -> fetch_knowledge -> respond_or_escalate -> save_memory
```

| Step | What happens |
|------|--------------|
| **identify_user** | Assigns or reuses a `conversation_id` (generates a UUID if none is provided). |
| **retrieve_memory** | Searches Mem0 or the local store for up to 5 relevant memories for the `user_id`. Queries are redacted before search. |
| **classify_intent** | Keyword scoring maps the message to one of seven intents: `billing`, `bug`, `onboarding`, `cancellation`, `feature_request`, `account`, or `general`. |
| **fetch_knowledge** | Token overlap against baked-in policy and playbook entries (billing policy, bug triage, onboarding checklist, etc.). |
| **respond_or_escalate** | If OpenRouter is configured, an LLM replies using memories, knowledge, intent, and escalation context. Otherwise a deterministic rule-based fallback is used. |
| **save_memory** | The user/assistant turn is persisted unless sensitive data was detected. Metadata includes intent, channel, escalation status, and app/agent IDs. |

### Runtime Modes

The app runs in two modes, controlled by `Settings` in `support_agent/config.py` and the `SUPPORT_AGENT_OFFLINE_MODE` env var (`auto`, `true`, or `false`):

| Mode | When | Memory | Replies |
|------|------|--------|---------|
| **Live** | `MEM0_API_KEY` and/or `OPENROUTER_API_KEY` present (with `offline_mode=auto`) | Mem0 cloud via `Mem0MemoryStore` | OpenRouter LLM (Claude Sonnet by default) |
| **Local demo** | Keys absent, or `SUPPORT_AGENT_OFFLINE_MODE=true` | In-process `LocalMemoryStore` | Deterministic template replies in `graph.py` |

### Memory Layer

Mem0 is isolated behind a small `MemoryStore` protocol in `support_agent/memory.py`. The rest of the app depends only on that interface, which keeps tests fast and allows offline operation without credentials.

- **`Mem0MemoryStore`** — Uses the Mem0 `MemoryClient` for search, add, list, delete, and mark-outdated. Memories are scoped by `user_id` and tagged with `run_id` (conversation), `app_id`, and `agent_id`.
- **`LocalMemoryStore`** — In-memory dict keyed by `user_id`. Summarizes messages into categories (`plan`, `preference`, `support_issue`, `conversation`), replaces old plan memories on update, skips outdated entries during search, and ranks by simple term overlap.

### Safety and Escalation

`support_agent/safety.py` and `support_agent/classifier.py` enforce guardrails:

- Passwords, card numbers, API keys, and SSNs are **not stored** (`contains_sensitive_data`).
- Sensitive values are **redacted** before LLM prompts and memory search (`redacted_for_prompt`).
- Conversations are **escalated** when sensitive data or angry/high-risk language is detected, intent is `billing`, account issues involve password/security/2FA, cancellation mentions billing/refunds, recurring bugs use phrases like "still happening", or `force_escalation: true` is sent from the UI.

### API and Frontends

`support_agent/api.py` exposes REST endpoints consumed by both UIs:

- `POST /chat` — Main support conversation.
- `GET /memories/{user_id}` — List stored memories (admin/debug).
- `DELETE /memories/{user_id}` — Privacy wipe for a user.
- `DELETE /memories/{user_id}/{memory_id}` — Delete a single memory.
- `PATCH /memories/{user_id}/{memory_id}/mark-outdated` — Soft-invalidate stale memory.
- `GET /health` — Reports live vs local mode.
- `GET /` — Static browser console.

The Next.js app (`frontend/`) is a three-column console: customer settings and memory admin on the left, chat in the center, and a run inspector (intent, escalation, memory hits, knowledge sources) on the right. API calls go to `/support-api/*`, proxied to the FastAPI backend by `frontend/next.config.ts`.

### Project Layout

```text
support_agent/          # Python backend
  graph.py              # LangGraph workflow + SupportAgent
  memory.py             # Mem0 + local memory stores
  classifier.py         # Intent + escalation rules
  knowledge.py          # Static product knowledge base
  safety.py             # PII detection + redaction
  api.py                # FastAPI routes
  models.py             # Pydantic request/response types
  config.py             # Environment-based settings

frontend/               # Next.js UI
static/                 # Simple HTML/JS fallback UI
tests/                  # Pytest integration tests
```

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

## Next.js Frontend

Install frontend dependencies:

```bash
cd frontend
npm install
```

Configure the backend proxy in `frontend/.env.local`:

```bash
SUPPORT_API_BASE_URL=http://127.0.0.1:8000
```

Run FastAPI and Next.js in separate terminals:

```bash
uv run uvicorn support_agent.api:app --reload
```

```bash
cd frontend
npm run dev
```

Open:

```text
http://localhost:3000
```

The Next app calls the backend through `/support-api/*`, which is proxied to `SUPPORT_API_BASE_URL` by `frontend/next.config.ts`.

Run tests:

```bash
uv run pytest
```

## Demo Prompts

Try these as the same `user_id` to see memory, escalation, and safety in action:

```text
The invoice export is broken in Chrome.
My issue is still happening.
Please keep answers short.
I need onboarding help.
Actually, my plan is Pro now.
What plan am I on?
My password is hunter2.
```

Expected behavior in local demo mode:

- **"Invoice export broken in Chrome"** — `bug` intent; memory saved.
- **"My issue is still happening"** — Retrieves prior bug memory; escalates.
- **"Please keep answers short"** — Preference memory stored; future replies are truncated.
- **"My plan is Pro now"** — Replaces any older plan memory.
- **"My password is hunter2"** — Escalates; nothing is stored.

## Notes

- Sensitive data such as passwords, card numbers, API keys, and SSNs is not stored.
- Billing, security, angry/high-risk messages, and recurring bugs are escalated.
- The local demo store keeps memory only while the app process is running.
