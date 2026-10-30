import { useEffect, useRef } from "react";
import { Layers3, PencilRuler } from "lucide-react";
import type { DesignState, Project } from "../types";

export function PlanPreview({
  project,
  design,
  view,
  onView,
  selectedRoom,
  onSelectRoom,
  compact = false,
}: {
  project: Project;
  design: DesignState | null;
  view: "design" | "plan";
  onView: (view: "design" | "plan") => void;
  selectedRoom?: string | null;
  onSelectRoom?: (roomId: string) => void;
  compact?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const svg = view === "design" && design?.design ? design.svg : project.svg;

  useEffect(() => {
    if (!ref.current) return;
    ref.current.querySelectorAll<SVGElement>(".room").forEach((element) => {
      element.classList.toggle(
        "selected",
        element.getAttribute("data-room-id") === selectedRoom,
      );
    });
  }, [svg, selectedRoom, view]);

  return (
    <section
      className={`flex min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm ${
        compact ? "h-full" : ""
      }`}
    >
      <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-3 py-2">
        <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-0.5">
          <button
            type="button"
            className={`rounded-md px-2.5 py-1 text-[11px] font-semibold ${
              view === "design"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
            onClick={() => onView("design")}
          >
            Design
          </button>
          <button
            type="button"
            className={`rounded-md px-2.5 py-1 text-[11px] font-semibold ${
              view === "plan"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
            onClick={() => onView("plan")}
          >
            Source
          </button>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-slate-500">
          <span className="flex items-center gap-1">
            <PencilRuler size={11} /> {project.units}
          </span>
          <span className="flex items-center gap-1">
            <Layers3 size={11} /> {project.rooms.length} rooms
          </span>
        </div>
      </div>
      <div
        ref={ref}
        className={`plan-svg min-h-0 flex-1 overflow-auto bg-[radial-gradient(circle_at_1px_1px,#dbe4ef_1px,transparent_1px)] [background-size:18px_18px] p-3 ${
          compact ? "" : "max-h-[58vh]"
        }`}
        onClick={(event) => {
          if (!onSelectRoom) return;
          const target = event.target as HTMLElement;
          const room = target.closest<HTMLElement>("[data-room-id]");
          if (room?.dataset.roomId) onSelectRoom(room.dataset.roomId);
        }}
        dangerouslySetInnerHTML={{ __html: svg }}
      />
      <div className="flex items-center justify-between border-t border-slate-100 px-3 py-1.5 text-[10px] text-slate-500">
        <span>{project.name}</span>
        <span>{design?.design ? `${design.design.layout_id} · ${design.design.pipes.length} pipes` : "No design yet"}</span>
      </div>
    </section>
  );
}
