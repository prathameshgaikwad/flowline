import { Download, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import type { DesignState } from "../types";

export function ApprovalDialog({
  open,
  design,
  busy,
  onClose,
  onApprove,
}: {
  open: boolean;
  design: DesignState | null;
  busy: boolean;
  onClose: () => void;
  onApprove: (approver: string) => void;
}) {
  const [approver, setApprover] = useState("Demo Engineer");
  if (!open || !design) return null;
  const noValidation = !design.validation?.length;
  const blocked =
    noValidation || design.stale || design.counts.ERROR > 0 || !design.design;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/45 p-4 backdrop-blur-sm">
      <div
        className="w-full max-w-lg overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
        data-testid="approval-dialog"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
          <div>
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">
              <ShieldCheck size={13} /> Engineer approval
            </div>
            <h2 className="mt-1 text-base font-bold text-slate-900">
              Review before export
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>
        <div className="space-y-3 px-5 py-4">
          <div className="flex flex-wrap gap-1.5">
            <span className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-700">
              {design.counts.PASS} pass
            </span>
            <span className="rounded-full bg-amber-50 px-2 py-1 text-[10px] font-bold text-amber-700">
              {design.counts.WARNING} warning
            </span>
            <span className="rounded-full bg-red-50 px-2 py-1 text-[10px] font-bold text-red-700">
              {design.counts.ERROR} error
            </span>
          </div>
          {blocked && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] leading-relaxed text-amber-800">
              {noValidation && "Validate the design before exporting. "}
              {design.stale && "The standard changed; revalidate. "}
              {design.counts.ERROR > 0 && "Fix all ERRORs before exporting. "}
            </div>
          )}
          <p className="text-[11px] leading-relaxed text-slate-500">
            {design.disclaimer}
          </p>
          <label className="block">
            <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">
              Approver
            </span>
            <input
              value={approver}
              onChange={(event) => setApprover(event.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-800 outline-none focus:border-blue-400"
            />
          </label>
        </div>
        <div className="flex items-center justify-between gap-3 border-t border-slate-100 bg-slate-50 px-5 py-4">
          {design.download_url ? (
            <a
              href={design.download_url}
              data-testid="dialog-download"
              className="flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-2 text-[11px] font-bold text-emerald-700 hover:bg-emerald-100"
            >
              <Download size={13} /> Download DXF
            </a>
          ) : (
            <span className="text-[10px] text-slate-400">The DXF is created after approval.</span>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold text-slate-600 hover:bg-slate-50"
            >
              Close
            </button>
            <button
              type="button"
              disabled={blocked || busy}
              onClick={() => onApprove(approver || "Engineer")}
              data-testid="dialog-approve"
              className="flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-2 text-[11px] font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              <ShieldCheck size={13} /> Approve &amp; export
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
