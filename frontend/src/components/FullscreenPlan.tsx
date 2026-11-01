import { useRef } from "react";
import { X } from "lucide-react";
import type { DesignState, Project } from "../types";
import {
  drawingName,
  friendlyProfileName,
  plumbingAreasLabel,
} from "../lib/labels";
import { DesignCanvas } from "./DesignCanvas";
import { Logo } from "./Logo";
import { useModalFocus } from "../hooks/useModalFocus";
import { IconButton } from "./ui";

export function FullscreenPlan({
  project,
  design,
  view,
  onView,
  busy,
  selectedRooms,
  onToggleRoom,
  stackPoint,
  pickingStack,
  onPickStack,
  onCancelStackPick,
  onClose,
  onHome,
}: {
  project: Project;
  design: DesignState | null;
  view: "design" | "source";
  onView: (view: "design" | "source") => void;
  busy: boolean;
  selectedRooms?: string[];
  onToggleRoom?: (roomId: string) => void;
  stackPoint?: { x: number; y: number } | null;
  pickingStack?: boolean;
  onPickStack?: (point: { x: number; y: number }) => void;
  onCancelStackPick?: () => void;
  onClose: () => void;
  onHome: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const containerRef = useModalFocus(true, onClose, closeRef);
  const room = plumbingAreasLabel(
    project,
    design?.room_ids || (design?.room_id ? [design.room_id] : []),
  );

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-canvas animate-fade-up"
      data-testid="fullscreen-plan"
      role="dialog"
      aria-modal="true"
      aria-label={`${room} plan, full screen`}
    >
      <div ref={containerRef} className="flex h-full flex-col">
        <header className="flex min-h-[60px] shrink-0 items-center gap-3 border-b border-line bg-surface px-4">
          <button
            type="button"
            onClick={onHome}
            aria-label="Go to Flowline home"
            className="flex min-h-11 items-center gap-2 rounded-control px-1.5 transition hover:bg-sunken"
          >
            <Logo size={28} withWord />
          </button>
          <div className="hidden h-6 w-px bg-line sm:block" aria-hidden="true" />
          <div className="min-w-0">
            <div className="truncate text-ui font-semibold text-ink">
              {room} plan
            </div>
            <div className="truncate text-xs text-muted">
              {drawingName(project)} ·{" "}
              {friendlyProfileName(design?.profile_name) || "Source drawing"}
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <IconButton
              ref={closeRef}
              label="Close full plan"
              onClick={onClose}
            >
              <X size={19} aria-hidden="true" />
            </IconButton>
          </div>
        </header>
        <div className="min-h-0 flex-1">
          <DesignCanvas
            project={project}
            design={design}
            view={view}
            onView={onView}
            busy={busy}
            selectedRooms={selectedRooms}
            onToggleRoom={onToggleRoom}
            stackPoint={stackPoint}
            pickingStack={pickingStack}
            onPickStack={onPickStack}
            onCancelStackPick={onCancelStackPick}
            fullscreen
            onToggleFullscreen={onClose}
          />
        </div>
      </div>
    </div>
  );
}

