"use client";

import { useState } from "react";

import { api } from "@/lib/api";

import { Modal, Field } from "./shared";

type Canonical = { id: string; name: string };

export function AliasManager({ kind, canonical }: { kind: "customer" | "machine" | "vendor"; canonical: Canonical[] }) {
  const [open, setOpen] = useState(false);
  const [alias, setAlias] = useState("");
  const [canonicalId, setCanonicalId] = useState(canonical[0]?.id ?? "");
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const data = await api.masterdataAliases(kind);
    setRows(data.items);
  }

  async function openManager() {
    setOpen(true);
    setNotice("");
    setError("");
    try {
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load aliases");
    }
  }

  async function checkAlias(value: string) {
    setAlias(value);
    if (!value.trim()) {
      setNotice("");
      return;
    }
    try {
      const resolved = await api.masterdataResolve(kind, value.trim());
      setNotice(
        resolved.resolved
          ? "That alias is already attached."
          : "No exact match. Choose the canonical record. A similar spelling will not be guessed.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not resolve alias");
    }
  }

  async function save() {
    setError("");
    try {
      await api.masterdataAddAlias(kind, canonicalId, alias.trim());
      setAlias("");
      setNotice("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add alias");
    }
  }

  async function remove(value: string) {
    setError("");
    try {
      await api.masterdataRemoveAlias(kind, value);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove alias");
    }
  }

  return (
    <>
      <button type="button" className="text-sm text-cyan underline" onClick={() => void openManager()}>
        Alias manager
      </button>
      {open ? (
        <Modal title="Aliases" onClose={() => setOpen(false)}>
          <p className="mb-3 text-sm text-white/60">Exact spelling only. An unknown alias stays unresolved until you attach it.</p>
          <table className="mb-4 w-full text-left text-sm">
            <thead className="text-white/50">
              <tr>
                <th className="py-1">Alias</th>
                <th>Canonical</th>
                <th>Source</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={String(row.alias)} className="border-t border-white/10">
                  <td className="py-2">{String(row.alias)}</td>
                  <td>{String(row.canonical_name)}</td>
                  <td>{String(row.source)}</td>
                  <td>
                    <button type="button" className="text-amber" onClick={() => void remove(String(row.alias))}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Field label="Alias" value={alias} onChange={(value) => void checkAlias(value)} />
          <label className="mb-3 block text-sm text-white/70">
            Canonical record
            <select
              className="mt-1 w-full rounded border border-white/10 bg-ink px-3 py-2 text-white"
              value={canonicalId}
              onChange={(event) => setCanonicalId(event.target.value)}
            >
              {canonical.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          {notice ? <p className="mb-2 text-sm text-white/70">{notice}</p> : null}
          {error ? <p className="mb-2 text-sm text-red">{error}</p> : null}
          <button type="button" className="rounded bg-cyan px-3 py-2 text-sm font-medium text-ink" onClick={() => void save()}>
            Add alias
          </button>
        </Modal>
      ) : null}
    </>
  );
}
