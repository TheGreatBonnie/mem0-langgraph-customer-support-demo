"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Bot, CircleCheck, CircleOff } from "lucide-react";
import { ChatComposer } from "@/components/chat-composer";
import { ChatMessage, ChatThread } from "@/components/chat-thread";
import { CustomerPanel } from "@/components/customer-panel";
import { MemoryAdmin } from "@/components/memory-admin";
import { RunInspector } from "@/components/run-inspector";
import {
  deleteMemory,
  deleteUserMemories,
  getHealth,
  getMemories,
  markMemoryOutdated,
  sendChat,
} from "@/lib/support-api";
import type { ChatResponse, MemoryOut } from "@/lib/support-api";

const CONVERSATION_STORAGE_KEY = "support-conversation-id";

export default function Home() {
  const [userId, setUserId] = useState("alice");
  const [channel, setChannel] = useState("web");
  const [conversationId, setConversationId] = useState("demo-session");
  const [forceEscalation, setForceEscalation] = useState(false);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "agent",
      text: "Hi, I am ready to help with support questions and remember useful context.",
    },
  ]);
  const [lastRun, setLastRun] = useState<ChatResponse | null>(null);
  const [memories, setMemories] = useState<MemoryOut[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [isMemoryLoading, setIsMemoryLoading] = useState(false);
  const [memoryError, setMemoryError] = useState<string | null>(null);
  const [appError, setAppError] = useState<string | null>(null);
  const [serviceStatus, setServiceStatus] = useState<"checking" | "live" | "local" | "offline">(
    "checking",
  );

  const normalizedUserId = useMemo(() => userId.trim() || "alice", [userId]);

  const refreshMemories = useCallback(
    async (targetUserId = normalizedUserId) => {
      setIsMemoryLoading(true);
      setMemoryError(null);
      try {
        const response = await getMemories(targetUserId);
        setMemories(response.memories);
      } catch (error) {
        setMemories([]);
        setMemoryError(errorMessage(error));
      } finally {
        setIsMemoryLoading(false);
      }
    },
    [normalizedUserId],
  );

  useEffect(() => {
    const storedConversation = window.localStorage.getItem(CONVERSATION_STORAGE_KEY);
    const nextConversationId = storedConversation || makeConversationId();
    setConversationId(nextConversationId);
    window.localStorage.setItem(CONVERSATION_STORAGE_KEY, nextConversationId);
  }, []);

  useEffect(() => {
    async function loadHealth() {
      try {
        const health = await getHealth();
        setServiceStatus(health.live_mem0 || health.live_llm ? "live" : "local");
      } catch {
        setServiceStatus("offline");
      }
    }

    void loadHealth();
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void refreshMemories();
    }, 250);

    return () => window.clearTimeout(timeout);
  }, [refreshMemories]);

  async function handleSend() {
    const trimmedMessage = message.trim();
    if (!trimmedMessage || isSending) return;

    const userMessage: ChatMessage = {
      id: makeId("user"),
      role: "user",
      text: trimmedMessage,
    };

    setMessages((current) => [...current, userMessage]);
    setMessage("");
    setIsSending(true);
    setAppError(null);

    try {
      const response = await sendChat({
        user_id: normalizedUserId,
        message: trimmedMessage,
        conversation_id: conversationId,
        channel,
        force_escalation: forceEscalation,
      });

      setLastRun(response);
      setConversationId(response.conversation_id);
      window.localStorage.setItem(CONVERSATION_STORAGE_KEY, response.conversation_id);
      setMessages((current) => [
        ...current,
        {
          id: makeId("agent"),
          role: "agent",
          text: response.reply,
        },
      ]);
      await refreshMemories(normalizedUserId);
    } catch (error) {
      const text = errorMessage(error);
      setAppError(text);
      setMessages((current) => [
        ...current,
        {
          id: makeId("error"),
          role: "error",
          text: `Request failed: ${text}`,
        },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  async function handleDeleteAllMemories() {
    if (!window.confirm(`Delete all memories for ${normalizedUserId}?`)) return;
    setAppError(null);
    try {
      await deleteUserMemories(normalizedUserId);
      await refreshMemories(normalizedUserId);
    } catch (error) {
      setAppError(errorMessage(error));
    }
  }

  async function handleDeleteMemory(memoryId: string) {
    setAppError(null);
    try {
      await deleteMemory(normalizedUserId, memoryId);
      await refreshMemories(normalizedUserId);
    } catch (error) {
      setAppError(errorMessage(error));
    }
  }

  async function handleMarkOutdated(memoryId: string, reason: string) {
    setAppError(null);
    try {
      await markMemoryOutdated(normalizedUserId, memoryId, reason);
      await refreshMemories(normalizedUserId);
    } catch (error) {
      setAppError(errorMessage(error));
    }
  }

  return (
    <main className="min-h-screen bg-[#f5f7fa] p-3 text-zinc-950 sm:p-4">
      <div className="mx-auto grid min-h-[calc(100vh-24px)] max-w-[1600px] gap-4 xl:grid-cols-[300px_minmax(420px,1fr)_360px]">
        <div className="grid content-start gap-4">
          <BrandBlock serviceStatus={serviceStatus} />
          <CustomerPanel
            userId={userId}
            channel={channel}
            conversationId={conversationId}
            forceEscalation={forceEscalation}
            onUserIdChange={setUserId}
            onChannelChange={setChannel}
            onConversationIdChange={setConversationId}
            onForceEscalationChange={setForceEscalation}
          />
          <MemoryAdmin
            memories={memories}
            isLoading={isMemoryLoading}
            error={memoryError}
            onRefresh={() => void refreshMemories(normalizedUserId)}
            onDeleteAll={handleDeleteAllMemories}
            onDeleteMemory={handleDeleteMemory}
            onMarkOutdated={handleMarkOutdated}
          />
        </div>

        <section className="flex min-h-[640px] min-w-0 flex-col overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm">
          <header className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 px-4 py-4">
            <div>
              <p className="text-xs font-semibold text-teal-700">Live demo</p>
              <h1 className="text-base font-semibold text-zinc-950">Customer conversation</h1>
            </div>
            <StatusPill serviceStatus={serviceStatus} />
          </header>

          {appError ? (
            <div className="border-b border-red-100 bg-red-50 px-4 py-2 text-sm text-red-800">
              {appError}
            </div>
          ) : null}

          <ChatThread messages={messages} />
          <ChatComposer
            message={message}
            isSending={isSending}
            onMessageChange={setMessage}
            onSubmit={handleSend}
          />
        </section>

        <RunInspector lastRun={lastRun} />
      </div>
    </main>
  );
}

function BrandBlock({ serviceStatus }: { serviceStatus: "checking" | "live" | "local" | "offline" }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="grid size-11 place-items-center rounded-lg bg-teal-700 text-white">
          <Bot size={22} aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <h2 className="text-lg font-semibold leading-tight text-zinc-950">Support Agent</h2>
          <p className="text-sm text-zinc-500">Memory-first console</p>
        </div>
      </div>
      <div className="mt-4">
        <StatusPill serviceStatus={serviceStatus} />
      </div>
    </section>
  );
}

function StatusPill({
  serviceStatus,
}: {
  serviceStatus: "checking" | "live" | "local" | "offline";
}) {
  const config = {
    checking: {
      label: "Checking",
      className: "bg-zinc-100 text-zinc-700 ring-zinc-200",
      icon: CircleOff,
    },
    live: {
      label: "Live services",
      className: "bg-emerald-50 text-emerald-800 ring-emerald-200",
      icon: CircleCheck,
    },
    local: {
      label: "Local demo",
      className: "bg-sky-50 text-sky-800 ring-sky-200",
      icon: CircleCheck,
    },
    offline: {
      label: "Offline",
      className: "bg-red-50 text-red-800 ring-red-200",
      icon: CircleOff,
    },
  }[serviceStatus];

  const Icon = config.icon;

  return (
    <span
      className={`inline-flex min-h-7 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${config.className}`}
    >
      <Icon size={14} aria-hidden="true" />
      {config.label}
    </span>
  );
}

function makeConversationId() {
  return `demo-${globalThis.crypto?.randomUUID?.() ?? Date.now()}`;
}

function makeId(prefix: string) {
  return `${prefix}-${globalThis.crypto?.randomUUID?.() ?? Date.now()}`;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unknown error";
}
