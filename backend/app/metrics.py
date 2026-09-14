"""Mission audit log + latency metrics (foundation Phase 0)."""

from __future__ import annotations

import statistics
import threading
import uuid
from collections import deque
from typing import Any

from . import db

_lock = threading.Lock()
_latency_samples: deque[dict[str, Any]] = deque(maxlen=200)


def new_mission_id() -> str:
    return f"m-{uuid.uuid4().hex[:12]}"


def record_mission_step(
    *,
    session_id: str,
    mission_id: str,
    step: int,
    role: str,
    detail: str = "",
    latency_ms: int | None = None,
    status: str = "ok",
    tokens: int | None = None,
    cost: float | None = None,
) -> None:
    """Persist one mission step (prompt / tool / result / hermes)."""
    db.add_mission_step(
        session_id=session_id,
        mission_id=mission_id,
        step=step,
        role=role,
        detail=(detail or "")[:2000],
        latency_ms=latency_ms,
        status=status,
        tokens=tokens,
        cost=cost,
    )
    # Mirror into classic audit only for hermes/prompt outcomes (avoid triple-logging tools)
    if role in {"hermes", "prompt"} and status != "ok":
        label = f"mission:{mission_id}:{role}"
        suffix = f" [{latency_ms}ms]" if latency_ms is not None else ""
        db.add_audit(session_id, label, f"step={step} {(detail or '')[:350]}{suffix}", status)


def record_hermes_latency(
    *,
    session_id: str,
    transport: str,
    casual: bool,
    latency_ms: int,
    ok: bool = True,
) -> None:
    sample = {
        "session_id": session_id,
        "transport": transport,
        "casual": casual,
        "latency_ms": int(latency_ms),
        "ok": ok,
        "at": db.utc_now(),
    }
    with _lock:
        _latency_samples.append(sample)


def metrics_snapshot() -> dict[str, Any]:
    with _lock:
        samples = list(_latency_samples)
    casual = [s["latency_ms"] for s in samples if s.get("casual") and s.get("ok")]
    all_ok = [s["latency_ms"] for s in samples if s.get("ok")]

    def _stats(values: list[int]) -> dict[str, Any]:
        if not values:
            return {"count": 0, "p50_ms": None, "p95_ms": None, "mean_ms": None}
        ordered = sorted(values)
        p50 = ordered[len(ordered) // 2]
        p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
        return {
            "count": len(values),
            "p50_ms": p50,
            "p95_ms": p95,
            "mean_ms": int(statistics.mean(values)),
        }

    recent_missions = db.list_mission_steps(limit=40)
    return {
        "hermes_latency": {
            "casual": _stats(casual),
            "all": _stats(all_ok),
            "recent": samples[-20:],
        },
        "mission_steps_recent": recent_missions,
        "targets": {
            "casual_warm_ms": 5000,
            "simple_tool_ms": 15000,
        },
    }
