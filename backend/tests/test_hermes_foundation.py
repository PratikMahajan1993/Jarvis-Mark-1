from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.agents import agent_for_kind, agent_for_tool, agent_status_payload
from app.hermes.bridge import (
    _extract_responses_text,
    _parse_hermes_output,
    hermes_available,
)
from app.hermes.hitl import request_human_approval
from app.tools.registry import execute_tool


def setup_module(_module=None):
    db.init_db()


def test_agent_map_stable():
    items = agent_status_payload()
    assert len(items) == 4
    codes = {row["code"] for row in items}
    assert codes == {"RES.01", "SEC.02", "DAT.03", "OPS.04"}
    assert agent_for_tool("draft_email") == "ops"
    assert agent_for_tool("research") == "research"
    assert agent_for_kind("sheets_write") == "data"


def test_hitl_queues_without_sending():
    session = "hitl-test"
    pending = request_human_approval(
        session_id=session,
        kind="email_send",
        title="Send: Hello",
        summary="To test@example.com",
        payload={"to": "test@example.com", "subject": "Hello", "body": "Hi"},
        tool_name="draft_email",
    )
    assert pending["id"]
    assert pending["agent_id"] == "ops"
    assert pending["tool_name"] == "draft_email"
    rows = db.list_pending(session)
    assert any(row["id"] == pending["id"] for row in rows)
    # Reject so we do not leave junk
    db.set_pending_status(pending["id"], "rejected")


def test_draft_email_tool_queues_hitl():
    session = "draft-hitl"
    result = execute_tool(
        "draft_email",
        {"to": "ops@example.com", "subject": "Shop note", "body": "Line one"},
        session,
    )
    assert result.get("ok")
    pending = result.get("pending") or {}
    assert pending.get("kind") == "email_send"
    assert pending.get("agent_id") == "ops"
    db.set_pending_status(pending["id"], "rejected")


def test_parse_hermes_quiet_mode_stdout_stderr():
    # Quiet (-Q) mode: answer on stdout, session_id on stderr
    speak, hid = _parse_hermes_output("PONG\n", "\nsession_id: 20260914_014545_0423ff\n")
    assert speak == "PONG"
    assert hid == "20260914_014545_0423ff"


def test_parse_hermes_pong_output():
    stdout = """Query: Reply with exactly: PONG

PONG

Resume this session with:
  hermes --resume 20260914_002606_e92053

Session:        20260914_002606_e92053
Title:          PONG
Duration:       10s
Messages:       2 (1 user, 0 tool calls)
"""
    speak, hid = _parse_hermes_output(stdout, "")
    assert "PONG" in speak
    assert "Resume" not in speak
    assert hid == "20260914_002606_e92053"


def test_hermes_session_title_stable():
    from app.hermes.bridge import hermes_session_title

    assert hermes_session_title("default") == "jarvis-default"
    assert hermes_session_title("shop floor") == "jarvis-shop-floor"


def test_is_casual_greetings():
    from app.hermes.bridge import _is_casual, is_casual_message

    assert _is_casual("How are you today?")
    assert is_casual_message("hey")
    assert not _is_casual("check my unread mail")


def test_clean_speak_strips_markdown_keeps_newlines():
    from app.hermes.bridge import _clean_speak

    speak = _clean_speak("**Hello**\n\nI am fine.\n")
    assert "Hello" in speak
    assert "**" not in speak
    assert "\n" in speak


def test_hermes_cli_available_or_skip():
    # Informational: environment may or may not have hermes on PATH in CI
    assert isinstance(hermes_available(), bool)


def test_extract_responses_text():
    payload = {
        "id": "resp_abc",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "PONG"}],
            }
        ],
    }
    assert _extract_responses_text(payload) == "PONG"
