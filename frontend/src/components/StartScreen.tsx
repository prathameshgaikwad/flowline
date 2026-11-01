import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  FileText,
  FileUp,
  GitCompareArrows,
  RefreshCw,
  ShieldCheck,
  Waves,
} from "lucide-react";
import type { Project, ProjectSummary } from "../types";
import { drawingName, plural } from "../lib/labels";
import { Logo } from "./Logo";
import { Badge, Button, cx } from "./ui";

const steps = [
  {
    number: "01",
    title: "Read the drawing",
    description: "Rooms, walls, stack, and wet areas are mapped from the DXF.",
    icon: FileText,
  },
  {
    number: "02",
    title: "Compare and route",
    description: "Layouts are ranked, then drainage, vent, and water are routed.",
    icon: GitCompareArrows,
  },
  {
    number: "03",
    title: "Check and export",
    description: "Cited checks, fixes, a construction sheet, and an approval gate.",
    icon: ShieldCheck,
  },
];

export function StartScreen({
  project,
  projects,
  blank,
  busy,
  onHome,
  onUpload,
  onSample,
  onUseCurrent,
  onOpenProject,
  onBack,
  onRetry,
}: {
  project: Project | null;
  projects: ProjectSummary[];
  blank: boolean;
  busy: boolean;
  onHome?: () => void;
  onUpload: (file: File) => void;
  onSample: () => void;
  onUseCurrent?: () => void;
  onOpenProject: (id: string) => void;
  onBack?: () => void;
  onRetry: () => void;
}) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const recent = projects.filter(
    (item) => item.project_id !== project?.project_id,
  );

  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
  }, []);

  return (
    <div
      className="h-full overflow-y-auto bg-canvas"
      data-testid={blank ? "new-design-workspace" : "start-screen"}
    >
      <a href="#launcher-main" className="skip-link">
        Skip to start options
      </a>
      <div className="mx-auto flex min-h-full w-full max-w-[1180px] flex-col px-4 py-5 sm:px-6 lg:px-10">
        <header className="flex min-h-11 items-center gap-3">
          {onHome ? (
            <button
              type="button"
              onClick={onHome}
              aria-label="Go to Flowline home"
              className="flex min-h-11 items-center gap-2 rounded-control px-1.5 transition hover:bg-sunken"
            >
              <Logo size={32} withWord />
            </button>
          ) : (
            <Logo size={32} withWord />
          )}
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden sm:contents">
              <Badge tone="neutral">Drafting studio</Badge>
            </span>
            {onBack && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onBack}
                className="whitespace-nowrap"
              >
                <ArrowLeft size={15} aria-hidden="true" /> Back to workspace
              </Button>
            )}
          </div>
        </header>

        <main
          id="launcher-main"
          tabIndex={-1}
          className="grid flex-1 items-start gap-10 pb-10 pt-10 focus:outline-none lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-16 lg:pt-16"
        >
          <section aria-labelledby="launcher-title" className="min-w-0">
            <div className="flex items-center gap-2 text-label font-semibold text-accent">
              <Waves size={16} aria-hidden="true" />
              Floor plumbing design
            </div>
            <h1
              ref={headingRef}
              id="launcher-title"
              tabIndex={-1}
              className="mt-3 max-w-[720px] text-[clamp(2rem,4vw,2.8rem)] font-semibold leading-[1.06] tracking-[-0.035em] text-ink focus:outline-none"
            >
              {blank
                ? "Start a new design."
                : "Turn a floor plan into a reviewed drainage design."}
            </h1>
            <p className="mt-4 max-w-[590px] text-base leading-relaxed text-muted">
              {blank
                ? "Upload another DXF, or continue with the open drawing. Flowline keeps the geometry, checks, and decisions in one workspace."
                : "Flowline reads the plan, compares layout options, routes the plumbing, checks a cited rule set, and prepares an AutoCAD-ready sheet for your review."}
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              <div
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragging(false);
                  if (busy) return;
                  const file = event.dataTransfer.files?.[0];
                  if (file) onUpload(file);
                }}
                className={cx(
                  "rounded-card border border-dashed transition-[border-color,background-color]",
                  dragging
                    ? "border-accent bg-accent-soft"
                    : "border-line-strong bg-surface",
                )}
              >
                <button
                  type="button"
                  onClick={() => inputRef.current?.click()}
                  disabled={busy}
                  className="flex min-h-[174px] w-full flex-col items-start justify-between p-5 text-left disabled:opacity-50"
                >
                  <span className="grid h-11 w-11 place-items-center rounded-full bg-sunken text-accent">
                    <FileUp size={19} aria-hidden="true" />
                  </span>
                  <span className="mt-5 block">
                    <span className="block text-ui font-semibold text-ink">
                      Upload a floor plan
                    </span>
                    <span className="mt-1 block text-label leading-relaxed text-muted">
                      Drop a DXF here, or browse files.
                    </span>
                  </span>
                  <span className="mt-3 inline-flex items-center gap-1 text-label font-semibold text-accent">
                    {busy ? "Working…" : "Choose a DXF"}{" "}
                    <ArrowRight size={14} aria-hidden="true" />
                  </span>
                </button>
                <input
                  ref={inputRef}
                  type="file"
                  accept=".dxf"
                  className="sr-only"
                  tabIndex={-1}
                  data-testid="start-upload"
                  disabled={busy}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) onUpload(file);
                    event.target.value = "";
                  }}
                />
              </div>

              <div className="flex flex-col justify-between rounded-card border border-line bg-surface p-5">
                <div>
                  <span className="text-xs font-semibold uppercase tracking-[0.08em] text-muted">
                    {onUseCurrent && project ? "Open drawing" : "Sample project"}
                  </span>
                  {onUseCurrent && project ? (
                    <>
                      <div className="mt-3 text-ui font-semibold text-ink">
                        {drawingName(project)}
                      </div>
                      <p className="mt-1 text-label leading-relaxed text-muted">
                        {plural(project.rooms.length, "room")} ·{" "}
                        {plural(project.shafts.length, "shaft")} ·{" "}
                        {plural(project.designs.length, "design")}
                      </p>
                    </>
                  ) : (
                    <>
                      <div className="mt-3 text-ui font-semibold text-ink">
                        Apartment sample
                      </div>
                      <p className="mt-1 text-label leading-relaxed text-muted">
                        A three-room drawing with an existing shaft, ready for a
                        first design.
                      </p>
                    </>
                  )}
                </div>
                <div className="mt-5">
                  {onUseCurrent && project ? (
                    <Button
                      onClick={onUseCurrent}
                      disabled={busy}
                      className="w-full"
                      data-testid="blank-use-current"
                    >
                      Use {drawingName(project)}{" "}
                      <ArrowRight size={15} aria-hidden="true" />
                    </Button>
                  ) : (
                    <Button
                      variant="secondary"
                      onClick={onSample}
                      disabled={busy}
                      className="w-full"
                      data-testid="start-sample"
                    >
                      Open sample apartment
                    </Button>
                  )}
                </div>
              </div>
            </div>

            {recent.length > 0 && (
              <section className="mt-8" aria-labelledby="recent-title">
                <div className="flex items-center justify-between gap-3">
                  <h2
                    id="recent-title"
                    className="text-label font-semibold text-ink"
                  >
                    Recent drawings
                  </h2>
                  <span className="text-xs text-muted">
                    {projects.length} local
                  </span>
                </div>
                <div className="mt-2 divide-y divide-line rounded-card border border-line bg-surface">
                  {recent.slice(0, 4).map((item) => (
                    <button
                      key={item.project_id}
                      type="button"
                      disabled={busy}
                      onClick={() => onOpenProject(item.project_id)}
                      className="flex min-h-14 w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-sunken disabled:opacity-50"
                    >
                      <FileText
                        size={17}
                        className="shrink-0 text-muted"
                        aria-hidden="true"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-ui font-medium text-ink">
                          {item.name.replace(/\.dxf$/i, "").replaceAll("_", " ")}
                        </span>
                        <span className="mt-0.5 block text-xs text-muted">
                          {plural(item.rooms, "room")} ·{" "}
                          {plural(item.designs, "design")}
                        </span>
                      </span>
                      <ArrowRight
                        size={15}
                        className="shrink-0 text-muted"
                        aria-hidden="true"
                      />
                    </button>
                  ))}
                </div>
              </section>
            )}

            {!project && (
              <div className="mt-6">
                <button
                  type="button"
                  onClick={onRetry}
                  className="inline-flex min-h-11 items-center gap-2 rounded-control px-2 text-label font-medium text-muted transition hover:text-ink"
                >
                  <RefreshCw size={15} aria-hidden="true" /> Try again
                </button>
              </div>
            )}
          </section>

          <aside
            aria-labelledby="how-it-works"
            className="border-t border-line pt-6 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-1"
          >
            <div className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">
              The workflow
            </div>
            <h2
              id="how-it-works"
              className="mt-2 text-xl font-semibold tracking-[-0.02em] text-ink"
            >
              From source drawing to reviewed sheet.
            </h2>
            <ol className="mt-6 space-y-5">
              {steps.map((step) => {
                const Icon = step.icon;
                return (
                  <li key={step.number} className="flex gap-4">
                    <span className="font-mono text-xs font-medium text-accent">
                      {step.number}
                    </span>
                    <span className="min-w-0 flex-1 border-t border-line pt-3">
                      <span className="flex items-center gap-2 text-ui font-semibold text-ink">
                        <Icon
                          size={16}
                          className="text-muted"
                          aria-hidden="true"
                        />
                        {step.title}
                      </span>
                      <span className="mt-1 block text-label leading-relaxed text-muted">
                        {step.description}
                      </span>
                    </span>
                  </li>
                );
              })}
            </ol>
            <div className="mt-8 rounded-card bg-ink px-4 py-4 text-surface">
              <div className="flex items-center gap-2 text-label font-semibold">
                <ShieldCheck size={16} aria-hidden="true" />
                Engineer approval stays in the loop.
              </div>
              <p className="mt-2 text-xs leading-relaxed text-surface/70">
                Demo rule set, not a compliance certificate. The local authority
                and a licensed engineer govern the issued design.
              </p>
            </div>
          </aside>
        </main>
      </div>
    </div>
  );
}

