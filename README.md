# Memory-First Customer Support Agent

Runnable customer support agent demo that combines **Mem0** (persistent user memory), **LangGraph** (workflow orchestration), and **FastAPI** (HTTP API). A **Next.js** frontend provides a full support console; a simpler static HTML UI ships with the backend at `/`.

## How It Works

Every chat message flows through a linear six-step pipeline. The `SupportAgent` in `support_agent/graph.py` orchestrates this via LangGraph (or a sequential fallback when LangGraph is unavailable):

```text
identify_user -> classify_intent -> retrieve_memory -> fetch_knowledge -> respond_or_escalate -> save_memory
```

| Step | What happens |
|------|--------------|
| **identify_user** | Assigns or reuses a `conversation_id` (generates a UUID if none is provided). |
| **classify_intent** | Keyword scoring maps the message to one of seven intents: `billing`, `bug`, `onboarding`, `cancellation`, `feature_request`, `account`, or `general`. |
| **retrieve_memory** | Multi-scope Mem0 search: thread memories (`run_id`) plus profile memories (`user_id`), with intent-aware queries, reranking, keyword search, and outdated filtering. |
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

- **`Mem0MemoryStore`** — Uses the Mem0 `MemoryClient` with enhanced retrieval (`rerank`, `keyword_search`, `threshold`, optional `enable_graph`), multi-scope search (thread + profile), selective `infer` for explicit facts, and delete-and-re-add correction via `correct_memory`.
- **`LocalMemoryStore`** — In-memory dict keyed by `user_id` with the same `search_for_context` interface. Summarizes messages into categories (`plan`, `preference`, `support_issue`, `conversation`), replaces old plan memories on update, skips outdated entries during search, and ranks by term overlap with intent/category hints.

#### Mem0 configuration

Tune live Mem0 behavior in `.env`:

```bash
MEM0_ENABLE_GRAPH=false        # include entity relations on add/search
MEM0_SEARCH_RERANK=true        # rerank semantic hits
MEM0_SEARCH_KEYWORD=true       # blend keyword search for exact terms
MEM0_SEARCH_THRESHOLD=0.3      # minimum similarity score
MEM0_THREAD_TOP_K=3            # per-conversation memory hits
MEM0_PROFILE_TOP_K=5           # cross-session customer memory hits
```

For best extraction quality in production, also configure **custom categories** and **custom instructions** in the Mem0 project dashboard (for example: `subscription_plan`, `open_support_issue`, `communication_preference`).

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
- `POST /memories/{user_id}/{memory_id}/correct` — Delete the old memory and store a corrected fact with `infer=false`.
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

Use the same `user_id` (for example `alice`) across prompts so memory carries over. Open the Next.js UI at `http://localhost:3000` or the static UI at `http://127.0.0.1:8000`. Watch the **Agent Run** panel for intent, memory scope, escalation, and linked entities.

### Full demo script

Use `conversation_id: demo-session-1` for steps 1–5, then switch to `demo-session-2` for step 6.

| # | Prompt | What to verify |
|---|--------|----------------|
| 1 | `The invoice export is broken in Chrome.` | Intent: `bug`; memory saved |
| 2 | `It still fails after refresh.` | Thread-scoped memory hit |
| 3 | `Please keep answers short.` | Preference saved |
| 4 | `I need onboarding help.` | Shorter reply; preference in memory hits |
| 5 | `Actually, my plan is Pro now.` | Plan memory updated |
| 6 | `My issue is still happening.` | Profile memory from step 1; escalation required |
| 7 | `What plan am I on?` | Reply recalls Pro |
| 8 | `My password is hunter2.` | Escalation required; no memory stored |

### Multi-scope memory (thread + profile)

**Conversation A** — keep the same `conversation_id` (for example `ticket-export-1`):

```text
The invoice export is broken in Chrome.
It still fails after I refresh the page.
```

Check the run inspector: memory hits should show **thread** scope.

**Conversation B** — use a new `conversation_id` (for example `ticket-billing-2`):

```text
My issue is still happening.
```

Check the run inspector: you should see **profile** scope (prior bug from Conversation A) and escalation.

### Intent-aware retrieval

```text
The dashboard export throws an error in Safari.
I need onboarding help for my workspace.
I was charged twice on my last invoice.
```

Confirm intent (`bug`, `onboarding`, `billing`) and that memory/knowledge hits align in the run inspector.

### Preference memory

```text
Please keep answers short.
I need onboarding help.
```

Expected: shorter reply; run inspector shows a preference memory hit with **profile** scope.

### Plan memory and replacement

```text
My plan is Basic.
Actually, my plan is Pro now.
What plan am I on?
```

Expected: only **Pro** in the Memories panel; the agent references Pro in its reply.

### Escalation and recurring bugs

```text
The invoice export is broken in Chrome.
```

Then in a new conversation:

```text
My issue is still happening.
```

Expected: **Escalation: Required** in the run inspector.

### Sensitive data (no storage)

```text
My password is hunter2 and my card number is 4242 4242 4242 4242.
```

Expected: escalation required, **Saved: 0** (or a skip reason), and no new memories in the Memories panel.

### Correct memory (UI: Correct button)

```text
My plan is Basic.
```

In Memories, click **Correct** on that memory and enter:

```text
User says their subscription plan is Enterprise.
```

Then chat:

```text
What plan am I on?
```

Expected: **Enterprise** in memories and in the reply; **Basic** is gone.

### Mark outdated (excluded from retrieval)

```text
The export button fails when I click it.
```

In Memories, click **Outdated** on that memory. Then send:

```text
The export button fails when I click it again.
```

Expected: the outdated memory does **not** appear in **Memory Hits**.

### Linked entities (live Mem0 with graph)

Set in `.env` and restart the backend:

```bash
MEM0_ENABLE_GRAPH=true
```

Then:

```text
The invoice export is broken in Chrome on my Pro workspace.
Actually, my plan is Pro now.
```

Check the **Linked Entities** section in the run inspector. With live Mem0 and graph enabled, relations come from Mem0; in local demo mode, relations are derived for support issues and plans.

### Force escalation

Enable **Force escalation** in the customer panel, then:

```text
Can you help me reset my notification settings?
```

Expected: escalation required even for a low-risk message.

### Live Mem0 vs local demo

| Mode | How to tell |
|------|-------------|
| **Local demo** | Status pill shows "Local demo"; graph relations are synthetic |
| **Live Mem0** | Status pill shows "Live services"; rerank, keyword, and graph use real Mem0 APIs |

For live mode, set `MEM0_API_KEY` and keep `SUPPORT_AGENT_OFFLINE_MODE` unset or set to `auto`. Optional tuning:

```bash
MEM0_SEARCH_RERANK=true
MEM0_SEARCH_KEYWORD=true
MEM0_THREAD_TOP_K=3
MEM0_PROFILE_TOP_K=5
MEM0_ENABLE_GRAPH=true
```

## Notes

- Sensitive data such as passwords, card numbers, API keys, and SSNs is not stored.
- Billing, security, angry/high-risk messages, and recurring bugs are escalated.
- The local demo store keeps memory only while the app process is running.
