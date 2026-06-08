import clsx from "clsx";
import { AlertTriangle, Brain, RefreshCw, Trash2 } from "lucide-react";
import type { MemoryOut } from "@/lib/support-api";

type MemoryAdminProps = {
  memories: MemoryOut[];
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
  onDeleteAll: () => void;
  onDeleteMemory: (memoryId: string) => void;
  onMarkOutdated: (memoryId: string, reason: string) => void;
};

export function MemoryAdmin({
  memories,
  isLoading,
  error,
  onRefresh,
  onDeleteAll,
  onDeleteMemory,
  onMarkOutdated,
}: MemoryAdminProps) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Brain size={18} className="text-teal-700" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-zinc-950">Memories</h2>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          className="grid size-9 place-items-center rounded-md border border-zinc-300 text-zinc-700 transition hover:bg-zinc-50"
          title="Refresh memories"
        >
          <RefreshCw size={16} aria-hidden="true" />
        </button>
      </div>

      <div className="grid gap-2">
        {isLoading ? (
          <p className="rounded-md border border-dashed border-zinc-200 px-3 py-3 text-xs text-zinc-500">
            Loading
          </p>
        ) : error ? (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-3 text-xs text-red-800">
            {error}
          </p>
        ) : memories.length ? (
          memories.map((memory) => (
            <MemoryItem
              key={memory.id}
              memory={memory}
              onDelete={() => onDeleteMemory(memory.id)}
              onMarkOutdated={() => {
                const reason = window.prompt("Reason", "Marked outdated by support admin");
                if (reason !== null) onMarkOutdated(memory.id, reason);
              }}
            />
          ))
        ) : (
          <p className="rounded-md border border-dashed border-zinc-200 px-3 py-3 text-xs text-zinc-500">
            No memories
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={onDeleteAll}
        className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-md border border-red-200 bg-white px-3 text-sm font-semibold text-red-700 transition hover:bg-red-50"
      >
        <Trash2 size={16} aria-hidden="true" />
        Delete user memory
      </button>
    </section>
  );
}

function MemoryItem({
  memory,
  onDelete,
  onMarkOutdated,
}: {
  memory: MemoryOut;
  onDelete: () => void;
  onMarkOutdated: () => void;
}) {
  const status = String(memory.metadata.status ?? "active");
  const category = String(memory.metadata.category ?? memory.categories[0] ?? "memory");

  return (
    <article
      className={clsx(
        "rounded-lg border px-3 py-3",
        status === "outdated"
          ? "border-zinc-200 bg-zinc-50 text-zinc-500"
          : "border-zinc-200 bg-white text-zinc-900",
      )}
    >
      <p className="break-words text-sm leading-5">{memory.memory}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-semibold text-zinc-600">
          {category}
        </span>
        <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-semibold text-zinc-600">
          {status}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onMarkOutdated}
          className="inline-flex min-h-8 items-center gap-1.5 rounded-md border border-amber-200 px-2.5 text-xs font-semibold text-amber-800 transition hover:bg-amber-50"
        >
          <AlertTriangle size={14} aria-hidden="true" />
          Outdated
        </button>
        <button
          type="button"
          onClick={onDelete}
          className="inline-flex min-h-8 items-center gap-1.5 rounded-md border border-red-200 px-2.5 text-xs font-semibold text-red-700 transition hover:bg-red-50"
        >
          <Trash2 size={14} aria-hidden="true" />
          Delete
        </button>
      </div>
    </article>
  );
}
