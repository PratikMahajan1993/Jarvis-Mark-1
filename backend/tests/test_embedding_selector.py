from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.memory import embeddings as emb
from app.memory.embeddings import HASH_EMBEDDING_MODEL, embed_text, resolve_embedder
from app.rag.ingest import ingest_text

_HASH_FIXTURE = (
    "Bracket drawing SPL4092BREV7\n\nDimension table for WIDGET-9912-Z tolerance H7."
)
_HASH_SNAPSHOT = embed_text(_HASH_FIXTURE)


def setup_module(_module=None):
    db.init_db()


def test_hash_embed_text_unchanged():
    assert embed_text(_HASH_FIXTURE) == _HASH_SNAPSHOT
    assert embed_text("") == [0.0] * emb.DIM


def test_resolve_embedder_flag_off_uses_hash():
    prev = settings.real_embeddings_enabled
    settings.real_embeddings_enabled = False
    try:
        resolved = resolve_embedder(model_path=Path("/nonexistent/model.onnx"))
        assert resolved.model_name == HASH_EMBEDDING_MODEL
        assert resolved.fallback_error is None
        assert resolved.embed("hello") == embed_text("hello")
    finally:
        settings.real_embeddings_enabled = prev


def test_ingest_flag_on_missing_model_stores_hash_and_last_error(tmp_path, monkeypatch):
    missing = tmp_path / "models" / "bge-small-en-v1.5.onnx"
    assert not missing.is_file()

    prev_flag = settings.real_embeddings_enabled
    prev_data = settings.data_dir
    prev_override = emb._onnx_model_path_override
    settings.real_embeddings_enabled = True
    settings.data_dir = tmp_path
    emb._onnx_model_path_override = missing
    db.init_db()

    try:
        body = f"Selector ingest probe {missing.name}\n\nRare token ZZTOP-881."
        result = ingest_text(body, namespace="selector-test")
        assert result["skipped"] is False
        assert result["chunks_written"] >= 1

        with db.connect() as conn:
            models = {
                row["embedding_model"]
                for row in conn.execute(
                    "SELECT embedding_model FROM rag_chunks WHERE document_id = ?",
                    (result["document_id"],),
                ).fetchall()
            }
            state = conn.execute(
                "SELECT model, last_error FROM rag_index_state WHERE id = 1"
            ).fetchone()

        assert models == {HASH_EMBEDDING_MODEL}
        assert state["model"] == HASH_EMBEDDING_MODEL
        assert str(missing) in (state["last_error"] or "")
    finally:
        settings.real_embeddings_enabled = prev_flag
        settings.data_dir = prev_data
        emb._onnx_model_path_override = prev_override
        db.init_db()
