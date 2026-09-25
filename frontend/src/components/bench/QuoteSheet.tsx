"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { motion } from "motion/react";
import type { Scene } from "@/lib/types";
import fixtureDoc from "@/lib/pane/fixtures/quote-fixture.json";
import {
  authorizeDisabled,
  type QuoteFixtureDocument,
  type QuoteRowGroup,
  type QuoteSheetRow,
  type QuoteVerifyResult,
} from "@/lib/pane/quoteContract";
import { usePane } from "@/lib/pane/paneStore";
import { SPRING } from "@/lib/pane/springs";
import { CustomerVisionConsent } from "@/components/orchestrator/engineering/CustomerVisionConsent";
import { FactConfirmChips } from "@/components/orchestrator/engineering/FactConfirmChips";
import { ToolChangeField } from "@/components/orchestrator/engineering/ToolChangeField";
import { VarianceCard } from "@/components/orchestrator/engineering/VarianceCard";
import { VisionBenchQueue } from "@/components/orchestrator/engineering/VisionBenchQueue";
import { MHRAttestationPanel } from "./MHRAttestationPanel";
import { OperationEditor } from "./OperationEditor";
import { ProofStrip } from "./ProofStrip";
import { RMTracker } from "./RMTracker";
import { SheetRow } from "./SheetRow";
import { pinsFromRows } from "./CalloutPins";

type SheetTab = "sheet" | "strategy" | "vision";

const GROUP_ORDER: QuoteRowGroup[] = ["raw", "machining", "outsource", "tooling", "margin"];

const GROUP_LABEL: Record<QuoteRowGroup, string> = {
  raw: "Raw material",
  machining: "Machining",
  outsource: "Outsource",
  tooling: "Fixtures/tooling",
  margin: "Margin",
};

const FIXTURE = fixtureDoc as QuoteFixtureDocument;

function scenePricedRows(scene: Scene): QuoteSheetRow[] | null {
  for (const w of scene.widgets || []) {
    if (w.type !== "quote") continue;
    const rows = (w as { pricedRows?: QuoteSheetRow[] }).pricedRows;
    if (Array.isArray(rows) && rows.length > 0) return rows;
  }
  return null;
}

function resolveDocument(scene: Scene): QuoteFixtureDocument {
  const live = scenePricedRows(scene);
  if (live) {
    return {
      ...FIXTURE,
      rows: live,
      meta: {
        ...FIXTURE.meta,
        rfqId: scene.title?.trim() || FIXTURE.meta.rfqId,
        part: scene.subtitle?.trim() || FIXTURE.meta.part,
      },
    };
  }
  return FIXTURE;
}

function formatTotal(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: currency || "INR",
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return String(amount);
  }
}

function pinIndexForRow(row: QuoteSheetRow, pinned: ReturnType<typeof pinsFromRows>): number | null {
  if (!row.region) return null;
  const found = pinned.find(
    (p) =>
      p.region.page === row.region!.page &&
      p.region.x === row.region!.x &&
      p.region.y === row.region!.y &&
      p.label === row.label,
  );
  return found ? found.index : null;
}

export function QuoteSheet({
  scene,
  entityType = "",
  entityId = "",
  hasDrawing = true,
  sessionId = "default",
}: {
  scene: Scene;
  entityType?: string;
  entityId?: string;
  /** False when the Engineering stage has no local drawing. */
  hasDrawing?: boolean;
  sessionId?: string;
}) {
  const [tab, setTab] = useState<SheetTab>("sheet");
  const [findNote, setFindNote] = useState("");
  const [finding, setFinding] = useState(false);
  const [scope, setScope] = useState<"" | "labour" | "with_material">("");
  const [scopeNote, setScopeNote] = useState("");
  const [liveVerify, setLiveVerify] = useState<QuoteVerifyResult | null>(null);
  const focusMode = usePane((s) => s.focusMode);
  const focused = focusMode === "stage";

  const doc = useMemo(() => resolveDocument(scene), [scene]);

  useEffect(() => {
    let cancelled = false;
    void api.quoteScope(sessionId, doc.meta.customer).then((result) => {
      if (cancelled) return;
      if (result.ok && (result.scope === "labour" || result.scope === "with_material")) {
        setScope(result.scope);
        setScopeNote(result.source === "customer" ? "Customer default" : "");
        return;
      }
      setScope("");
      setScopeNote(result.message || "Labour-only or with material?");
    }).catch(() => {
      if (!cancelled) setScopeNote("Labour-only or with material?");
    });
    return () => {
      cancelled = true;
    };
  }, [sessionId, doc.meta.customer]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void api
        .verifyQuote(sessionId)
        .then((result) => setLiveVerify(result))
        .catch(() => setLiveVerify(null));
    }, 500);
    return () => window.clearTimeout(handle);
  }, [sessionId, doc.rows]);
  const pinned = useMemo(() => pinsFromRows(doc.rows), [doc.rows]);

  const grouped = useMemo(() => {
    const map = new Map<QuoteRowGroup, QuoteSheetRow[]>();
    for (const g of GROUP_ORDER) map.set(g, []);
    for (const row of doc.rows) {
      const list = map.get(row.group) ?? [];
      list.push(row);
      map.set(row.group, list);
    }
    return GROUP_ORDER.map((g) => ({ group: g, rows: map.get(g) ?? [] })).filter(
      (b) => b.rows.length > 0,
    );
  }, [doc.rows]);

  const total = useMemo(() => {
    let sum = 0;
    let any = false;
    for (const row of doc.rows) {
      if (row.amount == null) continue;
      sum += row.amount;
      any = true;
    }
    return any ? sum : null;
  }, [doc.rows]);

  const verify = liveVerify ?? doc.verify;
  const isFixture = !scenePricedRows(scene);
  const authOff = verify.stop || authorizeDisabled(verify) || isFixture;
  const failingIds = liveVerify
    ? liveVerify.checks.filter((c) => !c.pass && c.severity !== "WARN").map((c) => c.id)
    : doc.failingCheckIds?.length > 0
      ? doc.failingCheckIds
      : verify.checks.filter((c) => !c.pass).map((c) => c.id);

  if (focused) {
    return (
      <div className="flex h-full min-h-0 flex-col justify-between gap-2 p-2" data-quote-sheet data-focus-tab>
        <div className="min-w-0">
          <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-[color:var(--muted)]/70">
            {doc.meta.rfqId}
          </p>
          <p className="font-display text-lg tabular-nums text-[color:var(--fg)]">
            {total != null ? formatTotal(total, doc.meta.currency) : "—"}
          </p>
        </div>
        <ProofStrip verify={verify} />
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden p-2" data-quote-sheet>
      <header className="shrink-0 border-b border-[color:var(--border)]/50 pb-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[color:var(--muted)]/70">
          {doc.meta.rfqId} · {doc.meta.customer}
        </p>
        <h2 className="font-display text-lg leading-snug text-[color:var(--fg)]">
          {doc.meta.part}
        </h2>
        <p className="mt-0.5 font-mono text-[10px] text-[color:var(--muted)]">
          {doc.meta.material} · qty {doc.meta.orderQty} · due {doc.meta.due}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2" role="group" aria-label="Quote scope">
          {(
            [
              ["labour", "Labour"],
              ["with_material", "With material"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              aria-pressed={scope === id}
              className={[
                "rounded border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em]",
                scope === id
                  ? "border-[color:var(--accent)] text-[color:var(--accent)]"
                  : "border-[color:var(--border)] text-[color:var(--fg)] hover:border-[color:var(--accent)]",
              ].join(" ")}
              onClick={() => {
                setScope(id);
                setScopeNote("");
                void api.quoteScope(sessionId, doc.meta.customer, id).then((result) => {
                  if (!result.ok) setScopeNote(result.message || "Labour-only or with material?");
                });
              }}
            >
              {label}
            </button>
          ))}
          {scopeNote ? (
            <p className="font-mono text-[10px] text-[color:var(--muted)]" data-quote-scope-note>
              {scopeNote}
            </p>
          ) : null}
        </div>
        {!hasDrawing ? (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="rounded border border-[color:var(--border)] px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--fg)] hover:border-[color:var(--accent)] disabled:opacity-50"
              disabled={finding}
              onClick={() => {
                setFinding(true);
                setFindNote("");
                void api
                  .findQuoteDrawing(sessionId)
                  .then((result) => {
                    if (result.ok && result.filename) {
                      setFindNote(`Drawing is ${result.filename}.`);
                      return;
                    }
                    const names = (result.candidates || [])
                      .map((row) => row.filename)
                      .filter(Boolean)
                      .join(", ");
                    setFindNote(names ? `${result.message || "Which drawing?"} ${names}` : result.message || "Which drawing — inbox attachment, file on desk, or photo?");
                  })
                  .catch(() => setFindNote("Could not look up a drawing."))
                  .finally(() => setFinding(false));
              }}
            >
              {finding ? "Finding…" : "Find Drawing"}
            </button>
            {findNote ? (
              <p className="font-mono text-[10px] text-[color:var(--muted)]" data-find-drawing-note>
                {findNote}
              </p>
            ) : null}
          </div>
        ) : null}
        <div
          className="relative mt-2 flex gap-3 font-mono text-[10px] uppercase tracking-[0.16em] text-[color:var(--muted)]"
          role="tablist"
          aria-label="Quote sheet sections"
        >
          {(
            [
              ["sheet", "Sheet"],
              ["strategy", "Strategy"],
              ["vision", "Vision"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={[
                "relative pb-1 transition-colors",
                tab === id ? "text-[color:var(--accent)]" : "hover:text-[color:var(--fg)]",
              ].join(" ")}
              onClick={() => setTab(id)}
            >
              {label}
              {tab === id ? (
                <motion.span
                  layoutId="quote-sheet-tab"
                  className="absolute inset-x-0 -bottom-px h-px bg-[color:var(--accent)]"
                  transition={SPRING.chip}
                />
              ) : null}
            </button>
          ))}
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto py-2">
        {tab === "sheet" ? (
          <div className="space-y-3">
            {grouped.map(({ group, rows }) => (
              <section key={group}>
                <h3 className="mb-1 font-mono text-[9px] uppercase tracking-[0.18em] text-[color:var(--muted)]/75">
                  {GROUP_LABEL[group]}
                </h3>
                {rows.map((row, i) => (
                  <SheetRow
                    key={`${group}-${i}-${row.label}`}
                    row={row}
                    pinIndex={pinIndexForRow(row, pinned)}
                  />
                ))}
              </section>
            ))}
          </div>
        ) : null}
        {tab === "strategy" ? (
          <div className="flex flex-col gap-3">
            <RMTracker sessionId={sessionId} />
            <OperationEditor sessionId={sessionId} />
            <MHRAttestationPanel />
            <VarianceCard />
            <ToolChangeField />
          </div>
        ) : null}
        {tab === "vision" ? (
          <div className="flex flex-col gap-3">
            <VisionBenchQueue />
            <CustomerVisionConsent />
            <FactConfirmChips entityType={entityType} entityId={entityId} />
          </div>
        ) : null}
      </div>

      <footer className="shrink-0 space-y-2 border-t border-[color:var(--border)]/50 pt-2">
        <div className="flex items-baseline justify-between gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-[color:var(--muted)]">
            Total
          </span>
          <span className="font-display text-[1.4rem] leading-none tabular-nums text-[color:var(--fg)]">
            {total != null ? formatTotal(total, doc.meta.currency) : "—"}
          </span>
        </div>
        <ProofStrip verify={verify} />
        {authOff && failingIds.length ? (
          <p className="font-mono text-[10px] leading-snug text-[color:oklch(78%_0.16_25)]">
            Failing: {failingIds.join(", ")}
          </p>
        ) : null}
        <div className="flex gap-2 relative">
          <button
            type="button"
            className="orch-btn orch-btn-primary flex-1"
            disabled={authOff}
            onClick={() => {
              /* Bench fixture Authorize ?" no mail / quote_send / jarvis_quote_build */
            }}
          >
            Authorize
          </button>
          <button
            type="button"
            className="orch-btn orch-btn-ghost flex-1"
            disabled={isFixture}
            onClick={() => {
              /* Bench fixture Reject ?" local UI only */
            }}
          >
            Reject
          </button>
          {isFixture && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-[1px] rounded-md pointer-events-none">
              <span className="font-mono text-[9px] uppercase tracking-widest text-[color:var(--muted)]">Preview - Not connected</span>
            </div>
          )}
        </div>
      </footer>
    </div>
  );
}

/** Rows used by DrawingStage pins — same document resolution as the sheet. */
export function quoteSheetRowsForScene(scene: Scene): QuoteSheetRow[] {
  return resolveDocument(scene).rows;
}
