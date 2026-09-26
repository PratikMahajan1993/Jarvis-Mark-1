"use client";

import { useState } from "react";

import { api } from "@/lib/api";

import { Field, Modal, Toolbar, superseded, text, useEntity, usePaged, type Row } from "./shared";

const EMPTY = { name: "", processes: "", lead_days: "" };

export function OutsourceVendorTable() {
  const { items, error, loading, reload } = useEntity("outsource-vendors");
  const [query, setQuery] = useState("");
  const paged = usePaged(items, query, ["name", "processes"]);
  const [editing, setEditing] = useState<Row | null>(null);
  const [fields, setFields] = useState(EMPTY);
  const [formError, setFormError] = useState("");

  function openReplace(row: Row) {
    setEditing(row);
    setFields({
      name: String(row.name ?? ""),
      processes: String(row.processes ?? ""),
      lead_days: row.lead_days == null ? "" : String(row.lead_days),
    });
  }

  async function save() {
    setFormError("");
    const payload = { ...fields, lead_days: fields.lead_days ? Number(fields.lead_days) : null };
    try {
      if (editing?.id) await api.masterdataReplace("outsource-vendors", String(editing.id), payload);
      else await api.masterdataCreate("outsource-vendors", payload);
      setEditing(null);
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not save vendor");
    }
  }

  return (
    <section>
      <p className="mb-2 text-sm text-white/60">{loading ? "Loading vendors…" : `${paged.total} outsource vendors`}</p>
      <Toolbar query={query} onQuery={setQuery} onAdd={() => { setEditing({}); setFields(EMPTY); }} addLabel="Add vendor" />
      {error ? <p className="mb-2 text-sm text-red">{error}</p> : null}
      <table className="w-full text-left text-sm">
        <thead className="text-white/50">
          <tr>
            <th className="py-1">Name</th>
            <th>Processes</th>
            <th>Lead days</th>
            <th>Quotes</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {paged.slice.map((row) => {
            const quotes = Array.isArray(row.quotes) ? row.quotes : [];
            return (
              <tr key={String(row.id)} className={`border-t border-white/10 ${superseded(row) ? "line-through opacity-50" : ""}`}>
                <td className="py-2">{text(row, "name")}</td>
                <td>{text(row, "processes")}</td>
                <td>{text(row, "lead_days")}</td>
                <td>{quotes.length}</td>
                <td>
                  {superseded(row) ? "Superseded" : (
                    <button type="button" className="text-cyan" onClick={() => openReplace(row)}>
                      Replace
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {editing ? (
        <Modal title={editing.id ? "Replace vendor" : "Add vendor"} onClose={() => setEditing(null)}>
          <Field label="Name" value={fields.name} onChange={(value) => setFields({ ...fields, name: value })} />
          <Field label="Processes" value={fields.processes} onChange={(value) => setFields({ ...fields, processes: value })} />
          <Field label="Lead days" value={fields.lead_days} onChange={(value) => setFields({ ...fields, lead_days: value })} />
          {formError ? <p className="mb-2 text-sm text-red">{formError}</p> : null}
          <button type="button" className="rounded bg-cyan px-3 py-2 text-sm font-medium text-ink" onClick={() => void save()}>
            Save
          </button>
        </Modal>
      ) : null}
    </section>
  );
}
