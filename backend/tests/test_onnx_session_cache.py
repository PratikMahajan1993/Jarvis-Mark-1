"""ONNX InferenceSession cache. real_embeddings_enabled stays off by default."""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings, settings
from app.memory import embeddings as emb
from app.memory.embeddings import HASH_EMBEDDING_MODEL, resolve_embedder


def test_real_embeddings_flag_stays_off():
    assert Settings.model_fields["real_embeddings_enabled"].default is False


def test_successful_session_is_cached_and_tokenizer_gap_still_uses_hash(tmp_path, monkeypatch):
    model = tmp_path / "bge-small-en-v1.5.onnx"
    model.write_bytes(b"not-a-real-model")
    calls: list[str] = []

    class _Input:
        name = "input_ids"

    class FakeSession:
        def get_inputs(self):
            return [_Input()]

    def inference_session(path, providers=None):
        calls.append(str(path))
        return FakeSession()

    module = types.ModuleType("onnxruntime")
    module.InferenceSession = inference_session
    monkeypatch.setitem(sys.modules, "onnxruntime", module)
    emb._session_cache.clear()

    previous = settings.real_embeddings_enabled
    settings.real_embeddings_enabled = True
    try:
        first = resolve_embedder(model_path=model)
        second = resolve_embedder(model_path=model)
    finally:
        settings.real_embeddings_enabled = previous
        emb._session_cache.clear()

    assert first.model_name == HASH_EMBEDDING_MODEL
    assert second.model_name == HASH_EMBEDDING_MODEL
    assert first.fallback_error is not None
    assert "tokenizer not wired" in first.fallback_error
    assert second.fallback_error == first.fallback_error
    assert calls == [str(model)]


def test_failed_session_is_not_cached(tmp_path, monkeypatch):
    model = tmp_path / "broken.onnx"
    model.write_bytes(b"broken")
    calls: list[str] = []

    def inference_session(path, providers=None):
        calls.append(str(path))
        raise RuntimeError("bad onnx")

    module = types.ModuleType("onnxruntime")
    module.InferenceSession = inference_session
    monkeypatch.setitem(sys.modules, "onnxruntime", module)
    emb._session_cache.clear()

    previous = settings.real_embeddings_enabled
    settings.real_embeddings_enabled = True
    try:
        first = resolve_embedder(model_path=model)
        second = resolve_embedder(model_path=model)
    finally:
        settings.real_embeddings_enabled = previous
        emb._session_cache.clear()

    assert first.model_name == HASH_EMBEDDING_MODEL
    assert "cannot load ONNX model" in (first.fallback_error or "")
    assert second.fallback_error == first.fallback_error
    assert len(calls) == 2
