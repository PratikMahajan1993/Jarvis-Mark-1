"""Local job library and RFQ rows.

Foundation only: SQLite CRUD + material/geometry lookup. No HTTP, intent,
agent, registry, or frontend wiring.

``margin`` is a REAL of percentage points (22.0 means 22%), not a 0–1
fraction. ``cycle_min`` is cycle time in minutes. Geometry notes are
machinist language (ops, holding, stock) — this module never invents
dimensions.

RFQ ``status`` is one of: intake | reasoned | pending | sent | dismissed.
``extract`` and ``similar_job_ids`` are JSON text in SQLite and native
list/dict objects in Python.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, TypedDict

from . import db
from .config import settings

RFQ_STATUSES = frozenset({"intake", "reasoned", "pending", "sent", "dismissed"})
DEMO_JOB_ID = "ace-pinion-blank"
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_RFQ_UPDATE_FIELDS = frozenset(
    {
        "mail_id",
        "conversation_id",
        "status",
        "extract",
        "similar_job_ids",
        "pending_reply",
        "deadline_iso",
    }
)


class Job(TypedDict):
    id: str
    customer: str
    part_name: str
    material: str
    machine: str
    cycle_min: float | None
    margin: float | None
    drawing_file: str
    geometry_notes: str
    created_at: str


class Rfq(TypedDict):
    id: str
    mail_id: str
    conversation_id: str
    status: str
    extract: dict[str, Any]
    similar_job_ids: list[str]
    pending_reply: str
    deadline_iso: str
    created_at: str
    updated_at: str


def _tokens(text: str) -> set[str]:
    return {match.group(0) for match in _TOKEN_RE.finditer((text or "").casefold()) if len(match.group(0)) >= 2}


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _job_row(row: Any) -> Job:
    data = dict(row)
    return {
        "id": data.get("id") or "",
        "customer": data.get("customer") or "",
        "part_name": data.get("part_name") or "",
        "material": data.get("material") or "",
        "machine": data.get("machine") or "",
        "cycle_min": _as_float(data.get("cycle_min")),
        "margin": _as_float(data.get("margin")),
        "drawing_file": data.get("drawing_file") or "",
        "geometry_notes": data.get("geometry_notes") or "",
        "created_at": data.get("created_at") or "",
    }


def _pack_json(value: Any, default: Any) -> str:
    """Store native objects as JSON text. Strings are parsed, then re-dumped."""
    if value is None:
        return json.dumps(default)
    if isinstance(value, str):
        if not value.strip():
            return json.dumps(default)
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("RFQ JSON is not valid") from exc
    return json.dumps(value)


def _load_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _load_id_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]


def _rfq_row(row: Any) -> Rfq:
    data = dict(row)
    return {
        "id": data.get("id") or "",
        "mail_id": data.get("mail_id") or "",
        "conversation_id": data.get("conversation_id") or "",
        "status": data.get("status") or "",
        "extract": _load_object(data.get("extract")),
        "similar_job_ids": _load_id_list(data.get("similar_job_ids")),
        "pending_reply": data.get("pending_reply") or "",
        "deadline_iso": data.get("deadline_iso") or "",
        "created_at": data.get("created_at") or "",
        "updated_at": data.get("updated_at") or "",
    }


def _validate_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized not in RFQ_STATUSES:
        allowed = ", ".join(sorted(RFQ_STATUSES))
        raise ValueError(f"Invalid RFQ status {status!r}; expected one of: {allowed}")
    return normalized


def seed_demo_job() -> Job | None:
    """Insert the Ace Designers demo job if the jobs table is empty.

    Idempotent: returns None when any job already exists.
    """
    with db.connect() as conn:
        count = int(conn.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"])
        if count:
            return None
        now = db.utc_now()
        conn.execute(
            """
            INSERT INTO jobs
            (id, customer, part_name, material, machine, cycle_min, margin,
             drawing_file, geometry_notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                DEMO_JOB_ID,
                "Ace Designers",
                "Input pinion blank",
                "18CrNiMo7-6",
                "Ace Designers turning cell",
                8.5,
                22.0,
                "ace-pinion-blank.pdf",
                (
                    "Soft-jaw hold on first-op OD. Face both ends square, "
                    "finish-turn OD leaving grind stock, drill and bore through, "
                    "chamfer OD and bore both sides. No thread this op. "
                    "Watch bore runout after the second-op flip."
                ),
                now,
            ),
        )
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (DEMO_JOB_ID,)).fetchone()
    return _job_row(row) if row else None


def create_job(
    *,
    customer: str,
    part_name: str,
    material: str,
    machine: str = "",
    cycle_min: float | None = None,
    margin: float | None = None,
    drawing_file: str = "",
    geometry_notes: str = "",
    job_id: str | None = None,
) -> Job:
    """Insert a historical job. ``margin`` is percentage points (22.0 = 22%)."""
    new_id = (job_id or "").strip() or uuid.uuid4().hex[:12]
    now = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs
            (id, customer, part_name, material, machine, cycle_min, margin,
             drawing_file, geometry_notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                customer or "",
                part_name or "",
                material or "",
                machine or "",
                cycle_min,
                margin,
                drawing_file or "",
                geometry_notes or "",
                now,
            ),
        )
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (new_id,)).fetchone()
    if not row:
        raise RuntimeError(f"Failed to read job {new_id} after insert")
    return _job_row(row)


def get_job(job_id: str) -> Job | None:
    if not job_id:
        return None
    if settings.masterdata_enabled:
        from .masterdata import routings as md_routings

        projected = md_routings.job_for_component_id(job_id)
        if projected is not None:
            return _job_row(projected)
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _job_row(row) if row else None


def list_jobs() -> list[Job]:
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    legacy = [_job_row(row) for row in rows]
    if not settings.masterdata_enabled:
        return legacy
    from .masterdata import routings as md_routings

    with db.connect() as conn:
        projected = md_routings.list_jobs_from_masterdata(conn)
    seen = {job["id"] for job in legacy}
    for job in projected:
        if job["id"] not in seen:
            legacy.append(_job_row(job))
            seen.add(job["id"])
    return legacy


def search_similar(material: str, geometry_notes: str = "", limit: int = 5) -> list[Job]:
    """Case-insensitive material match, then rank by geometry token overlap.

    Empty or unknown material returns []. No vector search.
    """
    needle = (material or "").strip()
    if not needle:
        return []
    cap = max(0, int(limit))
    if cap == 0:
        return []
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM jobs
            WHERE lower(material) = lower(?)
            ORDER BY created_at DESC
            """,
            (needle,),
        ).fetchall()
    matched = [_job_row(row) for row in rows]
    query_tokens = _tokens(geometry_notes)
    if query_tokens:
        matched.sort(
            key=lambda job: len(query_tokens & _tokens(job["geometry_notes"])),
            reverse=True,
        )
    return matched[:cap]


def create_rfq(
    *,
    mail_id: str = "",
    conversation_id: str = "",
    status: str = "intake",
    extract: dict[str, Any] | str | None = None,
    similar_job_ids: list[str] | str | None = None,
    pending_reply: str = "",
    deadline_iso: str = "",
    rfq_id: str | None = None,
) -> Rfq:
    new_id = (rfq_id or "").strip() or uuid.uuid4().hex[:12]
    now = db.utc_now()
    packed_status = _validate_status(status)
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO rfqs
            (id, mail_id, conversation_id, status, extract, similar_job_ids,
             pending_reply, deadline_iso, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                mail_id or "",
                conversation_id or "",
                packed_status,
                _pack_json(extract, {}),
                _pack_json(similar_job_ids, []),
                pending_reply or "",
                deadline_iso or "",
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM rfqs WHERE id = ?", (new_id,)).fetchone()
    if not row:
        raise RuntimeError(f"Failed to read RFQ {new_id} after insert")
    return _rfq_row(row)


def get_rfq(rfq_id: str) -> Rfq | None:
    if not rfq_id:
        return None
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM rfqs WHERE id = ?", (rfq_id,)).fetchone()
    return _rfq_row(row) if row else None


def list_rfqs(status: str | None = None) -> list[Rfq]:
    if status is None or status == "":
        with db.connect() as conn:
            rows = conn.execute("SELECT * FROM rfqs ORDER BY updated_at DESC").fetchall()
        return [_rfq_row(row) for row in rows]
    packed_status = _validate_status(status)
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM rfqs WHERE status = ? ORDER BY updated_at DESC",
            (packed_status,),
        ).fetchall()
    return [_rfq_row(row) for row in rows]


def update_rfq(rfq_id: str, **fields: Any) -> Rfq | None:
    unknown = sorted(key for key in fields if key not in _RFQ_UPDATE_FIELDS)
    if unknown:
        raise ValueError(f"Unknown RFQ field(s): {', '.join(unknown)}")
    if "status" in fields:
        fields = {**fields, "status": _validate_status(fields["status"])}
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM rfqs WHERE id = ?", (rfq_id,)).fetchone()
        if not row:
            return None
        current = _rfq_row(row)
        payload = {
            "mail_id": fields["mail_id"] if "mail_id" in fields else current["mail_id"],
            "conversation_id": fields["conversation_id"] if "conversation_id" in fields else current["conversation_id"],
            "status": fields["status"] if "status" in fields else current["status"],
            "extract": _pack_json(fields["extract"], {}) if "extract" in fields else json.dumps(current["extract"]),
            "similar_job_ids": (
                _pack_json(fields["similar_job_ids"], [])
                if "similar_job_ids" in fields
                else json.dumps(current["similar_job_ids"])
            ),
            "pending_reply": fields["pending_reply"] if "pending_reply" in fields else current["pending_reply"],
            "deadline_iso": fields["deadline_iso"] if "deadline_iso" in fields else current["deadline_iso"],
            "updated_at": db.utc_now(),
            "id": rfq_id,
        }
        conn.execute(
            """
            UPDATE rfqs
            SET mail_id = :mail_id,
                conversation_id = :conversation_id,
                status = :status,
                extract = :extract,
                similar_job_ids = :similar_job_ids,
                pending_reply = :pending_reply,
                deadline_iso = :deadline_iso,
                updated_at = :updated_at
            WHERE id = :id
            """,
            payload,
        )
        row = conn.execute("SELECT * FROM rfqs WHERE id = ?", (rfq_id,)).fetchone()
    return _rfq_row(row) if row else None
