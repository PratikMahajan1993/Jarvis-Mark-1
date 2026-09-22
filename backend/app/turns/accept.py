from __future__ import annotations

import sqlite3
from typing import Any

from . import store


def accept_chat_turn(
    *,
    session_id: str,
    message: str,
    idempotency_key: str,
) -> tuple[dict[str, Any], bool]:
    """Insert QUEUED turn or return existing row. Second value is True when newly created."""
    existing = store.get_turn_by_idempotency(idempotency_key)
    if existing:
        return existing, False
    try:
        row = store.insert_queued(
            session_id=session_id,
            message=message,
            idempotency_key=idempotency_key,
        )
        return row, True
    except sqlite3.IntegrityError as exc:
        if not store.is_unique_violation(exc):
            raise
        raced = store.get_turn_by_idempotency(idempotency_key)
        if raced:
            return raced, False
        raise
