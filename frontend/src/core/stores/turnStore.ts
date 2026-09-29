"use client";

import { liveLog } from "@/lib/liveLog";
import {
  INITIAL_JARVIS_STATE,
  effectsFor,
  isBusy,
  jarvisReducer,
  type JarvisEvent,
  type JarvisState,
  type TurnEffect,
} from "@/lib/orchestratorFsm";
import { createStore } from "./createStore";

type TurnStoreState = { state: JarvisState };

export const turnStore = createStore<TurnStoreState>({ state: INITIAL_JARVIS_STATE });

type AnyRunner = (effect: TurnEffect) => void;
const runners = new Map<TurnEffect["kind"], Set<AnyRunner>>();

/** Register a runner for one effect kind (substrate mode, scroll, autosave). */
export function onTurnEffect<K extends TurnEffect["kind"]>(
  kind: K,
  runner: (effect: Extract<TurnEffect, { kind: K }>) => void,
): () => void {
  let set = runners.get(kind);
  if (!set) {
    set = new Set();
    runners.set(kind, set);
  }
  const wrapped = runner as AnyRunner;
  set.add(wrapped);
  return () => set.delete(wrapped);
}

function runEffects(effects: TurnEffect[]) {
  for (const effect of effects) {
    const set = runners.get(effect.kind);
    if (!set) continue;
    for (const run of set) {
      try {
        run(effect);
      } catch (err) {
        console.error("[turnStore] effect failed", effect.kind, err);
      }
    }
  }
}

let sessionForLog = "default";
export function setTurnLogSession(sessionId: string) {
  sessionForLog = sessionId;
}

export function getTurn(): JarvisState {
  return turnStore.get().state;
}

/**
 * Apply one event synchronously. Returns the new state if it took effect, or
 * null when the reducer refused it (same reference). Effects run after commit.
 */
export function dispatchTurn(event: JarvisEvent): JarvisState | null {
  const prev = turnStore.get().state;
  const next = jarvisReducer(prev, event);
  const effects = effectsFor(prev, next, event);
  if (next !== prev) {
    if (prev.mode !== next.mode) {
      liveLog(
        "fsm",
        { event: event.type, from_mode: prev.mode, to_mode: next.mode, refused: false },
        { sessionId: sessionForLog },
      );
    }
    turnStore.set({ state: next });
  }
  runEffects(effects);
  return next === prev ? null : next;
}

export function useTurn(): JarvisState {
  return turnStore.use((s) => s.state);
}

export function useTurnBusy(): boolean {
  return turnStore.use((s) => isBusy(s.state));
}
