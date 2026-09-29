"use client";

import { Fragment, useState } from "react";

import { api } from "@/lib/api";

import {
  Field,
  HistoryRow,
  Modal,
  Toolbar,
  groupWithHistory,
  text,
  useEntity,
  usePaged,
  type Row,
} from "./shared";

const CREATE_EMPTY = { grade: "", form: "bar" };
const REPLACE_EMPTY = {
  grade: "",
  family: "",
  standard: "",
  density_kg_m3: "",
  form: "bar",
  equivalent_grade: "",
  confirmed_by: "",
};

export function MaterialTable() {
  const { items, error, loading, reload } = useEntity("materials");
  const [query, setQuery] = useState("");
  const grouped = groupWithHistory(items);
  const paged = usePaged(grouped, query, ["grade", "family", "standard", "form"], (g) => g.current);
  const [editing, setEditing] = useState<Row | null>(null);
  const [mode, setMode] = useState<"create" | "replace">("create");
  const [createFields, setCreateFields] = useState(CREATE_EMPTY);
  const [replaceFields, setReplaceFields] = useState(REPLACE_EMPTY);
  const [formError, setFormError] = useState("");

  function openNew() {
    setMode("create");
    setEditing({});
    setCreateFields(CREATE_EMPTY);
    setFormError("");
  }

  function openReplace(row: Row) {
    setMode("replace");
    setEditing(row);
    setReplaceFields({
      ...REPLACE_EMPTY,
      grade: String(row.grade ?? ""),
      family: String(row.family ?? ""),
      standard: String(row.standard ?? ""),
      density_kg_m3: row.density_kg_m3 == null ? "" : String(row.density_kg_m3),
      form: String(row.form ?? "bar"),
    });
    setFormError("");
  }

  async function save() {
    setFormError("");
    try {
      if (mode === "replace" && editing?.id) {
        await api.masterdataReplace("materials", String(editing.id), {
          ...replaceFields,
          density_kg_m3: replaceFields.density_kg_m3 ? Number(replaceFields.density_kg_m3) : null,
        });
      } else {
        await api.masterdataCreate("materials", {
          grade: createFields.grade,
          form: createFields.form,
        });
      }
      setEditing(null);
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not save material");
    }
  }

  return (
    <section>
      <p className="mb-2 text-sm text-white/60">{loading ? "Loading materials…" : `${paged.total} materials`}</p>
      <Toolbar query={query} onQuery={setQuery} onAdd={openNew} addLabel="Add material" />
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
          {paged.slice.map(({ current, history }) => {
            const equivalents = Array.isArray(current.equivalents) ? current.equivalents : [];
            return (
              <Fragment key={String(current.id)}>
                <tr className="border-t border-white/10">
                  <td className="py-2">{text(current, "grade")}</td>
                  <td>{text(current, "family")}</td>
                  <td>{text(current, "standard")}</td>
                  <td>{text(current, "density_kg_m3")}</td>
                  <td>{text(current, "form")}</td>
                  <td>{equivalents.map((item) => String((item as Row).equivalent_grade)).join(", ") || "—"}</td>
                  <td>
                    <button type="button" className="text-cyan" onClick={() => openReplace(current)}>
                      Replace
                    </button>
                  </td>
                </tr>
                {history.map((row) => (
                  <HistoryRow key={String(row.id)}>
                    <td className="py-1 pl-4">{text(row, "grade")}</td>
                    <td>{text(row, "family")}</td>
                    <td>{text(row, "standard")}</td>
                    <td>{text(row, "density_kg_m3")}</td>
                    <td>{text(row, "form")}</td>
                    <td>Superseded</td>
                    <td></td>
                  </HistoryRow>
                ))}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      {editing ? (
        <Modal title={mode === "replace" ? "Replace material" : "Add material"} onClose={() => setEditing(null)}>
          {mode === "create" ? (
            <>
              <Field label="Grade" value={createFields.grade} onChange={(value) => setCreateFields({ ...createFields, grade: value })} />
              <Field label="Form" value={createFields.form} onChange={(value) => setCreateFields({ ...createFields, form: value })} />
            </>
          ) : (
            <>
              <Field label="Grade" value={replaceFields.grade} onChange={(value) => setReplaceFields({ ...replaceFields, grade: value })} />
              <Field label="Family" value={replaceFields.family} onChange={(value) => setReplaceFields({ ...replaceFields, family: value })} />
              <Field
                label="Standard"
                value={replaceFields.standard}
                onChange={(value) => setReplaceFields({ ...replaceFields, standard: value })}
              />
              <Field
                label="Density kg/m3"
                value={replaceFields.density_kg_m3}
                onChange={(value) => setReplaceFields({ ...replaceFields, density_kg_m3: value })}
              />
              <Field label="Form" value={replaceFields.form} onChange={(value) => setReplaceFields({ ...replaceFields, form: value })} />
              <Field
                label="Equivalent grade"
                value={replaceFields.equivalent_grade}
                onChange={(value) => setReplaceFields({ ...replaceFields, equivalent_grade: value })}
              />
              <Field
                label="Equivalent confirmed by"
                value={replaceFields.confirmed_by}
                onChange={(value) => setReplaceFields({ ...replaceFields, confirmed_by: value })}
              />
            </>
          )}
          {formError ? <p className="mb-2 text-sm text-red">{formError}</p> : null}
          <button type="button" className="rounded bg-cyan px-3 py-2 text-sm font-medium text-ink" onClick={() => void save()}>
            Save
          </button>
        </Modal>
      ) : null}
    </section>
  );
}
