import { ChevronDown, MessageSquareText } from "lucide-react";

export function AgentNoteCard({
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
      className="group rounded-xl border border-sky-100 bg-sky-50/60 px-3 py-2"
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 text-[10px] font-bold uppercase tracking-[0.12em] text-sky-700">
        <MessageSquareText size={13} />
        Agent note
        {iteration ? <span className="font-medium text-sky-400">· step {iteration}</span> : null}
        <ChevronDown size={12} className="ml-auto transition group-open:rotate-180" />
      </summary>
      <div className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap border-t border-sky-100 pt-2 text-[11px] leading-relaxed text-slate-700">
        {content}
      </div>
    </details>
  );
}
