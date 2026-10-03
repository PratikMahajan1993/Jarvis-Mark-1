from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from app.connectors.sheets_toolkit.client import SheetsToolkitError
from app.connectors.sheets_toolkit.workbook import (
    copy_workbook,
    create_workbook,
    find_workbooks,
    get_workbook,
    share_workbook,
    trash_workbook,
    unshare_workbook,
    update_workbook_properties,
)


def test_create_workbook(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {
                "spreadsheetId": "new-id",
                "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/new-id/edit",
                "properties": {"title": "Shop Log"},
            }

    class _Spreadsheets:
        def create(self, body, fields):
            captured["body"] = body
            captured["fields"] = fields
            return _Call()

    class _Service:
        def spreadsheets(self):
            return _Spreadsheets()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.workbook.sheets_service",
        lambda account=None: _Service(),
    )
    out = create_workbook("Shop Log", account="shop")
    assert out["spreadsheetId"] == "new-id"
    assert captured["body"] == {"properties": {"title": "Shop Log"}}
    assert captured["fields"] == "spreadsheetId,spreadsheetUrl,properties.title"
    with pytest.raises(SheetsToolkitError):
        create_workbook("  ")


def test_get_workbook(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {"spreadsheetId": "sid", "properties": {"title": "T"}, "sheets": []}

    class _Spreadsheets:
        def get(self, spreadsheetId, fields):
            captured["spreadsheetId"] = spreadsheetId
            captured["fields"] = fields
            return _Call()

    class _Service:
        def spreadsheets(self):
            return _Spreadsheets()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.workbook.sheets_service",
        lambda account=None: _Service(),
    )
    out = get_workbook(" sid ", account="shop")
    assert out["spreadsheetId"] == "sid"
    assert captured["spreadsheetId"] == "sid"
    assert captured["fields"] == "spreadsheetId,properties,sheets.properties,spreadsheetUrl"


def test_update_workbook_properties(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["spreadsheet_id"] = spreadsheet_id
        captured["requests"] = requests
        captured["account"] = account
        return {"spreadsheetId": spreadsheet_id, "replies": [{}]}

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.workbook.batch_update",
        _batch_update,
    )
    out = update_workbook_properties(
        "sid",
        {"title": "Renamed", "locale": "en_US"},
        account="shop",
    )
    assert out["spreadsheetId"] == "sid"
    req = captured["requests"][0]["updateSpreadsheetProperties"]
    assert req["properties"] == {"title": "Renamed", "locale": "en_US"}
    assert set(req["fields"].split(",")) == {"title", "locale"}
    with pytest.raises(SheetsToolkitError):
        update_workbook_properties("sid", {"badKey": 1})


def test_find_workbooks(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {
                "files": [
                    {
                        "id": "f1",
                        "name": "O'Brien Parts",
                        "webViewLink": "https://drive/f1",
                    }
                ]
            }

    class _Files:
        def list(self, q, pageSize, fields, orderBy):
            captured["q"] = q
            captured["pageSize"] = pageSize
            captured["fields"] = fields
            captured["orderBy"] = orderBy
            return _Call()

    class _Service:
        def files(self):
            return _Files()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.workbook.drive_service",
        lambda account=None: _Service(),
    )
    out = find_workbooks("O'Brien", limit=5, account="shop")
    assert out == [
        {
            "spreadsheet_id": "f1",
            "title": "O'Brien Parts",
            "url": "https://drive/f1",
        }
    ]
    assert "O''Brien" in captured["q"]
    assert captured["pageSize"] == 5
    with pytest.raises(SheetsToolkitError):
        find_workbooks("x", limit=0)


def test_copy_workbook(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {"id": "copy-id", "name": "Copy Title", "webViewLink": "https://drive/copy"}

    class _Files:
        def copy(self, fileId, body, fields):
            captured["fileId"] = fileId
            captured["body"] = body
            captured["fields"] = fields
            return _Call()

    class _Service:
        def files(self):
            return _Files()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.workbook.drive_service",
        lambda account=None: _Service(),
    )
    out = copy_workbook("src-id", "Copy Title", account="shop")
    assert out == {
        "spreadsheet_id": "copy-id",
        "title": "Copy Title",
        "url": "https://drive/copy",
    }
    assert captured["fileId"] == "src-id"
    assert captured["body"] == {"name": "Copy Title"}
    with pytest.raises(SheetsToolkitError):
        copy_workbook("src-id", "")


def test_trash_workbook(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {"id": "sid", "trashed": True}

    class _Files:
        def update(self, fileId, body, fields):
            captured["fileId"] = fileId
            captured["body"] = body
            captured["fields"] = fields
            return _Call()

    class _Service:
        def files(self):
            return _Files()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.workbook.drive_service",
        lambda account=None: _Service(),
    )
    out = trash_workbook("sid", account="shop")
    assert out == {"id": "sid", "trashed": True}
    assert captured["body"] == {"trashed": True}
    assert captured["fields"] == "id,trashed"


def test_share_workbook(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {"id": "perm-1", "role": "writer", "emailAddress": "a@b.com"}

    class _Permissions:
        def create(self, fileId, body, sendNotificationEmail, fields):
            captured["fileId"] = fileId
            captured["body"] = body
            captured["sendNotificationEmail"] = sendNotificationEmail
            captured["fields"] = fields
            return _Call()

    class _Service:
        def permissions(self):
            return _Permissions()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.workbook.drive_service",
        lambda account=None: _Service(),
    )
    out = share_workbook("sid", "a@b.com", role="writer", account="shop")
    assert out["role"] == "writer"
    assert captured["body"] == {
        "type": "user",
        "role": "writer",
        "emailAddress": "a@b.com",
    }
    assert captured["sendNotificationEmail"] is False
    with pytest.raises(SheetsToolkitError):
        share_workbook("sid", "not-an-email", role="reader")


def test_unshare_workbook(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return None

    class _Permissions:
        def delete(self, fileId, permissionId):
            captured["fileId"] = fileId
            captured["permissionId"] = permissionId
            return _Call()

    class _Service:
        def permissions(self):
            return _Permissions()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.workbook.drive_service",
        lambda account=None: _Service(),
    )
    out = unshare_workbook("sid", "perm-9", account="shop")
    assert out == {
        "spreadsheet_id": "sid",
        "permission_id": "perm-9",
        "deleted": True,
    }
    assert captured["permissionId"] == "perm-9"
    with pytest.raises(SheetsToolkitError):
        unshare_workbook("sid", "  ")
