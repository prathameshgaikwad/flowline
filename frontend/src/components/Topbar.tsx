import { Download, ShieldCheck } from "lucide-react";
import type { DesignState, Profile, Project } from "../types";

function providerTone(provider?: string) {
  if (provider === "meta" || provider === "opencode") return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (provider === "openrouter") return "bg-sky-50 text-sky-700 border-sky-200";
  if (provider === "fake") return "bg-amber-50 text-amber-700 border-amber-200";
  return "bg-slate-100 text-slate-600 border-slate-200";
}

export function Topbar({
  project,
  design,
  profiles,
  selectedProfile,
  onProfile,
  onApprove,
  canApprove,
  provider,
  model,
  busy,
}: {
  project: Project | null;
  design: DesignState | null;
  profiles: Profile[];
  selectedProfile: string;
  onProfile: (profileId: string) => void;
  onApprove: () => void;
  canApprove: boolean;
  provider?: string;
  model?: string;
  busy: boolean;
}) {
  const room = design?.room_id || "New design";
  return (
    <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-5">
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
          <span className="truncate">{project?.name || "Workspace"}</span>
          {design && <span className="text-slate-300">/</span>}
          {design && <span className="text-slate-500">{room}</span>}
        </div>
        <div className="mt-0.5 flex items-center gap-2">
          <h1 className="truncate text-sm font-bold text-slate-900">
            {design?.design?.layout_id ? `Design ${design.design.layout_id}` : "Bathroom design workspace"}
          </h1>
          {busy && (
            <span className="flex items-center gap-1.5 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
              <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-blue-600" />
              Agent working
            </span>
          )}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span
          className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold ${providerTone(provider)}`}
          data-testid="provider-badge"
        >
          {provider ? `${provider} · ${model}` : "Checking provider"}
        </span>
        <label className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-[11px] text-slate-500">
          <ShieldCheck size={13} className="text-slate-400" />
          <select
            className="bg-transparent text-[11px] font-semibold text-slate-700 outline-none"
            value={selectedProfile}
            onChange={(event) => onProfile(event.target.value)}
            data-testid="profile-select"
          >
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={onApprove}
          disabled={!canApprove || busy}
          className="flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-1.5 text-[11px] font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          data-testid="approve-button"
        >
          <Download size={13} /> Approve &amp; export
        </button>
      </div>
    </header>
  );
}
