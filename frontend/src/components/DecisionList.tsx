import {
  ArrowRightLeft,
  CheckCircle2,
  ShieldAlert,
  Wrench,
} from "lucide-react";
import type { Decision, Project } from "../types";
import { roomNameFor } from "../lib/labels";
import { Badge, cx } from "./ui";

function decisionTime(decision: Decision) {
  if (!decision.at) return null;
  const date = new Date(Number(decision.at) * 1000);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function DecisionList({
  decisions,
  currentLayoutId,
  project,
  roomLayouts,
}: {
  decisions: Decision[];
  currentLayoutId?: string | null;
  project?: Project | null;
  roomLayouts?: Record<string, string | null>;
}) {
  if (!decisions.length) {
    return (
      <p className="rounded-card border border-dashed border-line-strong bg-sunken px-4 py-4 text-label text-muted">
        No decisions recorded yet.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      {[...decisions].reverse().map((decision, index) => {
        const time = decisionTime(decision);
        if (decision.kind === "layout_selected") {
          const rejected = (decision.rejected || []) as {
            id: string;
            reason: string;
            score?: number;
          }[];
          const roomId = decision.room_id ? String(decision.room_id) : null;
          const layoutForRoom = roomId
            ? roomLayouts?.[roomId] ?? null
            : currentLayoutId;
          const isCurrent =
            Boolean(layoutForRoom) &&
            String(decision.candidate_id) === String(layoutForRoom);
          const isEarlier = Boolean(layoutForRoom) && !isCurrent;
          return (
            <article
              key={`${decision.kind}-${index}`}
              className={cx(
                "rounded-card border p-4",
                isEarlier
                  ? "border-line bg-sunken/60"
                  : "border-accent/20 bg-accent-soft/60",
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <div
                  className={cx(
                    "flex items-center gap-1.5 text-label font-semibold",
                    isEarlier ? "text-muted" : "text-accent",
                  )}
                >
                  <CheckCircle2 size={15} aria-hidden="true" /> Layout selected
                </div>
                {roomId ? (
                  <Badge tone="neutral">{roomNameFor(project || null, roomId)}</Badge>
                ) : null}
                {isCurrent && <Badge tone="accent">Current</Badge>}
                {isEarlier && <Badge tone="neutral">Earlier</Badge>}
                {time && (
                  <time className="ml-auto text-xs text-muted" dateTime={new Date(Number(decision.at) * 1000).toISOString()}>
                    {time}
                  </time>
                )}
              </div>
              <div className="mt-2 text-ui font-semibold text-ink">
                {String(decision.candidate_id)} · {String(decision.pattern)}
              </div>
              <p className="mt-1 text-label leading-relaxed text-muted">
                {String(decision.rationale || "No rationale recorded.")}
              </p>
              {rejected.length > 0 && (
                <div className="mt-3 border-t border-line/80 pt-2.5">
                  <div className="text-xs font-semibold uppercase tracking-[0.06em] text-muted">
                    Other layouts considered
                  </div>
                  <ul className="mt-1.5 space-y-1.5">
                    {rejected.map((item) => (
                      <li key={item.id} className="text-label leading-relaxed text-muted">
                        <span className="font-mono font-semibold text-ink-soft">
                          {item.id}
                        </span>{" "}
                        — {item.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </article>
          );
        }
        if (decision.kind === "fix_applied") {
          return (
            <article
              key={`${decision.kind}-${index}`}
              className="rounded-card border border-success-line bg-success-soft/60 p-4"
            >
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1.5 text-label font-semibold text-success">
                  <Wrench size={15} aria-hidden="true" /> Fix applied
                </div>
                {time && (
                  <time className="ml-auto text-xs text-muted" dateTime={new Date(Number(decision.at) * 1000).toISOString()}>
                    {time}
                  </time>
                )}
              </div>
              <p className="mt-1.5 text-label leading-relaxed text-muted">
                {String(decision.description)}
              </p>
            </article>
          );
        }
        if (decision.kind === "profile_changed") {
          return (
            <article
              key={`${decision.kind}-${index}`}
              className="rounded-card border border-line bg-raised p-4"
            >
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1.5 text-label font-semibold text-muted">
                  <ArrowRightLeft size={15} aria-hidden="true" /> Code standard
                  changed
                </div>
                {time && (
                  <time className="ml-auto text-xs text-muted" dateTime={new Date(Number(decision.at) * 1000).toISOString()}>
                    {time}
                  </time>
                )}
              </div>
              <p className="mt-1.5 text-label leading-relaxed text-muted">
                {String(decision.previous_profile)} → {String(decision.profile_id)}.{" "}
                {String(decision.reason || "")}
              </p>
            </article>
          );
        }
        if (
          decision.kind === "route_failed" ||
          decision.kind === "fixtures_changed"
        ) {
          const failed = decision.kind === "route_failed";
          return (
            <article
              key={`${decision.kind}-${index}`}
              className={cx(
                "rounded-card border p-4",
                failed
                  ? "border-warning-line bg-warning-soft/60"
                  : "border-line bg-raised",
              )}
            >
              <div className="flex items-center gap-2">
                <div
                  className={cx(
                    "flex items-center gap-1.5 text-label font-semibold",
                    failed ? "text-warning" : "text-muted",
                  )}
                >
                  <ShieldAlert size={15} aria-hidden="true" />{" "}
                  {failed ? "Route failed" : "Fixtures updated"}
                </div>
                {time && (
                  <time className="ml-auto text-xs text-muted" dateTime={new Date(Number(decision.at) * 1000).toISOString()}>
                    {time}
                  </time>
                )}
              </div>
              <p className="mt-1.5 text-label leading-relaxed text-muted">
                {failed
                  ? String(decision.message)
                  : `Now using ${(decision.fixtures as string[])?.join(", ")}.`}
              </p>
            </article>
          );
        }
        return null;
      })}
    </div>
  );
}
