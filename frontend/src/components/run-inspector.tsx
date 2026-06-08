import clsx from "clsx";
import { Brain, ClipboardCheck, Database } from "lucide-react";
import type { ReactNode } from "react";
import type { ChatResponse, MemoryOut } from "@/lib/support-api";

type RunInspectorProps = {
  lastRun: ChatResponse | null;
};

export function RunInspector({ lastRun }: RunInspectorProps) {
  const intent = lastRun?.intent ?? "idle";

  return (
    <aside className="grid content-start gap-4 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <section className="grid gap-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ClipboardCheck size={18} className="text-teal-700" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-zinc-950">Agent Run</h2>
          </div>
          <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-700">
            {titleCase(intent)}
          </span>
        </div>

        <dl className="grid gap-2 text-sm">
          <Fact
            label="Escalation"
            value={lastRun ? (lastRun.escalation_required ? "Required" : "No") : "-"}
            tone={lastRun?.escalation_required ? "danger" : "neutral"}
          />
          <Fact
            label="Saved"
            value={
              lastRun
                ? lastRun.memory_write_skipped_reason ?? String(lastRun.saved_memory_count)
                : "-"
            }
          />
          <Fact label="Conversation" value={lastRun?.conversation_id ?? "-"} />
        </dl>
      </section>

      <EvidenceSection
        icon={<Brain size={18} aria-hidden="true" />}
        title="Memory Hits"
        empty="No memory hits"
        items={lastRun?.used_memories ?? []}
        renderItem={(memory) => (
          <EvidenceItem
            title={memory.memory}
            meta={memoryCategory(memory)}
            score={memory.score}
            status={String(memory.metadata.status ?? "active")}
          />
        )}
      />

      <EvidenceSection
        icon={<Database size={18} aria-hidden="true" />}
        title="Knowledge"
        empty="No knowledge hits"
        items={lastRun?.knowledge_sources ?? []}
        renderItem={(source) => (
          <EvidenceItem title={source.title} meta={source.content} score={source.score} />
        )}
      />
    </aside>
  );
}

function Fact({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "danger";
}) {
  return (
    <div className="grid grid-cols-[108px_1fr] gap-3 border-b border-zinc-100 pb-2 last:border-b-0 last:pb-0">
      <dt className="text-xs font-medium text-zinc-500">{label}</dt>
      <dd
        className={clsx(
          "min-w-0 break-words text-right text-xs font-semibold",
          tone === "danger" ? "text-red-700" : "text-zinc-800",
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function EvidenceSection<T>({
  icon,
  title,
  empty,
  items,
  renderItem,
}: {
  icon: ReactNode;
  title: string;
  empty: string;
  items: T[];
  renderItem: (item: T) => ReactNode;
}) {
  return (
    <section className="grid gap-3">
      <div className="flex items-center gap-2">
        <span className="text-teal-700">{icon}</span>
        <h2 className="text-sm font-semibold text-zinc-950">{title}</h2>
      </div>
      {items.length ? (
        <div className="grid gap-2">
          {items.map((item, index) => (
            <div key={index}>{renderItem(item)}</div>
          ))}
        </div>
      ) : (
        <p className="rounded-md border border-dashed border-zinc-200 px-3 py-3 text-xs text-zinc-500">
          {empty}
        </p>
      )}
    </section>
  );
}

function EvidenceItem({
  title,
  meta,
  score,
  status,
}: {
  title: string;
  meta: string;
  score: number | null;
  status?: string;
}) {
  return (
    <article className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-3">
      <p className="break-words text-sm leading-5 text-zinc-900">{title}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-semibold text-zinc-600 ring-1 ring-zinc-200">
          {meta}
        </span>
        {status ? (
          <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-semibold text-zinc-600 ring-1 ring-zinc-200">
            {status}
          </span>
        ) : null}
        {score ? (
          <span className="rounded-full bg-teal-50 px-2 py-0.5 text-[11px] font-semibold text-teal-800 ring-1 ring-teal-100">
            score {score}
          </span>
        ) : null}
      </div>
    </article>
  );
}

function memoryCategory(memory: MemoryOut) {
  return String(memory.metadata.category ?? memory.categories[0] ?? "memory");
}

function titleCase(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
