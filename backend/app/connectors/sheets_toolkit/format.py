from __future__ import annotations

from typing import Any

from app.connectors.sheets_toolkit.client import (
    SheetsToolkitError,
    batch_update,
    grid_range,
    require_sheet_id,
    require_spreadsheet_id,
)

_DIMENSIONS = frozenset({"ROWS", "COLUMNS"})
_BORDER_STYLES = frozenset({"SOLID", "DOTTED", "DASHED", "NONE"})
_MERGE_TYPES = frozenset({"MERGE_ALL", "MERGE_ROWS", "MERGE_COLUMNS"})


def _require_dimension(dimension: str) -> str:
    text = str(dimension or "").strip()
    if text not in _DIMENSIONS:
        raise SheetsToolkitError('dimension must be "ROWS" or "COLUMNS"')
    return text


def _require_index_range(start_index: int, end_index: int) -> tuple[int, int]:
    for name, value in (("start_index", start_index), ("end_index", end_index)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise SheetsToolkitError(f"{name} must be an int >= 0")
    if end_index < start_index:
        raise SheetsToolkitError("end_index must be >= start_index")
    return start_index, end_index


def _require_banded_range_id(banded_range_id: int) -> int:
    if isinstance(banded_range_id, bool) or not isinstance(banded_range_id, int):
        raise SheetsToolkitError("banded_range_id must be an int")
    if banded_range_id < 0:
        raise SheetsToolkitError("banded_range_id must be >= 0")
    return banded_range_id


def format_cells(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    cell_format: dict,
    fields: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Apply userEnteredFormat to a grid range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    if not isinstance(cell_format, dict) or not cell_format:
        raise SheetsToolkitError("cell_format must be a non-empty dict")
    fields_text = str(fields or "")
    if not fields_text.strip():
        raise SheetsToolkitError("fields is required")
    if not fields_text.startswith("userEnteredFormat"):
        raise SheetsToolkitError('fields must start with "userEnteredFormat"')
    return batch_update(
        sid,
        [
            {
                "repeatCell": {
                    "range": grid_range(
                        sheet_id, start_row, end_row, start_column, end_column
                    ),
                    "cell": {"userEnteredFormat": cell_format},
                    "fields": fields_text,
                }
            }
        ],
        account=account,
    )


def set_borders(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    style: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Set the same border style on all sides of a grid range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    border_style = str(style or "").strip()
    if border_style not in _BORDER_STYLES:
        raise SheetsToolkitError("style must be SOLID, DOTTED, DASHED, or NONE")
    border = {"style": border_style}
    return batch_update(
        sid,
        [
            {
                "updateBorders": {
                    "range": grid_range(
                        sheet_id, start_row, end_row, start_column, end_column
                    ),
                    "top": border,
                    "bottom": border,
                    "left": border,
                    "right": border,
                }
            }
        ],
        account=account,
    )


def merge_cells(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    merge_type: str = "MERGE_ALL",
    account: str | None = None,
) -> dict[str, Any]:
    """Merge cells in a grid range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    merge = str(merge_type or "").strip()
    if merge not in _MERGE_TYPES:
        raise SheetsToolkitError("merge_type must be MERGE_ALL, MERGE_ROWS, or MERGE_COLUMNS")
    return batch_update(
        sid,
        [
            {
                "mergeCells": {
                    "range": grid_range(
                        sheet_id, start_row, end_row, start_column, end_column
                    ),
                    "mergeType": merge,
                }
            }
        ],
        account=account,
    )


def unmerge_cells(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Unmerge cells in a grid range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    return batch_update(
        sid,
        [
            {
                "unmergeCells": {
                    "range": grid_range(
                        sheet_id, start_row, end_row, start_column, end_column
                    )
                }
            }
        ],
        account=account,
    )


def set_dimension_size(
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
    pixel_size: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Set row or column size in pixels."""
    sid = require_spreadsheet_id(spreadsheet_id)
    dim = _require_dimension(dimension)
    start, end = _require_index_range(start_index, end_index)
    if isinstance(pixel_size, bool) or not isinstance(pixel_size, int) or pixel_size < 1:
        raise SheetsToolkitError("pixel_size must be an int >= 1")
    sheet = require_sheet_id(sheet_id)
    return batch_update(
        sid,
        [
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet,
                        "dimension": dim,
                        "startIndex": start,
                        "endIndex": end,
                    },
                    "properties": {"pixelSize": pixel_size},
                    "fields": "pixelSize",
                }
            }
        ],
        account=account,
    )


def auto_resize(
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Auto-resize rows or columns to fit content."""
    sid = require_spreadsheet_id(spreadsheet_id)
    dim = _require_dimension(dimension)
    start, end = _require_index_range(start_index, end_index)
    sheet = require_sheet_id(sheet_id)
    return batch_update(
        sid,
        [
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheet,
                        "dimension": dim,
                        "startIndex": start,
                        "endIndex": end,
                    }
                }
            }
        ],
        account=account,
    )


def add_banding(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Add alternating row or column banding to a grid range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    return batch_update(
        sid,
        [
            {
                "addBanding": {
                    "bandedRange": {
                        "range": grid_range(
                            sheet_id, start_row, end_row, start_column, end_column
                        )
                    }
                }
            }
        ],
        account=account,
    )


def update_banding(
    spreadsheet_id: str,
    banded_range_id: int,
    banded_range: dict,
    fields: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Update an existing banded range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    range_id = _require_banded_range_id(banded_range_id)
    if not isinstance(banded_range, dict) or not banded_range:
        raise SheetsToolkitError("banded_range must be a non-empty dict")
    fields_text = str(fields or "")
    if not fields_text.strip():
        raise SheetsToolkitError("fields is required")
    merged = {**banded_range, "bandedRangeId": range_id}
    return batch_update(
        sid,
        [{"updateBanding": {"bandedRange": merged, "fields": fields_text}}],
        account=account,
    )


def delete_banding(
    spreadsheet_id: str,
    banded_range_id: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Remove a banded range by id."""
    sid = require_spreadsheet_id(spreadsheet_id)
    range_id = _require_banded_range_id(banded_range_id)
    return batch_update(
        sid,
        [{"deleteBanding": {"bandedRangeId": range_id}}],
        account=account,
    )


def add_dimension_group(
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Group contiguous rows or columns."""
    sid = require_spreadsheet_id(spreadsheet_id)
    dim = _require_dimension(dimension)
    start, end = _require_index_range(start_index, end_index)
    sheet = require_sheet_id(sheet_id)
    return batch_update(
        sid,
        [
            {
                "addDimensionGroup": {
                    "range": {
                        "sheetId": sheet,
                        "dimension": dim,
                        "startIndex": start,
                        "endIndex": end,
                    }
                }
            }
        ],
        account=account,
    )


def update_dimension_group(
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
    collapsed: bool,
    account: str | None = None,
) -> dict[str, Any]:
    """Collapse or expand a row or column group."""
    sid = require_spreadsheet_id(spreadsheet_id)
    dim = _require_dimension(dimension)
    start, end = _require_index_range(start_index, end_index)
    if not isinstance(collapsed, bool):
        raise SheetsToolkitError("collapsed must be a bool")
    sheet = require_sheet_id(sheet_id)
    return batch_update(
        sid,
        [
            {
                "updateDimensionGroup": {
                    "dimensionGroup": {
                        "range": {
                            "sheetId": sheet,
                            "dimension": dim,
                            "startIndex": start,
                            "endIndex": end,
                        },
                        "collapsed": collapsed,
                        "depth": 1,
                    },
                    "fields": "collapsed",
                }
            }
        ],
        account=account,
    )


def delete_dimension_group(
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Delete a row or column group."""
    sid = require_spreadsheet_id(spreadsheet_id)
    dim = _require_dimension(dimension)
    start, end = _require_index_range(start_index, end_index)
    sheet = require_sheet_id(sheet_id)
    return batch_update(
        sid,
        [
            {
                "deleteDimensionGroup": {
                    "range": {
                        "sheetId": sheet,
                        "dimension": dim,
                        "startIndex": start,
                        "endIndex": end,
                    }
                }
            }
        ],
        account=account,
    )
