from __future__ import annotations

from app import db
from app.connectors.email import _merge_gmail_fields
from app.connectors.mail_filter import should_keep_mail
from app.mail_sync import bulk_complete, get_state
from app.memory.ingest import reindex_all_mail_in_db


def setup_module(_module=None):
    db.init_db()


def test_mail_sync_state_roundtrip():
    db.set_mail_sync_state(status="running", days=100, synced_count=12, skipped_count=3)
    state = get_state()
    assert state["status"] == "running"
    assert state["days"] == 100
    assert state["synced_count"] == 12
    assert state["skipped_count"] == 3


def test_bulk_complete_requires_done_and_count():
    db.set_mail_sync_state(status="idle", synced_count=0)
    assert not bulk_complete()
    db.set_mail_sync_state(status="done", synced_count=5)
    assert bulk_complete()


def test_list_gmail_emails_local_and_reindex():
    db.init_db()
    for index in range(3):
        _merge_gmail_fields(
            {
                "id": f"gmail-test-{index}",
                "sender": f"user{index}@example.com",
                "to_addr": "me@example.com",
                "subject": f"Subject {index}",
                "body": f"Body text {index}",
                "unread": 0,
                "created_at": db.utc_now(),
                "folder": "INBOX",
                "labels": ["INBOX"],
            }
        )
    rows = db.list_gmail_emails_local(limit=10)
    assert len(rows) >= 3
    result = reindex_all_mail_in_db(batch_size=2)
    assert result["indexed"] >= 3


def test_filter_before_upsert_pattern():
    row = {
        "labels": ["SPAM"],
        "sender": "bad@spam.example",
        "subject": "Winner",
        "id": "gmail-spam-1",
        "body": "click here",
    }
    keep, _ = should_keep_mail(row)
    assert not keep
