export type Intent =
  | "billing"
  | "bug"
  | "onboarding"
  | "cancellation"
  | "feature_request"
  | "account"
  | "general";

export type ChatRequest = {
  user_id: string;
  message: string;
  conversation_id?: string | null;
  channel?: string;
  account_metadata?: Record<string, unknown>;
  force_escalation?: boolean;
};

export type MemoryRelation = {
  source: string;
  relationship: string;
  target: string;
};

export type MemoryOut = {
  id: string;
  memory: string;
  metadata: Record<string, unknown>;
  categories: string[];
  score: number | null;
  scope?: "thread" | "profile" | null;
};

export type KnowledgeOut = {
  title: string;
  content: string;
  source: string;
  score: number;
};

export type ChatResponse = {
  reply: string;
  intent: Intent;
  used_memories: MemoryOut[];
  memory_relations: MemoryRelation[];
  knowledge_sources: KnowledgeOut[];
  escalation_required: boolean;
  conversation_id: string;
  saved_memory_count: number;
  memory_write_skipped_reason: string | null;
};

export type MemoriesResponse = {
  user_id: string;
  memories: MemoryOut[];
};

export type DeleteResponse = {
  message: string;
  deleted: boolean;
};

export type MarkMemoryResponse = {
  memory: MemoryOut;
  message: string;
};

export type CorrectMemoryResponse = {
  memory: MemoryOut;
  message: string;
  replaced_memory_id: string;
};

export type HealthResponse = {
  status: string;
  live_mem0: boolean;
  live_llm: boolean;
  offline_mode: string;
};

const API_BASE = "/support-api";

export async function getHealth() {
  return requestJson<HealthResponse>("/health");
}

export async function sendChat(request: ChatRequest) {
  return requestJson<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function getMemories(userId: string) {
  return requestJson<MemoriesResponse>(`/memories/${encodeURIComponent(userId)}`);
}

export async function deleteUserMemories(userId: string) {
  return requestJson<DeleteResponse>(`/memories/${encodeURIComponent(userId)}`, {
    method: "DELETE",
  });
}

export async function deleteMemory(userId: string, memoryId: string) {
  return requestJson<DeleteResponse>(
    `/memories/${encodeURIComponent(userId)}/${encodeURIComponent(memoryId)}`,
    {
      method: "DELETE",
    },
  );
}

export async function markMemoryOutdated(userId: string, memoryId: string, reason: string) {
  return requestJson<MarkMemoryResponse>(
    `/memories/${encodeURIComponent(userId)}/${encodeURIComponent(memoryId)}/mark-outdated`,
    {
      method: "PATCH",
      body: JSON.stringify({ reason }),
    },
  );
}

export async function correctMemory(
  userId: string,
  memoryId: string,
  correctedText: string,
  reason: string,
) {
  return requestJson<CorrectMemoryResponse>(
    `/memories/${encodeURIComponent(userId)}/${encodeURIComponent(memoryId)}/correct`,
    {
      method: "POST",
      body: JSON.stringify({ corrected_text: correctedText, reason }),
    },
  );
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });

  if (!response.ok) {
    const detail = await safeReadError(response);
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function safeReadError(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: unknown; message?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
    if (typeof payload.message === "string") return payload.message;
  } catch {
    try {
      return await response.text();
    } catch {
      return "";
    }
  }
  return "";
}
