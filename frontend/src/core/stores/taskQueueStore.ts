"use client";

import type { PendingAction } from "@/lib/types";
import { isParkedApprovalExpired } from "./parkedExpiry";
import { pushToast } from "./toastStore";
import { createStore } from "./createStore";

const PARKED_KEY = "jarvis.parkedApprovals";
const PARKED_AT_KEY = "jarvis.parkedApprovalsAt";

export type TaskQueueState = {
  /** Server pending actions with status `pending` (the dock's source of truth). */
  items: PendingAction[];
  /** Ids the owner parked with Later. Client-side, survives refresh (X8). */
  parkedIds: string[];
};

type ExpiryHandlers = {
  /** Called after a parked chip is removed for client TTL — open Authorize if idle. */
  onTtlExpired?: (action: PendingAction) => void;
};

let expiryHandlers: ExpiryHandlers = {};

function loadParked(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = JSON.parse(localStorage.getItem(PARKED_KEY) || "[]");
    return Array.isArray(raw) ? raw.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

function loadParkedAt(): Record<string, number> {
  if (typeof window === "undefined") return {};
  try {
    const raw = JSON.parse(localStorage.getItem(PARKED_AT_KEY) || "{}");
    if (!raw || typeof raw !== "object") return {};
    const out: Record<string, number> = {};
    for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
      if (typeof v === "number" && Number.isFinite(v)) out[k] = v;
    }
    return out;
  } catch {
    return {};
  }
}

function persistParked(ids: string[]) {
  try {
    localStorage.setItem(PARKED_KEY, JSON.stringify(ids));
  } catch {
    /* ignore */
  }
}

function persistParkedAt(map: Record<string, number>) {
  try {
    localStorage.setItem(PARKED_AT_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

function clearParkedAt(id: string) {
  const map = loadParkedAt();
  if (!(id in map)) return;
  delete map[id];
  persistParkedAt(map);
}

function toastExpiredApproval(action: PendingAction | undefined, reason: "server" | "ttl") {
  const title = action?.title?.trim();
  const detail =
    reason === "server"
      ? "Server removed this approval — it is no longer pending."
      : "Parked approval expired — it needs a decision.";
  pushToast(title ? `${title}: ${detail}` : detail, `approval-expired-${action?.id ?? reason}-${Date.now()}`);
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
  const at = loadParkedAt();
  at[id] = Date.now();
  persistParkedAt(at);
}

export function unmarkParked(id: string) {
  const ids = taskQueueStore.get().parkedIds;
  if (!ids.includes(id)) return;
  const next = ids.filter((v) => v !== id);
  taskQueueStore.set({ parkedIds: next });
  persistParked(next);
  clearParkedAt(id);
}

/**
 * Merge one session's `/api/pending` list into the dock.
 * Only parked ids that belong to this session and are omitted from the refresh
 * are treated as server-expired.
 */
export function setPendingItems(items: PendingAction[], sessionId: string) {
  const open = items
    .filter((a) => String(a.status || "pending").toLowerCase() === "pending")
    .map((a) => (a.session_id ? a : { ...a, session_id: sessionId }));
  const live = new Set(open.map((a) => a.id));
  const prev = taskQueueStore.get();

  const keptParked: string[] = [];
  const dropped: string[] = [];
  for (const id of prev.parkedIds) {
    if (live.has(id)) {
      keptParked.push(id);
      continue;
    }
    const prevItem = prev.items.find((a) => a.id === id);
    if (prevItem?.session_id === sessionId) {
      dropped.push(id);
    } else {
      // Other session (or unknown) — do not treat omission as expiry.
      keptParked.push(id);
    }
  }

  for (const id of dropped) {
    toastExpiredApproval(prev.items.find((a) => a.id === id), "server");
    clearParkedAt(id);
  }

  const otherItems = prev.items.filter((a) => a.session_id !== sessionId && !live.has(a.id));
  const nextItems = [...otherItems, ...open];
  taskQueueStore.set({ items: nextItems, parkedIds: keptParked });
  persistParked(keptParked);
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

/** Client TTL for parked chips still on the server (X8). Returns expired actions. */
export function reconcileExpiredParkedApprovals(nowMs = Date.now()): PendingAction[] {
  const { items, parkedIds } = taskQueueStore.get();
  if (!parkedIds.length) return [];
  const atMap = loadParkedAt();
  const expired: PendingAction[] = [];
  for (const id of [...parkedIds]) {
    const action = items.find((a) => a.id === id);
    if (!action) continue;
    if (!isParkedApprovalExpired(action, nowMs, atMap[id])) continue;
    toastExpiredApproval(action, "ttl");
    unmarkParked(id);
    expired.push(action);
    expiryHandlers.onTtlExpired?.(action);
  }
  return expired;
}

let expiryTimer: ReturnType<typeof setInterval> | null = null;

/** Idempotent interval — started from TaskDock. */
export function startParkedExpiryWatcher(handlers?: ExpiryHandlers) {
  if (handlers) {
    expiryHandlers = { ...expiryHandlers, ...handlers };
  }
  if (typeof window === "undefined" || expiryTimer) return;
  reconcileExpiredParkedApprovals();
  expiryTimer = setInterval(() => reconcileExpiredParkedApprovals(), 30_000);
}
