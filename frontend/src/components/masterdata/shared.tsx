"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { api } from "@/lib/api";

export type Row = Record<string, unknown>;

export function text(row: Row, key: string): string {
  const value = row[key];
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

export function superseded(row: Row): boolean {
  return Boolean(row.effective_to) || row.status === "superseded";
}

export function useEntity(entity: string) {
  const [items, setItems] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.masterdataList(entity);
      setItems(data.items);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load master data");
    } finally {
      setLoading(false);
    }
  }, [entity]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { items, error, loading, reload };
}

export function usePaged(items: Row[], query: string, keys: string[]) {
  const [page, setPage] = useState(0);
  const pageSize = 8;
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return items;
    return items.filter((row) => keys.some((key) => String(row[key] ?? "").toLowerCase().includes(needle)));
  }, [items, keys, query]);
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pages - 1);
  const slice = filtered.slice(safePage * pageSize, safePage * pageSize + pageSize);
  return { slice, page: safePage, pages, setPage, total: filtered.length };
}

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg rounded-xl border border-white/10 bg-panel p-5 shadow-hud">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-xl text-cyan">{title}</h2>
          <button type="button" className="text-sm text-white/60" onClick={onClose}>
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="mb-3 block text-sm text-white/70">
      {label}
      <input
        className="mt-1 w-full rounded border border-white/10 bg-ink px-3 py-2 text-white"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

export function Toolbar({
  query,
  onQuery,
  onAdd,
  addLabel,
}: {
  query: string;
  onQuery: (value: string) => void;
  onAdd: () => void;
  addLabel: string;
}) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <input
        className="min-w-[12rem] flex-1 rounded border border-white/10 bg-ink px-3 py-2 text-sm"
        placeholder="Filter"
        value={query}
        onChange={(event) => onQuery(event.target.value)}
        aria-label="Filter rows"
      />
      <button type="button" className="rounded bg-cyan px-3 py-2 text-sm font-medium text-ink" onClick={onAdd}>
        {addLabel}
      </button>
    </div>
  );
}
