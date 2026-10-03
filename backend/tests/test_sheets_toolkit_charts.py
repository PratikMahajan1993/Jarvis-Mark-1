from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.connectors.sheets_toolkit import charts as charts_mod


def test_add_chart(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["spreadsheet_id"] = spreadsheet_id
        captured["requests"] = requests
        captured["account"] = account
        return {"replies": [{}]}

    monkeypatch.setattr(charts_mod, "batch_update", _batch_update)
    spec = {"basicChart": {"chartType": "BAR"}}
    out = charts_mod.add_chart("sid", 2, spec, account="shop")
    assert out == {"replies": [{}]}
    assert captured["spreadsheet_id"] == "sid"
    assert captured["account"] == "shop"
    assert list(captured["requests"][0].keys()) == ["addChart"]
    assert captured["requests"] == [
        {
            "addChart": {
                "chart": {
                    "spec": spec,
                    "position": {
                        "overlayPosition": {
                            "anchorCell": {
                                "sheetId": 2,
                                "rowIndex": 0,
                                "columnIndex": 0,
                            }
                        }
                    },
                }
            }
        }
    ]


def test_update_chart(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(charts_mod, "batch_update", _batch_update)
    spec = {"title": "Updated"}
    charts_mod.update_chart("sid", 7, spec, account="a")
    assert list(captured["requests"][0].keys()) == ["updateChartSpec"]
    assert captured["requests"] == [
        {"updateChartSpec": {"chartId": 7, "spec": spec}}
    ]


def test_move_embedded_object(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(charts_mod, "batch_update", _batch_update)
    charts_mod.move_embedded_object("sid", 3, 1, 4, 5, account="x")
    assert list(captured["requests"][0].keys()) == ["updateEmbeddedObjectPosition"]
    assert captured["requests"] == [
        {
            "updateEmbeddedObjectPosition": {
                "objectId": 3,
                "newPosition": {
                    "overlayPosition": {
                        "anchorCell": {
                            "sheetId": 1,
                            "rowIndex": 4,
                            "columnIndex": 5,
                        }
                    }
                },
                "fields": "overlayPosition.anchorCell",
            }
        }
    ]


def test_delete_embedded_object(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(charts_mod, "batch_update", _batch_update)
    charts_mod.delete_embedded_object("sid", 9, account="z")
    assert list(captured["requests"][0].keys()) == ["deleteEmbeddedObject"]
    assert captured["requests"] == [{"deleteEmbeddedObject": {"objectId": 9}}]


def test_set_embedded_object_border(monkeypatch):
    captured: dict = {}

    def _batch_update(spreadsheet_id, requests, account=None):
        captured["requests"] = requests
        return {"replies": [{}]}

    monkeypatch.setattr(charts_mod, "batch_update", _batch_update)
    charts_mod.set_embedded_object_border("sid", 11, 0.1, 0.5, 1.0, account="b")
    assert list(captured["requests"][0].keys()) == ["updateEmbeddedObjectBorder"]
    assert captured["requests"] == [
        {
            "updateEmbeddedObjectBorder": {
                "objectId": 11,
                "border": {
                    "colorStyle": {
                        "rgbColor": {"red": 0.1, "green": 0.5, "blue": 1.0}
                    }
                },
            }
        }
    ]
