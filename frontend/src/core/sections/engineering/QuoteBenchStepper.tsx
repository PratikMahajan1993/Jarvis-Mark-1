"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  QUOTE_BENCH_STEPS,
  type DrawingCellsMap,
  type QuoteBenchStepId,
  canShowMoveToWhatsApp,
} from "./quoteBench";

const CELL_LABELS: Record<string, string> = {
  revision: "Revision",
  quantity: "Quantity",
  material: "Material",
  heat_treat: "Heat treat",
  finish: "Finish",
  gdt: "GD&T",
};

const HARD = ["revision", "quantity", "material"] as const;
const SOFT = ["heat_treat", "finish", "gdt"] as const;

function DrawingCellsEditor({
  sessionId,
  cells,
  onChange,
  mode,
}: {
  sessionId: string;
  cells: DrawingCellsMap;
  onChange: () => void;
  mode: "confirm" | "assumptions";
}) {
  const keys = mode === "confirm" ? HARD : SOFT;

  const run = async (action: string, cell: string, value = "") => {
    await api.quoteDrawingCellsAction(sessionId, action, { cell, value });
    onChange();
  };

  return (
    <div className="space-y-2" data-quote-cells={mode}>
      {keys.map((key) => {
        const cell = cells[key] ?? { state: "empty", value: "" };
        return (
          <div
            key={key}
            className="flex flex-wrap items-center gap-2 rounded border border-[color:var(--border)]/60 px-2 py-1.5"
          >
            <span className="w-24 font-mono text-[9px] uppercase tracking-[0.14em] text-[color:var(--muted)]">
              {CELL_LABELS[key]}
            </span>
            <span className="min-w-0 flex-1 font-mono text-[10px] text-[color:var(--fg)]">
              {cell.value || "—"}
            </span>
            <span className="font-mono text-[9px] uppercase text-[color:var(--muted)]">{cell.state}</span>
            {mode === "confirm" ? (
              <>
                <button
                  type="button"
                  className="rounded border border-[color:var(--border)] px-1.5 py-0.5 font-mono text-[9px] uppercase"
                  onClick={() => {
                    const next = window.prompt(`Correct ${CELL_LABELS[key]}`, cell.value);
                    if (next != null) void run("correct", key, next);
                  }}
                >
                  Correct
                </button>
                <button
                  type="button"
                  className="rounded border border-[color:var(--accent)]/50 px-1.5 py-0.5 font-mono text-[9px] uppercase text-[color:var(--accent)]"
                  disabled={!cell.value.trim()}
                  onClick={() => void run("confirm", key, cell.value)}
                >
                  Accept
                </button>
              </>
            ) : (
              <button
                type="button"
                className="rounded border border-[color:var(--accent)]/40 px-1.5 py-0.5 font-mono text-[9px] uppercase text-[color:var(--accent)]"
                disabled={!cell.value.trim()}
                onClick={() => void run("assumption", key, cell.value)}
              >
                Tag assumption
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function QuoteBenchStepper({
  sessionId,
  activeStep,
  onStepChange,
  hasDrawing,
}: {
  sessionId: string;
  activeStep: QuoteBenchStepId;
  onStepChange: (step: QuoteBenchStepId) => void;
  hasDrawing: boolean;
}) {
  const [cells, setCells] = useState<DrawingCellsMap | null>(null);
  const [handoffReady, setHandoffReady] = useState(false);
  const [handoffNote, setHandoffNote] = useState("");
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!hasDrawing) return;
    const result = await api.quoteDrawingCells(sessionId);
    if (result.ok && result.cells) setCells(result.cells as DrawingCellsMap);
    else if (result.ok && !result.cells_initialized) setCells(null);
    setHandoffReady(Boolean(result.handoff_ready));
  }, [hasDrawing, sessionId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!hasDrawing || cells) return;
    void api.quoteDrawingCellsAction(sessionId, "init").then(() => refresh());
  }, [cells, hasDrawing, refresh, sessionId]);

  const showWhatsApp = canShowMoveToWhatsApp(cells) && !handoffReady;

  const onHandoff = async () => {
    setLoading(true);
    setHandoffNote("");
    try {
      const result = await api.quoteDrawingCellsAction(sessionId, "handoff_ready");
      if (!result.ok) {
        setHandoffNote(result.error || "Could not mark handoff ready");
        return;
      }
      setHandoffReady(true);
      setHandoffNote("Handoff ready — WhatsApp transport is not wired in this slice.");
    } finally {
      setLoading(false);
    }
  };

  if (!hasDrawing) return null;

  return (
    <div className="shrink-0 space-y-2 border-b border-[color:var(--border)]/40 pb-2" data-quote-bench>
      <div
        className="flex gap-1 overflow-x-auto overscroll-x-contain pb-1"
        role="tablist"
        aria-label="Quote bench steps"
      >
        {QUOTE_BENCH_STEPS.map((step) => (
          <button
            key={step.id}
            type="button"
            role="tab"
            aria-selected={activeStep === step.id}
            className={[
              "shrink-0 rounded-full border px-2 py-1 font-mono text-[9px] uppercase tracking-[0.12em]",
              activeStep === step.id
                ? "border-[color:var(--accent)] text-[color:var(--accent)]"
                : "border-[color:var(--border)] text-[color:var(--muted)] hover:text-[color:var(--fg)]",
            ].join(" ")}
            onClick={() => onStepChange(step.id)}
          >
            {step.label}
          </button>
        ))}
      </div>

      {activeStep === "confirm" && cells ? (
        <DrawingCellsEditor sessionId={sessionId} cells={cells} onChange={() => void refresh()} mode="confirm" />
      ) : null}
      {activeStep === "assumptions" && cells ? (
        <DrawingCellsEditor sessionId={sessionId} cells={cells} onChange={() => void refresh()} mode="assumptions" />
      ) : null}

      {showWhatsApp ? (
        <button
          type="button"
          className="rounded-full border border-[color:var(--accent)]/45 bg-[color:var(--accent)]/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--accent)]"
          disabled={loading}
          onClick={() => void onHandoff()}
          data-move-whatsapp
        >
          Move to WhatsApp
        </button>
      ) : null}
      {handoffReady ? (
        <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-[color:var(--accent)]">Handoff ready</p>
      ) : null}
      {handoffNote ? <p className="font-mono text-[10px] text-[color:var(--muted)]">{handoffNote}</p> : null}
    </div>
  );
}
