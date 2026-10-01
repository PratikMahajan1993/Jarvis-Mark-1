"""One live quote pipeline — single read/write for revision pipeline_state."""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from . import db

PIPELINE_STATES = frozenset(
    {
        "intake",
        "on_desk",
        "blocked",
        "handoff_ready",
        "live",
        "parked",
        "detour",
        "release_hold",
        "sending",
        "sent",
        "failed",
        "unknown",
    }
)
TERMINAL_STATES = frozenset({"sent", "failed", "unknown"})
LIVE_BLOCKING_STATES = frozenset({"live", "sending", "detour", "release_hold"})


def _revision_id(session_id: str, revision_id: str | None) -> str:
    if revision_id and revision_id.strip():
        return revision_id.strip()
    from .masterdata.quotes import revision_id_from_session

    return revision_id_from_session(session_id)


def _live_revision_for_session(conn: sqlite3.Connection, session_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT qr.id
        FROM quote_revisions qr
        JOIN quotes q ON q.id = qr.quote_id
        WHERE q.conversation_id = ?
          AND qr.pipeline_state IN ('live', 'sending', 'detour', 'release_hold')
        ORDER BY qr.revision DESC
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()
    return str(row["id"]) if row else None


def _snapshot_rates(conn: sqlite3.Connection, revision_id: str) -> str:
    rows = conn.execute(
        """
        SELECT id, kind, rate_source_kind, rate_source_id, rate_minor, machine_id
        FROM quote_lines
        WHERE quote_revision_id = ?
        ORDER BY seq
        """,
        (revision_id,),
    ).fetchall()
    payload = {
        "lines": [
            {
                "id": r["id"],
                "kind": r["kind"],
                "rate_source_kind": r["rate_source_kind"],
                "rate_source_id": r["rate_source_id"],
                "rate_minor": r["rate_minor"],
                "machine_id": r["machine_id"],
            }
            for r in rows
        ]
    }
    return json.dumps(payload)


def read_quote_pipeline_state(session_id: str, revision_id: str | None = None) -> dict[str, Any]:
    """Single source of truth: quote_revisions.pipeline_state for the session revision."""
    rid = _revision_id(session_id, revision_id)
    if not rid:
        return {"ok": True, "state": "on_desk", "revision_id": "", "pipeline_step": ""}
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT qr.pipeline_state, qr.pipeline_step, qr.detour_return_state, qr.rate_snapshot_json
            FROM quote_revisions qr
            WHERE qr.id = ?
            """,
            (rid,),
        ).fetchone()
    if not row:
        return {"ok": False, "error": f"revision {rid} not found", "revision_id": rid}
    state = str(row["pipeline_state"] or "on_desk").strip() or "on_desk"
    return {
        "ok": True,
        "state": state,
        "revision_id": rid,
        "pipeline_step": str(row["pipeline_step"] or ""),
        "detour_return_state": str(row["detour_return_state"] or ""),
        "rate_snapshot_json": str(row["rate_snapshot_json"] or ""),
        "handoff_ready": state == "handoff_ready",
    }


def write_quote_pipeline_state(
    session_id: str,
    revision_id: str,
    state: str,
    *,
    pipeline_step: str | None = None,
    detour_return_state: str | None = None,
    freeze_rates: bool = False,
) -> dict[str, Any]:
    """Validate transitions and persist pipeline_state on the revision."""
    norm = (state or "").strip().lower()
    if norm not in PIPELINE_STATES:
        return {"ok": False, "error": f"invalid pipeline state {state!r}"}
    rid = _revision_id(session_id, revision_id)
    if not rid:
        return {"ok": False, "error": "no quote revision for session"}

    with db.connect() as conn:
        row = conn.execute(
            "SELECT pipeline_state, rate_snapshot_json FROM quote_revisions WHERE id = ?",
            (rid,),
        ).fetchone()
        if not row:
            return {"ok": False, "error": f"revision {rid} not found"}

        if norm == "live":
            live_id = _live_revision_for_session(conn, session_id)
            if live_id and live_id != rid:
                return {
                    "ok": False,
                    "error": "Another quote is live — park it or finish send before going live.",
                    "live_revision_id": live_id,
                }

        rate_json = row["rate_snapshot_json"]
        if freeze_rates or norm in {"handoff_ready", "live", "parked"}:
            if not rate_json:
                rate_json = _snapshot_rates(conn, rid)

        step_val = pipeline_step
        if step_val is None:
            step_row = conn.execute("SELECT pipeline_step FROM quote_revisions WHERE id = ?", (rid,)).fetchone()
            step_val = str(step_row["pipeline_step"] or "") if step_row else ""

        detour_val = detour_return_state
        if detour_val is None:
            detour_row = conn.execute(
                "SELECT detour_return_state FROM quote_revisions WHERE id = ?",
                (rid,),
            ).fetchone()
            detour_val = str(detour_row["detour_return_state"] or "") if detour_row else ""

        conn.execute(
            """
            UPDATE quote_revisions
            SET pipeline_state = ?,
                pipeline_step = ?,
                detour_return_state = ?,
                rate_snapshot_json = ?
            WHERE id = ?
            """,
            (norm, step_val or "", detour_val or "", rate_json or "", rid),
        )
        conn.execute(
            """
            INSERT INTO quote_events (id, quote_revision_id, event, detail, external_effect_id, created_at)
            VALUES (?, ?, ?, ?, NULL, ?)
            """,
            (
                f"qev_{uuid.uuid4().hex[:12]}",
                rid,
                f"pipeline_{norm}",
                json.dumps({"session_id": session_id}),
                db.utc_now(),
            ),
        )

    if pipeline_step:
        db.add_memory(session_id, "quote_step", pipeline_step)
    return read_quote_pipeline_state(session_id, rid)


def pipeline_blocks_send(session_id: str) -> tuple[bool, str]:
    """True when quote_send must not queue (master-data detour)."""
    snap = read_quote_pipeline_state(session_id)
    if not snap.get("ok"):
        return False, ""
    if snap.get("state") == "detour":
        return True, "Quote is on master-data detour — finish or cancel before send."
    return False, ""


def mark_handoff_ready(session_id: str, revision_id: str | None = None) -> dict[str, Any]:
    return write_quote_pipeline_state(
        session_id,
        _revision_id(session_id, revision_id),
        "handoff_ready",
        pipeline_step="handoff_ready",
        freeze_rates=True,
    )


def activate_live_quote(session_id: str, revision_id: str | None = None) -> dict[str, Any]:
    rid = _revision_id(session_id, revision_id)
    snap = read_quote_pipeline_state(session_id, rid)
    if snap.get("state") not in {"handoff_ready", "parked"}:
        return {
            "ok": False,
            "error": f"Cannot go live from state {snap.get('state')!r} (need handoff_ready or parked)",
        }
    return write_quote_pipeline_state(session_id, rid, "live", freeze_rates=True)


def park_live_quote(session_id: str, revision_id: str | None = None) -> dict[str, Any]:
    rid = _revision_id(session_id, revision_id)
    snap = read_quote_pipeline_state(session_id, rid)
    if snap.get("state") != "live":
        return {"ok": False, "error": f"Cannot park from state {snap.get('state')!r}"}
    step = snap.get("pipeline_step") or _latest_step(session_id)
    return write_quote_pipeline_state(session_id, rid, "parked", pipeline_step=step, freeze_rates=True)


def resume_parked_quote(session_id: str, revision_id: str | None = None) -> dict[str, Any]:
    rid = _revision_id(session_id, revision_id)
    snap = read_quote_pipeline_state(session_id, rid)
    if snap.get("state") != "parked":
        return {"ok": False, "error": f"Cannot resume from state {snap.get('state')!r}"}
    return activate_live_quote(session_id, rid)


def begin_quote_detour(session_id: str, revision_id: str | None = None) -> dict[str, Any]:
    rid = _revision_id(session_id, revision_id)
    snap = read_quote_pipeline_state(session_id, rid)
    cur = snap.get("state") or "on_desk"
    if cur not in {"live", "handoff_ready", "on_desk", "blocked", "release_hold"}:
        return {"ok": False, "error": f"Cannot start detour from state {cur!r}"}
    step = snap.get("pipeline_step") or _latest_step(session_id)
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE quote_revisions
            SET detour_return_state = ?, pipeline_step = ?
            WHERE id = ?
            """,
            (cur, step, rid),
        )
    return write_quote_pipeline_state(session_id, rid, "detour", pipeline_step=step)


def end_quote_detour(session_id: str, revision_id: str | None = None, *, cancelled: bool = False) -> dict[str, Any]:
    rid = _revision_id(session_id, revision_id)
    snap = read_quote_pipeline_state(session_id, rid)
    if snap.get("state") != "detour":
        return {"ok": False, "error": "No master-data detour is open"}
    back = snap.get("detour_return_state") or "live"
    if cancelled and back == "live":
        back = "parked"
    step = snap.get("pipeline_step") or _latest_step(session_id)
    with db.connect() as conn:
        conn.execute(
            "UPDATE quote_revisions SET detour_return_state = ? WHERE id = ?",
            ("", rid),
        )
    return write_quote_pipeline_state(session_id, rid, back, pipeline_step=step)


def mark_quote_sending(session_id: str, revision_id: str | None = None) -> dict[str, Any]:
    rid = _revision_id(session_id, revision_id)
    snap = read_quote_pipeline_state(session_id, rid)
    if snap.get("state") in TERMINAL_STATES:
        return {"ok": False, "error": "Quote send already settled"}
    return write_quote_pipeline_state(session_id, rid, "sending")


def settle_quote_send_outcome(session_id: str, outcome: str, revision_id: str | None = None) -> dict[str, Any]:
    norm = (outcome or "").strip().lower()
    if norm not in TERMINAL_STATES:
        return {"ok": False, "error": f"invalid send outcome {outcome!r}"}
    rid = _revision_id(session_id, revision_id)
    snap = read_quote_pipeline_state(session_id, rid)
    if snap.get("state") != "sending":
        return {"ok": True, "skipped": True, "state": snap.get("state")}
    return write_quote_pipeline_state(session_id, rid, norm)


def set_revision_on_desk(
    session_id: str,
    revision_id: str,
    *,
    intake: bool = False,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Called when a new revision is persisted."""
    initial = "intake" if intake else "on_desk"

    def _apply(connection: sqlite3.Connection) -> None:
        live_id = _live_revision_for_session(connection, session_id)
        if live_id and live_id != revision_id:
            initial_state = "on_desk"
        else:
            initial_state = initial
        connection.execute(
            "UPDATE quote_revisions SET pipeline_state = ? WHERE id = ?",
            (initial_state, revision_id),
        )

    if conn is not None:
        _apply(conn)
        return
    with db.connect() as connection:
        _apply(connection)


def _latest_step(session_id: str) -> str:
    for mem in db.list_memories(session_id, limit=30):
        if mem.get("key") == "quote_step":
            return str(mem.get("value") or "")
    return ""


def pipeline_action(session_id: str, action: str, revision_id: str = "") -> dict[str, Any]:
    act = (action or "").strip().lower()
    rid = revision_id or None
    if act in {"get", "read", ""}:
        return read_quote_pipeline_state(session_id, rid)
    if act == "go_live":
        return activate_live_quote(session_id, rid)
    if act == "park":
        return park_live_quote(session_id, rid)
    if act == "resume":
        return resume_parked_quote(session_id, rid)
    if act == "detour_begin":
        return begin_quote_detour(session_id, rid)
    if act == "detour_end":
        return end_quote_detour(session_id, rid)
    if act == "detour_cancel":
        return end_quote_detour(session_id, rid, cancelled=True)
    return {"ok": False, "error": f"unknown pipeline action {action!r}"}
