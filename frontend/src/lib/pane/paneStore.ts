"use client";

import { useCallback, useSyncExternalStore } from "react";
import type { Lens } from "@/substrate/protocol";
import type { PresenceMode } from "@/substrate/protocol";
import { LENS_LAYOUT, PANEL_IDS } from "./lenses";
import { playLens } from "./conductor";

export type PanePhase = "settled" | "moving";
export type OverlayKind = "none" | "hitl" | "compose" | "prefs" | "google";
export type FocusMode = "normal" | "stage";

export type PaneState = {
  lens: Lens;
  /** UI / heavy panel reads — frozen while `phase === "moving"`. */
  displayLens: Lens;
  phase: PanePhase;
  mode: PresenceMode;
  overlay: OverlayKind;
  focusMode: FocusMode;
};

type PaneListener = () => void;

const SETTLE_WATCHDOG_MS = 1400;

let paneState: PaneState = {
  lens: "watch",
  displayLens: "watch",
  phase: "settled",
  mode: "idle",
  overlay: "none",
  focusMode: "normal",
};

let playLensRaf = 0;
let emitLensRaf = 0;
let queuedLens: Lens | null = null;

const listeners = new Set<PaneListener>();
let settleTimer: ReturnType<typeof setTimeout> | null = null;
let workerReady = true;
let heroReady = true;
let heroPanelsPending = 0;
let pendingLens: Lens | null = null;

function emit() {
  for (const l of listeners) l();
}

function resetGestureGates(lens: Lens) {
  pendingLens = lens;
  workerReady = false;
  heroPanelsPending = PANEL_IDS.filter((id) => LENS_LAYOUT[lens][id].depth === 0).length;
  heroReady = heroPanelsPending === 0;
}

function tryMarkSettled() {
  if (paneState.phase === "settled") return;
  if (workerReady && heroReady) {
    markPaneSettled();
  }
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

function schedulePlayLens(to: Lens) {
  if (playLensRaf) cancelAnimationFrame(playLensRaf);
  playLensRaf = requestAnimationFrame(() => {
    playLensRaf = 0;
    playLens(to);
  });
}

function applyLensGesture(to: Lens) {
  resetGestureGates(to);
  paneState = { ...paneState, lens: to, phase: "moving" };
  emit();
  schedulePlayLens(to);
  scheduleSettleWatchdog();
}

function retargetLensGesture(to: Lens) {
  resetGestureGates(to);
  paneState = { ...paneState, lens: to, phase: "moving" };
  schedulePlayLens(to);
  scheduleSettleWatchdog();
}

export function setLens(to: Lens): void {
  if (paneState.lens === to && paneState.phase === "settled") return;
  if (paneState.phase === "moving") {
    retargetLensGesture(to);
    return;
  }
  queuedLens = to;
  if (emitLensRaf) return;
  emitLensRaf = requestAnimationFrame(() => {
    emitLensRaf = 0;
    const target = queuedLens;
    queuedLens = null;
    if (!target) return;
    if (paneState.lens === target && paneState.phase === "settled") return;
    applyLensGesture(target);
  });
}

export function markPaneSettled(): void {
  if (paneState.phase === "settled") return;
  if (settleTimer) {
    clearTimeout(settleTimer);
    settleTimer = null;
  }
  pendingLens = null;
  paneState = { ...paneState, phase: "settled", displayLens: paneState.lens };
  emit();
}

export function markWorkerSettled(lens: Lens): void {
  if (pendingLens !== null && lens !== pendingLens) return;
  workerReady = true;
  tryMarkSettled();
}

export function markHeroPanelSettled(): void {
  if (heroPanelsPending > 0) heroPanelsPending -= 1;
  if (heroPanelsPending === 0) {
    heroReady = true;
    tryMarkSettled();
  }
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
  paneState = { ...paneState, lens, displayLens: lens, phase: "settled" };
  pendingLens = null;
  workerReady = true;
  heroReady = true;
  emit();
}

export function usePane<T>(selector: (s: PaneState) => T): T {
  const getSnapshot = useCallback(() => selector(getPaneState()), [selector]);
  return useSyncExternalStore(subscribePane, getSnapshot, getSnapshot);
}

export function useLens(): Lens {
  return usePane((s) => s.lens);
}

export function useDisplayLens(): Lens {
  return usePane((s) => s.displayLens);
}
