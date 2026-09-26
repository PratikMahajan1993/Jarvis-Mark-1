"""Read entity cards and build quotable summaries from owner-confirmed facts only."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .. import db

_FACT_COLUMNS = "id, field, value, unit, source_kind, source_ref"

STALENESS_THRESHOLDS = {
    "machine_status": timedelta(hours=1),
    "vendor_turnaround": timedelta(days=7),
    "stock": timedelta(hours=4),
    "oee": timedelta(hours=2),
    "drawing_card": timedelta(days=30),
}

_RECALL_FIELDS = (
    ("material", "Material"),
    ("qty", "Qty"),
    ("scope", "Scope"),
    ("tolerances", "Tolerances"),
    ("routing", "Routing"),
    ("last_quoted", "Last quoted"),
)

_VISION_ALIASES = {
    "material": "material",
    "qty": "qty",
    "quantity": "qty",
    "scope": "scope",
    "tolerance": "tolerances",
    "tolerances": "tolerances",
    "routing": "routing",
    "heat treat": "heat_treat",
    "heat_treat": "heat_treat",
    "od": "od",
    "bore": "bore",
    "bore diameter": "bore_diameter",
}
_VISION_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 _/-]{0,40})\s*[:=]\s*(.+?)\s*$")


def card_primary_id(entity_type: str, entity_id: str) -> str:
    return f"card:{entity_type}:{entity_id}"


def parse_iso(raw: str | None) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_stale(card: dict[str, Any], kind: str, *, now: datetime | None = None) -> bool:
    """True when the card/projection is older than its kind threshold, or has no stamp."""
    updated = parse_iso(str(card.get("updated_at") or card.get("as_of") or ""))
    if updated is None:
        return True
    threshold = STALENESS_THRESHOLDS.get(kind, timedelta(days=7))
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current - updated > threshold


def ensure_card(conn: sqlite3.Connection, entity_type: str, entity_id: str) -> str:
    card_id = card_primary_id(entity_type, entity_id)
    now = db.utc_now()
    conn.execute(
        """
        INSERT OR IGNORE INTO entity_cards (
          id, entity_type, entity_id, summary, fact_count, confirmed_count,
          open_questions, updated_at
        ) VALUES (?, ?, ?, '', 0, 0, '[]', ?)
        """,
        (card_id, entity_type, entity_id, now),
    )
    return card_id


def refresh_card_counts(conn: sqlite3.Connection, card_id: str, now: str | None = None) -> None:
    stamp = now or db.utc_now()
    fact_count = conn.execute(
        """
        SELECT COUNT(*) AS n FROM entity_facts
        WHERE card_id = ? AND state != 'rejected'
        """,
        (card_id,),
    ).fetchone()["n"]
    confirmed = conn.execute(
        """
        SELECT COUNT(*) AS n FROM entity_facts
        WHERE card_id = ? AND state = 'confirmed'
        """,
        (card_id,),
    ).fetchone()["n"]
    conn.execute(
        """
        UPDATE entity_cards
        SET fact_count = ?, confirmed_count = ?, updated_at = ?
        WHERE id = ?
        """,
        (int(fact_count or 0), int(confirmed or 0), stamp, card_id),
    )


def _parse_open_questions(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _row_to_fact(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "field": row["field"],
        "value": row["value"],
        "unit": row["unit"] or "",
        "source_kind": row["source_kind"],
        "source_ref": row["source_ref"] or "",
    }


def read_card(
    entity_type: str,
    entity_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Load card metadata, confirmed facts (quotable list), and unconfirmed candidates."""
    et = (entity_type or "").strip()
    eid = (entity_id or "").strip()
    base: dict[str, Any] = {
        "entity_type": et,
        "entity_id": eid,
        "found": False,
        "facts": [],
        "candidates": [],
        "open_questions": [],
    }
    if not et or not eid:
        return base

    card_id = card_primary_id(et, eid)

    def _load(connection: sqlite3.Connection) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT id, entity_type, entity_id, summary, fact_count, confirmed_count,
                   open_questions, updated_at
            FROM entity_cards
            WHERE entity_type = ? AND entity_id = ?
            """,
            (et, eid),
        ).fetchone()
        if not row:
            return base

        open_q = _parse_open_questions(row["open_questions"])
        confirmed_rows = connection.execute(
            f"""
            SELECT {_FACT_COLUMNS}
            FROM entity_facts
            WHERE card_id = ? AND state = 'confirmed'
            ORDER BY field ASC, id ASC
            """,
            (card_id,),
        ).fetchall()
        candidate_rows = connection.execute(
            f"""
            SELECT {_FACT_COLUMNS}, state
            FROM entity_facts
            WHERE card_id = ? AND state = 'candidate'
            ORDER BY field ASC, id ASC
            """,
            (card_id,),
        ).fetchall()

        facts = [_row_to_fact(r) for r in confirmed_rows]
        candidates = [_row_to_fact(r) for r in candidate_rows]
        updated_at = row["updated_at"]
        freshness = {
            "kind": "drawing_card",
            "updated_at": updated_at,
            "stale": is_stale({"updated_at": updated_at}, "drawing_card"),
        }

        return {
            "found": True,
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "card": {
                "id": row["id"],
                "summary": row["summary"] or "",
                "fact_count": int(row["fact_count"] or 0),
                "confirmed_count": int(row["confirmed_count"] or 0),
                "updated_at": updated_at,
            },
            "facts": facts,
            "candidates": candidates,
            "open_questions": open_q,
            "freshness": freshness,
        }

    from ..memory.store import CARD_LOAD_BUDGET_MS, latency_budget

    with latency_budget("card_load", CARD_LOAD_BUDGET_MS):
        if conn is not None:
            return _load(conn)
        with db.connect() as connection:
            return _load(connection)


def _format_fact_line(fact: dict[str, Any]) -> str:
    unit = (fact.get("unit") or "").strip()
    value = (fact.get("value") or "").strip()
    field = (fact.get("field") or "").strip()
    if unit:
        rendered = f"{value} {unit}".strip()
    else:
        rendered = value
    if field:
        return f"{field}: {rendered} [{fact['id']}]"
    return f"{rendered} [{fact['id']}]"


def what_do_you_know(
    entity_type: str,
    entity_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> str:
    """Short answer from owner-confirmed facts only; never guess materials or dimensions."""
    payload = read_card(entity_type, entity_id, conn=conn)
    et = payload.get("entity_type") or entity_type
    eid = payload.get("entity_id") or entity_id
    label = f"{et}/{eid}".strip("/")

    if not payload.get("found"):
        return f"I do not have a knowledge card for {label} yet — what should I record?"

    quotable = [
        f
        for f in payload.get("facts") or []
        if f.get("source_kind") == "owner_confirmed"
    ]
    open_q = payload.get("open_questions") or []

    if not quotable:
        if open_q:
            questions = "; ".join(str(q) for q in open_q)
            return (
                f"I have a card for {label} but no owner-confirmed facts yet. "
                f"Still open: {questions}. What can you confirm?"
            )
        return (
            f"I have a card for {label} but no owner-confirmed facts yet — "
            "what should I record?"
        )

    lines = [_format_fact_line(f) for f in quotable]
    text = f"What we know about {label} (owner-confirmed): " + "; ".join(lines)
    if open_q:
        questions = "; ".join(str(q) for q in open_q)
        text += f" Still open: {questions}."
    return text


def knowledge_card_api_payload(entity_type: str, entity_id: str) -> dict[str, Any]:
    from ..config import settings

    if not settings.knowledge_cards_enabled:
        return {"enabled": False, "found": False, "facts": []}
    body = read_card(entity_type, entity_id)
    body["enabled"] = True
    return body


def _canon_vision_field(raw: str) -> str:
    key = " ".join((raw or "").strip().lower().replace("_", " ").split())
    if key in _VISION_ALIASES:
        return _VISION_ALIASES[key]
    if "tolerance" in key:
        return "tolerances"
    if "heat" in key and "treat" in key:
        return "heat_treat"
    return ""


def _pairs_from_mapping(payload: dict[str, Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw_key, raw_val in payload.items():
        field = _canon_vision_field(str(raw_key))
        value = str(raw_val or "").strip()
        if field and value and not value.lower().startswith("error"):
            pairs.append((field, value))
    return pairs


def parse_vision_fields(summary: str) -> list[tuple[str, str]]:
    """Pull known drawing fields out of a vision summary. Error text is not a fact."""
    text = (summary or "").strip()
    if not text or text.lower().startswith("error"):
        return []
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return _pairs_from_mapping(parsed)
    pairs: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = _VISION_LINE.match(line.strip(" \t-*"))
        if not match:
            continue
        field = _canon_vision_field(match.group(1))
        value = match.group(2).strip()
        if field and value and not value.lower().startswith("error"):
            pairs.append((field, value))
    return pairs


def record_vision_candidates(
    entity_type: str,
    entity_id: str,
    summary: str,
    *,
    source_ref: str = "",
) -> dict[str, Any]:
    """Store vision suggestions as candidate facts. They stay unquotable until confirmed."""
    et = (entity_type or "").strip() or "part_revision"
    eid = (entity_id or "").strip()
    pairs = parse_vision_fields(summary)
    if not eid or not pairs:
        return {"ok": True, "inserted": 0, "skipped": "no_fields"}
    now = db.utc_now()
    inserted = 0
    with db.connect() as conn:
        card_id = ensure_card(conn, et, eid)
        for field, value in pairs:
            existing = conn.execute(
                """
                SELECT id FROM entity_facts
                WHERE card_id = ? AND field = ? AND value = ?
                  AND state IN ('candidate', 'confirmed')
                LIMIT 1
                """,
                (card_id, field, value),
            ).fetchone()
            if existing:
                continue
            conn.execute(
                """
                INSERT INTO entity_facts (
                  id, card_id, field, value, unit, source_kind, source_ref,
                  confidence, state, created_at
                ) VALUES (?, ?, ?, ?, '', 'vision_suggestion', ?, 0, 'candidate', ?)
                """,
                (f"fact-{uuid.uuid4().hex[:12]}", card_id, field, value, source_ref, now),
            )
            inserted += 1
        if inserted:
            refresh_card_counts(conn, card_id, now)
    return {"ok": True, "inserted": inserted, "entity_type": et, "entity_id": eid}


def _latest_memory(session_id: str, key: str) -> str:
    if not session_id:
        return ""
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT value FROM memories
            WHERE session_id = ? AND key = ?
            ORDER BY id DESC LIMIT 1
            """,
            (session_id, key),
        ).fetchone()
    return str(row["value"]) if row else ""


def _fact_index(facts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for fact in facts:
        field = str(fact.get("field") or "")
        if field and field not in indexed:
            indexed[field] = fact
    return indexed


def _lookup_recall_fact(index: dict[str, dict[str, Any]], field: str) -> dict[str, Any] | None:
    if field in index:
        return index[field]
    if field == "qty":
        return index.get("quantity")
    if field == "tolerances":
        for key, fact in index.items():
            if "tolerance" in key:
                return fact
    return None


def _render_fact_value(fact: dict[str, Any]) -> str:
    value = str(fact.get("value") or "").strip()
    unit = str(fact.get("unit") or "").strip()
    if unit:
        return f"{value} {unit}".strip()
    return value


def _drawing_heading(entity_id: str) -> str:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT drawing_no, revision FROM part_revisions WHERE id = ? LIMIT 1",
            (entity_id,),
        ).fetchone()
    if row and str(row["drawing_no"] or "").strip():
        rev = str(row["revision"] or "").strip() or "?"
        return f"Drawing: {row['drawing_no']} rev {rev}"
    return f"Drawing: {entity_id}"


def recall_drawing_knowledge(
    session_id: str = "",
    drawing_sha256: str = "",
    entity_id: str = "",
) -> dict[str, Any]:
    """Deterministic plain-language summary. Owner-confirmed facts only; gaps stated plainly."""
    from ..memory.store import LAST_LATENCIES

    eid = (entity_id or "").strip()
    if not eid and (drawing_sha256 or "").strip():
        from .identity import resolve_drawing_identity

        identity = resolve_drawing_identity(drawing_sha256=drawing_sha256.strip())
        eid = identity.part_revision_id or identity.matched_part_revision_id or ""
    if not eid and session_id:
        eid = _latest_memory(session_id, "last_part_revision_id")
    if not eid:
        return {
            "ok": False,
            "error": "no_drawing",
            "summary": "I do not have a drawing card to recall yet.",
            "gaps": [],
        }

    payload = read_card("part_revision", eid)
    if not payload.get("found"):
        return {
            "ok": True,
            "entity_id": eid,
            "found": False,
            "summary": f"Drawing: {eid}. Gaps: no knowledge card yet.",
            "gaps": ["no knowledge card yet"],
            "confirmed": [],
            "latencies_ms": dict(LAST_LATENCIES),
        }

    confirmed = [
        fact
        for fact in payload.get("facts") or []
        if fact.get("source_kind") == "owner_confirmed"
    ]
    candidates = list(payload.get("candidates") or [])
    confirmed_idx = _fact_index(confirmed)
    candidate_idx = _fact_index(candidates)
    clauses = [_drawing_heading(eid)]
    gaps: list[str] = []
    confirmed_lines: list[dict[str, str]] = []
    for field, label in _RECALL_FIELDS:
        owned = _lookup_recall_fact(confirmed_idx, field)
        if owned:
            rendered = _render_fact_value(owned)
            clauses.append(f"{label}: {rendered} (confirmed)")
            confirmed_lines.append({"field": field, "label": label, "value": rendered})
            continue
        suggested = _lookup_recall_fact(candidate_idx, field)
        if suggested:
            rendered = _render_fact_value(suggested)
            clauses.append(f"{label}: {rendered} (unconfirmed — gap)")
            gaps.append(label.lower())
            continue
        gaps.append(label.lower())
    for fact in candidates:
        field = str(fact.get("field") or "")
        if field in {name for name, _label in _RECALL_FIELDS} or field == "quantity":
            continue
        if "tolerance" in field:
            continue
        label = field.replace("_", " ")
        if label and label not in gaps:
            gaps.append(label)
    for question in payload.get("open_questions") or []:
        text = str(question).strip()
        if text and text not in gaps:
            gaps.append(text)
    if gaps:
        clauses.append("Gaps: " + ", ".join(gaps))
    summary = ". ".join(clauses)
    if not summary.endswith("."):
        summary += "."
    card = payload.get("card") or {}
    freshness = payload.get("freshness") or {}
    return {
        "ok": True,
        "found": True,
        "entity_type": "part_revision",
        "entity_id": eid,
        "summary": summary,
        "confirmed": confirmed_lines,
        "gaps": gaps,
        "updated_at": card.get("updated_at"),
        "stale": bool(freshness.get("stale")),
        "latencies_ms": {
            "sql": LAST_LATENCIES.get("sql_lookup"),
            "card": LAST_LATENCIES.get("card_load"),
            "corpus": LAST_LATENCIES.get("lance_search"),
        },
    }
