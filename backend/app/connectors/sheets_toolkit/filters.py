from __future__ import annotations

from typing import Any

from app.connectors.sheets_toolkit.client import (
    SheetsToolkitError,
    batch_update,
    grid_range,
    require_sheet_id,
    require_spreadsheet_id,
)


def _require_nonneg_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SheetsToolkitError(f"{name} must be an int")
    if value < 0:
        raise SheetsToolkitError(f"{name} must be >= 0")
    return value


def _require_title(title: str) -> str:
    if not str(title or "").strip():
        raise SheetsToolkitError("title is required")
    return title


def _require_spec(spec: dict) -> dict:
    if not isinstance(spec, dict) or not spec:
        raise SheetsToolkitError("spec must be a non-empty dict")
    return spec


def _require_condition_type(condition_type: str) -> str:
    text = str(condition_type or "").strip()
    if not text:
        raise SheetsToolkitError("condition_type is required")
    return text


def _require_string_list(values: list[str]) -> list[str]:
    if not isinstance(values, list):
        raise SheetsToolkitError("values must be a list")
    for item in values:
        if not isinstance(item, str):
            raise SheetsToolkitError("values must be a list of strings")
    return values


def _condition_values(values: list[str]) -> list[dict[str, str]]:
    return [{"userEnteredValue": v} for v in _require_string_list(values)]


def _conditional_boolean_rule(
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    condition_type: str,
    values: list[str],
) -> dict[str, Any]:
    ctype = _require_condition_type(condition_type)
    return {
        "ranges": [
            grid_range(sheet_id, start_row, end_row, start_column, end_column),
        ],
        "booleanRule": {
            "condition": {"type": ctype, "values": _condition_values(values)},
            "format": {"backgroundColor": {"red": 1, "green": 0.9, "blue": 0.6}},
        },
    }


def set_basic_filter(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Set the sheet basic filter over a grid range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    return batch_update(
        sid,
        [
            {
                "setBasicFilter": {
                    "filter": {
                        "range": grid_range(
                            sheet_id, start_row, end_row, start_column, end_column
                        ),
                    },
                },
            },
        ],
        account,
    )


def clear_basic_filter(
    spreadsheet_id: str,
    sheet_id: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Clear the basic filter on a sheet."""
    sid = require_spreadsheet_id(spreadsheet_id)
    return batch_update(
        sid,
        [{"clearBasicFilter": {"sheetId": require_sheet_id(sheet_id)}}],
        account,
    )


def add_filter_view(
    spreadsheet_id: str,
    sheet_id: int,
    title: str,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Add a named filter view over a grid range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    _require_title(title)
    return batch_update(
        sid,
        [
            {
                "addFilterView": {
                    "filter": {
                        "title": title,
                        "range": grid_range(
                            sheet_id, start_row, end_row, start_column, end_column
                        ),
                    },
                },
            },
        ],
        account,
    )


def update_filter_view(
    spreadsheet_id: str,
    filter_view_id: int,
    title: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Update a filter view title."""
    sid = require_spreadsheet_id(spreadsheet_id)
    _require_nonneg_int(filter_view_id, "filter_view_id")
    _require_title(title)
    return batch_update(
        sid,
        [
            {
                "updateFilterView": {
                    "filter": {"filterViewId": filter_view_id, "title": title},
                    "fields": "title",
                },
            },
        ],
        account,
    )


def delete_filter_view(
    spreadsheet_id: str,
    filter_view_id: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Delete a filter view by id."""
    sid = require_spreadsheet_id(spreadsheet_id)
    fid = _require_nonneg_int(filter_view_id, "filter_view_id")
    return batch_update(
        sid,
        [{"deleteFilterView": {"filterId": fid}}],
        account,
    )


def duplicate_filter_view(
    spreadsheet_id: str,
    filter_view_id: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Duplicate a filter view by id."""
    sid = require_spreadsheet_id(spreadsheet_id)
    fid = _require_nonneg_int(filter_view_id, "filter_view_id")
    return batch_update(
        sid,
        [{"duplicateFilterView": {"filterId": fid}}],
        account,
    )


def add_slicer(
    spreadsheet_id: str,
    sheet_id: int,
    spec: dict,
    account: str | None = None,
) -> dict[str, Any]:
    """Add a slicer anchored at the sheet origin."""
    sid = require_spreadsheet_id(spreadsheet_id)
    sheet = require_sheet_id(sheet_id)
    slicer_spec = _require_spec(spec)
    return batch_update(
        sid,
        [
            {
                "addSlicer": {
                    "slicer": {
                        "spec": slicer_spec,
                        "position": {
                            "overlayPosition": {
                                "anchorCell": {
                                    "sheetId": sheet,
                                    "rowIndex": 0,
                                    "columnIndex": 0,
                                },
                            },
                        },
                    },
                },
            },
        ],
        account,
    )


def update_slicer(
    spreadsheet_id: str,
    slicer_id: int,
    spec: dict,
    account: str | None = None,
) -> dict[str, Any]:
    """Replace a slicer spec."""
    sid = require_spreadsheet_id(spreadsheet_id)
    sid_int = _require_nonneg_int(slicer_id, "slicer_id")
    slicer_spec = _require_spec(spec)
    return batch_update(
        sid,
        [
            {
                "updateSlicerSpec": {
                    "slicerId": sid_int,
                    "spec": slicer_spec,
                    "fields": "*",
                },
            },
        ],
        account,
    )


def set_data_validation(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    condition_type: str,
    values: list[str],
    account: str | None = None,
) -> dict[str, Any]:
    """Apply data validation to a grid range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    ctype = _require_condition_type(condition_type)
    return batch_update(
        sid,
        [
            {
                "setDataValidation": {
                    "range": grid_range(
                        sheet_id, start_row, end_row, start_column, end_column
                    ),
                    "rule": {
                        "condition": {
                            "type": ctype,
                            "values": _condition_values(values),
                        },
                        "strict": True,
                        "showCustomUi": True,
                    },
                },
            },
        ],
        account,
    )


def add_conditional_format(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    condition_type: str,
    values: list[str],
    account: str | None = None,
) -> dict[str, Any]:
    """Add a conditional format rule at index zero."""
    sid = require_spreadsheet_id(spreadsheet_id)
    return batch_update(
        sid,
        [
            {
                "addConditionalFormatRule": {
                    "index": 0,
                    "rule": _conditional_boolean_rule(
                        sheet_id,
                        start_row,
                        end_row,
                        start_column,
                        end_column,
                        condition_type,
                        values,
                    ),
                },
            },
        ],
        account,
    )


def update_conditional_format(
    spreadsheet_id: str,
    sheet_id: int,
    index: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    condition_type: str,
    values: list[str],
    account: str | None = None,
) -> dict[str, Any]:
    """Update a conditional format rule on a sheet."""
    sid = require_spreadsheet_id(spreadsheet_id)
    idx = _require_nonneg_int(index, "index")
    sheet = require_sheet_id(sheet_id)
    return batch_update(
        sid,
        [
            {
                "updateConditionalFormatRule": {
                    "index": idx,
                    "sheetId": sheet,
                    "rule": _conditional_boolean_rule(
                        sheet_id,
                        start_row,
                        end_row,
                        start_column,
                        end_column,
                        condition_type,
                        values,
                    ),
                },
            },
        ],
        account,
    )


def delete_conditional_format(
    spreadsheet_id: str,
    sheet_id: int,
    index: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Delete a conditional format rule by index."""
    sid = require_spreadsheet_id(spreadsheet_id)
    sheet = require_sheet_id(sheet_id)
    idx = _require_nonneg_int(index, "index")
    return batch_update(
        sid,
        [{"deleteConditionalFormatRule": {"sheetId": sheet, "index": idx}}],
        account,
    )
