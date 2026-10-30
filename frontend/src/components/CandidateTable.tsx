import { CheckCircle2, Circle } from "lucide-react";
import type { Candidate } from "../types";

export function CandidateTable({
  candidates,
  rejectedReasons = {},
}: {
  candidates: Candidate[];
  rejectedReasons?: Record<string, string>;
}) {
  if (!candidates.length) {
    return <p className="text-xs text-slate-500">No layouts generated yet.</p>;
  }
  return (
    <div className="space-y-1.5" data-testid="candidate-table">
      {candidates.map((candidate) => {
        const reason =
          rejectedReasons[candidate.id] ||
          (candidate.violations.length
            ? `Hard violations: ${candidate.violations.join("; ")}`
            : candidate.rationale_hint);
        return (
          <div
            key={candidate.id}
            className={`flex items-start gap-2 rounded-xl border px-2.5 py-2 ${
              candidate.selected
                ? "border-blue-300 bg-blue-50/70"
                : "border-slate-100 bg-white"
            }`}
          >
            {candidate.selected ? (
              <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-blue-600" />
            ) : (
              <Circle size={14} className="mt-0.5 shrink-0 text-slate-300" />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-bold text-slate-800">
                  {candidate.id} · {candidate.pattern}
                </span>
                <span className="shrink-0 text-[10px] font-bold text-slate-500">
                  {candidate.score.toFixed(0)}
                </span>
              </div>
              <div
                className={`mt-0.5 text-[10px] leading-relaxed ${
                  candidate.violations.length ? "text-red-600" : "text-slate-500"
                }`}
              >
                {reason}
              </div>
            </div>
            {candidate.selected && (
              <span className="mt-0.5 shrink-0 rounded-full bg-blue-600 px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wide text-white">
                selected
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
