"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type QuoteOperation } from "@/lib/api";

const TEMPLATES = [
  ["turning", "Turning"],
  ["milling", "Milling"],
  ["edm", "EDM"],
  ["heat_treat", "Heat treat"],
  ["plating", "Plating"],
  ["grinding", "Grinding"],
] as const;

const CASES = [
  ["no_machine", "No machine"],
  ["customer_asked", "Customer asked"],
  ["capacity", "Capacity"],
  ["not_in_house", "Not in-house"],
] as const;

const field =
  "w-full rounded border border-[color:var(--border)] bg-transparent px-1 py-0.5 font-mono text-[10px]";

export function OperationEditor({ sessionId }: { sessionId: string }) {
  const [rows, setRows] = useState<QuoteOperation[]>([]);
  const [note, setNote] = useState("");
  const [adding, setAdding] = useState(false);

  const reload = useCallback((next?: QuoteOperation[]) => {
    if (next) {
      setRows(next);
      return;
    }
    void api.quoteOperations(sessionId).then((result) => setRows(result.operations || [])).catch(() => setNote("Could not load operations."));
  }, [sessionId]);

  useEffect(() => {
    reload();
  }, [reload]);

  function save(row: QuoteOperation) {
    void api.updateQuoteOperation(sessionId, row).then((result) => {
      if (result.operations) setRows(result.operations);
      if (!result.ok) setNote(result.message || "Could not update that operation.");
    });
  }

  function move(from: number, to: number) {
    if (to < 0 || to >= rows.length || from === to) return;
    const next = rows.slice();
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    setRows(next);
    void api.reorderQuoteOperations(sessionId, next.map((row) => row.id)).then((result) => {
      if (result.operations) setRows(result.operations);
    });
  }

  return (
    <section className="space-y-2" data-operation-editor>
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-mono text-[9px] uppercase tracking-[0.18em] text-[color:var(--muted)]/75">
          Operations
        </h3>
        <button
          type="button"
          className="font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--accent)]"
          onClick={() => setAdding((open) => !open)}
        >
          Add operation
        </button>
      </div>
      {adding ? (
        <div className="flex flex-wrap gap-1" role="dialog" aria-label="Operation templates">
          {TEMPLATES.map(([id, label]) => (
            <button
              key={id}
              type="button"
              className="rounded border border-[color:var(--border)] px-2 py-1 font-mono text-[10px]"
              onClick={() => {
                void api.addQuoteOperation(sessionId, id).then((result) => {
                  if (result.operations) setRows(result.operations);
                  setAdding(false);
                  if (!result.ok) setNote(result.message || "Could not add that operation.");
                });
              }}
            >
              {label}
            </button>
          ))}
        </div>
      ) : null}
      {rows.length === 0 ? (
        <p className="font-mono text-[10px] text-[color:var(--muted)]">No operations yet.</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((row, index) => (
            <li
              key={row.id}
              draggable
              onDragStart={(event) => event.dataTransfer.setData("text/plain", String(index))}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                const from = Number(event.dataTransfer.getData("text/plain"));
                if (!Number.isNaN(from)) move(from, index);
              }}
              className="space-y-1 rounded border border-[color:var(--border)]/60 p-1"
            >
              <div className="flex gap-1">
                <input
                  aria-label="Operation name"
                  className={field}
                  value={row.operation}
                  onChange={(event) => {
                    const next = rows.slice();
                    next[index] = { ...row, operation: event.target.value };
                    setRows(next);
                  }}
                  onBlur={() => save(rows[index])}
                />
                <input
                  aria-label="Machine"
                  className={field}
                  placeholder="Machine"
                  value={row.machine_type}
                  onChange={(event) => {
                    const next = rows.slice();
                    next[index] = { ...row, machine_type: event.target.value };
                    setRows(next);
                  }}
                  onBlur={() => save(rows[index])}
                />
                <button
                  type="button"
                  aria-label={`Delete ${row.operation}`}
                  className="px-1 font-mono text-[10px] text-[color:var(--muted)]"
                  onClick={() => {
                    void api.deleteQuoteOperation(sessionId, row.id).then((result) => {
                      if (result.operations) setRows(result.operations);
                    });
                  }}
                >
                  Delete
                </button>
              </div>
              <label className="flex items-center gap-2 font-mono text-[10px] text-[color:var(--muted)]">
                <input
                  type="checkbox"
                  checked={Boolean(row.outsource)}
                  onChange={(event) => {
                    const nextRow = { ...row, outsource: event.target.checked ? 1 : 0 };
                    const next = rows.slice();
                    next[index] = nextRow;
                    setRows(next);
                    save(nextRow);
                  }}
                />
                Outsource
              </label>
              {row.outsource ? (
                <div className="grid gap-1">
                  <select
                    aria-label="Outsource case"
                    className={field}
                    value={row.outsource_case}
                    onChange={(event) => {
                      const nextRow = { ...row, outsource_case: event.target.value };
                      const next = rows.slice();
                      next[index] = nextRow;
                      setRows(next);
                      save(nextRow);
                    }}
                  >
                    <option value="">Case</option>
                    {CASES.map(([id, label]) => (
                      <option key={id} value={id}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <input
                    aria-label="Vendor"
                    className={field}
                    placeholder="Vendor"
                    value={row.outsource_vendor}
                    onChange={(event) => {
                      const next = rows.slice();
                      next[index] = { ...row, outsource_vendor: event.target.value };
                      setRows(next);
                    }}
                    onBlur={() => save(rows[index])}
                  />
                  <input
                    aria-label="Outsource price INR"
                    className={field}
                    placeholder="Quote price INR"
                    value={row.outsource_price_minor == null ? "" : String(row.outsource_price_minor / 100)}
                    onChange={(event) => {
                      const parsed = Number(event.target.value);
                      const next = rows.slice();
                      next[index] = {
                        ...row,
                        outsource_price_minor: event.target.value.trim() && !Number.isNaN(parsed) ? Math.round(parsed * 100) : null,
                      };
                      setRows(next);
                    }}
                    onBlur={() => save(rows[index])}
                  />
                  <label className="flex items-center gap-2 font-mono text-[10px] text-[color:var(--muted)]">
                    <input
                      type="checkbox"
                      checked={Boolean(row.outsource_received)}
                      onChange={(event) => {
                        const nextRow = { ...row, outsource_received: event.target.checked ? 1 : 0 };
                        const next = rows.slice();
                        next[index] = nextRow;
                        setRows(next);
                        save(nextRow);
                      }}
                    />
                    Received
                  </label>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-1">
                  <input
                    aria-label="Setup INR"
                    className={field}
                    placeholder="Setup INR"
                    value={row.setup_minor == null ? "" : String(row.setup_minor / 100)}
                    onChange={(event) => {
                      const parsed = Number(event.target.value);
                      const next = rows.slice();
                      next[index] = {
                        ...row,
                        setup_minor: event.target.value.trim() && !Number.isNaN(parsed) ? Math.round(parsed * 100) : null,
                      };
                      setRows(next);
                    }}
                    onBlur={() => save(rows[index])}
                  />
                  <input
                    aria-label="Cycle minutes"
                    className={field}
                    placeholder="Cycle min"
                    value={row.cycle_min == null ? "" : String(row.cycle_min)}
                    onChange={(event) => {
                      const parsed = Number(event.target.value);
                      const next = rows.slice();
                      next[index] = {
                        ...row,
                        cycle_min: event.target.value.trim() && !Number.isNaN(parsed) ? parsed : null,
                      };
                      setRows(next);
                    }}
                    onBlur={() => save(rows[index])}
                  />
                </div>
              )}
              <input
                aria-label="Special tooling"
                className={field}
                placeholder="Special tooling"
                value={row.special_tooling}
                onChange={(event) => {
                  const next = rows.slice();
                  next[index] = { ...row, special_tooling: event.target.value };
                  setRows(next);
                }}
                onBlur={() => save(rows[index])}
              />
            </li>
          ))}
        </ul>
      )}
      {note ? <p className="font-mono text-[10px] text-[color:var(--muted)]">{note}</p> : null}
    </section>
  );
}
