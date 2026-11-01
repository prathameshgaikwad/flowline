import { useEffect, useId, useMemo, useRef } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import {
  Crosshair,
  FileText,
  Maximize2,
  Minimize2,
  Ruler,
  Scan,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import type { DesignState, Project } from "../types";
import { usePlanViewport } from "../hooks/usePlanViewport";
import { PlanLegend } from "./PlanLegend";
import {
  cx,
  IconButton,
  SegmentedControl,
} from "./ui";
import type { SegmentOption } from "./ui";

type StackPoint = { x: number; y: number };
type CanvasView = "design" | "source";

export function DesignCanvas({
  project,
  design,
  view,
  onView,
  busy = false,
  selectedRooms,
  onToggleRoom,
  stackPoint,
  pickingStack = false,
  onPickStack,
  onCancelStackPick,
  fullscreen = false,
  onToggleFullscreen,
  sheetReady = false,
  onOpenSheet,
}: {
  project: Project;
  design: DesignState | null;
  view: CanvasView;
  onView: (view: CanvasView) => void;
  busy?: boolean;
  selectedRooms?: string[];
  onToggleRoom?: (roomId: string) => void;
  stackPoint?: StackPoint | null;
  pickingStack?: boolean;
  onPickStack?: (point: StackPoint) => void;
  onCancelStackPick?: () => void;
  fullscreen?: boolean;
  onToggleFullscreen?: () => void;
  sheetReady?: boolean;
  onOpenSheet?: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const helpId = useId();
  const singleRoom = project.rooms.length === 1;
  const source = view === "design" && design?.design ? design.svg : project.svg;
  const svg = useMemo(
    () => bringRoomLabelsToFront(addStackMarker(source, stackPoint)),
    [source, stackPoint],
  );
  const resetKey = `${view}:${design?.design_id || "none"}:${
    design?.design ? "design" : "source"
  }:${fullscreen ? "full" : "work"}`;
  const viewport = usePlanViewport(containerRef, resetKey);

  useEffect(() => {
    if (!containerRef.current) return;
    containerRef.current.querySelectorAll<SVGElement>(".room").forEach((element) => {
      element.classList.toggle(
        "selected",
        Boolean(
          selectedRooms?.includes(element.getAttribute("data-room-id") || ""),
        ),
      );
    });
  }, [svg, selectedRooms, view]);

  const handleClick = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (viewport.consumeDrag()) return;
    if (pickingStack && onPickStack) {
      const point = pointFromEvent(event, containerRef.current);
      if (point) onPickStack(point);
      return;
    }
    if (!onToggleRoom) return;
    const target =
      document.elementFromPoint(event.clientX, event.clientY) ??
      (event.target as Element);
    const room = target.closest("[data-room-id]");
    const roomId = room?.getAttribute("data-room-id");
    if (roomId) onToggleRoom(roomId);
  };

  const viewOptions: SegmentOption<CanvasView | "sheet">[] = [];
  if (design?.design) {
    viewOptions.push(
      { value: "design", label: "Design", testId: "view-design" },
      { value: "source", label: "Source", testId: "view-source" },
    );
  }
  if (sheetReady && onOpenSheet) {
    viewOptions.push({
      value: "sheet",
      label: "Sheet",
      icon: <FileText size={14} aria-hidden="true" />,
      testId: "view-sheet",
    });
  }

  return (
    <section
      className="relative flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-canvas"
      data-testid={fullscreen ? "fullscreen-plan-canvas" : "plan-canvas"}
      aria-label={`${project.name} floor plan`}
    >
      <div
        ref={containerRef}
        className={cx(
          "plan-grid absolute inset-0 touch-none select-none overflow-hidden",
          singleRoom && "single-room-plan",
          pickingStack
            ? "cursor-crosshair"
            : viewport.scale > 1
              ? "cursor-grab active:cursor-grabbing"
              : "cursor-default",
        )}
        onClick={handleClick}
        onDoubleClick={viewport.fit}
        onKeyDown={(event) => {
          if (event.key === "=" || event.key === "+") viewport.zoomIn();
          if (event.key === "-") viewport.zoomOut();
          if (event.key === "0") viewport.fit();
        }}
        onPointerDown={viewport.onPointerDown}
        onPointerMove={viewport.onPointerMove}
        onPointerUp={viewport.onPointerUp}
        onPointerCancel={viewport.onPointerUp}
        tabIndex={0}
        role="application"
        aria-label="Interactive floor plan. Use the zoom controls or arrow keys on the resize handle. Click a room to add or remove it from the design."
        aria-describedby={helpId}
      >
        <p id={helpId} className="status-live">
          Floor plan viewer. Double click to fit. Use plus, minus, and zero keys
          to zoom and fit.
        </p>
        <div
          className="plan-svg plan-surface absolute inset-0"
          style={{
            transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.scale})`,
          }}
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>

      {busy && (
        <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-0.5 overflow-hidden bg-accent-soft">
          <div className="canvas-progress h-full w-1/3 bg-accent/70" />
        </div>
      )}

      <div className="pointer-events-none absolute inset-0 z-10">
        <div className="pointer-events-auto absolute left-3 top-3 flex max-w-[calc(100%-1.5rem)] items-center gap-2">
          {viewOptions.length > 0 ? (
            <SegmentedControl
              label="Plan view"
              compact
              value={view}
              onChange={(value) => {
                if (value === "sheet") {
                  onOpenSheet?.();
                  return;
                }
                onView(value);
              }}
              options={viewOptions}
            />
          ) : (
            <span className="flex min-h-9 items-center gap-1.5 rounded-card border border-line bg-raised/95 px-3 text-label font-medium text-muted shadow-card backdrop-blur-sm">
              <Ruler size={15} className="text-muted" aria-hidden="true" />
              Source plan
            </span>
          )}
        </div>

        {pickingStack && (
          <div className="pointer-events-auto absolute left-1/2 top-16 flex max-w-[calc(100%-1.5rem)] -translate-x-1/2 flex-wrap items-center justify-center gap-x-2 gap-y-1.5 rounded-card border border-accent/20 bg-accent-soft px-3.5 py-2 text-label font-medium text-accent shadow-card sm:top-3">
            <Crosshair size={16} className="shrink-0" aria-hidden="true" />
            <span className="min-w-0">Click the plan to place the drain stack</span>
            <button
              type="button"
              onClick={() => {
                const point = centerPointFromSvg(containerRef.current);
                if (point) onPickStack?.(point);
              }}
              className="min-h-8 rounded-control bg-raised px-2 font-semibold text-accent transition hover:bg-surface"
            >
              Place at plan centre
            </button>
            {onCancelStackPick && (
              <button
                type="button"
                onClick={onCancelStackPick}
                className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-accent/80 transition hover:bg-raised hover:text-accent"
                aria-label="Cancel stack placement"
              >
                <X size={15} aria-hidden="true" />
              </button>
            )}
          </div>
        )}

        <div className="pointer-events-auto absolute bottom-3 left-3 flex items-center gap-0.5 rounded-card border border-line bg-raised/95 p-1 shadow-card backdrop-blur-sm">
          <IconButton
            label="Zoom out"
            onClick={viewport.zoomOut}
            disabled={viewport.scale <= 1}
          >
            <ZoomOut size={18} aria-hidden="true" />
          </IconButton>
          <span className="w-11 text-center text-label font-medium text-muted tabular-nums">
            {viewport.zoomPercent}%
          </span>
          <IconButton
            label="Zoom in"
            onClick={viewport.zoomIn}
            disabled={viewport.scale >= 8}
          >
            <ZoomIn size={18} aria-hidden="true" />
          </IconButton>
          <div className="mx-0.5 h-5 w-px bg-line" aria-hidden="true" />
          <button
            type="button"
            onClick={viewport.fit}
            className="flex min-h-11 items-center gap-1 rounded-control px-2.5 text-label font-medium text-muted transition hover:bg-sunken hover:text-ink lg:min-h-8"
            data-testid="fit-plan"
          >
            <Scan size={16} aria-hidden="true" /> Fit
          </button>
          {onToggleFullscreen && (
            <IconButton
              label={fullscreen ? "Exit full screen" : "Open full plan"}
              onClick={onToggleFullscreen}
              data-testid={fullscreen ? "fullscreen-close" : "fullscreen-button"}
            >
              {fullscreen ? (
                <Minimize2 size={18} aria-hidden="true" />
              ) : (
                <Maximize2 size={18} aria-hidden="true" />
              )}
            </IconButton>
          )}
        </div>

        <div className="pointer-events-auto absolute bottom-16 right-3 sm:bottom-3">
          <PlanLegend design={design} project={project} defaultOpen={fullscreen} />
        </div>
      </div>
    </section>
  );
}

function bringRoomLabelsToFront(svg: string): string {
  const pattern = /<text class="room-label"[\s\S]*?<\/text>/g;
  const labels = svg.match(pattern);
  if (!labels?.length) return svg;
  return svg.replace(pattern, "").replace("</svg>", `${labels.join("")}</svg>`);
}

function addStackMarker(svg: string, point: StackPoint | null | undefined): string {
  if (!point) return svg;
  const match = /viewBox="([^"]+)"/.exec(svg);
  const values = match?.[1].trim().split(/\s+/).map(Number);
  if (!values || values.length !== 4 || values.some(Number.isNaN)) return svg;
  const [, minY, , height] = values;
  const cy = 2 * minY + height - point.y;
  const marker =
    `<g class="draft-stack-marker">` +
    `<circle class="draft-stack" cx="${point.x}" cy="${cy}" r="180"/>` +
    `<text class="draft-stack-label" x="${point.x}" y="${cy - 230}">STACK</text>` +
    `</g>`;
  return svg.replace("</svg>", `${marker}</svg>`);
}

function centerPointFromSvg(container: HTMLDivElement | null): StackPoint | null {
  const svg = container?.querySelector<SVGSVGElement>("svg");
  if (!svg) return null;
  const viewBox = svg.viewBox.baseVal;
  if (!viewBox.width || !viewBox.height) return null;
  const x = viewBox.x + viewBox.width / 2;
  const y = viewBox.y + viewBox.height / 2;
  return { x: Math.round(x / 10) * 10, y: Math.round(y / 10) * 10 };
}

function pointFromEvent(
  event: { clientX: number; clientY: number },
  container: HTMLDivElement | null,
): StackPoint | null {
  const svg = container?.querySelector<SVGSVGElement>("svg");
  if (!svg) return null;
  const rect = svg.getBoundingClientRect();
  const viewBox = svg.viewBox.baseVal;
  if (!rect.width || !rect.height || !viewBox.width || !viewBox.height) return null;
  const scale = Math.min(rect.width / viewBox.width, rect.height / viewBox.height);
  const offsetX = (rect.width - viewBox.width * scale) / 2;
  const offsetY = (rect.height - viewBox.height * scale) / 2;
  const userX = viewBox.x + (event.clientX - rect.left - offsetX) / scale;
  const userY = viewBox.y + (event.clientY - rect.top - offsetY) / scale;
  const y = 2 * viewBox.y + viewBox.height - userY;
  return { x: Math.round(userX / 10) * 10, y: Math.round(y / 10) * 10 };
}
