"use client";

import { createStore } from "./createStore";

export type NotificationPriority = "high" | "medium" | "low";
export type NotificationKind = "hitl" | "mail" | "desk" | "system";

export type DeskNotification = {
  id: string;
  title: string;
  body: string;
  priority: NotificationPriority;
  kind: NotificationKind;
  createdAt: number;
  read: boolean;
  /** Parked HITL — click reopens Authorize; never decides from here. */
  actionId?: string;
};

export type NotificationState = {
  items: DeskNotification[];
  overlayId: string | null;
  panelOpen: boolean;
};

export const OVERLAY_MS = 5000;
const MAX_ITEMS = 40;

export const notificationStore = createStore<NotificationState>({
  items: [],
  overlayId: null,
  panelOpen: false,
});

let overlayTimer: ReturnType<typeof setTimeout> | null = null;
let overlaySeq = 0;

function clearOverlayTimer() {
  if (overlayTimer !== null) {
    clearTimeout(overlayTimer);
    overlayTimer = null;
  }
}

export function mailPriority(from: string, subject: string): NotificationPriority {
  const blob = `${from} ${subject}`;
  if (/\b(unsubscribe|newsletter|promo|promotional|offer|% off|win\b|deal of|sale\b)\b/i.test(blob)) {
    return "medium";
  }
  return "high";
}

export function pushNotification(
  input: {
    id?: string;
    title: string;
    body?: string;
    priority: NotificationPriority;
    kind: NotificationKind;
    actionId?: string;
    overlay?: boolean;
  },
): string {
  const id = input.id ?? `n-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const prev = notificationStore.get().items;
  const existing = prev.find((n) => n.id === id);
  if (existing && input.overlay === false) return existing.id;
  const item: DeskNotification = {
    id,
    title: input.title,
    body: input.body ?? "",
    priority: input.priority,
    kind: input.kind,
    createdAt: existing?.createdAt ?? Date.now(),
    read: false,
    actionId: input.actionId,
  };
  const items = [item, ...prev.filter((n) => n.id !== id)].slice(0, MAX_ITEMS);
  const showOverlay = input.overlay !== false;
  notificationStore.set({
    items,
    overlayId: showOverlay ? id : notificationStore.get().overlayId,
  });
  if (showOverlay) {
    clearOverlayTimer();
    const seq = ++overlaySeq;
    overlayTimer = setTimeout(() => {
      if (seq !== overlaySeq) return;
      const cur = notificationStore.get();
      if (cur.overlayId === id) notificationStore.set({ overlayId: null });
      overlayTimer = null;
    }, OVERLAY_MS);
  }
  return id;
}

export function notifyDrawingClosed() {
  const last = notificationStore.get().items[0];
  if (last?.kind === "desk" && last.title === "Drawing closed" && Date.now() - last.createdAt < 2000) {
    return last.id;
  }
  return pushNotification({
    title: "Drawing closed",
    body: "The drawing on the bench was closed.",
    priority: "low",
    kind: "desk",
  });
}

export function dismissOverlay() {
  overlaySeq += 1;
  clearOverlayTimer();
  notificationStore.set({ overlayId: null });
}

export function togglePanel(open?: boolean) {
  const next = open ?? !notificationStore.get().panelOpen;
  notificationStore.set({ panelOpen: next });
  if (next) {
    notificationStore.set({
      items: notificationStore.get().items.map((n) => ({ ...n, read: true })),
    });
  }
}

export function markRead(id: string) {
  notificationStore.set({
    items: notificationStore.get().items.map((n) => (n.id === id ? { ...n, read: true } : n)),
  });
}

export function removeNotification(id: string) {
  const cur = notificationStore.get();
  notificationStore.set({
    items: cur.items.filter((n) => n.id !== id),
    overlayId: cur.overlayId === id ? null : cur.overlayId,
  });
}

export function unreadCount(items: DeskNotification[] = notificationStore.get().items): number {
  return items.filter((n) => !n.read).length;
}

export function overlayItem(state: NotificationState = notificationStore.get()): DeskNotification | null {
  if (!state.overlayId) return null;
  return state.items.find((n) => n.id === state.overlayId) ?? null;
}

export function useNotificationStore<T>(selector: (s: NotificationState) => T): T {
  return notificationStore.use(selector);
}

/** Reset timers between tests. */
export function resetNotificationStore() {
  overlaySeq += 1;
  clearOverlayTimer();
  notificationStore.set({ items: [], overlayId: null, panelOpen: false });
}
