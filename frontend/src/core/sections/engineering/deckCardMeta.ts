import type { PendingAction } from "@/lib/types";

/** Quote pipeline labels for deck chips (X9). */
export const QUOTE_STEP_LABELS = ["Scope", "RM", "Strategy", "MHR", "Assemble"] as const;

export type DeckCardMeta = {
  customer?: string;
  drawingNumber?: string;
  revision?: string;
  quoteStep?: string;
  verifyBlockers?: number;
  verifyWarnings?: number;
  draftTotal?: string;
  thumbnailUrl?: string;
};

function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

function asString(v: unknown): string | undefined {
  if (typeof v !== "string") return undefined;
  const t = v.trim();
  return t || undefined;
}

function asNumber(v: unknown): number | undefined {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim()) {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return undefined;
}

/** Normalize free-text step names to the X9 chip label when possible. */
export function normalizeQuoteStep(raw: unknown): string | undefined {
  const text = asString(raw);
  if (!text) return undefined;
  const key = text.toLowerCase().replace(/[^a-z]/g, "");
  const map: Record<string, string> = {
    scope: "Scope",
    rm: "RM",
    rawmaterial: "RM",
    strategy: "Strategy",
    mhr: "MHR",
    machinehour: "MHR",
    assemble: "Assemble",
    assembly: "Assemble",
  };
  if (map[key]) return map[key];
  for (const label of QUOTE_STEP_LABELS) {
    if (text.toLowerCase().includes(label.toLowerCase())) return label;
  }
  return text;
}

function verifyFromBlob(blob: Record<string, unknown>): Pick<DeckCardMeta, "verifyBlockers" | "verifyWarnings" | "draftTotal"> {
  const checks = Array.isArray(blob.checks) ? blob.checks : null;
  let blockers = asNumber(blob.blocker_count ?? blob.blockers ?? blob.blockerCount);
  let warnings = asNumber(blob.warning_count ?? blob.warnings ?? blob.warningCount);
  if (blockers == null && checks) {
    blockers = checks.filter((c) => {
      const row = asRecord(c);
      if (!row || row.pass) return false;
      const sev = asString(row.severity)?.toUpperCase() ?? "BLOCKER";
      return sev === "BLOCKER";
    }).length;
  }
  if (warnings == null && checks) {
    warnings = checks.filter((c) => {
      const row = asRecord(c);
      if (!row || row.pass) return false;
      return (asString(row.severity)?.toUpperCase() ?? "") === "WARNING";
    }).length;
  }
  const total =
    asString(blob.draft_total ?? blob.verified_total ?? blob.total_label) ??
    (asNumber(blob.draft_total_minor ?? blob.total_minor) != null
      ? String(blob.draft_total_minor ?? blob.total_minor)
      : undefined);
  return {
    verifyBlockers: blockers,
    verifyWarnings: warnings,
    draftTotal: total,
  };
}

/** Tool-owned deck fields from conversation focus / scene (no new API). */
export function deckMetaFromFocus(focus: Record<string, unknown> | undefined, _scene?: { widgets?: unknown[] }): DeckCardMeta {
  const f = focus || {};
  const extract = asRecord(f.extract);
  const verifyBlob =
    asRecord(f.quote_verify) ?? asRecord(f.last_quote_verify) ?? asRecord(f.verify) ?? asRecord(f.last_verify);
  const verify = verifyBlob ? verifyFromBlob(verifyBlob) : {};

  const thumbnailUrl =
    asString(f.thumbnail_url ?? f.thumb_url ?? f.pdf_thumbnail ?? f.thumbnailUrl ?? f.thumbUrl) ??
    asString(extract?.thumbnail_url);

  return {
    customer: asString(f.customer ?? f.customer_name ?? extract?.customer),
    drawingNumber: asString(f.drawing_number ?? f.drawing_no ?? f.drawingNumber ?? extract?.drawing_number),
    revision: asString(f.revision ?? extract?.revision),
    quoteStep: normalizeQuoteStep(f.quote_step ?? f.quoteStep ?? f.pipeline_step ?? f.step),
    thumbnailUrl,
    ...verify,
  };
}

export function pendingMatchesConversation(
  action: PendingAction,
  conv: { id: string; sessionId: string },
): boolean {
  const payload = action.payload || {};
  const cid = payload.conversation_id ?? payload.conversationId;
  if (typeof cid === "string" && cid === conv.id) return true;
  if (action.session_id && action.session_id === conv.sessionId) return true;
  const sid = payload.session_id ?? payload.sessionId;
  if (typeof sid === "string" && sid === conv.sessionId) return true;
  return false;
}

export function parkedApprovalForConversation(
  items: PendingAction[],
  parkedIds: string[],
  conv: { id: string; sessionId: string },
): PendingAction | undefined {
  const parked = new Set(parkedIds);
  return items.find((a) => parked.has(a.id) && pendingMatchesConversation(a, conv));
}
