"use client";

import type { PointerEvent as ReactPointerEvent } from "react";
import { worldToScreen } from "@/lib/canvas/camera";
import type { CanvasCamera, CanvasItem } from "@/lib/canvas/types";

export type ResizeHandle = "nw" | "ne" | "sw" | "se";

const HANDLES: Array<{ id: ResizeHandle; className: string; cursor: string }> = [
  { id: "nw", className: "-left-1.5 -top-1.5", cursor: "nwse-resize" },
  { id: "ne", className: "-right-1.5 -top-1.5", cursor: "nesw-resize" },
  { id: "sw", className: "-bottom-1.5 -left-1.5", cursor: "nesw-resize" },
  { id: "se", className: "-bottom-1.5 -right-1.5", cursor: "nwse-resize" },
];

/**
 * Drawn in screen space rather than inside the scaled world layer, so the
 * outline and handles keep the same pixel size at any zoom.
 */
export function SelectionFrame({
  item,
  camera,
  onResizeStart,
}: {
  item: CanvasItem;
  camera: CanvasCamera;
  onResizeStart: (handle: ResizeHandle, event: ReactPointerEvent<HTMLElement>) => void;
}) {
  const origin = worldToScreen({ x: item.x, y: item.y }, camera);
  return (
    <div
      className="pointer-events-none absolute z-10 border border-cyan/70"
      style={{
        left: origin.x,
        top: origin.y,
        width: item.w * camera.z,
        height: item.h * camera.z,
      }}
    >
      {HANDLES.map((handle) => (
        <button
          key={handle.id}
          type="button"
          aria-label={`Resize ${handle.id}`}
          onPointerDown={(event) => onResizeStart(handle.id, event)}
          style={{ cursor: handle.cursor }}
          className={`pointer-events-auto absolute h-3 w-3 rounded-sm border border-cyan bg-ink ${handle.className}`}
        />
      ))}
    </div>
  );
}
