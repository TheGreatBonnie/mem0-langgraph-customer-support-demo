const userIdInput = document.querySelector("#user-id");
const channelInput = document.querySelector("#channel");
const conversationInput = document.querySelector("#conversation-id");
const forceEscalationInput = document.querySelector("#force-escalation");
const chatForm = document.querySelector("#chat-form");
const messageInput = document.querySelector("#message");
const chatLog = document.querySelector("#chat-log");
const memoryList = document.querySelector("#memory-list");
const refreshMemoriesButton = document.querySelector("#refresh-memories");
const deleteAllMemoriesButton = document.querySelector("#delete-all-memories");
const statusPill = document.querySelector("#service-status");
const intentBadge = document.querySelector("#intent-badge");
const escalationValue = document.querySelector("#escalation-value");
const savedValue = document.querySelector("#saved-value");
const conversationValue = document.querySelector("#conversation-value");
const memoryHits = document.querySelector("#memory-hits");
const knowledgeHits = document.querySelector("#knowledge-hits");

const storedConversation = window.localStorage.getItem("support-conversation-id");
conversationInput.value = storedConversation || `demo-${crypto.randomUUID()}`;
window.localStorage.setItem("support-conversation-id", conversationInput.value);

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;

  appendMessage(message, "user");
  messageInput.value = "";
  setBusy(true);

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userIdInput.value.trim() || "alice",
        message,
        conversation_id: conversationInput.value.trim(),
        channel: channelInput.value,
        force_escalation: forceEscalationInput.checked,
      }),
    });

    if (!response.ok) {
      throw new Error(await response.text());
    }

    const payload = await response.json();
    conversationInput.value = payload.conversation_id;
    window.localStorage.setItem("support-conversation-id", payload.conversation_id);
    appendMessage(payload.reply, "agent");
    renderRun(payload);
    await loadMemories();
  } catch (error) {
    appendMessage(`Request failed: ${error.message}`, "error");
  } finally {
    setBusy(false);
    messageInput.focus();
  }
});

refreshMemoriesButton.addEventListener("click", () => loadMemories());

deleteAllMemoriesButton.addEventListener("click", async () => {
  const userId = currentUserId();
  if (!window.confirm(`Delete all memories for ${userId}?`)) return;
  await fetch(`/memories/${encodeURIComponent(userId)}`, { method: "DELETE" });
  await loadMemories();
});

userIdInput.addEventListener("change", () => loadMemories());

async function checkHealth() {
  try {
    const response = await fetch("/health");
    const health = await response.json();
    statusPill.textContent = health.live_mem0 || health.live_llm ? "Live services" : "Local demo";
  } catch {
    statusPill.textContent = "Offline";
  }
}

async function loadMemories() {
  memoryList.innerHTML = renderEmpty("Loading");
  try {
    const response = await fetch(`/memories/${encodeURIComponent(currentUserId())}`);
    if (!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    renderMemories(payload.memories);
  } catch (error) {
    memoryList.innerHTML = renderEmpty(error.message);
  }
}

function renderMemories(memories) {
  if (!memories.length) {
    memoryList.innerHTML = renderEmpty("No memories");
    return;
  }

  memoryList.innerHTML = "";
  for (const memory of memories) {
    const item = document.createElement("article");
    item.className = `memory-item ${memory.metadata?.status === "outdated" ? "outdated" : ""}`;
    item.innerHTML = `
      <p class="memory-text"></p>
      <div class="meta-row">
        <span class="meta-chip">${escapeHtml(memory.metadata?.category || memory.categories?.[0] || "memory")}</span>
        <span class="meta-chip">${escapeHtml(memory.metadata?.status || "active")}</span>
      </div>
      <div class="memory-actions">
        <button class="memory-action" type="button" data-action="outdated">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>
          Outdated
        </button>
        <button class="memory-action danger" type="button" data-action="delete">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2m-9 0 1 14h8l1-14M10 11v5m4-5v5"/></svg>
          Delete
        </button>
      </div>
    `;
    item.querySelector(".memory-text").textContent = memory.memory;
    item.querySelector('[data-action="outdated"]').addEventListener("click", () => markOutdated(memory.id));
    item.querySelector('[data-action="delete"]').addEventListener("click", () => deleteMemory(memory.id));
    memoryList.appendChild(item);
  }
}

async function markOutdated(memoryId) {
  const reason = window.prompt("Reason", "Marked outdated by support admin");
  if (reason === null) return;
  await fetch(`/memories/${encodeURIComponent(currentUserId())}/${encodeURIComponent(memoryId)}/mark-outdated`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  await loadMemories();
}

async function deleteMemory(memoryId) {
  await fetch(`/memories/${encodeURIComponent(currentUserId())}/${encodeURIComponent(memoryId)}`, {
    method: "DELETE",
  });
  await loadMemories();
}

function renderRun(payload) {
  intentBadge.textContent = titleCase(payload.intent);
  escalationValue.textContent = payload.escalation_required ? "Required" : "No";
  savedValue.textContent = payload.memory_write_skipped_reason
    ? payload.memory_write_skipped_reason
    : `${payload.saved_memory_count}`;
  conversationValue.textContent = payload.conversation_id;
  renderEvidence(memoryHits, payload.used_memories, "memory");
  renderEvidence(knowledgeHits, payload.knowledge_sources, "knowledge");
}

function renderEvidence(container, items, kind) {
  if (!items.length) {
    container.innerHTML = renderEmpty(kind === "memory" ? "No memory hits" : "No knowledge hits");
    return;
  }
  container.innerHTML = "";
  for (const item of items) {
    const block = document.createElement("article");
    block.className = "evidence-item";
    const title = kind === "memory" ? item.memory : item.title;
    const body = kind === "memory" ? item.metadata?.category || "memory" : item.content;
    block.innerHTML = `
      <p class="evidence-title"></p>
      <div class="meta-row">
        <span class="meta-chip"></span>
        ${item.score ? `<span class="meta-chip">score ${item.score}</span>` : ""}
      </div>
    `;
    block.querySelector(".evidence-title").textContent = title;
    block.querySelector(".meta-chip").textContent = body;
    container.appendChild(block);
  }
}

function appendMessage(text, role) {
  const message = document.createElement("div");
  message.className = `message ${role}`;
  message.textContent = text;
  chatLog.appendChild(message);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function setBusy(isBusy) {
  chatForm.querySelector("button").disabled = isBusy;
  statusPill.textContent = isBusy ? "Running" : statusPill.textContent;
}

function currentUserId() {
  return userIdInput.value.trim() || "alice";
}

function renderEmpty(text) {
  return `<p class="empty-state">${escapeHtml(text)}</p>`;
}

function titleCase(value) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

appendMessage("Hi, I am ready to help with support questions and remember useful context.", "agent");
checkHealth();
loadMemories();
