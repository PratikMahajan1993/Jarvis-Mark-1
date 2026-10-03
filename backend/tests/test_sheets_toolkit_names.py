from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.connectors.sheets_toolkit import names as names_mod


def test_add_named_range(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["spreadsheet_id"] = spreadsheet_id
        captured["requests"] = requests
        captured["account"] = account
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    out = names_mod.add_named_range("sid", "MyRange", 1, 0, 2, 0, 3, account="a")
    assert out == {"replies": [{}]}
    assert captured["spreadsheet_id"] == "sid"
    assert captured["account"] == "a"
    assert captured["requests"] == [
        {
            "addNamedRange": {
                "namedRange": {
                    "name": "MyRange",
                    "range": {
                        "sheetId": 1,
                        "startRowIndex": 0,
                        "endRowIndex": 2,
                        "startColumnIndex": 0,
                        "endColumnIndex": 3,
                    },
                }
            }
        }
    ]


def test_update_named_range(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.update_named_range("sid", "nr-1", "Renamed")
    assert captured["requests"] == [
        {
            "updateNamedRange": {
                "namedRange": {"namedRangeId": "nr-1", "name": "Renamed"},
                "fields": "name",
            }
        }
    ]


def test_delete_named_range(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.delete_named_range("sid", "nr-9")
    assert captured["requests"] == [{"deleteNamedRange": {"namedRangeId": "nr-9"}}]


def test_add_protected_range(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.add_protected_range("sid", 0, 1, 5, 2, 4, "")
    assert captured["requests"] == [
        {
            "addProtectedRange": {
                "protectedRange": {
                    "range": {
                        "sheetId": 0,
                        "startRowIndex": 1,
                        "endRowIndex": 5,
                        "startColumnIndex": 2,
                        "endColumnIndex": 4,
                    },
                    "description": "",
                    "warningOnly": True,
                }
            }
        }
    ]


def test_update_protected_range(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.update_protected_range("sid", 7, "locked area")
    assert captured["requests"] == [
        {
            "updateProtectedRange": {
                "protectedRange": {"protectedRangeId": 7, "description": "locked area"},
                "fields": "description",
            }
        }
    ]


def test_delete_protected_range(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.delete_protected_range("sid", 3)
    assert captured["requests"] == [{"deleteProtectedRange": {"protectedRangeId": 3}}]


def test_add_table(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.add_table("sid", 2, 0, 10, 0, 5, "Sales")
    assert captured["requests"] == [
        {
            "addTable": {
                "table": {
                    "name": "Sales",
                    "range": {
                        "sheetId": 2,
                        "startRowIndex": 0,
                        "endRowIndex": 10,
                        "startColumnIndex": 0,
                        "endColumnIndex": 5,
                    },
                }
            }
        }
    ]


def test_update_table(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.update_table("sid", "tbl-1", "NewTable")
    assert captured["requests"] == [
        {
            "updateTable": {
                "table": {"tableId": "tbl-1", "name": "NewTable"},
                "fields": "name",
            }
        }
    ]


def test_delete_table(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.delete_table("sid", "tbl-2")
    assert captured["requests"] == [{"deleteTable": {"tableId": "tbl-2"}}]


def test_create_developer_metadata(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.create_developer_metadata("sid", "k1", "v1", sheet_id=4)
    assert captured["requests"] == [
        {
            "createDeveloperMetadata": {
                "developerMetadata": {
                    "metadataKey": "k1",
                    "metadataValue": "v1",
                    "visibility": "DOCUMENT",
                    "location": {"sheetId": 4},
                }
            }
        }
    ]


def test_update_developer_metadata(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.update_developer_metadata("sid", 99, "next")
    assert captured["requests"] == [
        {
            "updateDeveloperMetadata": {
                "dataFilters": [{"developerMetadataLookup": {"metadataId": 99}}],
                "developerMetadata": {"metadataValue": "next"},
                "fields": "metadataValue",
            }
        }
    ]


def test_delete_developer_metadata(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.delete_developer_metadata("sid", 12)
    assert captured["requests"] == [
        {
            "deleteDeveloperMetadata": {
                "dataFilter": {"developerMetadataLookup": {"metadataId": 12}}
            }
        }
    ]


def test_add_data_source(monkeypatch):
    captured: dict = {}
    ds = {"spec": {"bigQuery": {"projectId": "p"}}}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.add_data_source("sid", ds)
    assert captured["requests"] == [{"addDataSource": {"dataSource": ds}}]


def test_update_data_source(monkeypatch):
    captured: dict = {}
    ds = {"dataSourceId": "ds-1", "spec": {}}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.update_data_source("sid", ds, "spec")
    assert captured["requests"] == [
        {"updateDataSource": {"dataSource": ds, "fields": "spec"}}
    ]


def test_delete_data_source(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.delete_data_source("sid", "ds-abc")
    assert captured["requests"] == [{"deleteDataSource": {"dataSourceId": "ds-abc"}}]


def test_refresh_data_source(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.refresh_data_source("sid", "ds-refresh")
    assert captured["requests"] == [
        {
            "refreshDataSource": {
                "force": True,
                "references": {"references": [{"dataSourceId": "ds-refresh"}]},
            }
        }
    ]


def test_cancel_data_source_refresh(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(names_mod, "batch_update", _batch_update)
    names_mod.cancel_data_source_refresh("sid", "ds-cancel")
    assert captured["requests"] == [
        {
            "cancelDataSourceRefresh": {
                "isAll": False,
                "references": {"references": [{"dataSourceId": "ds-cancel"}]},
            }
        }
    ]
