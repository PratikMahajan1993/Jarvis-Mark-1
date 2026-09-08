"use client";

import { memo, useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { panBy, screenToWorld, wheelZoomFactor, zoomAt, type Point } from "@/lib/canvas/camera";
import { worldMarqueeToLocal } from "@/lib/canvas/crop";
import { useCanvasActions, useCanvasState } from "@/lib/canvas/store";
import type { CanvasItem, CanvasTool, ItemLocalRect } from "@/lib/canvas/types";
import { CanvasBackground } from "./CanvasBackground";
import { CanvasItemContent } from "./items";
import { RegionFrame } from "./RegionFrame";
import { SelectionFrame, type ResizeHandle } from "./SelectionFrame";

/** setPointerCapture throws if the pointer is already gone; the drag can still proceed. */
function capture(element: HTMLElement | null, pointerId: number): void {
  try {
    element?.setPointerCapture(pointerId);
  } catch {
    /* pointer already released */
  }
}

function release(element: HTMLElement | null, pointerId: number): void {
  try {
    element?.releasePointerCapture(pointerId);
  } catch {
    /* pointer already released */
  }
}

type Interaction =
  | { mode: "none" }
  | { mode: "pan"; pointerId: number; from: Point; camera: Point }
  | { mode: "drag"; pointerId: number; id: string; grab: Point }
  | { mode: "marquee"; pointerId: number; id: string; origin: Point }
  | {
      mode: "resize";
      pointerId: number;
      id: string;
      handle: ResizeHandle;
      start: { x: number; y: number; w: number; h: number };
      aspect: number | null;
    };

export type CanvasCrop = { itemId: string; rect: ItemLocalRect; page?: number };

const ItemView = memo(function ItemView({ item }: { item: CanvasItem }) {
  return (
    <div
      data-item-id={item.id}
      className="absolute"
      style={{ left: item.x, top: item.y, width: item.w, height: item.h, zIndex: item.z }}
    >
      <CanvasItemContent item={item} />
    </div>
  );
});

export function CanvasViewport({
  tool,
  crop,
  cropBusy,
  onCropChange,
  onPlaceCrop,
  onDownloadCrop,
  onDropFiles,
  onCreateNote,
}: {
  tool: CanvasTool;
  crop: CanvasCrop | null;
  cropBusy?: boolean;
  onCropChange: (crop: CanvasCrop | null) => void;
  onPlaceCrop: () => void;
  onDownloadCrop: () => void;
  onDropFiles: (files: File[], world: Point) => void;
  onCreateNote: (world: Point) => void;
}) {
  const { board, selectedId } = useCanvasState();
  const { dispatch } = useCanvasActions();
  const containerRef = useRef<HTMLDivElement>(null);
  const interaction = useRef<Interaction>({ mode: "none" });
  const cameraRef = useRef(board.camera);
  const itemsRef = useRef(board.items);
  const toolRef = useRef(tool);
  const [fileOver, setFileOver] = useState(false);
  const [draft, setDraft] = useState<{ itemId: string; rect: ItemLocalRect } | null>(null);
  cameraRef.current = board.camera;
  itemsRef.current = board.items;
  toolRef.current = tool;

  useEffect(() => {
    if (tool !== "region" && interaction.current.mode === "marquee") {
      interaction.current = { mode: "none" };
      setDraft(null);
    }
  }, [tool]);

  const localPoint = useCallback((event: { clientX: number; clientY: number }): Point => {
    const rect = containerRef.current?.getBoundingClientRect();
    return { x: event.clientX - (rect?.left ?? 0), y: event.clientY - (rect?.top ?? 0) };
  }, []);

  const worldPoint = useCallback(
    (event: { clientX: number; clientY: number }): Point =>
      screenToWorld(localPoint(event), cameraRef.current),
    [localPoint],
  );

  // React attaches wheel passively, which would forbid preventDefault and let
  // the page scroll behind the board.
  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const camera = cameraRef.current;
      if (event.shiftKey && !event.ctrlKey && !event.metaKey) {
        dispatch({ type: "setCamera", camera: panBy(camera, -event.deltaY, 0) });
        return;
      }
      const factor = wheelZoomFactor(event.deltaY, event.deltaMode);
      const rect = element.getBoundingClientRect();
      const anchor = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      dispatch({ type: "setCamera", camera: zoomAt(camera, anchor, camera.z * factor) });
    };
    element.addEventListener("wheel", onWheel, { passive: false });
    return () => element.removeEventListener("wheel", onWheel);
  }, [dispatch]);

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 && event.button !== 1) return;
    const target = event.target as HTMLElement;
    const host = target.closest<HTMLElement>("[data-item-id]");
    const id = host?.dataset.itemId;
    // Elements that run their own pointer behaviour (note editor, links).
    if (target.closest("[data-canvas-interactive='true']")) return;

    capture(containerRef.current, event.pointerId);

    // Middle mouse pans from anywhere, including on top of an item.
    if (event.button === 1 || !id) {
      if (!id) dispatch({ type: "select", id: null });
      interaction.current = {
        mode: "pan",
        pointerId: event.pointerId,
        from: localPoint(event),
        camera: { x: cameraRef.current.x, y: cameraRef.current.y },
      };
      return;
    }

    const item = itemsRef.current.find((candidate) => candidate.id === id);
    if (!item) return;
    dispatch({ type: "select", id });
    dispatch({ type: "bringToFront", id });
    const world = worldPoint(event);

    if (toolRef.current === "region" && (item.kind === "pdf" || item.kind === "image")) {
      interaction.current = { mode: "marquee", pointerId: event.pointerId, id, origin: world };
      setDraft(null);
      onCropChange(null);
      return;
    }

    interaction.current = {
      mode: "drag",
      pointerId: event.pointerId,
      id,
      grab: { x: world.x - item.x, y: world.y - item.y },
    };
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const current = interaction.current;
    if (current.mode === "none" || current.pointerId !== event.pointerId) return;

    if (current.mode === "pan") {
      const point = localPoint(event);
      dispatch({
        type: "setCamera",
        camera: {
          ...cameraRef.current,
          x: current.camera.x + (point.x - current.from.x),
          y: current.camera.y + (point.y - current.from.y),
        },
      });
      return;
    }

    if (current.mode === "drag") {
      const world = worldPoint(event);
      dispatch({
        type: "moveItem",
        id: current.id,
        x: Math.round(world.x - current.grab.x),
        y: Math.round(world.y - current.grab.y),
      });
      return;
    }

    if (current.mode === "marquee") {
      const item = itemsRef.current.find((candidate) => candidate.id === current.id);
      if (!item) return;
      const rect = worldMarqueeToLocal(item, current.origin, worldPoint(event));
      setDraft(rect ? { itemId: item.id, rect } : null);
      return;
    }

    const world = worldPoint(event);
    const { start, handle, aspect } = current;
    const right = start.x + start.w;
    const bottom = start.y + start.h;
    const anchorX = handle === "nw" || handle === "sw" ? right : start.x;
    const anchorY = handle === "nw" || handle === "ne" ? bottom : start.y;
    let w = Math.max(40, Math.abs(world.x - anchorX));
    let h = Math.max(40, Math.abs(world.y - anchorY));
    if (aspect && !event.altKey) {
      // Longest edge wins, so the drag never feels like it fights the pointer.
      if (w / aspect > h) h = w / aspect;
      else w = h * aspect;
    }
    const x = handle === "nw" || handle === "sw" ? anchorX - w : anchorX;
    const y = handle === "nw" || handle === "ne" ? anchorY - h : anchorY;
    dispatch({
      type: "resizeItem",
      id: current.id,
      x: Math.round(x),
      y: Math.round(y),
      w: Math.round(w),
      h: Math.round(h),
    });
  };

  const endInteraction = (event: ReactPointerEvent<HTMLDivElement>) => {
    const current = interaction.current;
    if (current.mode !== "none" && current.pointerId === event.pointerId) {
      if (current.mode === "marquee") {
        const item = itemsRef.current.find((candidate) => candidate.id === current.id);
        const rect = item ? worldMarqueeToLocal(item, current.origin, worldPoint(event)) : null;
        const min = 8 / cameraRef.current.z;
        if (item && rect && rect.w >= min && rect.h >= min) {
          onCropChange({
            itemId: item.id,
            rect,
            page: item.kind === "pdf" ? item.page : undefined,
          });
        } else {
          onCropChange(null);
        }
        setDraft(null);
      }
      release(containerRef.current, event.pointerId);
    }
    interaction.current = { mode: "none" };
  };

  const onResizeStart = (handle: ResizeHandle, event: ReactPointerEvent<HTMLElement>) => {
    event.stopPropagation();
    const item = itemsRef.current.find((candidate) => candidate.id === selectedId);
    if (!item) return;
    capture(containerRef.current, event.pointerId);
    interaction.current = {
      mode: "resize",
      pointerId: event.pointerId,
      id: item.id,
      handle,
      start: { x: item.x, y: item.y, w: item.w, h: item.h },
      aspect: item.kind === "note" ? null : item.w / item.h,
    };
  };

  const selected = board.items.find((item) => item.id === selectedId) ?? null;
  const camera = board.camera;
  const draftItem = draft ? board.items.find((item) => item.id === draft.itemId) : null;
  const cropItem = crop ? board.items.find((item) => item.id === crop.itemId) : null;
  const cursor =
    interaction.current.mode === "pan"
      ? "grabbing"
      : tool === "region"
        ? "crosshair"
        : "default";

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 touch-none overflow-hidden"
      style={{ cursor }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endInteraction}
      onPointerCancel={endInteraction}
      onDoubleClick={(event) => {
        const target = event.target as HTMLElement;
        if (target.closest("[data-item-id]")) return;
        onCreateNote(worldPoint(event));
      }}
      onDragOver={(event) => {
        event.preventDefault();
        setFileOver(true);
      }}
      onDragLeave={(event) => {
        if (event.currentTarget.contains(event.relatedTarget as Node)) return;
        setFileOver(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setFileOver(false);
        const files = Array.from(event.dataTransfer.files);
        if (files.length) onDropFiles(files, worldPoint(event));
      }}
    >
      <CanvasBackground camera={camera} />

      <div
        className="absolute left-0 top-0 origin-top-left will-change-transform"
        style={{ transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.z})` }}
      >
        {board.items.map((item) => (
          <ItemView key={item.id} item={item} />
        ))}
      </div>

      {selected ? (
        <SelectionFrame item={selected} camera={camera} onResizeStart={onResizeStart} />
      ) : null}

      {draftItem && draft ? (
        <RegionFrame item={draftItem} region={draft.rect} camera={camera} draft />
      ) : null}

      {cropItem && crop ? (
        <RegionFrame
          item={cropItem}
          region={crop.rect}
          camera={camera}
          busy={cropBusy}
          onPlace={onPlaceCrop}
          onDownload={onDownloadCrop}
          onCancel={() => onCropChange(null)}
        />
      ) : null}

      {fileOver ? (
        <div className="pointer-events-none absolute inset-0 grid place-items-center bg-cyan/5 text-white/40">
          Drop it on the board
        </div>
      ) : null}
    </div>
  );
}
