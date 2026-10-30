import { useMemo } from "react";
import { Bot, Loader2 } from "lucide-react";
import type { AgentEvent, DesignState, Message } from "../types";
import { AgentNoteCard } from "./AgentNoteCard";
import { CandidateTable } from "./CandidateTable";
import { DecisionList } from "./DecisionList";
import { Markdown } from "./Markdown";
import { PlanStepper } from "./PlanStepper";
import { ReasoningCard } from "./ReasoningCard";
import { ToolTimeline } from "./ToolTimeline";
import { ValidationPanel } from "./ValidationPanel";

export function AgentTurn({
  events,
  assistant,
  design,
  busy,
  onApplyFix,
}: {
  events: AgentEvent[];
  assistant?: Message;
  design: DesignState | null;
  busy: boolean;
  onApplyFix: (fixId: string) => void;
}) {
  const reasoning = events.filter((event) => event.type === "reasoning");
  const notes = events.filter(
    (event) =>
      event.type === "assistant" &&
      event.content &&
      (event.tool_calls?.length || 0) > 0,
  );
  const plans = events.filter((event) => event.type === "plan");
  const plan = (plans[plans.length - 1]?.steps as DesignState["plan"]) || design?.plan || [];
  const turnDecisions = events
    .filter((event) => event.type === "decision")
    .map((event) => event.decision)
    .filter(Boolean);
  const hasSelection = turnDecisions.some((item: any) => item?.kind === "layout_selected");
  const hasValidation = events.some(
    (event) =>
      event.type === "tool_result" &&
      (event.tool === "validate_design" || event.tool === "apply_fix"),
  );
  const finalEvent = [...events].reverse().find((event) => event.type === "final");
  const finalContent = assistant?.content || finalEvent?.content || "";
  const rejectedReasons = useMemo(() => {
    const map: Record<string, string> = {};
    for (const decision of turnDecisions as any[]) {
      if (decision?.kind === "layout_selected") {
        for (const item of decision.rejected || []) {
          map[item.id] = item.reason;
        }
      }
    }
    return map;
  }, [turnDecisions]);

  return (
    <div className="flex gap-2.5" data-testid="agent-turn">
      <div className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-slate-900 to-slate-700 text-[10px] font-black text-white shadow-sm">
        <Bot size={14} />
      </div>
      <div className="min-w-0 flex-1 space-y-2.5">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-slate-900">Flowline</span>
          <span className="text-[10px] text-slate-400">
            {busy ? "working…" : finalContent ? "finished" : "waiting"}
          </span>
          {busy && <Loader2 size={11} className="animate-spin text-blue-600" />}
        </div>

        {plan.length > 0 && (
          <div className="rounded-xl border border-slate-100 bg-white px-3 py-2">
            <PlanStepper steps={plan} compact />
          </div>
        )}

        {notes.map((event, index) => (
          <AgentNoteCard
            key={`note-${event.seq || index}`}
            content={String(event.content || "")}
            iteration={Number(event.iteration || 0) || undefined}
            defaultOpen={busy || index === notes.length - 1}
          />
        ))}

        {reasoning.map((event, index) => (
          <ReasoningCard
            key={`${event.seq || index}`}
            content={String(event.content || "")}
            iteration={Number(event.iteration || 0) || undefined}
            defaultOpen={busy || index === reasoning.length - 1}
          />
        ))}

        {events.some((event) => event.type === "tool_call" || event.type === "tool_result") && (
          <div className="rounded-xl border border-slate-100 bg-white p-2.5">
            <ToolTimeline events={events} />
          </div>
        )}

        {hasSelection && design?.candidates?.length ? (
          <div className="rounded-xl border border-slate-100 bg-white p-2.5">
            <div className="mb-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">
              Layout comparison
            </div>
            <CandidateTable candidates={design.candidates} rejectedReasons={rejectedReasons} />
          </div>
        ) : null}

        {turnDecisions.length > 0 && (
          <div className="rounded-xl border border-slate-100 bg-white p-2.5">
            <DecisionList decisions={turnDecisions as any} />
          </div>
        )}

        {hasValidation && (
          <div className="rounded-xl border border-slate-100 bg-white p-2.5">
            <ValidationPanel design={design} busy={busy} onApplyFix={onApplyFix} compact />
          </div>
        )}

        {finalContent ? (
          <div className="rounded-2xl rounded-tl-md border border-slate-200 bg-white px-3.5 py-3 shadow-sm">
            <Markdown>{finalContent}</Markdown>
          </div>
        ) : busy ? (
          <div className="rounded-2xl rounded-tl-md border border-dashed border-slate-200 bg-white/60 px-3.5 py-2.5 text-[11px] text-slate-400">
            Inspecting, comparing, and validating…
          </div>
        ) : null}
      </div>
    </div>
  );
}
