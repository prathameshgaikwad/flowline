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
      className="group rounded-card border border-line bg-sunken/70"
    >
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 px-3.5 py-2.5 text-label font-semibold text-ink-soft">
        <BrainCircuit size={16} className="text-muted" aria-hidden="true" />
        How the assistant worked
        {iteration ? (
          <span className="font-normal text-muted">· step {iteration}</span>
        ) : null}
        <ChevronDown
          size={14}
          className="ml-auto text-muted transition-transform group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <div className="mt-0 max-h-64 overflow-y-auto whitespace-pre-wrap border-t border-line px-3.5 py-3 text-label leading-relaxed text-muted">
        {content}
      </div>
    </details>
  );
}
