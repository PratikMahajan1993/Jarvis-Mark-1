"use client";

import { useState } from "react";

import { api } from "@/lib/api";

import { TemporalRateEditor } from "./TemporalRateEditor";
import { text, useEntity, type Row } from "./shared";

export function MHRFloorTable() {
  const { items, error, loading, reload } = useEntity("mhr");
  const [machineType, setMachineType] = useState("");
  const [formError, setFormError] = useState("");
  const types = Array.from(new Set(items.map((row) => String(row.machine_type || "")).filter(Boolean)));
  const selected = machineType || types[0] || "";
  const rows = items.filter((row) => String(row.machine_type) === selected);

  async function addRate(fields: Record<string, string>) {
    setFormError("");
    if (!selected) throw new Error("Choose a machine type");
    await api.masterdataCreate("mhr", { ...fields, machine_type: selected });
    await reload();
  }

  async function replace(row: Row, fields: Record<string, string>) {
    await api.masterdataReplace("mhr", String(row.id), { ...fields, machine_type: selected });
    await reload();
  }

  return (
    <section>
      <p className="mb-2 text-sm text-white/60">{loading ? "Loading floors…" : "Machine-hour floors"}</p>
      {error ? <p className="mb-2 text-sm text-red">{error}</p> : null}
      <label className="mb-3 block text-sm text-white/70">
        Machine type
        <select
          className="mt-1 w-full max-w-sm rounded border border-white/10 bg-ink px-3 py-2"
          value={selected}
          onChange={(event) => setMachineType(event.target.value)}
        >
          {types.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </label>
      <TemporalRateEditor
        rows={rows}
        onAdd={async (fields) => {
          const current = rows.find((row) => row.current);
          if (current) await replace(current, fields);
          else await addRate(fields);
        }}
      />
      <ul className="mt-4 space-y-1 text-sm text-white/70">
        {rows.map((row) => (
          <li key={String(row.id)}>
            {text(row, "machine_type")} · {text(row, "min_mhr_inr")} INR/hr ·{" "}
            {row.attested_by ? `attested ${text(row, "attested_by")}` : "needs attestation"}
            {row.current ? "" : " · superseded"}
          </li>
        ))}
      </ul>
      {formError ? <p className="mt-2 text-sm text-red">{formError}</p> : null}
    </section>
  );
}
