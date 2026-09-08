"use client";

import Link from "next/link";
import { clampZoom, fitToItems, zoomAt } from "@/lib/canvas/camera";
import { useCanvasActions, useCanvasState } from "@/lib/canvas/store";
import type { CanvasTool } from "@/lib/canvas/types";

function ToolButton({
  label,
  onClick,
  title,
  active,
}: {
  label: string;
  onClick: () => void;
  title?: string;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`px-3 py-1.5 text-sm transition-colors ${
        active ? "text-cyan" : "text-white/45 hover:text-cyan"
      }`}
    >
      {label}
    </button>
  );
}

export function CanvasToolbar({
  viewport,
  tool,
  onAddNote,
  onTool,
}: {
  viewport: { width: number; height: number };
  tool: CanvasTool;
  onAddNote: () => void;
  onTool: (tool: CanvasTool) => void;
}) {
  const { board, status, dirty, error } = useCanvasState();
  const { dispatch } = useCanvasActions();
  const camera = board.camera;
  const center = { x: viewport.width / 2, y: viewport.height / 2 };

  const setCamera = (next: typeof camera) => dispatch({ type: "setCamera", camera: next });

  return (
    <div className="glass pointer-events-auto flex items-center gap-1 rounded-full px-3 py-1">
      <Link href="/" className="px-3 py-1.5 text-sm text-white/30 transition-colors hover:text-cyan">
        Jarvis
      </Link>
      <span className="h-4 w-px bg-white/10" />
      <ToolButton label="Note" title="Add a note (or double-click the board)" onClick={onAddNote} />
      <ToolButton
        label="Region"
        title="Drag a rectangle on a drawing or image (R)"
        active={tool === "region"}
        onClick={() => onTool(tool === "region" ? "select" : "region")}
      />
      <span className="h-4 w-px bg-white/10" />
      <ToolButton label="−" title="Zoom out" onClick={() => setCamera(zoomAt(camera, center, camera.z / 1.25))} />
      <button
        type="button"
        onClick={() => setCamera(zoomAt(camera, center, 1))}
        title="Reset zoom"
        className="min-w-[3.5rem] px-2 py-1.5 font-display text-sm tracking-widest text-white/50 hover:text-cyan"
      >
        {Math.round(clampZoom(camera.z) * 100)}%
      </button>
      <ToolButton label="+" title="Zoom in" onClick={() => setCamera(zoomAt(camera, center, camera.z * 1.25))} />
      <span className="h-4 w-px bg-white/10" />
      <ToolButton
        label="Fit"
        title="Frame everything"
        onClick={() => setCamera(fitToItems(board.items, viewport.width, viewport.height))}
      />
      <span className="h-4 w-px bg-white/10" />
      <span className="px-3 text-[11px] tracking-wide text-white/25">
        {error || (status === "loading" ? "Opening…" : dirty ? "Saving…" : "Saved")}
      </span>
    </div>
  );
}
