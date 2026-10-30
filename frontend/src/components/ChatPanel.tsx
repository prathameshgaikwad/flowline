import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUp,
  GitCompareArrows,
  Lightbulb,
  ListChecks,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import type { AgentEvent, DesignState, Message } from "../types";
import { AgentTurn } from "./AgentTurn";

const actions = [
  {
    label: "Compare layouts",
    icon: GitCompareArrows,
    prompt:
      "Compare the generated layouts and explain what you rejected and why.",
  },
  {
    label: "Validate",
    icon: ShieldCheck,
    prompt:
      "Validate the current design against the active standard. Do not change the layout.",
  },
  {
    label: "Apply best fix",
    icon: Wrench,
    prompt: "Apply the best recommended fix and revalidate.",
  },
  {
    label: "Explain decisions",
    icon: Lightbulb,
    prompt:
      "Explain the selected layout, rejected alternatives, validation warnings, and assumptions.",
  },
];

export function ChatPanel({
  design,
  messages,
  events,
  busy,
  onSend,
  onApplyFix,
  onApprove,
  canApprove,
}: {
  design: DesignState | null;
  messages: Message[];
  events: AgentEvent[];
  busy: boolean;
  onSend: (content: string) => void;
  onApplyFix: (fixId: string) => void;
  onApprove: () => void;
  canApprove: boolean;
}) {
  const [value, setValue] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const turns = useMemo(() => {
    const userMessages = messages.filter((message) => message.role === "user");
    return userMessages.map((user, index) => {
      const turnEvents = events.filter((event) => event.turn_id === user.turn_id);
      const assistant = messages.find(
        (message) =>
          message.role === "assistant" && message.turn_id === user.turn_id,
      );
      return {
        user,
        events: turnEvents,
        assistant,
        busy: busy && index === userMessages.length - 1,
      };
    });
  }, [messages, events, busy]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, events.length, busy]);

  const submit = () => {
    const text = value.trim();
    if (!text || busy) return;
    onSend(text);
    setValue("");
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white px-5 py-2.5">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-900">Design conversation</span>
            {design?.design && (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                {design.design.layout_id}
              </span>
            )}
          </div>
          <div className="mt-0.5 text-[10px] text-slate-500">
            {design?.profile_name} · {design?.counts.ERROR || 0} errors ·{" "}
            {design?.counts.WARNING || 0} warnings
          </div>
        </div>
        <button
          type="button"
          onClick={onApprove}
          disabled={!canApprove || busy}
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[10px] font-bold text-slate-600 transition hover:border-slate-300 disabled:opacity-40"
        >
          Export
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4" data-testid="chat-messages">
        {!turns.length && (
          <div className="mx-auto mt-10 max-w-xl rounded-2xl border border-dashed border-slate-200 bg-white px-6 py-8 text-center">
            <div className="mx-auto grid h-10 w-10 place-items-center rounded-2xl bg-blue-50 text-blue-600">
              <ListChecks size={18} />
            </div>
            <h2 className="mt-3 text-base font-bold text-slate-900">
              The agent is ready
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">
              Ask a question or use a quick action. The plan, reasoning, tool activity,
              rejected layouts, and validation will appear here.
            </p>
          </div>
        )}

        <div className="mx-auto max-w-3xl space-y-5">
          {turns.map((turn) => (
            <div key={turn.user.id} className="space-y-3">
              <div className="flex justify-end">
                <div className="max-w-[82%] rounded-2xl rounded-tr-md bg-blue-600 px-3.5 py-2.5 text-xs leading-relaxed text-white shadow-sm">
                  {turn.user.content}
                </div>
              </div>
              <AgentTurn
                events={turn.events}
                assistant={turn.assistant}
                design={design}
                busy={turn.busy}
                onApplyFix={onApplyFix}
              />
            </div>
          ))}
          <div ref={endRef} />
        </div>
      </div>

      <div className="shrink-0 border-t border-slate-200 bg-white px-5 py-3">
        <div className="mx-auto max-w-3xl">
          <div className="mb-2 flex flex-wrap gap-1.5">
            {actions.map((action) => {
              const Icon = action.icon;
              return (
                <button
                  key={action.label}
                  type="button"
                  disabled={busy || !design}
                  onClick={() => onSend(action.prompt)}
                  className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-semibold text-slate-600 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
                  data-testid={`quick-${action.label.toLowerCase().replaceAll(" ", "-")}`}
                >
                  <Icon size={11} /> {action.label}
                </button>
              );
            })}
            <button
              type="button"
              disabled={!canApprove || busy}
              onClick={onApprove}
              className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-semibold text-slate-600 transition hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ShieldCheck size={11} /> Review &amp; export
            </button>
          </div>
          <div className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-1.5 focus-within:border-blue-300 focus-within:bg-white">
            <textarea
              value={value}
              onChange={(event) => setValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  submit();
                }
              }}
              rows={1}
              placeholder={
                busy
                  ? "The agent is working…"
                  : "Ask about the design, or tell the agent what to change…"
              }
              disabled={busy}
              className="max-h-28 min-h-[34px] flex-1 resize-none bg-transparent px-2 py-2 text-xs text-slate-800 outline-none placeholder:text-slate-400 disabled:opacity-60"
              data-testid="composer"
            />
            <button
              type="button"
              onClick={submit}
              disabled={busy || !value.trim()}
              className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-blue-600 text-white transition hover:bg-blue-500 disabled:bg-slate-300"
              data-testid="send-message"
              aria-label="Send message"
            >
              <ArrowUp size={15} />
            </button>
          </div>
          <div className="mt-1.5 flex items-center justify-between text-[9px] text-slate-400">
            <span>Enter to send · Shift+Enter for a new line</span>
            <span>{design?.provider ? `${design.provider} · ${design.model}` : ""}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
