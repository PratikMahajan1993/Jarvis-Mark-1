"""Turn ledger open route + hydrate mapping (mirrors orchestratorFsm.ts)."""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.turns import store as turns_store

SESSION = "reconcile-test-session"


def _clear() -> None:
    db.init_db()
    with db.connect() as conn:
        conn.execute("DELETE FROM turn_events")
        conn.execute("DELETE FROM turns")
        conn.execute("DELETE FROM pending_actions")


def _pending_still_open(turn: dict) -> bool:
    status = str(turn.get("pending_status") or "pending").lower()
    return status == "pending"


def failure_line_for_turn(turn: dict) -> str:
    """Duplicate of frontend failureLineForTurn — keep in sync for T4."""
    stage = str(turn.get("stage") or "").strip()
    if stage:
        return f"The brain dropped that at {stage}. Retry?"
    err = str(turn.get("error") or "")
    match = re.search(r"FAILED\(([^)]+)\)", err, re.I)
    if match and match.group(1).strip():
        return f"The brain dropped that at {match.group(1).strip()}. Retry?"
    return "The brain dropped that. Retry?"


def hydrate_event(turn: dict | None) -> dict:
    """Duplicate of frontend hydrate() — keep in sync for T4."""
    if not turn:
        return {"type": "RESET"}
    st = str(turn.get("state") or "").upper()
    if st in (turns_store.STATE_QUEUED, turns_store.STATE_RUNNING):
        text = str(turn.get("input") or "").strip() or "Working…"
        return {"type": "SEND", "text": text}
    if st == turns_store.STATE_AWAITING_HITL:
        action = turn.get("pending_action")
        if action and _pending_still_open(turn):
            return {"type": "AWAIT_HITL", "action": action}
        return {"type": "RESET"}
    if st == turns_store.STATE_EXECUTING:
        action_id = str(turn.get("pending_action_id") or "").strip()
        if action_id:
            return {"type": "RECONCILE", "turn": {**turn, "state": "EXECUTING", "pending_action_id": action_id}}
        return {"type": "RESET"}
    if st in (turns_store.STATE_FAILED, turns_store.STATE_ABANDONED, turns_store.STATE_DONE):
        return {"type": "RESET"}
    return {"type": "RESET"}


def _insert_open_turn(
    *,
    turn_id: str,
    state: str,
    pending_action_id: str | None = None,
    stage: str = "",
    error: str = "",
    session_id: str = SESSION,
) -> None:
    now = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO turns (
                id, session_id, idempotency_key, state, stage, input,
                pending_action_id, error, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                turn_id,
                session_id,
                f"idem-{turn_id}",
                state,
                stage,
                "authorize this send",
                pending_action_id,
                error,
                now,
                now,
            ),
        )


@pytest.fixture
def client(monkeypatch):
    _clear()
    monkeypatch.setattr(settings, "turn_ledger_enabled", True)
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_open_turns_flag_off(monkeypatch):
    _clear()
    monkeypatch.setattr(settings, "turn_ledger_enabled", False)
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/turns/open", params={"session_id": SESSION})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"enabled": False, "turns": []}


def test_open_turns_returns_awaiting_hitl_with_pending(client: TestClient):
    action_id = f"pa-{uuid.uuid4().hex[:8]}"
    turn_id = f"t-{uuid.uuid4().hex[:8]}"
    db.add_pending(
        action_id,
        SESSION,
        "email_send",
        "Send mail",
        "To: test@example.com",
        {"to": "test@example.com"},
    )
    _insert_open_turn(
        turn_id=turn_id,
        state=turns_store.STATE_AWAITING_HITL,
        pending_action_id=action_id,
        stage="confirm",
    )

    resp = client.get("/api/turns/open", params={"session_id": SESSION})
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert len(body["turns"]) == 1
    row = body["turns"][0]
    assert row["id"] == turn_id
    assert row["state"] == turns_store.STATE_AWAITING_HITL
    assert row["pending_action_id"] == action_id
    assert row["pending_action"]["id"] == action_id
    assert row["pending_action"]["kind"] == "email_send"

    mapped = hydrate_event(row)
    assert mapped["type"] == "AWAIT_HITL"
    assert mapped["action"]["id"] == action_id


def test_failed_turn_failure_line_names_stage():
    turn = {
        "state": turns_store.STATE_FAILED,
        "stage": "vision",
        "error": "FAILED(vision): worker lease expired",
    }
    line = failure_line_for_turn(turn)
    assert "vision" in line
    assert hydrate_event(turn) == {"type": "RESET"}


def test_hydrate_running_maps_to_send():
    turn = {"state": turns_store.STATE_RUNNING, "input": "  ping  "}
    assert hydrate_event(turn) == {"type": "SEND", "text": "ping"}
