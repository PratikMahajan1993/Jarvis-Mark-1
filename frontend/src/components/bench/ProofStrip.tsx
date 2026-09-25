"use client";

import type { QuoteVerifyResult } from "@/lib/pane/quoteContract";

export function ProofStrip({ verify }: { verify: QuoteVerifyResult }) {
  const total = verify.checks.length;
  const failed = verify.failed_count;

  return (
    <div className="flex flex-wrap items-center gap-1.5" data-proof-strip>
      {verify.checks.map((check) => (
        <span
          key={check.id}
          title={`${check.id}: ${check.evidence}`}
          className={[
            "inline-flex h-2.5 min-w-[10px] items-center justify-center rounded-full px-1 font-mono text-[8px] leading-none",
            check.pass
              ? "bg-[color:color-mix(in_oklch,var(--accent)_35%,transparent)] text-[color:var(--accent)]"
              : "bg-[color:oklch(55%_0.18_25_/_0.45)] text-[color:oklch(78%_0.16_25)]",
          ].join(" ")}
          aria-label={`${check.id} ${check.pass ? "pass" : "fail"}`}
        >
          {check.pass ? "✓" : "✗"}
        </span>
      ))}
      <span className="ml-1 font-mono text-[10px] tabular-nums text-[color:var(--muted)]">
        {failed}/{total}
      </span>
      {verify.stop ? (
        <span className="ml-1 rounded border border-[color:oklch(55%_0.18_25_/_0.5)] px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-[color:oklch(78%_0.16_25)]">
          stop
        </span>
      ) : null}
      {verify.checks.some((check) => check.id === "mhr_demo_floor" && !check.pass) ? (
        <span className="ml-1 font-mono text-[9px] text-[color:oklch(78%_0.16_25)]" data-mhr-warning>
          Demo MHR not attested — will block send
        </span>
      ) : null}
    </div>
  );
}
