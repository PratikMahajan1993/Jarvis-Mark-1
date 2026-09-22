from __future__ import annotations

import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-migrations-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)

from app import db  # noqa: E402


def _db_file() -> Path:
    return settings.db_path


def _legacy_pre_migration_db(path: Path) -> None:
    """Schema shape before migration runner (CREATE only, no patch columns)."""
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                customer TEXT NOT NULL,
                part_name TEXT NOT NULL,
                material TEXT NOT NULL,
                machine TEXT NOT NULL,
                cycle_min REAL,
                margin REAL,
                drawing_file TEXT,
                created_at TEXT NOT NULL
            );
            INSERT INTO messages (session_id, role, content, created_at)
            VALUES ('legacy-session', 'user', 'keep-me', '2020-01-01T00:00:00+00:00');
            INSERT INTO jobs (id, customer, part_name, material, machine, created_at)
            VALUES ('job-legacy', 'Acme', 'Bracket', '6061', 'VMC', '2020-01-01T00:00:00+00:00');
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_fresh_db_migrations_and_pragmas():
    path = _db_file()
    if path.exists():
        path.unlink()

    db.init_db()

    with db.connect() as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        busy = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        rows = conn.execute("SELECT version, name FROM schema_migrations ORDER BY version").fetchall()
        names = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}

    assert mode.lower() == "wal"
    assert fk == 1
    assert busy == 5000
    assert len(rows) >= 1
    assert rows[0]["version"] == 1
    assert "jobs" in names
    assert "rfqs" in names


def test_second_init_db_is_idempotent():
    path = _db_file()
    if path.exists():
        path.unlink()

    db.init_db()
    with db.connect() as conn:
        first_count = conn.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()["n"]

    db.init_db()
    with db.connect() as conn:
        second_count = conn.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()["n"]

    assert first_count == second_count
    assert second_count >= 1


def test_existing_db_stamped_and_rows_preserved():
    path = _db_file()
    if path.exists():
        path.unlink()

    _legacy_pre_migration_db(path)
    db.init_db()

    with db.connect() as conn:
        msg = conn.execute(
            "SELECT content FROM messages WHERE session_id = ?",
            ("legacy-session",),
        ).fetchone()
        job = conn.execute("SELECT id FROM jobs WHERE id = ?", ("job-legacy",)).fetchone()
        stamped = conn.execute("SELECT version FROM schema_migrations WHERE version = 1").fetchone()
        job_cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}

    assert msg is not None and msg["content"] == "keep-me"
    assert job is not None
    assert stamped is not None
    assert "geometry_notes" in job_cols


def test_concurrent_write_waits_on_busy_timeout():
    path = _db_file()
    if path.exists():
        path.unlink()

    db.init_db()

    gate = threading.Event()
    result: dict[str, str | None] = {"error": None}

    def holder():
        conn = sqlite3.connect(path, timeout=5.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                ("hold", "user", "blocked", db.utc_now()),
            )
            gate.set()
            time.sleep(0.35)
            conn.commit()
        finally:
            conn.close()

    def waiter():
        gate.wait(timeout=2.0)
        try:
            with db.connect() as conn:
                conn.execute(
                    "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                    ("wait", "user", "ok", db.utc_now()),
                )
        except sqlite3.OperationalError as exc:
            result["error"] = str(exc)

    t1 = threading.Thread(target=holder)
    t2 = threading.Thread(target=waiter)
    t1.start()
    t2.start()
    t1.join(timeout=5.0)
    t2.join(timeout=10.0)

    assert result["error"] is None, result["error"]
    with db.connect() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM messages WHERE session_id IN ('hold', 'wait')").fetchone()["n"]
    assert n == 2
