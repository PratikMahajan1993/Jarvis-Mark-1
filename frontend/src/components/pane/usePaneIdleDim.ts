"use client";

import { useEffect, type RefObject } from "react";
import { idleWaitMs, setPaneIdleDim } from "@/lib/pane/ambient";
import type { OrchestratorMode } from "@/lib/orchestrator";

function isSpeechActive(mode: OrchestratorMode, listening: boolean): boolean {
  return listening || mode === "listening" || mode === "busy";
}

/** After idle timeout, dim pane brightness and cap substrate at 30 fps. */
export function usePaneIdleDim(
  rootRef: RefObject<HTMLElement | null>,
  orchestratorMode: OrchestratorMode,
  listening: boolean,
): void {
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    let lastInput = performance.now();
    let dimmed = false;
    const waitMs = idleWaitMs();

    const bump = () => {
      lastInput = performance.now();
      if (dimmed) {
        dimmed = false;
        setPaneIdleDim(root, false);
      }
    };

    const onPointer = () => bump();
    const onKey = () => bump();
    window.addEventListener("pointermove", onPointer, { passive: true });
    window.addEventListener("keydown", onKey);

    const tick = window.setInterval(() => {
      if (isSpeechActive(orchestratorMode, listening)) {
        lastInput = performance.now();
        if (dimmed) {
          dimmed = false;
          setPaneIdleDim(root, false);
        }
        return;
      }
      if (!dimmed && performance.now() - lastInput >= waitMs) {
        dimmed = true;
        setPaneIdleDim(root, true);
      }
    }, 250);

    return () => {
      window.removeEventListener("pointermove", onPointer);
      window.removeEventListener("keydown", onKey);
      window.clearInterval(tick);
      if (dimmed) setPaneIdleDim(root, false);
    };
  }, [rootRef, orchestratorMode, listening]);
}
