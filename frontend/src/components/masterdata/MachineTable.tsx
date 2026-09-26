"use client";

import { useState } from "react";

import { api } from "@/lib/api";

import { AliasManager } from "./AliasManager";
import { Field, Modal, Toolbar, superseded, text, useEntity, usePaged, type Row } from "./shared";

const EMPTY = {
  name: "",
  machine_type: "",
  control_make: "",
  control_model: "",
  axes: "",
  travel_x: "",
  travel_y: "",
  travel_z: "",
  rapid_x: "",
  rapid_y: "",
  rapid_z: "",
  max_rpm: "",
  spindle_kw: "",
  bar_capacity_mm: "",
  chuck_mm: "",
  capability_process: "",
};

export function MachineTable() {
  const { items, error, loading, reload } = useEntity("machines");
  const [query, setQuery] = useState("");
  const paged = usePaged(items, query, ["name", "machine_type", "control_make"]);
  const [editing, setEditing] = useState<Row | null>(null);
  const [fields, setFields] = useState(EMPTY);
  const [formError, setFormError] = useState("");

  function set<K extends keyof typeof EMPTY>(key: K, value: string) {
    setFields((current) => ({ ...current, [key]: value }));
  }

  function openReplace(row: Row) {
    setEditing(row);
    setFields({
      ...EMPTY,
      name: String(row.name ?? ""),
      machine_type: String(row.machine_type ?? ""),
      control_make: String(row.control_make ?? ""),
      control_model: String(row.control_model ?? ""),
      axes: row.axes == null ? "" : String(row.axes),
      travel_x: row.travel_x == null ? "" : String(row.travel_x),
      travel_y: row.travel_y == null ? "" : String(row.travel_y),
      travel_z: row.travel_z == null ? "" : String(row.travel_z),
      max_rpm: row.max_rpm == null ? "" : String(row.max_rpm),
      spindle_kw: row.spindle_kw == null ? "" : String(row.spindle_kw),
      bar_capacity_mm: row.bar_capacity_mm == null ? "" : String(row.bar_capacity_mm),
      chuck_mm: row.chuck_mm == null ? "" : String(row.chuck_mm),
    });
  }

  async function save() {
    setFormError("");
    const payload: Record<string, unknown> = {
      ...fields,
      axes: fields.axes ? Number(fields.axes) : null,
      travel_x: fields.travel_x ? Number(fields.travel_x) : null,
      travel_y: fields.travel_y ? Number(fields.travel_y) : null,
      travel_z: fields.travel_z ? Number(fields.travel_z) : null,
      rapid_x: fields.rapid_x ? Number(fields.rapid_x) : null,
      rapid_y: fields.rapid_y ? Number(fields.rapid_y) : null,
      rapid_z: fields.rapid_z ? Number(fields.rapid_z) : null,
      max_rpm: fields.max_rpm ? Number(fields.max_rpm) : null,
      spindle_kw: fields.spindle_kw ? Number(fields.spindle_kw) : null,
      bar_capacity_mm: fields.bar_capacity_mm ? Number(fields.bar_capacity_mm) : null,
      chuck_mm: fields.chuck_mm ? Number(fields.chuck_mm) : null,
    };
    try {
      if (editing?.id) await api.masterdataReplace("machines", String(editing.id), payload);
      else await api.masterdataCreate("machines", payload);
      setEditing(null);
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not save machine");
    }
  }

  const canonical = items.filter((row) => !superseded(row)).map((row) => ({ id: String(row.id), name: String(row.name) }));

  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm text-white/60">{loading ? "Loading machines…" : `${paged.total} machines`}</p>
        <AliasManager kind="machine" canonical={canonical} />
      </div>
      <Toolbar query={query} onQuery={setQuery} onAdd={() => { setEditing({}); setFields(EMPTY); }} addLabel="Add machine" />
      {error ? <p className="mb-2 text-sm text-red">{error}</p> : null}
      <table className="w-full text-left text-sm">
        <thead className="text-white/50">
          <tr>
            <th className="py-1">Name</th>
            <th>Type</th>
            <th>Control</th>
            <th>Axes</th>
            <th>Travels</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {paged.slice.map((row) => (
            <tr key={String(row.id)} className={`border-t border-white/10 ${superseded(row) ? "line-through opacity-50" : ""}`}>
              <td className="py-2">{text(row, "name")}</td>
              <td>{text(row, "machine_type")}</td>
              <td>
                {text(row, "control_make")} {text(row, "control_model")}
              </td>
              <td>{text(row, "axes")}</td>
              <td>
                {text(row, "travel_x")} / {text(row, "travel_y")} / {text(row, "travel_z")}
              </td>
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
        <Modal title={editing.id ? "Replace machine" : "Add machine"} onClose={() => setEditing(null)}>
          {(["name", "machine_type", "control_make", "control_model", "axes", "travel_x", "travel_y", "travel_z", "rapid_x", "max_rpm", "spindle_kw", "bar_capacity_mm", "chuck_mm", "capability_process"] as const).map(
            (key) => (
              <Field key={key} label={key.replaceAll("_", " ")} value={fields[key]} onChange={(value) => set(key, value)} />
            ),
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
