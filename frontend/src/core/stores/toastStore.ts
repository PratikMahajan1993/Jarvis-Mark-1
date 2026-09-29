"use client";

import { createStore } from "./createStore";

export type ToastItem = {
  id: string;
  message: string;
  createdAt: number;
};

export type ToastState = {
  items: ToastItem[];
};

export const toastStore = createStore<ToastState>({ items: [] });

export function pushToast(message: string, id?: string) {
  const toastId = id ?? `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const items = toastStore.get().items;
  if (items.some((t) => t.id === toastId)) return toastId;
  toastStore.set({
    items: [{ id: toastId, message, createdAt: Date.now() }, ...items].slice(0, 5),
  });
  return toastId;
}

export function dismissToast(id: string) {
  toastStore.set({ items: toastStore.get().items.filter((t) => t.id !== id) });
}

export function useToastStore<T>(selector: (s: ToastState) => T): T {
  return toastStore.use(selector);
}
