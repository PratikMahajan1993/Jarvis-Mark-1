"use client";

import { useCallback, useEffect, useMemo } from "react";
import type { MailAttachment, Scene } from "@/lib/types";
import {
  conversationToAttachment,
  isSavedLocal,
  sceneAttachments,
} from "@/lib/viewerMatch";
import { DrawingViewer } from "@/components/DrawingViewer";
import { playFocus } from "@/lib/pane/conductor";
import { setFocusMode, useDisplayLens, usePane } from "@/lib/pane/paneStore";
import type { QuoteSheetRow } from "@/lib/pane/quoteContract";
import { CalloutPins } from "./CalloutPins";

/** Match LENS_SUBSTRATE.bench centre — keep the mat clear so the substrate pilot can show. */
const PILOT_HOLE =
  "radial-gradient(circle at 4.5% 7.5%, transparent 0 7.5%, #000 9%)";

function isViewableDrawing(att: MailAttachment): boolean {
  if (!isSavedLocal(att)) return false;
  const name = (att.local_name || att.filename || "").toLowerCase();
  const mime = (att.mime || "").toLowerCase();
  if (name.endsWith(".pdf") || mime.includes("pdf")) return true;
  if (/\.(png|jpe?g|gif|webp|bmp|tiff?|svg)$/i.test(name)) return true;
  if (mime.startsWith("image/")) return true;
  return Boolean(att.readable);
}

function pickDrawingAttachment(
  scene: Scene,
  focus?: Record<string, unknown>,
): MailAttachment | null {
  const fromFocus = conversationToAttachment(focus);
  if (fromFocus && isViewableDrawing(fromFocus)) return fromFocus;
  for (const att of sceneAttachments(scene)) {
    if (isViewableDrawing(att)) return att;
  }
  return null;
}

function enterFocus() {
  setFocusMode("stage");
  playFocus(true);
}

function leaveFocus() {
  setFocusMode("normal");
  playFocus(false);
}

function toggleFocus(current: "normal" | "stage") {
  if (current === "stage") leaveFocus();
  else enterFocus();
}

export function DrawingStage({
  scene,
  focus,
  pinRows = [],
}: {
  scene: Scene;
  focus?: Record<string, unknown>;
  /** Ledger rows that may carry callout regions. */
  pinRows?: QuoteSheetRow[];
}) {
  const drawing = useMemo(() => pickDrawingAttachment(scene, focus), [scene, focus]);
  const displayLens = useDisplayLens();
  const focusMode = usePane((s) => s.focusMode);
  const benchActive = displayLens === "bench";

  const onDoubleClick = useCallback(() => {
    if (!benchActive) return;
    toggleFocus(focusMode);
  }, [benchActive, focusMode]);

  useEffect(() => {
    if (!benchActive) return;
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || target?.isContentEditable) return;

      if (e.key === "Escape" && focusMode === "stage") {
        e.preventDefault();
        leaveFocus();
        return;
      }
      if (e.key === "f" || e.key === "F") {
        if (e.metaKey || e.ctrlKey || e.altKey) return;
        e.preventDefault();
        toggleFocus(focusMode);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [benchActive, focusMode]);

  return (
    <div
      className="relative h-full min-h-0 w-full overflow-hidden"
      data-drawing-stage
      onDoubleClick={onDoubleClick}
    >
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background: "var(--mat, oklch(16% 0.004 240))",
          boxShadow: "inset 0 0 0 8px transparent, inset 0 0 24px rgba(0,0,0,0.45)",
          WebkitMaskImage: PILOT_HOLE,
          maskImage: PILOT_HOLE,
        }}
      />

      <div className="relative z-[1] flex h-full min-h-0 flex-col p-2">
        <div className="relative min-h-0 flex-1 overflow-hidden rounded-xl border border-[color:var(--border)]/50 bg-black/25">
          {drawing ? (
            <DrawingViewer
              embedded
              attachment={drawing}
              onClose={() => undefined}
              onWhisper={() => undefined}
            />
          ) : (
            <div className="flex h-full min-h-[200px] flex-col items-center justify-center gap-2 px-6 text-center">
              <p className="font-display text-lg text-[color:var(--fg)]/75">
                No drawing on the bench.
              </p>
              <p className="max-w-sm font-mono text-[10px] uppercase tracking-[0.16em] text-[color:var(--muted)]/65">
                Drop a PDF, say quote the attachment, or pick from the inbox.
              </p>
            </div>
          )}
          <CalloutPins rows={pinRows} page={1} />
        </div>
      </div>
    </div>
  );
}
