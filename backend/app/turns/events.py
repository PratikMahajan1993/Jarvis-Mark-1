from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from .. import db
from . import store

HEARTBEAT_INTERVAL_SEC = 5.0

_TERMINAL = frozenset({store.STATE_DONE, store.STATE_FAILED})


def append_turn_event(turn_id: str, state: str, stage: str) -> int:
    now = db.utc_now()
    with db.connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO turn_events (turn_id, state, stage, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (turn_id, state, stage, now),
        )
        event_id = int(cur.lastrowid or 0)
        if state == store.STATE_RUNNING:
            from .reaper import lease_expires_at_from

            expires = lease_expires_at_from(now)
            conn.execute(
                """
                UPDATE turns
                SET heartbeat_at = ?, lease_expires_at = ?, stage = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, expires, stage, now, turn_id),
            )
        elif state in _TERMINAL:
            conn.execute(
                """
                UPDATE turns
                SET stage = ?, updated_at = ?
                WHERE id = ?
                """,
                (stage, now, turn_id),
            )
    return event_id


def list_events_after(turn_id: str, after_id: int = 0) -> list[dict[str, Any]]:
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT id, turn_id, state, stage, created_at
            FROM turn_events
            WHERE turn_id = ? AND id > ?
            ORDER BY id ASC
            """,
            (turn_id, after_id),
        ).fetchall()
    return [dict(row) for row in rows]


def _event_payload(event: dict[str, Any], turn_row: dict[str, Any] | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "state": event["state"],
        "stage": event.get("stage") or "",
    }
    if turn_row and event["state"] in _TERMINAL:
        raw = turn_row.get("output_json") or ""
        if raw:
            try:
                payload["output"] = json.loads(raw)
            except json.JSONDecodeError:
                payload["output"] = None
        err = (turn_row.get("error") or "").strip()
        if err:
            payload["error"] = err
    return payload


def sse_frame(event: dict[str, Any], turn_row: dict[str, Any] | None = None) -> str:
    data = _event_payload(event, turn_row)
    return f"id: {event['id']}\nevent: turn\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


async def heartbeat_while_running(
    turn_id: str,
    *,
    interval_sec: float | None = None,
) -> None:
    interval = HEARTBEAT_INTERVAL_SEC if interval_sec is None else interval_sec
    while True:
        await asyncio.sleep(interval)
        row = store.get_turn(turn_id)
        if not row or row["state"] != store.STATE_RUNNING:
            return
        append_turn_event(turn_id, store.STATE_RUNNING, "working")


def publish_terminal_event(turn_id: str) -> None:
    row = store.get_turn(turn_id)
    if not row:
        return
    state = str(row.get("state") or "")
    if state not in _TERMINAL:
        return
    prior = list_events_after(turn_id, 0)
    if prior and prior[-1]["state"] in _TERMINAL:
        return
    stage = str(row.get("stage") or "").strip()
    if state == store.STATE_DONE:
        stage = stage or "complete"
    elif not stage:
        stage = (str(row.get("error") or "failed"))[:120] or "failed"
    append_turn_event(turn_id, state, stage)


async def stream_turn_events(
    turn_id: str,
    last_event_id: int = 0,
    *,
    poll_interval_sec: float = 0.15,
) -> AsyncIterator[str]:
    row = store.get_turn(turn_id)
    if not row:
        return

    cursor = last_event_id
    while True:
        batch = list_events_after(turn_id, cursor)
        for event in batch:
            cursor = int(event["id"])
            turn_row = store.get_turn(turn_id) if event["state"] in _TERMINAL else None
            yield sse_frame(event, turn_row)
            if event["state"] in _TERMINAL:
                return

        row = store.get_turn(turn_id)
        if not row:
            return
        if row["state"] in _TERMINAL:
            publish_terminal_event(turn_id)
        await asyncio.sleep(poll_interval_sec)


def parse_last_event_id(header_value: str | None) -> int:
    if not header_value:
        return 0
    raw = header_value.strip()
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0
