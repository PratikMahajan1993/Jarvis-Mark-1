"use client";

import { useCallback, useRef, useSyncExternalStore } from "react";
import { getPaneState, subscribePane, usePane } from "./paneStore";

export function useLensSettled(): boolean {
  return usePane((s) => s.phase === "settled");
}

/**
 * Returns `value` while settled; holds the last settled snapshot during `moving`
 * so subscribers do not re-render when a gesture starts.
 */
export function useValueWhenSettled<T>(value: T): T {
  const valueRef = useRef(value);
  valueRef.current = value;
  const heldRef = useRef(value);

  const getSnapshot = useCallback(() => {
    if (getPaneState().phase === "settled") {
      heldRef.current = valueRef.current;
    }
    return heldRef.current;
  }, []);

  return useSyncExternalStore(subscribePane, getSnapshot, getSnapshot);
}

/** @deprecated use useValueWhenSettled */
export function useLensGatedValue<T>(value: T): T {
  return useValueWhenSettled(value);
}

/** Imperative read for callbacks outside React render. */
export function isLensSettled(): boolean {
  return getPaneState().phase === "settled";
}

export function subscribeLensSettled(listener: () => void): () => void {
  let prev = getPaneState().phase === "settled";
  return subscribePane(() => {
    const next = getPaneState().phase === "settled";
    if (next === prev) return;
    prev = next;
    listener();
  });
}
