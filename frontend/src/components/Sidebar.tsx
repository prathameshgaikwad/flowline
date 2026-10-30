import {
  Building2,
  FileUp,
  LayoutList,
  Plus,
  Sparkles,
} from "lucide-react";
import type { DesignSummary, Project } from "../types";

const statusDot: Record<string, string> = {
  approved: "bg-emerald-400",
  validated: "bg-emerald-400",
  drafted: "bg-blue-400",
  needs_fix: "bg-red-400",
  stale: "bg-amber-400",
  setup: "bg-slate-500",
  missing: "bg-slate-600",
};

export function Sidebar({
  project,
  activeDesignId,
  onSelectDesign,
  onNewDesign,
  onUpload,
  onSample,
  provider,
  model,
}: {
  project: Project | null;
  activeDesignId: string | null;
  onSelectDesign: (id: string) => void;
  onNewDesign: () => void;
  onUpload: (file: File) => void;
  onSample: () => void;
  provider?: string;
  model?: string;
}) {
  const designs: DesignSummary[] = project?.designs || [];
  return (
    <aside className="flex w-[268px] shrink-0 flex-col bg-slate-950 text-slate-300">
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-blue-600 to-cyan-400 text-sm font-black text-white shadow-lg shadow-blue-900/40">
          F
        </div>
        <div>
          <div className="text-sm font-bold tracking-tight text-white">Flowline</div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
            Agentic MEP
          </div>
        </div>
      </div>

      <div className="px-3">
        <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.14em] text-slate-500">
            <Building2 size={12} /> Workspace
          </div>
          <div className="mt-1 truncate text-sm font-semibold text-white">
            {project?.name?.replace(".dxf", "") || "No drawing"}
          </div>
          <div className="mt-0.5 text-[11px] text-slate-500">
            {project
              ? `${project.rooms.length} rooms · ${project.designs.length} ${
                  project.designs.length === 1 ? "design" : "designs"
                }`
              : "Upload a DXF to begin"}
          </div>
          <div className="mt-3 flex gap-2">
            <label className="flex flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-lg bg-blue-600 px-2 py-1.5 text-[11px] font-semibold text-white transition hover:bg-blue-500">
              <FileUp size={12} /> Upload
              <input
                type="file"
                accept=".dxf"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) onUpload(file);
                  event.target.value = "";
                }}
              />
            </label>
            <button
              type="button"
              onClick={onSample}
              className="rounded-lg border border-white/10 px-2.5 py-1.5 text-[11px] font-semibold text-slate-300 transition hover:border-white/20 hover:text-white"
            >
              Sample
            </button>
          </div>
        </div>
      </div>

      <div className="mt-5 flex items-center justify-between px-5">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.14em] text-slate-500">
          <LayoutList size={12} /> Designs
        </div>
        <button
          type="button"
          onClick={onNewDesign}
          className="flex items-center gap-1 text-[11px] font-semibold text-blue-400 hover:text-blue-300"
        >
          <Plus size={12} /> New
        </button>
      </div>

      <div className="mt-2 flex-1 space-y-1 overflow-y-auto px-3 pb-4">
        {!designs.length && (
          <div className="rounded-lg border border-dashed border-white/10 px-3 py-4 text-[11px] text-slate-500">
            No designs yet. Select a room and start one.
          </div>
        )}
        {designs.map((design) => (
          <button
            key={design.design_id}
            type="button"
            onClick={() => onSelectDesign(design.design_id)}
            className={`flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left transition ${
              design.design_id === activeDesignId
                ? "bg-white/10 text-white"
                : "text-slate-400 hover:bg-white/[0.05] hover:text-slate-200"
            }`}
            data-testid={`design-${design.design_id}`}
          >
            <span
              className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                statusDot[design.status] || "bg-slate-500"
              }`}
            />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-semibold">
                {design.room_id || "Room"}
              </span>
              <span className="block truncate text-[10px] capitalize text-slate-500">
                {design.layout_id || "unplanned"} · {design.status.replace("_", " ")}
              </span>
            </span>
          </button>
        ))}
      </div>

      <div className="border-t border-white/10 px-5 py-4">
        <div className="flex items-center gap-2 text-[10px] text-slate-500">
          <Sparkles size={12} className="text-blue-400" />
          <span className="truncate">
            {provider ? `${provider} · ${model}` : "Provider not checked"}
          </span>
        </div>
        <p className="mt-2 text-[10px] leading-relaxed text-slate-600">
          The model coordinates. Geometry, sizes, slopes and rule checks are deterministic.
        </p>
      </div>
    </aside>
  );
}
