import { useRef } from "react";
import { FileText, Trash2, TriangleAlert, X } from "lucide-react";
import type { ProjectSummary } from "../types";
import { plural } from "../lib/labels";
import { useModalFocus } from "../hooks/useModalFocus";
import {
  Button,
  IconButton,
  InlineAlert,
  Spinner,
} from "./ui";

function formatUpdated(value: number) {
  const date = new Date(value > 1_000_000_000_000 ? value : value * 1000);
  if (Number.isNaN(date.getTime())) return "Recently updated";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: date.getFullYear() === new Date().getFullYear() ? undefined : "numeric",
  }).format(date);
}

function drawingName(name: string) {
  const value = name.replace(/\.dxf$/i, "").replaceAll("_", " ");
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function DeleteProjectDialog({
  project,
  current,
  running,
  busy,
  error,
  onClose,
  onConfirm,
}: {
  project: ProjectSummary | null;
  current: boolean;
  running: boolean;
  busy: boolean;
  error?: string | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const containerRef = useModalFocus<HTMLDivElement>(
    Boolean(project),
    onClose,
    cancelRef,
  );

  if (!project) return null;

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
        aria-labelledby="delete-project-title"
        aria-describedby="delete-project-description"
        className="my-auto w-full max-w-[520px] overflow-hidden rounded-overlay border border-line bg-raised shadow-2xl animate-fade-up"
        data-testid="delete-project-dialog"
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div className="flex items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-card bg-danger-soft text-danger">
              <Trash2 size={19} aria-hidden="true" />
            </span>
            <div>
              <h2
                id="delete-project-title"
                className="text-lg font-semibold tracking-[-0.02em] text-ink"
              >
                Delete this drawing?
              </h2>
              <p className="mt-0.5 text-label leading-relaxed text-muted">
                This cannot be undone.
              </p>
            </div>
          </div>
          <IconButton
            label="Cancel deleting drawing"
            onClick={onClose}
            disabled={busy}
          >
            <X size={19} aria-hidden="true" />
          </IconButton>
        </div>

        <div className="space-y-4 px-5 py-4">
          <div className="rounded-card border border-line bg-sunken px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-ui font-semibold text-ink">
                {drawingName(project.name)}
              </span>
              <span className="ml-auto text-xs text-muted">
                {formatUpdated(project.updated_at)}
              </span>
            </div>
            <div className="mt-1 text-label text-muted">
              {plural(project.rooms, "room")} ·{" "}
              {plural(project.designs, "design")}
            </div>
          </div>

          <div id="delete-project-description" className="space-y-3">
            <InlineAlert tone="danger" icon={<TriangleAlert size={17} />}>
              The source DXF, all design files, conversations, activity logs,
              previews, sheets, and exports for this drawing will be permanently
              removed.
            </InlineAlert>
            <div className="flex items-start gap-2.5 rounded-card border border-line px-3.5 py-3 text-label leading-relaxed text-muted">
              <FileText
                size={16}
                className="mt-0.5 shrink-0"
                aria-hidden="true"
              />
              <span>
                {current
                  ? "This drawing is currently open. Deleting it will close the workspace."
                  : "Other drawings are not affected."}
              </span>
            </div>
            {running && (
              <p className="rounded-control border border-warning-line bg-warning-soft px-3.5 py-3 text-label leading-relaxed text-warning">
                The assistant is working in this drawing. Deleting it will stop
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
            data-testid="delete-project-confirm"
          >
            {busy ? <Spinner size={16} /> : <Trash2 size={16} aria-hidden="true" />}
            {busy
              ? "Deleting…"
              : running
                ? "Stop run & delete"
                : "Delete drawing"}
          </Button>
        </div>
      </div>
    </div>
  );
}
