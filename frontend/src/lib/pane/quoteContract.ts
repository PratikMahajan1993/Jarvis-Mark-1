/** Quote sheet + quote_verify shapes for Bench (Phase 4b). Types only — no React. */

/** ● tool-sourced — jarvis_quote_* / MHR floor / RM table */
export type QuoteProvenanceTool = "tool";
/** ◉ owner-confirmed */
export type QuoteProvenanceConfirmed = "confirmed";
/** ◐ analyzer proposed, not confirmed */
export type QuoteProvenancePending = "pending";
/** ○ no source — amount must be null, never a guessed number */
export type QuoteProvenanceMissing = "missing";

export type QuoteProvenance =
  | QuoteProvenanceTool
  | QuoteProvenanceConfirmed
  | QuoteProvenancePending
  | QuoteProvenanceMissing;

export type QuoteRowGroup = "raw" | "machining" | "outsource" | "tooling" | "margin";

export type QuoteSheetRow = {
  label: string;
  group: QuoteRowGroup;
  /** Piece quantity when the row is qty-priced; use `basis` instead for hour/rate lines. */
  qty?: number | null;
  /** Mono basis string (hours × floor, kg × rate, etc.). */
  basis?: string | null;
  /** Minor units in `currency`; null when provenance is `missing`. */
  amount: number | null;
  currency: string;
  provenance: QuoteProvenance;
};

export type QuoteVerifySeverity = "BLOCKER" | "WARN";

/** One check from `verify_quote` / `_check` in backend `quote.py`. */
export type QuoteVerifyCheck = {
  id: string;
  pass: boolean;
  evidence: string;
  severity: QuoteVerifySeverity;
  source: string;
};

export type QuoteVerifyChecklistItem = {
  label: string;
  pass: boolean;
  evidence: string;
  severity: QuoteVerifySeverity;
};

export type QuoteVerifyScene = {
  title: string;
  widgets: Array<{
    type: "checklist";
    title: string;
    items: QuoteVerifyChecklistItem[];
  }>;
};

/** Return shape of `_finalize_verify` — any failing BLOCKER sets `stop`. */
export type QuoteVerifyResult = {
  ok: true;
  passed: boolean;
  failed_count: number;
  warn_count: number;
  stop: boolean;
  verdict: "pass" | "block";
  checks: QuoteVerifyCheck[];
  scene: QuoteVerifyScene;
};

export type QuoteFixtureDocument = {
  meta: {
    rfqId: string;
    customer: string;
    part: string;
    material: string;
    orderQty: number;
    due: string;
    currency: string;
  };
  rows: QuoteSheetRow[];
  verify: QuoteVerifyResult;
  /** Explicit list of check ids with `pass: false` (BLOCKER + WARN) for Authorize gating UX. */
  failingCheckIds: string[];
};

function blockerFailureCount(result: QuoteVerifyResult): number {
  return result.checks.filter(
    (c) => !c.pass && (c.severity ?? "BLOCKER") === "BLOCKER",
  ).length;
}

/** True when more than two BLOCKER checks failed — Authorize card disabled (UI mirrors backend `stop`). */
export function authorizeDisabled(result: QuoteVerifyResult): boolean {
  return blockerFailureCount(result) > 2;
}
