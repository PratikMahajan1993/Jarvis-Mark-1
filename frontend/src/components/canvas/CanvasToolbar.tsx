"use client";

import Link from "next/link";
import { clampZoom, fitToItems, zoomAt } from "@/lib/canvas/camera";
import { useCanvasActions, useCanvasState } from "@/lib/canvas/store";

function ToolButton({
  label,
  onClick,
  title,
  active,
  disabled,
}: {
  label: string;
  onClick: () => void;
  title?: string;
  active?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      disabled={disabled}
      className={`px-3 py-1.5 text-sm transition-colors disabled:opacity-30 ${
        active ? "text-cyan" : "text-white/45 hover:text-cyan"
      }`}
    >
      {label}
    </button>
  );
}

export function CanvasToolbar({
  viewport,
  snap,
  onAddNote,
  onToggleSnap,
  onExport,
}: {
  viewport: { width: number; height: number };
  snap: boolean;
  onAddNote: () => void;
  onToggleSnap: () => void;
  onExport: () => void;
}) {
  const { board, status, dirty, error, past, future, selectedIds } = useCanvasState();
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
      <ToolButton label="Note" title="Add a note (N)" onClick={onAddNote} />
      <ToolButton
        label="Undo"
        title="Undo (⌘Z)"
        disabled={!past.length}
        onClick={() => dispatch({ type: "undo" })}
      />
      <ToolButton
        label="Redo"
        title="Redo (⌘⇧Z)"
        disabled={!future.length}
        onClick={() => dispatch({ type: "redo" })}
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
        title="Frame everything (1)"
        onClick={() => setCamera(fitToItems(board.items, viewport.width, viewport.height))}
      />
      <ToolButton
        label="Snap"
        title="Snap to grid (G)"
        active={snap}
        onClick={onToggleSnap}
      />
      <ToolButton
        label="Export"
        title="Export selection or board (⌘E)"
        disabled={!board.items.length}
        onClick={onExport}
      />
      <span className="h-4 w-px bg-white/10" />
      <span className="px-3 text-[11px] tracking-wide text-white/25">
        {error ||
          (status === "loading"
            ? "Opening…"
            : dirty
              ? "Saving…"
              : selectedIds.length > 1
                ? `${selectedIds.length} selected`
                : "Saved")}
      </span>
    </div>
  );
}
