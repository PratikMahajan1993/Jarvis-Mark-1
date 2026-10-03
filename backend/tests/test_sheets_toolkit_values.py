from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.connectors.sheets_toolkit import values as sheets_values


def test_read_range(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {"range": "Sheet1!A1", "values": [["x"]]}

    class _Values:
        def get(self, spreadsheetId, range, valueRenderOption):
            captured["method"] = "get"
            captured["spreadsheetId"] = spreadsheetId
            captured["range"] = range
            captured["valueRenderOption"] = valueRenderOption
            return _Call()

    class _Spreadsheets:
        def values(self):
            return _Values()

    class _Service:
        def spreadsheets(self):
            return _Spreadsheets()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.values.sheets_service",
        lambda account=None: _Service(),
    )
    out = sheets_values.read_range("sid", "Sheet1!A1", account="shop")
    assert out["values"] == [["x"]]
    assert captured == {
        "method": "get",
        "spreadsheetId": "sid",
        "range": "Sheet1!A1",
        "valueRenderOption": "FORMATTED_VALUE",
    }


def test_read_ranges(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {"valueRanges": []}

    class _Values:
        def batchGet(self, spreadsheetId, ranges, valueRenderOption):
            captured["method"] = "batchGet"
            captured["spreadsheetId"] = spreadsheetId
            captured["ranges"] = ranges
            captured["valueRenderOption"] = valueRenderOption
            return _Call()

    class _Spreadsheets:
        def values(self):
            return _Values()

    class _Service:
        def spreadsheets(self):
            return _Spreadsheets()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.values.sheets_service",
        lambda account=None: _Service(),
    )
    sheets_values.read_ranges("sid", ["A1", "B2"], value_render="UNFORMATTED_VALUE")
    assert captured["ranges"] == ["A1", "B2"]
    assert captured["valueRenderOption"] == "UNFORMATTED_VALUE"


def test_write_range(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {"updatedRange": "A1:B1", "updatedRows": 1}

    class _Values:
        def update(self, spreadsheetId, range, valueInputOption, body):
            captured["method"] = "update"
            captured["spreadsheetId"] = spreadsheetId
            captured["range"] = range
            captured["valueInputOption"] = valueInputOption
            captured["body"] = body
            return _Call()

    class _Spreadsheets:
        def values(self):
            return _Values()

    class _Service:
        def spreadsheets(self):
            return _Spreadsheets()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.values.sheets_service",
        lambda account=None: _Service(),
    )
    sheets_values.write_range("sid", "A1", [[1, 2]], value_input="RAW")
    assert captured["body"] == {"values": [[1, 2]]}
    assert captured["valueInputOption"] == "RAW"


def test_write_ranges(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {"totalUpdatedCells": 2}

    class _Values:
        def batchUpdate(self, spreadsheetId, body):
            captured["method"] = "batchUpdate"
            captured["spreadsheetId"] = spreadsheetId
            captured["body"] = body
            return _Call()

    class _Spreadsheets:
        def values(self):
            return _Values()

    class _Service:
        def spreadsheets(self):
            return _Spreadsheets()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.values.sheets_service",
        lambda account=None: _Service(),
    )
    data = [{"range": "A1", "values": [[1]]}, {"range": "B1", "values": [[2]]}]
    sheets_values.write_ranges("sid", data)
    assert captured["body"] == {"valueInputOption": "USER_ENTERED", "data": data}


def test_append_rows(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {"updates": {"updatedRows": 1}}

    class _Values:
        def append(
            self,
            spreadsheetId,
            range,
            valueInputOption,
            insertDataOption,
            body,
        ):
            captured["method"] = "append"
            captured["spreadsheetId"] = spreadsheetId
            captured["range"] = range
            captured["valueInputOption"] = valueInputOption
            captured["insertDataOption"] = insertDataOption
            captured["body"] = body
            return _Call()

    class _Spreadsheets:
        def values(self):
            return _Values()

    class _Service:
        def spreadsheets(self):
            return _Spreadsheets()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.values.sheets_service",
        lambda account=None: _Service(),
    )
    sheets_values.append_rows("sid", "Sheet1!A:A", [["new"]])
    assert captured["insertDataOption"] == "INSERT_ROWS"
    assert captured["body"] == {"values": [["new"]]}


def test_clear_range(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {"clearedRange": "A1:B2"}

    class _Values:
        def clear(self, spreadsheetId, range, body):
            captured["method"] = "clear"
            captured["spreadsheetId"] = spreadsheetId
            captured["range"] = range
            captured["body"] = body
            return _Call()

    class _Spreadsheets:
        def values(self):
            return _Values()

    class _Service:
        def spreadsheets(self):
            return _Spreadsheets()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.values.sheets_service",
        lambda account=None: _Service(),
    )
    sheets_values.clear_range("sid", "A1:B2")
    assert captured["body"] == {}
    assert captured["range"] == "A1:B2"


def test_clear_ranges(monkeypatch):
    captured: dict = {}

    class _Call:
        def execute(self):
            return {"clearedRanges": ["A1", "B2"]}

    class _Values:
        def batchClear(self, spreadsheetId, body):
            captured["method"] = "batchClear"
            captured["spreadsheetId"] = spreadsheetId
            captured["body"] = body
            return _Call()

    class _Spreadsheets:
        def values(self):
            return _Values()

    class _Service:
        def spreadsheets(self):
            return _Spreadsheets()

    monkeypatch.setattr(
        "app.connectors.sheets_toolkit.values.sheets_service",
        lambda account=None: _Service(),
    )
    sheets_values.clear_ranges("sid", ["A1", "B2"])
    assert captured["body"] == {"ranges": ["A1", "B2"]}
