"use client";

import { memo, useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { panBy, screenToWorld, wheelZoomFactor, worldToScreen, zoomAt, type Point } from "@/lib/canvas/camera";
import { worldMarqueeToLocal } from "@/lib/canvas/crop";
import {
  boundsFromPoints,
  groupMembers,
  itemsInRect,
  rectFromPoints,
  snap as snapValue,
  snapToItems,
  toLocal,
} from "@/lib/canvas/geometry";
import { useCanvasActions, useCanvasState } from "@/lib/canvas/store";
import {
  createId,
  type CanvasItem,
  type CanvasTool,
  type ItemLocalRect,
  type ShapeKind,
  type StrokeColor,
} from "@/lib/canvas/types";
import { CanvasBackground } from "./CanvasBackground";
import { CanvasItemContent } from "./items";
import { RegionFrame } from "./RegionFrame";
import { SelectionFrame, type ResizeHandle } from "./SelectionFrame";

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

type Origins = Record<string, Point>;

type Interaction =
  | { mode: "none" }
  | { mode: "pan"; pointerId: number; from: Point; camera: Point }
  | { mode: "drag"; pointerId: number; id: string; grab: Point; origins: Origins }
  | { mode: "box"; pointerId: number; origin: Point }
  | { mode: "crop"; pointerId: number; id: string; origin: Point }
  | { mode: "draw"; pointerId: number; tool: CanvasTool; origin: Point }
  | { mode: "ink"; pointerId: number; points: Point[] }
  | {
      mode: "resize";
      pointerId: number;
      id: string;
      handle: ResizeHandle;
      start: { x: number; y: number; w: number; h: number };
      aspect: number | null;
    }
  | { mode: "rotate"; pointerId: number; id: string; center: Point; startAngle: number; startRot: number };

export type CanvasCrop = { itemId: string; rect: ItemLocalRect; page?: number };

const DRAW_TOOLS: CanvasTool[] = ["rect", "ellipse", "diamond", "line", "arrow"];

const ItemView = memo(function ItemView({ item }: { item: CanvasItem }) {
  return (
    <div
      data-item-id={item.id}
      className="absolute"
      style={{
        left: item.x,
        top: item.y,
        width: item.w,
        height: item.h,
        zIndex: item.z,
        transform: item.rotation ? `rotate(${item.rotation}deg)` : undefined,
        transformOrigin: "center",
        opacity: item.locked ? 0.82 : 1,
      }}
    >
      <CanvasItemContent item={item} />
    </div>
  );
});

export function CanvasViewport({
  tool,
  snap,
  spacePan,
  strokeColor,
  crop,
  cropBusy,
  onCropChange,
  onPlaceCrop,
  onDownloadCrop,
  onDropFiles,
  onCreateNote,
  onCreateText,
  onContextMenu,
}: {
  tool: CanvasTool;
  snap: boolean;
  spacePan: boolean;
  strokeColor: StrokeColor;
  crop: CanvasCrop | null;
  cropBusy?: boolean;
  onCropChange: (crop: CanvasCrop | null) => void;
  onPlaceCrop: () => void;
  onDownloadCrop: () => void;
  onDropFiles: (files: File[], world: Point) => void;
  onCreateNote: (world: Point) => void;
  onCreateText: (world: Point) => void;
  onContextMenu: (screen: Point, itemId: string | null) => void;
}) {
  const { board, selectedIds } = useCanvasState();
  const { dispatch } = useCanvasActions();
  const containerRef = useRef<HTMLDivElement>(null);
  const interaction = useRef<Interaction>({ mode: "none" });
  const cameraRef = useRef(board.camera);
  const itemsRef = useRef(board.items);
  const toolRef = useRef(tool);
  const snapRef = useRef(snap);
  const spaceRef = useRef(spacePan);
  const selectedRef = useRef(selectedIds);
  const colorRef = useRef(strokeColor);
  const [fileOver, setFileOver] = useState(false);
  const [draft, setDraft] = useState<{ itemId: string; rect: ItemLocalRect } | null>(null);
  const [box, setBox] = useState<{ a: Point; b: Point } | null>(null);
  const [ink, setInk] = useState<Point[] | null>(null);
  const [shape, setShape] = useState<{ tool: CanvasTool; a: Point; b: Point } | null>(null);
  cameraRef.current = board.camera;
  itemsRef.current = board.items;
  toolRef.current = tool;
  snapRef.current = snap;
  spaceRef.current = spacePan;
  selectedRef.current = selectedIds;
  colorRef.current = strokeColor;

  useEffect(() => {
    if (tool !== "region" && interaction.current.mode === "crop") {
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

  const applySnap = (rect: { x: number; y: number; w: number; h: number }, skipId?: string) => {
    let next = rect;
    if (snapRef.current) next = { ...next, x: snapValue(next.x), y: snapValue(next.y) };
    const others = itemsRef.current.filter((item) => item.id !== skipId);
    return snapToItems(next, others);
  };

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button === 2) return;
    if (event.button !== 0 && event.button !== 1) return;
    const target = event.target as HTMLElement;
    if (target.closest("[data-canvas-interactive='true']")) return;
    const host = target.closest<HTMLElement>("[data-item-id]");
    const id = host?.dataset.itemId;
    capture(containerRef.current, event.pointerId);
    const world = worldPoint(event);
    const currentTool = toolRef.current;
    const pan =
      event.button === 1 || spaceRef.current || currentTool === "pan";

    if (pan) {
      interaction.current = {
        mode: "pan",
        pointerId: event.pointerId,
        from: localPoint(event),
        camera: { x: cameraRef.current.x, y: cameraRef.current.y },
      };
      return;
    }

    if (currentTool === "ink") {
      interaction.current = { mode: "ink", pointerId: event.pointerId, points: [world] };
      setInk([world]);
      return;
    }

    if (DRAW_TOOLS.includes(currentTool)) {
      interaction.current = { mode: "draw", pointerId: event.pointerId, tool: currentTool, origin: world };
      setShape({ tool: currentTool, a: world, b: world });
      return;
    }

    if (currentTool === "note" || currentTool === "text") {
      interaction.current = { mode: "box", pointerId: event.pointerId, origin: world };
      return;
    }

    if (!id) {
      if (!event.shiftKey) dispatch({ type: "select", ids: [] });
      interaction.current = { mode: "box", pointerId: event.pointerId, origin: world };
      setBox({ a: world, b: world });
      return;
    }

    const item = itemsRef.current.find((candidate) => candidate.id === id);
    if (!item) return;

    if (currentTool === "region" && (item.kind === "pdf" || item.kind === "image")) {
      dispatch({ type: "select", ids: [id] });
      interaction.current = { mode: "crop", pointerId: event.pointerId, id, origin: world };
      setDraft(null);
      onCropChange(null);
      return;
    }

    const grouped = groupMembers(itemsRef.current, item);
    const already = selectedRef.current.includes(id);
    let nextIds = selectedRef.current;
    if (event.shiftKey) {
      nextIds = already ? nextIds.filter((value) => value !== id) : [...nextIds, ...grouped.map((entry) => entry.id)];
      dispatch({ type: "select", ids: Array.from(new Set(nextIds)) });
    } else if (!already) {
      nextIds = grouped.map((entry) => entry.id);
      dispatch({ type: "select", ids: nextIds });
    }

    if (item.locked) return;

    const movingIds = (event.shiftKey ? nextIds : already ? selectedRef.current : nextIds).filter((value) => {
      const found = itemsRef.current.find((entry) => entry.id === value);
      return found && !found.locked;
    });
    const unique = Array.from(new Set(movingIds.length ? movingIds : [id]));

    if (event.altKey) {
      dispatch({ type: "checkpoint" });
      const clones = unique
        .map((value) => itemsRef.current.find((entry) => entry.id === value))
        .filter(Boolean)
        .map((entry) => ({ ...entry!, id: createId(), groupId: undefined }));
      dispatch({ type: "addItems", items: clones });
      const origins: Origins = {};
      clones.forEach((clone) => {
        origins[clone.id] = { x: clone.x, y: clone.y };
      });
      interaction.current = {
        mode: "drag",
        pointerId: event.pointerId,
        id: clones[0]?.id ?? id,
        grab: { x: world.x - item.x, y: world.y - item.y },
        origins,
      };
      return;
    }

    dispatch({ type: "checkpoint" });
    const origins: Origins = {};
    unique.forEach((value) => {
      const found = itemsRef.current.find((entry) => entry.id === value);
      if (found) origins[found.id] = { x: found.x, y: found.y };
    });
    interaction.current = {
      mode: "drag",
      pointerId: event.pointerId,
      id,
      grab: { x: world.x - item.x, y: world.y - item.y },
      origins,
    };
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const current = interaction.current;
    if (current.mode === "none" || current.pointerId !== event.pointerId) return;
    const world = worldPoint(event);

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
      const origin = current.origins[current.id];
      if (!origin) return;
      let x = world.x - current.grab.x;
      let y = world.y - current.grab.y;
      const primary = itemsRef.current.find((item) => item.id === current.id);
      const snapped = applySnap({ x, y, w: primary?.w ?? 1, h: primary?.h ?? 1 }, current.id);
      x = snapped.x;
      y = snapped.y;
      const dx = x - origin.x;
      const dy = y - origin.y;
      dispatch({
        type: "moveItems",
        moves: Object.entries(current.origins).map(([id, start]) => ({
          id,
          x: Math.round(start.x + dx),
          y: Math.round(start.y + dy),
        })),
      });
      return;
    }

    if (current.mode === "box") {
      setBox({ a: current.origin, b: world });
      return;
    }

    if (current.mode === "crop") {
      const item = itemsRef.current.find((candidate) => candidate.id === current.id);
      if (!item) return;
      const rect = worldMarqueeToLocal(item, current.origin, world);
      setDraft(rect ? { itemId: item.id, rect } : null);
      return;
    }

    if (current.mode === "draw") {
      setShape({ tool: current.tool, a: current.origin, b: world });
      return;
    }

    if (current.mode === "ink") {
      const points = [...current.points, world];
      current.points = points;
      setInk(points);
      return;
    }

    if (current.mode === "rotate") {
      const angle = (Math.atan2(world.y - current.center.y, world.x - current.center.x) * 180) / Math.PI;
      dispatch({
        type: "updateItem",
        id: current.id,
        patch: { rotation: Math.round(current.startRot + (angle - current.startAngle)) },
      });
      return;
    }

    const { start, handle, aspect } = current;
    const right = start.x + start.w;
    const bottom = start.y + start.h;
    const anchorX = handle === "nw" || handle === "sw" ? right : start.x;
    const anchorY = handle === "nw" || handle === "ne" ? bottom : start.y;
    let w = Math.max(8, Math.abs(world.x - anchorX));
    let h = Math.max(8, Math.abs(world.y - anchorY));
    if (aspect && !event.altKey) {
      if (w / aspect > h) h = w / aspect;
      else w = h * aspect;
    }
    if (snapRef.current) {
      w = snapValue(w);
      h = snapValue(h);
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

  const commitInk = (points: Point[]) => {
    if (points.length < 2) return;
    const bounds = boundsFromPoints(points, 10);
    dispatch({
      type: "addItem",
      item: {
        id: createId(),
        kind: "stroke",
        mode: "ink",
        x: Math.round(bounds.x),
        y: Math.round(bounds.y),
        w: Math.round(bounds.w),
        h: Math.round(bounds.h),
        rotation: 0,
        z: 0,
        points: toLocal(points, { x: bounds.x, y: bounds.y }),
        color: colorRef.current,
        weight: 2.5,
      },
    });
  };

  const commitShape = (drawTool: CanvasTool, a: Point, b: Point, shift: boolean) => {
    let rect = rectFromPoints(a, b);
    if (rect.w < 4 && rect.h < 4) return;
    if (shift) {
      const size = Math.max(rect.w, rect.h);
      rect = { ...rect, w: size, h: size };
    }
    if (drawTool === "line" || drawTool === "arrow") {
      const pad = 12;
      const bounds = boundsFromPoints([a, b], pad);
      dispatch({
        type: "addItem",
        item: {
          id: createId(),
          kind: "stroke",
          mode: drawTool === "arrow" ? "arrow" : "line",
          x: Math.round(bounds.x),
          y: Math.round(bounds.y),
          w: Math.round(bounds.w),
          h: Math.round(bounds.h),
          rotation: 0,
          z: 0,
          points: toLocal([a, b], { x: bounds.x, y: bounds.y }),
          color: colorRef.current,
          weight: 2,
        },
      });
      return;
    }
    dispatch({
      type: "addItem",
      item: {
        id: createId(),
        kind: "shape",
        shape: drawTool as ShapeKind,
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        w: Math.round(Math.max(8, rect.w)),
        h: Math.round(Math.max(8, rect.h)),
        rotation: 0,
        z: 0,
        fill: "none",
        stroke: colorRef.current,
        weight: 2,
      },
    });
  };

  const endInteraction = (event: ReactPointerEvent<HTMLDivElement>) => {
    const current = interaction.current;
    if (current.mode !== "none" && current.pointerId === event.pointerId) {
      const world = worldPoint(event);
      if (current.mode === "crop") {
        const item = itemsRef.current.find((candidate) => candidate.id === current.id);
        const rect = item ? worldMarqueeToLocal(item, current.origin, world) : null;
        const min = 8 / cameraRef.current.z;
        if (item && rect && rect.w >= min && rect.h >= min) {
          onCropChange({
            itemId: item.id,
            rect,
            page: item.kind === "pdf" ? item.page : undefined,
          });
        } else onCropChange(null);
        setDraft(null);
      }
      if (current.mode === "box") {
        const rect = rectFromPoints(current.origin, world);
        const min = 4 / cameraRef.current.z;
        if (rect.w >= min && rect.h >= min) {
          const hits = itemsInRect(itemsRef.current, rect);
          const ids = event.shiftKey
            ? Array.from(new Set([...selectedRef.current, ...hits.map((item) => item.id)]))
            : hits.map((item) => item.id);
          dispatch({ type: "select", ids });
        } else if (toolRef.current === "note") onCreateNote(current.origin);
        else if (toolRef.current === "text") onCreateText(current.origin);
        setBox(null);
      }
      if (current.mode === "draw") {
        commitShape(current.tool, current.origin, world, event.shiftKey);
        setShape(null);
      }
      if (current.mode === "ink") {
        commitInk(current.points);
        setInk(null);
      }
      release(containerRef.current, event.pointerId);
    }
    interaction.current = { mode: "none" };
  };

  const onResizeStart = (handle: ResizeHandle, event: ReactPointerEvent<HTMLElement>) => {
    event.stopPropagation();
    const item = itemsRef.current.find((candidate) => candidate.id === selectedIds[0]);
    if (!item || item.locked) return;
    dispatch({ type: "checkpoint" });
    capture(containerRef.current, event.pointerId);
    interaction.current = {
      mode: "resize",
      pointerId: event.pointerId,
      id: item.id,
      handle,
      start: { x: item.x, y: item.y, w: item.w, h: item.h },
      aspect: item.kind === "note" || item.kind === "text" || item.kind === "shape" ? null : item.w / item.h,
    };
  };

  const onRotateStart = (event: ReactPointerEvent<HTMLElement>) => {
    event.stopPropagation();
    const item = itemsRef.current.find((candidate) => candidate.id === selectedIds[0]);
    if (!item || item.locked) return;
    dispatch({ type: "checkpoint" });
    capture(containerRef.current, event.pointerId);
    const center = { x: item.x + item.w / 2, y: item.y + item.h / 2 };
    const world = worldPoint(event);
    interaction.current = {
      mode: "rotate",
      pointerId: event.pointerId,
      id: item.id,
      center,
      startAngle: (Math.atan2(world.y - center.y, world.x - center.x) * 180) / Math.PI,
      startRot: item.rotation || 0,
    };
  };

  const selected = board.items.filter((item) => selectedIds.includes(item.id));
  const camera = board.camera;
  const draftItem = draft ? board.items.find((item) => item.id === draft.itemId) : null;
  const cropItem = crop ? board.items.find((item) => item.id === crop.itemId) : null;
  const cursor =
    interaction.current.mode === "pan" || spacePan || tool === "pan"
      ? interaction.current.mode === "pan"
        ? "grabbing"
        : "grab"
      : tool === "region" || tool === "ink" || DRAW_TOOLS.includes(tool)
        ? "crosshair"
        : tool === "text"
          ? "text"
          : "default";

  const boxScreen = box
    ? {
        a: worldToScreen(box.a, camera),
        b: worldToScreen(box.b, camera),
      }
    : null;

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 touch-none overflow-hidden"
      style={{ cursor }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endInteraction}
      onPointerCancel={endInteraction}
      onContextMenu={(event) => {
        event.preventDefault();
        const target = event.target as HTMLElement;
        const id = target.closest<HTMLElement>("[data-item-id]")?.dataset.itemId ?? null;
        onContextMenu(localPoint(event), id);
      }}
      onDoubleClick={(event) => {
        const target = event.target as HTMLElement;
        if (target.closest("[data-item-id]")) return;
        if (toolRef.current === "select") onCreateNote(worldPoint(event));
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
        {ink
          ? ink.map((point, index) =>
              index === 0 ? null : (
                <div
                  key={index}
                  className="absolute bg-cyan"
                  style={{
                    left: Math.min(ink[index - 1].x, point.x),
                    top: Math.min(ink[index - 1].y, point.y) - 1,
                    width: Math.max(2, Math.hypot(point.x - ink[index - 1].x, point.y - ink[index - 1].y)),
                    height: 2,
                    transformOrigin: "left center",
                    transform: `rotate(${Math.atan2(point.y - ink[index - 1].y, point.x - ink[index - 1].x)}rad)`,
                  }}
                />
              ),
            )
          : null}
        {shape ? <DraftShape tool={shape.tool} a={shape.a} b={shape.b} color={strokeColor} /> : null}
      </div>

      {selected.length ? (
        <SelectionFrame
          items={selected}
          camera={camera}
          onResizeStart={onResizeStart}
          onRotateStart={onRotateStart}
        />
      ) : null}

        {boxScreen && tool === "select" ? (
        <div
          className="pointer-events-none absolute border border-dashed border-cyan/70 bg-cyan/10"
          style={{
            left: Math.min(boxScreen.a.x, boxScreen.b.x),
            top: Math.min(boxScreen.a.y, boxScreen.b.y),
            width: Math.abs(boxScreen.b.x - boxScreen.a.x),
            height: Math.abs(boxScreen.b.y - boxScreen.a.y),
          }}
        />
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

function DraftShape({
  tool,
  a,
  b,
  color,
}: {
  tool: CanvasTool;
  a: Point;
  b: Point;
  color: StrokeColor;
}) {
  const rect = rectFromPoints(a, b);
  const stroke = color === "amber" ? "#f5c16c" : color === "rose" ? "#f082a0" : "#3ee0d4";
  if (tool === "line" || tool === "arrow") {
    return (
      <svg className="pointer-events-none absolute left-0 top-0 overflow-visible" width={1} height={1}>
        <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={stroke} strokeWidth={2} />
      </svg>
    );
  }
  return (
    <div
      className="pointer-events-none absolute border border-cyan/80"
      style={{
        left: rect.x,
        top: rect.y,
        width: rect.w,
        height: rect.h,
        borderRadius: tool === "ellipse" ? 9999 : 0,
        transform: tool === "diamond" ? "rotate(45deg)" : undefined,
        transformOrigin: "center",
      }}
    />
  );
}
