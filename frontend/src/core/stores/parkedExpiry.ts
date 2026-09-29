import type { PendingAction } from "@/lib/types";

export const DEFAULT_PARKED_TTL_MS = 30 * 60 * 1000;

type LoosePending = PendingAction & {
  expires_at?: string;
  expiresAt?: string;
};

function parseTime(v: unknown): number | undefined {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim()) {
    const t = Date.parse(v);
    if (Number.isFinite(t)) return t;
  }
  return undefined;
}

/**
 * Absolute expiry instant (ms) for a parked approval.
 * Explicit server `expires_at` wins; otherwise the clock is parkedAt + 30 min.
 */
export function pendingExpiryAtMs(action: PendingAction, parkedAtMs?: number): number {
  const loose = action as LoosePending;
  const payload = action.payload || {};
  const explicit =
    parseTime(loose.expires_at ?? loose.expiresAt) ??
    parseTime(payload.expires_at ?? payload.expiresAt ?? payload.expiry);
  if (explicit != null) return explicit;

  const base = parkedAtMs ?? Date.now();
  return base + DEFAULT_PARKED_TTL_MS;
}

export function isParkedApprovalExpired(action: PendingAction, nowMs: number, parkedAtMs?: number): boolean {
  return nowMs >= pendingExpiryAtMs(action, parkedAtMs);
}
