import { useEffect, useRef } from "react";
import type { RefObject } from "react";

const FOCUSABLE =
  'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function usePopoverFocus(
  open: boolean,
  onClose: () => void,
  panelRef: RefObject<HTMLElement | null>,
) {
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const panel = panelRef.current;
    if (!panel) return;
    const returnFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const frame = window.requestAnimationFrame(() => {
      panel.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    });
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeRef.current();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handleKeyDown);
      returnFocus?.focus();
    };
  }, [open, panelRef]);
}
