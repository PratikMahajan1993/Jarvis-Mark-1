from __future__ import annotations

from typing import Any

from app.connectors.sheets_toolkit.client import (
    SheetsToolkitError,
    batch_update,
    grid_range,
    require_sheet_id,
    require_spreadsheet_id,
)


def _require_non_blank_str(value: str, field: str) -> str:
    if not str(value or "").strip():
        raise SheetsToolkitError(f"{field} is required")
    return value


def _require_int_id(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SheetsToolkitError(f"{field} must be an int >= 0")
    return value


def _require_non_empty_dict(value: dict, field: str = "data_source") -> dict:
    if not isinstance(value, dict) or not value:
        raise SheetsToolkitError(f"{field} must be a non-empty dict")
    return value


def add_named_range(
    spreadsheet_id: str,
    name: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Add a named range on a sheet grid."""
    sid = require_spreadsheet_id(spreadsheet_id)
    _require_non_blank_str(name, "name")
    return batch_update(
        sid,
        [
            {
                "addNamedRange": {
                    "namedRange": {
                        "name": name,
                        "range": grid_range(
                            sheet_id, start_row, end_row, start_column, end_column
                        ),
                    }
                }
            }
        ],
        account=account,
    )


def update_named_range(
    spreadsheet_id: str,
    named_range_id: str,
    name: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Rename an existing named range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    _require_non_blank_str(named_range_id, "named_range_id")
    _require_non_blank_str(name, "name")
    return batch_update(
        sid,
        [
            {
                "updateNamedRange": {
                    "namedRange": {"namedRangeId": named_range_id, "name": name},
                    "fields": "name",
                }
            }
        ],
        account=account,
    )


def delete_named_range(
    spreadsheet_id: str,
    named_range_id: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Delete a named range by id."""
    sid = require_spreadsheet_id(spreadsheet_id)
    _require_non_blank_str(named_range_id, "named_range_id")
    return batch_update(
        sid,
        [{"deleteNamedRange": {"namedRangeId": named_range_id}}],
        account=account,
    )


def add_protected_range(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    description: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Add a warning-only protected range on a grid."""
    sid = require_spreadsheet_id(spreadsheet_id)
    return batch_update(
        sid,
        [
            {
                "addProtectedRange": {
                    "protectedRange": {
                        "range": grid_range(
                            sheet_id, start_row, end_row, start_column, end_column
                        ),
                        "description": description,
                        "warningOnly": True,
                    }
                }
            }
        ],
        account=account,
    )


def update_protected_range(
    spreadsheet_id: str,
    protected_range_id: int,
    description: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Update the description of a protected range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    pid = _require_int_id(protected_range_id, "protected_range_id")
    return batch_update(
        sid,
        [
            {
                "updateProtectedRange": {
                    "protectedRange": {
                        "protectedRangeId": pid,
                        "description": description,
                    },
                    "fields": "description",
                }
            }
        ],
        account=account,
    )


def delete_protected_range(
    spreadsheet_id: str,
    protected_range_id: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Delete a protected range by id."""
    sid = require_spreadsheet_id(spreadsheet_id)
    pid = _require_int_id(protected_range_id, "protected_range_id")
    return batch_update(
        sid,
        [{"deleteProtectedRange": {"protectedRangeId": pid}}],
        account=account,
    )


def add_table(
    spreadsheet_id: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_column: int,
    end_column: int,
    name: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Add a table over a grid range."""
    sid = require_spreadsheet_id(spreadsheet_id)
    _require_non_blank_str(name, "name")
    return batch_update(
        sid,
        [
            {
                "addTable": {
                    "table": {
                        "name": name,
                        "range": grid_range(
                            sheet_id, start_row, end_row, start_column, end_column
                        ),
                    }
                }
            }
        ],
        account=account,
    )


def update_table(
    spreadsheet_id: str,
    table_id: str,
    name: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Rename an existing table."""
    sid = require_spreadsheet_id(spreadsheet_id)
    _require_non_blank_str(table_id, "table_id")
    _require_non_blank_str(name, "name")
    return batch_update(
        sid,
        [
            {
                "updateTable": {
                    "table": {"tableId": table_id, "name": name},
                    "fields": "name",
                }
            }
        ],
        account=account,
    )


def delete_table(
    spreadsheet_id: str,
    table_id: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Delete a table by id."""
    sid = require_spreadsheet_id(spreadsheet_id)
    _require_non_blank_str(table_id, "table_id")
    return batch_update(
        sid,
        [{"deleteTable": {"tableId": table_id}}],
        account=account,
    )


def create_developer_metadata(
    spreadsheet_id: str,
    key: str,
    value: str,
    sheet_id: int | None = None,
    account: str | None = None,
) -> dict[str, Any]:
    """Create spreadsheet- or sheet-scoped developer metadata."""
    sid = require_spreadsheet_id(spreadsheet_id)
    _require_non_blank_str(key, "key")
    if sheet_id is None:
        location: dict[str, Any] = {"spreadsheet": True}
    else:
        location = {"sheetId": require_sheet_id(sheet_id)}
    return batch_update(
        sid,
        [
            {
                "createDeveloperMetadata": {
                    "developerMetadata": {
                        "metadataKey": key,
                        "metadataValue": value,
                        "visibility": "DOCUMENT",
                        "location": location,
                    }
                }
            }
        ],
        account=account,
    )


def update_developer_metadata(
    spreadsheet_id: str,
    metadata_id: int,
    value: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Update developer metadata value by metadata id."""
    sid = require_spreadsheet_id(spreadsheet_id)
    mid = _require_int_id(metadata_id, "metadata_id")
    return batch_update(
        sid,
        [
            {
                "updateDeveloperMetadata": {
                    "dataFilters": [
                        {"developerMetadataLookup": {"metadataId": mid}}
                    ],
                    "developerMetadata": {"metadataValue": value},
                    "fields": "metadataValue",
                }
            }
        ],
        account=account,
    )


def delete_developer_metadata(
    spreadsheet_id: str,
    metadata_id: int,
    account: str | None = None,
) -> dict[str, Any]:
    """Delete developer metadata by metadata id."""
    sid = require_spreadsheet_id(spreadsheet_id)
    mid = _require_int_id(metadata_id, "metadata_id")
    return batch_update(
        sid,
        [
            {
                "deleteDeveloperMetadata": {
                    "dataFilter": {"developerMetadataLookup": {"metadataId": mid}}
                }
            }
        ],
        account=account,
    )


def add_data_source(
    spreadsheet_id: str,
    data_source: dict,
    account: str | None = None,
) -> dict[str, Any]:
    """Add a connected data source to the spreadsheet."""
    sid = require_spreadsheet_id(spreadsheet_id)
    ds = _require_non_empty_dict(data_source)
    if "spec" not in ds:
        raise SheetsToolkitError('data_source must contain key "spec"')
    return batch_update(
        sid,
        [{"addDataSource": {"dataSource": ds}}],
        account=account,
    )


def update_data_source(
    spreadsheet_id: str,
    data_source: dict,
    fields: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Update fields on an existing data source."""
    sid = require_spreadsheet_id(spreadsheet_id)
    ds = _require_non_empty_dict(data_source)
    _require_non_blank_str(fields, "fields")
    return batch_update(
        sid,
        [{"updateDataSource": {"dataSource": ds, "fields": fields}}],
        account=account,
    )


def delete_data_source(
    spreadsheet_id: str,
    data_source_id: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Remove a data source from the spreadsheet."""
    sid = require_spreadsheet_id(spreadsheet_id)
    _require_non_blank_str(data_source_id, "data_source_id")
    return batch_update(
        sid,
        [{"deleteDataSource": {"dataSourceId": data_source_id}}],
        account=account,
    )


def refresh_data_source(
    spreadsheet_id: str,
    data_source_id: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Force-refresh a connected data source."""
    sid = require_spreadsheet_id(spreadsheet_id)
    dsid = _require_non_blank_str(data_source_id, "data_source_id")
    return batch_update(
        sid,
        [
            {
                "refreshDataSource": {
                    "force": True,
                    "references": {"references": [{"dataSourceId": dsid}]},
                }
            }
        ],
        account=account,
    )


def cancel_data_source_refresh(
    spreadsheet_id: str,
    data_source_id: str,
    account: str | None = None,
) -> dict[str, Any]:
    """Cancel an in-progress data source refresh."""
    sid = require_spreadsheet_id(spreadsheet_id)
    dsid = _require_non_blank_str(data_source_id, "data_source_id")
    return batch_update(
        sid,
        [
            {
                "cancelDataSourceRefresh": {
                    "isAll": False,
                    "references": {"references": [{"dataSourceId": dsid}]},
                }
            }
        ],
        account=account,
    )
