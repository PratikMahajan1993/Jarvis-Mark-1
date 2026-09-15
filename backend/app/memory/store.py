"""Structured + vector memory store (LanceDB preferred, SQLite fallback)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .. import db
from ..config import settings
from .embeddings import cosine, embed_text

NAMESPACES = ("profile", "people", "jobs", "session", "corpus")

_lance = None
_lance_tried = False


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
                UNIQUE(namespace, key)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_ns ON memory_docs(namespace)"
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


def _lance_upsert(doc_id: str, namespace: str, key: str, text: str, vector: list[float], meta: dict) -> None:
    ldb = _get_lance()
    if ldb is None:
        return
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
        except AttributeError:
            names = set(ldb.table_names())  # Fallback for very old LanceDB
        except Exception:
            names = set()
        if table_name not in names:
            ldb.create_table(table_name, [row], mode="overwrite")
        else:
            table = ldb.open_table(table_name)
            try:
                table.delete(f"id = '{doc_id}'")
            except Exception:
                pass
            table.add([row])
    except Exception:
        # Lance optional — SQLite remains source of truth
        pass


def upsert(
    *,
    namespace: str,
    key: str,
    text: str,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ensure_schema()
    ns = (namespace or "corpus").strip().lower()
    if ns not in NAMESPACES:
        ns = "corpus"
    key = (key or "").strip() or f"auto-{uuid.uuid4().hex[:10]}"
    text = (text or "").strip()
    meta = dict(meta or {})
    vector = embed_text(text)
    now = db.utc_now()
    doc_id = f"{ns}:{key}"
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO memory_docs (id, namespace, key, text, meta, vector, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(namespace, key) DO UPDATE SET
                text = excluded.text,
                meta = excluded.meta,
                vector = excluded.vector,
                updated_at = excluded.updated_at
            """,
            (doc_id, ns, key, text, json.dumps(meta), json.dumps(vector), now, now),
        )
    _lance_upsert(doc_id, ns, key, text, vector, meta)
    return {"id": doc_id, "namespace": ns, "key": key, "text": text, "meta": meta}


def search(
    query: str,
    *,
    namespace: str | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    _ensure_schema()
    qvec = embed_text(query)
    with db.connect() as conn:
        if namespace:
            rows = conn.execute(
                "SELECT * FROM memory_docs WHERE namespace = ?",
                (namespace.strip().lower(),),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM memory_docs").fetchall()
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        item = dict(row)
        try:
            vec = json.loads(item.get("vector") or "[]")
        except json.JSONDecodeError:
            vec = []
        score = cosine(qvec, vec)
        meta = {}
        try:
            meta = json.loads(item.get("meta") or "{}")
        except json.JSONDecodeError:
            meta = {}
        scored.append(
            (
                score,
                {
                    "id": item["id"],
                    "namespace": item["namespace"],
                    "key": item["key"],
                    "text": item["text"],
                    "meta": meta,
                    "score": round(score, 4),
                    "updated_at": item.get("updated_at"),
                },
            )
        )
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[: max(1, min(limit, 50))]]


def forget(
    *,
    namespace: str | None = None,
    key: str | None = None,
    doc_id: str | None = None,
    wipe_namespace: bool = False,
) -> dict[str, Any]:
    _ensure_schema()
    deleted = 0
    with db.connect() as conn:
        if doc_id:
            cur = conn.execute("DELETE FROM memory_docs WHERE id = ?", (doc_id,))
            deleted = cur.rowcount or 0
        elif wipe_namespace and namespace:
            cur = conn.execute(
                "DELETE FROM memory_docs WHERE namespace = ?",
                (namespace.strip().lower(),),
            )
            deleted = cur.rowcount or 0
        elif namespace and key:
            cur = conn.execute(
                "DELETE FROM memory_docs WHERE namespace = ? AND key = ?",
                (namespace.strip().lower(), key),
            )
            deleted = cur.rowcount or 0
        else:
            return {"ok": False, "error": "Specify doc_id, or namespace+key, or wipe_namespace"}
    return {"ok": True, "deleted": deleted}


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
