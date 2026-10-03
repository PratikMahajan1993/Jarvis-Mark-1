from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from app.connectors.sheets_toolkit.client import (
    SheetsToolkitError,
    batch_update,
    grid_range,
    require_spreadsheet_id,
)


def test_require_spreadsheet_id_rejects_blank():
    with pytest.raises(SheetsToolkitError):
        require_spreadsheet_id("  ")
    assert require_spreadsheet_id(" abc ") == "abc"


def test_grid_range_is_half_open():
    assert grid_range(3, 0, 2, 1, 4) == {
        "sheetId": 3,
        "startRowIndex": 0,
        "endRowIndex": 2,
        "startColumnIndex": 1,
        "endColumnIndex": 4,
    }
    with pytest.raises(SheetsToolkitError):
        grid_range(1, 2, 1, 0, 1)


def test_batch_update_sends_requests(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {"spreadsheetId": "sid", "replies": [{"addSheet": {}}]}

    class _Spreadsheets:
        def batchUpdate(self, spreadsheetId, body, fields):
            captured["spreadsheetId"] = spreadsheetId
            captured["body"] = body
            captured["fields"] = fields
            return _Call()

    class _Service:
        def spreadsheets(self):
            return _Spreadsheets()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.client.sheets_service",
        lambda account=None: _Service(),
    )
    out = batch_update("sid", [{"addSheet": {"properties": {"title": "Reports"}}}], account="shop")
    assert out["replies"][0]["addSheet"] == {}
    assert captured["body"]["requests"][0]["addSheet"]["properties"]["title"] == "Reports"
    with pytest.raises(SheetsToolkitError):
        batch_update("sid", [])
