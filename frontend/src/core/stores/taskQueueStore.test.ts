/** @vitest-environment jsdom */
import { beforeEach, describe, expect, it } from "vitest";
import type { PendingAction } from "@/lib/types";
import { toastStore } from "./toastStore";
import {
  markParked,
  setPendingItems,
  taskQueueStore,
} from "./taskQueueStore";

function action(partial: Partial<PendingAction> & Pick<PendingAction, "id">): PendingAction {
  return {
    kind: "email_send",
    title: partial.title ?? partial.id,
    summary: "",
    payload: {},
    status: "pending",
    ...partial,
  };
}

describe("setPendingItems session prune", () => {
  beforeEach(() => {
    localStorage.clear();
    taskQueueStore.set({ items: [], parkedIds: [] });
    toastStore.set({ items: [] });
  });

  it("drops and toasts parked ids omitted from the same session refresh", () => {
    setPendingItems([action({ id: "a1", session_id: "s1", title: "Mail A" })], "s1");
    markParked("a1");
    expect(taskQueueStore.get().parkedIds).toEqual(["a1"]);

    setPendingItems([], "s1");

    expect(taskQueueStore.get().parkedIds).toEqual([]);
    expect(taskQueueStore.get().items).toEqual([]);
    expect(toastStore.get().items.some((t) => t.message.includes("Mail A"))).toBe(true);
  });

  it("keeps parked ids that belong to a different session", () => {
    setPendingItems([action({ id: "a1", session_id: "s1", title: "Session 1" })], "s1");
    markParked("a1");
    setPendingItems([action({ id: "b1", session_id: "s2", title: "Session 2" })], "s2");
    markParked("b1");

    // Refresh s2 without b1 would prune b1; refreshing s1 must not drop b1.
    setPendingItems([action({ id: "a1", session_id: "s1" })], "s1");

    expect(taskQueueStore.get().parkedIds.sort()).toEqual(["a1", "b1"]);
    expect(taskQueueStore.get().items.map((i) => i.id).sort()).toEqual(["a1", "b1"]);
    expect(toastStore.get().items).toHaveLength(0);
  });

  it("stamps session_id on items that omit it", () => {
    setPendingItems([action({ id: "a1" })], "s9");
    expect(taskQueueStore.get().items[0]?.session_id).toBe("s9");
  });
});
