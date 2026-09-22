"""Hybrid RAG store (FTS5 + hash vectors) — ingest off the chat turn path."""

from .ingest import ingest_text
from .search import hybrid_search

__all__ = ["ingest_text", "hybrid_search"]
