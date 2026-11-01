import { useState } from "react";
import {
  ArrowRight,
  ChevronDown,
  Crosshair,
  Droplets,
  ShieldCheck,
  ShowerHead,
  Sparkles,
  Toilet,
  TriangleAlert,
  Utensils,
  Waves,
  X,
} from "lucide-react";
import type { Profile, Project } from "../types";
import { RoomSelectionList } from "./RoomSelectionList";
import type { SetupRoomSelection } from "./RoomSelectionList";
import { friendlyProfileName } from "../lib/labels";
import {
  Badge,
  Button,
  cx,
  Field,
  selectClass,
  Spinner,
} from "./ui";

const FIXTURES = [
  { id: "WC", label: "Toilet", icon: Toilet },
  { id: "BASIN", label: "Basin", icon: Droplets },
  { id: "SHOWER", label: "Shower", icon: ShowerHead },
  { id: "FLOOR_DRAIN", label: "Floor drain", icon: Waves },
  { id: "KITCHEN_SINK", label: "Kitchen sink", icon: Utensils },
];

export function NewDesignPanel({
  project,
  profiles,
  selectedProfile,
  selections,
  activeRoomId,
  onToggleRoom,
  onActivateRoom,
  onSelectAll,
  onFixture,
  onStack,
  onProfile,
  onStart,
  busy,
  stackPoint,
  pickingStack,
  onToggleStackPick,
  onClearStack,
}: {
  project: Project;
  profiles: Profile[];
  selectedProfile: string;
  selections: SetupRoomSelection[];
  activeRoomId: string | null;
  onToggleRoom: (roomId: string) => void;
  onActivateRoom: (roomId: string) => void;
  onSelectAll: () => void;
  onFixture: (roomId: string, fixture: string) => void;
  onStack: (roomId: string, stackId: string) => void;
  onProfile: (profileId: string) => void;
  onStart: () => void;
  busy: boolean;
  stackPoint: { x: number; y: number } | null;
  pickingStack: boolean;
  onToggleStackPick: () => void;
  onClearStack: () => void;
}) {
  const [notesOpen, setNotesOpen] = useState(false);
  const profile = profiles.find((item) => item.id === selectedProfile);
  const hasStack = project.stacks.length > 0 || Boolean(stackPoint);
  const fixtureCount = selections.reduce(
    (total, item) => total + item.fixtures.length,
    0,
  );
  const canStart =
    selections.length > 0 &&
    selections.every((item) => item.fixtures.length > 0) &&
    hasStack &&
    !busy;

  const ctaLabel = busy
    ? "Starting design…"
    : !selections.length
      ? "Select plumbing areas"
      : selections.some((item) => !item.fixtures.length)
        ? "Choose fixtures for every area"
        : !hasStack
          ? "Place a drain stack"
          : `Design ${selections.length} ${
              selections.length === 1 ? "area" : "areas"
            }`;

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-surface">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 [scrollbar-gutter:stable] sm:px-5">
        <div className="mx-auto max-w-[560px]">
          <div className="flex items-center gap-2 text-label font-semibold text-accent">
            <Sparkles size={16} aria-hidden="true" />
            New design
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-[-0.025em] text-ink">
            Plan the plumbing
          </h1>
          <p className="mt-1.5 text-ui leading-relaxed text-muted">
            Choose the plumbing areas, fixtures, and drain connections. Flowline
            will design one coordinated floor plan.
          </p>

          {project.warnings.length > 0 && (
            <div className="mt-5">
              <button
                type="button"
                onClick={() => setNotesOpen((open) => !open)}
                aria-expanded={notesOpen}
                className="flex min-h-11 w-full items-center gap-2 rounded-card border border-warning-line bg-warning-soft px-3.5 py-2.5 text-left text-label font-medium text-warning"
              >
                <TriangleAlert size={16} className="shrink-0" aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  {project.warnings.length}{" "}
                  {project.warnings.length === 1
                    ? "drawing note"
                    : "drawing notes"}
                </span>
                <ChevronDown
                  size={16}
                  className={cx("shrink-0 transition-transform", notesOpen && "rotate-180")}
                  aria-hidden="true"
                />
              </button>
              {notesOpen && (
                <ul className="mt-2 space-y-1.5 rounded-card border border-line bg-sunken px-4 py-3 text-label leading-relaxed text-ink-soft">
                  {project.warnings.map((warning) => (
                    <li key={warning} className="flex gap-2">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-warning" />
                      <span>{warning}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <div className="mt-7 space-y-7">
            <section aria-labelledby="room-step">
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-xs font-medium text-accent">01</span>
                <h2 id="room-step" className="text-ui font-semibold text-ink">
                  Plumbing areas
                </h2>
              </div>
              <p className="mt-1 text-label text-muted">
                Detected bathrooms, kitchens, balconies, and utility areas are
                selected automatically. Click the plan or a room below to adjust.
              </p>
              <RoomSelectionList
                project={project}
                selections={selections}
                activeRoomId={activeRoomId}
                onToggle={onToggleRoom}
                onActivate={onActivateRoom}
                onSelectAll={onSelectAll}
              />
            </section>

            <section aria-labelledby="fixture-step">
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-xs font-medium text-accent">02</span>
                <h2 id="fixture-step" className="text-ui font-semibold text-ink">
                  Fixtures by area
                </h2>
              </div>
              <p className="mt-1 text-label text-muted">
                Set each plumbing area independently. A toilet may need only a WC
                and basin, while a larger bathroom can take a shower.
              </p>
              <div className="mt-3 space-y-2.5">
                {selections.map((selection) => {
                  const selectedRoom = project.rooms.find(
                    (item) => item.id === selection.roomId,
                  );
                  return (
                    <div
                      key={selection.roomId}
                      className="rounded-card border border-line bg-raised px-3.5 py-3"
                    >
                      <div className="flex items-center gap-2">
                        <span className="min-w-0 flex-1 truncate text-ui font-semibold text-ink">
                          {selectedRoom?.name || selection.roomId}
                        </span>
                        <span className="text-xs text-muted">
                          {selection.fixtures.length} selected
                        </span>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {FIXTURES.map((fixture) => {
                          const Icon = fixture.icon;
                          const active = selection.fixtures.includes(fixture.id);
                          return (
                            <button
                              key={fixture.id}
                              type="button"
                              onClick={() =>
                                onFixture(selection.roomId, fixture.id)
                              }
                              className={cx(
                                "inline-flex min-h-9 items-center gap-1.5 rounded-control border px-2.5 text-xs font-medium transition-[border-color,background-color,color]",
                                active
                                  ? "border-accent/40 bg-accent-soft text-accent"
                                  : "border-line bg-surface text-muted hover:border-line-strong hover:bg-sunken hover:text-ink",
                              )}
                              data-testid={`fixture-${selection.roomId}-${fixture.id.toLowerCase()}`}
                              aria-pressed={active}
                            >
                              <Icon size={14} aria-hidden="true" />
                              {fixture.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
                {!selections.length && (
                  <p className="rounded-card border border-dashed border-line-strong bg-sunken px-3.5 py-4 text-label text-muted">
                    Select at least one plumbing area above to assign fixtures.
                  </p>
                )}
              </div>
            </section>

            <section aria-labelledby="stack-step">
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-xs font-medium text-accent">03</span>
                <h2 id="stack-step" className="text-ui font-semibold text-ink">
                  Drain stack
                </h2>
              </div>

              {project.stacks.length > 0 ? (
                <div className="mt-3 space-y-2">
                  <div className="flex items-center gap-2 text-label text-muted">
                    <Badge tone="success">From drawing</Badge>
                    <span>
                      {project.stacks.length}{" "}
                      {project.stacks.length === 1 ? "stack" : "stacks"} available
                    </span>
                  </div>
                  {selections.map((selection) => {
                    const selectedRoom = project.rooms.find(
                      (item) => item.id === selection.roomId,
                    );
                    return (
                      <div
                        key={selection.roomId}
                        className="flex items-center gap-3 rounded-card border border-line bg-raised px-3.5 py-2.5"
                      >
                        <Droplets
                          size={16}
                          className="shrink-0 text-muted"
                          aria-hidden="true"
                        />
                        <span className="min-w-0 flex-1 truncate text-ui text-ink-soft">
                          {selectedRoom?.name || selection.roomId}
                        </span>
                        <select
                          value={selection.stackId}
                          onChange={(event) =>
                            onStack(selection.roomId, event.target.value)
                          }
                          className="min-h-9 rounded-control border border-line bg-surface px-2 text-label text-ink-soft"
                          aria-label={`Drain stack for ${
                            selectedRoom?.name || selection.roomId
                          }`}
                        >
                          {project.stacks.map((stack) => (
                            <option key={stack.id} value={stack.id}>
                              {stack.id}
                            </option>
                          ))}
                        </select>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="mt-3 space-y-2">
                  <button
                    type="button"
                    onClick={onToggleStackPick}
                    className={cx(
                      "flex min-h-11 w-full items-center justify-center gap-2 rounded-card border px-3 text-label font-medium transition",
                      pickingStack
                        ? "border-accent bg-accent-soft text-accent"
                        : "border-line-strong bg-raised text-ink-soft hover:bg-sunken",
                    )}
                    data-testid="pick-stack"
                  >
                    <Crosshair size={16} aria-hidden="true" />
                    {pickingStack
                      ? "Click the plan to place it"
                      : stackPoint
                        ? "Change stack point"
                        : "Place stack on plan"}
                  </button>
                  {stackPoint && (
                    <div className="flex min-h-11 items-center justify-between gap-2 rounded-card bg-sunken px-3.5 py-2 text-label text-muted">
                      <span className="tabular-nums">
                        Custom stack · {stackPoint.x.toFixed(0)},{" "}
                        {stackPoint.y.toFixed(0)} mm
                      </span>
                      <button
                        type="button"
                        onClick={onClearStack}
                        className="grid h-8 w-8 place-items-center rounded-control transition hover:bg-raised hover:text-ink"
                        aria-label="Clear custom stack position"
                      >
                        <X size={15} aria-hidden="true" />
                      </button>
                    </div>
                  )}
                  {!stackPoint && (
                    <p className="text-label leading-relaxed text-muted">
                      No shaft exists in this drawing. Place a drain stack point
                      on the plan before starting.
                    </p>
                  )}
                </div>
              )}
            </section>

            <section aria-labelledby="standard-step">
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-xs font-medium text-accent">04</span>
                <h2 id="standard-step" className="text-ui font-semibold text-ink">
                  Code standard
                </h2>
              </div>
              <Field label="Validate against" htmlFor="profile-select" className="mt-3">
                <select
                  id="profile-select"
                  value={selectedProfile}
                  onChange={(event) => onProfile(event.target.value)}
                  className={selectClass}
                >
                  {profiles.map((item) => (
                    <option key={item.id} value={item.id}>
                      {friendlyProfileName(item.name)}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="mt-2.5 flex items-start gap-2 text-xs leading-relaxed text-muted">
                <ShieldCheck
                  size={14}
                  className="mt-0.5 shrink-0"
                  aria-hidden="true"
                />
                <span>
                  This demo rule set cites a small subset of requirements. It is
                  not a compliance certificate.
                </span>
              </div>
            </section>
          </div>
        </div>
      </div>

      <div className="shrink-0 border-t border-line bg-surface px-4 py-3 sm:px-5">
        <div className="mx-auto max-w-[560px]">
          {canStart && (
            <div className="mb-2.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
              <span className="font-medium text-ink-soft">
                {selections.length}{" "}
                {selections.length === 1 ? "plumbing area" : "plumbing areas"}
              </span>
              <span aria-hidden="true">�</span>
              <span>{fixtureCount} fixtures</span>
              <span aria-hidden="true">�</span>
              <span className="truncate">
                {friendlyProfileName(profile?.name) || selectedProfile}
              </span>
            </div>
          )}
          <Button
            size="lg"
            onClick={onStart}
            disabled={!canStart}
            className="w-full"
            data-testid="start-design"
          >
            {busy && <Spinner size={16} />}
            {ctaLabel}
            {!busy && <ArrowRight size={16} aria-hidden="true" />}
          </Button>
        </div>
      </div>
    </div>
  );
}
