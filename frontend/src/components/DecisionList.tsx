import {
  ArrowRightLeft,
  CheckCircle2,
  Scale,
  ShieldAlert,
  Wrench,
} from "lucide-react";
import type { Decision } from "../types";

function Counts({ counts }: { counts?: Record<string, number> }) {
  if (!counts) return null;
  return (
    <span className="flex gap-1 text-[9px] font-semibold">
      <span className="rounded-full bg-emerald-50 px-1.5 py-0.5 text-emerald-700">
        {counts.PASS || 0} pass
      </span>
      <span className="rounded-full bg-amber-50 px-1.5 py-0.5 text-amber-700">
        {counts.WARNING || 0} warn
      </span>
      <span className="rounded-full bg-red-50 px-1.5 py-0.5 text-red-700">
        {counts.ERROR || 0} error
      </span>
    </span>
  );
}

export function DecisionList({ decisions }: { decisions: Decision[] }) {
  if (!decisions.length) {
    return <p className="text-xs text-slate-500">No decisions recorded yet.</p>;
  }
  return (
    <div className="space-y-2">
      {[...decisions].reverse().map((decision, index) => {
        if (decision.kind === "layout_selected") {
          const rejected = (decision.rejected || []) as {
            id: string;
            reason: string;
            score?: number;
          }[];
          return (
            <div
              key={`${decision.kind}-${index}`}
              className="rounded-xl border border-blue-100 bg-blue-50/50 p-2.5"
            >
              <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-blue-700">
                <CheckCircle2 size={12} /> Layout selected
              </div>
              <div className="mt-1 text-xs font-bold text-slate-900">
                {String(decision.candidate_id)} · {String(decision.pattern)}
              </div>
              <p className="mt-1 text-[10px] leading-relaxed text-slate-600">
                {String(decision.rationale || "No rationale recorded.")}
              </p>
              {rejected.length > 0 && (
                <div className="mt-2 border-t border-blue-100 pt-1.5">
                  <div className="text-[9px] font-bold uppercase tracking-[0.12em] text-blue-500">
                    Rejected alternatives
                  </div>
                  <ul className="mt-1 space-y-0.5">
                    {rejected.map((item) => (
                      <li key={item.id} className="text-[10px] text-slate-500">
                        <span className="font-semibold text-slate-700">{item.id}</span>{" "}
                        — {item.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          );
        }
        if (decision.kind === "fix_applied") {
          return (
            <div
              key={`${decision.kind}-${index}`}
              className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-2.5"
            >
              <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-emerald-700">
                <Wrench size={12} /> Fix applied
              </div>
              <p className="mt-1 text-[10px] text-slate-600">{String(decision.description)}</p>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <Counts counts={decision.before as Record<string, number>} />
                <ArrowRightLeft size={10} className="text-slate-400" />
                <Counts counts={decision.after as Record<string, number>} />
              </div>
            </div>
          );
        }
        if (decision.kind === "profile_changed") {
          return (
            <div
              key={`${decision.kind}-${index}`}
              className="rounded-xl border border-sky-100 bg-sky-50/50 p-2.5"
            >
              <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-sky-700">
                <ArrowRightLeft size={12} /> Standard changed
              </div>
              <p className="mt-1 text-[10px] text-slate-600">
                {String(decision.previous_profile)} → {String(decision.profile_id)}.{" "}
                {String(decision.reason || "")}
              </p>
            </div>
          );
        }
        if (decision.kind === "validation") {
          return (
            <div
              key={`${decision.kind}-${index}`}
              className="flex items-center justify-between gap-2 rounded-xl border border-slate-100 bg-slate-50/60 p-2.5"
            >
              <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">
                <Scale size={12} /> Validation · {String(decision.profile_id)}
              </div>
              <Counts counts={decision.counts as Record<string, number>} />
            </div>
          );
        }
        if (decision.kind === "route_failed" || decision.kind === "fixtures_changed") {
          return (
            <div
              key={`${decision.kind}-${index}`}
              className="rounded-xl border border-amber-100 bg-amber-50/50 p-2.5"
            >
              <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-amber-700">
                <ShieldAlert size={12} />{" "}
                {decision.kind === "route_failed" ? "Route failed" : "Fixtures changed"}
              </div>
              <p className="mt-1 text-[10px] text-slate-600">
                {decision.kind === "route_failed"
                  ? String(decision.message)
                  : `Now using ${(decision.fixtures as string[])?.join(", ")}.`}
              </p>
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}
