from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from app.connectors.sheets_toolkit.client import SheetsToolkitError
from app.connectors.sheets_toolkit import format as format_mod


def test_format_cells(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["spreadsheet_id"] = spreadsheet_id
        captured["requests"] = requests
        captured["account"] = account
        return {"replies": [{}]}

    monkeypatch.setattr(format_mod, "batch_update", _batch_update)
    cell_format = {"backgroundColor": {"red": 1, "green": 1, "blue": 0}}
    out = format_mod.format_cells(
        " sid ",
        2,
        0,
        3,
        1,
        5,
        cell_format,
        "userEnteredFormat.backgroundColor",
        account="shop",
    )
    assert out["replies"] == [{}]
    assert captured["spreadsheet_id"] == "sid"
    assert captured["account"] == "shop"
    assert captured["requests"] == [
        {
            "repeatCell": {
                "range": {
                    "sheetId": 2,
                    "startRowIndex": 0,
                    "endRowIndex": 3,
                    "startColumnIndex": 1,
                    "endColumnIndex": 5,
                },
                "cell": {"userEnteredFormat": cell_format},
                "fields": "userEnteredFormat.backgroundColor",
            }
        }
    ]
    with pytest.raises(SheetsToolkitError):
        format_mod.format_cells("sid", 0, 0, 1, 0, 1, {}, "userEnteredFormat.x")


def test_set_borders(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(format_mod, "batch_update", _batch_update)
    format_mod.set_borders("sid", 1, 0, 2, 0, 4, "SOLID", account="a")
    border = {"style": "SOLID"}
    assert captured["requests"] == [
        {
            "updateBorders": {
                "range": {
                    "sheetId": 1,
                    "startRowIndex": 0,
                    "endRowIndex": 2,
                    "startColumnIndex": 0,
                    "endColumnIndex": 4,
                },
                "top": border,
                "bottom": border,
                "left": border,
                "right": border,
            }
        }
    ]
    with pytest.raises(SheetsToolkitError):
        format_mod.set_borders("sid", 1, 0, 2, 0, 4, "WAVY")


def test_merge_cells(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(format_mod, "batch_update", _batch_update)
    format_mod.merge_cells("sid", 0, 1, 3, 2, 4, merge_type="MERGE_ROWS")
    assert captured["requests"] == [
        {
            "mergeCells": {
                "range": {
                    "sheetId": 0,
                    "startRowIndex": 1,
                    "endRowIndex": 3,
                    "startColumnIndex": 2,
                    "endColumnIndex": 4,
                },
                "mergeType": "MERGE_ROWS",
            }
        }
    ]
    with pytest.raises(SheetsToolkitError):
        format_mod.merge_cells("sid", 0, 0, 1, 0, 1, merge_type="MERGE_EVERYTHING")


def test_unmerge_cells(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(format_mod, "batch_update", _batch_update)
    format_mod.unmerge_cells("sid", 5, 0, 1, 0, 2)
    assert captured["requests"] == [
        {
            "unmergeCells": {
                "range": {
                    "sheetId": 5,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 2,
                }
            }
        }
    ]


def test_set_dimension_size(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(format_mod, "batch_update", _batch_update)
    format_mod.set_dimension_size("sid", 3, "ROWS", 2, 5, 120)
    assert captured["requests"] == [
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": 3,
                    "dimension": "ROWS",
                    "startIndex": 2,
                    "endIndex": 5,
                },
                "properties": {"pixelSize": 120},
                "fields": "pixelSize",
            }
        }
    ]
    with pytest.raises(SheetsToolkitError):
        format_mod.set_dimension_size("sid", 3, "ROWS", 2, 5, 0)


def test_auto_resize(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(format_mod, "batch_update", _batch_update)
    format_mod.auto_resize("sid", 1, "COLUMNS", 0, 3)
    assert captured["requests"] == [
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": 1,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 3,
                }
            }
        }
    ]


def test_add_banding(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(format_mod, "batch_update", _batch_update)
    format_mod.add_banding("sid", 2, 0, 10, 0, 6)
    assert captured["requests"] == [
        {
            "addBanding": {
                "bandedRange": {
                    "range": {
                        "sheetId": 2,
                        "startRowIndex": 0,
                        "endRowIndex": 10,
                        "startColumnIndex": 0,
                        "endColumnIndex": 6,
                    }
                }
            }
        }
    ]


def test_update_banding(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(format_mod, "batch_update", _batch_update)
    banded_range = {"firstBandColor": {"red": 0.9, "green": 0.9, "blue": 0.9}}
    format_mod.update_banding("sid", 7, banded_range, "firstBandColor")
    assert captured["requests"] == [
        {
            "updateBanding": {
                "bandedRange": {**banded_range, "bandedRangeId": 7},
                "fields": "firstBandColor",
            }
        }
    ]
    with pytest.raises(SheetsToolkitError):
        format_mod.update_banding("sid", 7, {}, "firstBandColor")


def test_delete_banding(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(format_mod, "batch_update", _batch_update)
    format_mod.delete_banding("sid", 4)
    assert captured["requests"] == [{"deleteBanding": {"bandedRangeId": 4}}]


def test_add_dimension_group(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(format_mod, "batch_update", _batch_update)
    format_mod.add_dimension_group("sid", 0, "ROWS", 1, 4)
    assert captured["requests"] == [
        {
            "addDimensionGroup": {
                "range": {
                    "sheetId": 0,
                    "dimension": "ROWS",
                    "startIndex": 1,
                    "endIndex": 4,
                }
            }
        }
    ]


def test_update_dimension_group(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(format_mod, "batch_update", _batch_update)
    format_mod.update_dimension_group("sid", 2, "COLUMNS", 0, 2, True)
    assert captured["requests"] == [
        {
            "updateDimensionGroup": {
                "dimensionGroup": {
                    "range": {
                        "sheetId": 2,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": 2,
                    },
                    "collapsed": True,
                    "depth": 1,
                },
                "fields": "collapsed",
            }
        }
    ]
    with pytest.raises(SheetsToolkitError):
        format_mod.update_dimension_group("sid", 2, "COLUMNS", 0, 2, "yes")


def test_delete_dimension_group(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(format_mod, "batch_update", _batch_update)
    format_mod.delete_dimension_group("sid", 1, "ROWS", 3, 8)
    assert captured["requests"] == [
        {
            "deleteDimensionGroup": {
                "range": {
                    "sheetId": 1,
                    "dimension": "ROWS",
                    "startIndex": 3,
                    "endIndex": 8,
                }
            }
        }
    ]
