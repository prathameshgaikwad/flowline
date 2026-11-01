import { useMemo, useState } from "react";
import {
  Activity,
  CheckCircle2,
  FileText,
  LayoutList,
  ShieldCheck,
  X,
} from "lucide-react";
import type { AgentEvent, DesignState, PlanStep, Project } from "../types";
import {
  designStatus,
  displayCounts,
  drawingCounts,
  fixtureName,
  plumbingAreasLabel,
  roomNameFor,
  selectedLayout,
  sheetSizeLabel,
} from "../lib/labels";
import { useModalFocus } from "../hooks/useModalFocus";
import { AgentNoteCard } from "./AgentNoteCard";
import { CandidateTable } from "./CandidateTable";
import { DecisionList } from "./DecisionList";
import { PlanStepper } from "./PlanStepper";
import { ReasoningCard } from "./ReasoningCard";
import { ToolTimeline } from "./ToolTimeline";
import { ValidationPanel } from "./ValidationPanel";
import {
  Badge,
  Button,
  cx,
  Dot,
  EmptyState,
  IconButton,
  SegmentedControl,
} from "./ui";

export type DetailsTab = "design" | "checks" | "activity";
type ActivityFilter = "all" | "tools" | "notes";

export function DetailsDrawer({
  open,
  tab,
  onTab,
  design,
  project,
  events,
  busy,
  onClose,
  onApplyFix,
  onRunChecks,
  onViewSheet,
}: {
  open: boolean;
  tab: DetailsTab;
  onTab: (tab: DetailsTab) => void;
  design: DesignState | null;
  project: Project | null;
  events: AgentEvent[];
  busy: boolean;
  onClose: () => void;
  onApplyFix: (fixId: string) => void;
  onRunChecks: () => void;
  onViewSheet: () => void;
}) {
  const [activityFilter, setActivityFilter] = useState<ActivityFilter>("all");
  const containerRef = useModalFocus(open, onClose);

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
  const plan = useMemo(() => {
    const plans = events.filter((event) => event.type === "plan");
    return (
      (plans[plans.length - 1]?.steps as PlanStep[] | undefined) ||
      design?.plan ||
      []
    );
  }, [events, design]);
  const rejectedReasons = useMemo(() => {
    const map: Record<string, string> = {};
    const primaryRoom = design?.design?.room_id || design?.room_id;
    for (const decision of design?.decisions || []) {
      if (
        decision.kind === "layout_selected" &&
        (!decision.room_id || decision.room_id === primaryRoom)
      ) {
        for (const item of (decision.rejected || []) as {
          id: string;
          reason: string;
        }[]) {
          map[item.id] = item.reason;
        }
      }
    }
    return map;
  }, [design]);

  if (!open) return null;

  const candidate = selectedLayout(design);
  const status = designStatus(design, busy);
  const display = displayCounts(design);
  const issueCount = display.ERROR + display.WARNING;
  const drawing = drawingCounts(design);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div
        className="absolute inset-0 bg-ink/20"
        onClick={onClose}
        role="presentation"
      />
      <aside
        ref={containerRef}
        className="relative flex h-full w-full max-w-[560px] flex-col border-l border-line bg-raised shadow-2xl animate-slide-in"
        data-testid="details-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="details-title"
        tabIndex={-1}
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-line px-4 py-3.5">
          <div className="min-w-0">
            <h2 id="details-title" className="text-ui font-semibold text-ink">
              Design details
            </h2>
            <div className="mt-1 flex items-center gap-1.5 text-xs text-muted">
              <Dot tone={status.tone} pulse={status.pulse} />
              <span>{status.label}</span>
              <span aria-hidden="true" className="text-line-strong">
                ·
              </span>
              <span className="truncate font-mono">
                {design?.design_id || "No design selected"}
              </span>
            </div>
          </div>
          <IconButton label="Close design details" onClick={onClose}>
            <X size={19} aria-hidden="true" />
          </IconButton>
        </div>

        <div className="shrink-0 border-b border-line px-3 py-2.5">
          <SegmentedControl
            label="Design detail sections"
            className="w-full [&>button]:flex-1"
            value={tab}
            onChange={onTab}
            options={[
              {
                value: "design",
                label: "Design",
                icon: <LayoutList size={15} aria-hidden="true" />,
                testId: "details-tab-design",
              },
              {
                value: "checks",
                label: "Checks",
                icon: <ShieldCheck size={15} aria-hidden="true" />,
                count: issueCount,
                testId: "details-tab-checks",
              },
              {
                value: "activity",
                label: "Activity",
                icon: <Activity size={15} aria-hidden="true" />,
                testId: "details-tab-activity",
              },
            ]}
          />
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
          {!design?.design && tab !== "activity" ? (
            <EmptyState
              icon={<LayoutList size={20} />}
              title={design?.design_id ? "No layout yet" : "No design yet"}
              description={
                design?.design_id
                  ? "The assistant could not produce a layout. Return to the workspace, adjust the fixtures or room, and try again."
                  : "Start a design to see the selected layout, alternatives, fixtures, and decision history."
              }
              action={
                <Button variant="secondary" onClick={onClose}>
                  Back to workspace
                </Button>
              }
            />
          ) : null}

          {design?.design && tab === "design" && (
            <div className="space-y-6">
              <section
                aria-labelledby="current-design-title"
                className="rounded-card border border-line bg-accent-soft/55 p-4"
              >
                <div className="flex items-center gap-2 text-label font-semibold text-accent">
                  <CheckCircle2 size={16} aria-hidden="true" />
                  Current design
                </div>
                <h3
                  id="current-design-title"
                  className="mt-2 text-lg font-semibold tracking-[-0.02em] text-ink"
                >
                  {design.design.layout_id || candidate?.id || "Selected layout"}
                  {candidate?.pattern ? ` · ${candidate.pattern}` : ""}
                </h3>
                <p className="mt-1 text-label leading-relaxed text-muted">
                  {candidate?.rationale_hint ||
                    design.design.rationale ||
                    "No rationale recorded."}
                </p>
                <div className="mt-3 grid grid-cols-3 divide-x divide-accent/15 border-t border-accent/15 pt-3">
                  <div>
                    <div className="text-lg font-semibold text-ink tabular-nums">
                      {design.design.fixtures.length}
                    </div>
                    <div className="text-xs text-muted">Fixtures</div>
                  </div>
                  <div className="pl-3">
                    <div className="text-lg font-semibold text-ink tabular-nums">
                      {design.design.pipes.length}
                    </div>
                    <div className="text-xs text-muted">Pipes</div>
                  </div>
                  <div className="pl-3">
                    <div className="text-lg font-semibold text-ink tabular-nums">
                      {display.PASS}
                    </div>
                    <div className="text-xs text-muted">Checks passed</div>
                  </div>
                </div>
                {design.design.room_plans?.length ? (
                  <div className="mt-3 border-t border-accent/15 pt-3">
                    <div className="text-xs font-medium text-muted">
                      {plumbingAreasLabel(
                        project,
                        design.design.room_plans.map((plan) => plan.room_id),
                      )}
                    </div>
                    <ul className="mt-2 space-y-1.5">
                      {design.design.room_plans.map((plan) => (
                        <li
                          key={plan.room_id}
                          className="flex items-center gap-2 text-label text-ink-soft"
                        >
                          <span className="min-w-0 flex-1 truncate">
                            {roomNameFor(project, plan.room_id)}
                          </span>
                          <Badge tone="neutral" className="font-mono">
                            {plan.layout_id || "Draft"}
                          </Badge>
                          <span className="text-xs text-muted">
                            {
                              design.design?.fixtures.filter(
                                (fixture) => fixture.room_id === plan.room_id,
                              ).length
                            }{" "}
                            fixtures
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </section>

              <section aria-labelledby="layout-options-title">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <h3
                    id="layout-options-title"
                    className="text-label font-semibold text-ink-soft"
                  >
                    Layout options
                  </h3>
                  <span className="text-xs text-muted">
                    Deterministic fit score
                  </span>
                </div>
                <CandidateTable
                  candidates={design.candidates}
                  rejectedReasons={rejectedReasons}
                />
              </section>

              <section aria-labelledby="fixtures-title">
                <h3
                  id="fixtures-title"
                  className="mb-2 text-label font-semibold text-ink-soft"
                >
                  Fixtures
                </h3>
                {design.design.room_plans?.length ? (
                  <div className="space-y-3">
                    {design.design.room_plans.map((plan) => {
                      const fixtures = design.design?.fixtures.filter(
                        (fixture) => fixture.room_id === plan.room_id,
                      ) || [];
                      return (
                        <div key={plan.room_id}>
                          <div className="mb-1.5 text-xs font-medium text-muted">
                            {roomNameFor(project, plan.room_id)}
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {fixtures.map((fixture) => (
                              <Badge
                                key={fixture.id}
                                tone="neutral"
                                className="min-h-7 px-2.5 text-label"
                              >
                                {fixtureName(fixture.type)}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {design.design.fixtures.map((fixture) => (
                      <Badge
                        key={fixture.id}
                        tone="neutral"
                        className="min-h-7 px-2.5 text-label"
                      >
                        {fixtureName(fixture.type)}
                      </Badge>
                    ))}
                  </div>
                )}
              </section>

              {design.design.assumptions?.length ? (
                <section aria-labelledby="assumptions-title">
                  <h3
                    id="assumptions-title"
                    className="mb-2 text-label font-semibold text-ink-soft"
                  >
                    Assumptions
                  </h3>
                  <ul className="space-y-2 rounded-card border border-line bg-sunken px-4 py-3 text-label leading-relaxed text-muted">
                    {design.design.assumptions.map((item) => (
                      <li key={item} className="flex gap-2">
                        <span
                          className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-line-strong"
                          aria-hidden="true"
                        />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              <section aria-labelledby="history-title">
                <h3
                  id="history-title"
                  className="mb-2 text-label font-semibold text-ink-soft"
                >
                  History
                </h3>
                <DecisionList
                  decisions={design.decisions}
                  project={project}
                  roomLayouts={Object.fromEntries(
                    (design.design.room_plans || []).map((plan) => [
                      plan.room_id,
                      plan.layout_id,
                    ]),
                  )}
                  currentLayoutId={
                    design.design.layout_id || candidate?.id || null
                  }
                />
              </section>
            </div>
          )}

          {design?.design && tab === "checks" && (
            <div className="space-y-4">
              <ValidationPanel
                design={design}
                project={project}
                busy={busy}
                onApplyFix={onApplyFix}
                onRunChecks={onRunChecks}
              />
              {design.sheet_ready && design.sheet && (
                <section className="rounded-card border border-line bg-raised p-4">
                  <div className="flex items-center gap-2">
                    <FileText size={16} className="text-muted" aria-hidden="true" />
                    <h3 className="text-ui font-semibold text-ink">
                      Drawing review
                    </h3>
                    <Badge
                      tone={
                        drawing.ERROR
                          ? "danger"
                          : drawing.WARNING
                            ? "warning"
                            : "success"
                      }
                      className="ml-auto"
                    >
                      {drawing.ERROR
                        ? `${drawing.ERROR} errors`
                        : drawing.WARNING
                          ? `${drawing.WARNING} warnings`
                          : "Ready"}
                    </Badge>
                  </div>
                  <div className="mt-1.5 text-label text-muted">
                    {sheetSizeLabel(design.sheet)} · 1:{design.sheet.scale} ·{" "}
                    {design.sheet_pages || 1}{" "}
                    {(design.sheet_pages || 1) === 1 ? "page" : "pages"}
                  </div>
                  <div className="mt-2 space-y-2">
                    {(design.drawing_review || [])
                      .filter((check) => check.severity !== "PASS")
                      .slice(0, 5)
                      .map((check) => (
                        <div
                          key={check.rule_id}
                          className="text-label leading-relaxed text-muted"
                        >
                          <span
                            className={cx(
                              "font-semibold",
                              check.severity === "ERROR"
                                ? "text-danger"
                                : "text-warning",
                            )}
                          >
                            {check.severity}
                          </span>{" "}
                          {check.message}
                        </div>
                      ))}
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="mt-3"
                    onClick={onViewSheet}
                  >
                    <FileText size={14} aria-hidden="true" /> View sheet
                  </Button>
                </section>
              )}
            </div>
          )}

          {tab === "activity" && (
            <div className="space-y-6">
              <section aria-labelledby="plan-title">
                <h3
                  id="plan-title"
                  className="mb-2 flex items-center gap-1.5 text-label font-semibold text-ink-soft"
                >
                  Plan
                  {busy && <Dot tone="accent" pulse />}
                </h3>
                <div className="rounded-card border border-line bg-sunken/70 p-4">
                  <PlanStepper steps={plan} />
                  {!plan.length && (
                    <div className="mt-2 text-xs text-muted">
                      The plan appears when the assistant starts working.
                    </div>
                  )}
                </div>
              </section>

              <section aria-labelledby="activity-title">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <h3
                    id="activity-title"
                    className="text-label font-semibold text-ink-soft"
                  >
                    Activity
                  </h3>
                  <SegmentedControl
                    label="Filter activity"
                    compact
                    value={activityFilter}
                    onChange={setActivityFilter}
                    options={[
                      { value: "all", label: "All" },
                      { value: "tools", label: "Tools" },
                      { value: "notes", label: "Notes" },
                    ]}
                  />
                </div>
                <div className="space-y-4">
                  {activityFilter !== "notes" && (
                    <ToolTimeline events={events} />
                  )}
                  {activityFilter !== "tools" && (
                    <div>
                      <h4 className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-muted">
                        Assistant notes
                      </h4>
                      {!thinking.length ? (
                        <p className="text-label leading-relaxed text-muted">
                          No reasoning or interim notes captured yet.
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {thinking.map((event, index) =>
                            event.type === "reasoning" ? (
                              <ReasoningCard
                                key={`${event.seq || index}`}
                                content={String(event.content || "")}
                                iteration={
                                  Number(event.iteration || 0) || undefined
                                }
                                defaultOpen={index === thinking.length - 1}
                              />
                            ) : (
                              <AgentNoteCard
                                key={`note-${event.seq || index}`}
                                content={String(event.content || "")}
                                iteration={
                                  Number(event.iteration || 0) || undefined
                                }
                                defaultOpen={index === thinking.length - 1}
                              />
                            ),
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </section>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
