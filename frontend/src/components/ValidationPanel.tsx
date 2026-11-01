import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  RefreshCw,
  ShieldCheck,
  Wrench,
  XCircle,
} from "lucide-react";
import type { DesignState, Project } from "../types";
import { displayCounts, displayIssues, roomNameFor } from "../lib/labels";
import {
  Button,
  cx,
  EmptyState,
  InlineAlert,
  SegmentedControl,
} from "./ui";

type CheckFilter = "all" | "errors" | "warnings";

export function ValidationPanel({
  design,
  project,
  busy,
  onApplyFix,
  onRunChecks,
}: {
  design: DesignState | null;
  project?: Project | null;
  busy: boolean;
  onApplyFix: (fixId: string) => void;
  onRunChecks?: () => void;
}) {
  const [filter, setFilter] = useState<CheckFilter>("all");
  if (!design) {
    return <p className="text-label text-muted">No design selected.</p>;
  }
  const counts = displayCounts(design);
  const issues = displayIssues(design);
  const hasValidation = Boolean(design.validation?.length);
  const rank = { ERROR: 0, WARNING: 1, PASS: 2 };
  const ordered = [...issues]
    .sort((a, b) => (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3))
    .filter((issue) =>
      filter === "all"
        ? true
        : filter === "errors"
          ? issue.severity === "ERROR"
          : issue.severity === "WARNING",
    );

  return (
    <div className="space-y-4" data-testid="validation-panel">
      <div className="grid grid-cols-3 gap-2">
        <CountCard value={counts.PASS} label="Passed" tone="success" />
        <CountCard value={counts.WARNING} label="Warnings" tone="warning" />
        <CountCard value={counts.ERROR} label="Errors" tone="danger" />
      </div>

      {design.stale && (
        <InlineAlert tone="warning" icon={<RefreshCw size={17} />}>
          The code standard changed. Run the checks again before exporting.
        </InlineAlert>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {onRunChecks && (
          <Button
            variant={design.stale || !hasValidation ? "primary" : "secondary"}
            onClick={onRunChecks}
            disabled={busy}
            className="flex-1 sm:flex-none"
          >
            <ShieldCheck size={16} aria-hidden="true" />
            {busy
              ? "Checking…"
              : hasValidation
                ? "Run checks again"
                : "Run the first check"}
          </Button>
        )}
        {hasValidation && issues.length > 0 && (
          <SegmentedControl
            label="Filter check results"
            compact
            value={filter}
            onChange={setFilter}
            options={[
              { value: "all", label: "All", count: issues.length },
              { value: "errors", label: "Errors", count: counts.ERROR },
              {
                value: "warnings",
                label: "Warnings",
                count: counts.WARNING,
              },
            ]}
          />
        )}
      </div>

      {!hasValidation && (
        <EmptyState
          icon={<ShieldCheck size={20} />}
          title="No checks yet"
          description="Run the active code standard before exporting. Results include measured values and the cited rule."
        />
      )}

      {ordered.map((issue, index) => {
        const error = issue.severity === "ERROR";
        return (
          <article
            key={`${issue.rule_id}-${index}`}
            className={cx(
              "rounded-card border p-4",
              error
                ? "border-danger-line bg-danger-soft/55"
                : "border-warning-line bg-warning-soft/55",
            )}
          >
            <div className="flex items-start gap-2.5">
              {error ? (
                <XCircle
                  size={17}
                  className="mt-0.5 shrink-0 text-danger"
                  aria-hidden="true"
                />
              ) : (
                <AlertTriangle
                  size={17}
                  className="mt-0.5 shrink-0 text-warning"
                  aria-hidden="true"
                />
              )}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={cx(
                      "text-xs font-semibold uppercase tracking-[0.06em]",
                      error ? "text-danger" : "text-warning",
                    )}
                  >
                    {issue.severity}
                  </span>
                  <span className="rounded bg-surface/70 px-1.5 py-0.5 font-mono text-xs font-medium text-muted">
                    {issue.rule_id}
                  </span>
                  {issue.affected?.room_id ? (
                    <span className="rounded bg-surface/70 px-1.5 py-0.5 text-xs font-medium text-ink-soft">
                      {roomNameFor(project || null, String(issue.affected.room_id))}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1.5 text-ui leading-relaxed text-ink-soft">
                  {issue.message}
                </p>
                {(issue.measured != null || issue.required != null) && (
                  <div className="mt-2 grid gap-2 text-label sm:grid-cols-2">
                    {issue.measured != null && (
                      <div className="rounded-control bg-surface/70 px-2.5 py-2">
                        <div className="text-xs text-muted">Measured</div>
                        <div className="mt-0.5 font-medium text-ink">
                          {String(issue.measured)}
                        </div>
                      </div>
                    )}
                    {issue.required != null && (
                      <div className="rounded-control bg-surface/70 px-2.5 py-2">
                        <div className="text-xs text-muted">Required</div>
                        <div className="mt-0.5 font-medium text-ink">
                          {String(issue.required)}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                <details className="group mt-2">
                  <summary className="flex min-h-11 cursor-pointer lg:min-h-8 list-none items-center gap-1 text-label font-medium text-muted transition hover:text-ink">
                    <ChevronDown
                      size={13}
                      className="transition-transform group-open:rotate-180"
                      aria-hidden="true"
                    />
                    Rule basis
                  </summary>
                  <p className="mt-1 rounded-control bg-surface/70 px-3 py-2 text-label leading-relaxed text-muted">
                    {issue.source}
                  </p>
                </details>
              </div>
            </div>
          </article>
        );
      })}

      {hasValidation && issues.length === 0 && (
        <InlineAlert tone="success" icon={<CheckCircle2 size={17} />}>
          All checks pass.
        </InlineAlert>
      )}

      {hasValidation && ordered.length === 0 && filter !== "all" && (
        <p className="text-label text-muted">
          No {filter === "errors" ? "errors" : "warnings"} match this filter.
        </p>
      )}

      {counts.ERROR > 0 && !design.fixes?.length && (
        <InlineAlert tone="warning" icon={<AlertTriangle size={17} />}>
          No automatic fix can clear these errors. Remove a fixture, use a larger
          room, or ask the assistant to re-plan.
        </InlineAlert>
      )}

      {design.fixes?.length > 0 && (
        <section
          aria-labelledby="suggested-fixes-title"
          className="rounded-card border border-accent/20 bg-accent-soft/60 p-4"
        >
          <div className="flex items-center gap-2 text-label font-semibold text-accent">
            <Wrench size={16} aria-hidden="true" />
            <h3 id="suggested-fixes-title">Suggested fixes</h3>
          </div>
          <div className="mt-2.5 space-y-2">
            {design.fixes.map((fix) => (
              <button
                key={fix.id}
                type="button"
                disabled={busy}
                onClick={() => onApplyFix(fix.id)}
                className="min-h-11 w-full rounded-control border border-accent/20 bg-raised px-3 py-2.5 text-left transition hover:border-accent/40 hover:bg-surface disabled:opacity-50"
              >
                <span className="block text-label font-semibold text-ink">
                  {fix.kind.replaceAll("_", " ")}
                </span>
                <span className="mt-0.5 block text-label leading-relaxed text-muted">
                  {fix.description}
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="rounded-card bg-sunken px-3.5 py-2.5 text-xs leading-relaxed text-muted">
        Demo rule set. Not a compliance certificate.
      </div>
    </div>
  );
}

function CountCard({
  value,
  label,
  tone,
}: {
  value: number;
  label: string;
  tone: "success" | "warning" | "danger";
}) {
  const tones = {
    success: "text-success bg-success-soft border-success-line",
    warning: "text-warning bg-warning-soft border-warning-line",
    danger: "text-danger bg-danger-soft border-danger-line",
  };
  return (
    <div
      className={cx(
        "rounded-card border px-3 py-2.5",
        value > 0 ? tones[tone] : "border-line bg-sunken text-muted",
      )}
    >
      <div className="text-xl font-semibold tabular-nums">{value}</div>
      <div className="mt-0.5 text-xs font-medium opacity-80">{label}</div>
    </div>
  );
}
