from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.connectors import email as email_conn
from app.intent import classify
from app.snapshot import uses_snapshot, wants_fresh


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


def test_snapshot_kinds_skip_brain():
    assert uses_snapshot("mail_search")
    assert uses_snapshot("mail_read")
    assert uses_snapshot("briefing")
    assert uses_snapshot("calendar_list")
    assert not uses_snapshot("mail_draft")
    assert not uses_snapshot("research")
    assert not uses_snapshot("chat")


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


if __name__ == "__main__":
    tests = [test_fresh_phrases, test_snapshot_kinds_skip_brain, test_local_mail_search_does_not_need_gmail]
    for test in tests:
        test()
        print("ok", test.__name__)
    print(f"passed {len(tests)}")
