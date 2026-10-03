from __future__ import annotations

from app.connectors.sheets_toolkit.client import (
    SheetsToolkitError,
    require_spreadsheet_id,
    sheets_service,
)

_VALUE_RENDER_OPTIONS = frozenset(
    {"UNFORMATTED_VALUE", "FORMATTED_VALUE", "FORMULA"}
)
_VALUE_INPUT_OPTIONS = frozenset({"USER_ENTERED", "RAW"})


def _require_non_blank_a1(a1: str) -> str:
    text = str(a1 or "").strip()
    if not text:
        raise SheetsToolkitError("a1 range is required")
    return text


def _require_values(values: list[list]) -> list[list]:
    if not isinstance(values, list):
        raise SheetsToolkitError("values must be a list of lists")
    for row in values:
        if not isinstance(row, list):
            raise SheetsToolkitError("values must be a list of lists")
    return values


def _require_value_render(value_render: str) -> str:
    if value_render not in _VALUE_RENDER_OPTIONS:
        raise SheetsToolkitError(
            "value_render must be UNFORMATTED_VALUE, FORMATTED_VALUE, or FORMULA"
        )
    return value_render


def _require_value_input(value_input: str) -> str:
    if value_input not in _VALUE_INPUT_OPTIONS:
        raise SheetsToolkitError("value_input must be USER_ENTERED or RAW")
    return value_input


def _require_non_empty_ranges(a1_ranges: list[str]) -> list[str]:
    if not isinstance(a1_ranges, list) or not a1_ranges:
        raise SheetsToolkitError("ranges must be a non-empty list")
    return [_require_non_blank_a1(r) for r in a1_ranges]


def _require_batch_data(data: list[dict]) -> list[dict]:
    if not isinstance(data, list):
        raise SheetsToolkitError("data must be a list")
    for item in data:
        if not isinstance(item, dict):
            raise SheetsToolkitError("each data item must be a dict")
        if "range" not in item or "values" not in item:
            raise SheetsToolkitError("each data item must have range and values")
        _require_non_blank_a1(item["range"])
        _require_values(item["values"])
    return data


def read_range(
    spreadsheet_id: str,
    a1: str,
    account: str | None = None,
    value_render: str = "FORMATTED_VALUE",
) -> dict:
    """Read a single A1 range from a spreadsheet."""
    sid = require_spreadsheet_id(spreadsheet_id)
    a1_clean = _require_non_blank_a1(a1)
    render = _require_value_render(value_render)
    return (
        sheets_service(account)
        .spreadsheets()
        .values()
        .get(
            spreadsheetId=sid,
            range=a1_clean,
            valueRenderOption=render,
        )
        .execute()
    )


def read_ranges(
    spreadsheet_id: str,
    a1_ranges: list[str],
    account: str | None = None,
    value_render: str = "FORMATTED_VALUE",
) -> dict:
    """Read multiple A1 ranges in one batchGet call."""
    sid = require_spreadsheet_id(spreadsheet_id)
    ranges = _require_non_empty_ranges(a1_ranges)
    render = _require_value_render(value_render)
    return (
        sheets_service(account)
        .spreadsheets()
        .values()
        .batchGet(
            spreadsheetId=sid,
            ranges=ranges,
            valueRenderOption=render,
        )
        .execute()
    )


def write_range(
    spreadsheet_id: str,
    a1: str,
    values: list[list],
    account: str | None = None,
    value_input: str = "USER_ENTERED",
) -> dict:
    """Write a 2D values grid to a single A1 range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    a1_clean = _require_non_blank_a1(a1)
    rows = _require_values(values)
    option = _require_value_input(value_input)
    return (
        sheets_service(account)
        .spreadsheets()
        .values()
        .update(
            spreadsheetId=sid,
            range=a1_clean,
            valueInputOption=option,
            body={"values": rows},
        )
        .execute()
    )


def write_ranges(
    spreadsheet_id: str,
    data: list[dict],
    account: str | None = None,
    value_input: str = "USER_ENTERED",
) -> dict:
    """Write multiple ranges in one batchUpdate call."""
    sid = require_spreadsheet_id(spreadsheet_id)
    payload = _require_batch_data(data)
    option = _require_value_input(value_input)
    return (
        sheets_service(account)
        .spreadsheets()
        .values()
        .batchUpdate(
            spreadsheetId=sid,
            body={"valueInputOption": option, "data": payload},
        )
        .execute()
    )


def append_rows(
    spreadsheet_id: str,
    a1: str,
    values: list[list],
    account: str | None = None,
    value_input: str = "USER_ENTERED",
) -> dict:
    """Append rows below an A1 range with INSERT_ROWS."""
    sid = require_spreadsheet_id(spreadsheet_id)
    a1_clean = _require_non_blank_a1(a1)
    rows = _require_values(values)
    option = _require_value_input(value_input)
    return (
        sheets_service(account)
        .spreadsheets()
        .values()
        .append(
            spreadsheetId=sid,
            range=a1_clean,
            valueInputOption=option,
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        )
        .execute()
    )


def clear_range(
    spreadsheet_id: str,
    a1: str,
    account: str | None = None,
) -> dict:
    """Clear all values in a single A1 range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    a1_clean = _require_non_blank_a1(a1)
    return (
        sheets_service(account)
        .spreadsheets()
        .values()
        .clear(
            spreadsheetId=sid,
            range=a1_clean,
            body={},
        )
        .execute()
    )


def clear_ranges(
    spreadsheet_id: str,
    a1_ranges: list[str],
    account: str | None = None,
) -> dict:
    """Clear multiple A1 ranges in one batchClear call."""
    sid = require_spreadsheet_id(spreadsheet_id)
    ranges = _require_non_empty_ranges(a1_ranges)
    return (
        sheets_service(account)
        .spreadsheets()
        .values()
        .batchClear(
            spreadsheetId=sid,
            body={"ranges": ranges},
        )
        .execute()
    )
