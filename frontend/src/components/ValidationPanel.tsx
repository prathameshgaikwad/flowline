import {
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  ShieldAlert,
  Wrench,
  XCircle,
} from "lucide-react";
import type { DesignState } from "../types";

export function ValidationPanel({
  design,
  busy,
  onApplyFix,
  compact = false,
}: {
  design: DesignState | null;
  busy: boolean;
  onApplyFix: (fixId: string) => void;
  compact?: boolean;
}) {
  if (!design) {
    return <p className="text-xs text-slate-500">No design selected.</p>;
  }
  const counts = design.counts;
  const issues = design.issues || [];
  const hasValidation = design.validation?.length > 0;
  return (
    <div className="space-y-2" data-testid="validation-panel">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-700">
          {counts.PASS} pass
        </span>
        <span className="rounded-full bg-amber-50 px-2 py-1 text-[10px] font-bold text-amber-700">
          {counts.WARNING} warn
        </span>
        <span className="rounded-full bg-red-50 px-2 py-1 text-[10px] font-bold text-red-700">
          {counts.ERROR} error
        </span>
        {design.stale && (
          <span className="flex items-center gap-1 rounded-full bg-amber-100 px-2 py-1 text-[10px] font-bold text-amber-800">
            <RefreshCw size={10} /> stale — revalidate
          </span>
        )}
      </div>

      {!hasValidation && (
        <p className="rounded-lg bg-slate-50 px-2.5 py-2 text-[10px] text-slate-500">
          Not validated yet. Ask the agent to validate or use the Validate action.
        </p>
      )}

      {issues.map((issue, index) => {
        const tone =
          issue.severity === "ERROR"
            ? "border-red-100 bg-red-50/50"
            : issue.severity === "WARNING"
              ? "border-amber-100 bg-amber-50/50"
              : "border-slate-100 bg-slate-50/50";
        return (
          <div
            key={`${issue.rule_id}-${index}`}
            className={`rounded-xl border p-2.5 ${tone}`}
          >
            <div className="flex items-start gap-1.5">
              {issue.severity === "ERROR" ? (
                <XCircle size={12} className="mt-0.5 shrink-0 text-red-600" />
              ) : (
                <AlertTriangle size={12} className="mt-0.5 shrink-0 text-amber-600" />
              )}
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-mono text-[9px] font-bold text-slate-500">
                    {issue.rule_id}
                  </span>
                  <span className="text-[9px] font-bold uppercase tracking-wide text-slate-400">
                    {issue.severity}
                  </span>
                </div>
                <p className="mt-0.5 text-[10px] leading-relaxed text-slate-700">
                  {issue.message}
                </p>
                <p className="mt-0.5 text-[9px] text-slate-400">{issue.source}</p>
              </div>
            </div>
          </div>
        );
      })}

      {design.fixes?.length > 0 && (
        <div className="rounded-xl border border-blue-100 bg-blue-50/40 p-2.5">
          <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-blue-700">
            <Wrench size={12} /> Recommended fixes
          </div>
          <div className="mt-1.5 space-y-1">
            {design.fixes.map((fix) => (
              <button
                key={fix.id}
                type="button"
                disabled={busy}
                onClick={() => onApplyFix(fix.id)}
                className="w-full rounded-lg border border-blue-200 bg-white px-2 py-1.5 text-left text-[10px] font-medium text-blue-700 transition hover:bg-blue-50 disabled:opacity-50"
              >
                {fix.kind.replaceAll("_", " ").toLowerCase()} · {fix.description}
              </button>
            ))}
          </div>
        </div>
      )}

      {hasValidation && !issues.length && (
        <div className="flex items-center gap-1.5 rounded-xl border border-emerald-100 bg-emerald-50/50 p-2.5 text-[10px] font-semibold text-emerald-700">
          <CheckCircle2 size={12} /> All current checks pass. The rule-pack warning still applies.
        </div>
      )}

      {!compact && (
        <div className="flex items-start gap-1.5 rounded-lg bg-slate-50 px-2 py-1.5 text-[9px] leading-relaxed text-slate-400">
          <ShieldAlert size={11} className="mt-0.5 shrink-0" />
          {design.disclaimer}
        </div>
      )}
    </div>
  );
}
