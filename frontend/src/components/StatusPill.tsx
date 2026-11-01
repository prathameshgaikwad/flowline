import type { DesignState } from "../types";
import { designStatus } from "../lib/labels";
import { cx, Dot } from "./ui";

const tones = {
  neutral: "border-line-strong bg-sunken text-muted",
  accent: "border-accent/20 bg-accent-soft text-accent",
  success: "border-success-line bg-success-soft text-success",
  warning: "border-warning-line bg-warning-soft text-warning",
  danger: "border-danger-line bg-danger-soft text-danger",
};

export function StatusPill({
  design,
  busy,
  className,
}: {
  design: DesignState | null;
  busy: boolean;
  className?: string;
}) {
  const status = designStatus(design, busy);
  return (
    <span
      className={cx(
        "inline-flex min-h-7 max-w-[145px] shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        tones[status.tone],
        className,
      )}
      title={status.label}
      data-testid="status-pill"
    >
      <Dot tone={status.tone} pulse={status.pulse} />
      <span className="truncate">{status.label}</span>
    </span>
  );
}
