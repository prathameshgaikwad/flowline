import { useEffect, useRef } from "react";
import {
  ArrowRight,
  FileText,
  FileUp,
  FolderOpen,
  Layers3,
  ShieldCheck,
  Sparkles,
  Trash2,
  Waves,
} from "lucide-react";
import type { DesignState, Project, ProjectSummary } from "../types";
import {
  designStatus,
  drawingName,
  plumbingAreasLabel,
  plural,
} from "../lib/labels";
import { Logo } from "./Logo";
import {
  Badge,
  Button,
  cx,
  EmptyState,
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

function projectName(name: string) {
  const value = name.replace(/\.dxf$/i, "").replaceAll("_", " ");
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function HomePage({
  projects,
  project,
  design,
  busy,
  onResume,
  onOpenProject,
  onDeleteProject,
  onUpload,
  onSample,
}: {
  projects: ProjectSummary[];
  project: Project | null;
  design: DesignState | null;
  busy: boolean;
  onResume: () => void;
  onOpenProject: (id: string) => void;
  onDeleteProject: (project: ProjectSummary) => void;
  onUpload: (file: File) => void;
  onSample: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  const totalRooms = projects.reduce((sum, item) => sum + item.rooms, 0);
  const totalDesigns = projects.reduce((sum, item) => sum + item.designs, 0);
  const activeStatus = design ? designStatus(design, busy) : null;

  useEffect(() => {
    mainRef.current?.focus({ preventScroll: true });
  }, []);

  return (
    <div className="h-full overflow-y-auto bg-canvas" data-testid="home-page">
      <a href="#home-main" className="skip-link">
        Skip to home
      </a>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex min-h-[68px] w-full max-w-[1180px] items-center gap-3 px-4 sm:px-6 lg:px-10">
          <Logo size={32} withWord />
          <Badge tone="neutral">Home</Badge>
          <div className="ml-auto hidden items-center gap-2 text-xs text-muted sm:flex">
            <span className="h-2 w-2 rounded-full bg-success" aria-hidden="true" />
            Local workspace
          </div>
        </div>
      </header>

      <main
        ref={mainRef}
        id="home-main"
        tabIndex={-1}
        className="mx-auto w-full max-w-[1180px] px-4 pb-12 pt-8 focus:outline-none sm:px-6 lg:px-10 lg:pt-12"
      >
        <section
          aria-labelledby="home-title"
          className="grid gap-8 border-b border-line pb-10 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start lg:gap-16"
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-label font-semibold text-accent">
              <Waves size={16} aria-hidden="true" />
              Flowline studio
            </div>
            <h1
              id="home-title"
              className="mt-3 max-w-[680px] text-[clamp(2rem,4vw,2.8rem)] font-semibold leading-[1.06] tracking-[-0.035em] text-ink"
            >
              Your drawings, at a glance.
            </h1>
            <p className="mt-4 max-w-[560px] text-base leading-relaxed text-muted">
              Return to a bathroom design, open another DXF, or start a fresh
              workspace. Geometry, checks, and decisions stay together locally.
            </p>

            <div className="mt-6 flex flex-wrap items-center gap-2">
              {project && (
                <Button onClick={onResume} data-testid="home-resume">
                  Open {drawingName(project)}
                  <ArrowRight size={16} aria-hidden="true" />
                </Button>
              )}
              <Button
                variant={project ? "secondary" : "primary"}
                onClick={() => inputRef.current?.click()}
                disabled={busy}
                data-testid="home-upload-button"
              >
                <FileUp size={16} aria-hidden="true" /> New drawing
              </Button>
              <Button variant="ghost" onClick={onSample} disabled={busy}>
                Open sample
              </Button>
              <input
                ref={inputRef}
                type="file"
                accept=".dxf"
                className="sr-only"
                tabIndex={-1}
                data-testid="home-upload"
                disabled={busy}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) onUpload(file);
                  event.target.value = "";
                }}
              />
            </div>

            {busy && project && (
              <InlineAlert
                tone="accent"
                icon={<Spinner size={16} />}
                className="mt-4 max-w-[560px]"
              >
                The assistant is working on {drawingName(project)}. You can
                return to it from here; other drawings will be available when
                the run finishes.
              </InlineAlert>
            )}
          </div>

          <aside
            aria-labelledby="studio-snapshot"
            className="rounded-card border border-line bg-raised p-5 shadow-card"
          >
            <div className="flex items-center justify-between gap-3">
              <h2
                id="studio-snapshot"
                className="text-ui font-semibold text-ink"
              >
                Studio snapshot
              </h2>
              <Badge tone="accent">Local</Badge>
            </div>
            <dl className="mt-4 grid grid-cols-3 divide-x divide-line">
              <div>
                <dt className="text-xs text-muted">Drawings</dt>
                <dd className="mt-1 text-xl font-semibold text-ink tabular-nums">
                  {projects.length}
                </dd>
              </div>
              <div className="pl-3">
                <dt className="text-xs text-muted">Designs</dt>
                <dd className="mt-1 text-xl font-semibold text-ink tabular-nums">
                  {totalDesigns}
                </dd>
              </div>
              <div className="pl-3">
                <dt className="text-xs text-muted">Rooms</dt>
                <dd className="mt-1 text-xl font-semibold text-ink tabular-nums">
                  {totalRooms}
                </dd>
              </div>
            </dl>

            <div className="mt-5 border-t border-line pt-4">
              <div className="text-xs font-semibold uppercase tracking-[0.08em] text-muted">
                Current workspace
              </div>
              {project ? (
                <>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span className="text-ui font-semibold text-ink">
                      {drawingName(project)}
                    </span>
                    {activeStatus && (
                      <Badge
                        tone={activeStatus.tone}
                        className="ml-auto"
                      >
                        {activeStatus.label}
                      </Badge>
                    )}
                  </div>
                  <div className="mt-1 text-label text-muted">
                    {plumbingAreasLabel(project, design?.room_ids || (design?.room_id ? [design.room_id] : []))} ·{" "}
                    {project.designs.length}{" "}
                    {project.designs.length === 1 ? "design" : "designs"}
                  </div>
                  {design && (
                    <div className="mt-1 text-xs text-muted">
                      {design.final_answer
                        ? "Latest design state saved"
                        : "Ready for a first run"}
                    </div>
                  )}
                </>
              ) : (
                <p className="mt-2 text-label leading-relaxed text-muted">
                  No drawing is open. Upload a DXF or open the sample to begin.
                </p>
              )}
            </div>

            <div className="mt-5 flex items-start gap-2 rounded-card bg-sunken px-3.5 py-3 text-xs leading-relaxed text-muted">
              <ShieldCheck
                size={15}
                className="mt-0.5 shrink-0"
                aria-hidden="true"
              />
              <span>
                Designs and activity are stored as local project files. Nothing
                is sent to a cloud workspace.
              </span>
            </div>
          </aside>
        </section>

        <section className="pt-8" aria-labelledby="drawings-title">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-label font-semibold text-ink">
                <FolderOpen size={16} className="text-muted" aria-hidden="true" />
                <h2 id="drawings-title">Drawings</h2>
              </div>
              <p className="mt-1 text-label text-muted">
                Open a drawing to continue its latest design.
              </p>
            </div>
            <span className="text-xs text-muted">
              {projects.length}{" "}
              {projects.length === 1 ? "local drawing" : "local drawings"}
            </span>
          </div>

          {projects.length ? (
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {projects.map((item) => {
                const current = item.project_id === project?.project_id;
                const disabled = busy && !current;
                return (
                  <div
                    key={item.project_id}
                    className={cx(
                      "group relative flex min-h-[168px] flex-col rounded-card border bg-raised shadow-card transition-[border-color,background-color]",
                      current
                        ? "border-accent/45 ring-1 ring-accent/10"
                        : "border-line hover:border-line-strong hover:bg-surface",
                    )}
                  >
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => {
                        if (current) {
                          onResume();
                        } else {
                          onOpenProject(item.project_id);
                        }
                      }}
                      aria-label={`Open ${projectName(item.name)}${current ? " workspace" : ""}`}
                      title={
                        disabled
                          ? "Wait for the current assistant run to finish."
                          : undefined
                      }
                      className="flex min-h-[168px] w-full flex-col items-start rounded-card p-4 pr-14 text-left disabled:cursor-not-allowed disabled:opacity-45"
                      data-testid={`home-project-${item.project_id}`}
                    >
                      <div className="flex w-full items-start gap-3">
                        <span
                          className={cx(
                            "grid h-10 w-10 shrink-0 place-items-center rounded-card",
                            current
                              ? "bg-accent-soft text-accent"
                              : "bg-sunken text-muted",
                          )}
                        >
                          <FileText size={18} aria-hidden="true" />
                        </span>
                        {current && <Badge tone="accent">Open</Badge>}
                      </div>
                      <div className="mt-4 w-full min-w-0">
                        <div className="truncate text-ui font-semibold text-ink">
                          {projectName(item.name)}
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                          <span>{plural(item.rooms, "room")}</span>
                          <span aria-hidden="true">·</span>
                          <span>{plural(item.designs, "design")}</span>
                          <span aria-hidden="true">·</span>
                          <span>{formatUpdated(item.updated_at)}</span>
                        </div>
                      </div>
                      <div
                        data-testid="home-open-action"
                        className="mt-auto flex items-center gap-1.5 pt-4 text-xs font-medium text-accent transition-opacity md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100"
                      >
                        <Layers3 size={13} aria-hidden="true" />
                        {current ? "Return to workspace" : "Open drawing"}
                        <ArrowRight size={13} aria-hidden="true" />
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => onDeleteProject(item)}
                      aria-label={`Delete drawing ${projectName(item.name)}`}
                      title="Delete drawing"
                      className="absolute right-2 top-2 grid h-11 w-11 place-items-center rounded-control text-muted transition-[opacity,background-color,color] hover:bg-danger-soft hover:text-danger md:pointer-events-none md:opacity-0 md:group-hover:pointer-events-auto md:group-hover:opacity-100 md:group-focus-within:pointer-events-auto md:group-focus-within:opacity-100"
                      data-testid={`home-delete-project-${item.project_id}`}
                    >
                      <Trash2 size={16} aria-hidden="true" />
                    </button>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState
              className="mt-4"
              icon={<FolderOpen size={20} />}
              title="No drawings yet"
              description="Upload a DXF or open the sample apartment to start a bathroom plumbing design."
              action={
                <div className="flex flex-wrap justify-center gap-2">
                  <Button
                    onClick={() => inputRef.current?.click()}
                    disabled={busy}
                  >
                    <FileUp size={16} aria-hidden="true" /> Upload a drawing
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={onSample}
                    disabled={busy}
                  >
                    Open sample apartment
                  </Button>
                </div>
              }
            />
          )}
        </section>

        <footer className="mt-12 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-5 text-xs text-muted">
          <Sparkles size={14} aria-hidden="true" />
          <span>Flowline bathroom plumbing design</span>
          <span aria-hidden="true">·</span>
          <span>Demo rule set, not a compliance certificate.</span>
        </footer>
      </main>
    </div>
  );
}





