"use client";

import { motion, useReducedMotion } from "motion/react";
import { useCallback, useEffect, useMemo } from "react";
import type { MailAttachment, Scene } from "@/lib/types";
import {
  conversationToAttachment,
  isSavedLocal,
  sceneAttachments,
} from "@/lib/viewerMatch";
import { DrawingViewer } from "@/components/DrawingViewer";
import type { QuoteSheetRow } from "@/lib/pane/quoteContract";
import { SPRING } from "@/lib/pane/springs";
import { CalloutPins } from "./CalloutPins";

export type StageFocusMode = "normal" | "stage";

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

export function DrawingStage({
  scene,
  focus,
  pinRows = [],
  active,
  focusMode,
  onFocusModeChange,
  morphLayoutId,
  highlight = false,
}: {
  scene: Scene;
  focus?: Record<string, unknown>;
  /** Ledger rows that may carry callout regions. */
  pinRows?: QuoteSheetRow[];
  /** Engineering is the active section: F / Escape / double-click toggle focus. */
  active: boolean;
  focusMode: StageFocusMode;
  onFocusModeChange: (mode: StageFocusMode) => void;
  /** X9 shared-layout morph from the front deck card (omit under reduced motion). */
  morphLayoutId?: string;
  /** Brief highlight after a deck drop opens the PDF. */
  highlight?: boolean;
}) {
  const reduced = useReducedMotion();
  const drawing = useMemo(() => pickDrawingAttachment(scene, focus), [scene, focus]);
  const layoutId = reduced ? undefined : morphLayoutId;

  const toggleFocus = useCallback(
    (current: StageFocusMode) => onFocusModeChange(current === "stage" ? "normal" : "stage"),
    [onFocusModeChange],
  );
  const leaveFocus = useCallback(() => onFocusModeChange("normal"), [onFocusModeChange]);

  const onDoubleClick = useCallback(() => {
    if (!active) return;
    toggleFocus(focusMode);
  }, [active, focusMode, toggleFocus]);

  useEffect(() => {
    if (!active) return;
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
  }, [active, focusMode, toggleFocus, leaveFocus]);

  return (
    <motion.div
      layoutId={layoutId}
      transition={SPRING.pane}
      className={[
        "relative h-full min-h-0 w-full overflow-hidden",
        highlight ? "ring-2 ring-[color:var(--accent)]/70 ring-offset-2 ring-offset-transparent" : "",
      ].join(" ")}
      data-drawing-stage
      data-drop-highlight={highlight ? "true" : undefined}
      onDoubleClick={onDoubleClick}
    >
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background: "var(--mat, oklch(16% 0.004 240))",
          boxShadow: "inset 0 0 0 8px transparent, inset 0 0 24px rgba(0,0,0,0.45)",
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
    </motion.div>
  );
}
