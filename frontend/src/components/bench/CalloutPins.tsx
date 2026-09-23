"use client";

import { useEffect, useRef } from "react";
import type { QuoteSheetRow } from "@/lib/pane/quoteContract";
import { clearBenchHighlight, registerPinScale, setBenchHighlight } from "./highlight";

export type PinSpec = {
  index: number;
  label: string;
  region: NonNullable<QuoteSheetRow["region"]>;
};

export function pinsFromRows(rows: QuoteSheetRow[]): PinSpec[] {
  const out: PinSpec[] = [];
  for (const row of rows) {
    if (!row.region) continue;
    out.push({ index: out.length, label: row.label, region: row.region });
  }
  return out;
}

function Pin({ pin }: { pin: PinSpec }) {
  const btnRef = useRef<HTMLButtonElement>(null);
  const scaleRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const btn = btnRef.current;
    const scaleEl = scaleRef.current;
    if (!btn || !scaleEl) return;
    const unregister = registerPinScale(pin.index, scaleEl);
    const enter = () => setBenchHighlight(pin.index);
    const leave = () => clearBenchHighlight();
    btn.addEventListener("mouseenter", enter);
    btn.addEventListener("mouseleave", leave);
    return () => {
      unregister();
      btn.removeEventListener("mouseenter", enter);
      btn.removeEventListener("mouseleave", leave);
    };
  }, [pin.index]);

  const { region } = pin;
  const left = `${region.x * 100}%`;
  const top = `${region.y * 100}%`;

  return (
    <button
      ref={btnRef}
      type="button"
      data-bench-pin={String(pin.index)}
      title={pin.label}
      className="bench-callout-pin absolute z-[2] flex h-7 w-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-[color:var(--accent)]/55 bg-black/55 font-mono text-[11px] text-[color:var(--accent)] shadow-[0_0_0_1px_rgba(0,0,0,0.35)] transition-[box-shadow] duration-150 hover:shadow-[0_0_0_2px_color-mix(in_oklch,var(--accent)_55%,transparent)]"
      style={{ left, top }}
    >
      <span ref={scaleRef} className="inline-flex">
        ⊕{pin.index + 1}
      </span>
    </button>
  );
}

export function CalloutPins({
  rows,
  page = 1,
}: {
  rows: QuoteSheetRow[];
  page?: number;
}) {
  const pins = pinsFromRows(rows).filter((p) => p.region.page === page);
  if (!pins.length) return null;
  return (
    <div className="pointer-events-none absolute inset-0 z-[2]">
      <div className="pointer-events-auto absolute inset-0">
        {pins.map((pin) => (
          <Pin key={pin.index} pin={pin} />
        ))}
      </div>
    </div>
  );
}
