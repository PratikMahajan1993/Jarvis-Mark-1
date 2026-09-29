"use client";

import type { PendingAction } from "@/lib/types";
import { createStore } from "./createStore";

const PARKED_KEY = "jarvis.parkedApprovals";

export type TaskQueueState = {
  /** Server pending actions with status `pending` (the dock's source of truth). */
  items: PendingAction[];
  /** Ids the owner parked with Later. Client-side, survives refresh (X8). */
  parkedIds: string[];
};

function loadParked(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = JSON.parse(localStorage.getItem(PARKED_KEY) || "[]");
    return Array.isArray(raw) ? raw.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

function persistParked(ids: string[]) {
  try {
    localStorage.setItem(PARKED_KEY, JSON.stringify(ids));
  } catch {
    /* ignore */
  }
}

export const taskQueueStore = createStore<TaskQueueState>({ items: [], parkedIds: [] });

export function hydrateParked() {
  taskQueueStore.set({ parkedIds: loadParked() });
}

export function getParkedIds(): string[] {
  return taskQueueStore.get().parkedIds;
}

export function isParked(id: string): boolean {
  return taskQueueStore.get().parkedIds.includes(id);
}

export function markParked(id: string) {
  const ids = taskQueueStore.get().parkedIds;
  if (ids.includes(id)) return;
  const next = [...ids, id];
  taskQueueStore.set({ parkedIds: next });
  persistParked(next);
}

export function unmarkParked(id: string) {
  const ids = taskQueueStore.get().parkedIds;
  if (!ids.includes(id)) return;
  const next = ids.filter((v) => v !== id);
  taskQueueStore.set({ parkedIds: next });
  persistParked(next);
}

/** Replace the pending set; parked ids for rows that left the server are dropped. */
export function setPendingItems(items: PendingAction[]) {
  const open = items.filter((a) => String(a.status || "pending").toLowerCase() === "pending");
  const live = new Set(open.map((a) => a.id));
  const parked = taskQueueStore.get().parkedIds.filter((id) => live.has(id));
  taskQueueStore.set({ items: open, parkedIds: parked });
  persistParked(parked);
}

/** First pending action that is not parked. */
export function firstUnparked(items: PendingAction[]): PendingAction | null {
  const parked = taskQueueStore.get().parkedIds;
  return items.find((a) => !parked.includes(a.id)) ?? null;
}

export function useTaskQueue<T>(selector: (s: TaskQueueState) => T): T {
  return taskQueueStore.use(selector);
}

export function upsertPending(action: PendingAction) {
  const items = taskQueueStore.get().items;
  taskQueueStore.set({ items: items.some((a) => a.id === action.id) ? items : [...items, action] });
}

export function removePending(id: string) {
  const { items } = taskQueueStore.get();
  taskQueueStore.set({ items: items.filter((a) => a.id !== id) });
  unmarkParked(id);
}
