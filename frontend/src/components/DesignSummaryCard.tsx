import {
  ArrowRight,
  ChevronDown,
  Download,
  FileText,
  ListChecks,
  Maximize2,
  ShieldCheck,
} from "lucide-react";
import type { DesignState } from "../types";
import {
  designStatus,
  displayCounts,
  drawingCounts,
  selectedLayout,
  sheetSizeLabel,
} from "../lib/labels";
import { Markdown } from "./Markdown";
import { Badge, Button, cx, Dot } from "./ui";

export function DesignSummaryCard({
  design,
  content,
  busy,
  onOpenDetails,
  onOpenFullscreen,
  onOpenSheet,
  onApprove,
}: {
  design: DesignState;
  content?: string;
  busy: boolean;
  onOpenDetails: (tab: "design" | "checks" | "activity") => void;
  onOpenFullscreen: () => void;
  onOpenSheet: () => void;
  onApprove: () => void;
}) {
  const candidate = selectedLayout(design);
  const layoutId = design.design?.layout_id || candidate?.id || "Draft";
  const pattern = candidate?.pattern || "Selected layout";
  const roomIds =
    design.room_ids || design.room_plans?.map((plan) => plan.room_id) || [];
  const roomCount = roomIds.length || 1;
  const fixtureCount = design.design?.fixtures.length ?? design.fixtures.length;
  const pipeCount = design.design?.pipes.length ?? 0;
  const counts = displayCounts(design);
  const hasChecks = Boolean(design.validation?.length);
  const ready =
    Boolean(design.design) && hasChecks && !design.stale && counts.ERROR === 0;
  const sheet = design.sheet;
  const officeCounts = drawingCounts(design);
  const sheetReady = Boolean(design.sheet_ready && sheet);
  const sheetPdf =
    design.sheet_pdf_url ||
    (design.design_id ? `/api/designs/${design.design_id}/sheet.pdf` : null);
  const status = designStatus(design, busy);

  const primary = () => {
    if (design.approved && design.download_url) {
      return (
        <a
          href={design.download_url}
          className="inline-flex min-h-11 items-center lg:min-h-9 justify-center gap-2 rounded-control border border-transparent bg-accent px-3 text-ui font-semibold text-on-accent shadow-sm transition hover:bg-accent-hover"
          data-testid="summary-download"
        >
          <Download size={16} aria-hidden="true" /> Download DXF
        </a>
      );
    }
    const hasIssues =
      counts.ERROR > 0 ||
      counts.WARNING > 0 ||
      officeCounts.ERROR > 0 ||
      officeCounts.WARNING > 0 ||
      design.stale ||
      !hasChecks ||
      Boolean(design.fixes?.length);
    if (hasIssues) {
      return (
        <Button
          onClick={onApprove}
          disabled={busy}
          data-testid="summary-export"
        >
          <ShieldCheck size={16} aria-hidden="true" /> Review issues &amp; export
        </Button>
      );
    }
    if (ready) {
      return (
        <Button
          onClick={onApprove}
          disabled={busy}
          data-testid="summary-export"
        >
          <ShieldCheck size={16} aria-hidden="true" /> Review &amp; export
        </Button>
      );
    }
    return (
      <Button onClick={() => onOpenDetails("checks")}>
        <ListChecks size={16} aria-hidden="true" /> Open checks
      </Button>
    );
  };

  return (
    <div
      className="overflow-hidden rounded-card border border-line bg-raised shadow-card animate-fade-up"
      data-testid="summary-card"
    >
      <div className="p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2">
          <Dot tone={status.tone} pulse={status.pulse} />
          <span className="text-label font-semibold text-ink-soft">
            {status.label}
          </span>
          <Badge tone="neutral" className="ml-auto font-mono">
            {layoutId}
          </Badge>
        </div>

        <h2 className="mt-3 text-lg font-semibold tracking-[-0.02em] text-ink">
          {design.approved ? "Final plumbing design" : "Plumbing design"}
        </h2>
        <div className="mt-1 text-label text-muted">
          {roomCount} {roomCount === 1 ? "area" : "areas"} · {pattern} ·{" "}
          {fixtureCount} fixtures · {pipeCount} pipes
        </div>

        <div className="mt-4 grid grid-cols-3 divide-x divide-line rounded-card border border-line bg-sunken">
          <Stat value={counts.PASS} label="Passed" tone="success" />
          <Stat value={counts.WARNING} label="Warnings" tone="warning" />
          <Stat value={counts.ERROR} label="Errors" tone="danger" />
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          {primary()}
          <Button
            variant="secondary"
            onClick={() => onOpenDetails(design.approved ? "design" : "checks")}
          >
            <ListChecks size={16} aria-hidden="true" />
            {design.approved ? "Details" : "Checks"}
          </Button>
          <button
            type="button"
            onClick={onOpenFullscreen}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-control px-2 text-label font-medium text-muted transition hover:bg-sunken hover:text-ink lg:min-h-9"
          >
            <Maximize2 size={16} aria-hidden="true" /> Full plan
          </button>
        </div>

        {(candidate?.rationale_hint || design.design?.rationale) && (
          <p className="mt-3 line-clamp-3 text-label leading-relaxed text-muted">
            {candidate?.rationale_hint || design.design?.rationale}
          </p>
        )}

        {sheetReady && sheet && (
          <div className="mt-4 rounded-card border border-line bg-sunken px-3.5 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <FileText size={15} className="shrink-0 text-muted" aria-hidden="true" />
              <span className="min-w-0 flex-1 text-label font-medium leading-relaxed text-ink-soft">
                {sheetSizeLabel(sheet)} · 1:{sheet.scale} ·{" "}
                {design.sheet_pages || 1}{" "}
                {(design.sheet_pages || 1) === 1 ? "page" : "pages"}
              </span>
              <Badge
                tone={
                  officeCounts.ERROR
                    ? "danger"
                    : officeCounts.WARNING
                      ? "warning"
                      : "success"
                }
              >
                {officeCounts.ERROR
                  ? `${officeCounts.ERROR} errors`
                  : officeCounts.WARNING
                    ? `${officeCounts.WARNING} warnings`
                    : "Drawing ready"}
              </Badge>
            </div>
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={onOpenSheet}
                data-testid="summary-view-sheet"
                className="inline-flex min-h-11 lg:min-h-8 items-center gap-1.5 rounded-control border border-line-strong bg-raised px-2.5 text-label font-medium text-ink-soft transition hover:bg-surface hover:text-ink"
              >
                <FileText size={14} aria-hidden="true" /> View sheet
              </button>
              {sheetPdf && (
                <a
                  href={sheetPdf}
                  data-testid="summary-sheet-pdf"
                  className="inline-flex min-h-11 lg:min-h-8 items-center gap-1.5 rounded-control border border-line-strong bg-raised px-2.5 text-label font-medium text-ink-soft transition hover:bg-surface hover:text-ink"
                >
                  <Download size={14} aria-hidden="true" /> PDF
                </a>
              )}
              {design.approved && design.download_url && (
                <a
                  href={design.download_url}
                  data-testid="summary-sheet-dxf"
                  className="inline-flex min-h-11 lg:min-h-8 items-center gap-1.5 rounded-control border border-line-strong bg-raised px-2.5 text-label font-medium text-ink-soft transition hover:bg-surface hover:text-ink"
                >
                  <Download size={14} aria-hidden="true" /> DXF
                </a>
              )}
            </div>
          </div>
        )}

      </div>

      {content && (
        <details className="group border-t border-line bg-sunken/60 px-4 py-3 sm:px-5">
          <summary className="flex min-h-11 lg:min-h-8 cursor-pointer list-none items-center gap-1.5 text-label font-medium text-muted transition hover:text-ink">
            <ChevronDown
              size={14}
              className="transition-transform group-open:rotate-180"
              aria-hidden="true"
            />
            Full answer
          </summary>
          <div className="mt-2 border-t border-line pt-3">
            <Markdown>{content}</Markdown>
          </div>
        </details>
      )}

      <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-2 sm:px-5">
        <button
          type="button"
          onClick={() => onOpenDetails("design")}
          className="inline-flex min-h-11 items-center lg:min-h-9 gap-1 text-label font-medium text-muted transition hover:text-ink"
        >
          Other layouts
          <ArrowRight size={13} aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={() => onOpenDetails("activity")}
          className="inline-flex min-h-11 items-center lg:min-h-9 gap-1 text-label font-medium text-accent transition hover:text-accent-hover"
        >
          View activity
          <ArrowRight size={13} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

function Stat({
  value,
  label,
  tone,
}: {
  value: number;
  label: string;
  tone: "success" | "warning" | "danger";
}) {
  const tones = {
    success: "text-success",
    warning: "text-warning",
    danger: "text-danger",
  };
  return (
    <div className="min-w-0 px-3 py-2.5">
      <div
        className={cx(
          "text-xl font-semibold tabular-nums",
          value > 0 ? tones[tone] : "text-ink",
        )}
      >
        {value}
      </div>
      <div className="mt-0.5 text-xs font-medium text-muted">{label}</div>
    </div>
  );
}
