"use client";

import { useState } from "react";

import { api } from "@/lib/api";

import { Field, Modal, Toolbar, superseded, text, useEntity, usePaged, type Row } from "./shared";

const EMPTY = { grade: "", family: "", standard: "", density_kg_m3: "", form: "bar", equivalent_grade: "", confirmed_by: "" };

export function MaterialTable() {
  const { items, error, loading, reload } = useEntity("materials");
  const [query, setQuery] = useState("");
  const paged = usePaged(items, query, ["grade", "family", "standard"]);
  const [editing, setEditing] = useState<Row | null>(null);
  const [fields, setFields] = useState(EMPTY);
  const [formError, setFormError] = useState("");

  function openReplace(row: Row) {
    setEditing(row);
    setFields({
      ...EMPTY,
      grade: String(row.grade ?? ""),
      family: String(row.family ?? ""),
      standard: String(row.standard ?? ""),
      density_kg_m3: row.density_kg_m3 == null ? "" : String(row.density_kg_m3),
      form: String(row.form ?? "bar"),
    });
  }

  async function save() {
    setFormError("");
    const payload = {
      ...fields,
      density_kg_m3: fields.density_kg_m3 ? Number(fields.density_kg_m3) : null,
    };
    try {
      if (editing?.id) await api.masterdataReplace("materials", String(editing.id), payload);
      else await api.masterdataCreate("materials", payload);
      setEditing(null);
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not save material");
    }
  }

  return (
    <section>
      <p className="mb-2 text-sm text-white/60">{loading ? "Loading materials…" : `${paged.total} materials`}</p>
      <Toolbar query={query} onQuery={setQuery} onAdd={() => { setEditing({}); setFields(EMPTY); }} addLabel="Add material" />
      {error ? <p className="mb-2 text-sm text-red">{error}</p> : null}
      <table className="w-full text-left text-sm">
        <thead className="text-white/50">
          <tr>
            <th className="py-1">Grade</th>
            <th>Family</th>
            <th>Standard</th>
            <th>Density</th>
            <th>Form</th>
            <th>Equivalents</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {paged.slice.map((row) => {
            const equivalents = Array.isArray(row.equivalents) ? row.equivalents : [];
            return (
              <tr key={String(row.id)} className={`border-t border-white/10 ${superseded(row) ? "line-through opacity-50" : ""}`}>
                <td className="py-2">{text(row, "grade")}</td>
                <td>{text(row, "family")}</td>
                <td>{text(row, "standard")}</td>
                <td>{text(row, "density_kg_m3")}</td>
                <td>{text(row, "form")}</td>
                <td>{equivalents.map((item) => String((item as Row).equivalent_grade)).join(", ") || "—"}</td>
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
        <Modal title={editing.id ? "Replace material" : "Add material"} onClose={() => setEditing(null)}>
          <Field label="Grade" value={fields.grade} onChange={(value) => setFields({ ...fields, grade: value })} />
          <Field label="Family" value={fields.family} onChange={(value) => setFields({ ...fields, family: value })} />
          <Field label="Standard" value={fields.standard} onChange={(value) => setFields({ ...fields, standard: value })} />
          <Field label="Density kg/m3" value={fields.density_kg_m3} onChange={(value) => setFields({ ...fields, density_kg_m3: value })} />
          <Field label="Form" value={fields.form} onChange={(value) => setFields({ ...fields, form: value })} />
          <Field label="Equivalent grade" value={fields.equivalent_grade} onChange={(value) => setFields({ ...fields, equivalent_grade: value })} />
          <Field label="Equivalent confirmed by" value={fields.confirmed_by} onChange={(value) => setFields({ ...fields, confirmed_by: value })} />
          {formError ? <p className="mb-2 text-sm text-red">{formError}</p> : null}
          <button type="button" className="rounded bg-cyan px-3 py-2 text-sm font-medium text-ink" onClick={() => void save()}>
            Save
          </button>
        </Modal>
      ) : null}
    </section>
  );
}
