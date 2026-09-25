"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type RmRequest = {
  id: string;
  material: string;
  supplier: string;
  status: string;
  quoted_price_minor?: number | null;
  currency?: string;
  is_estimate?: number;
  notes?: string;
  quote_date?: string | null;
};

function rupees(minor: number | null | undefined): string {
  if (minor == null) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(minor / 100);
}

export function RMTracker({ sessionId }: { sessionId: string }) {
  const [rows, setRows] = useState<RmRequest[]>([]);
  const [note, setNote] = useState("");
  const [material, setMaterial] = useState("");
  const [supplier, setSupplier] = useState("");
  const [email, setEmail] = useState("");
  const [price, setPrice] = useState("");
  const [quoteDate, setQuoteDate] = useState("");
  const [basis, setBasis] = useState("");
  const [estimate, setEstimate] = useState(false);

  const reload = useCallback(() => {
    void api
      .rmQuotes(sessionId)
      .then((result) => setRows(result.requests || []))
      .catch(() => setNote("Could not load raw-material quotes."));
  }, [sessionId]);

  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <section className="space-y-2" data-rm-tracker>
      <h3 className="font-mono text-[9px] uppercase tracking-[0.18em] text-[color:var(--muted)]/75">
        Raw material quotes
      </h3>
      {rows.length === 0 ? (
        <p className="font-mono text-[10px] text-[color:var(--muted)]">No supplier quote requested yet.</p>
      ) : (
        <ul className="space-y-1">
          {rows.map((row) => (
            <li key={row.id} className="font-mono text-[10px] text-[color:var(--fg)]">
              {row.material} · {row.supplier} · {row.status}
              {row.status === "received" ? ` · ${rupees(row.quoted_price_minor)}` : ""}
              {row.is_estimate ? " · estimate" : ""}
            </li>
          ))}
        </ul>
      )}
      <form
        className="grid gap-1"
        onSubmit={(event) => {
          event.preventDefault();
          setNote("");
          void api.requestRmQuote(sessionId, material, supplier, email).then((result) => {
            setNote(result.ok ? "Request queued for Authorize. Not sent." : result.message || "Could not queue the request.");
            if (result.ok) reload();
          });
        }}
      >
        <input
          aria-label="Material"
          value={material}
          onChange={(event) => setMaterial(event.target.value)}
          placeholder="Material"
          className="rounded border border-[color:var(--border)] bg-transparent px-2 py-1 font-mono text-[10px]"
        />
        <input
          aria-label="Supplier"
          value={supplier}
          onChange={(event) => setSupplier(event.target.value)}
          placeholder="Supplier"
          className="rounded border border-[color:var(--border)] bg-transparent px-2 py-1 font-mono text-[10px]"
        />
        <input
          aria-label="Supplier email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="Supplier email"
          className="rounded border border-[color:var(--border)] bg-transparent px-2 py-1 font-mono text-[10px]"
        />
        <button
          type="submit"
          className="w-fit rounded border border-[color:var(--border)] px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em]"
        >
          Request quote
        </button>
      </form>
      <form
        className="grid gap-1"
        onSubmit={(event) => {
          event.preventDefault();
          setNote("");
          void api
            .recordRmQuote(sessionId, {
              price_inr: price,
              quote_date: quoteDate,
              notes: basis,
              is_estimate: estimate,
            })
            .then((result) => {
              setNote(result.ok ? "Quote recorded." : result.message || "Could not record the quote.");
              if (result.ok) reload();
            });
        }}
      >
        <input
          aria-label="Price INR"
          value={price}
          onChange={(event) => setPrice(event.target.value)}
          placeholder="Price INR"
          className="rounded border border-[color:var(--border)] bg-transparent px-2 py-1 font-mono text-[10px]"
        />
        <input
          aria-label="Quote date"
          value={quoteDate}
          onChange={(event) => setQuoteDate(event.target.value)}
          placeholder="Quote date YYYY-MM-DD"
          className="rounded border border-[color:var(--border)] bg-transparent px-2 py-1 font-mono text-[10px]"
        />
        <label className="flex items-center gap-2 font-mono text-[10px] text-[color:var(--muted)]">
          <input
            type="checkbox"
            checked={estimate}
            onChange={(event) => setEstimate(event.target.checked)}
          />
          Estimate
        </label>
        <input
          aria-label="Basis note"
          value={basis}
          onChange={(event) => setBasis(event.target.value)}
          placeholder="Historical or market basis"
          className="rounded border border-[color:var(--border)] bg-transparent px-2 py-1 font-mono text-[10px]"
        />
        <button
          type="submit"
          className="w-fit rounded border border-[color:var(--border)] px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em]"
        >
          Record quote
        </button>
      </form>
      {note ? (
        <p className="font-mono text-[10px] text-[color:var(--muted)]" data-rm-note>
          {note}
        </p>
      ) : null}
    </section>
  );
}
