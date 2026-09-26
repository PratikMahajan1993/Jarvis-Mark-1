"""Exact alias resolution. No similarity, no fuzzy match — an unknown alias is unresolved."""

from __future__ import annotations

import sqlite3


class AliasError(ValueError):
    """Alias write rejected."""


def _clean(alias: str) -> str:
    text = (alias or "").strip()
    if not text:
        raise AliasError("Alias is empty.")
    return text


def add_customer_alias(conn: sqlite3.Connection, customer_id: str, alias: str, source: str = "manual") -> dict:
    return _add(conn, "customer_aliases", "customer_id", "customers", customer_id, alias, source)


def remove_customer_alias(conn: sqlite3.Connection, alias: str) -> dict:
    return _remove(conn, "customer_aliases", alias)


def list_customer_aliases(conn: sqlite3.Connection, customer_id: str | None = None) -> list[dict]:
    return _list(conn, "customer_aliases", "customer_id", "customers", "name", customer_id)


def resolve_customer_alias(conn: sqlite3.Connection, alias: str) -> str | None:
    return _resolve(conn, "customer_aliases", "customer_id", alias)


def add_machine_alias(conn: sqlite3.Connection, machine_id: str, alias: str, source: str = "manual") -> dict:
    return _add(conn, "machine_aliases", "machine_id", "machines", machine_id, alias, source)


def remove_machine_alias(conn: sqlite3.Connection, alias: str) -> dict:
    return _remove(conn, "machine_aliases", alias)


def list_machine_aliases(conn: sqlite3.Connection, machine_id: str | None = None) -> list[dict]:
    return _list(conn, "machine_aliases", "machine_id", "machines", "name", machine_id)


def resolve_machine_alias(conn: sqlite3.Connection, alias: str) -> str | None:
    return _resolve(conn, "machine_aliases", "machine_id", alias)


def add_vendor_alias(conn: sqlite3.Connection, vendor_id: str, alias: str, source: str = "manual") -> dict:
    return _add(conn, "vendor_aliases", "vendor_id", "suppliers", vendor_id, alias, source)


def remove_vendor_alias(conn: sqlite3.Connection, alias: str) -> dict:
    return _remove(conn, "vendor_aliases", alias)


def list_vendor_aliases(conn: sqlite3.Connection, vendor_id: str | None = None) -> list[dict]:
    return _list(conn, "vendor_aliases", "vendor_id", "suppliers", "name", vendor_id)


def resolve_vendor_alias(conn: sqlite3.Connection, alias: str) -> str | None:
    return _resolve(conn, "vendor_aliases", "vendor_id", alias)


def _add(
    conn: sqlite3.Connection,
    table: str,
    id_col: str,
    parent: str,
    parent_id: str,
    alias: str,
    source: str,
) -> dict:
    canonical = (parent_id or "").strip()
    text = _clean(alias)
    src = (source or "manual").strip() or "manual"
    if not canonical:
        raise AliasError("Canonical id is required.")
    found = conn.execute(f"SELECT id FROM {parent} WHERE id = ?", (canonical,)).fetchone()
    if found is None:
        raise AliasError("Canonical record was not found.")
    try:
        conn.execute(
            f"INSERT INTO {table} ({id_col}, alias, source) VALUES (?, ?, ?)",
            (canonical, text, src),
        )
    except sqlite3.IntegrityError as exc:
        raise AliasError("That alias is already assigned.") from exc
    return {"alias": text, "canonical_id": canonical, "source": src}


def _remove(conn: sqlite3.Connection, table: str, alias: str) -> dict:
    text = _clean(alias)
    cur = conn.execute(f"DELETE FROM {table} WHERE alias = ? COLLATE NOCASE", (text,))
    if not cur.rowcount:
        raise AliasError("Alias was not found.")
    return {"alias": text, "removed": True}


def _resolve(conn: sqlite3.Connection, table: str, id_col: str, alias: str) -> str | None:
    text = (alias or "").strip()
    if not text:
        return None
    row = conn.execute(
        f"SELECT {id_col} AS canonical_id FROM {table} WHERE alias = ? COLLATE NOCASE LIMIT 1",
        (text,),
    ).fetchone()
    if row is None:
        return None
    return str(row["canonical_id"])


def _list(
    conn: sqlite3.Connection,
    table: str,
    id_col: str,
    parent: str,
    name_col: str,
    parent_id: str | None,
) -> list[dict]:
    sql = f"""
        SELECT a.alias AS alias, a.{id_col} AS canonical_id, a.source AS source, p.{name_col} AS canonical_name
        FROM {table} a
        JOIN {parent} p ON p.id = a.{id_col}
    """
    params: tuple = ()
    if parent_id:
        sql += f" WHERE a.{id_col} = ?"
        params = (parent_id,)
    sql += " ORDER BY a.alias COLLATE NOCASE"
    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "alias": row["alias"],
            "canonical_id": row["canonical_id"],
            "canonical_name": row["canonical_name"],
            "source": row["source"],
        }
        for row in rows
    ]
