import { useMemo } from "react";
import {
  Check,
  ChevronDown,
  CircleAlert,
  LoaderCircle,
  Wrench,
} from "lucide-react";
import type { AgentEvent } from "../types";
import { humanTool, toolSummary } from "../lib/labels";

type Pair = {
  name: string;
  args: Record<string, unknown>;
  output?: Record<string, unknown>;
  success?: boolean;
  duration?: number;
};

export function ToolTimeline({ events }: { events: AgentEvent[] }) {
  const pairs = useMemo<Pair[]>(() => {
    const queues: Record<string, Pair[]> = {};
    const result: Pair[] = [];
    for (const event of events) {
      if (event.type === "tool_call") {
        const pair: Pair = {
          name: String(event.tool || "tool"),
          args: (event.arguments || {}) as Record<string, unknown>,
        };
        queues[pair.name] = queues[pair.name] || [];
        queues[pair.name].push(pair);
        result.push(pair);
      } else if (event.type === "tool_result") {
        const name = String(event.tool || "tool");
        const queue = queues[name] || [];
        const pair = queue.shift();
        if (pair) {
          pair.output = (event.output || {}) as Record<string, unknown>;
          pair.success = Boolean(event.success);
          pair.duration = Number(event.duration_ms || 0);
        } else {
          result.push({
            name,
            args: {},
            output: (event.output || {}) as Record<string, unknown>,
            success: Boolean(event.success),
            duration: Number(event.duration_ms || 0),
          });
        }
      }
    }
    return result;
  }, [events]);

  if (!pairs.length) {
    return (
      <p className="rounded-card border border-dashed border-line-strong bg-sunken px-4 py-4 text-label text-muted">
        No activity yet. Tools appear here as the assistant works.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {pairs.map((pair, index) => (
        <details
          key={`${pair.name}-${index}`}
          className="group rounded-card border border-line bg-raised"
        >
          <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 px-3 py-2.5">
            <Wrench size={14} className="shrink-0 text-muted" aria-hidden="true" />
            <span className="shrink-0 text-label font-medium text-ink-soft">
              {humanTool(pair.name)}
            </span>
            <span className="min-w-0 flex-1 truncate text-xs text-muted">
              {toolSummary(pair.name, pair.output)}
            </span>
            <span className="flex shrink-0 items-center gap-1.5">
              {pair.output === undefined ? (
                <LoaderCircle
                  size={14}
                  className="animate-spin text-accent"
                  aria-label="Running"
                />
              ) : pair.success ? (
                <Check size={14} className="text-success" aria-label="Succeeded" />
              ) : (
                <CircleAlert
                  size={14}
                  className="text-danger"
                  aria-label="Failed"
                />
              )}
              {pair.duration && pair.duration >= 10 ? (
                <span className="hidden font-mono text-xs text-muted tabular-nums sm:inline">
                  {pair.duration.toFixed(0)} ms
                </span>
              ) : null}
              <ChevronDown
                size={14}
                className="text-muted transition-transform group-open:rotate-180"
                aria-hidden="true"
              />
            </span>
          </summary>
          <div className="mt-0 space-y-2 border-t border-line px-3 pb-3 pt-2.5">
            <div>
              <div className="mb-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-muted">
                Input
              </div>
              <pre className="tool-json">{JSON.stringify(pair.args, null, 2)}</pre>
            </div>
            {pair.output !== undefined && (
              <div>
                <div className="mb-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-muted">
                  Result
                </div>
                <pre className="tool-json">
                  {JSON.stringify(pair.output, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </details>
      ))}
    </div>
  );
}
