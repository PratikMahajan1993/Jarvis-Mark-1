from __future__ import annotations

from typing import Any

from app.connectors.sheets_toolkit.client import (
    SheetsToolkitError,
    batch_update,
    require_sheet_id,
)


def _require_object_id(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SheetsToolkitError(f"{name} must be an int")
    if value < 0:
        raise SheetsToolkitError(f"{name} must be >= 0")
    return value


def _require_chart_spec(chart_spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(chart_spec, dict) or not chart_spec:
        raise SheetsToolkitError("chart_spec must be a non-empty dict")
    return chart_spec


def _require_rgb(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SheetsToolkitError(f"{name} must be a float")
    number = float(value)
    if number < 0 or number > 1:
        raise SheetsToolkitError(f"{name} must be between 0 and 1")
    return number


def _require_row_column(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SheetsToolkitError(f"{name} must be an int")
    if value < 0:
        raise SheetsToolkitError(f"{name} must be >= 0")
    return value


def add_chart(
    spreadsheet_id: str,
    sheet_id: int,
    chart_spec: dict[str, Any],
    account: str | None = None,
) -> dict[str, Any]:
    """Add a chart anchored at the sheet origin."""
    spec = _require_chart_spec(chart_spec)
    sid = require_sheet_id(sheet_id)
    return batch_update(
        spreadsheet_id,
        [
            {
                "addChart": {
                    "chart": {
                        "spec": spec,
                        "position": {
                            "overlayPosition": {
                                "anchorCell": {
                                    "sheetId": sid,
                                    "rowIndex": 0,
                                    "columnIndex": 0,
                                }
                            }
                        },
                    }
                }
            }
        ],
        account=account,
    )


def update_chart(
    spreadsheet_id: str,
    chart_id: int,
    chart_spec: dict[str, Any],
    account: str | None = None,
) -> dict[str, Any]:
    """Replace an existing chart spec."""
    spec = _require_chart_spec(chart_spec)
    cid = _require_object_id("chart_id", chart_id)
    return batch_update(
        spreadsheet_id,
        [{"updateChartSpec": {"chartId": cid, "spec": spec}}],
        account=account,
    )


def move_embedded_object(
    spreadsheet_id: str,
    object_id: int,
    sheet_id: int,
    row: int,
    column: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Move an embedded object to a new anchor cell."""
    oid = _require_object_id("object_id", object_id)
    sid = require_sheet_id(sheet_id)
    row_index = _require_row_column("row", row)
    column_index = _require_row_column("column", column)
    return batch_update(
        spreadsheet_id,
        [
            {
                "updateEmbeddedObjectPosition": {
                    "objectId": oid,
                    "newPosition": {
                        "overlayPosition": {
                            "anchorCell": {
                                "sheetId": sid,
                                "rowIndex": row_index,
                                "columnIndex": column_index,
                            }
                        }
                    },
                    "fields": "overlayPosition.anchorCell",
                }
            }
        ],
        account=account,
    )


def delete_embedded_object(
    spreadsheet_id: str,
    object_id: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Delete an embedded object by id."""
    oid = _require_object_id("object_id", object_id)
    return batch_update(
        spreadsheet_id,
        [{"deleteEmbeddedObject": {"objectId": oid}}],
        account=account,
    )


def set_embedded_object_border(
    spreadsheet_id: str,
    object_id: int,
    red: float,
    green: float,
    blue: float,
    account: str | None = None,
) -> dict[str, Any]:
    """Set the RGB border color on an embedded object."""
    oid = _require_object_id("object_id", object_id)
    r = _require_rgb("red", red)
    g = _require_rgb("green", green)
    b = _require_rgb("blue", blue)
    return batch_update(
        spreadsheet_id,
        [
            {
                "updateEmbeddedObjectBorder": {
                    "objectId": oid,
                    "border": {
                        "colorStyle": {"rgbColor": {"red": r, "green": g, "blue": b}}
                    },
                }
            }
        ],
        account=account,
    )
