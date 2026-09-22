"""Confirm or reject entity_facts candidates; expire stale candidates (manifest §4B.4)."""

from __future__ import annotations

import sqlite3
from typing import Any

from .. import db

_HIGH_VALUE_FIELDS = frozenset({"material", "scope", "qty"})


def field_requires_value_confirm(field: str) -> bool:
    name = (field or "").strip().lower()
    if name in _HIGH_VALUE_FIELDS:
        return True
    return "tolerance" in name or "heat_treat" in name


def _normalize_value(value: str | None) -> str:
    return (value or "").strip()


def _fetch_fact(conn: sqlite3.Connection, fact_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, card_id, field, value, source_kind, state, expires_at
        FROM entity_facts
        WHERE id = ?
        """,
        (fact_id,),
    ).fetchone()


def list_quotable_fact_ids(
    card_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> list[str]:
    """Confirmed facts only — candidates and rejected rows are never quotable."""

    def _load(connection: sqlite3.Connection) -> list[str]:
        rows = connection.execute(
            """
            SELECT id FROM entity_facts
            WHERE card_id = ? AND state = 'confirmed'
            ORDER BY field ASC, id ASC
            """,
            (card_id,),
        ).fetchall()
        return [str(row["id"]) for row in rows]

    if conn is not None:
        return _load(conn)
    with db.connect() as connection:
        return _load(connection)


def expire_candidates(
    now: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Reject candidate facts whose expires_at is in the past. Confirmed facts are untouched."""

    def _run(connection: sqlite3.Connection) -> int:
        cur = connection.execute(
            """
            UPDATE entity_facts
            SET state = 'rejected'
            WHERE state = 'candidate'
              AND expires_at IS NOT NULL
              AND expires_at < ?
            """,
            (now,),
        )
        return int(cur.rowcount or 0)

    if conn is not None:
        return _run(conn)
    with db.connect() as connection:
        return _run(connection)


def confirm_fact(
    fact_id: str,
    confirmed_by: str,
    value: str | None = None,
    *,
    conn: sqlite3.Connection | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    actor = (confirmed_by or "").strip()
    if not actor:
        return {"ok": False, "error": "confirmed_by required"}

    confirmed_at = now or db.utc_now()

    def _run(connection: sqlite3.Connection) -> dict[str, Any]:
        row = _fetch_fact(connection, fact_id)
        if not row:
            return {"ok": False, "error": "not_found", "fact_id": fact_id}
        if row["state"] != "candidate":
            return {
                "ok": False,
                "error": "not_candidate",
                "fact_id": fact_id,
                "state": row["state"],
            }

        field = str(row["field"])
        stored_value = str(row["value"])
        if field_requires_value_confirm(field):
            if _normalize_value(value) != _normalize_value(stored_value):
                return {
                    "ok": False,
                    "error": "value_required",
                    "fact_id": fact_id,
                    "state": "candidate",
                    "field": field,
                }

        source_kind = str(row["source_kind"])
        confirmed_from: str | None = None
        if source_kind == "vision_suggestion":
            confirmed_from = "vision_suggestion"

        connection.execute(
            """
            UPDATE entity_facts
            SET state = 'confirmed',
                confirmed_by = ?,
                confirmed_at = ?,
                confirmed_from = ?
            WHERE id = ?
            """,
            (actor, confirmed_at, confirmed_from, fact_id),
        )
        return {
            "ok": True,
            "fact_id": fact_id,
            "state": "confirmed",
            "confirmed_by": actor,
            "confirmed_at": confirmed_at,
            "confirmed_from": confirmed_from,
            "source_kind": source_kind,
        }

    if conn is not None:
        return _run(conn)
    with db.connect() as connection:
        return _run(connection)


def reject_fact(
    fact_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    def _run(connection: sqlite3.Connection) -> dict[str, Any]:
        row = _fetch_fact(connection, fact_id)
        if not row:
            return {"ok": False, "error": "not_found", "fact_id": fact_id}
        if row["state"] != "candidate":
            return {
                "ok": False,
                "error": "not_candidate",
                "fact_id": fact_id,
                "state": row["state"],
            }
        connection.execute(
            "UPDATE entity_facts SET state = 'rejected' WHERE id = ?",
            (fact_id,),
        )
        return {"ok": True, "fact_id": fact_id, "state": "rejected"}

    if conn is not None:
        return _run(conn)
    with db.connect() as connection:
        return _run(connection)
