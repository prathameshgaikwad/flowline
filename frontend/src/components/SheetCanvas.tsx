import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Scan,
  SlidersHorizontal,
  TriangleAlert,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import type { SheetSpec } from "../types";
import { useClickAway } from "../hooks/useClickAway";
import { usePlanViewport } from "../hooks/usePlanViewport";
import { usePopoverFocus } from "../hooks/usePopoverFocus";
import {
  Button,
  cx,
  Field,
  IconButton,
  inputClass,
  selectClass,
  Skeleton,
} from "./ui";

const PRESETS = [
  ["A4", "A4"],
  ["A3", "A3"],
  ["A2", "A2"],
  ["A1", "A1"],
  ["A0", "A0"],
  ["ANSI_A", "ANSI A"],
  ["ANSI_B", "ANSI B"],
  ["ANSI_C", "ANSI C"],
  ["ANSI_D", "ANSI D"],
  ["ANSI_E", "ANSI E"],
  ["CUSTOM", "Custom"],
];

export type SheetUpdate = {
  preset?: string;
  width_mm?: number;
  height_mm?: number;
  orientation?: string;
  scale?: number;
};

export function SheetCanvas({
  svg,
  loading,
  error,
  page,
  pages,
  sheet,
  updating,
  onPage,
  onBack,
  onUpdateSheet,
  onRetry,
}: {
  svg: string | null;
  loading: boolean;
  error: string | null;
  page: number;
  pages: number;
  sheet: SheetSpec | null;
  updating: boolean;
  onPage: (page: number) => void;
  onBack: () => void;
  onUpdateSheet: (body: SheetUpdate) => void;
  onRetry: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);
  const settingsPanelRef = useRef<HTMLDivElement>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [preset, setPreset] = useState(sheet?.preset || "A3");
  const [orientation, setOrientation] = useState(sheet?.orientation || "landscape");
  const [width, setWidth] = useState(String(sheet?.width_mm || 420));
  const [height, setHeight] = useState(String(sheet?.height_mm || 297));
  const [dimensionError, setDimensionError] = useState<string | null>(null);
  const viewport = usePlanViewport(
    containerRef,
    `${page}:${sheet?.preset}:${sheet?.width_mm}:${sheet?.height_mm}:${svg?.length || 0}`,
  );

  useClickAway(settingsRef, () => setSettingsOpen(false), settingsOpen);
  usePopoverFocus(
    settingsOpen,
    () => setSettingsOpen(false),
    settingsPanelRef,
  );

  useEffect(() => {
    if (!sheet) return;
    setPreset(sheet.preset);
    setOrientation(sheet.orientation);
    setWidth(String(sheet.width_mm));
    setHeight(String(sheet.height_mm));
  }, [sheet]);

  useEffect(() => {
    if (!settingsOpen) setDimensionError(null);
  }, [settingsOpen]);

  const apply = () => {
    const body: SheetUpdate = {
      preset,
      orientation,
    };
    if (preset === "CUSTOM") {
      const parsedWidth = Number(width);
      const parsedHeight = Number(height);
      if (
        !Number.isFinite(parsedWidth) ||
        !Number.isFinite(parsedHeight) ||
        parsedWidth < 100 ||
        parsedHeight < 100 ||
        parsedWidth > 5000 ||
        parsedHeight > 5000
      ) {
        setDimensionError("Enter values between 100 and 5000 mm.");
        return;
      }
      setDimensionError(null);
      body.width_mm = parsedWidth;
      body.height_mm = parsedHeight;
    }
    onUpdateSheet(body);
    setSettingsOpen(false);
  };

  return (
    <section
      className="relative flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-board"
      data-testid="sheet-canvas"
      aria-label={`Construction sheet preview, page ${page} of ${pages}`}
    >
      <p className="status-live" aria-live="polite">
        {loading
          ? "Preparing construction sheet preview."
          : error
            ? `Sheet preview failed. ${error}`
            : `Construction sheet page ${page} of ${pages} ready.`}
      </p>
      <div
        ref={containerRef}
        className={cx(
          "absolute inset-0 touch-none select-none overflow-hidden",
          viewport.scale > 1
            ? "cursor-grab active:cursor-grabbing"
            : "cursor-default",
        )}
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
        aria-label="Construction sheet preview. Use plus, minus, and zero keys to zoom and fit."
      >
        <div
          className="plan-svg sheet-svg plan-surface absolute inset-0"
          style={{
            transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.scale})`,
          }}
          dangerouslySetInnerHTML={{ __html: svg || "" }}
        />
        {loading && (
          <div className="absolute inset-0 grid place-items-center bg-board/85">
            <div className="w-[min(78%,740px)] rounded-card bg-raised p-5 shadow-float">
              <Skeleton className="mx-auto aspect-[1.414/1] w-full rounded-sm" />
              <div className="mt-4 flex items-center gap-2 text-label font-medium text-muted">
                <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
                Preparing sheet preview…
              </div>
            </div>
          </div>
        )}
        {error && !loading && (
          <div className="absolute inset-0 grid place-items-center p-6">
            <div className="max-w-md rounded-overlay border border-line bg-raised px-5 py-5 text-center shadow-float">
              <span className="mx-auto grid h-10 w-10 place-items-center rounded-full bg-danger-soft text-danger">
                <TriangleAlert size={18} aria-hidden="true" />
              </span>
              <div className="mt-3 text-ui font-semibold text-ink">
                Could not render the sheet
              </div>
              <p className="mt-1 text-label leading-relaxed text-muted">{error}</p>
              <Button variant="secondary" className="mt-4" onClick={onRetry}>
                Try again
              </Button>
            </div>
          </div>
        )}
      </div>

      <div className="pointer-events-none absolute inset-0 z-10">
        <div className="pointer-events-auto absolute left-3 top-3 flex max-w-[calc(100%-1.5rem)] items-center gap-2">
          <button
            type="button"
            onClick={onBack}
            data-testid="sheet-back"
            className="flex min-h-11 items-center gap-1.5 rounded-card border border-line bg-raised/95 px-3 text-label font-medium text-ink-soft shadow-card backdrop-blur-sm transition hover:bg-raised lg:min-h-9"
          >
            <ArrowLeft size={15} aria-hidden="true" /> Back to plan
          </button>
          {pages > 1 && (
            <div className="flex min-h-11 items-center gap-0.5 rounded-card border border-line bg-raised/95 px-1 shadow-card backdrop-blur-sm lg:min-h-9">
              <button
                type="button"
                onClick={() => onPage(page - 1)}
                disabled={page <= 1}
                className="grid h-9 w-9 place-items-center rounded-control text-muted transition hover:bg-sunken disabled:opacity-30"
                aria-label="Previous sheet"
              >
                <ChevronLeft size={17} aria-hidden="true" />
              </button>
              <span className="px-1 text-label font-medium text-ink-soft tabular-nums">
                {page} / {pages}
              </span>
              <button
                type="button"
                onClick={() => onPage(page + 1)}
                disabled={page >= pages}
                className="grid h-9 w-9 place-items-center rounded-control text-muted transition hover:bg-sunken disabled:opacity-30"
                aria-label="Next sheet"
              >
                <ChevronRight size={17} aria-hidden="true" />
              </button>
            </div>
          )}
        </div>

        <div className="pointer-events-auto absolute right-3 top-3" ref={settingsRef}>
          <button
            type="button"
            onClick={() => setSettingsOpen((open) => !open)}
            aria-expanded={settingsOpen}
            aria-haspopup="dialog"
            aria-controls="sheet-settings-panel"
            className={cx(
              "flex min-h-11 items-center gap-1.5 rounded-card border border-line bg-raised/95 px-3 text-label font-medium text-ink-soft shadow-card backdrop-blur-sm transition hover:bg-raised lg:min-h-9",
              settingsOpen && "bg-raised text-ink",
            )}
            data-testid="sheet-settings-button"
          >
            <SlidersHorizontal size={15} aria-hidden="true" /> Sheet
          </button>
          {settingsOpen && (
            <div
              ref={settingsPanelRef}
              id="sheet-settings-panel"
              role="dialog"
              aria-label="Sheet setup"
              className="absolute right-0 top-[calc(100%+8px)] w-[min(320px,calc(100vw-1.5rem))] rounded-overlay border border-line bg-raised p-4 shadow-float animate-fade-up"
            >
              <div className="text-ui font-semibold text-ink">Sheet setup</div>
              <p className="mt-0.5 text-xs leading-relaxed text-muted">
                The plan scale is fitted automatically.
              </p>
              <div className="mt-3 space-y-3">
                <Field label="Size" htmlFor="sheet-preset">
                  <select
                    id="sheet-preset"
                    value={preset}
                    onChange={(event) => setPreset(event.target.value)}
                    className={selectClass}
                    data-testid="sheet-preset"
                  >
                    {PRESETS.map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </Field>
                {preset === "CUSTOM" && (
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="Width (mm)" htmlFor="sheet-width">
                      <input
                        id="sheet-width"
                        inputMode="numeric"
                        value={width}
                        onChange={(event) => setWidth(event.target.value)}
                        className={inputClass}
                      />
                    </Field>
                    <Field label="Height (mm)" htmlFor="sheet-height">
                      <input
                        id="sheet-height"
                        inputMode="numeric"
                        value={height}
                        onChange={(event) => setHeight(event.target.value)}
                        className={inputClass}
                      />
                    </Field>
                  </div>
                )}
                {dimensionError && (
                  <p role="alert" className="text-xs font-medium text-danger">
                    {dimensionError}
                  </p>
                )}
                <Field label="Orientation" htmlFor="sheet-orientation">
                  <select
                    id="sheet-orientation"
                    value={orientation}
                    onChange={(event) => setOrientation(event.target.value)}
                    className={selectClass}
                  >
                    <option value="landscape">Landscape</option>
                    <option value="portrait">Portrait</option>
                  </select>
                </Field>
                <Button
                  className="w-full"
                  onClick={apply}
                  disabled={updating}
                  data-testid="sheet-apply"
                >
                  {updating ? "Rebuilding…" : "Apply & rebuild"}
                </Button>
              </div>
            </div>
          )}
        </div>

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
          >
            <Scan size={16} aria-hidden="true" /> Fit
          </button>
        </div>
      </div>
    </section>
  );
}
