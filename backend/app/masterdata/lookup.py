"""Customer name lookup against master data tables."""

from __future__ import annotations

import sqlite3

from ..config import settings
from .import_aliases import import_client_names_from_markdown


def sync_client_names_if_enabled(conn: sqlite3.Connection | None = None) -> None:
    """When masterdata is on, backfill aliases from client-names.md (idempotent)."""
    if not settings.masterdata_enabled:
        return
    if conn is not None:
        import_client_names_from_markdown(conn)
        return
    from .. import db

    with db.connect() as c:
        import_client_names_from_markdown(c)


def customer_name_is_known(conn: sqlite3.Connection, name: str) -> bool:
    """True if name exactly matches a canonical customer name or alias (case-insensitive)."""
    norm = (name or "").strip()
    if not norm:
        return False
    row = conn.execute(
        """
        SELECT 1 FROM customer_aliases WHERE alias = ? COLLATE NOCASE LIMIT 1
        """,
        (norm,),
    ).fetchone()
    if row:
        return True
    row = conn.execute(
        """
        SELECT 1 FROM customers WHERE name = ? COLLATE NOCASE LIMIT 1
        """,
        (norm,),
    ).fetchone()
    return row is not None
