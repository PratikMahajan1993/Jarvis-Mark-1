"""SQLite VACUUM INTO backups, boot integrity_check helper, sent-quote archive."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings

BACKUP_GLOB = "jarvis-*.db"

_last_integrity_status: str | None = None


def last_integrity_status() -> str | None:
    return _last_integrity_status


def run_integrity_check(conn: sqlite3.Connection) -> str:
    """Run PRAGMA integrity_check on conn; record and return the status string."""
    global _last_integrity_status
    row = conn.execute("PRAGMA integrity_check").fetchone()
    status = str(row[0]) if row else "missing integrity_check result"
    _last_integrity_status = status
    return status


def _sqlite_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def backup_database(dest_dir: str | Path, keep: int = 7) -> Path:
    """Copy the live jarvis.db via VACUUM INTO dest_dir; retain the newest `keep` files."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    target = dest / f"jarvis-{stamp}.db"
    if target.exists():
        raise FileExistsError(target)

    source = settings.db_path.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"database not found: {source}")

    dest_sql = _sqlite_path(target)
    conn = sqlite3.connect(source, timeout=5.0)
    try:
        conn.execute(f"VACUUM INTO '{dest_sql}'")
        conn.commit()
    finally:
        conn.close()

    _prune_backups(dest, keep)
    return target


def _prune_backups(dest: Path, keep: int) -> None:
    if keep < 1:
        return
    files = sorted(dest.glob(BACKUP_GLOB), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        old.unlink(missing_ok=True)


class ArchiveExistsError(FileExistsError):
    """Sent-quote archive entry already exists for this PDF digest."""


def archive_sent_quote(
    pdf_path: str | Path,
    payload: dict[str, Any],
    dest_dir: str | Path,
) -> dict[str, str]:
    """Append-only copy of sent quote PDF + JSON payload keyed by content sha256."""
    src = Path(pdf_path)
    if not src.is_file():
        raise FileNotFoundError(src)

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    pdf_bytes = src.read_bytes()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    pdf_dest = dest / f"{digest}.pdf"
    json_dest = dest / f"{digest}.json"
    if pdf_dest.exists() or json_dest.exists():
        raise ArchiveExistsError(f"archive already exists for sha256 {digest}")

    pdf_dest.write_bytes(pdf_bytes)
    json_dest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"sha256": digest, "pdf": str(pdf_dest), "json": str(json_dest)}


def restore_database_from_backup(backup_path: str | Path) -> Path:
    """Replace the live database file with a backup copy (operator / drill helper)."""
    backup = Path(backup_path).resolve()
    if not backup.is_file():
        raise FileNotFoundError(backup)
    target = settings.db_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(backup.read_bytes())
    return target
