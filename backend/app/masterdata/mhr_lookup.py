"""Temporal as-of lookup for machine hour rate floors."""

from __future__ import annotations

import sqlite3
from typing import TypedDict

from ..config import settings
from .import_mhr_demo import import_mhr_demo_from_markdown


class MachineHourRateAsOf(TypedDict):
    min_mhr_minor: int
    attested_by: str
    attested_at: str | None
    shipped_seed_value_minor: int | None


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


def machine_hour_rate_as_of(
    conn: sqlite3.Connection,
    *,
    machine_type: str,
    as_of: str,
) -> MachineHourRateAsOf | None:
    """Rate row valid on as_of, including attestation fields."""
    norm = (machine_type or "").strip()
    if not norm:
        return None
    row = conn.execute(
        """
        SELECT min_mhr_minor, attested_by, attested_at, shipped_seed_value_minor
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
    seed = row["shipped_seed_value_minor"]
    return MachineHourRateAsOf(
        min_mhr_minor=int(row["min_mhr_minor"]),
        attested_by=(row["attested_by"] or "").strip(),
        attested_at=row["attested_at"],
        shipped_seed_value_minor=int(seed) if seed is not None else None,
    )


def min_mhr_minor_as_of(
    conn: sqlite3.Connection,
    *,
    machine_type: str,
    as_of: str,
) -> int | None:
    """Return min_mhr_minor for machine_type valid on as_of (YYYY-MM-DD), or None."""
    rec = machine_hour_rate_as_of(conn, machine_type=machine_type, as_of=as_of)
    if not rec:
        return None
    return rec["min_mhr_minor"]


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


def mhr_rate_is_sendable_as_of(rec: MachineHourRateAsOf | None) -> bool:
    """True when attested and no longer the shipped seed value."""
    if rec is None:
        return False
    if not rec["attested_by"]:
        return False
    seed = rec["shipped_seed_value_minor"]
    if seed is not None and rec["min_mhr_minor"] == seed:
        return False
    return True
