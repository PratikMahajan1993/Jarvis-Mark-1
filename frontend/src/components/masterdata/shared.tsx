"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { api } from "@/lib/api";
import { useToast, useTopic } from "@/sdk";

export type Row = Record<string, unknown>;

export function text(row: Row, key: string): string {
  const value = row[key];
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

export function superseded(row: Row): boolean {
  return Boolean(row.effective_to) || row.status === "superseded";
}

/** Active rows with every superseded predecessor listed directly underneath. */
export function groupWithHistory(items: Row[]): Array<{ current: Row; history: Row[] }> {
  const actives = items.filter((row) => !superseded(row));
  return actives.map((current) => {
    const history: Row[] = [];
    const queue = [String(current.id)];
    const seen = new Set<string>();
    while (queue.length) {
      const id = queue.shift()!;
      if (seen.has(id)) continue;
      seen.add(id);
      for (const row of items) {
        if (String(row.superseded_by ?? "") === id) {
          history.push(row);
          queue.push(String(row.id));
        }
      }
    }
    return { current, history };
  });
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

  useTopic<{ kind?: string; name?: string }>("masterdata.changed", () => {
    void reload();
  });

  return { items, error, loading, reload };
}

/** Desk + /masterdata toast for successful remote creates. */
export function useMasterdataChangedToast() {
  const { toast } = useToast();
  useTopic<{ kind?: string; name?: string }>("masterdata.changed", (data) => {
    const kind = (data?.kind || "Record").toString();
    const name = (data?.name || "").toString().trim();
    const label = kind.charAt(0).toUpperCase() + kind.slice(1);
    toast(name ? `${label} ${name} saved` : `${label} saved`);
  });
}

export function usePaged<T>(items: T[], query: string, keys: string[], getRow?: (item: T) => Row) {
  const [page, setPage] = useState(0);
  const pageSize = 8;
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return items;
    return items.filter((item) => {
      const row = getRow ? getRow(item) : (item as Row);
      return keys.some((key) => String(row[key] ?? "").toLowerCase().includes(needle));
    });
  }, [items, keys, query, getRow]);
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

export function YesNoField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: "yes" | "no" | "";
  onChange: (value: "yes" | "no") => void;
}) {
  return (
    <fieldset className="mb-3 text-sm text-white/70">
      <legend className="mb-1">{label}</legend>
      <div className="flex gap-3">
        {(["yes", "no"] as const).map((choice) => (
          <label key={choice} className="flex items-center gap-2">
            <input type="radio" name={label} checked={value === choice} onChange={() => onChange(choice)} />
            {choice === "yes" ? "Yes" : "No"}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ id: string; label: string }>;
}) {
  return (
    <label className="mb-3 block text-sm text-white/70">
      {label}
      <select
        className="mt-1 w-full rounded border border-white/10 bg-ink px-3 py-2 text-white"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Select…</option>
        {options.map((opt) => (
          <option key={opt.id} value={opt.id}>
            {opt.label}
          </option>
        ))}
      </select>
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

export function HistoryRow({ children }: { children: ReactNode }) {
  return <tr className="border-t border-white/5 bg-white/[0.02] text-white/45 line-through">{children}</tr>;
}
