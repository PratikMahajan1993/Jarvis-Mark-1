from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from .. import db

STATE_QUEUED = "QUEUED"
STATE_RUNNING = "RUNNING"
STATE_DONE = "DONE"
STATE_FAILED = "FAILED"


def new_turn_id() -> str:
    return f"t-{uuid.uuid4().hex}"


def get_turn(turn_id: str) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM turns WHERE id = ?", (turn_id,)).fetchone()
    return dict(row) if row else None


def get_turn_by_idempotency(idempotency_key: str) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM turns WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
    return dict(row) if row else None


def insert_queued(
    *,
    session_id: str,
    message: str,
    idempotency_key: str,
) -> dict[str, Any]:
    turn_id = new_turn_id()
    now = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO turns (
                id, session_id, idempotency_key, state, input, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (turn_id, session_id, idempotency_key, STATE_QUEUED, message, now, now),
        )
    row = get_turn(turn_id)
    assert row is not None
    return row


def mark_running(turn_id: str) -> bool:
    now = db.utc_now()
    with db.connect() as conn:
        cur = conn.execute(
            """
            UPDATE turns
            SET state = ?, updated_at = ?, heartbeat_at = ?
            WHERE id = ? AND state = ?
            """,
            (STATE_RUNNING, now, now, turn_id, STATE_QUEUED),
        )
    return cur.rowcount > 0


def finish_turn(
    turn_id: str,
    *,
    output_json: str,
    route: str = "",
) -> None:
    now = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE turns
            SET state = ?, output_json = ?, route = ?, updated_at = ?, error = ''
            WHERE id = ?
            """,
            (STATE_DONE, output_json, route, now, turn_id),
        )


def fail_turn(turn_id: str, error: str) -> None:
    now = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE turns
            SET state = ?, error = ?, updated_at = ?
            WHERE id = ?
            """,
            (STATE_FAILED, (error or "unknown error")[:2000], now, turn_id),
        )


def turn_row_to_api(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    raw = out.get("output_json") or ""
    if raw:
        try:
            out["output"] = json.loads(raw)
        except json.JSONDecodeError:
            out["output"] = None
    else:
        out["output"] = None
    return out


def is_unique_violation(exc: BaseException) -> bool:
    if not isinstance(exc, sqlite3.IntegrityError):
        return False
    return "unique" in str(exc).lower()
