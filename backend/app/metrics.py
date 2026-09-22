"""Mission audit log + latency metrics (foundation Phase 0)."""

from __future__ import annotations

import sqlite3
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
    if role in {"tool", "result", "hermes", "prompt"}:
        try:
            from .live_log import record as live_record

            live_record(
                source="api",
                kind="tool",
                session_id=session_id,
                latency_ms=latency_ms,
                fields={
                    "name": detail.split()[0][:80] if detail else role,
                    "role": role,
                    "detail": (detail or "")[:400],
                    "status": status,
                    "mission_id": mission_id,
                    "step": step,
                },
            )
        except Exception:
            pass
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
    try:
        from .live_log import record as live_record

        live_record(
            source="api",
            kind="hermes_latency",
            session_id=session_id,
            latency_ms=int(latency_ms),
            fields={
                "transport": transport,
                "casual": casual,
                "ok": ok,
            },
        )
    except Exception:
        pass


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def load_durable_metrics(conn: sqlite3.Connection) -> dict[str, Any]:
    """SQLite-backed metric series (survives process restart)."""
    out: dict[str, Any] = {}

    if _table_exists(conn, "turns"):
        rows = conn.execute(
            "SELECT stage, COUNT(*) AS n FROM turns GROUP BY stage"
        ).fetchall()
        out["stage_counts"] = {str(row["stage"]): int(row["n"]) for row in rows}
    else:
        out["stage_counts"] = {}

    if _table_exists(conn, "quote_proofs"):
        total_row = conn.execute("SELECT COUNT(*) AS n FROM quote_proofs").fetchone()
        total = int(total_row["n"]) if total_row else 0
        if total == 0:
            out["proof_block_rate"] = {"ask": True, "reason": "no proof rows"}
        else:
            blocked_row = conn.execute(
                """
                SELECT COUNT(*) AS n FROM quote_proofs
                WHERE blockers > 0 OR LOWER(verdict) = 'block'
                """
            ).fetchone()
            blocked = int(blocked_row["n"]) if blocked_row else 0
            out["proof_block_rate"] = blocked / total
    else:
        out["proof_block_rate"] = {"ask": True, "reason": "no proof rows"}

    if not _table_exists(conn, "external_effects"):
        out["duplicate_external_effect_count"] = 0
    else:
        total_row = conn.execute("SELECT COUNT(*) AS n FROM external_effects").fetchone()
        total = int(total_row["n"]) if total_row else 0
        if total == 0:
            out["duplicate_external_effect_count"] = 0
        else:
            dup_row = conn.execute(
                """
                SELECT COALESCE(SUM(c - 1), 0) AS n FROM (
                    SELECT COUNT(*) AS c
                    FROM external_effects
                    GROUP BY provider, request_hash
                    HAVING COUNT(*) > 1
                )
                """
            ).fetchone()
            out["duplicate_external_effect_count"] = int(dup_row["n"] or 0)

    if _table_exists(conn, "rag_index_state"):
        row = conn.execute(
            "SELECT pending, embedded FROM rag_index_state WHERE id = 1"
        ).fetchone()
        if row is None:
            out["index_lag"] = {"ask": True}
        else:
            pending = int(row["pending"])
            embedded = int(row["embedded"])
            out["index_lag"] = {
                "pending": pending,
                "embedded": embedded,
                "lag": max(0, pending - embedded),
            }
    else:
        out["index_lag"] = {"ask": True}

    return out


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
    with db.connect() as conn:
        durable = load_durable_metrics(conn)
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
        **durable,
    }
