from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.connectors import email as email_conn
from app.intent import classify
from app.snapshot import calendar_ready, skips_model, uses_snapshot, wants_fresh


def test_fresh_phrases():
    assert wants_fresh("anything new")
    assert wants_fresh("what's new")
    assert wants_fresh("any new mail")
    assert wants_fresh("check again")
    assert not wants_fresh("check my mail")
    assert not wants_fresh("open Neha's last email")
    assert classify("anything new").kind == "mail_search"
    assert classify("what's new").kind == "mail_search"
    assert classify("check my mail").kind == "mail_search"
    assert classify("anything new on the calendar").kind == "calendar_list"
    assert wants_fresh("anything new on the calendar")


def test_snapshot_kinds_skip_brain():
    assert uses_snapshot("mail_search")
    assert uses_snapshot("mail_read")
    assert uses_snapshot("briefing")
    assert uses_snapshot("calendar_list")
    assert not uses_snapshot("mail_draft")
    assert not uses_snapshot("research")
    assert not uses_snapshot("chat")
    assert skips_model("calendar_list")
    assert skips_model("calendar_create")
    assert skips_model("shop_read")
    assert skips_model("shop_write")
    assert not skips_model("mail_draft")
    assert not uses_snapshot("calendar_create")
    assert not uses_snapshot("shop_read")


def test_local_mail_search_does_not_need_gmail():
    db.init_db()
    db.upsert_email(
        {
            "id": "snap-local-neha",
            "sender": "Neha <neha@example.com>",
            "to_addr": "tony@example.com",
            "subject": "Advance payment",
            "body": "Please send the proforma.",
            "unread": 1,
            "folder": "INBOX",
        }
    )
    called = {"gmail": 0}

    def boom(**_kwargs):
        called["gmail"] += 1
        raise AssertionError("Gmail should not run for a local hit")

    import app.connectors.gmail as gmail_conn

    original = gmail_conn.list_messages
    gmail_conn.list_messages = boom  # type: ignore[method-assign]
    try:
        rows = email_conn.search_emails(query="from:Neha", limit=5)
        assert rows, rows
        assert any("Neha" in (row.get("sender") or "") for row in rows)
        assert called["gmail"] == 0
        found = email_conn.get_email("snap-local-neha")
        assert found and "proforma" in (found.get("body") or "")
    finally:
        gmail_conn.list_messages = original  # type: ignore[method-assign]


def test_local_calendar_list_does_not_need_google():
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    from app.connectors import calendar as calendar_conn
    from app.connectors import google_auth

    db.init_db()
    tz = ZoneInfo("Asia/Kolkata")
    start = datetime.now(tz).replace(hour=16, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=1)
    db.upsert_calendar_event(
        {
            "id": "snap-cal-local",
            "title": "Northline client review",
            "start_at": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "end_at": end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "location": "Conference B",
            "notes": "",
        }
    )
    called = {"google": 0}

    def boom(*_args, **_kwargs):
        called["google"] += 1
        raise AssertionError("Google should not run for a local list")

    original_list = calendar_conn._google_list
    original_live = calendar_conn.live
    original_connected = google_auth.connected
    calendar_conn._google_list = boom  # type: ignore[method-assign]
    calendar_conn.live = lambda: False  # type: ignore[method-assign]
    google_auth.connected = lambda: False  # type: ignore[method-assign]
    try:
        assert calendar_ready()
        rows = calendar_conn.list_events(days=2)
        assert called["google"] == 0
        assert any(row.get("id") == "snap-cal-local" for row in rows), rows
        today = calendar_conn.list_events(days=2, span="today")
        assert any(row.get("id") == "snap-cal-local" for row in today)
        tomorrow = calendar_conn.list_events(days=2, span="tomorrow")
        assert all(row.get("id") != "snap-cal-local" for row in tomorrow)
    finally:
        calendar_conn._google_list = original_list  # type: ignore[method-assign]
        calendar_conn.live = original_live  # type: ignore[method-assign]
        google_auth.connected = original_connected  # type: ignore[method-assign]


if __name__ == "__main__":
    tests = [
        test_fresh_phrases,
        test_snapshot_kinds_skip_brain,
        test_local_mail_search_does_not_need_gmail,
        test_local_calendar_list_does_not_need_google,
    ]
    for test in tests:
        test()
        print("ok", test.__name__)
    print(f"passed {len(tests)}")
