"""Read entity cards and build quotable summaries from owner-confirmed facts only."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .. import db

_FACT_COLUMNS = "id, field, value, unit, source_kind, source_ref"


def card_primary_id(entity_type: str, entity_id: str) -> str:
    return f"card:{entity_type}:{entity_id}"


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

        return {
            "found": True,
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "card": {
                "id": row["id"],
                "summary": row["summary"] or "",
                "fact_count": int(row["fact_count"] or 0),
                "confirmed_count": int(row["confirmed_count"] or 0),
                "updated_at": row["updated_at"],
            },
            "facts": facts,
            "candidates": candidates,
            "open_questions": open_q,
        }

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
