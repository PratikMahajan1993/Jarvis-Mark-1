"use client";

import { useCallback, useSyncExternalStore } from "react";
import type { Lens } from "@/substrate/protocol";
import type { PresenceMode } from "@/substrate/protocol";

export type PanePhase = "settled" | "moving";
export type OverlayKind = "none" | "hitl" | "compose" | "prefs" | "google";
export type FocusMode = "normal" | "stage";

export type PaneState = {
  lens: Lens;
  phase: PanePhase;
  mode: PresenceMode;
  overlay: OverlayKind;
  focusMode: FocusMode;
};

type PaneListener = () => void;

const SETTLE_WATCHDOG_MS = 1400;

let paneState: PaneState = {
  lens: "watch",
  phase: "settled",
  mode: "idle",
  overlay: "none",
  focusMode: "normal",
};

const listeners = new Set<PaneListener>();
let settleTimer: ReturnType<typeof setTimeout> | null = null;
let onLensChange: ((lens: Lens) => void) | null = null;

function emit() {
  for (const l of listeners) l();
}

function scheduleSettleWatchdog() {
  if (settleTimer) clearTimeout(settleTimer);
  settleTimer = setTimeout(() => {
    settleTimer = null;
    markPaneSettled();
  }, SETTLE_WATCHDOG_MS);
}

export function getPaneState(): PaneState {
  return paneState;
}

export function subscribePane(listener: PaneListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function registerLensSideEffect(fn: (lens: Lens) => void): () => void {
  onLensChange = fn;
  return () => {
    if (onLensChange === fn) onLensChange = null;
  };
}

export function setLens(to: Lens): void {
  if (paneState.lens === to && paneState.phase === "settled") return;
  paneState = { ...paneState, lens: to, phase: "moving" };
  emit();
  onLensChange?.(to);
  scheduleSettleWatchdog();
}

export function markPaneSettled(): void {
  if (paneState.phase === "settled") return;
  paneState = { ...paneState, phase: "settled" };
  emit();
}

export function setPresenceMode(mode: PresenceMode): void {
  if (paneState.mode === mode) return;
  paneState = { ...paneState, mode };
  emit();
}

export function setOverlay(overlay: OverlayKind): void {
  if (paneState.overlay === overlay) return;
  paneState = { ...paneState, overlay };
  emit();
}

export function setFocusMode(focusMode: FocusMode): void {
  if (paneState.focusMode === focusMode) return;
  paneState = { ...paneState, focusMode };
  emit();
}

/** Hydrate lens from persisted workspace without marking a gesture (initial load). */
export function initLensFromWorkspace(lens: Lens): void {
  paneState = { ...paneState, lens, phase: "settled" };
  emit();
}

export function usePane<T>(selector: (s: PaneState) => T): T {
  const getSnapshot = useCallback(() => selector(getPaneState()), [selector]);
  return useSyncExternalStore(subscribePane, getSnapshot, getSnapshot);
}

export function useLens(): Lens {
  return usePane((s) => s.lens);
}

export function useLensSettled(): boolean {
  return usePane((s) => s.phase === "settled");
}
