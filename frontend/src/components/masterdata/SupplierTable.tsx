"use client";

import { useState } from "react";

import { api } from "@/lib/api";

import { AliasManager } from "./AliasManager";
import { Field, Modal, Toolbar, superseded, text, useEntity, usePaged, type Row } from "./shared";

const EMPTY = { name: "", contact: "", lead_days: "" };

export function SupplierTable() {
  const { items, error, loading, reload } = useEntity("suppliers");
  const [query, setQuery] = useState("");
  const paged = usePaged(items, query, ["name", "contact"]);
  const [editing, setEditing] = useState<Row | null>(null);
  const [fields, setFields] = useState(EMPTY);
  const [formError, setFormError] = useState("");
  const canonical = items.filter((row) => !superseded(row)).map((row) => ({ id: String(row.id), name: String(row.name) }));

  function openReplace(row: Row) {
    setEditing(row);
    setFields({
      name: String(row.name ?? ""),
      contact: String(row.contact ?? ""),
      lead_days: row.lead_days == null ? "" : String(row.lead_days),
    });
  }

  async function save() {
    setFormError("");
    const payload = { ...fields, lead_days: fields.lead_days ? Number(fields.lead_days) : null };
    try {
      if (editing?.id) await api.masterdataReplace("suppliers", String(editing.id), payload);
      else await api.masterdataCreate("suppliers", payload);
      setEditing(null);
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not save supplier");
    }
  }

  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm text-white/60">{loading ? "Loading suppliers…" : `${paged.total} suppliers`}</p>
        <AliasManager kind="vendor" canonical={canonical} />
      </div>
      <Toolbar query={query} onQuery={setQuery} onAdd={() => { setEditing({}); setFields(EMPTY); }} addLabel="Add supplier" />
      {error ? <p className="mb-2 text-sm text-red">{error}</p> : null}
      <table className="w-full text-left text-sm">
        <thead className="text-white/50">
          <tr>
            <th className="py-1">Name</th>
            <th>Contact</th>
            <th>Lead days</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {paged.slice.map((row) => (
            <tr key={String(row.id)} className={`border-t border-white/10 ${superseded(row) ? "line-through opacity-50" : ""}`}>
              <td className="py-2">{text(row, "name")}</td>
              <td>{text(row, "contact")}</td>
              <td>{text(row, "lead_days")}</td>
              <td>
                {superseded(row) ? "Superseded" : (
                  <button type="button" className="text-cyan" onClick={() => openReplace(row)}>
                    Replace
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {editing ? (
        <Modal title={editing.id ? "Replace supplier" : "Add supplier"} onClose={() => setEditing(null)}>
          <Field label="Name" value={fields.name} onChange={(value) => setFields({ ...fields, name: value })} />
          <Field label="Contact" value={fields.contact} onChange={(value) => setFields({ ...fields, contact: value })} />
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
