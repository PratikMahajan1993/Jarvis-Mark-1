"""Human-style stress tests for mail compose, decisions, and routing."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.agent import classify_decision, resolve_pending, run_agent
from app.config import settings
from app.intent import classify, match_mail_trigger
from app.mail_compose import (
    _is_address_only_remainder,
    _subject_from_body,
    extract_email_address,
    llm_fill_compose,
    merge_compose_from_message,
    start_email_compose,
)


def setup_module(_module=None):
    db.init_db()


def _clear_session(session: str) -> None:
    for row in db.list_pending(session):
        db.set_pending_status(row["id"], "rejected")
    db.set_focus_pending(session, None)


# --- Intent / triggers -------------------------------------------------------

COMPOSE_YES = [
    "Draft an email to pratik.281293@gmail.com",
    "draft an email to pratik.281293@gmail.com",
    "DRAFT AN EMAIL TO ops@example.com",
    "Draft a email to ops@example.com saying hi",  # a/an slip
    "draft email to ops@example.com",
    "Send an email to ops@example.com",
    "send email to ops@example.com about copper",
    "Compose an email to Neha",
    "compose a mail to ops@example.com",
    "Write an email to ops@example.com",
    "write a mail to ops@example.com saying the shop is clear",
    "Draft an e-mail to ops@example.com",
    "  draft an email to ops@example.com  ",
    "Draft an email to pratik.281293@gggg,com",  # comma typo
    "Draft an email , to ops@example.com",
]

COMPOSE_NO = [
    "write to Deepak",
    "email Pratik about copper",
    "can you maybe draft something later",
    "I drafted an email yesterday",
    "please check my email",
    "send this email",  # loose — not tight trigger
    "forward that email",
    "don't draft an email",
]

REPLY_YES = [
    "reply to that",
    "Reply to this",
    "reply to the last email",
    "reply to the last mail",
    "draft a reply",
    "write a reply",
    "reply to Neha",
    "Reply to Pratik saying thanks",
]


@pytest.mark.parametrize("text", COMPOSE_YES)
def test_compose_triggers_human_variants(text: str):
    assert classify(text).kind == "mail_draft", text
    assert match_mail_trigger(text) is not None, text


@pytest.mark.parametrize("text", COMPOSE_NO)
def test_compose_rejects_loose_phrasing(text: str):
    assert classify(text).kind != "mail_draft" or match_mail_trigger(text) is None, text


@pytest.mark.parametrize("text", REPLY_YES)
def test_reply_triggers(text: str):
    assert classify(text).kind == "mail_draft", text
    hit = match_mail_trigger(text)
    assert hit and hit["mode"] == "reply", text


# --- Address extraction ------------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("to pratik.281293@gmail.com", "pratik.281293@gmail.com"),
        ("pratik.281293@gggg,com", "pratik.281293@gggg.com"),
        ("mail ops@example.com please", "ops@example.com"),
        ("no address here", ""),
        ("Draft an email to pratik.28 1293@gmail.com", "pratik.281293@gmail.com"),
        ("to deepak.ops@pgeneration.in", "deepak.ops@pgeneration.in"),
        ("ops @ example.com", "ops@example.com"),
        ("no address here", ""),
    ],
)
def test_extract_email_variants(text: str, expected: str):
    assert extract_email_address(text) == expected


def test_spaced_local_part_still_recovers_when_possible():
    # Humans often pause mid-address while speaking; classifier may not recover.
    # Ensure comma domain typo still works (speech→text common error).
    assert extract_email_address("pratik.281293@gmail,com") == "pratik.281293@gmail.com"


# --- Subject / missing fields ------------------------------------------------

def test_address_only_remainder_helper():
    assert _is_address_only_remainder("to pratik.281293@gmail.com")
    assert _is_address_only_remainder("pratik.281293@gmail.com")
    assert not _is_address_only_remainder("saying the shop needs maintenance")


def test_subject_from_body_shortens():
    body = "Please share the current prices of copper, aluminium and MS rods urgently. Thanks."
    subj = _subject_from_body(body)
    assert subj
    assert len(subj) <= 72
    assert "@" not in subj


def test_llm_does_not_ask_for_subject_when_only_to_known():
    with patch(
        "app.mail_compose.brain_chat",
        return_value={
            "content": (
                '{"to":"pratik.281293@gmail.com","subject":"to pratik.281293@gmail.com",'
                '"body":"","speak":"I need the subject and body."}'
            )
        },
    ):
        filled = llm_fill_compose(
            user_message="Draft an email to pratik.281293@gmail.com",
            remainder="to pratik.281293@gmail.com",
            mode="compose",
        )
    assert filled["missing"] == ["body"]
    assert filled["subject"] == ""
    assert "subject" not in filled["speak"].lower()


def test_follow_up_dictation_becomes_body_and_subject():
    with patch(
        "app.mail_compose.brain_chat",
        return_value={"content": '{"to":"","subject":"","body":"","speak":""}'},
    ):
        # LLM fails / empty → salvage utterance as body
        filled = llm_fill_compose(
            user_message="ask what copper aluminium and MS rod prices are currently I need it urgently",
            remainder="ask what copper aluminium and MS rod prices are currently I need it urgently",
            mode="compose",
            seed_to="pratik.281293@gmail.com",
            follow_up=True,
        )
    assert filled["to"] == "pratik.281293@gmail.com"
    assert filled["body"]
    assert filled["subject"]
    assert filled["missing"] == []
    assert "authorize" in filled["speak"].lower()


def test_user_can_still_supply_subject_explicitly():
    with patch(
        "app.mail_compose.brain_chat",
        return_value={
            "content": (
                '{"to":"ops@example.com","subject":"Shop maintenance",'
                '"body":"The floor needs maintenance this week.","speak":"Draft ready."}'
            )
        },
    ):
        filled = llm_fill_compose(
            user_message="Draft an email to ops@example.com subject Shop maintenance saying the floor needs maintenance this week",
            remainder="to ops@example.com subject Shop maintenance saying the floor needs maintenance this week",
            mode="compose",
        )
    assert filled["subject"].lower().startswith("shop")
    assert filled["missing"] == []


# --- Merge / pending flow ----------------------------------------------------

def test_merge_follow_up_fills_body_on_open_compose():
    session = f"merge-{uuid.uuid4().hex[:8]}"
    _clear_session(session)
    intent = classify("Draft an email to ops@example.com")
    with patch(
        "app.mail_compose.brain_chat",
        return_value={
            "content": '{"to":"ops@example.com","subject":"","body":"","speak":"What should the email say?"}'
        },
    ):
        first = start_email_compose(session, "Draft an email to ops@example.com", intent)
    assert first.pending
    pending = db.get_pending(first.pending[0].id)
    assert pending
    assert "body" in (pending["payload"].get("missing") or [])

    with patch(
        "app.mail_compose.brain_chat",
        return_value={
            "content": (
                '{"to":"ops@example.com","subject":"Copper prices",'
                '"body":"What are current copper prices?","speak":"Draft ready for ops@example.com. Authorize to send."}'
            )
        },
    ):
        second = merge_compose_from_message(
            session,
            "What are current copper prices",
            pending,
        )
    assert second is not None
    assert second.pending[0].payload.get("body")
    assert second.pending[0].payload.get("missing") == []
    assert "authorize" in (second.speak or "").lower()
    _clear_session(session)


def test_authorize_without_subject_derives_and_would_send_shape():
    session = f"auth-subj-{uuid.uuid4().hex[:8]}"
    _clear_session(session)
    action_id = f"compose-{uuid.uuid4().hex[:8]}"
    pending = db.add_pending(
        action_id,
        session,
        "email_compose",
        "Draft email",
        "To ops@example.com",
        {
            "to": "ops@example.com",
            "subject": "",
            "body": "Please confirm the shift start on September 19.",
            "missing": [],
        },
        agent_id="ops",
        tool_name="draft_email",
    )
    db.set_focus_pending(session, pending["id"])
    with patch("app.connectors.email.send_email", return_value={"id": "x", "thread_id": "t"}):
        out = resolve_pending(pending["id"], True, session)
    assert "sent" in out.speak.lower()
    assert "ops@example.com" in (out.reply or out.speak or "")
    _clear_session(session)


def test_authorize_without_body_stays_pending():
    session = f"auth-body-{uuid.uuid4().hex[:8]}"
    _clear_session(session)
    action_id = f"compose-{uuid.uuid4().hex[:8]}"
    pending = db.add_pending(
        action_id,
        session,
        "email_compose",
        "Draft email",
        "To ops@example.com",
        {"to": "ops@example.com", "subject": "", "body": "", "missing": ["body"]},
        agent_id="ops",
        tool_name="draft_email",
    )
    db.set_focus_pending(session, pending["id"])
    out = resolve_pending(pending["id"], True, session)
    assert "body" in out.speak.lower()
    still = db.get_pending(pending["id"])
    assert still and still["status"] == "pending"
    _clear_session(session)


# --- Decision classifier (voice) ---------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("authorize", True),
        ("authorize to send", True),
        ("Authorise to send", True),
        ("send it", True),
        ("yes", True),
        ("go ahead", True),
        ("reject", False),
        ("don't send", False),
        ("cancel", False),
        ("no", False),
        ("", None),
        ("ask what copper prices are currently", None),
        ("Please share prices and send me the list tomorrow", None),  # not pure decision
        ("yes please send the email", True),
        ("please confirm copper rod availability", None),
        ("yes please send the prices list when ready", None),
        ("confirm", True),
        ("authorize to send please", True),
    ],
)
def test_classify_decision_variants(text: str, expected: bool | None):
    assert classify_decision(text) is expected


# --- Agent routing: mail_draft bypasses Hermes; chat uses Hermes when up ----

def test_run_agent_unread_mail_skips_hermes_when_snapshot_warm():
    """A14: router tool_ops must not block on Hermes when snapshot is warm."""
    session = f"route-unread-{uuid.uuid4().hex[:8]}"
    _clear_session(session)
    object.__setattr__(settings, "hermes_enabled", True)

    from app.schemas import ChatResponse, Scene
    from app.semantic_router import IntentClassification

    route = IntentClassification(intent="tool_ops", target_agent="SEC.02", confidence=0.9)

    def boom(*_a, **_k):
        raise AssertionError("Hermes must not run for warm snapshot mail_search")

    with patch("app.hermes.bridge.run_hermes_turn", side_effect=boom), patch(
        "app.agent.snapshot_ready", return_value=True
    ), patch("app.agent._run_agent_legacy") as legacy:
        legacy.return_value = ChatResponse(
            speak="Three unread threads.",
            reply="Three unread threads.",
            scene=Scene(title="Inbox", widgets=[]),
            pending=[],
            offline=False,
        )
        result = run_agent("Any unread mail?", session, route=route)

    legacy.assert_called_once()
    assert "unread" in (result.speak or "").lower()
    _clear_session(session)


def test_run_agent_mail_draft_skips_hermes():
    session = f"route-draft-{uuid.uuid4().hex[:8]}"
    _clear_session(session)
    object.__setattr__(settings, "hermes_enabled", True)

    def boom(*_a, **_k):
        raise AssertionError("Hermes must not run for mail_draft")

    with patch("app.hermes.bridge.run_hermes_turn", side_effect=boom), patch(
        "app.mail_compose.brain_chat",
        return_value={
            "content": '{"to":"ops@example.com","subject":"","body":"","speak":"What should the email say?"}'
        },
    ):
        result = run_agent("Draft an email to ops@example.com", session)
    assert result.pending
    assert result.pending[0].kind == "email_compose"
    _clear_session(session)


def test_run_agent_shop_oee_skips_hermes():
    """F1: shop OEE must read the bound sheet — never Hermes textbook definitions."""
    from app.schemas import Scene
    from app.semantic_router import IntentClassification

    session = f"route-shop-oee-{uuid.uuid4().hex[:8]}"
    _clear_session(session)
    object.__setattr__(settings, "hermes_enabled", True)
    route = IntentClassification(intent="tool_ops", target_agent="DAT.03", confidence=0.9)

    def boom(*_a, **_k):
        raise AssertionError("Hermes must not run for shop_read")

    fake = {
        "speak": "Shop OEE is 87 percent.",
        "scene": {"title": "Shop log", "subtitle": "Production", "widgets": []},
        "data": {"ok": True},
    }
    with patch("app.hermes.bridge.run_hermes_turn", side_effect=boom), patch(
        "app.agent.execute_tool",
        return_value={"speak": fake["speak"], "scene": fake["scene"], "data": fake["data"]},
    ) as tool:
        result = run_agent("What's shop OEE?", session, route=route)
    tool.assert_called()
    assert tool.call_args[0][0] == "read_shop_sheet"
    assert "87" in (result.speak or "")
    assert "Overall Equipment Effectiveness" not in (result.speak or "")
    _clear_session(session)


def test_run_agent_chat_prefers_hermes_then_falls_back():
    session = f"route-chat-{uuid.uuid4().hex[:8]}"
    _clear_session(session)
    object.__setattr__(settings, "hermes_enabled", True)

    from app.schemas import ActivityEvent, AgentStatus, ChatResponse, Scene

    fake = ChatResponse(
        speak="Hermes here.",
        reply="Hermes here.",
        scene=Scene(title="Jarvis", widgets=[]),
        pending=[],
        activity=[ActivityEvent(id="1", time="", agent="SYS", message="gateway")],
        agents=[],
        offline=False,
    )
    with patch("app.hermes.bridge.hermes_available", return_value=True), patch(
        "app.hermes.bridge.run_hermes_turn", return_value=fake
    ) as hermes:
        result = run_agent("How are you today?", session)
    hermes.assert_called_once()
    assert "Hermes" in (result.speak or "")

    with patch("app.hermes.bridge.hermes_available", return_value=True), patch(
        "app.hermes.bridge.run_hermes_turn", side_effect=TimeoutError("Hermes timed out after 30s")
    ), patch("app.agent._run_agent_legacy") as legacy:
        legacy.return_value = ChatResponse(
            speak="Gemini fallback.",
            reply="Gemini fallback.",
            scene=Scene(title="", widgets=[]),
            pending=[],
            offline=False,
        )
        result2 = run_agent("How are you today?", session)
    legacy.assert_called_once()
    assert "Gemini" in (result2.speak or "")
    _clear_session(session)


def test_new_compose_while_incomplete_replaces_draft():
    session = f"replace-{uuid.uuid4().hex[:8]}"
    _clear_session(session)
    intent = classify("Draft an email to ops@example.com")
    with patch(
        "app.mail_compose.brain_chat",
        return_value={
            "content": '{"to":"ops@example.com","subject":"","body":"","speak":"What should the email say?"}'
        },
    ):
        first = start_email_compose(session, "Draft an email to ops@example.com", intent)
    old_id = first.pending[0].id
    # Simulate agent path: new trigger while pending
    from app.agent import _run_agent

    with patch(
        "app.mail_compose.brain_chat",
        return_value={
            "content": '{"to":"other@example.com","subject":"","body":"","speak":"What should the email say?"}'
        },
    ), patch("app.hermes.bridge.hermes_available", return_value=False):
        second = _run_agent("Draft an email to other@example.com", session)
    assert second.pending
    assert second.pending[0].payload.get("to") == "other@example.com"
    old = db.get_pending(old_id)
    assert old is None or old.get("status") != "pending"
    _clear_session(session)
