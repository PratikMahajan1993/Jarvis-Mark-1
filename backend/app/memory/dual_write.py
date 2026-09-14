"""Best-effort dual-write into local memory while Honcho remains live."""

from __future__ import annotations

from typing import Any

from .store import upsert


def mirror_fact(
    text: str,
    *,
    namespace: str = "profile",
    key: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mirror a durable fact/preference into the local store."""
    body = (text or "").strip()
    if not body:
        return {"ok": False, "error": "empty"}
    return {
        "ok": True,
        **upsert(
            namespace=namespace,
            key=key or f"fact-{abs(hash(body)) % 10_000_000}",
            text=body,
            meta={"source": "dual_write", **(meta or {})},
        ),
    }
