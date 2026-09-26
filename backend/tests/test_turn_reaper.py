"""Turn lease reaper — expired RUNNING rows fail or requeue by stage.

EXECUTING leases fail closed: stage is kept and nothing is rescheduled.
"""

from __future__ import annotations

import asyncio
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


def _insert_executing(
    turn_id: str,
    *,
    stage: str,
    lease_expires_at: str | None,
    updated_at: str | None = None,
    attempt: int = 1,
) -> None:
    stamp = updated_at or db.utc_now()
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
                turns_store.STATE_EXECUTING,
                stage,
                attempt,
                "send it",
                lease_expires_at,
                lease_expires_at,
                stamp,
                stamp,
            ),
        )


def test_executing_expired_fails_with_stage_and_does_not_reschedule():
    _clear_turn_data()
    scheduled: list[str] = []
    _insert_executing(
        "t-exec-send",
        stage="tool:email_send",
        lease_expires_at="2000-01-01T00:00:00+00:00",
        attempt=1,
    )

    assert reaper.reaper_pass(schedule_turn=scheduled.append) == 1

    row = turns_store.get_turn("t-exec-send")
    assert row is not None
    assert row["state"] == turns_store.STATE_FAILED
    assert row["stage"] == "tool:email_send"
    assert row["attempt"] == 1
    err = row.get("error") or ""
    assert "tool:email_send" in err
    assert "not retried" in err.lower()
    assert scheduled == []

    ev = turn_events.list_events_after("t-exec-send", 0)
    assert ev[-1]["state"] == turns_store.STATE_FAILED
    assert ev[-1]["stage"] == "tool:email_send"


def test_executing_auto_retry_stage_still_fails_without_second_send():
    """hermes would requeue a RUNNING lease. EXECUTING must not."""
    _clear_turn_data()
    scheduled: list[str] = []
    _insert_executing(
        "t-exec-hermes",
        stage="hermes",
        lease_expires_at="2000-01-01T00:00:00+00:00",
        attempt=1,
    )

    assert reaper.reaper_pass(schedule_turn=scheduled.append) == 1

    row = turns_store.get_turn("t-exec-hermes")
    assert row is not None
    assert row["state"] == turns_store.STATE_FAILED
    assert row["stage"] == "hermes"
    assert row["attempt"] == 1
    assert scheduled == []


def test_executing_fresh_lease_is_left_alone():
    _clear_turn_data()
    _insert_executing(
        "t-exec-live",
        stage="tool:quote_send",
        lease_expires_at="2999-01-01T00:00:00+00:00",
    )

    assert reaper.reaper_pass(schedule_turn=lambda _: None) == 0
    row = turns_store.get_turn("t-exec-live")
    assert row is not None
    assert row["state"] == turns_store.STATE_EXECUTING
    assert row["stage"] == "tool:quote_send"


def test_executing_unarmed_inside_window_is_not_failed():
    _clear_turn_data()
    _insert_executing("t-exec-grace", stage="confirm", lease_expires_at=None)

    assert reaper.reaper_pass(schedule_turn=lambda _: None) == 0
    row = turns_store.get_turn("t-exec-grace")
    assert row is not None
    assert row["state"] == turns_store.STATE_EXECUTING
    assert row["stage"] == "confirm"


def test_executing_unarmed_past_window_fails_and_keeps_stage():
    _clear_turn_data()
    scheduled: list[str] = []
    _insert_executing(
        "t-exec-stuck",
        stage="confirm",
        lease_expires_at=None,
        updated_at="2000-01-01T00:00:00+00:00",
    )

    assert reaper.reaper_pass(schedule_turn=scheduled.append) == 1
    row = turns_store.get_turn("t-exec-stuck")
    assert row is not None
    assert row["state"] == turns_store.STATE_FAILED
    assert row["stage"] == "confirm"
    assert scheduled == []


def test_refresh_executing_lease_extends_expiry_without_changing_stage():
    _clear_turn_data()
    past = "2000-01-01T00:00:00+00:00"
    _insert_executing(
        "t-exec-refresh",
        stage="tool:email_send",
        lease_expires_at=past,
    )

    reaper.refresh_executing_lease("t-exec-refresh")
    row = turns_store.get_turn("t-exec-refresh")
    assert row is not None
    assert row["state"] == turns_store.STATE_EXECUTING
    assert row["stage"] == "tool:email_send"
    assert row["lease_expires_at"] is not None
    assert row["lease_expires_at"] > past

    scheduled: list[str] = []
    assert reaper.reaper_pass(schedule_turn=scheduled.append) == 0
    assert scheduled == []


def test_heartbeat_while_executing_refreshes_then_stops():
    _clear_turn_data()
    past = "2000-01-01T00:00:00+00:00"
    turn_id = "t-exec-hb"
    _insert_executing(turn_id, stage="tool:quote_send", lease_expires_at=past)

    async def _run() -> None:
        task = asyncio.create_task(
            reaper.heartbeat_while_executing(turn_id, interval_sec=0.05),
        )
        await asyncio.sleep(0.02)
        row = turns_store.get_turn(turn_id)
        assert row is not None
        assert row["state"] == turns_store.STATE_EXECUTING
        assert row["stage"] == "tool:quote_send"
        assert (row.get("lease_expires_at") or "") > past
        with db.connect() as conn:
            conn.execute(
                "UPDATE turns SET state = ? WHERE id = ?",
                (turns_store.STATE_FAILED, turn_id),
            )
        await asyncio.wait_for(task, timeout=1.0)

    asyncio.run(_run())
    row = turns_store.get_turn(turn_id)
    assert row is not None
    assert row["state"] == turns_store.STATE_FAILED
    assert row["stage"] == "tool:quote_send"
