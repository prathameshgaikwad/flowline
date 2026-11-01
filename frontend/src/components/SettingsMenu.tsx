import { useRef } from "react";
import { Info, ShieldCheck, Sparkles, X } from "lucide-react";
import type { Profile } from "../types";
import { friendlyProfileName } from "../lib/labels";
import { usePopoverFocus } from "../hooks/usePopoverFocus";
import { Badge, IconButton, selectClass } from "./ui";

export function SettingsMenu({
  profiles,
  selectedProfile,
  onProfile,
  provider,
  model,
  onClose,
  busy = false,
}: {
  profiles: Profile[];
  selectedProfile: string;
  onProfile: (profileId: string) => void;
  provider?: string;
  model?: string;
  onClose: () => void;
  busy?: boolean;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const active = profiles.find((profile) => profile.id === selectedProfile);
  usePopoverFocus(true, onClose, panelRef);

  return (
    <div
      ref={panelRef}
      id="settings-menu"
      role="dialog"
      aria-label="Design settings"
      className="absolute right-0 top-[calc(100%+8px)] z-50 w-[min(360px,calc(100vw-1.5rem))] overflow-hidden rounded-overlay border border-line bg-raised shadow-float animate-fade-up"
      data-testid="settings-menu"
    >
      <div className="flex items-center justify-between border-b border-line px-4 py-3.5">
        <div>
          <div className="text-ui font-semibold text-ink">Design settings</div>
          <div className="mt-0.5 text-xs text-muted">
            Applies to the selected design
          </div>
        </div>
        <IconButton label="Close design settings" onClick={onClose}>
          <X size={18} />
        </IconButton>
      </div>

      <div className="space-y-4 px-4 py-4">
        <label className="block">
          <span className="flex items-center gap-1.5 text-label font-medium text-ink-soft">
            <ShieldCheck size={14} className="text-accent" aria-hidden="true" />
            Code standard
          </span>
          <select
            value={selectedProfile}
            onChange={(event) => {
              onProfile(event.target.value);
              onClose();
            }}
            disabled={busy}
            className={`${selectClass} mt-2`}
            data-testid="profile-select"
          >
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {friendlyProfileName(profile.name)}
              </option>
            ))}
          </select>
          <span className="mt-2 block text-xs leading-relaxed text-muted">
            {busy
              ? "Wait for the current run to finish before changing the standard."
              : "Changing the standard marks this design for recheck before export."}
          </span>
        </label>

        <div className="rounded-card border border-line bg-sunken px-3.5 py-3">
          <div className="flex items-center gap-1.5 text-label font-medium text-ink-soft">
            <Sparkles size={14} className="text-muted" aria-hidden="true" />
            Model
          </div>
          <div className="mt-1 break-words text-label text-ink">
            {provider ? `${provider} · ${model}` : "Checking provider"}
          </div>
          {active?.status === "POC" && (
            <Badge tone="warning" className="mt-2">
              Demo rule set
            </Badge>
          )}
        </div>

        <div className="flex items-start gap-2.5 rounded-card border border-line px-3.5 py-3 text-xs leading-relaxed text-muted">
          <Info size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>
            Flowline checks a small, cited rule set. It is a design assistant,
            not a compliance certificate. A licensed engineer governs the
            issued design.
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between border-t border-line bg-sunken px-4 py-3 text-xs text-muted">
        <span>Shortcuts</span>
        <span className="flex items-center gap-1.5">
          <kbd className="rounded border border-line-strong bg-raised px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">
            F
          </kbd>
          full screen
          <span aria-hidden="true">·</span>
          <kbd className="rounded border border-line-strong bg-raised px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">
            Esc
          </kbd>
          close
        </span>
      </div>
    </div>
  );
}
