"use client";

import { useCallback, useEffect, useState } from "react";
import GradientText from "@/components/react-bits/GradientText";
import SpotlightCard from "@/components/react-bits/SpotlightCard";
import { api } from "@/lib/api";

type ErosionItem = {
  quote_line_id: string;
  kind: string;
  description: string;
  erosion_minor: number;
  quoted_amount_minor: number;
  actual_amount_minor: number;
  source_ref: string;
  recorded_at: string;
};

function formatErosionInr(erosionMinor: number): string {
  const inr = erosionMinor / 100;
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(inr);
}

export function VarianceCard() {
  const [items, setItems] = useState<ErosionItem[] | null>(null);
  const [failed, setFailed] = useState(false);

  const refresh = useCallback(async () => {
    setFailed(false);
    try {
      const data = await api.quoteVarianceErosion(20);
      setItems(Array.isArray(data.items) ? data.items : []);
    } catch {
      setFailed(true);
      setItems([]);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const empty = failed || !items?.length;

  return (
    <SpotlightCard
      className="shrink-0 rounded-2xl border border-[color:var(--border)] bg-black/40 backdrop-blur-md"
      bodyClassName="max-h-48 overflow-y-auto p-4"
    >
      <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.22em]">
        <GradientText className="font-mono text-[10px] uppercase tracking-[0.22em]" animationSpeed={9}>
          Margin erosion
        </GradientText>
      </p>
      {empty ? (
        <p className="text-sm text-[color:var(--muted)]">No recorded actuals</p>
      ) : (
        <ol className="space-y-2">
          {items!.map((row, index) => (
            <li
              key={row.quote_line_id}
              className="rounded-xl border border-[color:var(--border)] bg-black/30 px-3 py-2"
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-mono text-[10px] text-[color:var(--muted)]/70">
                  {index + 1}
                </span>
                <span className="font-display text-sm text-[color:var(--accent)]">
                  {formatErosionInr(row.erosion_minor)} INR
                </span>
              </div>
              <p className="mt-1 text-xs leading-snug text-[color:var(--fg)]/90">
                {(row.description || "").trim() || row.kind}
              </p>
              {row.source_ref ? (
                <p className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-[color:var(--muted)]/60">
                  {row.source_ref}
                </p>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </SpotlightCard>
  );
}
