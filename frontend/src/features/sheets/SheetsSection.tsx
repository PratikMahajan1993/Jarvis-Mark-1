"use client";

import { useEffect, useState } from "react";
import { api, useFeatureQuery, type SectionProps } from "@/sdk";
import { SheetGraphic } from "./SheetGraphic";
import {
  EMPTY_SHEET_DRAFT,
  SHEET_FILLED_BY,
  SHEET_KINDS,
  filledByLabel,
  kindLabel,
  type SheetColumn,
  type SheetDraft,
  type SheetFilledBy,
  type SheetKind,
} from "./sheetDraft";

const fieldClass =
  "w-full rounded border border-[color:var(--border)] bg-black/30 px-2 py-1 text-sm text-[color:var(--fg)] outline-none";

function asDraft(raw: SheetDraft | undefined): SheetDraft {
  if (!raw) return EMPTY_SHEET_DRAFT;
  return {
    workbook_title: raw.workbook_title || "",
    tab_title: raw.tab_title || "",
    columns: (raw.columns || []).map((column) => ({
      name: column.name || "",
      kind: SHEET_KINDS.includes(column.kind) ? column.kind : "text",
      filled_by: SHEET_FILLED_BY.includes(column.filled_by) ? column.filled_by : "",
      formula: column.formula || "",
    })),
  };
}

function draftProblem(draft: SheetDraft): string | null {
  const names = draft.columns.map((column) => column.name.trim()).filter(Boolean);
  if (names.length !== draft.columns.length) return "Every column needs a name.";
  const seen = new Set<string>();
  for (const name of names) {
    const key = name.toLocaleLowerCase();
    if (seen.has(key)) return "Column names must be different.";
    seen.add(key);
  }
  return null;
}

export function SheetsSection(_props: SectionProps) {
  const query = useFeatureQuery<{ draft: SheetDraft; updated_at: string | null }>(
    ["sheets", "draft"],
    () => api.sheetDraft(),
    { topics: ["sheets.changed"] },
  );
  const [draft, setDraft] = useState<SheetDraft | null>(null);
  const [saveError, setSaveError] = useState("");

  useEffect(() => {
    if (draft === null && query.data?.draft) setDraft(asDraft(query.data.draft));
  }, [draft, query.data]);

  useEffect(() => {
    if (draft === null) return;
    const problem = draftProblem(draft);
    if (problem) return;
    const handle = window.setTimeout(() => {
      void api
        .saveSheetDraft(draft)
        .then(() => setSaveError(""))
        .catch(() => setSaveError("The draft did not save."));
    }, 400);
    return () => window.clearTimeout(handle);
  }, [draft]);

  const current = draft ?? asDraft(query.data?.draft);
  const problem = draftProblem(current);

  function patch(next: SheetDraft) {
    setDraft(next);
  }

  function patchColumn(index: number, column: SheetColumn) {
    const columns = current.columns.slice();
    columns[index] = column;
    patch({ ...current, columns });
  }

  return (
    <div className="grid h-full min-h-0 grid-cols-12 gap-4">
      <form
        className="col-span-4 flex min-h-0 flex-col gap-3 overflow-y-auto pr-1"
        onSubmit={(event) => event.preventDefault()}
      >
        <div>
          <h2 className="font-display text-lg text-[color:var(--fg)]">Sheet draft</h2>
          <p className="mt-1 text-sm text-[color:var(--muted)]">
            The grid is a picture of this draft. Nothing is written to Google.
          </p>
        </div>
        <label className="block text-sm text-[color:var(--muted)]">
          Workbook
          <input
            className={`${fieldClass} mt-1`}
            value={current.workbook_title}
            onChange={(event) => patch({ ...current, workbook_title: event.target.value })}
          />
        </label>
        <label className="block text-sm text-[color:var(--muted)]">
          Tab
          <input
            className={`${fieldClass} mt-1`}
            value={current.tab_title}
            onChange={(event) => patch({ ...current, tab_title: event.target.value })}
          />
        </label>
        <div className="flex flex-col gap-2">
          {current.columns.map((column, index) => (
            <div key={index} className="rounded border border-[color:var(--border)] p-2">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="font-mono text-[0.6rem] uppercase tracking-[0.12em] text-[color:var(--muted)]">
                  Column {index + 1}
                </span>
                <button
                  type="button"
                  className="font-mono text-[0.6rem] uppercase tracking-[0.1em] text-[color:var(--accent)]"
                  onClick={() =>
                    patch({ ...current, columns: current.columns.filter((_, item) => item !== index) })
                  }
                >
                  Remove
                </button>
              </div>
              <input
                className={fieldClass}
                aria-label={`Column ${index + 1} name`}
                value={column.name}
                onChange={(event) => patchColumn(index, { ...column, name: event.target.value })}
              />
              <div className="mt-2 grid grid-cols-2 gap-2">
                <select
                  className={fieldClass}
                  aria-label={`Column ${index + 1} kind`}
                  value={column.kind}
                  onChange={(event) =>
                    patchColumn(index, { ...column, kind: event.target.value as SheetKind })
                  }
                >
                  {SHEET_KINDS.map((kind) => (
                    <option key={kind} value={kind}>
                      {kindLabel(kind)}
                    </option>
                  ))}
                </select>
                <select
                  className={fieldClass}
                  aria-label={`Column ${index + 1} filled by`}
                  value={column.filled_by}
                  onChange={(event) =>
                    patchColumn(index, { ...column, filled_by: event.target.value as SheetFilledBy })
                  }
                >
                  {SHEET_FILLED_BY.map((filled) => (
                    <option key={filled || "open"} value={filled}>
                      {filled ? filledByLabel(filled) : "Open"}
                    </option>
                  ))}
                </select>
              </div>
              {column.kind === "formula" ? (
                <input
                  className={`${fieldClass} mt-2 font-mono`}
                  aria-label={`Column ${index + 1} formula`}
                  placeholder="Formula"
                  value={column.formula}
                  onChange={(event) => patchColumn(index, { ...column, formula: event.target.value })}
                />
              ) : null}
            </div>
          ))}
        </div>
        <button
          type="button"
          className="self-start font-mono text-[0.65rem] uppercase tracking-[0.12em] text-[color:var(--accent)]"
          onClick={() =>
            patch({
              ...current,
              columns: [...current.columns, { name: "", kind: "text", filled_by: "", formula: "" }],
            })
          }
        >
          Add column
        </button>
        {problem ? <p className="text-sm text-amber-200">{problem}</p> : null}
        {saveError ? <p className="text-sm text-amber-200">{saveError}</p> : null}
        {query.isLoading ? <p className="text-sm text-[color:var(--muted)]">Loading the draft…</p> : null}
        {query.isError ? (
          <p className="text-sm text-amber-200">The draft could not be loaded.</p>
        ) : null}
      </form>
      <div className="col-span-8 min-h-0 self-end overflow-auto pb-2">
        <SheetGraphic draft={current} />
      </div>
    </div>
  );
}
