from __future__ import annotations

from typing import Any

from app.connectors.sheets_toolkit.client import (
    SheetsToolkitError,
    batch_update,
    require_sheet_id,
    require_spreadsheet_id,
    sheets_service,
)


def list_tabs(spreadsheet_id: str, account: str | None = None) -> list[dict[str, Any]]:
    """List sheet tabs and their metadata."""
    sid = require_spreadsheet_id(spreadsheet_id)
    result = (
        sheets_service(account)
        .spreadsheets()
        .get(
            spreadsheetId=sid,
            fields="sheets.properties(sheetId,title,index,hidden)",
        )
        .execute()
    )
    tabs: list[dict[str, Any]] = []
    for sheet in result.get("sheets") or []:
        props = sheet.get("properties") or {}
        tabs.append(
            {
                "sheet_id": props.get("sheetId"),
                "title": props.get("title", ""),
                "index": props.get("index", 0),
                "hidden": bool(props.get("hidden", False)),
            }
        )
    return tabs


def add_tab(
    spreadsheet_id: str,
    title: str,
    account: str | None = None,
    row_count: int = 1000,
    column_count: int = 26,
) -> dict[str, Any]:
    """Add a new sheet tab."""
    sid = require_spreadsheet_id(spreadsheet_id)
    if not str(title or "").strip():
        raise SheetsToolkitError("title is required")
    if isinstance(row_count, bool) or not isinstance(row_count, int) or row_count < 1:
        raise SheetsToolkitError("row_count must be an int >= 1")
    if isinstance(column_count, bool) or not isinstance(column_count, int) or column_count < 1:
        raise SheetsToolkitError("column_count must be an int >= 1")
    return batch_update(
        sid,
        [
            {
                "addSheet": {
                    "properties": {
                        "title": title,
                        "gridProperties": {
                            "rowCount": row_count,
                            "columnCount": column_count,
                        },
                    }
                }
            }
        ],
        account=account,
    )


def delete_tab(
    spreadsheet_id: str, sheet_id: int, account: str | None = None
) -> dict[str, Any]:
    """Delete a sheet tab by id."""
    sid = require_spreadsheet_id(spreadsheet_id)
    sid_int = require_sheet_id(sheet_id)
    return batch_update(sid, [{"deleteSheet": {"sheetId": sid_int}}], account=account)


def rename_tab(
    spreadsheet_id: str, sheet_id: int, title: str, account: str | None = None
) -> dict[str, Any]:
    """Rename a sheet tab."""
    sid = require_spreadsheet_id(spreadsheet_id)
    sid_int = require_sheet_id(sheet_id)
    return batch_update(
        sid,
        [
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sid_int, "title": title},
                    "fields": "title",
                }
            }
        ],
        account=account,
    )


def duplicate_tab(
    spreadsheet_id: str, sheet_id: int, new_title: str, account: str | None = None
) -> dict[str, Any]:
    """Duplicate a sheet tab with a new title."""
    sid = require_spreadsheet_id(spreadsheet_id)
    sid_int = require_sheet_id(sheet_id)
    return batch_update(
        sid,
        [
            {
                "duplicateSheet": {
                    "sourceSheetId": sid_int,
                    "newSheetName": new_title,
                }
            }
        ],
        account=account,
    )


def copy_tab_to(
    spreadsheet_id: str,
    sheet_id: int,
    destination_spreadsheet_id: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Copy a sheet tab into another spreadsheet."""
    sid = require_spreadsheet_id(spreadsheet_id)
    sid_int = require_sheet_id(sheet_id)
    dest = require_spreadsheet_id(destination_spreadsheet_id)
    result = (
        sheets_service(account)
        .spreadsheets()
        .sheets()
        .copyTo(
            spreadsheetId=sid,
            sheetId=sid_int,
            body={"destinationSpreadsheetId": dest},
        )
        .execute()
    )
    return result if isinstance(result, dict) else {}


def reorder_tab(
    spreadsheet_id: str, sheet_id: int, index: int, account: str | None = None
) -> dict[str, Any]:
    """Move a sheet tab to a new index."""
    sid = require_spreadsheet_id(spreadsheet_id)
    sid_int = require_sheet_id(sheet_id)
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise SheetsToolkitError("index must be an int >= 0")
    return batch_update(
        sid,
        [
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sid_int, "index": index},
                    "fields": "index",
                }
            }
        ],
        account=account,
    )


def set_tab_hidden(
    spreadsheet_id: str, sheet_id: int, hidden: bool, account: str | None = None
) -> dict[str, Any]:
    """Show or hide a sheet tab."""
    sid = require_spreadsheet_id(spreadsheet_id)
    sid_int = require_sheet_id(sheet_id)
    if not isinstance(hidden, bool):
        raise SheetsToolkitError("hidden must be a bool")
    return batch_update(
        sid,
        [
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sid_int, "hidden": hidden},
                    "fields": "hidden",
                }
            }
        ],
        account=account,
    )


def set_tab_color(
    spreadsheet_id: str,
    sheet_id: int,
    red: float,
    green: float,
    blue: float,
    account: str | None = None,
) -> dict[str, Any]:
    """Set the tab color using RGB channels in 0..1."""
    sid = require_spreadsheet_id(spreadsheet_id)
    sid_int = require_sheet_id(sheet_id)
    for name, value in (("red", red), ("green", green), ("blue", blue)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SheetsToolkitError(f"{name} must be a float from 0 to 1")
        if value < 0 or value > 1:
            raise SheetsToolkitError(f"{name} must be a float from 0 to 1")
    return batch_update(
        sid,
        [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sid_int,
                        "tabColor": {"red": red, "green": green, "blue": blue},
                    },
                    "fields": "tabColor",
                }
            }
        ],
        account=account,
    )


def freeze_tab(
    spreadsheet_id: str,
    sheet_id: int,
    frozen_rows: int,
    frozen_columns: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Freeze rows and columns on a sheet tab."""
    sid = require_spreadsheet_id(spreadsheet_id)
    sid_int = require_sheet_id(sheet_id)
    for name, value in (("frozen_rows", frozen_rows), ("frozen_columns", frozen_columns)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise SheetsToolkitError(f"{name} must be an int >= 0")
    return batch_update(
        sid,
        [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sid_int,
                        "gridProperties": {
                            "frozenRowCount": frozen_rows,
                            "frozenColumnCount": frozen_columns,
                        },
                    },
                    "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
                }
            }
        ],
        account=account,
    )
