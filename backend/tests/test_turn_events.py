"""Turn stage SSE stream and Last-Event-ID resume."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.turns import store as turns_store
from app.turns import events as turn_events


def _clear_turn_data() -> None:
    db.init_db()
    with db.connect() as conn:
        conn.execute("DELETE FROM turn_events")
        conn.execute("DELETE FROM turns")


def _insert_running_turn(turn_id: str = "t-test-events") -> None:
    now = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO turns (
                id, session_id, idempotency_key, state, input, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (turn_id, "sess", f"idem-{turn_id}", turns_store.STATE_RUNNING, "hi", now, now),
        )


def _read_sse_events(raw: str) -> list[dict]:
    out: list[dict] = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_id = None
        data_line = None
        for line in block.split("\n"):
            if line.startswith("id:"):
                event_id = int(line.split(":", 1)[1].strip())
            elif line.startswith("data:"):
                data_line = line.split(":", 1)[1].strip()
        if event_id is not None and data_line:
            payload = json.loads(data_line)
            payload["_id"] = event_id
            out.append(payload)
    return out


def test_last_event_id_returns_only_later_rows():
    _clear_turn_data()
    _insert_running_turn()
    first = turn_events.append_turn_event("t-test-events", turns_store.STATE_RUNNING, "alpha")
    second = turn_events.append_turn_event("t-test-events", turns_store.STATE_DONE, "beta")

    from app.main import app

    with TestClient(app) as client:
        with client.stream(
            "GET",
            "/api/turns/t-test-events/events",
            headers={"Last-Event-ID": str(first)},
        ) as resp:
            assert resp.status_code == 200
            body = resp.read().decode("utf-8")

    parsed = _read_sse_events(body)
    assert len(parsed) == 1
    assert parsed[0]["_id"] == second
    assert parsed[0]["stage"] == "beta"


def test_stream_closes_on_terminal_event():
    _clear_turn_data()
    _insert_running_turn()
    turn_events.append_turn_event("t-test-events", turns_store.STATE_RUNNING, "router")
    turn_events.append_turn_event("t-test-events", turns_store.STATE_DONE, "complete")

    from app.main import app

    with TestClient(app) as client:
        with client.stream("GET", "/api/turns/t-test-events/events") as resp:
            assert resp.status_code == 200
            body = resp.read().decode("utf-8")

    events = _read_sse_events(body)
    assert events[-1]["state"] == turns_store.STATE_DONE
    assert events[-1]["stage"] == "complete"


def test_heartbeat_interval_is_injectable():
    import asyncio

    _clear_turn_data()
    turn_id = "t-hb-inject"
    now = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO turns (
                id, session_id, idempotency_key, state, input, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (turn_id, "sess", "idem-hb", turns_store.STATE_RUNNING, "ping", now, now),
        )

    async def _run() -> None:
        hb = asyncio.create_task(
            turn_events.heartbeat_while_running(turn_id, interval_sec=0.05),
        )
        await asyncio.sleep(0.13)
        with db.connect() as conn:
            conn.execute(
                "UPDATE turns SET state = ? WHERE id = ?",
                (turns_store.STATE_DONE, turn_id),
            )
        await asyncio.wait_for(hb, timeout=1.0)

    t0 = time.perf_counter()
    asyncio.run(_run())
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, "injectable heartbeat must not require a 5s sleep"

    stages = [row["stage"] for row in turn_events.list_events_after(turn_id, 0)]
    assert "working" in stages
    assert turn_events.HEARTBEAT_INTERVAL_SEC == 5.0


def test_flag_off_chat_shape_unchanged(monkeypatch):
    """Contract: ledger flag off => no turn_id on /api/chat."""
    _clear_turn_data()
    monkeypatch.setattr(settings, "turn_ledger_enabled", False)
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr("app.voicebox.prefetch_tts", lambda *_a, **_k: None)

    from app.main import app

    with TestClient(app) as client:
        resp = client.post(
            "/api/chat",
            json={"session_id": "sse-contract", "message": "hide the dock"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "turn_id" not in data
    assert "speak" in data
