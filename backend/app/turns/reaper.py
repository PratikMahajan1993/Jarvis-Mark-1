from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .. import db
from . import events, store

LEASE_DURATION_SEC = 15
REAPER_POLL_SEC = 5.0
MAX_AUTO_ATTEMPTS = 2

_AUTO_RETRY_STAGES = frozenset(
    {
        "router",
        "hermes",
        "rag",
        "tool:quote_build",
        "tool:quote_pdf",
    }
)


def _parse_utc(iso: str) -> datetime:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def lease_expires_at_from(now_iso: str | None = None) -> str:
    base = _parse_utc(now_iso or db.utc_now())
    return (base + timedelta(seconds=LEASE_DURATION_SEC)).isoformat()


def refresh_running_lease(turn_id: str) -> None:
    now = db.utc_now()
    expires = lease_expires_at_from(now)
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE turns
            SET heartbeat_at = ?, lease_expires_at = ?, updated_at = ?
            WHERE id = ? AND state = ?
            """,
            (now, expires, now, turn_id, store.STATE_RUNNING),
        )


def refresh_executing_lease(turn_id: str) -> None:
    """Heartbeat an EXECUTING turn. Does not change stage and does not requeue."""
    now = db.utc_now()
    expires = lease_expires_at_from(now)
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE turns
            SET heartbeat_at = ?, lease_expires_at = ?, updated_at = ?
            WHERE id = ? AND state = ?
            """,
            (now, expires, now, turn_id, store.STATE_EXECUTING),
        )


async def heartbeat_while_executing(
    turn_id: str,
    *,
    interval_sec: float | None = None,
) -> None:
    """Refresh the EXECUTING lease until the turn leaves that state.

    Expiry is fail-closed: the reaper marks FAILED and does not schedule another send.
    """
    interval = events.HEARTBEAT_INTERVAL_SEC if interval_sec is None else interval_sec
    while True:
        row = store.get_turn(turn_id)
        if not row or row["state"] != store.STATE_EXECUTING:
            return
        refresh_executing_lease(turn_id)
        await asyncio.sleep(interval)


def _is_never_auto_retry_stage(stage: str) -> bool:
    if stage == "confirm":
        return True
    return stage.startswith("tool:") and stage.endswith("_send")


def _executing_expired_error(stage: str) -> str:
    named = stage or "unknown"
    return f"FAILED({named}): executing lease expired; not retried automatically"


def _failure_error(stage: str) -> str:
    stage = stage or "unknown"
    if stage == "vision":
        return (
            f"FAILED({stage}): worker lease expired; owner must ask once before retry"
        )
    if _is_never_auto_retry_stage(stage):
        return f"FAILED({stage}): worker lease expired; not retried automatically"
    return f"FAILED({stage}): worker lease expired"


def _list_expired_running(now_iso: str) -> list[dict[str, Any]]:
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM turns
            WHERE state = ?
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at < ?
            ORDER BY lease_expires_at ASC
            """,
            (store.STATE_RUNNING, now_iso),
        ).fetchall()
    return [dict(row) for row in rows]


def _unarmed_executing_cutoff(now_iso: str) -> str:
    base = _parse_utc(now_iso)
    return (base - timedelta(seconds=LEASE_DURATION_SEC)).isoformat()


def _list_expired_executing(now_iso: str) -> list[dict[str, Any]]:
    """EXECUTING rows whose lease expired, or that never armed a lease within the window."""
    cutoff = _unarmed_executing_cutoff(now_iso)
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM turns
            WHERE state = ?
              AND (
                (lease_expires_at IS NOT NULL AND lease_expires_at < ?)
                OR (
                  lease_expires_at IS NULL
                  AND (updated_at IS NULL OR updated_at < ?)
                )
              )
            ORDER BY COALESCE(lease_expires_at, updated_at) ASC
            """,
            (store.STATE_EXECUTING, now_iso, cutoff),
        ).fetchall()
    return [dict(row) for row in rows]


def _requeue_turn(turn_id: str, stage: str, attempt: int) -> None:
    now = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE turns
            SET state = ?, attempt = ?, stage = ?, error = '',
                heartbeat_at = NULL, lease_expires_at = NULL,
                updated_at = ?
            WHERE id = ? AND state = ?
            """,
            (store.STATE_QUEUED, attempt, stage, now, turn_id, store.STATE_RUNNING),
        )
    events.append_turn_event(turn_id, store.STATE_QUEUED, stage)


def _fail_expired_turn(turn_id: str, stage: str, error: str) -> None:
    store.fail_turn(turn_id, error)
    events.append_turn_event(turn_id, store.STATE_FAILED, stage or "failed")


def _fail_expired_executing(turn_id: str, stage: str) -> None:
    """FAILED with the stage column unchanged. Never schedules another send."""
    store.fail_turn(turn_id, _executing_expired_error(stage))
    events.append_turn_event(turn_id, store.STATE_FAILED, stage)


def reaper_pass(
    *,
    schedule_turn: Callable[[str], None] | None = None,
    now_iso: str | None = None,
) -> int:
    """Expire RUNNING leases (retry or fail) and EXECUTING leases (fail, never retry)."""
    now = now_iso or db.utc_now()
    handled = 0
    for row in _list_expired_running(now):
        turn_id = str(row["id"])
        stage = str(row.get("stage") or "").strip()
        attempt = int(row.get("attempt") or 1)

        if stage in _AUTO_RETRY_STAGES and attempt < MAX_AUTO_ATTEMPTS:
            next_attempt = attempt + 1
            _requeue_turn(turn_id, stage, next_attempt)
            if schedule_turn is not None:
                schedule_turn(turn_id)
            handled += 1
            continue

        _fail_expired_turn(turn_id, stage, _failure_error(stage))
        handled += 1

    for row in _list_expired_executing(now):
        turn_id = str(row["id"])
        stage = str(row.get("stage") or "").strip()
        _fail_expired_executing(turn_id, stage)
        handled += 1

    return handled


def start_reaper_daemon() -> tuple[threading.Event, threading.Thread]:
    """Background poll loop; tests call reaper_pass() directly."""
    stop = threading.Event()

    def _loop() -> None:
        from .worker import schedule_turn

        while not stop.is_set():
            try:
                reaper_pass(schedule_turn=schedule_turn)
            except Exception:
                pass
            if stop.wait(REAPER_POLL_SEC):
                break

    thread = threading.Thread(target=_loop, daemon=True, name="turn-reaper")
    thread.start()
    return stop, thread
