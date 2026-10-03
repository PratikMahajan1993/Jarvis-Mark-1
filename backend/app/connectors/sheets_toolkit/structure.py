from __future__ import annotations

from typing import Any

from app.connectors.sheets_toolkit.client import (
    SheetsToolkitError,
    batch_update,
    grid_range,
    require_sheet_id,
    require_spreadsheet_id,
)

_VALID_DIMENSIONS = frozenset({"ROWS", "COLUMNS"})


def _require_dimension(dimension: str) -> str:
    if dimension not in _VALID_DIMENSIONS:
        raise SheetsToolkitError('dimension must be "ROWS" or "COLUMNS"')
    return dimension


def _require_index(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SheetsToolkitError(f"{name} must be an int >= 0")
    return value


def _require_positive_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SheetsToolkitError(f"{name} must be an int >= 1")
    return value


def _dimension_range(
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
) -> dict[str, Any]:
    dim = _require_dimension(dimension)
    start = _require_index(start_index, "start_index")
    end = _require_index(end_index, "end_index")
    if end < start:
        raise SheetsToolkitError("range end is before start")
    return {
        "sheetId": require_sheet_id(sheet_id),
        "dimension": dim,
        "startIndex": start,
        "endIndex": end,
    }


def _paste_destination(sheet_id: int, row: int, column: int) -> dict[str, int]:
    return {
        "sheetId": require_sheet_id(sheet_id),
        "rowIndex": _require_index(row, "destination_row"),
        "columnIndex": _require_index(column, "destination_column"),
    }


def insert_dimension(
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Insert empty rows or columns at an index."""
    sid = require_spreadsheet_id(spreadsheet_id)
    request = {
        "insertDimension": {
            "range": _dimension_range(sheet_id, dimension, start_index, end_index),
            "inheritFromBefore": False,
        }
    }
    return batch_update(sid, [request], account)


def delete_dimension(
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Delete rows or columns in an index range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    request = {
        "deleteDimension": {
            "range": _dimension_range(sheet_id, dimension, start_index, end_index),
        }
    }
    return batch_update(sid, [request], account)


def append_dimension(
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    length: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Append empty rows or columns at the end of a sheet."""
    sid = require_spreadsheet_id(spreadsheet_id)
    request = {
        "appendDimension": {
            "sheetId": require_sheet_id(sheet_id),
            "dimension": _require_dimension(dimension),
            "length": _require_positive_int(length, "length"),
        }
    }
    return batch_update(sid, [request], account)


def move_dimension(
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
    destination_index: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Move rows or columns to a new index."""
    sid = require_spreadsheet_id(spreadsheet_id)
    request = {
        "moveDimension": {
            "source": _dimension_range(sheet_id, dimension, start_index, end_index),
            "destinationIndex": _require_index(destination_index, "destination_index"),
        }
    }
    return batch_update(sid, [request], account)


def insert_range(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    shift: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Insert cells and shift existing content."""
    sid = require_spreadsheet_id(spreadsheet_id)
    request = {
        "insertRange": {
            "range": grid_range(sheet_id, start_row, end_row, start_column, end_column),
            "shiftDimension": _require_dimension(shift),
        }
    }
    return batch_update(sid, [request], account)


def delete_range(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    shift: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Delete cells and shift remaining content."""
    sid = require_spreadsheet_id(spreadsheet_id)
    request = {
        "deleteRange": {
            "range": grid_range(sheet_id, start_row, end_row, start_column, end_column),
            "shiftDimension": _require_dimension(shift),
        }
    }
    return batch_update(sid, [request], account)


def copy_range(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    destination_sheet_id: int,
    destination_row: int,
    destination_column: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Copy a cell range to another location."""
    sid = require_spreadsheet_id(spreadsheet_id)
    request = {
        "copyPaste": {
            "source": grid_range(sheet_id, start_row, end_row, start_column, end_column),
            "destination": _paste_destination(
                destination_sheet_id, destination_row, destination_column
            ),
            "pasteType": "PASTE_NORMAL",
        }
    }
    return batch_update(sid, [request], account)


def cut_range(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    destination_sheet_id: int,
    destination_row: int,
    destination_column: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Cut a cell range to another location."""
    sid = require_spreadsheet_id(spreadsheet_id)
    request = {
        "cutPaste": {
            "source": grid_range(sheet_id, start_row, end_row, start_column, end_column),
            "destination": _paste_destination(
                destination_sheet_id, destination_row, destination_column
            ),
        }
    }
    return batch_update(sid, [request], account)


def paste_text(
    spreadsheet_id: str,
    sheet_id: int,
    row: int,
    column: int,
    data: str,
    delimiter: str = ",",
    account: str | None = None,
) -> dict[str, Any]:
    """Paste delimited text starting at a cell."""
    sid = require_spreadsheet_id(spreadsheet_id)
    request = {
        "pasteData": {
            "coordinate": {
                "sheetId": require_sheet_id(sheet_id),
                "rowIndex": _require_index(row, "row"),
                "columnIndex": _require_index(column, "column"),
            },
            "data": data,
            "delimiter": delimiter,
            "type": "PASTE_NORMAL",
        }
    }
    return batch_update(sid, [request], account)


def sort_range(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    sort_column: int,
    ascending: bool = True,
    account: str | None = None,
) -> dict[str, Any]:
    """Sort a range by one column."""
    sid = require_spreadsheet_id(spreadsheet_id)
    if not isinstance(ascending, bool):
        raise SheetsToolkitError("ascending must be a bool")
    request = {
        "sortRange": {
            "range": grid_range(sheet_id, start_row, end_row, start_column, end_column),
            "sortSpecs": [
                {
                    "dimensionIndex": _require_index(sort_column, "sort_column"),
                    "sortOrder": "ASCENDING" if ascending else "DESCENDING",
                }
            ],
        }
    }
    return batch_update(sid, [request], account)


def find_replace(
    spreadsheet_id: str,
    find: str,
    replacement: str,
    sheet_id: int | None = None,
    match_case: bool = False,
    account: str | None = None,
) -> dict[str, Any]:
    """Find and replace text in one sheet or the whole workbook."""
    sid = require_spreadsheet_id(spreadsheet_id)
    if not isinstance(match_case, bool):
        raise SheetsToolkitError("match_case must be a bool")
    payload: dict[str, Any] = {
        "find": find,
        "replacement": replacement,
        "matchCase": match_case,
    }
    if sheet_id is None:
        payload["allSheets"] = True
    else:
        payload["sheetId"] = require_sheet_id(sheet_id)
    request = {"findReplace": payload}
    return batch_update(sid, [request], account)


def text_to_columns(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    delimiter: str = ",",
    account: str | None = None,
) -> dict[str, Any]:
    """Split text in a range into columns."""
    sid = require_spreadsheet_id(spreadsheet_id)
    request = {
        "textToColumns": {
            "source": grid_range(sheet_id, start_row, end_row, start_column, end_column),
            "delimiter": delimiter,
            "delimiterType": "CUSTOM",
        }
    }
    return batch_update(sid, [request], account)


def trim_whitespace(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Trim leading and trailing whitespace in a range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    request = {
        "trimWhitespace": {
            "range": grid_range(sheet_id, start_row, end_row, start_column, end_column),
        }
    }
    return batch_update(sid, [request], account)


def delete_duplicates(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Remove duplicate rows within a range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    request = {
        "deleteDuplicates": {
            "range": grid_range(sheet_id, start_row, end_row, start_column, end_column),
            "comparisonColumns": [],
        }
    }
    return batch_update(sid, [request], account)


def randomize_range(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Randomize the order of rows in a range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    request = {
        "randomizeRange": {
            "range": grid_range(sheet_id, start_row, end_row, start_column, end_column),
        }
    }
    return batch_update(sid, [request], account)


def autofill(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    dimension: str,
    fill_length: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Extend a range pattern along rows or columns."""
    sid = require_spreadsheet_id(spreadsheet_id)
    request = {
        "autoFill": {
            "sourceAndDestination": {
                "source": grid_range(
                    sheet_id, start_row, end_row, start_column, end_column
                ),
                "dimension": _require_dimension(dimension),
                "fillLength": _require_positive_int(fill_length, "fill_length"),
            }
        }
    }
    return batch_update(sid, [request], account)
