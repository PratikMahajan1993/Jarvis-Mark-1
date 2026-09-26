"""Confirm or reject entity_facts candidates; expire stale candidates (manifest §4B.4)."""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from .. import db

_HIGH_VALUE_FIELDS = frozenset({"material", "scope", "qty", "quantity"})


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


def confirm_drawing_fact(
    session_id: str = "",
    entity_type: str = "part_revision",
    entity_id: str = "",
    field: str = "",
    value: str = "",
    unit: str = "",
    source_ref: str = "",
) -> dict[str, Any]:
    """Owner confirms a candidate. High-value fields require the value. Result is owner_confirmed."""
    del session_id
    et = (entity_type or "").strip() or "part_revision"
    eid = (entity_id or "").strip()
    field_name = (field or "").strip()
    if not eid or not field_name:
        return {"ok": False, "error": "entity_id and field required"}
    supplied = _normalize_value(value)
    if field_requires_value_confirm(field_name) and not supplied:
        return {
            "ok": False,
            "error": "value_required",
            "field": field_name,
            "state": "candidate",
        }
    actor = "owner"
    now = db.utc_now()

    def _run(connection: sqlite3.Connection) -> dict[str, Any]:
        from .cards import ensure_card, refresh_card_counts

        card_id = ensure_card(connection, et, eid)
        row = connection.execute(
            """
            SELECT id, value FROM entity_facts
            WHERE card_id = ? AND field = ? AND state = 'candidate'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (card_id, field_name),
        ).fetchone()
        if row and (
            not field_requires_value_confirm(field_name)
            or _normalize_value(str(row["value"])) == supplied
        ):
            out = confirm_fact(
                str(row["id"]),
                actor,
                supplied or str(row["value"]),
                conn=connection,
                now=now,
            )
            if not out.get("ok"):
                return out
            connection.execute(
                "UPDATE entity_facts SET source_kind = 'owner_confirmed' WHERE id = ?",
                (row["id"],),
            )
            refresh_card_counts(connection, card_id, now)
            out["source_kind"] = "owner_confirmed"
            out["entity_id"] = eid
            return out
        if row:
            connection.execute(
                "UPDATE entity_facts SET state = 'superseded' WHERE id = ?",
                (row["id"],),
            )
        if not supplied:
            return {
                "ok": False,
                "error": "value_required",
                "field": field_name,
                "state": "candidate",
            }
        fact_id = f"fact-{uuid.uuid4().hex[:12]}"
        connection.execute(
            """
            INSERT INTO entity_facts (
              id, card_id, field, value, unit, source_kind, source_ref,
              confidence, state, confirmed_by, confirmed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, 'owner_confirmed', ?, 1, 'confirmed', ?, ?, ?)
            """,
            (
                fact_id,
                card_id,
                field_name,
                supplied,
                (unit or "").strip(),
                source_ref,
                actor,
                now,
                now,
            ),
        )
        refresh_card_counts(connection, card_id, now)
        return {
            "ok": True,
            "fact_id": fact_id,
            "state": "confirmed",
            "source_kind": "owner_confirmed",
            "confirmed_by": actor,
            "confirmed_at": now,
            "field": field_name,
            "value": supplied,
            "entity_id": eid,
        }

    with db.connect() as connection:
        return _run(connection)
