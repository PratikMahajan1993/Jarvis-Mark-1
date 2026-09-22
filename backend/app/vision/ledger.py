"""Quota ledger: cycle boundary, atomic claim, override."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .. import db
from ..config import settings
from .schema import ensure_vision_schema

VISION_CAP = 5
VISION_PAGE_THRESHOLD = 4

_SPENT_STATES = ("claimed", "dispatched", "override")


def vision_page_threshold() -> int:
    return VISION_PAGE_THRESHOLD


def current_cycle_start(*, now: datetime | None = None) -> str:
    """ISO timestamp of the 10:00 local boundary that opened the current cycle."""
    tz = ZoneInfo(settings.tz or "Asia/Kolkata")
    instant = now.astimezone(tz) if now else datetime.now(tz)
    boundary_today = instant.replace(hour=10, minute=0, second=0, microsecond=0)
    if instant < boundary_today:
        boundary_today = boundary_today - timedelta(days=1)
    return boundary_today.isoformat()


def next_cycle_reset_at(*, now: datetime | None = None) -> str:
    """ISO timestamp of the next 10:00 local boundary after the current cycle opened."""
    tz = ZoneInfo(settings.tz or "Asia/Kolkata")
    cycle_iso = current_cycle_start(now=now)
    opened = datetime.fromisoformat(cycle_iso)
    if opened.tzinfo is None:
        opened = opened.replace(tzinfo=tz)
    return (opened + timedelta(days=1)).isoformat()


def current_cycle_used(*, now: datetime | None = None) -> int:
    cycle = current_cycle_start(now=now)
    with db.connect() as conn:
        ensure_vision_schema(conn)
        return _count_charged_units(conn, cycle)


def _count_charged_units(conn: sqlite3.Connection, cycle_start: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM vision_quota_usage
        WHERE cycle_start = ? AND state IN ('claimed', 'dispatched', 'override')
        """,
        (cycle_start,),
    ).fetchone()
    return int(row["n"] if row else 0)


def _get_usage_row(conn: sqlite3.Connection, cycle_start: str, file_sha256: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM vision_quota_usage
        WHERE cycle_start = ? AND file_sha256 = ?
        """,
        (cycle_start, file_sha256),
    ).fetchone()


def claim_unit(
    conn: sqlite3.Connection,
    *,
    cycle_start: str,
    file_sha256: str,
    customer_id: str | None,
    spent_by: str,
    arrival: str,
    pages: int,
    turn_id: str | None = None,
) -> dict[str, Any]:
    """
    Atomically claim one quota unit for this document in the cycle.
    Returns {"ok": True, "claim_id", "reused": bool} or {"ok": False, "reason": "cap"|"exists"}.
    """
    existing = _get_usage_row(conn, cycle_start, file_sha256)
    if existing:
        state = str(existing["state"])
        if state == "dispatched":
            return {"ok": True, "claim_id": existing["id"], "reused": True}
        if state in _SPENT_STATES:
            return {"ok": True, "claim_id": existing["id"], "reused": False}
    charged = _count_charged_units(conn, cycle_start)
    if charged >= VISION_CAP:
        return {"ok": False, "reason": "cap"}
    claim_id = uuid.uuid4().hex[:16]
    try:
        conn.execute(
            """
            INSERT INTO vision_quota_usage (
              id, cycle_start, file_sha256, customer_id, spent_by, arrival,
              pages, state, turn_id, override_action_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'claimed', ?, NULL, ?)
            """,
            (
                claim_id,
                cycle_start,
                file_sha256,
                customer_id,
                spent_by,
                arrival,
                pages,
                turn_id,
                db.utc_now(),
            ),
        )
    except sqlite3.IntegrityError:
        row = _get_usage_row(conn, cycle_start, file_sha256)
        if row and str(row["state"]) == "dispatched":
            return {"ok": True, "claim_id": row["id"], "reused": True}
        return {"ok": False, "reason": "race"}
    return {"ok": True, "claim_id": claim_id, "reused": False}


def release_claim(conn: sqlite3.Connection, claim_id: str) -> None:
    ensure_vision_schema(conn)
    conn.execute("DELETE FROM vision_quota_usage WHERE id = ? AND state = 'claimed'", (claim_id,))


def mark_dispatched(conn: sqlite3.Connection, claim_id: str) -> None:
    ensure_vision_schema(conn)
    conn.execute(
        "UPDATE vision_quota_usage SET state = 'dispatched' WHERE id = ?",
        (claim_id,),
    )


def write_disclosure(
    conn: sqlite3.Connection,
    *,
    file_sha256: str,
    customer_id: str | None,
    provider: str,
    purpose: str,
    nbytes: int,
    turn_id: str | None,
    cycle_start: str,
    authorized_by: str,
) -> None:
    ensure_vision_schema(conn)
    conn.execute(
        """
        INSERT INTO disclosure_log (
          id, file_sha256, customer_id, provider, purpose, bytes,
          turn_id, cycle_start, authorized_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex[:16],
            file_sha256,
            customer_id,
            provider,
            purpose,
            nbytes,
            turn_id,
            cycle_start,
            authorized_by,
            db.utc_now(),
        ),
    )


def apply_override_claim(
    conn: sqlite3.Connection,
    *,
    cycle_start: str,
    file_sha256: str,
    customer_id: str | None,
    arrival: str,
    pages: int,
    override_action_id: str,
    turn_id: str | None = None,
) -> dict[str, Any]:
    """
    Grant exactly one extra unit for one named document when the cycle cap is exhausted.
    Does not raise the global cap for other documents.
    """
    ensure_vision_schema(conn)
    existing = _get_usage_row(conn, cycle_start, file_sha256)
    if existing and str(existing["state"]) == "dispatched":
        return {"ok": True, "claim_id": existing["id"], "reused": True}
    if existing and str(existing["state"]) in _SPENT_STATES:
        return {"ok": True, "claim_id": existing["id"], "reused": False}
    claim_id = uuid.uuid4().hex[:16]
    try:
        conn.execute(
            """
            INSERT INTO vision_quota_usage (
              id, cycle_start, file_sha256, customer_id, spent_by, arrival,
              pages, state, turn_id, override_action_id, created_at
            ) VALUES (?, ?, ?, ?, 'owner_override', ?, ?, 'override', ?, ?, ?)
            """,
            (
                claim_id,
                cycle_start,
                file_sha256,
                customer_id,
                arrival,
                pages,
                turn_id,
                override_action_id,
                db.utc_now(),
            ),
        )
    except sqlite3.IntegrityError:
        row = _get_usage_row(conn, cycle_start, file_sha256)
        if row:
            return {"ok": True, "claim_id": row["id"], "reused": str(row["state"]) == "dispatched"}
        return {"ok": False, "reason": "race"}
    return {"ok": True, "claim_id": claim_id, "reused": False}
