"""Read-only shop sheet listening. Named tabs only; never writes Google Sheets."""

from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from . import db
from .config import settings
from .connectors import google_auth
from .connectors import sheets
from .connectors.sheets import SheetNotFoundError
from .core.features import publish

COLUMN_KEYS = ("date", "machine", "job", "qty", "downtime")
_MISSING = object()


class ListenError(ValueError):
    """Binding or refresh rejected."""


def _today_local() -> str:
    return datetime.now(ZoneInfo(settings.tz)).date().isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def normalize_column_map(raw: Any) -> dict[str, str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as exc:
            raise ListenError("column_map must be JSON object") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ListenError("column_map must be an object of header names")
    out: dict[str, str] = {}
    for key in COLUMN_KEYS:
        header = str(raw.get(key) or "").strip()
        if header:
            out[key] = header
    return out


def column_map_ready(column_map: dict[str, str]) -> bool:
    """A sheet counts as current-state only when the date header is mapped."""
    return bool(str(column_map.get("date") or "").strip())


def _cell_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _parse_date_iso(value: Any) -> str | None:
    if _cell_missing(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # Google Sheets serial date (days since 1899-12-30).
        try:
            return (date(1899, 12, 30) + timedelta(days=int(value))).isoformat()
        except (OverflowError, ValueError):
            return None
    text = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    for fmt in (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d %b %Y",
        "%d %B %Y",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_qty(value: Any) -> int | None | object:
    """Integer piece count when present; empty stays missing (never invent zero)."""
    if _cell_missing(value):
        return _MISSING
    if isinstance(value, bool):
        return _MISSING
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return int(round(value))
    text = str(value).strip().replace(",", "")
    if not text:
        return _MISSING
    try:
        number = float(text)
    except ValueError:
        return _MISSING
    if number.is_integer():
        return int(number)
    return int(round(number))


def _parse_downtime(value: Any) -> float | None | object:
    if _cell_missing(value):
        return _MISSING
    if isinstance(value, bool):
        return _MISSING
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return _MISSING
    try:
        return float(text)
    except ValueError:
        return _MISSING


def _header_index(headers: list[str], name: str) -> int | None:
    needle = name.strip().lower()
    for index, header in enumerate(headers):
        if str(header or "").strip().lower() == needle:
            return index
    return None


def mapped_row(
    headers: list[str],
    values: list[Any],
    column_map: dict[str, str],
) -> dict[str, Any]:
    """Map one raw row. Empty cells stay missing (None); never coerce to 0."""
    out: dict[str, Any] = {
        "date": None,
        "machine": None,
        "job": None,
        "qty": None,
        "downtime": None,
        "missing": [],
    }
    for key in COLUMN_KEYS:
        header = column_map.get(key)
        if not header:
            out["missing"].append(key)
            continue
        index = _header_index(headers, header)
        if index is None:
            out["missing"].append(key)
            continue
        raw = values[index] if index < len(values) else None
        if key == "date":
            parsed = _parse_date_iso(raw)
            if parsed is None:
                out["missing"].append(key)
                out["date"] = None
            else:
                out["date"] = parsed
        elif key == "machine":
            if _cell_missing(raw):
                out["missing"].append(key)
                out["machine"] = None
            else:
                out["machine"] = str(raw).strip()
        elif key == "job":
            if _cell_missing(raw):
                out["missing"].append(key)
                out["job"] = None
            else:
                out["job"] = str(raw).strip()
        elif key == "qty":
            parsed_qty = _parse_qty(raw)
            if parsed_qty is _MISSING:
                out["missing"].append(key)
                out["qty"] = None
            else:
                out["qty"] = parsed_qty
        elif key == "downtime":
            parsed_dt = _parse_downtime(raw)
            if parsed_dt is _MISSING:
                out["missing"].append(key)
                out["downtime"] = None
            else:
                out["downtime"] = parsed_dt
    return out


def today_rows(
    headers: list[str],
    rows: list[list[Any]],
    column_map: dict[str, str],
    today: str | None = None,
) -> list[dict[str, Any]]:
    """Rows whose mapped date is today in settings.tz. No date map → no today rows."""
    if not column_map_ready(column_map):
        return []
    day = today or _today_local()
    out: list[dict[str, Any]] = []
    for values in rows:
        mapped = mapped_row(headers, values, column_map)
        if mapped.get("date") == day:
            out.append(mapped)
    return out


def detect_conflicts(sheet_today: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """When two sheets disagree on a figure, state both values and sources. No winner."""
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for sheet in sheet_today:
        display = str(sheet.get("display_name") or sheet.get("id") or "")
        sheet_id = str(sheet.get("id") or "")
        for row in sheet.get("today") or []:
            machine = str(row.get("machine") or "").strip()
            if not machine:
                continue
            job = str(row.get("job") or "").strip()
            for field in ("qty", "downtime"):
                value = row.get(field)
                if value is None:
                    continue
                key = (machine.lower(), job.lower(), field)
                buckets.setdefault(key, []).append(
                    {
                        "sheet_id": sheet_id,
                        "display_name": display,
                        "machine": machine,
                        "job": job or None,
                        "field": field,
                        "value": value,
                    }
                )
    conflicts: list[dict[str, Any]] = []
    for (_machine, _job, field), entries in buckets.items():
        distinct = {json.dumps(entry["value"], sort_keys=True, default=str) for entry in entries}
        sources = {entry["sheet_id"] for entry in entries}
        if len(distinct) > 1 and len(sources) > 1:
            conflicts.append(
                {
                    "machine": entries[0]["machine"],
                    "job": entries[0]["job"],
                    "field": field,
                    "values": [
                        {
                            "sheet_id": e["sheet_id"],
                            "display_name": e["display_name"],
                            "value": e["value"],
                        }
                        for e in entries
                    ],
                }
            )
    return conflicts


def _account_row(conn, account_id: str | None = None, label: str | None = None) -> dict[str, Any] | None:
    if account_id:
        row = conn.execute("SELECT * FROM google_accounts WHERE id = ?", (account_id,)).fetchone()
    elif label:
        row = conn.execute(
            "SELECT * FROM google_accounts WHERE label = ?",
            (google_auth.normalize_account(label),),
        ).fetchone()
    else:
        return None
    return dict(row) if row else None


def list_google_accounts() -> list[dict[str, Any]]:
    with db.connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM google_accounts ORDER BY label").fetchall()]
    out: list[dict[str, Any]] = []
    for row in rows:
        label = str(row["label"])
        st = google_auth.account_status(label)
        out.append(
            {
                **row,
                "connected": st["connected"],
                "sheets": st["sheets"],
                "calendar": st["calendar"],
            }
        )
    return out


def list_listened_sheets(*, include_retired: bool = True) -> list[dict[str, Any]]:
    with db.connect() as conn:
        sql = """
            SELECT ls.*, ga.label AS account_label, ga.token_filename
            FROM listened_sheets ls
            JOIN google_accounts ga ON ga.id = ls.account_id
        """
        if not include_retired:
            sql += " WHERE ls.effective_to IS NULL AND COALESCE(ls.status, '') != 'superseded'"
        sql += " ORDER BY ls.display_name COLLATE NOCASE, ls.effective_from"
        items = [dict(r) for r in conn.execute(sql).fetchall()]
    for item in items:
        item["column_map"] = normalize_column_map(item.pop("column_map_json", "{}"))
        item["stale"] = bool(item.get("last_error"))
        item["column_map_ready"] = column_map_ready(item["column_map"])
        snap = _load_snapshot(item["id"])
        item["last_read_at"] = snap.get("read_at") if snap else item.get("last_ok_at")
        item["has_snapshot"] = snap is not None
    return items


def create_listened_sheet(fields: dict[str, Any]) -> dict[str, Any]:
    link = str(fields.get("spreadsheet_url") or fields.get("link") or fields.get("spreadsheet_id") or "").strip()
    spreadsheet_id = sheets.spreadsheet_id_from(link) or str(fields.get("spreadsheet_id") or "").strip()
    if not spreadsheet_id:
        raise ListenError("Paste a Google Sheets link or spreadsheet id")
    tab_name = str(fields.get("tab_name") or "").strip()
    if not tab_name:
        raise ListenError("Tab name is required")
    display_name = str(fields.get("display_name") or tab_name).strip() or tab_name
    account_id = str(fields.get("account_id") or "").strip()
    account_label = str(fields.get("account") or fields.get("account_label") or "").strip()
    column_map = normalize_column_map(fields.get("column_map") or {
        "date": fields.get("col_date"),
        "machine": fields.get("col_machine"),
        "job": fields.get("col_job"),
        "qty": fields.get("col_qty"),
        "downtime": fields.get("col_downtime"),
    })
    with db.connect() as conn:
        account = _account_row(conn, account_id=account_id or None, label=account_label or None)
        if not account:
            raise ListenError("Pick the shop or staff Google account")
        existing = conn.execute(
            """
            SELECT * FROM listened_sheets
            WHERE spreadsheet_id = ? AND tab_name = ?
              AND effective_to IS NULL AND COALESCE(status, '') != 'superseded'
            LIMIT 1
            """,
            (spreadsheet_id, tab_name),
        ).fetchone()
        if existing:
            raise ListenError(f"Already listening to that link and tab ({existing['display_name']})")
        row_id = _new_id("lsheet")
        now = db.utc_now()
        url = str(fields.get("spreadsheet_url") or "").strip() or sheets.spreadsheet_url(spreadsheet_id)
        conn.execute(
            """
            INSERT INTO listened_sheets (
              id, account_id, spreadsheet_id, spreadsheet_url, tab_name, display_name,
              column_map_json, last_ok_at, last_error, status, effective_from, effective_to, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, 'active', ?, NULL, NULL)
            """,
            (
                row_id,
                account["id"],
                spreadsheet_id,
                url,
                tab_name,
                display_name,
                json.dumps(column_map),
                now,
            ),
        )
    publish("masterdata.changed", {"kind": "listened_sheet", "name": display_name, "id": row_id})
    publish("sheet-listen.changed", {"id": row_id, "op": "create"})
    return {"ok": True, "id": row_id}


def retire_listened_sheet(row_id: str) -> dict[str, Any]:
    """End-date a binding. Never hard-delete authoritative rows or their snapshots."""
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM listened_sheets WHERE id = ?", (row_id,)).fetchone()
        if not row:
            raise ListenError("Listened sheet not found")
        if row["effective_to"] or row["status"] == "superseded":
            return {"ok": True, "id": row_id, "already_retired": True}
        now = db.utc_now()
        conn.execute(
            """
            UPDATE listened_sheets
            SET effective_to = ?, status = 'superseded'
            WHERE id = ?
            """,
            (now, row_id),
        )
    publish("masterdata.changed", {"kind": "listened_sheet", "name": row["display_name"], "id": row_id})
    publish("sheet-listen.changed", {"id": row_id, "op": "retire"})
    return {"ok": True, "id": row_id, "retired": True}


def update_listened_sheet(row_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Update column map / display name on the active row (no hard delete)."""
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM listened_sheets WHERE id = ?", (row_id,)).fetchone()
        if not row:
            raise ListenError("Listened sheet not found")
        if row["effective_to"] or row["status"] == "superseded":
            raise ListenError("That binding is retired; add a new one")
        display_name = str(fields.get("display_name") or row["display_name"]).strip() or row["display_name"]
        if "column_map" in fields:
            column_map = normalize_column_map(fields.get("column_map"))
        elif any(f"col_{k}" in fields for k in COLUMN_KEYS):
            base = normalize_column_map(row["column_map_json"])
            column_map = normalize_column_map(
                {
                    "date": fields["col_date"] if "col_date" in fields else base.get("date"),
                    "machine": fields["col_machine"] if "col_machine" in fields else base.get("machine"),
                    "job": fields["col_job"] if "col_job" in fields else base.get("job"),
                    "qty": fields["col_qty"] if "col_qty" in fields else base.get("qty"),
                    "downtime": fields["col_downtime"] if "col_downtime" in fields else base.get("downtime"),
                }
            )
        else:
            column_map = normalize_column_map(row["column_map_json"])
        conn.execute(
            """
            UPDATE listened_sheets
            SET display_name = ?, column_map_json = ?
            WHERE id = ?
            """,
            (display_name, json.dumps(column_map), row_id),
        )
    publish("masterdata.changed", {"kind": "listened_sheet", "name": display_name, "id": row_id})
    publish("sheet-listen.changed", {"id": row_id, "op": "update"})
    return {"ok": True, "id": row_id}


def _load_snapshot(listened_sheet_id: str) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM sheet_snapshots WHERE listened_sheet_id = ?",
            (listened_sheet_id,),
        ).fetchone()
    if not row:
        return None
    try:
        headers = json.loads(row["headers_json"] or "[]")
        rows = json.loads(row["rows_json"] or "[]")
    except json.JSONDecodeError:
        return None
    return {
        "listened_sheet_id": listened_sheet_id,
        "read_at": row["read_at"],
        "headers": headers if isinstance(headers, list) else [],
        "rows": rows if isinstance(rows, list) else [],
    }


def _store_snapshot(listened_sheet_id: str, headers: list[Any], rows: list[list[Any]], read_at: str) -> None:
    # Empty cells already None from sheets.read_sheet; keep them missing, never zero.
    headers_json = json.dumps(list(headers))
    rows_json = json.dumps([[(None if _cell_missing(cell) else cell) for cell in row] for row in rows])
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO sheet_snapshots (listened_sheet_id, read_at, headers_json, rows_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(listened_sheet_id) DO UPDATE SET
              read_at = excluded.read_at,
              headers_json = excluded.headers_json,
              rows_json = excluded.rows_json
            """,
            (listened_sheet_id, read_at, headers_json, rows_json),
        )


def _set_sheet_error(listened_sheet_id: str, error: str) -> None:
    with db.connect() as conn:
        conn.execute(
            "UPDATE listened_sheets SET last_error = ? WHERE id = ?",
            (error, listened_sheet_id),
        )


def _set_sheet_ok(listened_sheet_id: str, when: str) -> None:
    with db.connect() as conn:
        conn.execute(
            "UPDATE listened_sheets SET last_ok_at = ?, last_error = NULL WHERE id = ?",
            (when, listened_sheet_id),
        )


def refresh_listened_sheet(listened_sheet_id: str) -> dict[str, Any]:
    """Read the named tab into the local copy. Never writes Google. Keeps last copy on failure."""
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT ls.*, ga.label AS account_label
            FROM listened_sheets ls
            JOIN google_accounts ga ON ga.id = ls.account_id
            WHERE ls.id = ?
            """,
            (listened_sheet_id,),
        ).fetchone()
    if not row:
        raise ListenError("Listened sheet not found")
    if row["effective_to"] or row["status"] == "superseded":
        raise ListenError("That binding is retired")
    account = str(row["account_label"])
    spreadsheet_id = str(row["spreadsheet_id"])
    tab_name = str(row["tab_name"])
    display_name = str(row["display_name"])

    if not google_auth.connected(account):
        msg = f"Google account {account!r} is not connected. Reconnect in Preferences."
        _set_sheet_error(listened_sheet_id, msg)
        publish("sheet-listen.changed", {"id": listened_sheet_id, "op": "stale"})
        return {
            "ok": False,
            "id": listened_sheet_id,
            "stale": True,
            "error": msg,
            "has_snapshot": _load_snapshot(listened_sheet_id) is not None,
        }

    try:
        payload = sheets.read_sheet(spreadsheet_id, tab_name, account=account)
    except SheetNotFoundError as exc:
        msg = str(exc)
        _set_sheet_error(listened_sheet_id, msg)
        publish("sheet-listen.changed", {"id": listened_sheet_id, "op": "stale"})
        return {
            "ok": False,
            "id": listened_sheet_id,
            "stale": True,
            "error": msg,
            "has_snapshot": _load_snapshot(listened_sheet_id) is not None,
        }
    except Exception as exc:
        msg = f"Refresh failed: {exc}"
        _set_sheet_error(listened_sheet_id, msg)
        publish("sheet-listen.changed", {"id": listened_sheet_id, "op": "stale"})
        return {
            "ok": False,
            "id": listened_sheet_id,
            "stale": True,
            "error": msg,
            "has_snapshot": _load_snapshot(listened_sheet_id) is not None,
        }

    read_at = db.utc_now()
    raw = payload.get("raw") or []
    headers = list(payload.get("headers") or (raw[0] if raw else []))
    data_rows: list[list[Any]] = []
    for values in raw[1:] if raw else []:
        data_rows.append(list(values))
    _store_snapshot(listened_sheet_id, headers, data_rows, read_at)
    _set_sheet_ok(listened_sheet_id, read_at)
    publish("sheet-listen.changed", {"id": listened_sheet_id, "op": "refresh"})
    return {
        "ok": True,
        "id": listened_sheet_id,
        "display_name": display_name,
        "read_at": read_at,
        "row_count": len(data_rows),
        "stale": False,
    }


def refresh_all() -> dict[str, Any]:
    active = [s for s in list_listened_sheets(include_retired=False)]
    results = [refresh_listened_sheet(str(s["id"])) for s in active]
    return {"ok": True, "results": results, "state": today_state()}


def today_state() -> dict[str, Any]:
    """Current shop state from local copies: today rows only, conflicts listed both ways."""
    day = _today_local()
    sheets_out: list[dict[str, Any]] = []
    for item in list_listened_sheets(include_retired=False):
        column_map = item.get("column_map") or {}
        snap = _load_snapshot(str(item["id"]))
        today: list[dict[str, Any]] = []
        if snap and column_map_ready(column_map):
            today = today_rows(snap["headers"], snap["rows"], column_map, today=day)
        machines = sorted(
            {
                str(row.get("machine"))
                for row in today
                if row.get("machine")
            }
        )
        if item.get("last_error"):
            line = "stale"
        elif not column_map_ready(column_map):
            line = "column map needs a date header"
        elif not snap:
            line = "not read yet"
        elif not today:
            line = "no rows today"
        else:
            line = "machines: " + ", ".join(machines) if machines else "no rows today"
        sheets_out.append(
            {
                "id": item["id"],
                "display_name": item["display_name"],
                "account_label": item.get("account_label"),
                "tab_name": item["tab_name"],
                "last_ok_at": item.get("last_ok_at"),
                "last_read_at": item.get("last_read_at") or (snap.get("read_at") if snap else None),
                "last_error": item.get("last_error"),
                "stale": bool(item.get("last_error")),
                "column_map_ready": column_map_ready(column_map),
                "today": today,
                "machines_today": machines,
                "line": line,
            }
        )
    conflicts = detect_conflicts(sheets_out)
    return {
        "today": day,
        "tz": settings.tz,
        "sheets": sheets_out,
        "conflicts": conflicts,
    }


def monitor_status() -> dict[str, Any]:
    state = today_state()
    return {"ok": True, **state}


def briefing_facts() -> dict[str, Any]:
    """Refresh listened sheets (best effort) and return speak-friendly facts for the morning brief."""
    try:
        refresh_all()
    except Exception:
        pass
    state = today_state()
    machines: list[str] = []
    stale_names: list[str] = []
    for sheet in state.get("sheets") or []:
        if sheet.get("stale"):
            stale_names.append(str(sheet.get("display_name") or sheet.get("id")))
        for name in sheet.get("machines_today") or []:
            if name not in machines:
                machines.append(name)
    conflicts = state.get("conflicts") or []
    return {
        "sheet_listen_today": state.get("today"),
        "sheet_listen_machines": machines,
        "sheet_listen_stale": stale_names,
        "sheet_listen_conflicts": conflicts,
        "sheet_listen_sheets": state.get("sheets") or [],
    }


def briefing_speak_extra(facts: dict[str, Any]) -> str:
    parts: list[str] = []
    machines = facts.get("sheet_listen_machines") or []
    stale = facts.get("sheet_listen_stale") or []
    conflicts = facts.get("sheet_listen_conflicts") or []
    sheets = facts.get("sheet_listen_sheets") or []
    if not sheets:
        return ""
    if machines:
        parts.append("Today's listened logs show " + ", ".join(machines[:6]) + ".")
    elif not stale:
        parts.append("No rows today on the listened shop logs.")
    if stale:
        parts.append("Stale sheet" + ("s" if len(stale) > 1 else "") + ": " + ", ".join(stale) + ". Reconnect Google if needed.")
    if conflicts:
        # State both values; never pick a winner.
        bits = []
        for conflict in conflicts[:3]:
            field = conflict.get("field")
            vals = conflict.get("values") or []
            shown = " vs ".join(
                f"{v.get('display_name')}={v.get('value')}" for v in vals
            )
            bits.append(f"{conflict.get('machine')} {field}: {shown}")
        if bits:
            parts.append("Conflicting figures: " + "; ".join(bits) + ".")
    return " ".join(parts)
