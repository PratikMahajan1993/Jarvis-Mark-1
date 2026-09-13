"""Google Sheets shop log. Never invents OEE — empty cells stay missing."""

from __future__ import annotations

import logging
import re
from typing import Any

from . import google_auth

log = logging.getLogger(__name__)

DEFAULT_TITLE = "Jarvis shop log"
DEFAULT_TAB = "Production"
_SHEET_ID = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
_BARE_ID = re.compile(r"^[a-zA-Z0-9-_]{20,}$")
_CONSOLE = re.compile(r"https://console\.(?:developers|cloud)\.google\.com/[^\s\"'<>]+")


def google_error(exc: BaseException, fallback: str = "Google Sheets did not take it.") -> dict[str, str]:
    """Short HUD speak for a Sheets API failure. Never dumps the raw HttpError."""
    blob = str(exc)
    match = _CONSOLE.search(blob)
    url = (match.group(0).rstrip(".,);") if match else "")
    lowered = blob.lower()
    if "service_disabled" in lowered or "has not been used" in lowered or "is disabled" in lowered:
        speak = (
            "The Google Sheets API is off on this Google Cloud project. "
            "Enable it in the console, wait a minute, then try again."
        )
    elif "access_token_scope_insufficient" in lowered or "insufficientpermissions" in lowered:
        speak = "Reconnect Google in preferences (Add Sheets) so I can use the shop log."
    else:
        speak = fallback
    return {"speak": speak, "url": url}


class SheetNotFoundError(ValueError):
    """Named tab does not exist; the first tab is never used as a fallback."""


def live() -> bool:
    return google_auth.connected() and google_auth.has_sheets()


def spreadsheet_id_from(text: str) -> str:
    blob = (text or "").strip()
    if not blob:
        return ""
    match = _SHEET_ID.search(blob)
    if match:
        return match.group(1)
    if _BARE_ID.match(blob) and " " not in blob:
        return blob
    return ""


def _service():
    return google_auth.google_service("sheets", "v4")


def _drive():
    return google_auth.google_service("drive", "v3")


def spreadsheet_url(spreadsheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"


def list_sheets(spreadsheet_id: str) -> list[str]:
    meta = (
        _service()
        .spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title")
        .execute()
    )
    names: list[str] = []
    for sheet in meta.get("sheets") or []:
        title = str((sheet.get("properties") or {}).get("title") or "").strip()
        if title:
            names.append(title)
    return names


def _cell_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _row_is_empty(values: list[Any]) -> bool:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return False
    return True


def _header_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _record_from_row(headers: list[str], values: list[Any]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for index, header in enumerate(headers):
        if not header or header in record:
            continue
        record[header] = values[index] if index < len(values) else None
    return record


def read_sheet(spreadsheet_id: str, sheet_name: str) -> dict[str, Any]:
    names = list_sheets(spreadsheet_id)
    if sheet_name not in names:
        available = ", ".join(names) if names else "(none)"
        raise SheetNotFoundError(f"Sheet {sheet_name!r} not found. Available: {available}")
    quoted = "'" + sheet_name.replace("'", "''") + "'"
    result = (
        _service()
        .spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=quoted, majorDimension="ROWS")
        .execute()
    )
    raw: list[list[Any]] = []
    for row in result.get("values") or []:
        raw.append([_cell_value(cell) for cell in row])
    while raw and _row_is_empty(raw[-1]):
        raw.pop()
    headers = [_header_text(cell) for cell in raw[0]] if raw else []
    keyed_headers = [name for name in headers if name]
    rows: list[dict[str, Any]] = []
    for values in raw[1:]:
        if _row_is_empty(values):
            continue
        rows.append(_record_from_row(headers, values))
    return {
        "sheet": sheet_name,
        "headers": headers,
        "rows": rows,
        "raw": raw,
        "keyed_headers": keyed_headers,
        "spreadsheet_id": spreadsheet_id,
    }


def _a1(row: int, col: int) -> str:
    letters = ""
    n = col
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row}"


def _parse_update(item: dict[str, Any]) -> tuple[int, int, Any]:
    if not isinstance(item, dict):
        raise TypeError("Each update must be a dict")
    if "value" not in item:
        raise ValueError("Each update requires a 'value'")
    value = item["value"]
    cell = str(item.get("cell") or "").strip()
    if cell:
        match = re.fullmatch(r"([A-Za-z]+)(\d+)", cell)
        if not match:
            raise ValueError(f"Bad cell {cell!r}")
        col = 0
        for ch in match.group(1).upper():
            col = col * 26 + (ord(ch) - 64)
        return int(match.group(2)), col, value
    if "row" in item and "col" in item:
        row = int(item["row"])
        col = item["col"]
        if isinstance(col, str) and col.strip() and not col.strip().isdigit():
            index = 0
            for ch in col.strip().upper():
                index = index * 26 + (ord(ch) - 64)
            col = index
        else:
            col = int(col)
        if row < 1 or col < 1:
            raise ValueError("row and col are 1-based")
        return row, col, value
    raise ValueError("Each update requires 'cell' or both 'row' and 'col'")


def update_cells(
    spreadsheet_id: str,
    sheet_name: str,
    updates: list[dict[str, Any]],
) -> dict[str, Any]:
    names = list_sheets(spreadsheet_id)
    if sheet_name not in names:
        available = ", ".join(names) if names else "(none)"
        raise SheetNotFoundError(f"Sheet {sheet_name!r} not found. Available: {available}")
    data = []
    written: list[str] = []
    quoted = sheet_name.replace("'", "''")
    for item in updates:
        row, col, value = _parse_update(item)
        a1 = _a1(row, col)
        data.append({"range": f"'{quoted}'!{a1}", "values": [[value]]})
        written.append(a1)
    if data:
        _service().spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": data},
        ).execute()
    return {
        "sheet": sheet_name,
        "spreadsheet_id": spreadsheet_id,
        "url": spreadsheet_url(spreadsheet_id),
        "updated": written,
    }


def create_shop_spreadsheet(title: str = DEFAULT_TITLE) -> dict[str, Any]:
    body = {
        "properties": {"title": title or DEFAULT_TITLE},
        "sheets": [
            {"properties": {"title": "Production"}},
            {"properties": {"title": "Scrap"}},
            {"properties": {"title": "Downtime"}},
        ],
    }
    created = _service().spreadsheets().create(body=body, fields="spreadsheetId,spreadsheetUrl,properties.title").execute()
    spreadsheet_id = str(created.get("spreadsheetId") or "")
    _service().spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "valueInputOption": "RAW",
            "data": [
                {"range": "Production!A1:C1", "values": [["Machine", "OEE", "Notes"]]},
                {"range": "Scrap!A1:B1", "values": [["Part", "Qty"]]},
                {"range": "Downtime!A1:B1", "values": [["Machine", "Minutes"]]},
            ],
        },
    ).execute()
    return {
        "spreadsheet_id": spreadsheet_id,
        "title": str((created.get("properties") or {}).get("title") or title or DEFAULT_TITLE),
        "url": created.get("spreadsheetUrl") or spreadsheet_url(spreadsheet_id),
        "sheet_name": DEFAULT_TAB,
    }


def find_by_name(name: str, limit: int = 8) -> list[dict[str, Any]]:
    needle = (name or "").strip()
    if not needle:
        return []
    safe = needle.replace("'", "\\'")
    query = (
        f"name contains '{safe}' and mimeType = 'application/vnd.google-apps.spreadsheet' "
        "and trashed = false"
    )
    listed = (
        _drive()
        .files()
        .list(q=query, pageSize=max(1, min(limit, 20)), fields="files(id,name,webViewLink)")
        .execute()
    )
    out: list[dict[str, Any]] = []
    for row in listed.get("files") or []:
        file_id = str(row.get("id") or "")
        if not file_id:
            continue
        out.append(
            {
                "spreadsheet_id": file_id,
                "title": str(row.get("name") or ""),
                "url": str(row.get("webViewLink") or spreadsheet_url(file_id)),
            }
        )
    return out


def get_title(spreadsheet_id: str) -> str:
    meta = (
        _service()
        .spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="properties.title")
        .execute()
    )
    return str((meta.get("properties") or {}).get("title") or "")


def efficiency_snapshot(
    spreadsheet_id: str,
    sheet_name: str,
    oee_aliases: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    from ..shop_excel import DEFAULT_OEE_ALIASES, efficiency_from_payload

    aliases = oee_aliases if oee_aliases is not None else DEFAULT_OEE_ALIASES
    snap = efficiency_from_payload(read_sheet(spreadsheet_id, sheet_name), aliases)
    snap["spreadsheet_id"] = spreadsheet_id
    snap["url"] = spreadsheet_url(spreadsheet_id)
    snap["sheet"] = sheet_name
    return snap
