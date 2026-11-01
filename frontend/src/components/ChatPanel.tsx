import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUp,
  FileText,
  GitCompareArrows,
  Lightbulb,
  ListChecks,
  ShieldCheck,
  Sparkles,
  Wrench,
} from "lucide-react";
import type { AgentEvent, DesignState, Message } from "../types";
import { designStatus } from "../lib/labels";
import { useClickAway } from "../hooks/useClickAway";
import { useMenuFocus } from "../hooks/useMenuFocus";
import { AgentTurn } from "./AgentTurn";
import { Logo } from "./Logo";
import { cx, Dot, IconButton, Spinner } from "./ui";

const actions = [
  {
    label: "Compare layouts",
    hint: "See what else was considered",
    icon: GitCompareArrows,
    prompt:
      "Compare the generated layouts and explain what you rejected and why.",
  },
  {
    label: "Run checks",
    hint: "Recheck against the active code standard",
    icon: ShieldCheck,
    prompt:
      "Validate the current design against the active standard. Do not change the layout.",
  },
  {
    label: "Apply best fix",
    hint: "Fix the most important issue and recheck",
    icon: Wrench,
    prompt: "Apply the best recommended fix and revalidate.",
  },
  {
    label: "Explain decisions",
    hint: "Get a plain-language walkthrough",
    icon: Lightbulb,
    prompt:
      "Explain the selected layout, plumbing systems, validation warnings, and assumptions in plain language.",
  },
  {
    label: "Prepare sheet",
    hint: "Build the construction sheet and preview",
    icon: FileText,
    prompt:
      "Prepare the construction sheet with the riser diagram, schedules, and title block, then review it.",
  },
  {
    label: "Review drawing",
    hint: "Check the sheet before export",
    icon: ShieldCheck,
    prompt: "Review the construction sheet and report any drawing issues.",
  },
];

export function ChatPanel({
  design,
  messages,
  events,
  busy,
  onSend,
  onOpenDetails,
  onOpenFullscreen,
  onOpenSheet,
  onApprove,
}: {
  design: DesignState | null;
  messages: Message[];
  events: AgentEvent[];
  busy: boolean;
  onSend: (content: string) => void;
  onOpenDetails: (tab: "design" | "checks" | "activity") => void;
  onOpenFullscreen: () => void;
  onOpenSheet: () => void;
  onApprove: () => void;
}) {
  const [value, setValue] = useState("");
  const [actionsOpen, setActionsOpen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const nearBottomRef = useRef(true);
  const actionsRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useClickAway(actionsRef, () => setActionsOpen(false), actionsOpen);
  useMenuFocus(actionsOpen, () => setActionsOpen(false), menuRef);

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
        isLatest: index === userMessages.length - 1,
      };
    });
  }, [messages, events, busy]);

  useEffect(() => {
    if (!nearBottomRef.current) return;
    endRef.current?.scrollIntoView({
      behavior: busy ? "auto" : "smooth",
      block: "end",
    });
  }, [messages.length, events.length, busy]);

  const submit = () => {
    const text = value.trim();
    if (!text || busy) return;
    onSend(text);
    setValue("");
    nearBottomRef.current = true;
  };

  const status = designStatus(design, busy);

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-surface">
      <div className="flex min-h-14 shrink-0 items-center gap-2.5 border-b border-line px-4 py-2.5">
        <span className="grid h-8 w-8 place-items-center rounded-card bg-accent-soft text-accent">
          <Sparkles size={16} aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-ui font-semibold text-ink">Design assistant</div>
          <div className="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
            <Dot tone={status.tone} pulse={status.pulse} />
            <span className="truncate">{status.label}</span>
          </div>
        </div>
        <span className="lg:hidden">
          <IconButton
            label="Open design details"
            onClick={() => onOpenDetails("design")}
          >
            <ListChecks size={18} aria-hidden="true" />
          </IconButton>
        </span>
      </div>

      <div
        ref={scrollRef}
        role="log"
        aria-label="Design conversation"
        aria-live="polite"
        aria-relevant="additions text"
        aria-busy={busy}
        className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-5 [scrollbar-gutter:stable] sm:px-5"
        onScroll={(event) => {
          const element = event.currentTarget;
          nearBottomRef.current =
            element.scrollHeight - element.scrollTop - element.clientHeight < 80;
        }}
        data-testid="chat-messages"
      >
        {!turns.length ? (
          <div className="mx-auto max-w-[460px] py-8 text-center sm:py-12">
            <div className="mx-auto w-fit">
              <Logo size={40} />
            </div>
            <h2 className="mt-4 text-xl font-semibold tracking-[-0.02em] text-ink">
              Review the design with evidence.
            </h2>
            <p className="mx-auto mt-2 max-w-[380px] text-ui leading-relaxed text-muted">
              Ask about layouts, code checks, plumbing routes, or the
              construction sheet. Every action stays in the workspace.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {actions.slice(0, 3).map((action) => {
                const Icon = action.icon;
                return (
                  <button
                    key={action.label}
                    type="button"
                    disabled={busy}
                    onClick={() => onSend(action.prompt)}
                    className="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-line-strong bg-raised px-3 text-label font-medium text-ink-soft transition hover:border-accent/40 hover:bg-accent-soft hover:text-accent disabled:opacity-40"
                    data-testid={`quick-${action.label.toLowerCase().replaceAll(" ", "-")}`}
                  >
                    <Icon size={14} aria-hidden="true" /> {action.label}
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-[700px] space-y-6">
            {turns.map((turn) => (
              <div key={turn.user.id} className="space-y-3">
                <div className="flex justify-end">
                  <div className="max-w-[86%] rounded-card rounded-br-sm bg-accent px-4 py-2.5 text-chat leading-relaxed text-on-accent shadow-sm">
                    {turn.user.content}
                  </div>
                </div>
                <AgentTurn
                  events={turn.events}
                  assistant={turn.assistant}
                  design={design}
                  busy={turn.busy}
                  isLatest={turn.isLatest}
                  onOpenDetails={onOpenDetails}
                  onOpenFullscreen={onOpenFullscreen}
                  onOpenSheet={onOpenSheet}
                  onApprove={onApprove}
                />
              </div>
            ))}
            <div ref={endRef} />
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-line bg-surface px-4 py-3 sm:px-5">
        <div className="mx-auto max-w-[700px]">
          <div className="flex items-end gap-2 rounded-card border border-line-strong bg-raised p-1.5 shadow-sm transition-[border-color,box-shadow] focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/15">
            <div className="relative" ref={actionsRef}>
              <IconButton
                label="Suggested actions"
                onClick={() => setActionsOpen((open) => !open)}
                disabled={busy}
                aria-expanded={actionsOpen}
                aria-haspopup="menu"
                aria-controls="chat-actions-menu"
                className={cx(actionsOpen && "bg-sunken text-ink")}
                data-testid="actions-button"
              >
                <Sparkles size={18} aria-hidden="true" />
              </IconButton>
              {actionsOpen && (
                <div
                  ref={menuRef}
                  id="chat-actions-menu"
                  role="menu"
                  aria-label="Suggested actions"
                  className="absolute bottom-[calc(100%+10px)] left-0 z-40 w-[min(320px,calc(100vw-2rem))] overflow-hidden rounded-overlay border border-line bg-raised p-1.5 shadow-float animate-fade-up"
                >
                  {actions.map((action) => {
                    const Icon = action.icon;
                    return (
                      <button
                        key={action.label}
                        type="button"
                        role="menuitem"
                        disabled={busy}
                        onClick={() => {
                          onSend(action.prompt);
                          setActionsOpen(false);
                        }}
                        className="flex min-h-12 w-full items-start gap-3 rounded-control px-2.5 py-2 text-left transition hover:bg-sunken disabled:opacity-40"
                        data-testid={`quick-${action.label.toLowerCase().replaceAll(" ", "-")}`}
                      >
                        <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-card bg-sunken text-muted">
                          <Icon size={16} aria-hidden="true" />
                        </span>
                        <span className="min-w-0">
                          <span className="block text-ui font-medium text-ink">
                            {action.label}
                          </span>
                          <span className="mt-0.5 block text-xs leading-snug text-muted">
                            {action.hint}
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            <label htmlFor="design-composer" className="sr-only">
              Ask about the plan
            </label>
            <textarea
              id="design-composer"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  submit();
                }
              }}
              rows={1}
              placeholder={busy ? "Designing…" : "Ask about the plan…"}
              disabled={busy}
              className="max-h-32 min-h-11 flex-1 resize-none bg-transparent px-1.5 py-2 text-base leading-relaxed text-ink outline-none placeholder:text-muted disabled:opacity-70 lg:min-h-9 lg:text-chat"
              data-testid="composer"
            />
            <button
              type="button"
              onClick={submit}
              disabled={busy || !value.trim()}
              className="mb-0.5 grid h-11 w-11 shrink-0 place-items-center rounded-control bg-accent text-on-accent transition hover:bg-accent-hover disabled:bg-line-strong disabled:text-surface lg:h-9 lg:w-9"
              data-testid="send-message"
              aria-label="Send message"
            >
              {busy ? <Spinner size={16} /> : <ArrowUp size={18} aria-hidden="true" />}
            </button>
          </div>
          <div className="mt-2 hidden items-center justify-between gap-3 text-xs text-muted sm:flex">
            <span>Enter to send · Shift+Enter for a new line</span>
            <span>Plumbing design scope only</span>
          </div>
        </div>
      </div>
    </div>
  );
}
