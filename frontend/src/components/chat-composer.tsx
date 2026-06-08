import { Loader2, Send } from "lucide-react";
import type { FormEvent } from "react";

type ChatComposerProps = {
  message: string;
  isSending: boolean;
  onMessageChange: (value: string) => void;
  onSubmit: () => void;
};

export function ChatComposer({
  message,
  isSending,
  onMessageChange,
  onSubmit,
}: ChatComposerProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <form
      className="grid gap-3 border-t border-zinc-200 bg-white p-4 md:grid-cols-[1fr_auto]"
      onSubmit={handleSubmit}
    >
      <textarea
        className="max-h-40 min-h-24 resize-y rounded-md border border-zinc-300 px-3 py-3 text-sm leading-6 text-zinc-950 outline-none transition placeholder:text-zinc-400 focus:border-teal-600 focus:ring-3 focus:ring-teal-100"
        value={message}
        onChange={(event) => onMessageChange(event.target.value)}
        placeholder="Ask about billing, bugs, onboarding, account access, cancellation, or product questions."
      />
      <button
        type="submit"
        disabled={isSending || !message.trim()}
        className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-teal-700 px-4 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-zinc-300 disabled:text-zinc-600"
      >
        {isSending ? (
          <Loader2 className="animate-spin" size={18} aria-hidden="true" />
        ) : (
          <Send size={18} aria-hidden="true" />
        )}
        Send
      </button>
    </form>
  );
}
