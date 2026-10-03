from __future__ import annotations

from app.connectors.sheets_toolkit.client import (
    SheetsToolkitError,
    batch_update,
    drive_service,
    require_spreadsheet_id,
    sheets_service,
)

_ALLOWED_WORKBOOK_PROPERTY_KEYS = frozenset(
    {
        "title",
        "locale",
        "timeZone",
        "autoRecalc",
        "iterativeCalculationSettings",
    }
)

_SHARE_ROLES = frozenset({"reader", "commenter", "writer"})


def _require_non_blank_title(title: str) -> str:
    text = str(title or "").strip()
    if not text:
        raise SheetsToolkitError("title is required")
    return text


def _escape_drive_query_name(name: str) -> str:
    return str(name).replace("'", "''")


def create_workbook(title: str, account: str | None = None) -> dict:
    """Create a new spreadsheet with the given title."""
    clean_title = _require_non_blank_title(title)
    return (
        sheets_service(account)
        .spreadsheets()
        .create(
            body={"properties": {"title": clean_title}},
            fields="spreadsheetId,spreadsheetUrl,properties.title",
        )
        .execute()
    )


def get_workbook(spreadsheet_id: str, account: str | None = None) -> dict:
    """Fetch spreadsheet metadata including sheet tab properties."""
    sid = require_spreadsheet_id(spreadsheet_id)
    return (
        sheets_service(account)
        .spreadsheets()
        .get(
            spreadsheetId=sid,
            fields="spreadsheetId,properties,sheets.properties,spreadsheetUrl",
        )
        .execute()
    )


def update_workbook_properties(
    spreadsheet_id: str,
    properties: dict,
    account: str | None = None,
) -> dict:
    """Update allowed top-level spreadsheet properties."""
    if not isinstance(properties, dict) or not properties:
        raise SheetsToolkitError("properties must be a non-empty dict")
    unknown = set(properties.keys()) - _ALLOWED_WORKBOOK_PROPERTY_KEYS
    if unknown:
        raise SheetsToolkitError(f"unknown property keys: {sorted(unknown)}")
    sid = require_spreadsheet_id(spreadsheet_id)
    fields = ",".join(properties.keys())
    return batch_update(
        sid,
        [
            {
                "updateSpreadsheetProperties": {
                    "properties": properties,
                    "fields": fields,
                }
            }
        ],
        account,
    )


def find_workbooks(
    name: str,
    limit: int = 8,
    account: str | None = None,
) -> list[dict]:
    """Search Drive for spreadsheets whose name contains the given text."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 50:
        raise SheetsToolkitError("limit must be between 1 and 50")
    escaped = _escape_drive_query_name(name)
    q = (
        f"name contains '{escaped}' and mimeType='application/vnd.google-apps.spreadsheet' "
        "and trashed=false"
    )
    result = (
        drive_service(account)
        .files()
        .list(
            q=q,
            pageSize=limit,
            fields="files(id,name,webViewLink)",
            orderBy="modifiedTime desc",
        )
        .execute()
    )
    files = result.get("files", []) if isinstance(result, dict) else []
    return [
        {
            "spreadsheet_id": item["id"],
            "title": item["name"],
            "url": item["webViewLink"],
        }
        for item in files
        if isinstance(item, dict)
    ]


def copy_workbook(
    spreadsheet_id: str,
    title: str,
    account: str | None = None,
) -> dict:
    """Copy a spreadsheet in Drive under a new title."""
    sid = require_spreadsheet_id(spreadsheet_id)
    clean_title = _require_non_blank_title(title)
    result = (
        drive_service(account)
        .files()
        .copy(
            fileId=sid,
            body={"name": clean_title},
            fields="id,name,webViewLink",
        )
        .execute()
    )
    return {
        "spreadsheet_id": result["id"],
        "title": result["name"],
        "url": result["webViewLink"],
    }


def trash_workbook(spreadsheet_id: str, account: str | None = None) -> dict:
    """Move a spreadsheet to the Drive trash."""
    sid = require_spreadsheet_id(spreadsheet_id)
    return (
        drive_service(account)
        .files()
        .update(fileId=sid, body={"trashed": True}, fields="id,trashed")
        .execute()
    )


def share_workbook(
    spreadsheet_id: str,
    email: str,
    role: str = "reader",
    account: str | None = None,
) -> dict:
    """Grant a user permission on a spreadsheet."""
    sid = require_spreadsheet_id(spreadsheet_id)
    address = str(email or "").strip()
    if "@" not in address:
        raise SheetsToolkitError("email must contain @")
    if role not in _SHARE_ROLES:
        raise SheetsToolkitError("role must be reader, commenter, or writer")
    return (
        drive_service(account)
        .permissions()
        .create(
            fileId=sid,
            body={"type": "user", "role": role, "emailAddress": address},
            sendNotificationEmail=False,
            fields="id,role,emailAddress",
        )
        .execute()
    )


def unshare_workbook(
    spreadsheet_id: str,
    permission_id: str,
    account: str | None = None,
) -> dict:
    """Remove a permission from a spreadsheet."""
    sid = require_spreadsheet_id(spreadsheet_id)
    pid = str(permission_id or "").strip()
    if not pid:
        raise SheetsToolkitError("permission_id is required")
    (
        drive_service(account)
        .permissions()
        .delete(fileId=sid, permissionId=pid)
        .execute()
    )
    return {"spreadsheet_id": sid, "permission_id": pid, "deleted": True}
