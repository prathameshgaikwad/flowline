import { useEffect, useRef } from "react";
import type { RefObject } from "react";

const MENU_ITEM = '[role="menuitem"]:not([disabled])';

export function useMenuFocus(
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

    const focusFrame = window.requestAnimationFrame(() => {
      panel.querySelector<HTMLElement>(MENU_ITEM)?.focus();
    });

    function items() {
      return Array.from(panel!.querySelectorAll<HTMLElement>(MENU_ITEM));
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeRef.current();
        return;
      }
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      const list = items();
      if (!list.length) return;
      event.preventDefault();
      const active = document.activeElement;
      const index = list.indexOf(active as HTMLElement);
      const next =
        event.key === "ArrowDown"
          ? (index + 1 + list.length) % list.length
          : (index - 1 + list.length) % list.length;
      list[next]?.focus();
    }

    panel.addEventListener("keydown", handleKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      panel.removeEventListener("keydown", handleKeyDown);
      returnFocus?.focus();
    };
  }, [open, panelRef]);
}
