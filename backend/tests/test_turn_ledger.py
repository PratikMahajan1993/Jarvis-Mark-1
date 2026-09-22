"""Turn ledger accept path (flag on): fast accept, async finish, idempotency."""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.schemas import ChatResponse, Scene
from app.turns import store as turns_store

SESSION_ID = "turn-ledger-test-session"
# Production accept SLO is 100ms; allow small harness slack on Windows CI.
ACCEPT_BUDGET_MS = 125
BRAIN_SLEEP_SEC = 1.25


def _clear_turns() -> None:
    db.init_db()
    with db.connect() as conn:
        conn.execute("DELETE FROM turns")


@pytest.fixture
def ledger_client(monkeypatch):
    _clear_turns()
    monkeypatch.setattr(settings, "turn_ledger_enabled", True)
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr("app.voicebox.prefetch_tts", lambda *_a, **_k: None)

    async def _fast_route(_message: str):
        from app.semantic_router import IntentClassification

        return IntentClassification(intent="tool_ops", target_agent="RES.01", confidence=0.9)

    def _slow_agent(message: str, session_id: str = "default", route=None) -> ChatResponse:
        time.sleep(BRAIN_SLEEP_SEC)
        return ChatResponse(speak="ledger-ok", reply="ledger-ok", scene=Scene())

    monkeypatch.setattr("app.semantic_router.try_obvious_casual", lambda _m: None)
    monkeypatch.setattr("app.semantic_router.classify_intent", _fast_route)
    monkeypatch.setattr("app.agent.run_agent", _slow_agent)

    from app.main import app

    with TestClient(app) as client:
        yield client


def test_accept_returns_before_brain_finishes(ledger_client: TestClient):
    idem = f"idem-{uuid.uuid4().hex}"
    t0 = time.perf_counter()
    resp = ledger_client.post(
        "/api/chat",
        json={"session_id": SESSION_ID, "message": "ping ledger"},
        headers={"Idempotency-Key": idem},
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"turn_id", "state"}
    assert body["state"] == turns_store.STATE_QUEUED
    assert body["turn_id"].startswith("t-")
    assert elapsed_ms < ACCEPT_BUDGET_MS, f"accept took {elapsed_ms:.1f}ms"
    assert elapsed_ms < BRAIN_SLEEP_SEC * 1000 * 0.25, "accept waited on brain work"

    turn_id = body["turn_id"]
    deadline = time.time() + BRAIN_SLEEP_SEC + 5.0
    row = None
    while time.time() < deadline:
        got = ledger_client.get(f"/api/turns/{turn_id}")
        assert got.status_code == 200
        row = got.json()
        if row["state"] in (turns_store.STATE_DONE, turns_store.STATE_FAILED):
            break
        time.sleep(0.05)

    assert row is not None
    assert row["state"] == turns_store.STATE_DONE
    assert row["output"] is not None
    assert row["output"].get("speak") == "ledger-ok"


def test_idempotency_key_reuses_turn(ledger_client: TestClient):
    idem = f"idem-{uuid.uuid4().hex}"
    first = ledger_client.post(
        "/api/chat",
        json={"session_id": SESSION_ID, "message": "once"},
        headers={"Idempotency-Key": idem},
    )
    second = ledger_client.post(
        "/api/chat",
        json={"session_id": SESSION_ID, "message": "once again"},
        headers={"Idempotency-Key": idem},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    a = first.json()
    b = second.json()
    assert a["turn_id"] == b["turn_id"]

    with db.connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM turns WHERE idempotency_key = ?",
            (idem,),
        ).fetchone()["n"]
    assert n == 1


def test_flag_off_chat_shape_unchanged(monkeypatch):
    _clear_turns()
    monkeypatch.setattr(settings, "turn_ledger_enabled", False)
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr("app.voicebox.prefetch_tts", lambda *_a, **_k: None)

    from app.main import app

    with TestClient(app) as client:
        resp = client.post(
            "/api/chat",
            json={"session_id": SESSION_ID, "message": "hide the dock"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "turn_id" not in data
    assert "speak" in data
