"""Hybrid retrieval: FTS5 + hash-vector cosine, fused with RRF."""

from __future__ import annotations

import re
import struct

from .. import db
from ..memory.embeddings import cosine, embed_text, tokenize

RRF_K = 60
_JARVIS_FILTER = "d.authored_by != 'jarvis'"
_FTS_TOKEN = re.compile(r"[a-z0-9]{2,}", re.I)


def unpack_vector(blob: bytes | None, dim: int) -> list[float]:
    if not blob:
        return []
    n = len(blob) // 4
    if n != dim:
        return []
    return list(struct.unpack(f"{n}f", blob))


def _fts_query(query: str) -> str:
    tokens = _FTS_TOKEN.findall((query or "").lower())
    if not tokens:
        return ""
    # OR so any query token can match; quote for literal part codes.
    return " OR ".join(f'"{tok}"' for tok in tokens)


def _fts_ranked(conn, fts_q: str, limit: int) -> list[str]:
    if not fts_q:
        return []
    rows = conn.execute(
        f"""
        SELECT c.id
        FROM rag_fts
        JOIN rag_chunks c ON c.rowid = rag_fts.rowid
        JOIN rag_documents d ON d.id = c.document_id
        WHERE rag_fts MATCH ? AND {_JARVIS_FILTER}
        ORDER BY bm25(rag_fts)
        LIMIT ?
        """,
        (fts_q, limit),
    ).fetchall()
    return [row["id"] for row in rows]


def _vector_ranked(conn, query: str, limit: int) -> list[str]:
    qvec = embed_text(query)
    rows = conn.execute(
        f"""
        SELECT c.id, c.embedding_dim, c.vector
        FROM rag_chunks c
        JOIN rag_documents d ON d.id = c.document_id
        WHERE c.vector IS NOT NULL AND {_JARVIS_FILTER}
        """
    ).fetchall()
    scored: list[tuple[float, str]] = []
    for row in rows:
        vec = unpack_vector(row["vector"], int(row["embedding_dim"]))
        if not vec:
            continue
        scored.append((cosine(qvec, vec), row["id"]))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [cid for _, cid in scored[:limit]]


def _reciprocal_rank_fusion(*ranked_lists: list[str], limit: int = 8) -> list[str]:
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank)
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [cid for cid, _ in ordered[:limit]]


def hybrid_search(query: str, limit: int = 8) -> list[str]:
    """Return chunk ids; excludes jarvis-authored documents."""
    lim = max(1, int(limit))
    fetch = max(lim * 4, 32)
    fts_q = _fts_query(query)

    with db.connect() as conn:
        fts_ids = _fts_ranked(conn, fts_q, fetch)
        vec_ids = _vector_ranked(conn, query, fetch)

    if not fts_ids and not vec_ids:
        # Fallback: token overlap scan for very short queries FTS may skip.
        qtoks = set(tokenize(query))
        if not qtoks:
            return []
        with db.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT c.id, c.text
                FROM rag_chunks c
                JOIN rag_documents d ON d.id = c.document_id
                WHERE {_JARVIS_FILTER}
                """
            ).fetchall()
        hits = [
            row["id"]
            for row in rows
            if qtoks.intersection(tokenize(row["text"]))
        ]
        return hits[:lim]

    return _reciprocal_rank_fusion(fts_ids, vec_ids, limit=lim)
