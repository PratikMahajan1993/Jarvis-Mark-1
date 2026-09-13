from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.agent import resolve_pending
from app.intent import classify, match_mail_trigger
from app.mail_compose import extract_email_address, llm_fill_compose, start_email_compose


def setup_module(_module=None):
    db.init_db()


def test_tight_compose_triggers():
    assert classify("Draft an email to ops@example.com saying hello").kind == "mail_draft"
    assert classify("send an email to ops@example.com").kind == "mail_draft"
    assert classify("reply to that").kind == "mail_draft"
    assert classify("reply to Neha").kind == "mail_draft"
    assert classify("write to Deepak").kind == "chat"
    assert classify("can you maybe email them").kind == "chat"
    hit = match_mail_trigger("Draft an email to ops@example.com saying the shop is clear")
    assert hit and hit["mode"] == "compose"
    assert "ops@example.com" in str(hit["remainder"])


def test_extract_email_fixes_comma_typo():
    assert extract_email_address("pratik.281293@gggg,com") == "pratik.281293@gggg.com"


def test_llm_fill_compose_uses_seed_address(monkeypatch=None):
    with patch(
        "app.mail_compose.brain_chat",
        return_value={
            "content": '{"to":"ops@example.com","subject":"Shop clear","body":"The shop is clear this afternoon.","speak":"Draft ready."}'
        },
    ):
        filled = llm_fill_compose(
            user_message="Draft an email to ops@example.com saying the shop is clear this afternoon",
            remainder="to ops@example.com saying the shop is clear this afternoon",
            mode="compose",
        )
    assert filled["to"] == "ops@example.com"
    assert "shop" in filled["subject"].lower() or "shop" in filled["body"].lower()
    assert filled["missing"] == []


def test_start_email_compose_queues_pending():
    session = "compose-modal-test"
    for row in db.list_pending(session):
        db.set_pending_status(row["id"], "rejected")
    intent = classify("Draft an email to ops@example.com saying hello from the floor")
    with patch(
        "app.mail_compose.brain_chat",
        return_value={
            "content": '{"to":"ops@example.com","subject":"Hello from the floor","body":"Hello from the floor.","speak":"Draft ready for ops@example.com."}'
        },
    ):
        result = start_email_compose(session, "Draft an email to ops@example.com saying hello from the floor", intent)
    assert result.pending
    assert result.pending[0].kind == "email_compose"
    assert result.pending[0].payload["to"] == "ops@example.com"


def test_address_only_draft_asks_for_body_not_subject():
    with patch(
        "app.mail_compose.brain_chat",
        return_value={
            "content": '{"to":"pratik.281293@gmail.com","subject":"to pratik.281293@gmail.com","body":"","speak":"I need the subject, body."}'
        },
    ):
        filled = llm_fill_compose(
            user_message="Draft an email to pratik.281293@gmail.com",
            remainder="to pratik.281293@gmail.com",
            mode="compose",
        )
    assert filled["to"] == "pratik.281293@gmail.com"
    assert filled["body"] == ""
    assert filled["missing"] == ["body"]
    assert "subject" not in filled["speak"].lower()
    assert "body" in filled["speak"].lower() or "say" in filled["speak"].lower()


def test_follow_up_body_derives_subject():
    with patch(
        "app.mail_compose.brain_chat",
        return_value={
            "content": '{"to":"pratik.281293@gmail.com","subject":"","body":"Please share current copper prices urgently.","speak":"Draft ready."}'
        },
    ):
        filled = llm_fill_compose(
            user_message="Please share current copper prices urgently",
            remainder="Please share current copper prices urgently",
            mode="compose",
            seed_to="pratik.281293@gmail.com",
            seed_subject="",
            seed_body="",
            follow_up=True,
        )
    assert filled["missing"] == []
    assert filled["body"]
    assert filled["subject"]
    assert "@" not in filled["subject"]


def test_authorize_incomplete_compose_stays_pending():
    session = "compose-incomplete"
    for row in db.list_pending(session):
        db.set_pending_status(row["id"], "rejected")
    action_id = f"compose-incomplete-{uuid.uuid4().hex[:8]}"
    pending = db.add_pending(
        action_id,
        session,
        "email_compose",
        "Draft email",
        "Recipient needed",
        {"to": "", "subject": "Hi", "body": "Hello", "missing": ["to"]},
        agent_id="ops",
        tool_name="draft_email",
    )
    db.set_focus_pending(session, pending["id"])
    out = resolve_pending(pending["id"], True, session)
    assert "need" in out.speak.lower() or "recipient" in out.speak.lower()
    still = db.get_pending(pending["id"])
    assert still and still["status"] == "pending"
