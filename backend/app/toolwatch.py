"""Toolwatch v0 — deterministic shop-log capture and median-life alerts (M5)."""

from __future__ import annotations

import re
import sqlite3
import statistics
import uuid
from typing import Any, TypedDict

from . import db

SAMPLE_THRESHOLD = 3
INSUFFICIENT_HISTORY_TEXT = "not enough history for this tool/material pair"
_MODEL_VERSION = "v0"

_CHANGE_RE = re.compile(
    r"\b(?:changed?|swapped?|replaced?)\b.*\b(?:insert|tool)\b|\b(?:new|fresh)\s+insert\b",
    re.I,
)
_PIECES_RE = re.compile(
    r"\b(\d{1,6})\s*(?:pieces?|pcs?|parts?)\b",
    re.I,
)
_WEAR_MM_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:mm)\s*(?:wear|flank)",
    re.I,
)

_ONES: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_MULTIPLIERS: dict[str, int] = {"hundred": 100, "thousand": 1000}

_TELEGRAPHIC_PIECES_RE = re.compile(
    r"\b(" + "|".join(_ONES.keys()) + r")\s+(" + "|".join(_TENS.keys()) + r")\b",
    re.I,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _parse_spoken_integer(fragment: str) -> int | None:
    tokens = re.findall(r"[a-z]+", fragment.casefold())
    if not tokens:
        return None
    total = 0
    current = 0
    for tok in tokens:
        if tok in _ONES:
            current += _ONES[tok]
        elif tok in _TENS:
            current += _TENS[tok]
        elif tok in _MULTIPLIERS:
            if current == 0:
                current = 1
            current *= _MULTIPLIERS[tok]
            total += current
            current = 0
        else:
            return None
    return total + current


def parse_pieces_from_utterance(text: str) -> int | None:
    """Parse piece count; shop shorthand "two forty" => 240."""
    body = text or ""
    m = _PIECES_RE.search(body)
    if m:
        return int(m.group(1))
    tele = _TELEGRAPHIC_PIECES_RE.search(body)
    if tele:
        hundreds = _ONES.get(tele.group(1).casefold())
        tens = _TENS.get(tele.group(2).casefold())
        if hundreds is not None and tens is not None:
            return hundreds * 100 + tens
    spoken = re.search(
        r"\b((?:"
        + "|".join(list(_ONES.keys()) + list(_TENS.keys()) + list(_MULTIPLIERS.keys()))
        + r")(?:\s+(?:"
        + "|".join(list(_ONES.keys()) + list(_TENS.keys()) + list(_MULTIPLIERS.keys()) + ["and"])
        + r")){0,6})\s*(?:pieces?|pcs?|parts?)\b",
        body,
        re.I,
    )
    if spoken:
        val = _parse_spoken_integer(spoken.group(1))
        if val is not None:
            return val
    return None


def _extract_reason(text: str, *, pieces_span: tuple[int, int] | None) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    tail = raw
    if pieces_span:
        tail = raw[pieces_span[1] :].strip(" ,;")
    tail = re.sub(r"^(?:pieces?|pcs?|parts?)\b", "", tail, flags=re.I).strip(" ,;")
    if tail:
        return tail.strip(" .")
    for phrase in (
        r"edge\s+chipped?",
        r"flank\s+wear",
        r"built[- ]up?\s+edge",
        r"chatter",
        r"size\s+drift",
        r"planned\s+change",
    ):
        m = re.search(phrase, raw, re.I)
        if m:
            return m.group(0).strip()
    return ""


def _machine_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, name FROM machines ORDER BY length(name) DESC"
    ).fetchall()


def _score_machine_match(haystack: str, machine_name: str) -> int:
    name = (machine_name or "").casefold()
    text = (haystack or "").casefold()
    if not name or not text:
        return 0
    if name in text:
        return len(name) + 100
    name_tokens = {t for t in re.findall(r"[a-z0-9]+", name) if len(t) >= 3}
    text_tokens = set(re.findall(r"[a-z0-9]+", text))
    overlap = name_tokens & text_tokens
    return len(overlap) * 10 + sum(len(t) for t in overlap)


def resolve_machine_id(
    conn: sqlite3.Connection,
    *,
    utterance: str,
    open_job_machine: str = "",
) -> str | None:
    best_id: str | None = None
    best_score = 0
    for row in _machine_rows(conn):
        for source in (utterance, open_job_machine):
            score = _score_machine_match(source, row["name"])
            if score > best_score:
                best_score = score
                best_id = row["id"]
    if best_score <= 0:
        return None
    return best_id


def parse_tool_change_utterance(
    utterance: str,
    *,
    open_job_machine: str = "",
) -> dict[str, Any]:
    """Deterministic parse of a one-breath insert-change line (no model call)."""
    text = (utterance or "").strip()
    if not text:
        return {"ask": True, "reason": "what changed on which machine?"}
    if not _CHANGE_RE.search(text):
        return {"ask": True, "reason": "say that you changed the insert and how many pieces it ran"}

    pieces = parse_pieces_from_utterance(text)
    if pieces is None or pieces < 0:
        return {"ask": True, "reason": "how many pieces did the insert run?"}

    pieces_span: tuple[int, int] | None = None
    m = _PIECES_RE.search(text)
    if m:
        pieces_span = m.span()
    else:
        tele = _TELEGRAPHIC_PIECES_RE.search(text)
        if tele:
            pieces_span = tele.span()

    reason = _extract_reason(text, pieces_span=pieces_span)
    if not reason:
        return {"ask": True, "reason": "what was the reason for the change?"}

    wear_match = _WEAR_MM_RE.search(text)
    measured_wear_mm = float(wear_match.group(1)) if wear_match else None

    with db.connect() as conn:
        machine_id = resolve_machine_id(
            conn, utterance=text, open_job_machine=open_job_machine
        )
    if not machine_id:
        return {"ask": True, "reason": "which machine was that on?"}

    with db.connect() as conn:
        machine_name = conn.execute(
            "SELECT name FROM machines WHERE id = ?", (machine_id,)
        ).fetchone()
    reply_machine = machine_name["name"] if machine_name else machine_id

    return {
        "ok": True,
        "pieces_made": pieces,
        "reason": reason,
        "measured_wear_mm": measured_wear_mm,
        "machine_id": machine_id,
        "reply": f"Recorded insert change on {reply_machine} — {pieces} pieces, {reason}.",
    }


class ToolwatchTuple(TypedDict):
    tool_geometry: str
    insert_grade: str
    material_id: str
    operation: str


def _tuple_for_instance(conn: sqlite3.Connection, tool_instance_id: str) -> ToolwatchTuple | None:
    row = conn.execute(
        """
        SELECT t.geometry AS tool_geometry, ti.insert_grade, ti.material_id, ti.operation
        FROM tool_instances ti
        JOIN tools t ON t.id = ti.tool_id
        WHERE ti.id = ?
        """,
        (tool_instance_id,),
    ).fetchone()
    if row is None:
        return None
    return ToolwatchTuple(
        tool_geometry=row["tool_geometry"],
        insert_grade=row["insert_grade"],
        material_id=row["material_id"],
        operation=row["operation"],
    )


def _historical_pieces_for_tuple(
    conn: sqlite3.Connection, tup: ToolwatchTuple
) -> list[int]:
    rows = conn.execute(
        """
        SELECT tle.pieces_made
        FROM tool_life_events tle
        JOIN tool_instances ti ON ti.id = tle.tool_instance_id
        JOIN tools t ON t.id = ti.tool_id
        WHERE t.geometry = ?
          AND ti.insert_grade = ?
          AND ti.material_id = ?
          AND ti.operation = ?
        ORDER BY tle.changed_at
        """,
        (
            tup["tool_geometry"],
            tup["insert_grade"],
            tup["material_id"],
            tup["operation"],
        ),
    ).fetchall()
    return [int(r["pieces_made"]) for r in rows]


def _active_instance_on_machine(
    conn: sqlite3.Connection, machine_id: str
) -> sqlite3.Row | None:
    rows = conn.execute(
        """
        SELECT * FROM tool_instances
        WHERE machine_id = ? AND retired_at IS NULL
        ORDER BY fitted_at DESC
        """,
        (machine_id,),
    ).fetchall()
    if len(rows) == 1:
        return rows[0]
    return None


def _alert_for_life_used(life_used: float) -> str | None:
    if life_used >= 0.95:
        return "95"
    if life_used >= 0.80:
        return "80"
    return None


def jarvis_toolwatch_record_change(
    tool_instance_id: str,
    reason: str,
    pieces_made: int,
    measured_wear_mm: str | float = "",
) -> dict[str, Any]:
    tid = (tool_instance_id or "").strip()
    why = (reason or "").strip()
    if not tid:
        return {"ask": True, "reason": "tool_instance_id is required"}
    if not why:
        return {"ask": True, "reason": "reason is required"}
    try:
        pieces = int(pieces_made)
    except (TypeError, ValueError):
        return {"ask": True, "reason": "pieces_made must be an integer"}
    if pieces < 0:
        return {"ask": True, "reason": "pieces_made must be non-negative"}

    wear: float | None
    if measured_wear_mm is None or measured_wear_mm == "":
        wear = None
    else:
        try:
            wear = float(measured_wear_mm)
        except (TypeError, ValueError):
            return {"ask": True, "reason": "measured_wear_mm must be a number"}

    now = db.utc_now()
    with db.connect() as conn:
        inst = conn.execute(
            "SELECT * FROM tool_instances WHERE id = ?", (tid,)
        ).fetchone()
        if inst is None:
            return {"ask": True, "reason": "tool_instance_id not found"}
        if inst["retired_at"]:
            return {"ask": True, "reason": "tool_instance is already retired"}

        event_id = _new_id("tle")
        conn.execute(
            """
            INSERT INTO tool_life_events (
              id, tool_instance_id, changed_at, reason, pieces_made, measured_wear_mm
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, tid, now, why, pieces, wear),
        )
        conn.execute(
            "UPDATE tool_instances SET retired_at = ? WHERE id = ?",
            (now, tid),
        )

        new_id = _new_id("ti")
        conn.execute(
            """
            INSERT INTO tool_instances (
              id, tool_id, insert_grade, material_id, operation, machine_id,
              position, fitted_at, retired_at, pieces_since_fit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 0)
            """,
            (
                new_id,
                inst["tool_id"],
                inst["insert_grade"],
                inst["material_id"],
                inst["operation"],
                inst["machine_id"],
                inst["position"],
                now,
            ),
        )

    return {
        "ok": True,
        "event_id": event_id,
        "tool_instance_id": tid,
        "new_tool_instance_id": new_id,
        "pieces_made": pieces,
        "reason": why,
    }


def jarvis_toolwatch_status(
    machine_id: str = "",
    tool_instance_id: str = "",
) -> dict[str, Any]:
    mid = (machine_id or "").strip()
    tid = (tool_instance_id or "").strip()

    with db.connect() as conn:
        if tid:
            inst = conn.execute(
                "SELECT * FROM tool_instances WHERE id = ?", (tid,)
            ).fetchone()
        elif mid:
            inst = _active_instance_on_machine(conn, mid)
            if inst is None:
                rows = conn.execute(
                    """
                    SELECT id FROM tool_instances
                    WHERE machine_id = ? AND retired_at IS NULL
                    """,
                    (mid,),
                ).fetchall()
                if len(rows) > 1:
                    return {
                        "ask": True,
                        "reason": "multiple active tools on this machine — specify tool_instance_id",
                    }
                inst = None
        else:
            return {"ask": True, "reason": "machine_id or tool_instance_id is required"}

        if inst is None:
            return {"ask": True, "reason": "no active tool instance found"}

        if inst["retired_at"]:
            return {"ask": True, "reason": "tool_instance is retired"}

        tup = _tuple_for_instance(conn, inst["id"])
        if tup is None:
            return {"ask": True, "reason": "tool instance has no tool geometry"}

        history = _historical_pieces_for_tuple(conn, tup)
        current_pieces = int(inst["pieces_since_fit"] or 0)

        if len(history) < SAMPLE_THRESHOLD:
            basis = (
                f"v0 median-life needs {SAMPLE_THRESHOLD} prior changes; "
                f"have {len(history)} for {tup['tool_geometry']}/{tup['insert_grade']}/"
                f"{tup['material_id']}/{tup['operation']}"
            )
            conn.execute(
                """
                INSERT INTO toolwatch_predictions (
                  id, tool_instance_id, predicted_remaining_pieces,
                  confidence, basis, model_version, computed_at
                ) VALUES (?, ?, NULL, ?, ?, ?, ?)
                """,
                (
                    _new_id("twp"),
                    inst["id"],
                    "none",
                    basis,
                    _MODEL_VERSION,
                    db.utc_now(),
                ),
            )
            return {
                "ok": True,
                "status": INSUFFICIENT_HISTORY_TEXT,
                "life_used": None,
                "confidence": "none",
                "basis": basis,
                "pieces_since_fit": current_pieces,
                "sample_n": len(history),
            }

        median_life = float(statistics.median(history))
        if median_life <= 0:
            return {
                "ok": True,
                "status": INSUFFICIENT_HISTORY_TEXT,
                "life_used": None,
                "confidence": "none",
                "basis": "median life is zero",
                "pieces_since_fit": current_pieces,
                "sample_n": len(history),
            }

        life_used = current_pieces / median_life
        remaining = max(0, int(round(median_life - current_pieces)))
        alert = _alert_for_life_used(life_used)
        confidence = "medium" if len(history) < 8 else "high"
        basis = (
            f"median {int(round(median_life))} pieces from {len(history)} prior changes "
            f"({tup['tool_geometry']}, {tup['insert_grade']}, {tup['material_id']}, "
            f"{tup['operation']})"
        )

        conn.execute(
            """
            INSERT INTO toolwatch_predictions (
              id, tool_instance_id, predicted_remaining_pieces,
              confidence, basis, model_version, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _new_id("twp"),
                inst["id"],
                remaining,
                confidence,
                basis,
                _MODEL_VERSION,
                db.utc_now(),
            ),
        )

        out: dict[str, Any] = {
            "ok": True,
            "life_used": round(life_used, 4),
            "remaining": remaining,
            "confidence": confidence,
            "basis": basis,
            "median_life_pieces": int(round(median_life)),
            "pieces_since_fit": current_pieces,
            "sample_n": len(history),
            "tool_instance_id": inst["id"],
            "machine_id": inst["machine_id"],
        }
        if alert:
            out["alert"] = alert
        return out


def capture_tool_change_from_utterance(
    utterance: str,
    *,
    open_job_machine: str = "",
    tool_instance_id: str = "",
) -> dict[str, Any]:
    """Parse utterance; on success write tool_life_events (via record_change)."""
    parsed = parse_tool_change_utterance(
        utterance, open_job_machine=open_job_machine
    )
    if parsed.get("ask"):
        return parsed

    tid = (tool_instance_id or "").strip()
    with db.connect() as conn:
        if not tid:
            active = _active_instance_on_machine(conn, parsed["machine_id"])
            if active is None:
                rows = conn.execute(
                    """
                    SELECT id FROM tool_instances
                    WHERE machine_id = ? AND retired_at IS NULL
                    """,
                    (parsed["machine_id"],),
                ).fetchall()
                if not rows:
                    return {"ask": True, "reason": "no active tool on that machine"}
                if len(rows) > 1:
                    return {
                        "ask": True,
                        "reason": "multiple active tools — specify tool_instance_id",
                    }
                tid = rows[0]["id"]
            else:
                tid = active["id"]

    recorded = jarvis_toolwatch_record_change(
        tid,
        parsed["reason"],
        parsed["pieces_made"],
        measured_wear_mm=parsed.get("measured_wear_mm") or "",
    )
    if recorded.get("ask"):
        return recorded
    recorded["reply"] = parsed.get("reply", "")
    recorded["machine_id"] = parsed["machine_id"]
    return recorded
