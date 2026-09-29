"use client";

import { Fragment, useState } from "react";

import { api } from "@/lib/api";

import { AliasManager } from "./AliasManager";
import {
  Field,
  HistoryRow,
  Modal,
  Toolbar,
  groupWithHistory,
  superseded,
  text,
  useEntity,
  usePaged,
  type Row,
} from "./shared";

const CREATE_EMPTY = { name: "" };
const REPLACE_EMPTY = { name: "", contact: "", lead_days: "" };

export function SupplierTable() {
  const { items, error, loading, reload } = useEntity("suppliers");
  const [query, setQuery] = useState("");
  const grouped = groupWithHistory(items);
  const paged = usePaged(grouped, query, ["name", "contact"], (g) => g.current);
  const [editing, setEditing] = useState<Row | null>(null);
  const [mode, setMode] = useState<"create" | "replace">("create");
  const [createFields, setCreateFields] = useState(CREATE_EMPTY);
  const [replaceFields, setReplaceFields] = useState(REPLACE_EMPTY);
  const [formError, setFormError] = useState("");
  const canonical = items.filter((row) => !superseded(row)).map((row) => ({ id: String(row.id), name: String(row.name) }));

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
      name: String(row.name ?? ""),
      contact: String(row.contact ?? ""),
      lead_days: row.lead_days == null ? "" : String(row.lead_days),
    });
    setFormError("");
  }

  async function save() {
    setFormError("");
    try {
      if (mode === "replace" && editing?.id) {
        await api.masterdataReplace("suppliers", String(editing.id), {
          ...replaceFields,
          lead_days: replaceFields.lead_days ? Number(replaceFields.lead_days) : null,
        });
      } else {
        await api.masterdataCreate("suppliers", { name: createFields.name });
      }
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
      <Toolbar query={query} onQuery={setQuery} onAdd={openNew} addLabel="Add supplier" />
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
          {paged.slice.map(({ current, history }) => (
            <Fragment key={String(current.id)}>
              <tr className="border-t border-white/10">
                <td className="py-2">{text(current, "name")}</td>
                <td>{text(current, "contact")}</td>
                <td>{text(current, "lead_days")}</td>
                <td>
                  <button type="button" className="text-cyan" onClick={() => openReplace(current)}>
                    Replace
                  </button>
                </td>
              </tr>
              {history.map((row) => (
                <HistoryRow key={String(row.id)}>
                  <td className="py-1 pl-4">{text(row, "name")}</td>
                  <td>{text(row, "contact")}</td>
                  <td>Superseded</td>
                  <td></td>
                </HistoryRow>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
      {editing ? (
        <Modal title={mode === "replace" ? "Replace supplier" : "Add supplier"} onClose={() => setEditing(null)}>
          {mode === "create" ? (
            <Field label="Name" value={createFields.name} onChange={(value) => setCreateFields({ name: value })} />
          ) : (
            <>
              <Field label="Name" value={replaceFields.name} onChange={(value) => setReplaceFields({ ...replaceFields, name: value })} />
              <Field
                label="Contact"
                value={replaceFields.contact}
                onChange={(value) => setReplaceFields({ ...replaceFields, contact: value })}
              />
              <Field
                label="Lead days"
                value={replaceFields.lead_days}
                onChange={(value) => setReplaceFields({ ...replaceFields, lead_days: value })}
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
