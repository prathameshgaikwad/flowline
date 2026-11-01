import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  CheckCircle2,
  Download,
  FileText,
  ShieldCheck,
  TriangleAlert,
  X,
} from "lucide-react";
import type { DesignState } from "../types";
import {
  displayCounts,
  drawingCounts,
  sheetSizeLabel,
} from "../lib/labels";
import { useModalFocus } from "../hooks/useModalFocus";
import {
  Button,
  cx,
  Field,
  IconButton,
  InlineAlert,
  inputClass,
} from "./ui";

export function ApprovalDialog({
  open,
  design,
  busy,
  onClose,
  onApprove,
}: {
  open: boolean;
  design: DesignState | null;
  busy: boolean;
  onClose: () => void;
  onApprove: (approver: string) => void;
}) {
  const [approver, setApprover] = useState("Demo Engineer");
  const [approverError, setApproverError] = useState<string | null>(null);
  const approverRef = useRef<HTMLInputElement>(null);
  const downloadRef = useRef<HTMLAnchorElement>(null);

  function closeDialog() {
    onClose();
    window.requestAnimationFrame(() => {
      document
        .querySelector<HTMLElement>('[data-testid="approve-button"]')
        ?.focus();
    });
  }

  const containerRef = useModalFocus<HTMLFormElement>(
    open,
    closeDialog,
    approverRef,
  );

  useEffect(() => {
    if (!open) return;
    setApproverError(null);
  }, [open]);

  useEffect(() => {
    if (!open || !design?.download_url) return;
    const frame = window.requestAnimationFrame(() => {
      downloadRef.current?.focus();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [design?.download_url, open]);

  if (!open || !design) return null;

  const noValidation = !design.validation?.length;
  const counts = displayCounts(design);
  const drawing = drawingCounts(design);
  const blocked = !design.design;
  const approved = Boolean(design.download_url);
  const sheetPdf =
    design.sheet_ready && design.design_id
      ? design.sheet_pdf_url ||
        `/api/designs/${design.design_id}/sheet.pdf`
      : null;
  const problems = [
    ...(noValidation
      ? [
          {
            key: "no-checks",
            severity: "WARNING" as const,
            label: "CHECKS",
            message: "No checks have been run for this design.",
          },
        ]
      : []),
    ...(design.stale
      ? [
          {
            key: "stale",
            severity: "WARNING" as const,
            label: "CHECKS",
            message:
              "The code standard changed after the last check. Results may be outdated.",
          },
        ]
      : []),
    ...(design.issues || [])
      .filter((issue) => issue.severity !== "PASS")
      .map((issue, index) => ({
        key: `design-${issue.rule_id}-${index}`,
        severity: issue.severity,
        label: issue.rule_id,
        message: issue.message,
      })),
    ...(design.drawing_review || [])
      .filter((issue) => issue.severity !== "PASS")
      .map((issue, index) => ({
        key: `drawing-${issue.rule_id}-${index}`,
        severity: issue.severity,
        label: `DRAWING ${issue.rule_id}`,
        message: issue.message,
      })),
  ];
  const hasProblems = problems.length > 0;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (blocked || busy) return;
    if (!approver.trim()) {
      setApproverError("Enter the name of the engineer approving this design.");
      approverRef.current?.focus();
      return;
    }
    setApproverError(null);
    onApprove(approver.trim());
  };

  return (
    <div
      className="fixed inset-0 z-[60] grid place-items-center overflow-y-auto bg-ink/35 p-4 backdrop-blur-[2px]"
      onMouseDown={(event) => {
        if (!busy && event.target === event.currentTarget) closeDialog();
      }}
    >
      <form
        ref={containerRef}
        onSubmit={submit}
        className="my-auto w-full max-w-[560px] overflow-hidden rounded-overlay border border-line bg-raised shadow-2xl animate-fade-up"
        data-testid="approval-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="approval-title"
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div className="flex items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-card bg-accent-soft text-accent">
              <ShieldCheck size={19} aria-hidden="true" />
            </span>
            <div>
              <h2
                id="approval-title"
                className="text-lg font-semibold tracking-[-0.02em] text-ink"
              >
                {approved ? "Approved and ready" : "Review & export"}
              </h2>
              <p className="mt-0.5 text-label leading-relaxed text-muted">
                {approved
                  ? "Your reviewed DXF is ready to download."
                  : "Review the issues and sign off to generate the DXF."}
              </p>
            </div>
          </div>
          <IconButton label="Close export review" onClick={closeDialog}>
            <X size={19} aria-hidden="true" />
          </IconButton>
        </div>

        <div className="space-y-4 px-5 py-4">
          <div className="grid grid-cols-3 gap-2">
            <Metric value={counts.PASS} label="Passed" tone="success" />
            <Metric value={counts.WARNING} label="Warnings" tone="warning" />
            <Metric value={counts.ERROR} label="Errors" tone="danger" />
          </div>

          {design.sheet && design.sheet_ready && (
            <div className="flex items-center gap-2.5 rounded-card border border-line bg-sunken px-3.5 py-3 text-label text-ink-soft">
              <FileText size={16} className="shrink-0 text-muted" aria-hidden="true" />
              <span className="min-w-0 flex-1">
                {sheetSizeLabel(design.sheet)} · 1:{design.sheet.scale} ·{" "}
                {design.sheet_pages || 1}{" "}
                {(design.sheet_pages || 1) === 1 ? "page" : "pages"}
              </span>
              <span
                className={cx(
                  "shrink-0 font-medium",
                  drawing.ERROR
                    ? "text-danger"
                    : drawing.WARNING
                      ? "text-warning"
                      : "text-success",
                )}
              >
                {drawing.ERROR
                  ? `${drawing.ERROR} drawing errors`
                  : drawing.WARNING
                    ? `${drawing.WARNING} drawing warnings`
                    : "Drawing ready"}
              </span>
            </div>
          )}

          {approved ? (
            <InlineAlert tone="success" icon={<CheckCircle2 size={17} />}>
              {hasProblems
                ? "Approved and exported. The issues below are included in the record."
                : "Approved. The DXF and PDF are ready to download."}
            </InlineAlert>
          ) : blocked ? (
            <InlineAlert tone="warning" icon={<TriangleAlert size={17} />}>
              Generate a design before exporting.
            </InlineAlert>
          ) : hasProblems ? (
            <InlineAlert tone="warning" icon={<TriangleAlert size={17} />}>
              <div className="font-semibold">This design has issues</div>
              <p className="mt-1">
                Review the problems below. You can still approve and export the
                DXF with these issues recorded.
              </p>
            </InlineAlert>
          ) : (
            <InlineAlert tone="success" icon={<CheckCircle2 size={17} />}>
              All checks and drawing checks pass.
            </InlineAlert>
          )}

          {hasProblems && (
            <section aria-labelledby="approval-problems-title" data-testid="approval-problems">
              <h3
                id="approval-problems-title"
                className="text-label font-semibold text-ink-soft"
              >
                Issues to review ({problems.length})
              </h3>
              <ul className="mt-2 max-h-56 space-y-2 overflow-y-auto rounded-card border border-line bg-sunken p-3">
                {problems.map((problem) => (
                  <li key={problem.key} className="flex gap-2 text-label leading-relaxed">
                    <span
                      className={cx(
                        "mt-0.5 shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase",
                        problem.severity === "ERROR"
                          ? "bg-danger-soft text-danger"
                          : "bg-warning-soft text-warning",
                      )}
                    >
                      {problem.severity}
                    </span>
                    <span className="min-w-0">
                      <span className="mr-2 font-mono text-xs text-muted">
                        {problem.label}
                      </span>
                      <span className="text-ink-soft">{problem.message}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {!approved && (
            <Field
              label="Approving engineer"
              htmlFor="approver-name"
              error={approverError}
              optional={false}
            >
              <input
                ref={approverRef}
                id="approver-name"
                name="approver"
                autoComplete="name"
                value={approver}
                onChange={(event) => {
                  setApprover(event.target.value);
                  if (approverError) setApproverError(null);
                }}
                className={inputClass}
                placeholder="Engineer name"
                aria-invalid={Boolean(approverError)}
                aria-describedby={approverError ? "approver-name-error" : undefined}
              />
            </Field>
          )}

          <p className="text-xs leading-relaxed text-muted">
            Demo rule set. This is not a compliance certificate. The local
            authority and a licensed engineer govern the issued design.
          </p>
        </div>

        <div
          className={cx(
            "flex flex-wrap items-center gap-3 border-t border-line bg-sunken/70 px-5 py-4",
            approved ? "justify-between" : "justify-end",
          )}
        >
          {approved ? (
            <div className="flex flex-wrap gap-2">
              <a
                ref={downloadRef}
                href={design.download_url || "#"}
                data-testid="dialog-download"
                className="inline-flex min-h-11 items-center gap-2 rounded-control bg-accent px-3 text-ui font-semibold text-on-accent transition hover:bg-accent-hover lg:min-h-9"
              >
                <Download size={16} aria-hidden="true" /> Download DXF
              </a>
              {sheetPdf && (
                <a
                  href={sheetPdf}
                  data-testid="dialog-pdf"
                  className="inline-flex min-h-11 items-center gap-2 rounded-control border border-line-strong bg-raised px-3 text-ui font-medium text-ink-soft transition hover:bg-surface lg:min-h-9"
                >
                  <Download size={16} aria-hidden="true" /> PDF
                </a>
              )}
            </div>
          ) : null}
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={closeDialog}>
              {approved ? "Done" : "Cancel"}
            </Button>
            {!approved && (
              <Button
                type="submit"
                onClick={() => {
                  if (!approver.trim()) {
                    setApproverError(
                      "Enter the name of the engineer approving this design.",
                    );
                    approverRef.current?.focus();
                  }
                }}
                disabled={blocked || busy}
                data-testid="dialog-approve"
              >
                <ShieldCheck size={16} aria-hidden="true" />
                {busy ? "Generating export…" : "Approve & generate DXF"}
              </Button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}

function Metric({
  value,
  label,
  tone,
}: {
  value: number;
  label: string;
  tone: "success" | "warning" | "danger";
}) {
  const tones = {
    success: "border-success-line bg-success-soft text-success",
    warning: "border-warning-line bg-warning-soft text-warning",
    danger: "border-danger-line bg-danger-soft text-danger",
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
