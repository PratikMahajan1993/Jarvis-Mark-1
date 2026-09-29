import { describe, expect, it } from "vitest";
import type { PendingAction } from "@/lib/types";
import { DEFAULT_PARKED_TTL_MS, isParkedApprovalExpired, pendingExpiryAtMs } from "./parkedExpiry";

const base: PendingAction = {
  id: "a1",
  kind: "email_send",
  title: "Send quote",
  summary: "",
  payload: {},
};

describe("parkedExpiry", () => {
  it("uses explicit expires_at when present", () => {
    const action = { ...base, expires_at: "2026-01-01T12:00:00.000Z" } as PendingAction;
    expect(pendingExpiryAtMs(action)).toBe(Date.parse("2026-01-01T12:00:00.000Z"));
    expect(isParkedApprovalExpired(action, Date.parse("2026-01-01T12:00:01.000Z"))).toBe(true);
  });

  it("ignores created_at and clocks from parkedAt + 30 minutes", () => {
    const created = Date.parse("2026-01-01T10:00:00.000Z");
    const parkedAt = Date.parse("2026-01-01T11:45:00.000Z");
    const action = { ...base, created_at: "2026-01-01T10:00:00.000Z" } as PendingAction;
    expect(pendingExpiryAtMs(action, parkedAt)).toBe(parkedAt + DEFAULT_PARKED_TTL_MS);
    expect(pendingExpiryAtMs(action, parkedAt)).not.toBe(created + DEFAULT_PARKED_TTL_MS);
    expect(isParkedApprovalExpired(action, parkedAt + DEFAULT_PARKED_TTL_MS - 1, parkedAt)).toBe(false);
    expect(isParkedApprovalExpired(action, parkedAt + DEFAULT_PARKED_TTL_MS, parkedAt)).toBe(true);
  });

  it("uses parkedAt when no server expires_at", () => {
    const parkedAt = 1_700_000_000_000;
    expect(pendingExpiryAtMs(base, parkedAt)).toBe(parkedAt + DEFAULT_PARKED_TTL_MS);
  });

  it("explicit expires_at still wins over parkedAt", () => {
    const parkedAt = Date.parse("2026-01-01T11:00:00.000Z");
    const action = { ...base, expires_at: "2026-01-01T12:00:00.000Z" } as PendingAction;
    expect(pendingExpiryAtMs(action, parkedAt)).toBe(Date.parse("2026-01-01T12:00:00.000Z"));
  });
});
