import { useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, RefObject } from "react";

type Viewport = { scale: number; x: number; y: number };

const MIN_SCALE = 1;
const MAX_SCALE = 8;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function usePlanViewport(
  containerRef: RefObject<HTMLDivElement | null>,
  resetKey: string,
) {
  const [viewport, setViewport] = useState<Viewport>({ scale: 1, x: 0, y: 0 });
  const viewportRef = useRef(viewport);
  const dragRef = useRef<{
    startX: number;
    startY: number;
    originX: number;
    originY: number;
    moved: boolean;
  } | null>(null);
  const movedRef = useRef(false);

  useEffect(() => {
    viewportRef.current = viewport;
  }, [viewport]);

  const constrain = useCallback(
    (next: Viewport): Viewport => {
      const element = containerRef.current;
      if (!element) return next;
      const width = element.clientWidth;
      const height = element.clientHeight;
      const minX = width - width * next.scale;
      const minY = height - height * next.scale;
      return {
        scale: next.scale,
        x: clamp(next.x, minX, 0),
        y: clamp(next.y, minY, 0),
      };
    },
    [containerRef],
  );

  const zoomAt = useCallback(
    (factor: number, clientX?: number, clientY?: number) => {
      const element = containerRef.current;
      if (!element) return;
      const rect = element.getBoundingClientRect();
      const pointX = clientX === undefined ? rect.width / 2 : clientX - rect.left;
      const pointY = clientY === undefined ? rect.height / 2 : clientY - rect.top;
      setViewport((current) => {
        const nextScale = clamp(current.scale * factor, MIN_SCALE, MAX_SCALE);
        const ratio = nextScale / current.scale;
        const nextX = pointX - ratio * (pointX - current.x);
        const nextY = pointY - ratio * (pointY - current.y);
        return constrain({ scale: nextScale, x: nextX, y: nextY });
      });
    },
    [constrain, containerRef],
  );

  const zoomIn = useCallback(() => zoomAt(1.25), [zoomAt]);
  const zoomOut = useCallback(() => zoomAt(0.8), [zoomAt]);
  const fit = useCallback(() => setViewport({ scale: 1, x: 0, y: 0 }), []);

  useEffect(() => {
    fit();
  }, [fit, resetKey]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      const factor = Math.exp(-event.deltaY * 0.0015);
      zoomAt(factor, event.clientX, event.clientY);
    };
    element.addEventListener("wheel", handleWheel, { passive: false });
    return () => element.removeEventListener("wheel", handleWheel);
  }, [containerRef, zoomAt]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver(() => {
      setViewport((current) => constrain(current));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [constrain, containerRef]);

  const onPointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (event.button !== 0) return;
      dragRef.current = {
        startX: event.clientX,
        startY: event.clientY,
        originX: viewportRef.current.x,
        originY: viewportRef.current.y,
        moved: false,
      };
      movedRef.current = false;
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    [],
  );

  const onPointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current;
      if (!drag) return;
      const dx = event.clientX - drag.startX;
      const dy = event.clientY - drag.startY;
      if (!drag.moved && Math.abs(dx) + Math.abs(dy) > 3) {
        drag.moved = true;
        movedRef.current = true;
      }
      if (!drag.moved) return;
      setViewport(
        constrain({
          scale: viewportRef.current.scale,
          x: drag.originX + dx,
          y: drag.originY + dy,
        }),
      );
    },
    [constrain],
  );

  const onPointerUp = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }, []);

  const consumeDrag = useCallback(() => {
    const moved = movedRef.current;
    movedRef.current = false;
    return moved;
  }, []);

  return {
    ...viewport,
    zoomIn,
    zoomOut,
    fit,
    zoomPercent: Math.round(viewport.scale * 100),
    onPointerDown,
    onPointerMove,
    onPointerUp,
    consumeDrag,
  };
}
