"use client";

import { useSyncExternalStore } from "react";

export type Store<S> = {
  get: () => S;
  set: (patch: Partial<S> | ((prev: S) => Partial<S>)) => void;
  subscribe: (listener: () => void) => () => void;
  use: <T>(selector: (s: S) => T) => T;
};

/** Minimal external store (the paneStore pattern). No new state library. */
export function createStore<S extends object>(initial: S): Store<S> {
  let state = initial;
  const listeners = new Set<() => void>();
  const get = () => state;
  const set: Store<S>["set"] = (patch) => {
    const partial = typeof patch === "function" ? patch(state) : patch;
    let changed = false;
    for (const key of Object.keys(partial) as (keyof S)[]) {
      if (!Object.is(state[key], partial[key])) {
        changed = true;
        break;
      }
    }
    if (!changed) return;
    state = { ...state, ...partial };
    for (const l of listeners) l();
  };
  const subscribe = (listener: () => void) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  };
  function use<T>(selector: (s: S) => T): T {
    return useSyncExternalStore(
      subscribe,
      () => selector(state),
      () => selector(initial),
    );
  }
  return { get, set, subscribe, use };
}
