from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.connectors.sheets_toolkit import filters as filters_mod

_RANGE = {
    "sheetId": 1,
    "startRowIndex": 0,
    "endRowIndex": 10,
    "startColumnIndex": 0,
    "endColumnIndex": 5,
}


def test_set_basic_filter(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["spreadsheet_id"] = spreadsheet_id
        captured["requests"] = requests
        captured["account"] = account
        return {"replies": [{}]}

    monkeypatch.setattr(filters_mod, "batch_update", _batch_update)
    out = filters_mod.set_basic_filter(" sid ", 1, 0, 10, 0, 5, account="shop")
    assert out == {"replies": [{}]}
    assert captured["spreadsheet_id"] == "sid"
    assert captured["account"] == "shop"
    assert captured["requests"] == [
        {"setBasicFilter": {"filter": {"range": _RANGE}}},
    ]


def test_clear_basic_filter(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(filters_mod, "batch_update", _batch_update)
    filters_mod.clear_basic_filter("sid", 2, account="a")
    assert captured["requests"] == [{"clearBasicFilter": {"sheetId": 2}}]


def test_add_filter_view(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(filters_mod, "batch_update", _batch_update)
    filters_mod.add_filter_view("sid", 1, "Q1", 0, 10, 0, 5)
    assert captured["requests"] == [
        {
            "addFilterView": {
                "filter": {"title": "Q1", "range": _RANGE},
            },
        },
    ]


def test_update_filter_view(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(filters_mod, "batch_update", _batch_update)
    filters_mod.update_filter_view("sid", 7, "Renamed")
    assert captured["requests"] == [
        {
            "updateFilterView": {
                "filter": {"filterViewId": 7, "title": "Renamed"},
                "fields": "title",
            },
        },
    ]


def test_delete_filter_view(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(filters_mod, "batch_update", _batch_update)
    filters_mod.delete_filter_view("sid", 3)
    assert captured["requests"] == [{"deleteFilterView": {"filterId": 3}}]


def test_duplicate_filter_view(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(filters_mod, "batch_update", _batch_update)
    filters_mod.duplicate_filter_view("sid", 4)
    assert captured["requests"] == [{"duplicateFilterView": {"filterId": 4}}]


def test_add_slicer(monkeypatch):
    captured: dict = {}
    spec = {"dataRange": {"sheetId": 1}}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(filters_mod, "batch_update", _batch_update)
    filters_mod.add_slicer("sid", 1, spec)
    assert captured["requests"] == [
        {
            "addSlicer": {
                "slicer": {
                    "spec": spec,
                    "position": {
                        "overlayPosition": {
                            "anchorCell": {
                                "sheetId": 1,
                                "rowIndex": 0,
                                "columnIndex": 0,
                            },
                        },
                    },
                },
            },
        },
    ]


def test_update_slicer(monkeypatch):
    captured: dict = {}
    spec = {"title": "Region"}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(filters_mod, "batch_update", _batch_update)
    filters_mod.update_slicer("sid", 9, spec)
    assert captured["requests"] == [
        {
            "updateSlicerSpec": {
                "slicerId": 9,
                "spec": spec,
                "fields": "*",
            },
        },
    ]


def test_set_data_validation(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(filters_mod, "batch_update", _batch_update)
    filters_mod.set_data_validation(
        "sid", 1, 0, 10, 0, 5, "ONE_OF_LIST", ["A", "B"]
    )
    assert captured["requests"] == [
        {
            "setDataValidation": {
                "range": _RANGE,
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [
                            {"userEnteredValue": "A"},
                            {"userEnteredValue": "B"},
                        ],
                    },
                    "strict": True,
                    "showCustomUi": True,
                },
            },
        },
    ]


def test_add_conditional_format(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(filters_mod, "batch_update", _batch_update)
    filters_mod.add_conditional_format(
        "sid", 1, 0, 10, 0, 5, "TEXT_EQ", ["done"]
    )
    assert captured["requests"] == [
        {
            "addConditionalFormatRule": {
                "index": 0,
                "rule": {
                    "ranges": [_RANGE],
                    "booleanRule": {
                        "condition": {
                            "type": "TEXT_EQ",
                            "values": [{"userEnteredValue": "done"}],
                        },
                        "format": {
                            "backgroundColor": {"red": 1, "green": 0.9, "blue": 0.6},
                        },
                    },
                },
            },
        },
    ]


def test_update_conditional_format(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(filters_mod, "batch_update", _batch_update)
    filters_mod.update_conditional_format(
        "sid", 1, 2, 0, 10, 0, 5, "NUMBER_GREATER", ["0"]
    )
    assert captured["requests"] == [
        {
            "updateConditionalFormatRule": {
                "index": 2,
                "sheetId": 1,
                "rule": {
                    "ranges": [_RANGE],
                    "booleanRule": {
                        "condition": {
                            "type": "NUMBER_GREATER",
                            "values": [{"userEnteredValue": "0"}],
                        },
                        "format": {
                            "backgroundColor": {"red": 1, "green": 0.9, "blue": 0.6},
                        },
                    },
                },
            },
        },
    ]


def test_delete_conditional_format(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(filters_mod, "batch_update", _batch_update)
    filters_mod.delete_conditional_format("sid", 1, 0)
    assert captured["requests"] == [
        {"deleteConditionalFormatRule": {"sheetId": 1, "index": 0}},
    ]
