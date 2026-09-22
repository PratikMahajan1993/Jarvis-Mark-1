"""Durable /api/metrics series read from SQLite after reconnect (O1)."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-durable-metrics-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)

from app import db  # noqa: E402
from app.metrics import load_durable_metrics, metrics_snapshot  # noqa: E402


def _fresh_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _seed_turns_and_effects() -> None:
    now = db.utc_now()
    with db.connect() as conn:
        conn.executemany(
            """
            INSERT INTO turns (
                id, session_id, idempotency_key, state, stage, input, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("t1", "s1", "idem-t1", "DONE", "pricing", "a", now, now),
                ("t2", "s1", "idem-t2", "DONE", "pricing", "b", now, now),
                ("t3", "s1", "idem-t3", "FAILED", "verify", "c", now, now),
            ],
        )
        conn.execute(
            """
            INSERT INTO external_effects (
                id, action_id, provider, request_hash, state, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("ef-1", "act-1", "gmail", "hash-a", "settled", now),
        )
        conn.execute(
            """
            UPDATE rag_index_state
            SET pending = 12, embedded = 7, updated_at = ?
            WHERE id = 1
            """,
            (now,),
        )


def test_durable_metrics_survive_new_connection():
    db_path = settings.db_path
    if db_path.exists():
        db_path.unlink()

    db.init_db()
    _seed_turns_and_effects()

    conn = _fresh_connection()
    try:
        snap = load_durable_metrics(conn)
    finally:
        conn.close()

    assert snap["stage_counts"] == {"pricing": 2, "verify": 1}
    assert snap["proof_block_rate"] == {"ask": True, "reason": "no proof rows"}
    assert snap["duplicate_external_effect_count"] == 0
    assert snap["index_lag"] == {"pending": 12, "embedded": 7, "lag": 5}


def test_metrics_snapshot_includes_durable_and_legacy_keys():
    snap = metrics_snapshot()
    assert "hermes_latency" in snap
    assert snap["targets"]["casual_warm_ms"] == 5000
    assert snap["stage_counts"] == {"pricing": 2, "verify": 1}
    assert snap["index_lag"]["lag"] == 5


def test_proof_block_rate_from_rows():
    now = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO customers (id, name) VALUES ('cust-m', 'Metrics Co')"
        )
        conn.execute(
            "INSERT INTO quotes (id, customer_id) VALUES ('q-m', 'cust-m')"
        )
        conn.execute(
            """
            INSERT INTO quote_revisions (
                id, quote_id, revision, scope, scope_source, qty, currency, total_minor
            ) VALUES ('rev-m', 'q-m', 1, 'labour', 'owner', 1, 'INR', 100)
            """
        )
        conn.executemany(
            """
            INSERT INTO quote_proofs (
                id, quote_revision_id, verdict, blockers, warnings, checklist_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("p1", "rev-m", "block", 2, 0, "[]", now),
                ("p2", "rev-m", "pass", 0, 1, "[]", now),
                ("p3", "rev-m", "pass", 0, 0, "[]", now),
            ],
        )

    conn = _fresh_connection()
    try:
        snap = load_durable_metrics(conn)
    finally:
        conn.close()

    assert snap["proof_block_rate"] == 1 / 3
