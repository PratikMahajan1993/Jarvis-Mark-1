"""Temporal as-of lookup for machine hour rate floors."""

from __future__ import annotations

import sqlite3

from ..config import settings
from .import_mhr_demo import import_mhr_demo_from_markdown


def sync_mhr_demo_if_enabled(conn: sqlite3.Connection | None = None) -> None:
    """When masterdata is on, backfill demo MHR from mhr-demo.md (idempotent)."""
    if not settings.masterdata_enabled:
        return
    if conn is not None:
        import_mhr_demo_from_markdown(conn)
        return
    from .. import db

    with db.connect() as c:
        import_mhr_demo_from_markdown(c)


def min_mhr_minor_as_of(
    conn: sqlite3.Connection,
    *,
    machine_type: str,
    as_of: str,
) -> int | None:
    """Return min_mhr_minor for machine_type valid on as_of (YYYY-MM-DD), or None."""
    norm = (machine_type or "").strip()
    if not norm:
        return None
    row = conn.execute(
        """
        SELECT min_mhr_minor
        FROM machine_hour_rates
        WHERE machine_type = ? COLLATE NOCASE
          AND effective_from <= ?
          AND (effective_to IS NULL OR effective_to > ?)
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (norm, as_of, as_of),
    ).fetchone()
    if not row:
        return None
    return int(row["min_mhr_minor"])


def mhr_demo_floor_rupees_as_of(
    conn: sqlite3.Connection,
    machine_type: str,
    as_of: str,
) -> float | None:
    """Floor in INR/hr (same units as session last_quote_machining_rate), or None."""
    minor = min_mhr_minor_as_of(conn, machine_type=machine_type, as_of=as_of)
    if minor is None:
        return None
    return minor / 100.0
