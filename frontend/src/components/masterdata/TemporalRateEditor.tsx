"use client";

import { useState } from "react";

import { Field, Modal, type Row, text } from "./shared";

export function TemporalRateEditor({
  rows,
  onAdd,
}: {
  rows: Row[];
  onAdd: (fields: Record<string, string>) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [rate, setRate] = useState("");
  const [error, setError] = useState("");

  async function save() {
    setError("");
    try {
      await onAdd({ effective_from: effectiveFrom, min_mhr_inr: rate, price_inr: rate });
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add rate");
    }
  }

  return (
    <div>
      <div className="mb-3 flex h-3 overflow-hidden rounded bg-white/5">
        {rows.map((row) => (
          <div
            key={String(row.id)}
            title={`${text(row, "effective_from")} → ${text(row, "effective_to")}`}
            className={`h-full flex-1 ${row.current ? "bg-cyan" : "bg-white/20"}`}
          />
        ))}
      </div>
      <table className="w-full text-left text-sm">
        <thead className="text-white/50">
          <tr>
            <th className="py-1">Effective from</th>
            <th>Effective to</th>
            <th>Rate</th>
            <th>Attested by</th>
            <th>Attested at</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row.id)} className="border-t border-white/10">
              <td className="py-2">{text(row, "effective_from")}</td>
              <td>{text(row, "effective_to")}</td>
              <td>{text(row, "min_mhr_inr") !== "—" ? text(row, "min_mhr_inr") : text(row, "price_inr")}</td>
              <td>{text(row, "attested_by")}</td>
              <td>
                {text(row, "attested_at")}
                {row.current ? <span className="ml-2 rounded bg-cyan/20 px-2 py-0.5 text-xs text-cyan">Current rate</span> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button type="button" className="mt-3 text-sm text-cyan underline" onClick={() => setOpen(true)}>
        Add rate
      </button>
      {open ? (
        <Modal title="Add rate" onClose={() => setOpen(false)}>
          <Field label="Effective from" value={effectiveFrom} onChange={setEffectiveFrom} />
          <Field label="Rate (INR)" value={rate} onChange={setRate} />
          {error ? <p className="mb-2 text-sm text-red">{error}</p> : null}
          <button type="button" className="rounded bg-cyan px-3 py-2 text-sm font-medium text-ink" onClick={() => void save()}>
            Save rate
          </button>
        </Modal>
      ) : null}
    </div>
  );
}
