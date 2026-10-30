import { useMemo, useState } from "react";
import {
  Activity,
  BrainCircuit,
  GitCompareArrows,
  ListChecks,
  ShieldCheck,
} from "lucide-react";
import type { AgentEvent, DesignState } from "../types";
import { AgentNoteCard } from "./AgentNoteCard";
import { DecisionList } from "./DecisionList";
import { PlanStepper } from "./PlanStepper";
import { ReasoningCard } from "./ReasoningCard";
import { ToolTimeline } from "./ToolTimeline";
import { ValidationPanel } from "./ValidationPanel";

type Tab = "plan" | "thinking" | "decisions" | "validation" | "activity";

const tabs: { id: Tab; label: string; icon: typeof ListChecks }[] = [
  { id: "plan", label: "Plan", icon: ListChecks },
  { id: "thinking", label: "Thinking", icon: BrainCircuit },
  { id: "decisions", label: "Decisions", icon: GitCompareArrows },
  { id: "validation", label: "Checks", icon: ShieldCheck },
  { id: "activity", label: "Activity", icon: Activity },
];

export function MissionControl({
  design,
  events,
  busy,
  onApplyFix,
}: {
  design: DesignState | null;
  events: AgentEvent[];
  busy: boolean;
  onApplyFix: (fixId: string) => void;
}) {
  const [tab, setTab] = useState<Tab>("plan");
  const thinking = useMemo(
    () =>
      events.filter(
        (event) =>
          event.type === "reasoning" ||
          (event.type === "assistant" &&
            event.content &&
            (event.tool_calls?.length || 0) > 0),
      ),
    [events],
  );
  const decisions = design?.decisions || [];

  return (
    <section
      className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
      data-testid="mission-control"
    >
      <div className="flex shrink-0 items-center gap-0.5 overflow-x-auto border-b border-slate-100 px-2 py-1.5">
        {tabs.map((item) => {
          const Icon = item.icon;
          const active = tab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setTab(item.id)}
              className={`flex shrink-0 items-center gap-1 rounded-lg px-2 py-1.5 text-[10px] font-bold transition ${
                active
                  ? "bg-slate-900 text-white"
                  : "text-slate-500 hover:bg-slate-100 hover:text-slate-700"
              }`}
              data-testid={`mission-tab-${item.id}`}
            >
              <Icon size={11} /> {item.label}
            </button>
          );
        })}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {tab === "plan" && (
          <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-3">
            <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400">
              Agent plan
            </div>
            <PlanStepper steps={design?.plan || []} activeId={busy ? "active" : null} />
            {design?.design && (
              <div className="mt-3 border-t border-slate-200 pt-2 text-[10px] text-slate-500">
                Selected layout:{" "}
                <span className="font-semibold text-slate-800">
                  {design.design.layout_id}
                </span>{" "}
                · {design.design.pipes.length} pipes ·{" "}
                {design.design.fixtures.length} fixtures
              </div>
            )}
          </div>
        )}

        {tab === "thinking" && (
          <div className="space-y-2">
            {!thinking.length && (
              <p className="text-xs text-slate-500">
                No provider reasoning or agent notes captured yet. Start a design or ask a
                follow-up.
              </p>
            )}
            {thinking.map((event, index) =>
              event.type === "reasoning" ? (
                <ReasoningCard
                  key={`${event.seq || index}`}
                  content={String(event.content || "")}
                  iteration={Number(event.iteration || 0) || undefined}
                  defaultOpen={index === thinking.length - 1}
                />
              ) : (
                <AgentNoteCard
                  key={`note-${event.seq || index}`}
                  content={String(event.content || "")}
                  iteration={Number(event.iteration || 0) || undefined}
                  defaultOpen={index === thinking.length - 1}
                />
              ),
            )}
          </div>
        )}

        {tab === "decisions" && (
          <div className="space-y-2">
            {design?.design && (
              <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-2.5">
                <div className="text-[9px] font-bold uppercase tracking-[0.12em] text-emerald-600">
                  Current design
                </div>
                <div className="mt-0.5 text-xs font-bold text-slate-900">
                  {design.design.layout_id} ·{" "}
                  {design.candidates.find((item) => item.selected)?.pattern || "selected layout"}
                </div>
                <p className="mt-1 text-[10px] leading-relaxed text-slate-600">
                  {design.design.rationale || "No rationale recorded."}
                </p>
              </div>
            )}
            <DecisionList decisions={decisions} />
            {design?.candidates?.length ? (
              <div className="mt-2 rounded-xl border border-slate-100 bg-slate-50/60 p-2.5">
                <div className="mb-1 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">
                  Layout candidates
                </div>
                <div className="space-y-1">
                  {design.candidates.map((candidate) => (
                    <div
                      key={candidate.id}
                      className={`flex items-center justify-between gap-2 rounded-lg px-2 py-1 text-[10px] ${
                        candidate.selected ? "bg-blue-50 text-blue-800" : "text-slate-500"
                      }`}
                    >
                      <span className="font-semibold">
                        {candidate.id} · {candidate.pattern}
                      </span>
                      <span>{candidate.score.toFixed(0)}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        )}

        {tab === "validation" && (
          <ValidationPanel design={design} busy={busy} onApplyFix={onApplyFix} />
        )}

        {tab === "activity" && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-[10px] text-slate-400">
              <span>{events.length} persisted events</span>
              <span>{events.filter((item) => item.type === "tool_result").length} tool results</span>
            </div>
            <ToolTimeline events={events} />
          </div>
        )}
      </div>
    </section>
  );
}
