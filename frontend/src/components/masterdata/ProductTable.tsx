"use client";

import { Fragment, useEffect, useState } from "react";

import { api } from "@/lib/api";

import {
  Field,
  HistoryRow,
  Modal,
  SelectField,
  Toolbar,
  YesNoField,
  groupWithHistory,
  text,
  useEntity,
  usePaged,
  type Row,
} from "./shared";

const EMPTY = {
  name: "",
  product_number: "",
  customer_id: "",
  uom: "ea",
  monitor_stock: "" as "" | "yes" | "no",
  material_id: "",
};

export function ProductTable() {
  const { items, error, loading, reload } = useEntity("products");
  const [query, setQuery] = useState("");
  const grouped = groupWithHistory(items);
  const paged = usePaged(grouped, query, ["name", "product_number", "customer_name", "uom"], (g) => g.current);
  const [editing, setEditing] = useState<Row | null>(null);
  const [fields, setFields] = useState(EMPTY);
  const [formError, setFormError] = useState("");
  const [customers, setCustomers] = useState<Array<{ id: string; name: string }>>([]);
  const [materials, setMaterials] = useState<Array<{ id: string; grade: string }>>([]);

  useEffect(() => {
    void api.masterdataOptions().then((data) => {
      setCustomers(data.customers || []);
      setMaterials(data.materials || []);
    });
  }, []);

  function openNew() {
    setEditing({});
    setFields(EMPTY);
    setFormError("");
  }

  function openReplace(row: Row) {
    setEditing(row);
    setFields({
      name: String(row.name ?? ""),
      product_number: String(row.product_number ?? ""),
      customer_id: String(row.customer_id ?? ""),
      uom: String(row.uom ?? "ea"),
      monitor_stock: row.monitor_stock ? "yes" : "no",
      material_id: String(row.material_id ?? ""),
    });
    setFormError("");
  }

  async function save() {
    setFormError("");
    if (!fields.name.trim() || !fields.product_number.trim() || !fields.customer_id || !fields.uom.trim()) {
      setFormError("Name, product number, customer, and unit of measure are required");
      return;
    }
    if (fields.monitor_stock !== "yes" && fields.monitor_stock !== "no") {
      setFormError("Choose whether to monitor stock");
      return;
    }
    const payload = {
      name: fields.name,
      product_number: fields.product_number,
      customer_id: fields.customer_id,
      uom: fields.uom,
      monitor_stock: fields.monitor_stock,
      material_id: fields.material_id || null,
    };
    try {
      if (editing?.id) await api.masterdataReplace("products", String(editing.id), payload);
      else await api.masterdataCreate("products", payload);
      setEditing(null);
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not save product");
    }
  }

  return (
    <section>
      <p className="mb-2 text-sm text-white/60">{loading ? "Loading products…" : `${paged.total} products`}</p>
      <Toolbar query={query} onQuery={setQuery} onAdd={openNew} addLabel="Add product" />
      {error ? <p className="mb-2 text-sm text-red">{error}</p> : null}
      <table className="w-full text-left text-sm">
        <thead className="text-white/50">
          <tr>
            <th className="py-1">Number</th>
            <th>Name</th>
            <th>Customer</th>
            <th>UoM</th>
            <th>Monitor stock</th>
            <th>Material</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {paged.slice.map(({ current, history }) => (
            <Fragment key={String(current.id)}>
              <tr className="border-t border-white/10">
                <td className="py-2">{text(current, "product_number")}</td>
                <td>{text(current, "name")}</td>
                <td>{text(current, "customer_name")}</td>
                <td>{text(current, "uom")}</td>
                <td>{current.monitor_stock ? "yes" : "no"}</td>
                <td>{text(current, "material_grade")}</td>
                <td>
                  <button type="button" className="text-cyan" onClick={() => openReplace(current)}>
                    Replace
                  </button>
                </td>
              </tr>
              {history.map((row) => (
                <HistoryRow key={String(row.id)}>
                  <td className="py-1 pl-4">{text(row, "product_number")}</td>
                  <td>{text(row, "name")}</td>
                  <td>{text(row, "customer_name")}</td>
                  <td>{text(row, "uom")}</td>
                  <td>Superseded</td>
                  <td>{text(row, "material_grade")}</td>
                  <td></td>
                </HistoryRow>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
      {editing ? (
        <Modal title={editing.id ? "Replace product" : "Add product"} onClose={() => setEditing(null)}>
          <Field label="Product name" value={fields.name} onChange={(value) => setFields({ ...fields, name: value })} />
          <Field
            label="Product number"
            value={fields.product_number}
            onChange={(value) => setFields({ ...fields, product_number: value })}
          />
          <SelectField
            label="Customer"
            value={fields.customer_id}
            onChange={(value) => setFields({ ...fields, customer_id: value })}
            options={customers.map((c) => ({ id: c.id, label: c.name }))}
          />
          <Field label="Unit of measure" value={fields.uom} onChange={(value) => setFields({ ...fields, uom: value })} />
          <YesNoField
            label="Monitor stock?"
            value={fields.monitor_stock}
            onChange={(value) => setFields({ ...fields, monitor_stock: value })}
          />
          <SelectField
            label="Material (optional)"
            value={fields.material_id}
            onChange={(value) => setFields({ ...fields, material_id: value })}
            options={materials.map((m) => ({ id: m.id, label: m.grade }))}
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
