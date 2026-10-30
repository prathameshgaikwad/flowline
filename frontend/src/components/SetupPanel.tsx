import {
  ArrowRight,
  DoorOpen,
  Droplets,
  Ruler,
  Sparkles,
  Wand2,
} from "lucide-react";
import type { Profile, Project } from "../types";
import { PlanPreview } from "./PlanPreview";

const FIXTURES = ["WC", "BASIN", "SHOWER", "FLOOR_DRAIN"];

export function SetupPanel({
  project,
  profiles,
  selectedProfile,
  selectedRoom,
  fixtures,
  shaftId,
  onRoom,
  onFixture,
  onShaft,
  onStart,
  busy,
  planView,
  onPlanView,
}: {
  project: Project;
  profiles: Profile[];
  selectedProfile: string;
  selectedRoom: string | null;
  fixtures: string[];
  shaftId: string;
  onRoom: (roomId: string) => void;
  onFixture: (fixture: string) => void;
  onShaft: (shaftId: string) => void;
  onStart: () => void;
  busy: boolean;
  planView: "design" | "plan";
  onPlanView: (view: "design" | "plan") => void;
}) {
  const room = project.rooms.find((item) => item.id === selectedRoom);
  const profile = profiles.find((item) => item.id === selectedProfile);
  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-y-auto p-5 xl:grid-cols-[minmax(0,1fr)_390px]">
      <div className="min-h-[420px]">
        <PlanPreview
          project={project}
          design={null}
          view={planView}
          onView={onPlanView}
          selectedRoom={selectedRoom}
          onSelectRoom={onRoom}
          compact
        />
      </div>
      <div className="flex flex-col gap-4">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.16em] text-blue-600">
            <Wand2 size={13} /> New design
          </div>
          <h2 className="mt-1 text-lg font-bold tracking-tight text-slate-900">
            Set up the wet area
          </h2>
          <p className="mt-1 text-xs leading-relaxed text-slate-500">
            Pick a room, stack and fixture set. The agent will inspect the drawing, compare
            layouts, route drainage, validate, and explain every decision.
          </p>

          <div className="mt-5">
            <div className="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">
              <DoorOpen size={12} /> Room
            </div>
            <div className="space-y-1.5">
              {project.rooms.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onRoom(item.id)}
                  className={`flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left transition ${
                    item.id === selectedRoom
                      ? "border-blue-500 bg-blue-50"
                      : "border-slate-200 hover:border-blue-300 hover:bg-slate-50"
                  }`}
                  data-testid={`setup-room-${item.id}`}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-xs font-semibold text-slate-800">
                      {item.name || item.id}
                    </span>
                    <span className="mt-0.5 block text-[10px] text-slate-500">
                      {item.width_mm.toFixed(0)} × {item.height_mm.toFixed(0)} mm
                    </span>
                  </span>
                  <span className="rounded-full bg-white px-2 py-1 text-[10px] font-bold text-blue-700">
                    {item.area_m2.toFixed(2)} m²
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="mt-5">
            <div className="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">
              <Droplets size={12} /> Stack / shaft
            </div>
            <select
              value={shaftId}
              onChange={(event) => onShaft(event.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 outline-none focus:border-blue-400"
            >
              {!project.shafts.length && <option value="">No shaft detected</option>}
              {project.shafts.map((shaft) => (
                <option key={shaft.id} value={shaft.id}>
                  {shaft.id} · {shaft.width_mm} × {shaft.depth_mm} mm
                </option>
              ))}
            </select>
          </div>

          <div className="mt-5">
            <div className="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">
              <Ruler size={12} /> Fixtures
            </div>
            <div className="flex flex-wrap gap-1.5">
              {FIXTURES.map((fixture) => (
                <button
                  key={fixture}
                  type="button"
                  onClick={() => onFixture(fixture)}
                  className={`rounded-full border px-3 py-1.5 text-[11px] font-semibold transition ${
                    fixtures.includes(fixture)
                      ? "border-blue-500 bg-blue-50 text-blue-700"
                      : "border-slate-200 bg-white text-slate-500 hover:border-slate-300"
                  }`}
                >
                  {fixture === "FLOOR_DRAIN" ? "Floor drain" : fixture}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-5 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5">
            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">
              <Sparkles size={12} /> Standard
            </div>
            <div className="mt-1 text-xs font-semibold text-slate-800">
              {profile?.name || selectedProfile}
            </div>
            <div className="mt-0.5 text-[10px] leading-relaxed text-slate-500">
              {profile?.status === "POC"
                ? "POC rule pack. Cited guidance, not a compliance certificate."
                : "Cited rule pack."}
            </div>
          </div>

          <button
            type="button"
            onClick={onStart}
            disabled={!room || !fixtures.length || busy}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-bold text-white shadow-sm transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-300"
            data-testid="start-design"
          >
            Start design <ArrowRight size={14} />
          </button>
        </section>
      </div>
    </div>
  );
}
