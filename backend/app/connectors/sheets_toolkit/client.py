"""Shared Google Sheets and Drive client for the sheets toolkit.

Batch-update indexes are 0-based and end-exclusive. A1 ranges are 1-based.
sheet_id is the numeric Google sheet id, not the tab title.
"""

from __future__ import annotations

from typing import Any

from app.connectors import google_auth

_SHEETS_FIELDS = "spreadsheetId,replies"


class SheetsToolkitError(RuntimeError):
    """A Sheets or Drive call was rejected before it was sent, or the caller passed a bad argument."""


def sheets_service(account: str | None = None):
    return google_auth.google_service("sheets", "v4", account=account)


def drive_service(account: str | None = None):
    return google_auth.google_service("drive", "v3", account=account)


def require_spreadsheet_id(spreadsheet_id: str) -> str:
    text = str(spreadsheet_id or "").strip()
    if not text:
        raise SheetsToolkitError("spreadsheet_id is required")
    return text


def require_sheet_id(sheet_id: int) -> int:
    if isinstance(sheet_id, bool) or not isinstance(sheet_id, int):
        raise SheetsToolkitError("sheet_id must be an int")
    if sheet_id < 0:
        raise SheetsToolkitError("sheet_id must be >= 0")
    return sheet_id


def spreadsheet_url(spreadsheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{require_spreadsheet_id(spreadsheet_id)}/edit"


def grid_range(
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
) -> dict[str, int]:
    """0-based inclusive start, exclusive end."""
    bounds = {
        "sheetId": require_sheet_id(sheet_id),
        "startRowIndex": start_row,
        "endRowIndex": end_row,
        "startColumnIndex": start_column,
        "endColumnIndex": end_column,
    }
    for key, value in bounds.items():
        if key == "sheetId":
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise SheetsToolkitError(f"{key} must be an int >= 0")
    if end_row < start_row or end_column < start_column:
        raise SheetsToolkitError("range end is before start")
    return bounds


def batch_update(
    spreadsheet_id: str,
    requests: list[dict[str, Any]],
    account: str | None = None,
) -> dict[str, Any]:
    if not isinstance(requests, list) or not requests:
        raise SheetsToolkitError("requests must be a non-empty list")
    for item in requests:
        if not isinstance(item, dict) or len(item) != 1:
            raise SheetsToolkitError("each request must be a one-key dict")
    result = (
        sheets_service(account)
        .spreadsheets()
        .batchUpdate(
            spreadsheetId=require_spreadsheet_id(spreadsheet_id),
            body={"requests": requests},
            fields=_SHEETS_FIELDS,
        )
        .execute()
    )
    return result if isinstance(result, dict) else {"replies": []}
