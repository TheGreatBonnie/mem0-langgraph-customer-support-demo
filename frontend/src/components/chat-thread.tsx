import clsx from "clsx";
import { Bot, UserRound } from "lucide-react";
import { ChatMarkdown } from "@/components/chat-markdown";

export type ChatMessage = {
  id: string;
  role: "agent" | "user" | "error";
  text: string;
};

type ChatThreadProps = {
  messages: ChatMessage[];
};

export function ChatThread({ messages }: ChatThreadProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
      {messages.map((message) => (
        <article
          key={message.id}
          className={clsx(
            "flex max-w-[860px] gap-3 rounded-lg border px-3 py-3 text-sm leading-6 shadow-sm",
            message.role === "user" && "ml-auto border-emerald-200 bg-emerald-50",
            message.role === "agent" && "mr-auto border-sky-200 bg-sky-50",
            message.role === "error" && "mx-auto border-red-200 bg-red-50 text-red-800",
          )}
        >
          <div
            className={clsx(
              "mt-0.5 grid size-7 shrink-0 place-items-center rounded-md",
              message.role === "user" && "bg-emerald-700 text-white",
              message.role === "agent" && "bg-sky-700 text-white",
              message.role === "error" && "bg-red-700 text-white",
            )}
          >
            {message.role === "user" ? (
              <UserRound size={15} aria-hidden="true" />
            ) : (
              <Bot size={15} aria-hidden="true" />
            )}
          </div>
          {message.role === "error" ? (
            <p className="min-w-0 whitespace-pre-wrap wrap-break-word">{message.text}</p>
          ) : (
            <ChatMarkdown content={message.text} />
          )}
        </article>
      ))}
    </div>
  );
}
