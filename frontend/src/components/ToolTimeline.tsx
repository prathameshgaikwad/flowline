import { useMemo } from "react";
import { Check, ChevronDown, CircleAlert, Loader2, Wrench } from "lucide-react";
import type { AgentEvent } from "../types";

type Pair = {
  name: string;
  args: Record<string, unknown>;
  output?: Record<string, unknown>;
  success?: boolean;
  duration?: number;
};

function summarize(name: string, output?: Record<string, any>): string {
  if (!output) return "running";
  if (output.error) return String(output.error);
  if (name === "inspect_plan") return `${output.rooms?.length ?? 0} rooms · ${output.shafts?.length ?? 0} shafts`;
  if (name === "list_layout_options") return `${output.count ?? 0} layout candidates`;
  if (name === "select_layout") return `${output.layout_id ?? "layout"} · ${output.pattern ?? ""}`;
  if (name === "route_drainage") return `${output.count ?? 0} branch pipes`;
  if (name === "validate_design" || name === "apply_fix") {
    const counts = output.counts || {};
    return `${counts.PASS ?? 0} pass · ${counts.WARNING ?? 0} warn · ${counts.ERROR ?? 0} error`;
  }
  if (name === "compare_layouts") return `${output.candidates?.length ?? 0} layouts compared`;
  if (name === "get_design_state") return "design state snapshot";
  if (name === "set_fixtures") return `${output.fixtures?.join(", ") ?? "fixtures"} selected`;
  if (name === "explain_design") return "summary ready";
  return "ok";
}

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
    return <p className="text-xs text-slate-500">No tool calls yet.</p>;
  }

  return (
    <div className="space-y-1.5">
      {pairs.map((pair, index) => (
        <details
          key={`${pair.name}-${index}`}
          className="group rounded-xl border border-slate-100 bg-slate-50/60 px-2.5 py-2"
        >
          <summary className="flex cursor-pointer list-none items-center gap-2">
            <Wrench size={12} className="text-slate-400" />
            <span className="font-mono text-[10px] font-bold text-slate-700">{pair.name}</span>
            <span className="truncate text-[10px] text-slate-500">
              {summarize(pair.name, pair.output)}
            </span>
            <span className="ml-auto flex shrink-0 items-center gap-1">
              {pair.output === undefined ? (
                <Loader2 size={12} className="animate-spin text-blue-500" />
              ) : pair.success ? (
                <Check size={12} className="text-emerald-600" />
              ) : (
                <CircleAlert size={12} className="text-red-500" />
              )}
              {pair.duration ? (
                <span className="text-[9px] text-slate-400">{pair.duration.toFixed(0)} ms</span>
              ) : null}
              <ChevronDown size={12} className="text-slate-400 transition group-open:rotate-180" />
            </span>
          </summary>
          <div className="mt-2 space-y-2 border-t border-slate-200 pt-2">
            <div>
              <div className="mb-1 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-400">
                Arguments
              </div>
              <pre className="tool-json">{JSON.stringify(pair.args, null, 2)}</pre>
            </div>
            {pair.output !== undefined && (
              <div>
                <div className="mb-1 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-400">
                  Result
                </div>
                <pre className="tool-json">{JSON.stringify(pair.output, null, 2)}</pre>
              </div>
            )}
          </div>
        </details>
      ))}
    </div>
  );
}
