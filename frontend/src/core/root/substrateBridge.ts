"use client";

import { useSyncExternalStore } from "react";
import type { SubstrateHandle } from "@/substrate/createSubstrate";
import type { SubstrateIn, SubstrateOut } from "@/substrate/protocol";

export type SubstrateBridgeState = {
  ready: boolean;
  contextLost: boolean;
  settled: boolean;
  transport: "worker" | "inline" | null;
  stats: Extract<SubstrateOut, { type: "stats" }> | null;
};

export type JarvisSubstrateGlobal = SubstrateBridgeState & {
  latest: SubstrateOut | null;
  /** Forward SubstrateIn (e.g. a quality override) from the console or headless tooling. */
  post?: (msg: SubstrateIn) => void;
};

declare global {
  interface Window {
    __JARVIS_SUBSTRATE__?: JarvisSubstrateGlobal;
  }
}

type ReplayType = Exclude<SubstrateIn["type"], "init" | "resize" | "pointer">;

const REPLAY_ORDER: ReplayType[] = [
  "sections",
  "orb",
  "mode",
  "level",
  "gather",
  "route",
  "visibility",
  "reducedMotion",
  "quality",
];

let handle: SubstrateHandle | null = null;
const lastByType = new Map<SubstrateIn["type"], SubstrateIn>();
const listeners = new Set<() => void>();
const outListeners = new Set<(msg: SubstrateOut) => void>();
let state: SubstrateBridgeState = {
  ready: false,
  contextLost: false,
  settled: false,
  transport: null,
  stats: null,
};

function emit() {
  for (const l of listeners) l();
}

function publishGlobal(latest: SubstrateOut | null) {
  if (typeof window === "undefined") return;
  window.__JARVIS_SUBSTRATE__ = {
    ...state,
    latest,
    post: (msg) => postSubstrate(msg),
  };
}

/**
 * Post to the single substrate. The latest message of each kind is kept and
 * replayed when a (re)mounted engine attaches, so callers never wait on boot order.
 */
export function postSubstrate(msg: SubstrateIn) {
  if (msg.type !== "init" && msg.type !== "resize" && msg.type !== "pointer") {
    lastByType.set(msg.type, msg);
  }
  if (msg.type === "init") return;
  handle?.post(msg);
}

export function lastPosted<T extends SubstrateIn["type"]>(type: T): Extract<SubstrateIn, { type: T }> | undefined {
  return lastByType.get(type) as Extract<SubstrateIn, { type: T }> | undefined;
}

export function attachSubstrate(next: SubstrateHandle, transport: "worker" | "inline") {
  handle = next;
  state = { ...state, transport, ready: false, contextLost: false, settled: false };
  for (const type of REPLAY_ORDER) {
    const msg = lastByType.get(type);
    if (msg) next.post(msg);
  }
  publishGlobal(null);
  emit();
}

export function detachSubstrate(prev: SubstrateHandle) {
  if (handle !== prev) return;
  handle = null;
  state = { ...state, ready: false, settled: false };
  emit();
}

export function receiveSubstrate(msg: SubstrateOut) {
  if (msg.type === "ready") state = { ...state, ready: true, contextLost: false };
  else if (msg.type === "contextLost") state = { ...state, contextLost: true, ready: false };
  else if (msg.type === "settled") state = { ...state, settled: true };
  else if (msg.type === "stats") state = { ...state, stats: msg };
  publishGlobal(msg);
  for (const l of outListeners) l(msg);
  if (msg.type !== "stats") emit();
}

export function onSubstrateOut(listener: (msg: SubstrateOut) => void): () => void {
  outListeners.add(listener);
  return () => outListeners.delete(listener);
}

export function getSubstrateState(): SubstrateBridgeState {
  return state;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useSubstrateState(): SubstrateBridgeState {
  return useSyncExternalStore(subscribe, getSubstrateState, getSubstrateState);
}
