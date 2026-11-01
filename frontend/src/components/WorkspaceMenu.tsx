import { useRef } from "react";
import { ChevronRight, FilePlus2, FileText, FileUp, Plus, Trash2 } from "lucide-react";
import type { DesignSummary, Project, ProjectSummary } from "../types";
import {
  drawingName,
  plumbingAreasLabel,
  plural,
  summaryStatusLabel,
  summaryStatusTone,
} from "../lib/labels";
import { useMenuFocus } from "../hooks/useMenuFocus";
import { cx, Dot } from "./ui";

export function WorkspaceMenu({
  project,
  projects,
  activeDesignId,
  onSelectDesign,
  onDeleteDesign,
  onNewDesign,
  onUpload,
  onSample,
  onOpenProject,
  onClose,
  busy = false,
}: {
  project: Project;
  projects: ProjectSummary[];
  activeDesignId: string | null;
  onSelectDesign: (id: string) => void;
  onDeleteDesign: (design: DesignSummary) => void;
  onNewDesign: () => void;
  onUpload: (file: File) => void;
  onSample: () => void;
  onOpenProject?: (id: string) => void;
  onClose: () => void;
  busy?: boolean;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const otherProjects = projects.filter(
    (item) => item.project_id !== project.project_id,
  );
  useMenuFocus(true, onClose, panelRef);

  return (
    <div
      ref={panelRef}
      id="workspace-menu"
      role="menu"
      aria-label="Workspace"
      className="fixed left-3 right-3 top-[68px] z-50 max-h-[calc(100dvh-5rem)] overflow-y-auto rounded-overlay border border-line bg-raised shadow-float animate-fade-up sm:absolute sm:left-0 sm:right-auto sm:top-[calc(100%+8px)] sm:max-h-none sm:w-[min(380px,calc(100vw-1.5rem))] sm:overflow-hidden"
      data-testid="workspace-menu"
    >
      <div className="flex items-start gap-3 border-b border-line px-4 py-4">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-card bg-sunken text-muted">
          <FileText size={18} aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-ui font-semibold text-ink">
            {drawingName(project)}
          </div>
          <div className="mt-0.5 text-xs text-muted">
            {plural(project.rooms.length, "room")} ·{" "}
            {plural(project.designs.length, "design")}
          </div>
        </div>
        <button
          type="button"
          role="menuitem"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
          className="inline-flex min-h-11 items-center gap-1.5 rounded-control border border-line-strong lg:min-h-8 bg-surface px-2.5 text-label font-medium text-ink-soft transition hover:bg-sunken hover:text-ink disabled:pointer-events-none disabled:opacity-40"
        >
          <FileUp size={14} aria-hidden="true" /> Upload
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".dxf"
          className="hidden"
          disabled={busy}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onUpload(file);
            event.target.value = "";
            onClose();
          }}
        />
      </div>

      <div className="flex items-center justify-between px-4 pb-1.5 pt-3.5">
        <span className="text-xs font-medium text-muted">Designs</span>
        <button
          type="button"
          role="menuitem"
          disabled={busy}
          onClick={() => {
            onNewDesign();
            onClose();
          }}
          className="inline-flex min-h-11 items-center gap-1 rounded-control px-2 text-label font-semibold text-accent lg:min-h-8 transition hover:bg-accent-soft disabled:pointer-events-none disabled:opacity-40"
          data-testid="new-design"
        >
          <Plus size={14} aria-hidden="true" /> New design
        </button>
      </div>

      <div className="max-h-[300px] space-y-0.5 overflow-y-auto px-2 pb-2">
        {!project.designs.length && (
          <div className="mx-2 mt-1 rounded-card border border-dashed border-line-strong px-4 py-5 text-center">
            <FilePlus2 size={20} className="mx-auto text-muted" aria-hidden="true" />
            <div className="mt-2 text-label font-semibold text-ink">
              No designs yet
            </div>
            <p className="mt-0.5 text-xs leading-relaxed text-muted">
              Start from a room above to create the first option.
            </p>
          </div>
        )}
        {project.designs.map((design) => {
          const active = design.design_id === activeDesignId;
          return (
            <div
              key={design.design_id}
              className={cx(
                "flex min-h-12 items-center gap-0.5 rounded-card pr-1 transition",
                active ? "bg-accent-soft" : "hover:bg-sunken",
              )}
            >
              <button
                type="button"
                role="menuitem"
                disabled={busy}
                aria-current={active ? "true" : undefined}
                onClick={() => {
                  onSelectDesign(design.design_id);
                  onClose();
                }}
                className={cx(
                  "flex min-h-12 min-w-0 flex-1 items-center gap-3 rounded-card px-3 py-2.5 text-left transition disabled:pointer-events-none disabled:opacity-40",
                  active ? "text-ink" : "text-ink-soft",
                )}
                data-testid={`design-${design.design_id}`}
              >
                <Dot tone={summaryStatusTone(design.status)} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-ui font-medium">
                    {plumbingAreasLabel(
                      project,
                      design.room_ids || (design.room_id ? [design.room_id] : []),
                    )}
                  </span>
                  <span className="mt-0.5 block truncate text-xs text-muted">
                    {design.layout_id || design.design_id} ·{" "}
                    {summaryStatusLabel(design.status)}
                  </span>
                </span>
                <ChevronRight
                  size={16}
                  className={cx(
                    "shrink-0",
                    active ? "text-accent" : "text-muted",
                  )}
                  aria-hidden="true"
                />
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  onDeleteDesign(design);
                  onClose();
                }}
                aria-label={`Delete ${plumbingAreasLabel(
                  project,
                  design.room_ids || (design.room_id ? [design.room_id] : []),
                )} design ${design.design_id}`}
                title="Delete design"
                className="grid h-11 w-11 shrink-0 place-items-center rounded-control text-muted transition hover:bg-danger-soft hover:text-danger disabled:pointer-events-none disabled:opacity-40"
                data-testid={`delete-design-${design.design_id}`}
              >
                <Trash2 size={16} aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>

      {otherProjects.length > 0 && (
        <div className="border-t border-line px-2 pb-2 pt-2">
          <div className="px-3 pb-1 text-xs font-medium text-muted">
            Other drawings
          </div>
          {otherProjects.slice(0, 4).map((item) => (
            <button
              key={item.project_id}
              type="button"
              role="menuitem"
              disabled={busy}
              onClick={() => {
                onOpenProject?.(item.project_id);
                onClose();
              }}
              className="flex min-h-12 w-full items-center gap-3 rounded-card px-3 py-2.5 text-left transition hover:bg-sunken disabled:pointer-events-none disabled:opacity-40"
            >
              <FileText size={16} className="shrink-0 text-muted" aria-hidden="true" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-ui font-medium text-ink-soft">
                  {item.name.replace(/\.dxf$/i, "").replaceAll("_", " ")}
                </span>
                <span className="mt-0.5 block text-xs text-muted">
                  {plural(item.rooms, "room")} · {plural(item.designs, "design")}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between border-t border-line bg-sunken px-4 py-3">
        <span className="text-xs text-muted">Need a starting point?</span>
        <button
          type="button"
          role="menuitem"
          disabled={busy}
          onClick={() => {
            onSample();
            onClose();
          }}
          className="inline-flex min-h-11 items-center rounded-control px-2 text-label font-semibold text-ink-soft lg:min-h-8 transition hover:bg-raised hover:text-accent disabled:pointer-events-none disabled:opacity-40"
        >
          Open sample
        </button>
      </div>
    </div>
  );
}




