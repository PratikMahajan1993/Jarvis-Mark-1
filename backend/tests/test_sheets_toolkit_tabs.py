from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from app.connectors.sheets_toolkit.client import SheetsToolkitError
from app.connectors.sheets_toolkit import tabs as tabs_mod


def test_list_tabs(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {
                "sheets": [
                    {"properties": {"sheetId": 0, "title": "A", "index": 0}},
                    {"properties": {"sheetId": 1, "title": "B", "index": 1, "hidden": True}},
                ]
            }

    class _Spreadsheets:
        def get(self, spreadsheetId, fields):
            captured["spreadsheetId"] = spreadsheetId
            captured["fields"] = fields
            return _Call()

    class _Service:
        def spreadsheets(self):
            return _Spreadsheets()

    monkeypatch.setattr(tabs_mod, "sheets_service", lambda account=None: _Service())
    out = tabs_mod.list_tabs(" sid ", account="shop")
    assert captured["spreadsheetId"] == "sid"
    assert captured["fields"] == "sheets.properties(sheetId,title,index,hidden)"
    assert out == [
        {"sheet_id": 0, "title": "A", "index": 0, "hidden": False},
        {"sheet_id": 1, "title": "B", "index": 1, "hidden": True},
    ]


def test_add_tab(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["spreadsheet_id"] = spreadsheet_id
        captured["requests"] = requests
        captured["account"] = account
        return {"replies": [{}]}

    monkeypatch.setattr(tabs_mod, "batch_update", _batch_update)
    out = tabs_mod.add_tab("sid", "Reports", account="a", row_count=500, column_count=10)
    assert out["replies"] == [{}]
    assert captured["requests"] == [
        {
            "addSheet": {
                "properties": {
                    "title": "Reports",
                    "gridProperties": {"rowCount": 500, "columnCount": 10},
                }
            }
        }
    ]
    with pytest.raises(SheetsToolkitError):
        tabs_mod.add_tab("sid", "  ", row_count=1, column_count=1)


def test_delete_tab(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{"deleteSheet": {}}]}

    monkeypatch.setattr(tabs_mod, "batch_update", _batch_update)
    out = tabs_mod.delete_tab("sid", 3, account="x")
    assert out["replies"][0]["deleteSheet"] == {}
    assert captured["requests"] == [{"deleteSheet": {"sheetId": 3}}]


def test_rename_tab(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(tabs_mod, "batch_update", _batch_update)
    tabs_mod.rename_tab("sid", 2, "New name")
    assert captured["requests"] == [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": 2, "title": "New name"},
                "fields": "title",
            }
        }
    ]


def test_duplicate_tab(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(tabs_mod, "batch_update", _batch_update)
    tabs_mod.duplicate_tab("sid", 1, "Copy of One")
    assert captured["requests"] == [
        {"duplicateSheet": {"sourceSheetId": 1, "newSheetName": "Copy of One"}}
    ]


def test_copy_tab_to(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {"sheetId": 99, "title": "Copy"}

    class _Sheets:
        def copyTo(self, spreadsheetId, sheetId, body):
            captured["spreadsheetId"] = spreadsheetId
            captured["sheetId"] = sheetId
            captured["body"] = body
            return _Call()

    class _Spreadsheets:
        def sheets(self):
            return _Sheets()

    class _Service:
        def spreadsheets(self):
            return _Spreadsheets()

    monkeypatch.setattr(tabs_mod, "sheets_service", lambda account=None: _Service())
    out = tabs_mod.copy_tab_to("src", 4, " dest ")
    assert out == {"sheetId": 99, "title": "Copy"}
    assert captured["spreadsheetId"] == "src"
    assert captured["sheetId"] == 4
    assert captured["body"] == {"destinationSpreadsheetId": "dest"}


def test_reorder_tab(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(tabs_mod, "batch_update", _batch_update)
    tabs_mod.reorder_tab("sid", 0, 2)
    assert captured["requests"] == [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": 0, "index": 2},
                "fields": "index",
            }
        }
    ]
    with pytest.raises(SheetsToolkitError):
        tabs_mod.reorder_tab("sid", 0, -1)


def test_set_tab_hidden(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(tabs_mod, "batch_update", _batch_update)
    tabs_mod.set_tab_hidden("sid", 1, True)
    assert captured["requests"] == [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": 1, "hidden": True},
                "fields": "hidden",
            }
        }
    ]
    with pytest.raises(SheetsToolkitError):
        tabs_mod.set_tab_hidden("sid", 1, 1)


def test_set_tab_color(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(tabs_mod, "batch_update", _batch_update)
    tabs_mod.set_tab_color("sid", 0, 1.0, 0.5, 0.0)
    assert captured["requests"] == [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": 0,
                    "tabColor": {"red": 1.0, "green": 0.5, "blue": 0.0},
                },
                "fields": "tabColor",
            }
        }
    ]
    with pytest.raises(SheetsToolkitError):
        tabs_mod.set_tab_color("sid", 0, 1.5, 0.0, 0.0)


def test_freeze_tab(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(tabs_mod, "batch_update", _batch_update)
    tabs_mod.freeze_tab("sid", 2, 1, 3)
    assert captured["requests"] == [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": 2,
                    "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 3},
                },
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
            }
        }
    ]
    with pytest.raises(SheetsToolkitError):
        tabs_mod.freeze_tab("sid", 2, -1, 0)
