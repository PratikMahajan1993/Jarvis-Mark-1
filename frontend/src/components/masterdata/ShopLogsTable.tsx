"use client";

import { Fragment, useEffect, useState } from "react";

import { api } from "@/lib/api";

import { Field, Modal, SelectField, Toolbar, text, useEntity, usePaged, type Row } from "./shared";

const EMPTY = {
  display_name: "",
  spreadsheet_url: "",
  tab_name: "",
  account_id: "",
  col_date: "Date",
  col_machine: "Machine",
  col_job: "Job",
  col_qty: "Qty",
  col_downtime: "Downtime",
};

export function ShopLogsTable() {
  const { items, error, loading, reload } = useEntity("listened-sheets");
  const [query, setQuery] = useState("");
  const active = items.filter((row) => !row.effective_to && row.status !== "superseded");
  const paged = usePaged(active, query, ["display_name", "tab_name", "spreadsheet_id", "account_label"], (r) => r);
  const [editing, setEditing] = useState<Row | null>(null);
  const [fields, setFields] = useState(EMPTY);
  const [formError, setFormError] = useState("");
  const [accounts, setAccounts] = useState<Array<{ id: string; label: string; connected?: boolean }>>([]);

  useEffect(() => {
    void api.masterdataGoogleAccounts().then((data) => {
      setAccounts(
        (data.items || []).map((row) => ({
          id: String(row.id),
          label: String(row.label),
          connected: Boolean(row.connected),
        })),
      );
    });
  }, []);

  function openNew() {
    setEditing({});
    setFields({
      ...EMPTY,
      account_id: accounts[0]?.id || "",
    });
    setFormError("");
  }

  function openEdit(row: Row) {
    const map = (row.column_map || {}) as Record<string, string>;
    setEditing(row);
    setFields({
      display_name: String(row.display_name ?? ""),
      spreadsheet_url: String(row.spreadsheet_url ?? ""),
      tab_name: String(row.tab_name ?? ""),
      account_id: String(row.account_id ?? ""),
      col_date: String(map.date ?? "Date"),
      col_machine: String(map.machine ?? "Machine"),
      col_job: String(map.job ?? "Job"),
      col_qty: String(map.qty ?? "Qty"),
      col_downtime: String(map.downtime ?? "Downtime"),
    });
    setFormError("");
  }

  async function save() {
    setFormError("");
    if (!fields.spreadsheet_url.trim() || !fields.tab_name.trim() || !fields.account_id) {
      setFormError("Link, tab name, and account are required");
      return;
    }
    const payload = {
      display_name: fields.display_name || fields.tab_name,
      spreadsheet_url: fields.spreadsheet_url,
      tab_name: fields.tab_name,
      account_id: fields.account_id,
      column_map: {
        date: fields.col_date,
        machine: fields.col_machine,
        job: fields.col_job,
        qty: fields.col_qty,
        downtime: fields.col_downtime,
      },
    };
    try {
      if (editing?.id) {
        await api.masterdataReplace("listened-sheets", String(editing.id), {
          display_name: payload.display_name,
          column_map: payload.column_map,
        });
      } else {
        await api.masterdataCreate("listened-sheets", payload);
      }
      setEditing(null);
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not save shop log");
    }
  }

  async function retire(row: Row) {
    try {
      await api.masterdataRetireListenedSheet(String(row.id));
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not retire binding");
    }
  }

  async function refresh(row: Row) {
    try {
      await api.masterdataRefreshListenedSheet(String(row.id));
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not refresh");
    }
  }

  return (
    <section>
      <p className="mb-2 text-sm text-white/60">
        {loading
          ? "Loading shop logs…"
          : `${paged.total} listened tab${paged.total === 1 ? "" : "s"}. Read only — Jarvis never writes these sheets.`}
      </p>
      <Toolbar query={query} onQuery={setQuery} onAdd={openNew} addLabel="Add shop log" />
      {formError && !editing ? <p className="mb-2 text-sm text-red">{formError}</p> : null}
      {error ? <p className="mb-2 text-sm text-red">{error}</p> : null}
      <table className="w-full text-left text-sm">
        <thead className="text-white/50">
          <tr>
            <th className="py-1">Name</th>
            <th>Account</th>
            <th>Tab</th>
            <th>Last read</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {paged.slice.map((row) => (
            <Fragment key={String(row.id)}>
              <tr className="border-t border-white/10">
                <td className="py-2">{text(row, "display_name")}</td>
                <td>{text(row, "account_label")}</td>
                <td>{text(row, "tab_name")}</td>
                <td className="font-mono text-xs">{text(row, "last_read_at")}</td>
                <td>{row.stale ? "stale" : row.column_map_ready ? "ready" : "needs date map"}</td>
                <td className="space-x-2 text-right">
                  <button type="button" className="text-cyan" onClick={() => void refresh(row)}>
                    Refresh
                  </button>
                  <button type="button" className="text-cyan" onClick={() => openEdit(row)}>
                    Edit map
                  </button>
                  <button type="button" className="text-white/50" onClick={() => void retire(row)}>
                    Retire
                  </button>
                </td>
              </tr>
            </Fragment>
          ))}
        </tbody>
      </table>

      {editing ? (
        <Modal title={editing.id ? "Edit column map" : "Add shop log"} onClose={() => setEditing(null)}>
          {formError ? <p className="mb-2 text-sm text-red">{formError}</p> : null}
          <Field
            label="Display name"
            value={fields.display_name}
            onChange={(value) => setFields({ ...fields, display_name: value })}
          />
          {!editing.id ? (
            <>
              <Field
                label="Spreadsheet link"
                value={fields.spreadsheet_url}
                onChange={(value) => setFields({ ...fields, spreadsheet_url: value })}
              />
              <Field
                label="Tab name (exact)"
                value={fields.tab_name}
                onChange={(value) => setFields({ ...fields, tab_name: value })}
              />
              <SelectField
                label="Google account"
                value={fields.account_id}
                onChange={(value) => setFields({ ...fields, account_id: value })}
                options={accounts.map((a) => ({
                  id: a.id,
                  label: `${a.label}${a.connected ? "" : " (not connected)"}`,
                }))}
              />
            </>
          ) : null}
          <p className="mb-2 text-xs text-white/50">Header names as they appear in row 1 of the tab.</p>
          <Field label="Date column" value={fields.col_date} onChange={(value) => setFields({ ...fields, col_date: value })} />
          <Field
            label="Machine column"
            value={fields.col_machine}
            onChange={(value) => setFields({ ...fields, col_machine: value })}
          />
          <Field label="Job column" value={fields.col_job} onChange={(value) => setFields({ ...fields, col_job: value })} />
          <Field label="Qty column" value={fields.col_qty} onChange={(value) => setFields({ ...fields, col_qty: value })} />
          <Field
            label="Downtime column"
            value={fields.col_downtime}
            onChange={(value) => setFields({ ...fields, col_downtime: value })}
          />
          <button type="button" className="rounded bg-cyan px-3 py-2 text-sm font-medium text-ink" onClick={() => void save()}>
            Save
          </button>
        </Modal>
      ) : null}
    </section>
  );
}
