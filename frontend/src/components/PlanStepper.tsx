import {
  AlertCircle,
  Check,
  Circle,
  Loader2,
  MinusCircle,
} from "lucide-react";
import type { PlanStep } from "../types";

const statusStyle: Record<string, string> = {
  pending: "text-slate-400",
  active: "text-blue-600",
  done: "text-emerald-600",
  skipped: "text-slate-400",
  error: "text-red-600",
};

function StatusIcon({ status }: { status: string }) {
  if (status === "done") return <Check size={14} />;
  if (status === "active") return <Loader2 size={14} className="animate-spin" />;
  if (status === "error") return <AlertCircle size={14} />;
  if (status === "skipped") return <MinusCircle size={14} />;
  return <Circle size={14} />;
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
      <p className="text-xs text-slate-500">
        The plan appears when the agent starts working.
      </p>
    );
  }
  return (
    <ol
      className={
        compact
          ? "flex flex-wrap items-center gap-x-4 gap-y-2"
          : "space-y-2"
      }
    >
      {steps.map((step) => {
        const status = step.id === activeId ? "active" : step.status;
        return (
          <li
            key={step.id}
            className={`flex items-center gap-2 text-xs ${
              statusStyle[status] || statusStyle.pending
            }`}
          >
            <StatusIcon status={status} />
            <span className={status === "pending" ? "text-slate-500" : ""}>
              {step.label}
            </span>
            {status === "skipped" && (
              <span className="text-[10px] text-slate-400">skipped</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
