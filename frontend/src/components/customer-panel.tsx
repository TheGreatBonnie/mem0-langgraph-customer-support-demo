import { AlertTriangle, UserRound } from "lucide-react";

type CustomerPanelProps = {
  userId: string;
  channel: string;
  conversationId: string;
  forceEscalation: boolean;
  onUserIdChange: (value: string) => void;
  onChannelChange: (value: string) => void;
  onConversationIdChange: (value: string) => void;
  onForceEscalationChange: (value: boolean) => void;
};

export function CustomerPanel({
  userId,
  channel,
  conversationId,
  forceEscalation,
  onUserIdChange,
  onChannelChange,
  onConversationIdChange,
  onForceEscalationChange,
}: CustomerPanelProps) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="mb-4 flex items-center gap-3">
        <div className="grid size-9 place-items-center rounded-lg bg-teal-700 text-white">
          <UserRound size={18} aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-zinc-950">Customer</h2>
          <p className="text-xs text-zinc-500">Session controls</p>
        </div>
      </div>

      <div className="grid gap-3">
        <label className="grid gap-1.5 text-xs font-semibold text-zinc-600">
          User ID
          <input
            className="h-10 rounded-md border border-zinc-300 px-3 text-sm text-zinc-950 outline-none transition focus:border-teal-600 focus:ring-3 focus:ring-teal-100"
            value={userId}
            onChange={(event) => onUserIdChange(event.target.value)}
            autoComplete="off"
          />
        </label>

        <label className="grid gap-1.5 text-xs font-semibold text-zinc-600">
          Channel
          <select
            className="h-10 rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950 outline-none transition focus:border-teal-600 focus:ring-3 focus:ring-teal-100"
            value={channel}
            onChange={(event) => onChannelChange(event.target.value)}
          >
            <option value="web">Web</option>
            <option value="email">Email</option>
            <option value="slack">Slack</option>
            <option value="zendesk">Zendesk</option>
          </select>
        </label>

        <label className="grid gap-1.5 text-xs font-semibold text-zinc-600">
          Conversation
          <input
            className="h-10 rounded-md border border-zinc-300 px-3 text-sm text-zinc-950 outline-none transition focus:border-teal-600 focus:ring-3 focus:ring-teal-100"
            value={conversationId}
            onChange={(event) => onConversationIdChange(event.target.value)}
            autoComplete="off"
          />
        </label>

        <label className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900">
          <input
            type="checkbox"
            className="size-4 accent-amber-700"
            checked={forceEscalation}
            onChange={(event) => onForceEscalationChange(event.target.checked)}
          />
          <AlertTriangle size={16} aria-hidden="true" />
          Force escalation
        </label>
      </div>
    </section>
  );
}
