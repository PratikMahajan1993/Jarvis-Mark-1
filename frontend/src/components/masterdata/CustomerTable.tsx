"use client";

import { Fragment, useState } from "react";

import { api } from "@/lib/api";

import { AliasManager } from "./AliasManager";
import {
  Field,
  HistoryRow,
  Modal,
  Toolbar,
  YesNoField,
  groupWithHistory,
  superseded,
  text,
  useEntity,
  usePaged,
  type Row,
} from "./shared";

const CREATE_EMPTY = { name: "", nda: "" as "" | "yes" | "no" };
const REPLACE_EMPTY = {
  name: "",
  gstin: "",
  currency: "INR",
  default_scope: "ask",
  payment_terms_days: "",
  nda: "" as "" | "yes" | "no",
};

export function CustomerTable() {
  const { items, error, loading, reload } = useEntity("customers");
  const [query, setQuery] = useState("");
  const grouped = groupWithHistory(items);
  const paged = usePaged(grouped, query, ["name", "gstin", "default_scope"], (g) => g.current);
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
      name: String(row.name ?? ""),
      gstin: String(row.gstin ?? ""),
      currency: String(row.currency ?? "INR"),
      default_scope: String(row.default_scope ?? "ask"),
      payment_terms_days: row.payment_terms_days == null ? "" : String(row.payment_terms_days),
      nda: row.nda ? "yes" : "no",
    });
    setFormError("");
  }

  async function save() {
    setFormError("");
    try {
      if (mode === "replace" && editing?.id) {
        await api.masterdataReplace("customers", String(editing.id), {
          name: replaceFields.name,
          gstin: replaceFields.gstin,
          currency: replaceFields.currency,
          default_scope: replaceFields.default_scope,
          payment_terms_days: replaceFields.payment_terms_days ? Number(replaceFields.payment_terms_days) : null,
          nda: replaceFields.nda === "yes" ? 1 : 0,
          allow_cloud_vision: 0,
        });
      } else {
        if (!createFields.name.trim()) {
          setFormError("Name is required");
          return;
        }
        if (createFields.nda !== "yes" && createFields.nda !== "no") {
          setFormError("Choose NDA yes or no");
          return;
        }
        await api.masterdataCreate("customers", {
          name: createFields.name,
          nda: createFields.nda,
        });
      }
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
            <th>NDA</th>
            <th>Vision</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {paged.slice.map(({ current, history }) => (
            <Fragment key={String(current.id)}>
              <tr className="border-t border-white/10">
                <td className="py-2">{text(current, "name")}</td>
                <td>{text(current, "gstin")}</td>
                <td>{text(current, "currency")}</td>
                <td>{text(current, "default_scope")}</td>
                <td>{text(current, "payment_terms_days")}</td>
                <td>{current.nda ? "yes" : "no"}</td>
                <td>{current.allow_cloud_vision ? "consented" : "off"}</td>
                <td>
                  <button type="button" className="text-cyan" onClick={() => openReplace(current)}>
                    Replace
                  </button>
                </td>
              </tr>
              {history.map((row) => (
                <HistoryRow key={String(row.id)}>
                  <td className="py-1 pl-4">{text(row, "name")}</td>
                  <td>{text(row, "gstin")}</td>
                  <td>{text(row, "currency")}</td>
                  <td>{text(row, "default_scope")}</td>
                  <td>{text(row, "payment_terms_days")}</td>
                  <td>{row.nda ? "yes" : "no"}</td>
                  <td>Superseded</td>
                  <td></td>
                </HistoryRow>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
      <Pager page={paged.page} pages={paged.pages} setPage={paged.setPage} />
      {editing ? (
        <Modal title={mode === "replace" ? "Replace customer" : "Add customer"} onClose={() => setEditing(null)}>
          {mode === "create" ? (
            <>
              <Field label="Name" value={createFields.name} onChange={(value) => setCreateFields({ ...createFields, name: value })} />
              <YesNoField
                label="NDA? Drawings must not leave the shop."
                value={createFields.nda}
                onChange={(value) => setCreateFields({ ...createFields, nda: value })}
              />
            </>
          ) : (
            <>
              <Field label="Name" value={replaceFields.name} onChange={(value) => setReplaceFields({ ...replaceFields, name: value })} />
              <Field label="GSTIN" value={replaceFields.gstin} onChange={(value) => setReplaceFields({ ...replaceFields, gstin: value })} />
              <Field
                label="Currency"
                value={replaceFields.currency}
                onChange={(value) => setReplaceFields({ ...replaceFields, currency: value })}
              />
              <Field
                label="Default scope"
                value={replaceFields.default_scope}
                onChange={(value) => setReplaceFields({ ...replaceFields, default_scope: value })}
              />
              <Field
                label="Payment terms (days)"
                value={replaceFields.payment_terms_days}
                onChange={(value) => setReplaceFields({ ...replaceFields, payment_terms_days: value })}
              />
              <YesNoField
                label="NDA? Drawings must not leave the shop."
                value={replaceFields.nda}
                onChange={(value) => setReplaceFields({ ...replaceFields, nda: value })}
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
