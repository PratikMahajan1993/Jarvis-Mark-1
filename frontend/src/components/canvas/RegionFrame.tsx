"use client";

import { worldToScreen } from "@/lib/canvas/camera";
import type { CanvasCamera, CanvasItem, ItemLocalRect } from "@/lib/canvas/types";

export function RegionFrame({
  item,
  region,
  camera,
  draft,
  busy,
  onPlace,
  onDownload,
  onCancel,
}: {
  item: CanvasItem;
  region: ItemLocalRect;
  camera: CanvasCamera;
  draft?: boolean;
  busy?: boolean;
  onPlace?: () => void;
  onDownload?: () => void;
  onCancel?: () => void;
}) {
  const origin = worldToScreen({ x: item.x + region.x, y: item.y + region.y }, camera);
  const width = region.w * camera.z;
  const height = region.h * camera.z;
  return (
    <div
      className="pointer-events-none absolute z-20 border border-dashed border-cyan/80"
      style={{ left: origin.x, top: origin.y, width, height }}
    >
      <div className="absolute inset-0 bg-cyan/10" />
      {!draft && onPlace && onDownload && onCancel ? (
        <div
          data-canvas-interactive="true"
          className="glass pointer-events-auto absolute left-1/2 top-full mt-2 flex -translate-x-1/2 items-center gap-1 rounded-full px-2 py-1"
        >
          <button
            type="button"
            disabled={busy}
            onClick={onPlace}
            className="px-3 py-1 text-sm text-white/45 transition-colors hover:text-cyan disabled:opacity-40"
          >
            {busy ? "Working…" : "Place"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onDownload}
            className="px-3 py-1 text-sm text-white/45 transition-colors hover:text-cyan disabled:opacity-40"
          >
            Download
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onCancel}
            className="px-3 py-1 text-sm text-white/35 transition-colors hover:text-cyan disabled:opacity-40"
          >
            Cancel
          </button>
        </div>
      ) : null}
    </div>
  );
}
