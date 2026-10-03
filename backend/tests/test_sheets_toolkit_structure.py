from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from app.connectors.sheets_toolkit.client import SheetsToolkitError
from app.connectors.sheets_toolkit import structure as structure_mod


def _patch_batch(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["spreadsheet_id"] = spreadsheet_id
        captured["requests"] = requests
        captured["account"] = account
        return {"spreadsheetId": spreadsheet_id, "replies": [{}]}

    monkeypatch.setattr(structure_mod, "batch_update", _batch_update)
    return captured


def test_insert_dimension(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.insert_dimension("sid", 1, "ROWS", 2, 5, account="shop")
    req = captured["requests"][0]
    assert set(req) == {"insertDimension"}
    assert req["insertDimension"]["inheritFromBefore"] is False
    with pytest.raises(SheetsToolkitError):
        structure_mod.insert_dimension("sid", 1, "ROWS", 5, 2)


def test_delete_dimension(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.delete_dimension("sid", 0, "COLUMNS", 1, 3)
    req = captured["requests"][0]
    assert set(req) == {"deleteDimension"}
    assert req["deleteDimension"]["range"]["dimension"] == "COLUMNS"


def test_append_dimension(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.append_dimension("sid", 2, "ROWS", 4)
    req = captured["requests"][0]
    assert set(req) == {"appendDimension"}
    assert req["appendDimension"]["length"] == 4
    with pytest.raises(SheetsToolkitError):
        structure_mod.append_dimension("sid", 2, "ROWS", 0)


def test_move_dimension(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.move_dimension("sid", 1, "ROWS", 0, 2, 5)
    req = captured["requests"][0]
    assert set(req) == {"moveDimension"}
    assert req["moveDimension"]["destinationIndex"] == 5


def test_insert_range(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.insert_range("sid", 3, 0, 2, 1, 4, "COLUMNS")
    req = captured["requests"][0]
    assert set(req) == {"insertRange"}
    assert req["insertRange"]["shiftDimension"] == "COLUMNS"


def test_delete_range(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.delete_range("sid", 3, 0, 2, 1, 4, "ROWS")
    req = captured["requests"][0]
    assert set(req) == {"deleteRange"}
    assert req["deleteRange"]["shiftDimension"] == "ROWS"


def test_copy_range(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.copy_range("sid", 1, 0, 1, 0, 2, 9, 3, 4)
    req = captured["requests"][0]
    assert set(req) == {"copyPaste"}
    assert req["copyPaste"]["pasteType"] == "PASTE_NORMAL"


def test_cut_range(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.cut_range("sid", 1, 0, 1, 0, 2, 9, 3, 4)
    req = captured["requests"][0]
    assert set(req) == {"cutPaste"}
    assert req["cutPaste"]["destination"]["sheetId"] == 9


def test_paste_text(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.paste_text("sid", 2, 1, 3, "a,b\nc,d", delimiter="|")
    req = captured["requests"][0]
    assert set(req) == {"pasteData"}
    assert req["pasteData"]["delimiter"] == "|"


def test_sort_range(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.sort_range("sid", 0, 1, 10, 0, 5, 2, ascending=False)
    req = captured["requests"][0]
    assert set(req) == {"sortRange"}
    assert req["sortRange"]["sortSpecs"][0]["sortOrder"] == "DESCENDING"


def test_find_replace(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.find_replace("sid", "old", "new", sheet_id=7, match_case=True)
    req = captured["requests"][0]
    assert set(req) == {"findReplace"}
    assert req["findReplace"]["sheetId"] == 7
    assert "allSheets" not in req["findReplace"]


def test_text_to_columns(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.text_to_columns("sid", 1, 0, 5, 0, 1, delimiter=";")
    req = captured["requests"][0]
    assert set(req) == {"textToColumns"}
    assert req["textToColumns"]["delimiterType"] == "CUSTOM"


def test_trim_whitespace(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.trim_whitespace("sid", 1, 0, 3, 0, 2)
    req = captured["requests"][0]
    assert set(req) == {"trimWhitespace"}
    assert req["trimWhitespace"]["range"]["sheetId"] == 1


def test_delete_duplicates(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.delete_duplicates("sid", 1, 0, 10, 0, 4)
    req = captured["requests"][0]
    assert set(req) == {"deleteDuplicates"}
    assert req["deleteDuplicates"]["comparisonColumns"] == []


def test_randomize_range(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.randomize_range("sid", 1, 2, 8, 0, 3)
    req = captured["requests"][0]
    assert set(req) == {"randomizeRange"}
    assert req["randomizeRange"]["range"]["startRowIndex"] == 2


def test_autofill(monkeypatch):
    captured = _patch_batch(monkeypatch)
    structure_mod.autofill("sid", 1, 0, 1, 0, 2, "COLUMNS", 3)
    req = captured["requests"][0]
    assert set(req) == {"autoFill"}
    assert req["autoFill"]["sourceAndDestination"]["fillLength"] == 3
    with pytest.raises(SheetsToolkitError):
        structure_mod.autofill("sid", 1, 0, 1, 0, 2, "BAD", 1)
