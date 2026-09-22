"""Local embedding helpers — hash-v1 fallback and optional ONNX slot (no auto-download)."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DIM = 384
HASH_EMBEDDING_MODEL = "hash-v1"
REAL_EMBEDDING_MODEL = "bge-small-en-v1.5"
ONNX_MODEL_FILENAME = "bge-small-en-v1.5.onnx"

_TOKEN = re.compile(r"[a-z0-9]{2,}", re.I)

# Tests may monkeypatch this path; production uses data_dir/models/<ONNX_MODEL_FILENAME>.
_onnx_model_path_override: Path | None = None


def onnx_model_path() -> Path:
    if _onnx_model_path_override is not None:
        return _onnx_model_path_override
    from ..config import settings

    return settings.data_dir / "models" / ONNX_MODEL_FILENAME


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


def embed_text(text: str, dim: int = DIM) -> list[float]:
    """Bag-of-words hashing trick → L2-normalized float vector."""
    vec = [0.0] * dim
    tokens = tokenize(text)
    if not tokens:
        return vec
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = 1.0 + (digest[5] / 255.0)
        vec[idx] += sign * weight
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: Iterable[float], b: Iterable[float]) -> float:
    aa = list(a)
    bb = list(b)
    if not aa or not bb or len(aa) != len(bb):
        return 0.0
    return sum(x * y for x, y in zip(aa, bb))


@dataclass(frozen=True)
class ResolvedEmbedder:
    model_name: str
    embed: Callable[[str], list[float]]
    fallback_error: str | None = None


def _try_open_onnx_embedder(path: Path) -> tuple[Callable[[str], list[float]] | None, str | None]:
    try:
        import onnxruntime as ort
    except ImportError:
        return None, "onnxruntime not installed; keeping hash-v1"

    try:
        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    except Exception as exc:
        return None, f"cannot load ONNX model at {path}: {exc}"

    input_meta = {item.name for item in session.get_inputs()}
    if "input_ids" in input_meta:
        return (
            None,
            f"real embeddings enabled but tokenizer not wired for ONNX model at {path}",
        )
    return None, f"ONNX model at {path} is not supported by the hash fallback slot yet"


def resolve_embedder(*, model_path: Path | None = None) -> ResolvedEmbedder:
    """Pick hash-v1 or a local ONNX embedder; never raises on missing model file."""
    from ..config import settings

    if not settings.real_embeddings_enabled:
        return ResolvedEmbedder(HASH_EMBEDDING_MODEL, embed_text)

    path = model_path if model_path is not None else onnx_model_path()
    if not path.is_file():
        return ResolvedEmbedder(
            HASH_EMBEDDING_MODEL,
            embed_text,
            fallback_error=f"real embeddings enabled but model file missing: {path}",
        )

    embed_fn, err = _try_open_onnx_embedder(path)
    if embed_fn is not None:
        return ResolvedEmbedder(REAL_EMBEDDING_MODEL, embed_fn)
    return ResolvedEmbedder(HASH_EMBEDDING_MODEL, embed_text, fallback_error=err)
