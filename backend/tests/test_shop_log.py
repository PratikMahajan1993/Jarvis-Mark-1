from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.connectors.sheets import spreadsheet_id_from
from app.shop_excel import efficiency_from_payload
from app import shop_log


def test_spreadsheet_id_from_url_and_bare():
    url = "https://docs.google.com/spreadsheets/d/1AbC-DEF_ghi1234567890xyz/edit#gid=0"
    assert spreadsheet_id_from(url) == "1AbC-DEF_ghi1234567890xyz"
    assert spreadsheet_id_from("https://docs.google.com/spreadsheets/d/1AbC-DEF_ghi1234567890xyz/edit?usp=sharing") == (
        "1AbC-DEF_ghi1234567890xyz"
    )
    assert spreadsheet_id_from("1AbC-DEF_ghi1234567890xyz") == "1AbC-DEF_ghi1234567890xyz"
    assert spreadsheet_id_from("not a sheet") == ""
    assert spreadsheet_id_from("") == ""


def test_efficiency_from_payload_does_not_invent():
    missing_col = efficiency_from_payload(
        {"headers": ["Machine", "Notes"], "raw": [["Machine", "Notes"], ["CNC-1", "ok"]]}
    )
    assert missing_col["oee_percent"] is None
    assert missing_col["reason"] == "no efficiency column"

    blank = efficiency_from_payload(
        {
            "headers": ["Machine", "OEE"],
            "raw": [["Machine", "OEE"], ["CNC-1", None], ["Press-1", ""]],
        }
    )
    assert blank["oee_percent"] is None
    assert blank["reason"] == "no numeric efficiency values"
    assert blank["column"] == "OEE"


def test_parse_updates_cell_and_machine():
    assert shop_log.parse_updates("write 88 in B2") == [{"cell": "B2", "value": 88}]
    assert shop_log.parse_updates("set C3 to 91.5") == [{"cell": "C3", "value": 91.5}]
    payload = {
        "headers": ["Machine", "OEE"],
        "raw": [["Machine", "OEE"], ["CNC-1", 80], ["Press-1", 95]],
    }
    assert shop_log.parse_updates("set CNC-1 OEE to 92", payload) == [{"row": 2, "col": 2, "value": 92}]


def test_bind_url_stores_preferences(monkeypatch):
    store: dict = {"timezone": "Asia/Kolkata"}
    monkeypatch.setattr("app.shop_log.db.get_preferences", lambda: dict(store))

    def _update(patch: dict) -> dict:
        store.update(patch)
        return dict(store)

    monkeypatch.setattr("app.shop_log.db.update_preferences", _update)
    monkeypatch.setattr("app.shop_log.google_auth.connected", lambda: True)
    monkeypatch.setattr("app.shop_log.google_auth.has_sheets", lambda: True)
    monkeypatch.setattr("app.shop_log.sheets.get_title", lambda _sid: "Floor book")
    monkeypatch.setattr("app.shop_log.sheets.list_sheets", lambda _sid: ["Production", "Scrap"])
    result = shop_log.bind("https://docs.google.com/spreadsheets/d/1AbC-DEF_ghi1234567890xyz/edit")
    assert result["data"]["bound"] is True
    assert store["shop_spreadsheet_id"] == "1AbC-DEF_ghi1234567890xyz"
    assert store["shop_spreadsheet_title"] == "Floor book"
    assert store["shop_sheet_name"] == "Production"
    assert "Using Floor book" in result["speak"]


def test_efficiency_snapshot_unbound_does_not_invent(monkeypatch):
    shop_log.reset_cache()
    monkeypatch.setattr("app.shop_log.google_auth.connected", lambda: True)
    monkeypatch.setattr("app.shop_log.google_auth.has_sheets", lambda: True)
    monkeypatch.setattr(
        "app.shop_log.db.get_preferences",
        lambda: {"shop_spreadsheet_id": "", "shop_sheet_name": "Production"},
    )
    snap = shop_log.efficiency_snapshot(force=True)
    assert snap["oee_percent"] is None
    assert snap["reason"] == "no shop sheet bound"


def test_queue_write_is_shall_i_not_api(monkeypatch):
    called = {"update": 0}
    monkeypatch.setattr("app.shop_log.google_auth.connected", lambda: True)
    monkeypatch.setattr("app.shop_log.google_auth.has_sheets", lambda: True)
    monkeypatch.setattr(
        "app.shop_log.db.get_preferences",
        lambda: {
            "shop_spreadsheet_id": "sheet1234567890abcdefg",
            "shop_spreadsheet_title": "Shop",
            "shop_spreadsheet_url": "https://docs.google.com/spreadsheets/d/sheet1234567890abcdefg/edit",
            "shop_sheet_name": "Production",
        },
    )
    monkeypatch.setattr(
        "app.shop_log.db.add_pending",
        lambda action_id, session_id, kind, title, summary, payload: {
            "id": action_id,
            "kind": kind,
            "title": title,
            "summary": summary,
            "payload": payload,
        },
    )
    monkeypatch.setattr(
        "app.shop_log.sheets.read_sheet",
        lambda *_args, **_kwargs: {"headers": ["Machine", "OEE"], "raw": [["Machine", "OEE"]]},
    )

    def _should_not_write(*_args, **_kwargs):
        called["update"] += 1
        return {}

    monkeypatch.setattr("app.shop_log.sheets.update_cells", _should_not_write)
    result = shop_log.queue_write("default", message="write 88 in B2")
    assert result["data"]["queued"] is True
    assert result["pending"]["kind"] == "sheets_write"
    assert called["update"] == 0
    assert "Shall I" in result["speak"]


def test_apply_write_hits_sheets(monkeypatch):
    seen: dict = {}

    def _update(spreadsheet_id: str, sheet_name: str, updates: list) -> dict:
        seen["args"] = (spreadsheet_id, sheet_name, updates)
        return {"updated": ["B2"], "spreadsheet_id": spreadsheet_id}

    monkeypatch.setattr("app.shop_log.sheets.update_cells", _update)
    out = shop_log.apply_write(
        {"spreadsheet_id": "abc", "sheet_name": "Production", "updates": [{"cell": "B2", "value": 88}]}
    )
    assert seen["args"][0] == "abc"
    assert seen["args"][2] == [{"cell": "B2", "value": 88}]
    assert out["updated"] == ["B2"]


def test_glance_efficiency_critical_only_when_low(monkeypatch):
    monkeypatch.setattr(
        "app.shop_log.efficiency_snapshot",
        lambda force=False: {
            "oee_percent": 82.0,
            "bottlenecks": [{"label": "CNC-1", "oee_percent": 82.0}],
            "url": "https://docs.google.com/spreadsheets/d/x/edit",
        },
    )
    chip = shop_log.glance_efficiency_critical()
    assert chip is not None
    assert chip["kind"] == "efficiency"
    assert "82" in chip["title"]
    monkeypatch.setattr(
        "app.shop_log.efficiency_snapshot",
        lambda force=False: {"oee_percent": 96.0, "bottlenecks": [], "url": ""},
    )
    assert shop_log.glance_efficiency_critical() is None
    monkeypatch.setattr(
        "app.shop_log.efficiency_snapshot",
        lambda force=False: {"oee_percent": None, "bottlenecks": [], "reason": "no shop sheet bound"},
    )
    assert shop_log.glance_efficiency_critical() is None


def test_glance_nine_am_briefing_key(monkeypatch):
    from app import briefing

    tz = ZoneInfo("Asia/Kolkata")
    monkeypatch.setattr(briefing, "_now", lambda: datetime(2026, 9, 10, 9, 2, tzinfo=tz))
    monkeypatch.setattr(
        briefing,
        "gather_briefing_facts",
        lambda: {
            "slot": "Morning",
            "name": "Tony",
            "priority_mail": [],
            "next_event": None,
            "unread_total": 0,
            "shop_oee": None,
        },
    )
    monkeypatch.setattr("app.connectors.calendar.upcoming", lambda days=7: [])
    monkeypatch.setattr("app.watch.watch_payload", lambda _session="default": {})
    glance = briefing.build_glance()
    assert glance["key"] == "briefing:2026-09-10:0900"
    assert "Morning, Tony" in glance["speak"]
    assert glance["line"] == "Morning briefing"


def test_briefing_speak_omits_missing_oee():
    from app.briefing import fallback_briefing_speak

    speak = fallback_briefing_speak(
        {
            "slot": "Morning",
            "name": "Tony",
            "priority_mail": [],
            "next_event": None,
            "unread_total": 0,
            "shop_oee": None,
        }
    )
    assert "OEE" not in speak
    with_oee = fallback_briefing_speak(
        {
            "slot": "Morning",
            "name": "Tony",
            "priority_mail": [],
            "next_event": None,
            "unread_total": 0,
            "shop_oee": 87.4,
            "shop_bottlenecks": [{"label": "CNC-1"}],
        }
    )
    assert "87 percent" in with_oee
    assert "CNC-1" in with_oee


def test_has_sheets_status(monkeypatch):
    from app.connectors import google_auth

    monkeypatch.setattr(google_auth, "token_scopes", lambda: [google_auth.SPREADSHEETS])
    assert google_auth.has_sheets() is True
    monkeypatch.setattr(google_auth, "token_scopes", lambda: [google_auth.GMAIL_SEND])
    assert google_auth.has_sheets() is False
    monkeypatch.setattr(google_auth, "configured", lambda: True)
    monkeypatch.setattr(google_auth, "connected", lambda: True)
    monkeypatch.setattr(google_auth, "has_calendar", lambda: True)
    monkeypatch.setattr(google_auth, "has_calendar_list", lambda: False)
    monkeypatch.setattr(google_auth, "has_sheets", lambda: False)
    status = google_auth.status()
    assert "sheets" in status
    assert status["sheets"] is False


def test_google_error_maps_disabled_api():
    from app.connectors.sheets import google_error

    blob = (
        'HttpError 403 ... "Google Sheets API has not been used in project 927278009871 before or it is disabled. '
        'Enable it by visiting https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=927278009871 then retry." '
        "SERVICE_DISABLED"
    )
    info = google_error(RuntimeError(blob), "Google Sheets did not create the shop log.")
    assert "API is off" in info["speak"]
    assert "sheets.googleapis.com" in info["url"]
    assert "927278009871" in info["url"]


def test_ensure_speaks_disabled_api(monkeypatch):
    monkeypatch.setattr("app.shop_log.google_auth.connected", lambda: True)
    monkeypatch.setattr("app.shop_log.google_auth.has_sheets", lambda: True)
    monkeypatch.setattr(
        "app.shop_log.db.get_preferences",
        lambda: {"shop_spreadsheet_id": "", "shop_sheet_name": "Production"},
    )

    def _boom(_title=""):
        raise RuntimeError(
            "HttpError 403 SERVICE_DISABLED Google Sheets API has not been used. "
            "https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=927278009871"
        )

    monkeypatch.setattr("app.shop_log.sheets.create_shop_spreadsheet", _boom)
    result = shop_log.ensure()
    assert result["data"]["bound"] is False
    assert "API is off" in result["speak"]
    assert any(
        "sheets.googleapis.com" in str(widget.get("text") or "")
        for widget in result["scene"]["widgets"]
    )
