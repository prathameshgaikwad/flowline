import { useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, RefObject } from "react";

const STORAGE_KEY = "flowline.split";

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function useSplitPane(
  containerRef: RefObject<HTMLElement | null>,
  {
    initial = 62,
    min = 46,
    max = 72,
    canvasMin = 480,
    assistantMin = 400,
  }: {
    initial?: number;
    min?: number;
    max?: number;
    canvasMin?: number;
    assistantMin?: number;
  } = {},
) {
  const [percent, setPercent] = useState(() => {
    try {
      const stored = Number(window.localStorage.getItem(STORAGE_KEY));
      if (Number.isFinite(stored) && stored >= min && stored <= max) return stored;
    } catch {
      // Local storage can be unavailable in private contexts.
    }
    return initial;
  });
  const [dragging, setDragging] = useState(false);
  const percentRef = useRef(percent);

  useEffect(() => {
    percentRef.current = percent;
    try {
      window.localStorage.setItem(STORAGE_KEY, String(percent));
    } catch {
      // Ignore storage failures.
    }
  }, [percent]);

  const updateFromClientX = useCallback(
    (clientX: number) => {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect || rect.width <= 0) return;
      const raw = ((clientX - rect.left) / rect.width) * 100;
      const minPercent = Math.max(min, (canvasMin / rect.width) * 100);
      const maxPercent = Math.max(minPercent, Math.min(max, 100 - (assistantMin / rect.width) * 100));
      setPercent(clamp(raw, minPercent, maxPercent));
    },
    [assistantMin, canvasMin, containerRef, max, min],
  );

  useEffect(() => {
    if (!dragging) return;
    const handleMove = (event: PointerEvent) => {
      event.preventDefault();
      updateFromClientX(event.clientX);
    };
    const handleUp = () => setDragging(false);
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [dragging, updateFromClientX]);

  const startDrag = useCallback(
    (event: ReactPointerEvent<HTMLElement>) => {
      event.preventDefault();
      setDragging(true);
    },
    [],
  );

  const reset = useCallback(() => setPercent(initial), [initial]);

  const onKeyDown = useCallback((event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const step = event.shiftKey ? 6 : 2;
    setPercent((current) =>
      clamp(current + (event.key === "ArrowRight" ? step : -step), min, max),
    );
  }, [max, min]);

  return { percent, dragging, startDrag, reset, onKeyDown };
}
