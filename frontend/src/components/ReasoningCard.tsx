import { BrainCircuit, ChevronDown } from "lucide-react";

export function ReasoningCard({
  content,
  iteration,
  defaultOpen = false,
}: {
  content: string;
  iteration?: number;
  defaultOpen?: boolean;
}) {
  return (
    <details
      open={defaultOpen}
      className="group rounded-xl border border-violet-100 bg-violet-50/60 px-3 py-2"
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 text-[10px] font-bold uppercase tracking-[0.12em] text-violet-700">
        <BrainCircuit size={13} />
        Model reasoning
        {iteration ? <span className="font-medium text-violet-400">· step {iteration}</span> : null}
        <ChevronDown size={12} className="ml-auto transition group-open:rotate-180" />
      </summary>
      <div className="mt-2 max-h-56 overflow-y-auto whitespace-pre-wrap border-t border-violet-100 pt-2 font-mono text-[10px] leading-relaxed text-violet-950/70">
        {content}
      </div>
      <p className="mt-1 text-[9px] text-violet-400">
        Provider-supplied reasoning; deterministic tool results remain authoritative.
      </p>
    </details>
  );
}
