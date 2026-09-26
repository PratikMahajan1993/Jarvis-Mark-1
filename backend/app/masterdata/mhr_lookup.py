"""Temporal as-of lookup for machine hour rate floors."""

from __future__ import annotations

import sqlite3
from typing import TypedDict

from ..config import settings


class MachineHourRateAsOf(TypedDict):
    min_mhr_minor: int
    attested_by: str
    attested_at: str | None
    shipped_seed_value_minor: int | None


def sync_mhr_demo_if_enabled(conn: sqlite3.Connection | None = None) -> None:
    """When masterdata is on, ensure SQL MHR seed rows exist.

    ``mhr-demo.md`` is obsolete once the flag is on. The markdown importer
    remains for explicit one-off use; this path no longer calls it.
    """
    if not settings.masterdata_enabled:
        return
    from .seed_master_data import seed_master_data

    if conn is not None:
        seed_master_data(conn)
        return
    from .. import db

    with db.connect() as c:
        seed_master_data(c)


_RATE_COLS = "min_mhr_minor, attested_by, attested_at, shipped_seed_value_minor, machine_id"
_WINDOW_SQL = """
  AND effective_from <= ?
  AND (effective_to IS NULL OR TRIM(effective_to) = '' OR effective_to > ?)
"""


def _rate_from_row(row: sqlite3.Row | None) -> MachineHourRateAsOf | None:
    if not row:
        return None
    seed = row["shipped_seed_value_minor"]
    return MachineHourRateAsOf(
        min_mhr_minor=int(row["min_mhr_minor"]),
        attested_by=(row["attested_by"] or "").strip(),
        attested_at=row["attested_at"],
        shipped_seed_value_minor=int(seed) if seed is not None else None,
    )


def machine_hour_rate_as_of(
    conn: sqlite3.Connection,
    *,
    machine_type: str,
    as_of: str,
    machine_id: str | None = None,
) -> MachineHourRateAsOf | None:
    """Rate valid on as_of for one machine, else the type floor.

    A set ``machine_id`` uses that machine's current row. With no id, a
    type-level row (``machine_id`` IS NULL) is the floor. Several current
    machine-specific rows for the same type and no id return None — never
    the latest ``effective_from`` across different machines. One current
    machine-specific row still resolves so a type lookup of a single seeded
    machine keeps working.
    """
    norm = (machine_type or "").strip()
    day = (as_of or "").strip()[:10]
    if not norm or len(day) != 10:
        return None
    mid = (machine_id or "").strip()
    if mid:
        row = conn.execute(
            f"""
            SELECT {_RATE_COLS}
            FROM machine_hour_rates
            WHERE machine_id = ?
              AND machine_type = ? COLLATE NOCASE
              {_WINDOW_SQL}
            ORDER BY effective_from DESC
            LIMIT 1
            """,
            (mid, norm, day, day),
        ).fetchone()
        return _rate_from_row(row)

    specific = conn.execute(
        f"""
        SELECT {_RATE_COLS}
        FROM machine_hour_rates
        WHERE machine_id IS NOT NULL
          AND TRIM(machine_id) != ''
          AND machine_type = ? COLLATE NOCASE
          {_WINDOW_SQL}
        ORDER BY effective_from DESC
        """,
        (norm, day, day),
    ).fetchall()
    machine_ids: list[str] = []
    for row in specific:
        ident = str(row["machine_id"])
        if ident not in machine_ids:
            machine_ids.append(ident)
    if len(machine_ids) > 1:
        return None

    type_row = conn.execute(
        f"""
        SELECT {_RATE_COLS}
        FROM machine_hour_rates
        WHERE machine_id IS NULL
          AND machine_type = ? COLLATE NOCASE
          {_WINDOW_SQL}
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (norm, day, day),
    ).fetchone()
    if type_row:
        return _rate_from_row(type_row)
    if len(machine_ids) == 1:
        return _rate_from_row(specific[0])
    return None


def min_mhr_minor_as_of(
    conn: sqlite3.Connection,
    *,
    machine_type: str,
    as_of: str,
    machine_id: str | None = None,
) -> int | None:
    """Return min_mhr_minor valid on as_of (YYYY-MM-DD), or None."""
    rec = machine_hour_rate_as_of(
        conn,
        machine_type=machine_type,
        as_of=as_of,
        machine_id=machine_id,
    )
    if not rec:
        return None
    return rec["min_mhr_minor"]


def mhr_demo_floor_rupees_as_of(
    conn: sqlite3.Connection,
    machine_type: str,
    as_of: str,
    machine_id: str | None = None,
) -> float | None:
    """Floor in INR/hr (same units as session last_quote_machining_rate), or None."""
    minor = min_mhr_minor_as_of(
        conn,
        machine_type=machine_type,
        as_of=as_of,
        machine_id=machine_id,
    )
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
