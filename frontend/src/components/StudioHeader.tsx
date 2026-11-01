import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, Download, PanelRight, Settings2, ShieldCheck } from "lucide-react";
import type { DesignState, DesignSummary, Profile, Project, ProjectSummary } from "../types";
import {
  compactProfileName,
  displayCounts,
  drawingName,
  friendlyProfileName,
  plumbingAreasLabel,
  selectedLayout,
} from "../lib/labels";
import { useClickAway } from "../hooks/useClickAway";
import { Logo } from "./Logo";
import { SettingsMenu } from "./SettingsMenu";
import { StatusPill } from "./StatusPill";
import { WorkspaceMenu } from "./WorkspaceMenu";
import { Button, cx, IconButton } from "./ui";

export function StudioHeader({
  project,
  projects,
  design,
  profiles,
  selectedProfile,
  onProfile,
  onApprove,
  canApprove,
  busy,
  provider,
  model,
  onSelectDesign,
  onDeleteDesign,
  onOpenHome,
  onNewDesign,
  onUpload,
  onSample,
  onOpenProject,
  onOpenDetails,
}: {
  project: Project;
  projects: ProjectSummary[];
  design: DesignState | null;
  profiles: Profile[];
  selectedProfile: string;
  onProfile: (profileId: string) => void;
  onApprove: () => void;
  canApprove: boolean;
  busy: boolean;
  provider?: string;
  model?: string;
  onSelectDesign: (id: string) => void;
  onDeleteDesign: (design: DesignSummary) => void;
  onOpenHome: () => void;
  onNewDesign: () => void;
  onUpload: (file: File) => void;
  onSample: () => void;
  onOpenProject?: (id: string) => void;
  onOpenDetails: () => void;
}) {
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);

  const closeWorkspace = useCallback(() => setWorkspaceOpen(false), []);
  const closeSettings = useCallback(() => setSettingsOpen(false), []);

  useClickAway(workspaceRef, closeWorkspace, workspaceOpen);
  useClickAway(settingsRef, closeSettings, settingsOpen);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setWorkspaceOpen(false);
        setSettingsOpen(false);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  const candidate = selectedLayout(design);
  const display = displayCounts(design);
  const detailsCount = display.ERROR + display.WARNING;
  const room = plumbingAreasLabel(
    project,
    design?.room_ids || (design?.room_id ? [design.room_id] : []),
  );
  const profile = profiles.find((item) => item.id === selectedProfile);
  const subtitle = design
    ? `${candidate?.pattern || design.design?.layout_id || "Draft"} · ${
        design.design ? `${design.design.fixtures.length} fixtures` : "In progress"
      }`
    : "Choose plumbing areas and fixtures";

  return (
    <header
      className="relative z-40 flex h-[60px] shrink-0 items-center gap-2 border-b border-line bg-surface px-3 sm:px-4"
      data-testid="topbar"
    >
      <button
        type="button"
        onClick={onOpenHome}
        aria-label="Go to Flowline home"
        data-testid="home-logo"
        className="flex min-h-11 shrink-0 items-center gap-2 rounded-control px-1.5 py-1.5 transition hover:bg-sunken"
      >
        <Logo size={30} />
        <span className="hidden text-ui font-semibold tracking-[-0.01em] text-ink xl:inline">
          Flowline
        </span>
      </button>

      <div className="h-6 w-px shrink-0 bg-line" aria-hidden="true" />

      <div className="relative min-w-0 flex-1" ref={workspaceRef}>
        <button
          type="button"
          onClick={() => {
            setWorkspaceOpen((open) => !open);
            setSettingsOpen(false);
          }}
          aria-expanded={workspaceOpen}
          aria-haspopup="menu"
          aria-controls="workspace-menu"
          aria-label={`Open workspace menu. ${room}, ${drawingName(project)}`}
          className={cx(
            "group flex max-w-full items-center gap-2 rounded-control px-2 py-1.5 text-left transition-[background-color] hover:bg-sunken",
            workspaceOpen && "bg-sunken",
          )}
          data-testid="workspace-trigger"
        >
          <span className="min-w-0">
            <span className="flex items-center gap-1.5">
              <span className="truncate text-ui font-semibold text-ink">
                {room}
              </span>
              <ChevronDown
                size={15}
                className={cx(
                  "shrink-0 text-muted transition-transform",
                  workspaceOpen && "rotate-180",
                )}
                aria-hidden="true"
              />
            </span>
            <span className="block truncate text-xs text-muted">
              {drawingName(project)} · {subtitle}
            </span>
          </span>
        </button>
        {workspaceOpen && (
          <WorkspaceMenu
            project={project}
            projects={projects}
            activeDesignId={design?.design_id || null}
            onSelectDesign={onSelectDesign}
            onDeleteDesign={onDeleteDesign}
            onNewDesign={onNewDesign}
            onUpload={onUpload}
            onSample={onSample}
            onOpenProject={onOpenProject}
            onClose={closeWorkspace}
            busy={busy}
          />
        )}
      </div>

      <div className="ml-auto flex min-w-0 items-center gap-1.5">
        <button
          type="button"
          onClick={() => {
            setSettingsOpen(true);
            setWorkspaceOpen(false);
          }}
          className="hidden max-w-[190px] items-center gap-1.5 rounded-control border border-line bg-sunken px-2.5 py-1.5 text-left text-xs font-medium text-ink-soft transition hover:border-line-strong hover:bg-raised xl:inline-flex"
          aria-label={`Code standard: ${friendlyProfileName(profile?.name) || "not selected"}. Open design settings.`}
        >
          <ShieldCheck size={14} className="shrink-0 text-accent" aria-hidden="true" />
          <span className="truncate">
            {compactProfileName(profile?.name) || "Code standard"}
          </span>
        </button>

        <span className="hidden sm:contents">
          <StatusPill design={design} busy={busy} />
        </span>

        {design && (
          <span className="hidden lg:contents">
            <Button
              variant="secondary"
              onClick={onOpenDetails}
              data-testid="details-button"
            >
              <PanelRight size={16} aria-hidden="true" />
              <span>Details</span>
              {detailsCount > 0 && (
                <span className="grid h-5 min-w-5 place-items-center rounded-full bg-warning-soft px-1 text-xs font-semibold text-warning">
                  {detailsCount}
                </span>
              )}
            </Button>
          </span>
        )}

        {design &&
          (design.approved && design.download_url ? (
            <a
              href={design.download_url}
              className="inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-control border border-transparent bg-accent px-3 text-ui font-semibold text-on-accent shadow-sm transition hover:bg-accent-hover lg:min-h-9"
              aria-label="Download DXF"
              data-testid="approve-button"
            >
              <Download size={16} aria-hidden="true" />
              <span className="hidden sm:inline">Download DXF</span>
            </a>
          ) : (
            <Button
              onClick={onApprove}
              disabled={!canApprove || busy}
              aria-label={canApprove ? "Review and export" : "Generate a design first"}
              data-testid="approve-button"
            >
              <Download size={16} aria-hidden="true" />
              <span className="hidden sm:inline">Review &amp; export</span>
            </Button>
          ))}

        <div className="relative" ref={settingsRef}>
          <IconButton
            label="Design settings"
            onClick={() => {
              setSettingsOpen((open) => !open);
              setWorkspaceOpen(false);
            }}
            aria-expanded={settingsOpen}
            aria-haspopup="dialog"
            aria-controls="settings-menu"
            data-testid="settings-button"
            className={cx(settingsOpen && "bg-sunken text-ink")}
          >
            <Settings2 size={18} aria-hidden="true" />
          </IconButton>
          {settingsOpen && (
            <SettingsMenu
              profiles={profiles}
              selectedProfile={selectedProfile}
              onProfile={onProfile}
              provider={provider}
              model={model}
              onClose={closeSettings}
              busy={busy}
            />
          )}
        </div>
      </div>
    </header>
  );
}


