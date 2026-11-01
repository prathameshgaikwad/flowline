import { Check, ChevronDown, Layers3 } from "lucide-react";
import type { Project } from "../types";
import { cx } from "./ui";
import { fixtureName, plumbingRoleLabel, plural } from "../lib/labels";

export type SetupRoomSelection = {
  roomId: string;
  fixtures: string[];
  stackId: string;
};

const FIXTURE_ORDER = [
  "WC",
  "BASIN",
  "SHOWER",
  "FLOOR_DRAIN",
  "KITCHEN_SINK",
];

export function RoomSelectionList({
  project,
  selections,
  activeRoomId,
  onToggle,
  onActivate,
  onSelectAll,
}: {
  project: Project;
  selections: SetupRoomSelection[];
  activeRoomId: string | null;
  onToggle: (roomId: string) => void;
  onActivate: (roomId: string) => void;
  onSelectAll: () => void;
}) {
  const selectedIds = new Set(selections.map((item) => item.roomId));
  const plumbingRooms = project.rooms.filter(
    (room) => room.plumbing_role !== "none",
  );
  const otherRooms = project.rooms.filter(
    (room) => room.plumbing_role === "none",
  );
  const selectedPlumbing = plumbingRooms.filter((room) =>
    selectedIds.has(room.id),
  ).length;

  const renderRoom = (roomId: string) => {
    const room = project.rooms.find((item) => item.id === roomId);
    if (!room) return null;
    const selection = selections.find((item) => item.roomId === roomId);
    const selected = Boolean(selection);
    const active = activeRoomId === roomId;
    const stack = project.stacks.find((item) => item.id === selection?.stackId);
    const detectedCounts = (room.fixtures || []).reduce<Record<string, number>>(
      (counts, fixture) => {
        counts[fixture.type] = (counts[fixture.type] || 0) + 1;
        return counts;
      },
      {},
    );
    return (
      <div
        key={room.id}
        className={cx(
          "flex items-stretch rounded-card border transition-[border-color,background-color]",
          selected
            ? active
              ? "border-accent/45 bg-accent-soft/45"
              : "border-line-strong bg-raised"
            : "border-line bg-raised",
        )}
      >
        <button
          type="button"
          onClick={() => {
            if (selected) {
              onActivate(room.id);
            } else {
              onToggle(room.id);
              onActivate(room.id);
            }
          }}
          className="min-w-0 flex-1 px-3.5 py-3 text-left"
          data-testid={`setup-room-${room.id}`}
        >
          <div className="flex items-center gap-2">
            <span className="min-w-0 flex-1 truncate text-ui font-semibold text-ink">
              {room.name || room.id}
            </span>
            <span className="shrink-0 rounded-full bg-sunken px-2 py-0.5 text-[11px] font-medium text-muted">
              {plumbingRoleLabel(room.plumbing_role)}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted">
            <span>{room.area_m2.toFixed(2)} m²</span>
            {selected && selection && (
              <>
                <span aria-hidden="true">·</span>
                <span>{plural(selection.fixtures.length, "fixture")}</span>
                {stack && (
                  <>
                    <span aria-hidden="true">·</span>
                    <span className="inline-flex items-center gap-1">
                      <Layers3 size={11} aria-hidden="true" />
                      {stack.id}
                    </span>
                  </>
                )}
              </>
            )}
          </div>
          {Object.keys(detectedCounts).length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {Object.entries(detectedCounts)
                .sort(
                  (first, second) =>
                    FIXTURE_ORDER.indexOf(first[0]) -
                    FIXTURE_ORDER.indexOf(second[0]),
                )
                .map(([type, count]) => (
                <span
                  key={type}
                  className="inline-flex items-center gap-1 rounded-full border border-line bg-sunken px-1.5 py-0.5 text-[11px] font-medium text-ink-soft"
                  title={`${plural(count, fixtureName(type))} detected in the drawing`}
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full bg-accent"
                    aria-hidden="true"
                  />
                  {fixtureName(type)}
                  {count > 1 ? ` ×${count}` : ""}
                </span>
              ))}
            </div>
          )}
        </button>
        <button
          type="button"
          onClick={() => onToggle(room.id)}
          aria-label={
            selected
              ? `Remove ${room.name || room.id} from the design`
              : `Add ${room.name || room.id} to the design`
          }
          aria-pressed={selected}
          className={cx(
            "grid w-12 shrink-0 place-items-center rounded-r-card border-l transition",
            selected
              ? "border-accent/20 bg-accent text-on-accent"
              : "border-line text-muted hover:bg-sunken hover:text-ink",
          )}
          data-testid={`setup-room-toggle-${room.id}`}
        >
          {selected ? (
            <Check size={16} strokeWidth={2.5} aria-hidden="true" />
          ) : (
            <span className="h-2 w-2 rounded-full bg-current" aria-hidden="true" />
          )}
        </button>
      </div>
    );
  };

  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-muted">
          {selectedPlumbing} of {plumbingRooms.length} plumbing areas selected
        </p>
        <button
          type="button"
          onClick={onSelectAll}
          className="min-h-8 rounded-control px-2 text-label font-semibold text-accent transition hover:bg-accent-soft"
          data-testid="select-all-plumbing"
        >
          Select all plumbing areas
        </button>
      </div>
      {plumbingRooms.length === 0 && (
        <p className="rounded-card border border-warning-line bg-warning-soft px-3 py-2 text-label leading-relaxed text-warning">
          No plumbing rooms were detected. Add a room below or label the wet areas
          in the drawing.
        </p>
      )}
      <div className="space-y-2">
        {plumbingRooms.map((room) => renderRoom(room.id))}
      </div>
      {otherRooms.length > 0 && (
        <details className="group rounded-card border border-line bg-sunken/50">
          <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 px-3 text-label font-medium text-muted [&::-webkit-details-marker]:hidden">
            <ChevronDown
              size={14}
              className="transition-transform group-open:rotate-180"
              aria-hidden="true"
            />
            Add a room that was not detected
          </summary>
          <div className="space-y-2 px-2 pb-2">
            {otherRooms.map((room) => renderRoom(room.id))}
          </div>
        </details>
      )}
    </div>
  );
}
