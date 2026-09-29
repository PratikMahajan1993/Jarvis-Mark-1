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

  it("falls back to created_at + 30 minutes", () => {
    const created = Date.parse("2026-01-01T10:00:00.000Z");
    const action = { ...base, created_at: "2026-01-01T10:00:00.000Z" } as PendingAction;
    expect(pendingExpiryAtMs(action)).toBe(created + DEFAULT_PARKED_TTL_MS);
    expect(isParkedApprovalExpired(action, created + DEFAULT_PARKED_TTL_MS - 1)).toBe(false);
    expect(isParkedApprovalExpired(action, created + DEFAULT_PARKED_TTL_MS)).toBe(true);
  });

  it("uses parkedAt when no server timestamps", () => {
    const parkedAt = 1_700_000_000_000;
    expect(pendingExpiryAtMs(base, parkedAt)).toBe(parkedAt + DEFAULT_PARKED_TTL_MS);
  });
});
