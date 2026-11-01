import { useEffect, useRef } from "react";
import type { RefObject } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function useModalFocus<T extends HTMLElement = HTMLDivElement>(
  open: boolean,
  onClose: () => void,
  initialFocusRef?: RefObject<HTMLElement | null>,
) {
  const containerRef = useRef<T>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const container = containerRef.current;
    if (!container) return;

    const returnFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const focusInitial = window.requestAnimationFrame(() => {
      const target =
        initialFocusRef?.current ||
        container.querySelector<HTMLElement>(FOCUSABLE) ||
        container;
      target.focus();
    });

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        container!.querySelectorAll<HTMLElement>(FOCUSABLE),
      ).filter(
        (element) =>
          element.offsetParent !== null ||
          element.getClientRects().length > 0,
      );
      if (!focusable.length) {
        event.preventDefault();
        container!.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === container)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      window.cancelAnimationFrame(focusInitial);
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      returnFocus?.focus();
    };
  }, [initialFocusRef, open]);

  return containerRef;
}
