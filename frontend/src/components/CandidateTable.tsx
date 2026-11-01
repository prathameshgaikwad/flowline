import { CheckCircle2, Circle } from "lucide-react";
import type { Candidate } from "../types";
import { EmptyState } from "./ui";

export function CandidateTable({
  candidates,
  rejectedReasons = {},
}: {
  candidates: Candidate[];
  rejectedReasons?: Record<string, string>;
}) {
  if (!candidates.length) {
    return (
      <EmptyState
        title="No layout options yet"
        description="The assistant creates layout candidates after reading the room and fixtures."
      />
    );
  }
  return (
    <div
      className="overflow-hidden rounded-card border border-line"
      data-testid="candidate-table"
    >
      <table className="w-full table-fixed border-collapse text-left">
        <caption className="sr-only">
          Compared layout options ordered by fit score
        </caption>
        <thead className="bg-sunken">
          <tr className="border-b border-line text-xs font-medium text-muted">
            <th scope="col" className="w-[38%] px-3 py-2.5 font-medium">
              Layout
            </th>
            <th scope="col" className="w-[18%] px-2 py-2.5 text-right font-medium">
              Score
            </th>
            <th scope="col" className="w-[44%] px-3 py-2.5 font-medium">
              Outcome
            </th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((candidate) => {
            const reason =
              rejectedReasons[candidate.id] ||
              (candidate.violations.length
                ? `Doesn't meet: ${candidate.violations.join("; ")}`
                : candidate.rationale_hint);
            return (
              <tr
                key={candidate.id}
                className={
                  candidate.selected
                    ? "border-b border-line bg-accent-soft/60 last:border-b-0"
                    : "border-b border-line last:border-b-0"
                }
              >
                <th scope="row" className="px-3 py-3 align-top font-normal">
                  <span className="flex items-start gap-2">
                    {candidate.selected ? (
                      <CheckCircle2
                        size={16}
                        className="mt-0.5 shrink-0 text-accent"
                        aria-hidden="true"
                      />
                    ) : (
                      <Circle
                        size={16}
                        className="mt-0.5 shrink-0 text-line-strong"
                        aria-hidden="true"
                      />
                    )}
                    <span className="min-w-0">
                      <span className="block font-mono text-xs font-semibold text-ink">
                        {candidate.id}
                      </span>
                      <span className="mt-0.5 block text-label font-medium text-ink-soft">
                        {candidate.pattern.replaceAll("_", " ")}
                      </span>
                    </span>
                  </span>
                </th>
                <td className="px-2 py-3 text-right align-top font-mono text-label font-medium text-ink-soft tabular-nums">
                  {candidate.score.toLocaleString()}
                </td>
                <td className="px-3 py-3 align-top">
                  {candidate.selected ? (
                    <span className="inline-flex rounded-full bg-accent px-2 py-0.5 text-xs font-semibold text-on-accent">
                      Selected
                    </span>
                  ) : (
                    <span className="text-xs leading-relaxed text-muted">
                      {reason}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
