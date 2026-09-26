"""Deprecated markdown backfill from client-names.md.

Obsolete once ``masterdata_enabled`` is on — SQL seed is the source.
Kept so an explicit import can still load a markdown list in tests.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

DEFAULT_CLIENT_NAMES_PATH = (
    Path(__file__).resolve().parent.parent
    / "hermes"
    / "playbooks"
    / "quote"
    / "files"
    / "client-names.md"
)

_SOURCE = "client-names.md"


def parse_client_names_markdown(text: str) -> list[str]:
    """Bullet lines only — prose headers in client-names.md are not customer names."""
    names: list[str] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw.startswith("-"):
            continue
        name = raw.lstrip("- ").strip()
        if name:
            names.append(name)
    return names


def _customer_id_for_name(name: str) -> str:
    digest = hashlib.sha256(name.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"cust_{digest}"


def import_client_names_from_markdown(
    conn: sqlite3.Connection,
    path: Path | None = None,
) -> int:
    """Insert customers and aliases from markdown; idempotent. Returns new alias rows inserted."""
    p = path or DEFAULT_CLIENT_NAMES_PATH
    if not p.is_file():
        return 0
    names = parse_client_names_markdown(p.read_text(encoding="utf-8"))
    if not names:
        return 0
    inserted = 0
    for name in names:
        canonical = name.strip()
        if not canonical:
            continue
        cid = _customer_id_for_name(canonical)
        conn.execute(
            """
            INSERT OR IGNORE INTO customers (id, name, gstin, currency, status)
            VALUES (?, ?, NULL, 'INR', 'active')
            """,
            (cid, canonical),
        )
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO customer_aliases (customer_id, alias, source)
            VALUES (?, ?, ?)
            """,
            (cid, canonical, _SOURCE),
        )
        if cur.rowcount:
            inserted += 1
    return inserted
