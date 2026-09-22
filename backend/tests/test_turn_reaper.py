"""Turn lease reaper — expired RUNNING rows fail or requeue by stage."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.turns import events as turn_events
from app.turns import reaper
from app.turns import store as turns_store


def _clear_turn_data() -> None:
    db.init_db()
    with db.connect() as conn:
        conn.execute("DELETE FROM turn_events")
        conn.execute("DELETE FROM turns")


def _insert_expired_running(
    turn_id: str,
    *,
    stage: str,
    attempt: int = 1,
) -> None:
    now = db.utc_now()
    past = "2000-01-01T00:00:00+00:00"
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO turns (
                id, session_id, idempotency_key, state, stage, attempt,
                input, heartbeat_at, lease_expires_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                turn_id,
                "sess",
                f"idem-{turn_id}",
                turns_store.STATE_RUNNING,
                stage,
                attempt,
                "hi",
                past,
                past,
                now,
                now,
            ),
        )


def test_hermes_expired_requeues_and_increments_attempt():
    _clear_turn_data()
    scheduled: list[str] = []

    _insert_expired_running("t-hermes-retry", stage="hermes", attempt=1)
    assert reaper.reaper_pass(schedule_turn=scheduled.append) == 1

    row = turns_store.get_turn("t-hermes-retry")
    assert row is not None
    assert row["state"] == turns_store.STATE_QUEUED
    assert row["attempt"] == 2
    assert scheduled == ["t-hermes-retry"]

    ev = turn_events.list_events_after("t-hermes-retry", 0)
    assert ev[-1]["state"] == turns_store.STATE_QUEUED
    assert ev[-1]["stage"] == "hermes"


def test_hermes_attempt_two_expires_to_failed_with_stage_in_error():
    _clear_turn_data()
    _insert_expired_running("t-hermes-fail", stage="hermes", attempt=2)

    assert reaper.reaper_pass(schedule_turn=lambda _: None) == 1

    row = turns_store.get_turn("t-hermes-fail")
    assert row is not None
    assert row["state"] == turns_store.STATE_FAILED
    assert "hermes" in (row.get("error") or "").lower()

    ev = turn_events.list_events_after("t-hermes-fail", 0)
    assert ev[-1]["state"] == turns_store.STATE_FAILED
    assert ev[-1]["stage"] == "hermes"


def test_tool_email_send_expired_fails_without_reschedule():
    _clear_turn_data()
    scheduled: list[str] = []

    _insert_expired_running("t-send-fail", stage="tool:email_send", attempt=1)
    assert reaper.reaper_pass(schedule_turn=scheduled.append) == 1

    row = turns_store.get_turn("t-send-fail")
    assert row is not None
    assert row["state"] == turns_store.STATE_FAILED
    assert "tool:email_send" in (row.get("error") or "")
    assert "not retried" in (row.get("error") or "").lower()
    assert scheduled == []

    ev = turn_events.list_events_after("t-send-fail", 0)
    assert ev[-1]["state"] == turns_store.STATE_FAILED


def test_vision_expired_fails_with_owner_ask_message():
    _clear_turn_data()
    _insert_expired_running("t-vision-fail", stage="vision", attempt=1)

    reaper.reaper_pass(schedule_turn=lambda _: None)

    row = turns_store.get_turn("t-vision-fail")
    assert row is not None
    assert row["state"] == turns_store.STATE_FAILED
    err = row.get("error") or ""
    assert "vision" in err
    assert "ask once" in err.lower()


def test_refresh_running_lease_extends_expiry():
    _clear_turn_data()
    turn_id = "t-lease-refresh"
    now = db.utc_now()
    past = "2000-01-01T00:00:00+00:00"
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO turns (
                id, session_id, idempotency_key, state, stage, input,
                heartbeat_at, lease_expires_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                turn_id,
                "sess",
                "idem-lease",
                turns_store.STATE_RUNNING,
                "hermes",
                "ping",
                past,
                past,
                now,
                now,
            ),
        )

    reaper.refresh_running_lease(turn_id)
    row = turns_store.get_turn(turn_id)
    assert row is not None
    assert row["lease_expires_at"] is not None
    assert row["lease_expires_at"] > past
