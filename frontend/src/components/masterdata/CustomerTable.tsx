"use client";

import { useState } from "react";

import { api } from "@/lib/api";

import { AliasManager } from "./AliasManager";
import { Field, Modal, Toolbar, superseded, text, useEntity, usePaged, type Row } from "./shared";

const EMPTY = { name: "", gstin: "", currency: "INR", default_scope: "ask", payment_terms_days: "" };

export function CustomerTable() {
  const { items, error, loading, reload } = useEntity("customers");
  const [query, setQuery] = useState("");
  const paged = usePaged(items, query, ["name", "gstin", "default_scope"]);
  const [editing, setEditing] = useState<Row | null>(null);
  const [fields, setFields] = useState(EMPTY);
  const [formError, setFormError] = useState("");

  function openNew() {
    setEditing({});
    setFields(EMPTY);
    setFormError("");
  }

  function openReplace(row: Row) {
    setEditing(row);
    setFields({
      name: String(row.name ?? ""),
      gstin: String(row.gstin ?? ""),
      currency: String(row.currency ?? "INR"),
      default_scope: String(row.default_scope ?? "ask"),
      payment_terms_days: row.payment_terms_days == null ? "" : String(row.payment_terms_days),
    });
    setFormError("");
  }

  async function save() {
    setFormError("");
    const payload = {
      ...fields,
      payment_terms_days: fields.payment_terms_days ? Number(fields.payment_terms_days) : null,
    };
    try {
      if (editing && editing.id) await api.masterdataReplace("customers", String(editing.id), payload);
      else await api.masterdataCreate("customers", payload);
      setEditing(null);
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not save customer");
    }
  }

  const canonical = items.filter((row) => !superseded(row)).map((row) => ({ id: String(row.id), name: String(row.name) }));

  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm text-white/60">{loading ? "Loading customers…" : `${paged.total} customers`}</p>
        <AliasManager kind="customer" canonical={canonical} />
      </div>
      <Toolbar query={query} onQuery={setQuery} onAdd={openNew} addLabel="Add customer" />
      {error ? <p className="mb-2 text-sm text-red">{error}</p> : null}
      <table className="w-full text-left text-sm">
        <thead className="text-white/50">
          <tr>
            <th className="py-1">Name</th>
            <th>GSTIN</th>
            <th>Currency</th>
            <th>Scope</th>
            <th>Terms</th>
            <th>Vision</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {paged.slice.map((row) => (
            <tr key={String(row.id)} className={`border-t border-white/10 ${superseded(row) ? "line-through opacity-50" : ""}`}>
              <td className="py-2">{text(row, "name")}</td>
              <td>{text(row, "gstin")}</td>
              <td>{text(row, "currency")}</td>
              <td>{text(row, "default_scope")}</td>
              <td>{text(row, "payment_terms_days")}</td>
              <td>{row.allow_cloud_vision ? "consented" : "off"}</td>
              <td>
                {superseded(row) ? (
                  "Superseded"
                ) : (
                  <button type="button" className="text-cyan" onClick={() => openReplace(row)}>
                    Replace
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pager page={paged.page} pages={paged.pages} setPage={paged.setPage} />
      {editing ? (
        <Modal title={editing.id ? "Replace customer" : "Add customer"} onClose={() => setEditing(null)}>
          <Field label="Name" value={fields.name} onChange={(value) => setFields({ ...fields, name: value })} />
          <Field label="GSTIN" value={fields.gstin} onChange={(value) => setFields({ ...fields, gstin: value })} />
          <Field label="Currency" value={fields.currency} onChange={(value) => setFields({ ...fields, currency: value })} />
          <Field label="Default scope" value={fields.default_scope} onChange={(value) => setFields({ ...fields, default_scope: value })} />
          <Field
            label="Payment terms (days)"
            value={fields.payment_terms_days}
            onChange={(value) => setFields({ ...fields, payment_terms_days: value })}
          />
          {formError ? <p className="mb-2 text-sm text-red">{formError}</p> : null}
          <button type="button" className="rounded bg-cyan px-3 py-2 text-sm font-medium text-ink" onClick={() => void save()}>
            Save
          </button>
        </Modal>
      ) : null}
    </section>
  );
}

function Pager({ page, pages, setPage }: { page: number; pages: number; setPage: (page: number) => void }) {
  return (
    <div className="mt-3 flex gap-2 text-sm text-white/60">
      <button type="button" disabled={page <= 0} onClick={() => setPage(page - 1)}>
        Prev
      </button>
      <span>
        {page + 1} / {pages}
      </span>
      <button type="button" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>
        Next
      </button>
    </div>
  );
}
