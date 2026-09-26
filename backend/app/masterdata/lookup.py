"""Customer name lookup and temporal as-of reads against master data tables."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import settings


def sync_client_names_if_enabled(conn: sqlite3.Connection | None = None) -> None:
    """When masterdata is on, ensure the SQL seed exists.

    ``client-names.md`` is obsolete once the flag is on. The markdown importer
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


def _as_of_day(as_of: str | None) -> str:
    """YYYY-MM-DD. Blank means today in settings.tz. A non-date is empty."""
    text = (as_of or "").strip()
    if not text:
        return datetime.now(ZoneInfo(settings.tz)).date().isoformat()
    day = text[:10]
    if len(day) == 10 and day[4] == "-" and day[7] == "-":
        return day
    return ""


def customer_name_is_known(
    conn: sqlite3.Connection,
    name: str,
    as_of: str | None = None,
) -> bool:
    """True if name matches a current customer or that customer's alias.

    Alias rows are undated. The customer window rejects a row whose
    ``effective_to`` is already past, whose ``effective_from`` is still in the
    future, or whose ``status`` is ``superseded``. Default ``as_of`` is today
    in ``settings.tz``.
    """
    norm = (name or "").strip()
    day = _as_of_day(as_of)
    if not norm or not day:
        return False
    row = conn.execute(
        """
        SELECT 1
        FROM customers c
        WHERE (
            c.name = ? COLLATE NOCASE
            OR EXISTS (
              SELECT 1 FROM customer_aliases a
              WHERE a.customer_id = c.id AND a.alias = ? COLLATE NOCASE
            )
          )
          AND LOWER(COALESCE(c.status, '')) != 'superseded'
          AND (c.effective_from IS NULL OR TRIM(c.effective_from) = '' OR c.effective_from <= ?)
          AND (c.effective_to IS NULL OR TRIM(c.effective_to) = '' OR c.effective_to > ?)
        LIMIT 1
        """,
        (norm, norm, day, day),
    ).fetchone()
    return row is not None


def material_id_for_grade(conn: sqlite3.Connection, grade: str) -> str | None:
    text = (grade or "").strip()
    if not text:
        return None
    row = conn.execute(
        """
        SELECT id FROM materials
        WHERE grade = ? COLLATE NOCASE
          AND (effective_to IS NULL OR effective_to = '')
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (text,),
    ).fetchone()
    if row is None:
        row = conn.execute(
            "SELECT id FROM materials WHERE grade = ? COLLATE NOCASE LIMIT 1",
            (text,),
        ).fetchone()
    return str(row["id"]) if row else None


def _as_of_row(conn: sqlite3.Connection, sql: str, params: tuple) -> sqlite3.Row | None:
    return conn.execute(sql, params).fetchone()


def supplier_rm_quote_as_of(conn: sqlite3.Connection, material_id: str, as_of: str) -> dict | None:
    """RM quote valid on as_of. Missing row is None — callers must treat that as a BLOCKER."""
    mid = (material_id or "").strip()
    day = (as_of or "").strip()[:10]
    if not mid or len(day) != 10:
        return None
    row = _as_of_row(
        conn,
        """
        SELECT id, supplier_id, material_id, price_minor, currency, unit_basis, size_spec,
               effective_from, effective_to, basis_date, source_kind, source_ref,
               is_estimate, attested_by, attested_at, shipped_seed_value_minor
        FROM supplier_rm_quotes
        WHERE material_id = ?
          AND effective_from <= ?
          AND (effective_to IS NULL OR effective_to > ?)
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (mid, day, day),
    )
    return dict(row) if row else None


def outsource_quote_as_of(conn: sqlite3.Connection, process: str, as_of: str) -> dict | None:
    """Outsource quote valid on as_of. Missing row is None — callers must treat that as a BLOCKER."""
    proc = (process or "").strip()
    day = (as_of or "").strip()[:10]
    if not proc or len(day) != 10:
        return None
    row = _as_of_row(
        conn,
        """
        SELECT id, vendor_id, process, spec, unit_basis, price_minor, currency,
               effective_from, effective_to, source_kind, source_ref
        FROM outsource_quotes
        WHERE process = ? COLLATE NOCASE
          AND effective_from <= ?
          AND (effective_to IS NULL OR effective_to > ?)
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (proc, day, day),
    )
    return dict(row) if row else None


def machine_capability_as_of(
    conn: sqlite3.Connection,
    machine_id: str,
    process: str,
    as_of: str,
) -> dict | None:
    """Capability row for a machine and process.

    ``machine_capabilities`` has no effective window. ``as_of`` is required so
    callers stay on the as-of API; a blank date returns None (BLOCKER).
    """
    mid = (machine_id or "").strip()
    proc = (process or "").strip()
    day = (as_of or "").strip()[:10]
    if not mid or not proc or len(day) != 10:
        return None
    row = conn.execute(
        """
        SELECT machine_id, process, tolerance_floor_mm, finish_floor_ra,
               max_part_x, max_part_y, max_part_z, max_part_kg
        FROM machine_capabilities
        WHERE machine_id = ? AND process = ? COLLATE NOCASE
        LIMIT 1
        """,
        (mid, proc),
    ).fetchone()
    return dict(row) if row else None
