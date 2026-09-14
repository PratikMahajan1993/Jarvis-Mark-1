"""Local embedding helpers — deterministic hash vectors (offline, no model download)."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable

DIM = 384
_TOKEN = re.compile(r"[a-z0-9]{2,}", re.I)


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
