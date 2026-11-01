import { useRef } from "react";
import { FileText, Trash2, TriangleAlert, X } from "lucide-react";
import type { DesignSummary, Project } from "../types";
import {
  drawingName,
  roomNameFor,
  summaryStatusLabel,
  summaryStatusTone,
} from "../lib/labels";
import { useModalFocus } from "../hooks/useModalFocus";
import {
  Badge,
  Button,
  Dot,
  IconButton,
  InlineAlert,
  Spinner,
} from "./ui";

export function DeleteDesignDialog({
  design,
  project,
  running = false,
  busy,
  error,
  onClose,
  onConfirm,
}: {
  design: DesignSummary | null;
  project: Project;
  running?: boolean;
  busy: boolean;
  error?: string | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const containerRef = useModalFocus<HTMLDivElement>(
    Boolean(design),
    onClose,
    cancelRef,
  );

  if (!design) return null;

  const room = roomNameFor(project, design.room_id);

  return (
    <div
      className="fixed inset-0 z-[60] grid place-items-center overflow-y-auto bg-ink/35 p-4 backdrop-blur-[2px]"
      onMouseDown={(event) => {
        if (!busy && event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-design-title"
        aria-describedby="delete-design-description"
        className="my-auto w-full max-w-[520px] overflow-hidden rounded-overlay border border-line bg-raised shadow-2xl animate-fade-up"
        data-testid="delete-design-dialog"
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div className="flex items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-card bg-danger-soft text-danger">
              <Trash2 size={19} aria-hidden="true" />
            </span>
            <div>
              <h2
                id="delete-design-title"
                className="text-lg font-semibold tracking-[-0.02em] text-ink"
              >
                Delete this design?
              </h2>
              <p className="mt-0.5 text-label leading-relaxed text-muted">
                This cannot be undone.
              </p>
            </div>
          </div>
          <IconButton
            label="Cancel deleting design"
            onClick={onClose}
            disabled={busy}
          >
            <X size={19} aria-hidden="true" />
          </IconButton>
        </div>

        <div className="space-y-4 px-5 py-4">
          <div className="rounded-card border border-line bg-sunken px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <Dot tone={summaryStatusTone(design.status)} />
              <span className="text-ui font-semibold text-ink">{room}</span>
              <Badge tone="neutral" className="ml-auto">
                {summaryStatusLabel(design.status)}
              </Badge>
            </div>
            <div className="mt-1 font-mono text-xs text-muted">
              {design.layout_id || design.design_id} · {drawingName(project)}
            </div>
          </div>

          <div id="delete-design-description" className="space-y-3">
            <InlineAlert tone="danger" icon={<TriangleAlert size={17} />}>
              The design state, conversation, activity log, preview, sheet, and
              exported files will be removed from this project.
            </InlineAlert>
            <div className="flex items-start gap-2.5 rounded-card border border-line px-3.5 py-3 text-label leading-relaxed text-muted">
              <FileText
                size={16}
                className="mt-0.5 shrink-0"
                aria-hidden="true"
              />
              <span>
                The source drawing and any other designs are not affected.
              </span>
            </div>
            {running && (
              <p className="rounded-control border border-warning-line bg-warning-soft px-3.5 py-3 text-label leading-relaxed text-warning">
                The assistant is working on this design. Deleting it will stop
                that run before removing the files.
              </p>
            )}
          </div>

          {error && (
            <p
              role="alert"
              className="rounded-control border border-danger-line bg-danger-soft px-3.5 py-3 text-label font-medium leading-relaxed text-danger"
            >
              {error}
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-line bg-sunken/70 px-5 py-4">
          <Button
            ref={cancelRef}
            variant="secondary"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={onConfirm}
            disabled={busy}
            data-testid="delete-design-confirm"
          >
            {busy ? <Spinner size={16} /> : <Trash2 size={16} aria-hidden="true" />}
            {busy
              ? "Deleting…"
              : running
                ? "Stop run & delete"
                : "Delete design"}
          </Button>
        </div>
      </div>
    </div>
  );
}

