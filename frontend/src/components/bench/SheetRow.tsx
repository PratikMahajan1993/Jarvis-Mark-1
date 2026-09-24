"use client";

import { useEffect, useRef } from "react";
import type { QuoteProvenance, QuoteSheetRow } from "@/lib/pane/quoteContract";
import { clearBenchHighlight, setBenchHighlight } from "./highlight";

const GLYPH: Record<QuoteProvenance, string> = {
  tool: "●",
  confirmed: "◉",
  pending: "◐",
  missing: "○",
};

function formatAmount(amount: number | null, currency: string, provenance: QuoteProvenance): string {
  if (provenance === "missing" || amount === null) return "—";
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

export function SheetRow({
  row,
  pinIndex,
}: {
  row: QuoteSheetRow;
  /** Index among rows that carry a region; null when this row has no pin. */
  pinIndex: number | null;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const pending = row.provenance === "pending";
  const missing = row.provenance === "missing";
  const amount = formatAmount(row.amount, row.currency, row.provenance);
  const basis =
    row.basis?.trim() ||
    (row.qty != null ? `qty ${row.qty}` : null);

  useEffect(() => {
    const el = ref.current;
    if (!el || pinIndex == null) return;
    const enter = () => setBenchHighlight(pinIndex);
    const leave = () => clearBenchHighlight();
    el.addEventListener("mouseenter", enter);
    el.addEventListener("mouseleave", leave);
    return () => {
      el.removeEventListener("mouseenter", enter);
      el.removeEventListener("mouseleave", leave);
    };
  }, [pinIndex]);

  return (
    <div
      ref={ref}
      className={[
        "bench-sheet-row group flex h-10 items-center gap-2 border-b border-[color:var(--border)]/40 px-1 transition-[transform,box-shadow] duration-150",
        pending ? "text-[color:oklch(78%_0.12_75)]" : "",
        missing ? "text-[color:var(--muted)]" : "text-[color:var(--fg)]",
      ]
        .filter(Boolean)
        .join(" ")}
      data-bench-row={pinIndex != null ? String(pinIndex) : undefined}
    >
      <span
        className={[
          "w-4 shrink-0 text-center text-sm leading-none",
          row.provenance === "confirmed" ? "text-[color:var(--accent)]" : "",
          pending ? "text-amber-300/90" : "",
          missing ? "text-[color:var(--muted)]/70" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        aria-label={row.provenance}
      >
        {GLYPH[row.provenance]}
      </span>
      <div className="min-w-0 flex-1">
        <p
          className={["truncate text-[13px] leading-tight", pending ? "italic" : ""]
            .filter(Boolean)
            .join(" ")}
          style={
            pending
              ? {
                  textDecorationLine: "underline",
                  textDecorationStyle: "dashed",
                  textDecorationColor: "oklch(78% 0.12 75 / 0.7)",
                  textUnderlineOffset: "3px",
                }
              : undefined
          }
        >
          {row.label}
        </p>
        {basis ? (
          <p className="truncate font-mono text-[10px] text-[color:var(--muted)]/70">{basis}</p>
        ) : null}
      </div>
      <span
        className={[
          "shrink-0 font-mono text-[12px] tabular-nums",
          pending ? "italic" : "",
          missing ? "text-[color:var(--muted)]/80" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        style={
          pending
            ? {
                textDecorationLine: "underline",
                textDecorationStyle: "dashed",
                textDecorationColor: "oklch(78% 0.12 75 / 0.7)",
                textUnderlineOffset: "3px",
              }
            : undefined
        }
      >
        {amount}
      </span>
    </div>
  );
}
