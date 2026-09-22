"""Golden JSON contracts for core HUD API routes (offline).

Pins top-level keys and value types for ``GET /api/session``, ``GET /api/pending``,
``POST /api/confirm``, and ``POST /api/chat`` so turn-ledger work cannot silently
drop fields the HUD expects.

Live ``POST /api/chat`` is exercised via the semantic-router ``ui_command`` path
(``settings.gemini_api_key`` cleared + ``hide the dock``) — no Hermes/Gemini/Ollama.
If that path were unavailable without production edits, ``ChatResponse`` model
fields would still be pinned via ``test_chat_response_model_fields``.
"""

from __future__ import annotations

import sys
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.hermes.hitl import request_human_approval
from app.schemas import ChatResponse

SESSION_ID = "golden-contract-session"

# Top-level ChatResponse keys (authoritative contract for chat + confirm bodies).
CHAT_TOP_KEYS = frozenset(ChatResponse.model_fields.keys())

SESSION_EMPTY_KEYS = frozenset({"restore", "speak", "reply", "scene", "watching", "more"})

PENDING_LIST_KEYS = frozenset({"items"})

PENDING_ITEM_KEYS = frozenset(
    {
        "id",
        "session_id",
        "kind",
        "title",
        "summary",
        "payload",
        "status",
        "created_at",
        "agent_id",
        "tool_name",
        "irreversibility",
        "consequence",
    }
)

SCENE_KEYS = frozenset({"title", "subtitle", "widgets"})

WIDGET_KEYS = frozenset(
    {
        "type",
        "label",
        "value",
        "hint",
        "title",
        "columns",
        "rows",
        "text",
        "chart_type",
        "points",
        "items",
        "cite",
        "email_id",
    }
)

AGENT_KEYS = frozenset({"id", "code", "label", "domain", "state"})

ACTIVITY_KEYS = frozenset({"id", "time", "agent", "message"})

ARTIFACT_KEYS = frozenset({"id", "kind", "name", "path", "created_at"})

ATTACHMENT_KEYS = frozenset(
    {
        "attachment_id",
        "filename",
        "mime",
        "size",
        "readable",
        "cad",
        "status",
        "local_path",
        "local_name",
        "drive_link",
        "artifact_id",
    }
)


def _assert_exact_keys(obj: Mapping[str, Any], expected: frozenset[str], *, label: str) -> None:
    keys = frozenset(obj.keys())
    assert keys == expected, f"{label}: expected keys {sorted(expected)}, got {sorted(keys)}"


def _assert_keys_superset(obj: Mapping[str, Any], required: frozenset[str], *, label: str) -> None:
    missing = required - frozenset(obj.keys())
    assert not missing, f"{label}: missing keys {sorted(missing)}"


def _assert_type(value: Any, *types: type) -> None:
    assert isinstance(value, types), f"expected {types}, got {type(value)!r}"


def _assert_chat_body(data: dict[str, Any]) -> None:
    _assert_exact_keys(data, CHAT_TOP_KEYS, label="chat/confirm body")
    _assert_type(data["speak"], str)
    _assert_type(data["reply"], str)
    _assert_type(data["offline"], bool)
    _assert_type(data["more"], int)
    _assert_type(data["watching"], bool)
    _assert_type(data["artifacts"], list)
    _assert_type(data["pending"], list)
    _assert_type(data["attachments"], list)
    _assert_type(data["activity"], list)
    _assert_type(data["agents"], list)
    if data["mail_id"] is not None:
        _assert_type(data["mail_id"], str)
    if data["critical"] is not None:
        _assert_type(data["critical"], dict)
    if data["wake_reason"] is not None:
        _assert_type(data["wake_reason"], str)
    if data["target_agent"] is not None:
        _assert_type(data["target_agent"], str)
    if data["route_intent"] is not None:
        _assert_type(data["route_intent"], str)
    if data["ui_action"] is not None:
        _assert_type(data["ui_action"], dict)

    scene = data["scene"]
    _assert_type(scene, dict)
    _assert_keys_superset(scene, SCENE_KEYS, label="scene")
    _assert_type(scene["title"], str)
    if scene.get("subtitle") is not None:
        _assert_type(scene["subtitle"], str)
    _assert_type(scene["widgets"], list)
    for widget in scene["widgets"]:
        _assert_type(widget, dict)
        _assert_keys_superset(widget, frozenset({"type"}), label="widget")
        _assert_type(widget["type"], str)

    for agent in data["agents"]:
        _assert_type(agent, dict)
        _assert_exact_keys(agent, AGENT_KEYS, label="agent")

    for event in data["activity"]:
        _assert_type(event, dict)
        _assert_exact_keys(event, ACTIVITY_KEYS, label="activity")

    for artifact in data["artifacts"]:
        _assert_type(artifact, dict)
        _assert_exact_keys(artifact, ARTIFACT_KEYS, label="artifact")

    for attachment in data["attachments"]:
        _assert_type(attachment, dict)
        _assert_exact_keys(attachment, ATTACHMENT_KEYS, label="attachment")

    for pending in data["pending"]:
        _assert_pending_item(pending)


def _assert_pending_item(item: dict[str, Any]) -> None:
    _assert_type(item, dict)
    _assert_exact_keys(item, PENDING_ITEM_KEYS, label="pending item")
    _assert_type(item["id"], str)
    _assert_type(item["session_id"], str)
    _assert_type(item["kind"], str)
    _assert_type(item["title"], str)
    _assert_type(item["summary"], str)
    _assert_type(item["payload"], dict)
    _assert_type(item["status"], str)
    _assert_type(item["created_at"], str)
    _assert_type(item["agent_id"], str)
    _assert_type(item["tool_name"], str)
    _assert_type(item["irreversibility"], int)
    _assert_type(item["consequence"], str)


def _assert_session_body(data: dict[str, Any]) -> None:
    _assert_keys_superset(data, SESSION_EMPTY_KEYS, label="session")
    _assert_type(data["restore"], bool)
    _assert_type(data["speak"], str)
    _assert_type(data["reply"], str)
    _assert_type(data["scene"], dict)
    _assert_type(data["watching"], bool)
    _assert_type(data["more"], int)


def _clear_session_tables() -> None:
    db.init_db()
    with db.connect() as conn:
        conn.execute("DELETE FROM pending_actions")
        conn.execute("DELETE FROM hud_state")
        conn.execute("DELETE FROM messages")


@pytest.fixture
def api_client(monkeypatch):
    _clear_session_tables()
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr("app.voicebox.prefetch_tts", lambda *_a, **_k: None)

    from app.main import app

    with TestClient(app) as client:
        yield client


def test_chat_response_model_fields():
    """Static pin when live chat is not executed."""
    assert CHAT_TOP_KEYS == frozenset(ChatResponse.model_fields.keys())


def test_get_session_empty_contract(api_client: TestClient):
    resp = api_client.get("/api/session", params={"session_id": SESSION_ID})
    assert resp.status_code == 200
    data = resp.json()
    _assert_exact_keys(data, SESSION_EMPTY_KEYS, label="empty session")
    _assert_session_body(data)


def test_get_pending_empty_contract(api_client: TestClient):
    resp = api_client.get("/api/pending", params={"session_id": SESSION_ID})
    assert resp.status_code == 200
    data = resp.json()
    _assert_exact_keys(data, PENDING_LIST_KEYS, label="pending list")
    _assert_type(data["items"], list)
    assert data["items"] == []


def test_get_pending_with_row_contract(api_client: TestClient):
    pending = request_human_approval(
        session_id=SESSION_ID,
        kind="memory_wipe",
        title="Forget profile namespace",
        summary="Test-only HITL row",
        payload={"namespace": "profile", "wipe_namespace": True},
        tool_name="memory_forget",
    )
    db.set_focus_pending(SESSION_ID, pending["id"])

    resp = api_client.get("/api/pending", params={"session_id": SESSION_ID})
    assert resp.status_code == 200
    data = resp.json()
    _assert_exact_keys(data, PENDING_LIST_KEYS, label="pending list")
    assert len(data["items"]) == 1
    _assert_pending_item(data["items"][0])

    db.set_pending_status(pending["id"], "rejected")


def test_post_confirm_unknown_action_contract(api_client: TestClient):
    missing_id = f"missing-{uuid.uuid4().hex}"
    resp = api_client.post(
        "/api/confirm",
        json={"session_id": SESSION_ID, "action_id": missing_id, "approved": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    _assert_chat_body(data)
    _assert_type(data["speak"], str)
    assert data["speak"].strip()


def test_post_confirm_rejected_contract(api_client: TestClient):
    pending = request_human_approval(
        session_id=SESSION_ID,
        kind="browser_action",
        title="Open example",
        summary="Contract test — reject only",
        payload={"url": "https://example.com", "title": "Example"},
        tool_name="browser_open",
    )
    db.set_focus_pending(SESSION_ID, pending["id"])

    resp = api_client.post(
        "/api/confirm",
        json={"session_id": SESSION_ID, "action_id": pending["id"], "approved": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    _assert_chat_body(data)
    _assert_type(data["speak"], str)
    assert data["speak"].strip()
    row = db.get_pending(pending["id"])
    assert row is not None
    assert row["status"] == "rejected"


def test_post_chat_ui_command_contract(api_client: TestClient):
    resp = api_client.post(
        "/api/chat",
        json={"session_id": SESSION_ID, "message": "hide the dock"},
    )
    assert resp.status_code == 200
    data = resp.json()
    _assert_chat_body(data)
    _assert_type(data["route_intent"], str)
    _assert_type(data["target_agent"], str)
    _assert_type(data["ui_action"], dict)

    session = api_client.get("/api/session", params={"session_id": SESSION_ID})
    assert session.status_code == 200
    _assert_session_body(session.json())
