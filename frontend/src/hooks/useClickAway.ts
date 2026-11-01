import { useEffect } from "react";
import type { RefObject } from "react";

export function useClickAway(
  ref: RefObject<HTMLElement | null>,
  onClose: () => void,
  active = true,
) {
  useEffect(() => {
    if (!active) return;
    const handlePointer = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handlePointer);
    return () => document.removeEventListener("mousedown", handlePointer);
  }, [ref, onClose, active]);
}
