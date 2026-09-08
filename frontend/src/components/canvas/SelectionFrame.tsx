"use client";

import type { PointerEvent as ReactPointerEvent } from "react";
import { worldToScreen } from "@/lib/canvas/camera";
import { pdfPageSize } from "@/lib/canvas/pdf";
import { useCanvasActions } from "@/lib/canvas/store";
import { sizeForAspect, type CanvasCamera, type CanvasItem, type PdfItem } from "@/lib/canvas/types";

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
      {item.kind === "pdf" ? <PdfPageBar item={item} /> : null}
    </div>
  );
}

function PdfPageBar({ item }: { item: PdfItem }) {
  const { dispatch, transport } = useCanvasActions();
  const last = Math.max(1, item.pageCount || 1);
  const page = Math.min(last, Math.max(1, item.page || 1));

  const go = (next: number) => {
    const target = Math.min(last, Math.max(1, next));
    if (target === page) return;
    void (async () => {
      try {
        const geo = await pdfPageSize(item.fileId, transport.fileUrl(item.fileId), target);
        const size = sizeForAspect(item.w, item.h, geo.width / geo.height);
        dispatch({
          type: "updateItem",
          id: item.id,
          patch: {
            page: target,
            pageCount: geo.pageCount,
            naturalW: geo.width,
            naturalH: geo.height,
            w: size.w,
            h: size.h,
          },
        });
      } catch {
        dispatch({ type: "updateItem", id: item.id, patch: { page: target } });
      }
    })();
  };

  return (
    <div
      data-canvas-interactive="true"
      className="glass pointer-events-auto absolute left-1/2 top-full mt-2 flex -translate-x-1/2 items-center gap-1 rounded-full px-2 py-1"
    >
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => go(page - 1)}
        className="px-2 py-0.5 text-sm text-white/45 transition-colors hover:text-cyan disabled:opacity-30"
        aria-label="Previous page"
      >
        ‹
      </button>
      <span className="min-w-[3.5rem] text-center font-display text-sm tracking-widest text-white/50">
        {page} / {last}
      </span>
      <button
        type="button"
        disabled={page >= last}
        onClick={() => go(page + 1)}
        className="px-2 py-0.5 text-sm text-white/45 transition-colors hover:text-cyan disabled:opacity-30"
        aria-label="Next page"
      >
        ›
      </button>
    </div>
  );
}
