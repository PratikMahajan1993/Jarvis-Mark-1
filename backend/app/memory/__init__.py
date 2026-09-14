"""Local dual-write memory + RAG (foundation Phase 1).

Engine: LanceDB when importable; otherwise SQLite vector blobs.
Embeddings: local deterministic hash vectors (no model download) — upgrade later.
"""

from __future__ import annotations

from .store import (
    NAMESPACES,
    forget,
    get_summary,
    search,
    upsert,
)
from .dual_write import mirror_fact
from .ingest import ingest_text, reindex_recent_mail

__all__ = [
    "NAMESPACES",
    "upsert",
    "search",
    "forget",
    "get_summary",
    "mirror_fact",
    "ingest_text",
    "reindex_recent_mail",
]
