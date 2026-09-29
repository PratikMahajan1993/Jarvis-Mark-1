/** @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  OVERLAY_MS,
  dismissOverlay,
  mailPriority,
  notifyDrawingClosed,
  pushNotification,
  resetNotificationStore,
  notificationStore,
} from "./notificationStore";

describe("notificationStore", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    resetNotificationStore();
  });
  afterEach(() => {
    resetNotificationStore();
    vi.useRealTimers();
  });

  it("shows an overlay then archives after 5s", () => {
    pushNotification({ title: "Drawing closed", priority: "low", kind: "desk" });
    expect(notificationStore.get().overlayId).toBeTruthy();
    expect(notificationStore.get().items).toHaveLength(1);
    vi.advanceTimersByTime(OVERLAY_MS);
    expect(notificationStore.get().overlayId).toBeNull();
    expect(notificationStore.get().items).toHaveLength(1);
  });

  it("dismissOverlay clears the toast without dropping the archive", () => {
    pushNotification({ title: "Parked", priority: "high", kind: "hitl", actionId: "a1" });
    dismissOverlay();
    expect(notificationStore.get().overlayId).toBeNull();
    expect(notificationStore.get().items[0]?.actionId).toBe("a1");
  });

  it("dedupes drawing-closed bursts", () => {
    notifyDrawingClosed();
    notifyDrawingClosed();
    expect(notificationStore.get().items).toHaveLength(1);
  });

  it("rates promotional mail medium and customer mail high", () => {
    expect(mailPriority("deals@shop.com", "50% off newsletter")).toBe("medium");
    expect(mailPriority("stores@srujansolutions.com", "RFQ: pinion housing")).toBe("high");
  });
});
