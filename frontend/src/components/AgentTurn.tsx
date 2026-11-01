import { useMemo, useState } from "react";
import { CheckCircle2, ChevronDown, CircleAlert } from "lucide-react";
import type { AgentEvent, DesignState, Message } from "../types";
import { displayCounts, plural, selectedLayout } from "../lib/labels";
import { DesignSummaryCard } from "./DesignSummaryCard";
import { Logo } from "./Logo";
import { Markdown } from "./Markdown";
import { RunCard } from "./RunCard";
import { cx, InlineAlert } from "./ui";

export function AgentTurn({
  events,
  assistant,
  design,
  busy,
  isLatest,
  onOpenDetails,
  onOpenFullscreen,
  onOpenSheet,
  onApprove,
}: {
  events: AgentEvent[];
  assistant?: Message;
  design: DesignState | null;
  busy: boolean;
  isLatest: boolean;
  onOpenDetails: (tab: "design" | "checks" | "activity") => void;
  onOpenFullscreen: () => void;
  onOpenSheet: () => void;
  onApprove: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const plan = useMemo(() => {
    const plans = events.filter((event) => event.type === "plan");
    return (
      (plans[plans.length - 1]?.steps as DesignState["plan"] | undefined) ||
      design?.plan ||
      []
    );
  }, [events, design]);
  const finalEvent = [...events].reverse().find((event) => event.type === "final");
  const finalContent = assistant?.content || finalEvent?.content || "";
  const errorEvent = [...events].reverse().find((event) => event.type === "error");
  const toolResults = events.filter((event) => event.type === "tool_result").length;
  const hasValidation = events.some(
    (event) =>
      event.type === "tool_result" &&
      (event.tool === "validate_design" || event.tool === "apply_fix"),
  );
  const hasSelection = events.some(
    (event) =>
      event.type === "decision" && event.decision?.kind === "layout_selected",
  );
  const designWork = hasSelection || hasValidation;
  const showSummary = Boolean(design?.design) && isLatest && designWork;
  const isLong = finalContent.length > 320;
  const counts = displayCounts(design);
  const candidate = selectedLayout(design);

  return (
    <div className="flex gap-3" data-testid="agent-turn">
      <div className="mt-0.5 shrink-0">
        <Logo size={27} />
      </div>
      <div className="min-w-0 flex-1 space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-ui font-semibold text-ink">Flowline</span>
          <span className="text-xs text-muted">
            {busy ? "working…" : finalContent ? "finished" : "waiting"}
          </span>
        </div>

        {busy && (
          <RunCard
            plan={plan}
            events={events}
            onOpenDetails={() => onOpenDetails("activity")}
          />
        )}

        {!busy && errorEvent && (
          <InlineAlert
            tone="danger"
            icon={<CircleAlert size={17} />}
            className="bg-danger-soft"
          >
            <span className="font-semibold">The assistant could not finish.</span>{" "}
            {String(errorEvent.message || "Try again from the composer.")}
          </InlineAlert>
        )}

        {!busy && !errorEvent && showSummary && design && (
          <DesignSummaryCard
            design={design}
            content={finalContent}
            busy={busy}
            onOpenDetails={onOpenDetails}
            onOpenFullscreen={onOpenFullscreen}
            onOpenSheet={onOpenSheet}
            onApprove={onApprove}
          />
        )}

        {!busy && !errorEvent && !showSummary && designWork && (
          <div
            className="rounded-card border border-line bg-sunken/60 px-4 py-3"
            data-testid="work-log"
          >
            <div className="flex items-start gap-2.5">
              <CheckCircle2
                size={16}
                className="mt-0.5 shrink-0 text-success"
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1">
                <div className="text-ui font-semibold text-ink">
                  {isLatest ? "Design updated" : "Design completed"}
                </div>
                <div className="mt-0.5 text-label leading-relaxed text-muted">
                  {candidate?.id || design?.design?.layout_id || "Layout"} ·{" "}
                  {counts.PASS} checks passed
                  {counts.ERROR + counts.WARNING > 0
                    ? ` · ${counts.ERROR + counts.WARNING} ${
                        counts.ERROR + counts.WARNING === 1
                          ? "issue"
                          : "issues"
                      }`
                    : ""}{" "}
                  · {plural(plan.length || toolResults, "step")}
                </div>
              </div>
              <button
                type="button"
                onClick={() => onOpenDetails("activity")}
                className="min-h-11 shrink-0 rounded-control lg:min-h-8 px-1.5 text-label font-medium text-accent transition hover:bg-accent-soft"
              >
                View details
              </button>
            </div>
            {finalContent && (
              <details className="group mt-2 border-t border-line pt-2">
                <summary className="flex min-h-11 cursor-pointer lg:min-h-8 list-none items-center gap-1 text-label font-medium text-muted transition hover:text-ink">
                  <ChevronDown
                    size={13}
                    className="transition-transform group-open:rotate-180"
                    aria-hidden="true"
                  />
                  Full answer
                </summary>
                <div className="mt-2">
                  <Markdown>{finalContent}</Markdown>
                </div>
              </details>
            )}
          </div>
        )}

        {!busy && !errorEvent && !showSummary && !designWork && finalContent && (
          <div className="rounded-card border border-line bg-raised px-4 py-3.5 shadow-card">
            <div
              className={cx(
                "prose-flowline",
                !expanded && isLong && "line-clamp-4",
              )}
            >
              <Markdown>{finalContent}</Markdown>
            </div>
            {isLong && (
              <button
                type="button"
                onClick={() => setExpanded((value) => !value)}
                className="mt-2 flex min-h-11 items-center gap-1 text-label lg:min-h-8 font-medium text-accent transition hover:text-accent-hover"
              >
                <ChevronDown
                  size={14}
                  className={cx("transition-transform", expanded && "rotate-180")}
                  aria-hidden="true"
                />
                {expanded ? "Show less" : "Show full answer"}
              </button>
            )}
            {toolResults > 0 && (
              <div className="mt-2 border-t border-line pt-1.5">
                <button
                  type="button"
                  onClick={() => onOpenDetails("activity")}
                  className="min-h-11 text-label font-medium lg:min-h-8 text-muted transition hover:text-ink"
                >
                  View activity · {plural(toolResults, "action")}
                </button>
              </div>
            )}
          </div>
        )}

        {!busy &&
          !errorEvent &&
          !showSummary &&
          !designWork &&
          !finalContent &&
          isLatest && (
            <div className="rounded-card border border-dashed border-line-strong bg-surface/60 px-4 py-3 text-label leading-relaxed text-muted">
              No written answer for this turn. Open the activity log for the
              full tool history.
            </div>
          )}
      </div>
    </div>
  );
}
