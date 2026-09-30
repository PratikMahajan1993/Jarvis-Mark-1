from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.connectors.sheets import SheetNotFoundError
from app import sheet_listen


def _init():
    db.init_db()


def test_migration_seeds_two_accounts():
    _init()
    accounts = sheet_listen.list_google_accounts()
    labels = {a["label"] for a in accounts}
    assert labels == {"shop", "staff"}
    filenames = {a["label"]: a["token_filename"] for a in accounts}
    assert filenames["shop"] == "google_token.json"
    assert filenames["staff"] == "google_token_staff.json"


def test_token_paths_are_distinct():
    from app.connectors import google_auth

    assert google_auth.token_path("shop").name == "google_token.json"
    assert google_auth.token_path("staff").name == "google_token_staff.json"
    assert google_auth.token_path("shop") != google_auth.token_path("staff")


def test_create_listened_sheet_refuses_duplicate_link_tab():
    _init()
    fields = {
        "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1AbC-DEF_ghi1234567890xyz/edit",
        "tab_name": "Production",
        "display_name": "Floor A",
        "account": "shop",
        "column_map": {
            "date": "Date",
            "machine": "Machine",
            "job": "Job",
            "qty": "Qty",
            "downtime": "Downtime",
        },
    }
    first = sheet_listen.create_listened_sheet(fields)
    assert first["ok"] is True
    try:
        sheet_listen.create_listened_sheet(fields)
        raise AssertionError("expected duplicate refuse")
    except sheet_listen.ListenError as exc:
        assert "Already listening" in str(exc)


def test_empty_qty_is_missing_not_zero():
    mapped = sheet_listen.mapped_row(
        ["Date", "Machine", "Job", "Qty", "Downtime"],
        ["2026-09-30", "CNC-1", "J1", "", ""],
        {"date": "Date", "machine": "Machine", "job": "Job", "qty": "Qty", "downtime": "Downtime"},
    )
    assert mapped["qty"] is None
    assert "qty" in mapped["missing"]
    assert mapped["downtime"] is None
    assert "downtime" in mapped["missing"]


def test_today_requires_date_column_map():
    headers = ["Date", "Machine", "Qty"]
    rows = [["2026-09-30", "CNC-1", 12], ["2026-09-29", "Press-1", 4]]
    with_date = sheet_listen.today_rows(
        headers,
        rows,
        {"date": "Date", "machine": "Machine", "qty": "Qty"},
        today="2026-09-30",
    )
    assert len(with_date) == 1
    assert with_date[0]["machine"] == "CNC-1"
    assert with_date[0]["qty"] == 12

    no_date = sheet_listen.today_rows(
        headers,
        rows,
        {"machine": "Machine", "qty": "Qty"},
        today="2026-09-30",
    )
    assert no_date == []


def test_conflicts_state_both_values_no_winner():
    conflicts = sheet_listen.detect_conflicts(
        [
            {
                "id": "a",
                "display_name": "Floor A",
                "today": [{"machine": "CNC-1", "job": "J1", "qty": 10, "downtime": None}],
            },
            {
                "id": "b",
                "display_name": "Floor B",
                "today": [{"machine": "CNC-1", "job": "J1", "qty": 12, "downtime": None}],
            },
        ]
    )
    assert len(conflicts) == 1
    assert conflicts[0]["field"] == "qty"
    values = {item["display_name"]: item["value"] for item in conflicts[0]["values"]}
    assert values == {"Floor A": 10, "Floor B": 12}


def test_refresh_keeps_snapshot_on_auth_failure(monkeypatch):
    _init()
    created = sheet_listen.create_listened_sheet(
        {
            "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1KeepSnapShotSheetIdXXXX/edit",
            "tab_name": "Production",
            "display_name": "Keep me",
            "account": "staff",
            "column_map": {"date": "Date", "machine": "Machine", "qty": "Qty"},
        }
    )
    sheet_id = created["id"]
    sheet_listen._store_snapshot(
        sheet_id,
        ["Date", "Machine", "Qty"],
        [["2026-09-30", "CNC-1", 7]],
        "2026-09-30T01:00:00+00:00",
    )
    sheet_listen._set_sheet_ok(sheet_id, "2026-09-30T01:00:00+00:00")

    monkeypatch.setattr("app.sheet_listen.google_auth.connected", lambda *a, **k: False)
    result = sheet_listen.refresh_listened_sheet(sheet_id)
    assert result["ok"] is False
    assert result["stale"] is True
    assert result["has_snapshot"] is True
    snap = sheet_listen._load_snapshot(sheet_id)
    assert snap is not None
    assert snap["rows"][0][2] == 7


def test_refresh_named_tab_missing_keeps_copy(monkeypatch):
    _init()
    created = sheet_listen.create_listened_sheet(
        {
            "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1MissingTabSheetIdYYYYY/edit",
            "tab_name": "Production",
            "display_name": "Missing tab",
            "account": "shop",
            "column_map": {"date": "Date", "machine": "Machine"},
        }
    )
    sheet_id = created["id"]
    sheet_listen._store_snapshot(
        sheet_id,
        ["Date", "Machine"],
        [["2026-09-30", "CNC-1"]],
        "2026-09-30T02:00:00+00:00",
    )

    monkeypatch.setattr("app.sheet_listen.google_auth.connected", lambda *a, **k: True)

    def _boom(*_a, **_k):
        raise SheetNotFoundError("Sheet 'Production' not found. Available: Scrap")

    monkeypatch.setattr("app.sheet_listen.sheets.read_sheet", _boom)
    result = sheet_listen.refresh_listened_sheet(sheet_id)
    assert result["stale"] is True
    assert sheet_listen._load_snapshot(sheet_id) is not None


def test_refresh_stores_full_copy(monkeypatch):
    _init()
    created = sheet_listen.create_listened_sheet(
        {
            "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1FreshCopySheetIdZZZZZZ/edit",
            "tab_name": "Production",
            "display_name": "Fresh",
            "account": "shop",
            "column_map": {
                "date": "Date",
                "machine": "Machine",
                "job": "Job",
                "qty": "Qty",
                "downtime": "Downtime",
            },
        }
    )
    sheet_id = created["id"]
    monkeypatch.setattr("app.sheet_listen.google_auth.connected", lambda *a, **k: True)
    monkeypatch.setattr(
        "app.sheet_listen.sheets.read_sheet",
        lambda *_a, **_k: {
            "headers": ["Date", "Machine", "Job", "Qty", "Downtime"],
            "raw": [
                ["Date", "Machine", "Job", "Qty", "Downtime"],
                ["2026-09-30", "CNC-1", "J1", 5, None],
                ["2026-09-29", "Press-1", "J0", "", 30],
            ],
            "rows": [],
        },
    )
    result = sheet_listen.refresh_listened_sheet(sheet_id)
    assert result["ok"] is True
    snap = sheet_listen._load_snapshot(sheet_id)
    assert snap is not None
    assert len(snap["rows"]) == 2
    assert snap["rows"][0][3] == 5
    assert snap["rows"][0][4] is None
    assert snap["rows"][1][3] is None


def test_retire_does_not_hard_delete():
    _init()
    created = sheet_listen.create_listened_sheet(
        {
            "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1RetireSheetIdAAAAAAAAA/edit",
            "tab_name": "Prod",
            "display_name": "Retire me",
            "account": "shop",
            "column_map": {"date": "Date"},
        }
    )
    sheet_id = created["id"]
    sheet_listen.retire_listened_sheet(sheet_id)
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM listened_sheets WHERE id = ?", (sheet_id,)).fetchone()
    assert row is not None
    assert row["effective_to"]
    assert row["status"] == "superseded"
    active = sheet_listen.list_listened_sheets(include_retired=False)
    assert all(item["id"] != sheet_id for item in active)


def test_today_state_line_and_conflicts(monkeypatch):
    _init()
    a = sheet_listen.create_listened_sheet(
        {
            "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1StateSheetAAAAAAAAAAAA/edit",
            "tab_name": "A",
            "display_name": "Log A",
            "account": "shop",
            "column_map": {"date": "Date", "machine": "Machine", "job": "Job", "qty": "Qty"},
        }
    )
    b = sheet_listen.create_listened_sheet(
        {
            "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1StateSheetBBBBBBBBBBBB/edit",
            "tab_name": "B",
            "display_name": "Log B",
            "account": "staff",
            "column_map": {"date": "Date", "machine": "Machine", "job": "Job", "qty": "Qty"},
        }
    )
    monkeypatch.setattr("app.sheet_listen._today_local", lambda: "2026-09-30")
    sheet_listen._store_snapshot(
        a["id"],
        ["Date", "Machine", "Job", "Qty"],
        [["2026-09-30", "STATE-CNC", "JOB-X", 10]],
        db.utc_now(),
    )
    sheet_listen._store_snapshot(
        b["id"],
        ["Date", "Machine", "Job", "Qty"],
        [["2026-09-30", "STATE-CNC", "JOB-X", 11]],
        db.utc_now(),
    )
    state = sheet_listen.today_state()
    assert state["today"] == "2026-09-30"
    our = [s for s in state["sheets"] if s["id"] in {a["id"], b["id"]}]
    assert any(s["line"].startswith("machines:") for s in our)
    conflict = next(
        c
        for c in state["conflicts"]
        if c.get("machine") == "STATE-CNC" and c.get("job") == "JOB-X"
    )
    values = {item["value"] for item in conflict["values"]}
    assert values == {10, 11}
