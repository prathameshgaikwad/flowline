import { ArrowRight, Wrench } from "lucide-react";
import type { AgentEvent, PlanStep } from "../types";
import { humanStep, toolSummary } from "../lib/labels";
import { cx, Dot } from "./ui";

export function RunCard({
  plan,
  events,
  onOpenDetails,
}: {
  plan: PlanStep[];
  events: AgentEvent[];
  onOpenDetails: () => void;
}) {
  const steps = plan.length
    ? plan
    : [
        { id: "start", label: "Getting started", status: "pending" as const },
      ];
  const doneCount = steps.filter(
    (step) => step.status === "done" || step.status === "skipped",
  ).length;
  const active =
    steps.find((step) => step.status === "pending") || steps[steps.length - 1];
  const results = events.filter((event) => event.type === "tool_result");
  const latest = results[results.length - 1];
  const latestText = latest
    ? toolSummary(
        String(latest.tool || "tool"),
        latest.output as Record<string, any>,
      )
    : "Reading the drawing and preparing a plan…";

  return (
    <div
      className="w-full min-w-0 overflow-hidden rounded-card border border-line bg-raised p-4 shadow-card animate-fade-up"
      data-testid="run-card"
      aria-label={`Designing. Step ${Math.min(doneCount + 1, steps.length)} of ${steps.length}. ${humanStep(active?.id || "", active?.label || "Working")}.`}
    >
      <div className="flex items-center gap-2">
        <Dot tone="accent" pulse />
        <span className="text-ui font-semibold text-ink">
          Designing the plumbing
        </span>
        <span className="ml-auto font-mono text-xs font-medium text-muted tabular-nums">
          {doneCount}/{steps.length}
        </span>
      </div>

      <div className="mt-3 flex gap-1" aria-hidden="true">
        {steps.map((step) => {
          const done = step.status === "done" || step.status === "skipped";
          const isActive = !done && step.id === active?.id;
          return (
            <span
              key={step.id}
              className={cx(
                "h-1.5 flex-1 rounded-full transition-colors",
                done
                  ? "bg-accent"
                  : isActive
                    ? "run-segment-active"
                    : "bg-line",
              )}
              title={humanStep(step.id, step.label)}
            />
          );
        })}
      </div>

      <div className="mt-3 flex items-start gap-2">
        <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full border-2 border-accent bg-surface" />
        <div className="min-w-0 flex-1 text-ui font-medium leading-snug text-ink">
          {humanStep(active?.id || "", active?.label || "Working")}
        </div>
      </div>
      <div className="mt-1.5 flex items-start gap-2 text-label leading-relaxed text-muted">
        <Wrench size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
        <span className="line-clamp-2 min-w-0">{latestText}</span>
      </div>

      <button
        type="button"
        onClick={onOpenDetails}
        className="mt-3 inline-flex min-h-11 items-center lg:min-h-8 gap-1 text-label font-semibold text-accent transition hover:text-accent-hover"
      >
        View live activity
        <ArrowRight size={13} aria-hidden="true" />
      </button>
    </div>
  );
}
