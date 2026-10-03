"use client";

import {
  SHEET_BLANK_ROWS,
  filledByLabel,
  kindLabel,
  type SheetDraft,
} from "./sheetDraft";

/** Graphic of the draft. Cells stay empty. This is not a Google sheet. */
export function SheetGraphic({ draft }: { draft: SheetDraft }) {
  const tab = draft.tab_title.trim() || "Untitled";
  const workbook = draft.workbook_title.trim() || "Workbook not chosen";
  const columns = draft.columns.filter((column) => column.name.trim());

  return (
    <div className="min-w-0">
      <div className="inline-flex max-w-full items-center rounded-t-md border border-b-0 border-[color:var(--border)] bg-[color:var(--bg)] px-4 py-1.5">
        <span className="truncate font-display text-sm text-[color:var(--fg)]">{tab}</span>
      </div>
      <div className="overflow-hidden rounded-b-lg rounded-tr-lg border border-[color:var(--border)] bg-[color:var(--bg)]">
        <div className="flex items-baseline justify-between gap-3 border-b border-[color:var(--border)] px-3 py-2">
          <p className="truncate font-mono text-[0.65rem] uppercase tracking-[0.14em] text-[color:var(--muted)]">
            {workbook}
          </p>
          <p className="shrink-0 font-mono text-[0.6rem] uppercase tracking-[0.12em] text-[color:var(--accent)]">
            Preview
          </p>
        </div>
        {columns.length === 0 ? (
          <p className="px-4 py-10 text-sm text-[color:var(--muted)]">
            Name a column and it will appear in this grid.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left" aria-label={`Preview of ${tab}`}>
              <thead>
                <tr>
                  <th className="w-8 border-b border-r border-[color:var(--border)] bg-[color:var(--surface)]" />
                  {columns.map((column) => {
                    const who = filledByLabel(column.filled_by);
                    return (
                      <th
                        key={column.name}
                        className="min-w-[8.5rem] border-b border-r border-[color:var(--border)] bg-[color:var(--surface)] px-2 py-2 align-top last:border-r-0"
                      >
                        <div className="text-sm font-medium text-[color:var(--fg)]">{column.name}</div>
                        <div className="mt-1 font-mono text-[0.6rem] uppercase tracking-[0.08em] text-[color:var(--muted)]">
                          {kindLabel(column.kind)}
                          {who ? ` · ${who}` : ""}
                        </div>
                        {column.kind === "formula" && column.formula ? (
                          <div className="mt-1 truncate font-mono text-[0.65rem] text-[color:var(--accent)]">
                            {column.formula}
                          </div>
                        ) : null}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: SHEET_BLANK_ROWS }, (_, row) => (
                  <tr key={row}>
                    <td className="border-b border-r border-[color:var(--border)] bg-[color:var(--bg)] px-1 py-2 text-center font-mono text-[0.6rem] text-[color:var(--muted)]">
                      {row + 1}
                    </td>
                    {columns.map((column) => (
                      <td
                        key={`${column.name}-${row}`}
                        className="h-9 border-b border-r border-[color:var(--border)] bg-[color:var(--bg)] last:border-r-0"
                      />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
