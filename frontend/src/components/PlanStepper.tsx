import {
  Check,
  Circle,
  LoaderCircle,
  MinusCircle,
  TriangleAlert,
} from "lucide-react";
import type { PlanStep } from "../types";
import { humanStep } from "../lib/labels";
import { cx } from "./ui";

const statusStyle: Record<string, string> = {
  pending: "text-muted",
  active: "text-accent",
  done: "text-success",
  skipped: "text-muted",
  error: "text-danger",
};

const statusLabel: Record<string, string> = {
  pending: "Pending",
  active: "In progress",
  done: "Done",
  skipped: "Skipped",
  error: "Failed",
};

function StatusIcon({ status }: { status: string }) {
  if (status === "done") return <Check size={16} aria-hidden="true" />;
  if (status === "active")
    return <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />;
  if (status === "error")
    return <TriangleAlert size={16} aria-hidden="true" />;
  if (status === "skipped")
    return <MinusCircle size={16} aria-hidden="true" />;
  return <Circle size={16} aria-hidden="true" />;
}

export function PlanStepper({
  steps,
  compact = false,
  activeId,
}: {
  steps: PlanStep[];
  compact?: boolean;
  activeId?: string | null;
}) {
  if (!steps.length) {
    return (
      <p className="text-label leading-relaxed text-muted">
        The plan appears when the assistant starts working.
      </p>
    );
  }
  return (
    <ol className={compact ? "flex flex-wrap gap-x-4 gap-y-2" : "space-y-2.5"}>
      {steps.map((step) => {
        const status = step.id === activeId ? "active" : step.status;
        return (
          <li
            key={step.id}
            aria-current={status === "active" ? "step" : undefined}
            className={cx(
              "flex min-h-6 items-start gap-2.5 text-label",
              statusStyle[status] || statusStyle.pending,
            )}
          >
            <span className="mt-0.5 shrink-0">
              <StatusIcon status={status} />
            </span>
            <span className={cx("min-w-0 flex-1", status === "pending" && "text-muted")}>
              {humanStep(step.id, step.label)}
            </span>
            <span className="sr-only">{statusLabel[status] || status}</span>
            {status === "skipped" && (
              <span className="text-xs text-muted">skipped</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
