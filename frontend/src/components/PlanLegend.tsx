import { useId, useState } from "react";
import { ChevronDown, Layers3 } from "lucide-react";
import type { DesignState, Project } from "../types";
import { cx } from "./ui";

export function PlanLegend({
  design,
  project,
  defaultOpen = false,
  className,
}: {
  design: DesignState | null;
  project?: Project | null;
  defaultOpen?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const bodyId = useId();
  const systems = new Set(
    [
      ...(design?.design?.pipes || []),
      ...(design?.design?.vent_pipes || []),
      ...(design?.design?.supply_pipes || []),
    ].map((pipe) => String(pipe.system)),
  );
  const shaftServices = new Set(
    (project?.shafts || []).flatMap((shaft) => shaft.services || []),
  );
  const hasDesign = Boolean(design?.design);
  const hasDetectedFixtures = Boolean(project?.detected_fixtures?.length);
  return (
    <div
      className={cx(
        "rounded-card border border-line bg-raised/95 shadow-card backdrop-blur-sm",
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={bodyId}
        className="flex min-h-11 items-center gap-1.5 px-3 text-label font-medium text-ink-soft lg:min-h-9"
      >
        <Layers3 size={15} className="text-muted" aria-hidden="true" />
        Legend
        <ChevronDown
          size={14}
          className={cx("text-muted transition-transform", open && "rotate-180")}
          aria-hidden="true"
        />
      </button>
      {open && (
        <div
          id={bodyId}
          className="space-y-2 border-t border-line px-3 py-2.5 text-label text-muted"
        >
          {hasDesign ? (
            <>
              {systems.has("SOIL") && (
                <LegendRow color="#dc2626" label="Soil pipe" />
              )}
              {systems.has("WASTE") && (
                <LegendRow color="#d97706" label="Waste pipe" />
              )}
              {systems.has("VENT") && (
                <LegendRow color="#15803d" label="Vent pipe (dashed)" dashed />
              )}
              {systems.has("COLD_WATER") && (
                <LegendRow color="#2563eb" label="Cold water" />
              )}
              {systems.has("HOT_WATER") && (
                <LegendRow color="#ea580c" label="Hot water" dashed />
              )}
              <LegendRow color="#1e40af" label="Fixtures" />
              <LegendRow color="#d92d20" label="Stack" outline />
            </>
          ) : (
            <>
              <LegendRow color="#24272e" label="Walls" />
              <LegendRow color="#cfc6b5" label="Rooms" />
              <LegendRow color="#a16207" label="Doors" />
              <LegendRow color="#0f6f8f" label="Windows" />
            </>
          )}
          {hasDetectedFixtures && (
            <LegendRow color="#2563eb" label="Detected fixtures" dashed />
          )}
          {Boolean(project?.shafts?.length) && (
            <LegendRow color="#4f46e5" label="Service shaft" outline />
          )}
          {shaftServices.has("DRAIN") && (
            <LegendRow color="#dc2626" label="Drain outlet" />
          )}
          {shaftServices.has("WATER") && (
            <LegendRow color="#2563eb" label="Water inlet" />
          )}
          {shaftServices.has("VENT") && (
            <LegendRow color="#16a34a" label="Vent" dashed />
          )}
          <div className="border-t border-line pt-2 text-xs text-muted">
            All dimensions in {design ? "mm" : "drawing units"}
          </div>
        </div>
      )}
    </div>
  );
}

function LegendRow({
  color,
  label,
  outline = false,
  dashed = false,
}: {
  color: string;
  label: string;
  outline?: boolean;
  dashed?: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <span
        className="h-2.5 w-5 shrink-0 rounded-full"
        style={{
          backgroundColor: outline
            ? "transparent"
            : dashed
              ? "transparent"
              : color,
          backgroundImage: dashed
            ? `repeating-linear-gradient(90deg, ${color} 0 5px, transparent 5px 9px)`
            : undefined,
          border: outline ? `2px solid ${color}` : undefined,
        }}
        aria-hidden="true"
      />
      <span>{label}</span>
    </div>
  );
}
