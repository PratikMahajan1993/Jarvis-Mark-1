"""Structured + vector memory store (SQLite source of truth, LanceDB mirror)."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .. import db
from ..config import settings
from .embeddings import cosine, embed_document

log = logging.getLogger(__name__)

NAMESPACES = ("profile", "people", "jobs", "session", "corpus")

SQL_LOOKUP_BUDGET_MS = 500
CARD_LOAD_BUDGET_MS = 1000
CORPUS_SEARCH_BUDGET_MS = 2000
LANCE_SEARCH_BUDGET_MS = 1000
LAST_LATENCIES: dict[str, float] = {}

_lance = None
_lance_tried = False
_lance_missing_logged = False
_drainer_lock = threading.Lock()
_drain_lock = threading.Lock()
_drainer_started = False
_drainer_autostart = True
_DRAIN_INTERVAL_SEC = 2.0


def _memory_dir() -> Path:
    path = settings.data_dir / "memory"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_schema() -> None:
    with db.connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_docs (
                id TEXT PRIMARY KEY,
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                text TEXT NOT NULL,
                meta TEXT NOT NULL,
                vector TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                embed_model_id TEXT,
                embed_dim INTEGER,
                embed_provider TEXT,
                UNIQUE(namespace, key)
            )
            """
        )
        have = {str(row[1]) for row in conn.execute("PRAGMA table_info(memory_docs)")}
        for name, ddl in (
            ("embed_model_id", "TEXT"),
            ("embed_dim", "INTEGER"),
            ("embed_provider", "TEXT"),
        ):
            if name not in have:
                conn.execute(f"ALTER TABLE memory_docs ADD COLUMN {name} {ddl}")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_ns ON memory_docs(namespace)"
        )


@contextmanager
def latency_budget(operation: str, budget_ms: int) -> Iterator[None]:
    """Record elapsed ms and warn when a retrieval step misses its budget."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        LAST_LATENCIES[operation] = round(elapsed, 1)
        if elapsed > budget_ms:
            log.warning(
                "%s exceeded budget: %.0fms > %sms",
                operation,
                elapsed,
                budget_ms,
            )


def _get_lance():
    global _lance, _lance_tried
    if _lance_tried:
        return _lance
    _lance_tried = True
    try:
        import lancedb  # type: ignore

        uri = str(_memory_dir() / "lancedb")
        _lance = lancedb.connect(uri)
        return _lance
    except Exception:
        _lance = None
        return None


def _lance_upsert(doc_id: str, namespace: str, key: str, text: str, vector: list[float], meta: dict) -> str | None:
    """Mirror one row into Lance. None on success, error text otherwise. Never raises."""
    global _lance_missing_logged
    ldb = _get_lance()
    if ldb is None:
        if not _lance_missing_logged:
            log.warning("lance upsert skipped; lancedb unavailable")
            _lance_missing_logged = True
        return "lancedb unavailable"
    table_name = "jarvis_memory"
    row = {
        "id": doc_id,
        "namespace": namespace,
        "key": key,
        "text": text,
        "meta": json.dumps(meta),
        "vector": vector,
    }
    try:
        try:
            names = set(ldb.list_tables())
        except Exception:
            names = set(ldb.table_names())
        if table_name not in names:
            ldb.create_table(table_name, [row], mode="overwrite")
        else:
            table = ldb.open_table(table_name)
            try:
                table.delete(f"id = '{doc_id}'")
            except Exception:
                log.debug("lance delete-before-add skipped for %s", doc_id)
            table.add([row])
    except Exception as exc:
        log.warning("lance upsert failed doc_id=%s namespace=%s: %s", doc_id, namespace, exc)
        return str(exc)
    return None


def _reject_mixed_namespace(conn, *, namespace: str, doc_id: str, dim: int) -> None:
    rows = conn.execute(
        """
        SELECT id, embed_dim FROM memory_docs
        WHERE namespace = ? AND embed_dim IS NOT NULL
        """,
        (namespace,),
    ).fetchall()
    foreign = {
        int(row["embed_dim"])
        for row in rows
        if str(row["id"]) != doc_id and row["embed_dim"] is not None
    }
    if any(existing != dim for existing in foreign):
        raise ValueError("mixed embedding dimensions rejected")


def upsert(
    *,
    namespace: str,
    key: str,
    text: str,
    meta: dict[str, Any] | None = None,
    embed_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ensure_schema()
    ns = (namespace or "corpus").strip().lower()
    if ns not in NAMESPACES:
        ns = "corpus"
    key = (key or "").strip() or f"auto-{uuid.uuid4().hex[:10]}"
    text = (text or "").strip()
    meta = dict(meta or {})
    with latency_budget("sql_lookup", SQL_LOOKUP_BUDGET_MS):
        vector, auto_meta = embed_document(text)
        supplied = dict(embed_meta or {})
        model_id = str(supplied.get("model_id") or auto_meta["model_id"])
        provider = str(supplied.get("provider") or auto_meta["provider"])
        dim = int(supplied["dim"]) if supplied.get("dim") is not None else int(auto_meta["dim"])
        if dim != len(vector):
            raise ValueError(
                f"mixed embedding dimensions rejected: meta dim {dim} != vector {len(vector)}"
            )
        meta["embed_model_id"] = model_id
        meta["embed_dim"] = dim
        meta["embed_provider"] = provider
        now = db.utc_now()
        doc_id = f"{ns}:{key}"
        with db.connect() as conn:
            _reject_mixed_namespace(conn, namespace=ns, doc_id=doc_id, dim=dim)
            conn.execute(
                """
                INSERT INTO memory_docs (
                    id, namespace, key, text, meta, vector, created_at, updated_at,
                    embed_model_id, embed_dim, embed_provider
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET
                    text = excluded.text,
                    meta = excluded.meta,
                    vector = excluded.vector,
                    updated_at = excluded.updated_at,
                    embed_model_id = excluded.embed_model_id,
                    embed_dim = excluded.embed_dim,
                    embed_provider = excluded.embed_provider
                """,
                (
                    doc_id,
                    ns,
                    key,
                    text,
                    json.dumps(meta),
                    json.dumps(vector),
                    now,
                    now,
                    model_id,
                    dim,
                    provider,
                ),
            )
            _insert_wal(
                conn,
                operation="upsert",
                namespace=ns,
                doc_id=doc_id,
                payload={
                    "id": doc_id,
                    "namespace": ns,
                    "key": key,
                    "text": text,
                    "vector": vector,
                    "meta": meta,
                },
            )
    _schedule_lance_drain()
    return {
        "id": doc_id,
        "namespace": ns,
        "key": key,
        "text": text,
        "meta": meta,
        "embed_model_id": model_id,
        "embed_dim": dim,
        "embed_provider": provider,
    }


def _lance_table():
    ldb = _get_lance()
    if ldb is None:
        return None
    try:
        try:
            names = set(ldb.list_tables())
        except Exception:
            names = set(ldb.table_names())
        if "jarvis_memory" not in names:
            return None
        return ldb.open_table("jarvis_memory")
    except Exception:
        return None


def _lance_delete(predicate: str) -> str | None:
    """Apply one Lance delete. None on success, error text otherwise. Never raises."""
    global _lance_missing_logged
    ldb = _get_lance()
    if ldb is None:
        if not _lance_missing_logged:
            log.warning("lance delete skipped; lancedb unavailable")
            _lance_missing_logged = True
        return "lancedb unavailable"
    table = _lance_table()
    if table is None:
        return None
    try:
        table.delete(predicate)
    except Exception as exc:
        log.warning("lance delete failed predicate=%s: %s", predicate, exc)
        return str(exc)
    return None


def _sql_quote(value: str) -> str:
    return (value or "").replace("'", "")


def _insert_wal(
    conn,
    *,
    operation: str,
    namespace: str,
    doc_id: str,
    payload: dict[str, Any],
) -> None:
    """Queue a Lance mirror op in the caller's SQLite transaction."""
    conn.execute("DELETE FROM lance_wal WHERE doc_id = ?", (doc_id,))
    conn.execute(
        """
        INSERT INTO lance_wal (operation, namespace, doc_id, payload, created_at, attempts)
        VALUES (?, ?, ?, ?, ?, 0)
        """,
        (operation, namespace, doc_id, json.dumps(payload), db.utc_now()),
    )


def _lance_wal_pending() -> bool:
    try:
        with db.connect() as conn:
            row = conn.execute("SELECT 1 FROM lance_wal LIMIT 1").fetchone()
        return row is not None
    except sqlite3.OperationalError as exc:
        log.warning("lance wal pending check failed: %s", exc)
        return True


def _apply_wal_item(item: dict[str, Any]) -> str | None:
    try:
        payload = json.loads(item.get("payload") or "{}")
    except json.JSONDecodeError as exc:
        return f"bad wal payload: {exc}"
    if not isinstance(payload, dict):
        payload = {}
    operation = str(item.get("operation") or "")
    if operation == "upsert":
        vector = payload.get("vector") or []
        if not isinstance(vector, list):
            return "wal upsert payload missing vector"
        meta = payload.get("meta") or {}
        if not isinstance(meta, dict):
            meta = {}
        return _lance_upsert(
            str(payload.get("id") or item.get("doc_id") or ""),
            str(payload.get("namespace") or item.get("namespace") or ""),
            str(payload.get("key") or ""),
            str(payload.get("text") or ""),
            vector,
            meta,
        )
    if operation == "delete":
        doc_id = _sql_quote(str(payload.get("id") or item.get("doc_id") or ""))
        return _lance_delete(f"id = '{doc_id}'")
    return f"unknown lance wal operation: {operation}"


def _claim_wal(row_id: int, attempts: int) -> bool:
    with db.connect() as conn:
        cur = conn.execute(
            "UPDATE lance_wal SET attempts = attempts + 1 WHERE id = ? AND attempts = ?",
            (row_id, attempts),
        )
        return (cur.rowcount or 0) == 1


def drain_lance_wal_once(*, limit: int = 50) -> int:
    """Retry pending Lance rows. Deletes a row only after the mirror write succeeds."""
    with _drain_lock:
        return _drain_lance_wal_once_locked(limit=limit)


def _drain_lance_wal_once_locked(*, limit: int) -> int:
    try:
        with db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, operation, namespace, doc_id, payload, attempts
                FROM lance_wal
                ORDER BY id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        pending = [dict(row) for row in rows]
    except sqlite3.OperationalError as exc:
        log.warning("lance wal read failed: %s", exc)
        return 0
    done = 0
    for item in pending:
        if not _claim_wal(int(item["id"]), int(item.get("attempts") or 0)):
            continue
        err = _apply_wal_item(item)
        with db.connect() as conn:
            if err is None:
                conn.execute("DELETE FROM lance_wal WHERE id = ?", (item["id"],))
                done += 1
            else:
                conn.execute(
                    "UPDATE lance_wal SET last_error = ? WHERE id = ?",
                    (str(err)[:500], item["id"]),
                )
    return done


def _lance_wal_drainer_loop() -> None:
    while True:
        try:
            drain_lance_wal_once()
        except Exception as exc:
            log.warning("lance wal drainer pass failed: %s", exc)
        time.sleep(_DRAIN_INTERVAL_SEC)


def start_lance_wal_drainer() -> None:
    """Start the daemon that retries Lance until each WAL row succeeds."""
    global _drainer_started
    if not _drainer_autostart:
        return
    with _drainer_lock:
        if _drainer_started:
            return
        _drainer_started = True
        threading.Thread(
            target=_lance_wal_drainer_loop,
            name="lance-wal-drainer",
            daemon=True,
        ).start()


def _schedule_lance_drain() -> None:
    """Best-effort mirror. Lance being down must not fail the SQLite write."""
    try:
        start_lance_wal_drainer()
        drain_lance_wal_once()
    except Exception as exc:
        log.warning("lance wal drain schedule failed: %s", exc)


def _hit_from_row(row: dict[str, Any], score: float) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    raw_meta = row.get("meta") or "{}"
    try:
        meta = json.loads(raw_meta) if isinstance(raw_meta, str) else dict(raw_meta)
    except (json.JSONDecodeError, TypeError, ValueError):
        meta = {}
    return {
        "id": row.get("id"),
        "namespace": row.get("namespace"),
        "key": row.get("key"),
        "text": row.get("text") or "",
        "meta": meta,
        "score": round(score, 4),
        "updated_at": row.get("updated_at"),
    }


def _row_dim(item: dict[str, Any]) -> int | None:
    raw = item.get("embed_dim")
    if raw is not None and str(raw) != "":
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    try:
        vec = json.loads(item.get("vector") or "[]")
    except json.JSONDecodeError:
        return None
    return len(vec) if isinstance(vec, list) else None


def _compatible_rows(rows: list[Any], qdim: int) -> tuple[list[dict[str, Any]], bool]:
    parsed = [dict(row) for row in rows]
    dims = {dim for dim in (_row_dim(item) for item in parsed) if dim is not None}
    if len(dims) <= 1:
        return parsed, False
    log.error(
        "mixed embedding dimensions rejected: %s; falling back to hash-labelled vectors",
        sorted(dims),
    )
    kept = [
        item
        for item in parsed
        if str(item.get("embed_provider") or "") == "hash" and _row_dim(item) == qdim
    ]
    return kept, True


def _sqlite_search(query: str, *, namespace: str | None, limit: int) -> list[dict[str, Any]]:
    qvec, _qmeta = embed_document(query)
    with db.connect() as conn:
        if namespace:
            rows = conn.execute(
                "SELECT * FROM memory_docs WHERE namespace = ?",
                (namespace.strip().lower(),),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM memory_docs").fetchall()
    usable, _mixed = _compatible_rows(list(rows), len(qvec))
    scored: list[tuple[float, dict[str, Any]]] = []
    for item in usable:
        try:
            vec = json.loads(item.get("vector") or "[]")
        except json.JSONDecodeError:
            vec = []
        score = cosine(qvec, vec)
        scored.append((score, _hit_from_row(item, score)))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[: max(1, min(limit, 50))]]


def _lance_search(query: str, *, namespace: str | None, limit: int) -> list[dict[str, Any]] | None:
    table = _lance_table()
    if table is None:
        return None
    try:
        qvec, _qmeta = embed_document(query)
        q = table.search(qvec).limit(max(1, min(limit, 50)))
        if namespace:
            ns = namespace.strip().lower().replace("'", "")
            q = q.where(f"namespace = '{ns}'")
        rows = q.to_list()
    except Exception:
        return None
    hits: list[dict[str, Any]] = []
    for row in rows:
        distance = row.get("_distance")
        try:
            score = 1.0 / (1.0 + float(distance)) if distance is not None else 0.0
        except (TypeError, ValueError):
            score = 0.0
        hits.append(_hit_from_row(row, score))
    return hits


def _search_budget_ms(namespace: str | None) -> int:
    ns = (namespace or "").strip().lower()
    if namespace is None or ns == "corpus":
        return CORPUS_SEARCH_BUDGET_MS
    return SQL_LOOKUP_BUDGET_MS


def _stored_dims(namespace: str | None) -> set[int]:
    with db.connect() as conn:
        if namespace:
            rows = conn.execute(
                "SELECT embed_dim, vector FROM memory_docs WHERE namespace = ?",
                (namespace.strip().lower(),),
            ).fetchall()
        else:
            rows = conn.execute("SELECT embed_dim, vector FROM memory_docs").fetchall()
    dims: set[int] = set()
    for row in rows:
        dim = _row_dim(dict(row))
        if dim is not None:
            dims.add(dim)
    return dims


def search(
    query: str,
    *,
    namespace: str | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    _ensure_schema()
    mixed = len(_stored_dims(namespace)) > 1
    # SQLite stays the source of truth while Lance is empty or the WAL is behind.
    if not mixed and not _lance_wal_pending():
        with latency_budget("lance_search", LANCE_SEARCH_BUDGET_MS):
            lance_hits = _lance_search(query, namespace=namespace, limit=limit)
        if lance_hits:
            return lance_hits
    with latency_budget("sql_lookup", _search_budget_ms(namespace)):
        return _sqlite_search(query, namespace=namespace, limit=limit)


def forget(
    *,
    namespace: str | None = None,
    key: str | None = None,
    doc_id: str | None = None,
    wipe_namespace: bool = False,
) -> dict[str, Any]:
    _ensure_schema()
    if not doc_id and not (wipe_namespace and namespace) and not (namespace and key):
        return {"ok": False, "error": "Specify doc_id, or namespace+key, or wipe_namespace"}
    deleted = 0
    with db.connect() as conn:
        if doc_id:
            rows = conn.execute(
                "SELECT id, namespace, key FROM memory_docs WHERE id = ?",
                (doc_id,),
            ).fetchall()
            cur = conn.execute("DELETE FROM memory_docs WHERE id = ?", (doc_id,))
        elif wipe_namespace and namespace:
            ns = namespace.strip().lower()
            rows = conn.execute(
                "SELECT id, namespace, key FROM memory_docs WHERE namespace = ?",
                (ns,),
            ).fetchall()
            cur = conn.execute("DELETE FROM memory_docs WHERE namespace = ?", (ns,))
        else:
            ns = (namespace or "").strip().lower()
            rows = conn.execute(
                "SELECT id, namespace, key FROM memory_docs WHERE namespace = ? AND key = ?",
                (ns, key),
            ).fetchall()
            cur = conn.execute(
                "DELETE FROM memory_docs WHERE namespace = ? AND key = ?",
                (ns, key),
            )
        deleted = cur.rowcount or 0
        for row in rows:
            _insert_wal(
                conn,
                operation="delete",
                namespace=str(row["namespace"]),
                doc_id=str(row["id"]),
                payload={"id": str(row["id"]), "namespace": str(row["namespace"]), "key": row["key"]},
            )
    _schedule_lance_drain()
    return {"ok": True, "deleted": deleted}


def reembed_namespace(namespace: str) -> dict[str, Any]:
    """Rewrite every vector in one namespace with the current embedder.

    Script and admin entry only — not registered as a chat tool. The mixed-dimension
    guard on ``upsert`` stays in place; this is the explicit rewrite path, so it
    updates the whole namespace in one transaction.
    """
    _ensure_schema()
    ns = (namespace or "").strip().lower()
    if ns not in NAMESPACES:
        raise ValueError(f"unknown namespace: {namespace}")
    updated = 0
    model_id = ""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, namespace, key, text, meta FROM memory_docs WHERE namespace = ?",
            (ns,),
        ).fetchall()
        now = db.utc_now()
        for row in rows:
            text = row["text"] or ""
            vector, auto = embed_document(text)
            model_id = str(auto["model_id"])
            meta: dict[str, Any] = {}
            try:
                parsed = json.loads(row["meta"] or "{}")
                if isinstance(parsed, dict):
                    meta = parsed
            except json.JSONDecodeError:
                meta = {}
            meta["embed_model_id"] = auto["model_id"]
            meta["embed_dim"] = auto["dim"]
            meta["embed_provider"] = auto["provider"]
            doc_id = str(row["id"])
            conn.execute(
                """
                UPDATE memory_docs
                SET text = ?, meta = ?, vector = ?, updated_at = ?,
                    embed_model_id = ?, embed_dim = ?, embed_provider = ?
                WHERE id = ?
                """,
                (
                    text,
                    json.dumps(meta),
                    json.dumps(vector),
                    now,
                    auto["model_id"],
                    int(auto["dim"]),
                    auto["provider"],
                    doc_id,
                ),
            )
            _insert_wal(
                conn,
                operation="upsert",
                namespace=ns,
                doc_id=doc_id,
                payload={
                    "id": doc_id,
                    "namespace": ns,
                    "key": row["key"],
                    "text": text,
                    "vector": vector,
                    "meta": meta,
                },
            )
            updated += 1
    _schedule_lance_drain()
    return {"namespace": ns, "updated": updated, "model_id": model_id}


def get_summary(*, limit: int = 40) -> dict[str, Any]:
    _ensure_schema()
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT namespace, key, text, updated_at FROM memory_docs
            ORDER BY updated_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        counts = conn.execute(
            "SELECT namespace, COUNT(*) AS n FROM memory_docs GROUP BY namespace"
        ).fetchall()
    return {
        "engine": "lancedb+sqlite" if _get_lance() is not None else "sqlite",
        "counts": {row["namespace"]: row["n"] for row in counts},
        "recent": [dict(row) for row in rows],
    }
