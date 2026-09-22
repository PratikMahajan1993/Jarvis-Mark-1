"""Write rag_documents / rag_chunks with hash-v1 vectors (no chat-turn side effects)."""

from __future__ import annotations

import hashlib
import re
import struct
import uuid
from typing import Any

from .. import db
from ..memory.embeddings import DIM, embed_text, tokenize

EMBEDDING_MODEL = "hash-v1"

_HEADING = re.compile(r"^#{1,6}\s+\S", re.M)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pack_vector(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def split_sections(text: str) -> list[tuple[str, str]]:
    """Split on blank lines and markdown-style headings."""
    raw = (text or "").strip()
    if not raw:
        return []

    parts: list[str] = []
    start = 0
    for match in _HEADING.finditer(raw):
        if match.start() > start:
            parts.append(raw[start : match.start()])
        start = match.start()
    if start < len(raw):
        parts.append(raw[start:])

    sections: list[tuple[str, str]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        blocks = re.split(r"\n\s*\n+", part)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            title = ""
            lines = block.splitlines()
            if lines and _HEADING.match(lines[0]):
                title = lines[0].lstrip("#").strip()
                body = "\n".join(lines[1:]).strip() or lines[0]
            else:
                body = block
            sections.append((title, body))
    return sections


def ingest_text(
    text: str,
    namespace: str,
    *,
    uri: str | None = None,
    doc_kind: str = "text",
    authored_by: str = "external",
) -> dict[str, Any]:
    """Persist chunked text; idempotent on (sha256, namespace)."""
    ns = (namespace or "").strip() or "corpus"
    body = text or ""
    doc_sha = _sha256_text(body)
    doc_uri = uri or f"{ns}:{doc_sha[:16]}"

    sections = split_sections(body)
    if not sections:
        sections = [("", body.strip())] if body.strip() else []

    now = db.utc_now()
    with db.connect() as conn:
        existing = conn.execute(
            "SELECT id FROM rag_documents WHERE sha256 = ? AND namespace = ?",
            (doc_sha, ns),
        ).fetchone()
        if existing:
            n_chunks = conn.execute(
                "SELECT COUNT(*) AS n FROM rag_chunks WHERE document_id = ?",
                (existing["id"],),
            ).fetchone()["n"]
            return {
                "document_id": existing["id"],
                "chunks_written": 0,
                "chunk_count": int(n_chunks),
                "skipped": True,
            }

        doc_id = uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO rag_documents
            (id, uri, sha256, doc_kind, namespace, authored_by, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (doc_id, doc_uri, doc_sha, doc_kind, ns, authored_by, now),
        )

        written = 0
        for ordinal, (section, chunk_text) in enumerate(sections):
            if not chunk_text.strip():
                continue
            vec = embed_text(chunk_text)
            chunk_id = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO rag_chunks
                (id, document_id, ordinal, section, text, text_sha256, token_count,
                 embedding_model, embedding_dim, vector, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    doc_id,
                    ordinal,
                    section,
                    chunk_text,
                    _sha256_text(chunk_text),
                    len(tokenize(chunk_text)),
                    EMBEDDING_MODEL,
                    DIM,
                    pack_vector(vec),
                    now,
                ),
            )
            row = conn.execute(
                "SELECT rowid FROM rag_chunks WHERE id = ?",
                (chunk_id,),
            ).fetchone()
            if row:
                conn.execute(
                    "INSERT INTO rag_fts(rowid, text) VALUES (?, ?)",
                    (int(row["rowid"]), chunk_text),
                )
            written += 1

        conn.execute(
            """
            UPDATE rag_index_state
            SET pending = pending + ?,
                embedded = embedded + ?,
                model = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (written, written, EMBEDDING_MODEL, now),
        )

    return {
        "document_id": doc_id,
        "chunks_written": written,
        "chunk_count": written,
        "skipped": False,
    }
