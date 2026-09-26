"""Lance write-ahead log, SQLite-first search, and explicit re-embed."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.memory import store
from app.memory.embeddings import DIM, HASH_EMBEDDING_MODEL
from app.memory.reembed_cli import main as reembed_main
from app.memory.store import (
    drain_lance_wal_once,
    forget,
    reembed_namespace,
    search,
    upsert,
)
from app.tools.registry import HANDLERS


@pytest.fixture
def memory_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(store, "_drainer_autostart", False)
    monkeypatch.setattr(store, "_lance_tried", True)
    monkeypatch.setattr(store, "_lance", None)
    monkeypatch.setattr(store, "_lance_missing_logged", False)
    db.init_db()
    return tmp_path


def _wal_rows() -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, operation, namespace, doc_id, payload, created_at, attempts, last_error FROM lance_wal ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def test_migration_creates_lance_wal_columns(memory_db):
    sql = (ROOT / "migrations" / "0027_lance_wal.sql").read_text(encoding="utf-8")
    assert sql.startswith("-- Description:")
    assert "-- Dependencies:" in sql
    with db.connect() as conn:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(lance_wal)")}
    assert {
        "operation",
        "namespace",
        "doc_id",
        "payload",
        "created_at",
        "attempts",
        "last_error",
    } <= cols


def test_upsert_wal_same_transaction_and_does_not_fail_when_lance_down(memory_db):
    saved = upsert(
        namespace="people",
        key="wal-koso",
        text="WALTOKEN-42 machining note for KOSO",
        meta={"company": "KOSO"},
    )
    assert saved["id"] == "people:wal-koso"
    rows = _wal_rows()
    assert len(rows) == 1
    assert rows[0]["operation"] == "upsert"
    assert rows[0]["namespace"] == "people"
    assert rows[0]["doc_id"] == "people:wal-koso"
    assert rows[0]["attempts"] == 1
    assert "lancedb unavailable" in (rows[0]["last_error"] or "")
    payload = json.loads(rows[0]["payload"])
    assert payload["text"] == "WALTOKEN-42 machining note for KOSO"
    assert payload["key"] == "wal-koso"


def test_wal_insert_failure_rolls_back_the_document(memory_db, monkeypatch):
    def boom(conn, **kwargs):
        raise RuntimeError("wal failed")

    monkeypatch.setattr(store, "_insert_wal", boom)
    with pytest.raises(RuntimeError, match="wal failed"):
        upsert(namespace="jobs", key="rollback-key", text="should not commit")
    with db.connect() as conn:
        row = conn.execute(
            "SELECT id FROM memory_docs WHERE namespace = ? AND key = ?",
            ("jobs", "rollback-key"),
        ).fetchone()
        wal = conn.execute("SELECT id FROM lance_wal").fetchall()
    assert row is None
    assert wal == []


def test_lance_upsert_logs_failure(memory_db, caplog):
    class BadTable:
        def delete(self, predicate):
            return None

        def add(self, rows):
            raise RuntimeError("disk full")

    class BadLance:
        def list_tables(self):
            return ["jarvis_memory"]

        def open_table(self, name):
            return BadTable()

    monkeypatch_lance = BadLance()
    store._lance_tried = True
    store._lance = monkeypatch_lance
    with caplog.at_level(logging.WARNING):
        err = store._lance_upsert("people:k", "people", "k", "text", [0.1, 0.2], {})
    assert err is not None
    assert "disk full" in err
    assert "lance upsert failed" in caplog.text


def test_drainer_deletes_wal_row_on_success(memory_db, monkeypatch):
    upsert(namespace="profile", key="pref", text="Prefer EN8 for shafts")
    assert _wal_rows()
    monkeypatch.setattr(store, "_lance_upsert", lambda *args, **kwargs: None)
    deleted = drain_lance_wal_once()
    assert deleted == 1
    assert _wal_rows() == []


def test_search_uses_sqlite_when_wal_is_behind(memory_db, monkeypatch):
    upsert(namespace="people", key="behind", text="unique BEHIND-TOKEN-99 shop note")

    def stale(*args, **kwargs):
        return [
            {
                "id": "people:stale",
                "namespace": "people",
                "key": "stale",
                "text": "STALE-LANCE",
                "meta": {},
                "score": 1.0,
            }
        ]

    monkeypatch.setattr(store, "_lance_search", stale)
    hits = search("BEHIND-TOKEN-99", namespace="people", limit=3)
    assert hits
    assert "BEHIND-TOKEN-99" in hits[0]["text"]
    assert hits[0]["text"] != "STALE-LANCE"


def test_search_uses_sqlite_when_lance_is_empty(memory_db, monkeypatch):
    upsert(namespace="corpus", key="empty-lance", text="EMPTY-LANCE-TOKEN only in sqlite")
    with db.connect() as conn:
        conn.execute("DELETE FROM lance_wal")
    monkeypatch.setattr(store, "_lance_search", lambda *args, **kwargs: [])
    hits = search("EMPTY-LANCE-TOKEN", namespace="corpus", limit=3)
    assert hits
    assert "EMPTY-LANCE-TOKEN" in hits[0]["text"]


def test_reembed_rewrites_namespace_and_is_not_a_chat_tool(memory_db):
    upsert(namespace="jobs", key="one", text="first job drawing SPL4092")
    upsert(namespace="jobs", key="two", text="second job drawing WIDGET-9912")
    with db.connect() as conn:
        conn.execute(
            "UPDATE memory_docs SET embed_dim = ?, vector = ? WHERE namespace = ? AND key = ?",
            (8, json.dumps([0.0] * 8), "jobs", "two"),
        )
    with pytest.raises(ValueError, match="mixed embedding dimensions"):
        upsert(namespace="jobs", key="three", text="blocked until reembed")

    result = reembed_namespace("jobs")
    assert result["updated"] == 2
    assert result["model_id"] == HASH_EMBEDDING_MODEL
    with db.connect() as conn:
        dims = {
            int(row["embed_dim"])
            for row in conn.execute(
                "SELECT embed_dim, vector FROM memory_docs WHERE namespace = ?",
                ("jobs",),
            )
        }
        vectors = [
            json.loads(row["vector"])
            for row in conn.execute(
                "SELECT vector FROM memory_docs WHERE namespace = ?",
                ("jobs",),
            )
        ]
    assert dims == {DIM}
    assert {len(vector) for vector in vectors} == {DIM}

    saved = upsert(namespace="jobs", key="three", text="allowed after reembed")
    assert saved["embed_dim"] == DIM
    assert "reembed_namespace" not in HANDLERS

    with pytest.raises(ValueError, match="unknown namespace"):
        reembed_namespace("not-a-namespace")


def test_reembed_cli_is_the_admin_entry(memory_db, capsys):
    upsert(namespace="session", key="note", text="session note for reembed cli")
    assert reembed_main(["session"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["namespace"] == "session"
    assert printed["updated"] == 1


def test_forget_queues_delete_without_failing_closed(memory_db):
    upsert(namespace="people", key="gone", text="forget me")
    with db.connect() as conn:
        conn.execute("DELETE FROM lance_wal")
    result = forget(namespace="people", key="gone")
    assert result["ok"] is True
    assert result["deleted"] == 1
    rows = _wal_rows()
    assert len(rows) == 1
    assert rows[0]["operation"] == "delete"
    assert rows[0]["doc_id"] == "people:gone"
